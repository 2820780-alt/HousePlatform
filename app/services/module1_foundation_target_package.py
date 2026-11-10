"""Controlled, review-only M1 foundation targets; no products or prices are created."""

from __future__ import annotations

from dataclasses import dataclass
import re
from unicodedata import normalize
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import column, select, table, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import quoted_name

from app.models.enums import MaterialStatus, UnitType
from app.models.material import Material
from app.models.material_attribute import MaterialAttribute
from app.models.material_category import MaterialCategory
from app.models.material_quality_issue import MaterialQualityIssue
from app.models.module2_material_gap import Module2MaterialGap
from app.models.module2_technology import TechnologyDefaultAssumption, TechnologyMaterialRequirement
from app.models.unit import Unit
from app.services.audit_service import log_event
from app.services.module1_foundation_target_specs import additional_targets
from app.services.module1_material_normalizer import normalize_raw_ingestion_item
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem


PACKAGE = "FND_M1_TARGETS_20261110"

# These M1-owned history records remain intact when their test material is archived.
M1_HISTORY_REFERENCES = frozenset({
    ("public", "catalog_products", "material_id"),
    ("public", "material_aliases", "material_id"),
    ("public", "material_analogs", "material_id"),
    ("public", "material_analogs", "analog_material_id"),
    ("public", "material_attributes", "material_id"),
    ("public", "material_documents", "material_id"),
    ("public", "material_match_candidates", "candidate_material_id"),
    ("public", "material_quality_issues", "material_id"),
    ("public", "material_specifications", "material_id"),
    ("public", "price_history", "material_id"),
    ("public", "supplier_prices", "material_id"),
})


async def _externally_referenced_material_ids(db: AsyncSession) -> set[UUID]:
    """Fail closed: protect any non-history FK to the canonical M1 material table."""
    rows = (await db.execute(text("""
        SELECT child_ns.nspname, child.relname, child_attr.attname
        FROM pg_catalog.pg_constraint AS constraint_row
        JOIN pg_catalog.pg_class AS parent ON parent.oid = constraint_row.confrelid
        JOIN pg_catalog.pg_namespace AS parent_ns ON parent_ns.oid = parent.relnamespace
        JOIN pg_catalog.pg_class AS child ON child.oid = constraint_row.conrelid
        JOIN pg_catalog.pg_namespace AS child_ns ON child_ns.oid = child.relnamespace
        CROSS JOIN LATERAL unnest(constraint_row.conkey, constraint_row.confkey)
            AS key_pair(child_number, parent_number)
        JOIN pg_catalog.pg_attribute AS child_attr
            ON child_attr.attrelid = child.oid AND child_attr.attnum = key_pair.child_number
        JOIN pg_catalog.pg_attribute AS parent_attr
            ON parent_attr.attrelid = parent.oid AND parent_attr.attnum = key_pair.parent_number
        WHERE constraint_row.contype = 'f' AND parent_ns.nspname = 'public'
          AND parent.relname = 'materials' AND parent_attr.attname = 'id'
    """))).all()
    if not rows:
        raise ValueError("material FK inventory is empty; stop before archiving")
    protected: set[UUID] = set()
    for schema, table_name, column_name in rows:
        if (schema, table_name, column_name) in M1_HISTORY_REFERENCES:
            continue
        relation = table(quoted_name(table_name, True), column(quoted_name(column_name, True)),
                         schema=quoted_name(schema, True))
        field = relation.c[column_name]
        protected.update((await db.scalars(select(field).where(field.is_not(None)).distinct())).all())
    return protected


async def material_inventory_fingerprint(db: AsyncSession) -> str:
    """Fingerprint material rows and attributes against a restored backup snapshot."""
    return (await db.execute(text("""
        SELECT md5(
            (SELECT coalesce(string_agg(md5(to_jsonb(material_row)::text), ''
                ORDER BY md5(to_jsonb(material_row)::text)), '') FROM public.materials AS material_row)
            || '|' ||
            (SELECT coalesce(string_agg(md5(to_jsonb(attribute_row)::text), ''
                ORDER BY md5(to_jsonb(attribute_row)::text)), '') FROM public.material_attributes AS attribute_row)
        )
    """))).scalar_one()


@dataclass(frozen=True)
class Target:
    key: str
    title: str
    group: str
    category_hint: str
    unit: str | None
    expected: dict[str, str]
    missing: tuple[str, ...]
    properties: tuple[tuple[str, str], ...] = ()
    category_slug: str | None = None


def targets() -> tuple[Target, ...]:
    concrete = tuple(Target(
        key=f"concrete-{value.replace('.', '-')}",
        title=f"Бетон B{value} (класс; состав смеси требует уточнения)",
        group="ready_mix_concrete", category_hint="бетон", unit="m3",
        expected={"concrete_class": f"B{value}"},
        missing=("назначение", "подвижность", "морозостойкость", "водонепроницаемость", "проверка стандарта и области применения"),
    ) for value in ("7.5", "10", "15", "20", "22.5", "25", "30"))
    steel = tuple(Target(
        key=f"rebar-{grade.lower()}-{diameter}", title=f"Арматура {grade} Ø{diameter} мм",
        group="rebar", category_hint="арматура", unit="m",
        expected={"steel_class": grade, "diameter_mm": str(diameter)},
        missing=("профиль и исполнение", "масса погонного метра по проверенному сортаменту", "проверка стандарта и применимости"),
        properties=(("registry_code", f"RA-{index:02d}"), ("declared_theoretical_mass_kg_per_m", mass),
                    ("declared_standard", "ГОСТ 34028-2016"),
                    ("declared_source", "USER_PROVIDED_SPRINT_SPECIFICATION")),
        category_slug="foundation-reinforcing-steel",
    ) for index, (grade, diameter, mass) in enumerate((
        ("A500C", 6, "0.222"), ("A500C", 8, "0.395"), ("A500C", 10, "0.617"),
        ("A500C", 12, "0.888"), ("A500C", 14, "1.208"), ("A500C", 16, "1.578"),
        ("A500C", 18, "1.998"), ("A500C", 20, "2.466"),
        ("A240", 6, "0.222"), ("A240", 8, "0.395"), ("A240", 10, "0.617"),
    ), 1))
    return concrete + steel + tuple(Target(**item) for item in additional_targets())


def _normalized(target: Target):
    candidate = normalize_raw_ingestion_item(Module1RawIngestionItem(
        legacy_source="raw_payload", raw_title=target.title,
        raw_category=target.category_hint, raw_unit=target.unit,
    ))
    if target.group == "unclassified":
        return candidate
    if candidate.suggested_group_code != target.group or candidate.normalized_unit != target.unit:
        raise ValueError(f"normalizer could not safely identify {target.key}")
    for name, expected in target.expected.items():
        if str(candidate.normalized_characteristics.get(name)) != expected:
            raise ValueError(f"normalizer did not retain {name} for {target.key}")
    return candidate


def _target_match(material: Material, target: Target) -> bool:
    attrs = {item.attribute_name: item.attribute_value for item in material.attributes}
    if attrs.get("registry_origin") == PACKAGE:
        return attrs.get("registry_key") == target.key
    if target.group == "unclassified":
        return " ".join(normalize("NFKC", material.canonical_name).casefold().split()) == (
            " ".join(normalize("NFKC", target.title).casefold().split())
        )
    candidate = normalize_raw_ingestion_item(Module1RawIngestionItem(
        legacy_source="raw_payload", raw_title=material.canonical_name,
        raw_category=target.category_hint, raw_unit=target.unit,
    ))
    if candidate.suggested_group_code != target.group:
        return False
    values = {**{k: str(v) for k, v in candidate.normalized_characteristics.items()}, **attrs}
    return all(values.get(key) == value for key, value in target.expected.items())


async def _unit(db: AsyncSession, abbreviation: str, kind: UnitType) -> Unit:
    unit = await db.scalar(select(Unit).where(Unit.abbreviation == abbreviation))
    if unit:
        if unit.unit_type != kind:
            raise ValueError(f"existing {abbreviation} unit has conflicting dimension")
        return unit
    unit = Unit(id=uuid5(NAMESPACE_URL, f"atom/unit/{abbreviation}"),
                name={"m": "Метр", "m2": "Квадратный метр", "m3": "Кубический метр", "piece": "Штука"}[abbreviation],
                abbreviation=abbreviation, unit_type=kind, is_base=True)
    db.add(unit)
    await db.flush()
    return unit


async def apply_foundation_target_package(
    db: AsyncSession, *, expected_existing: int, expected_inventory_fingerprint: str,
    acknowledge_test_data: bool = False,
) -> dict:
    """Archive the test cohort and create identifiable DRAFT targets, without committing."""
    if not acknowledge_test_data:
        raise ValueError("explicit acknowledgement of test-data archival is required")
    if not re.fullmatch(r"[0-9a-f]{32}", expected_inventory_fingerprint):
        raise ValueError("a valid backup inventory fingerprint is required")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd.m1.targets.20261110'))"))
    await db.execute(text("SET LOCAL lock_timeout = '3s'"))
    await db.execute(text("LOCK TABLE public.materials, public.material_attributes, "
                          "public.module2_technology_default_assumptions IN EXCLUSIVE MODE"))
    materials = list((await db.scalars(select(Material).options(selectinload(Material.attributes)))).all())
    if len(materials) != expected_existing:
        raise ValueError("material inventory changed since backup; stop for a fresh audit")
    if await material_inventory_fingerprint(db) != expected_inventory_fingerprint:
        raise ValueError("material inventory fingerprint changed since backup; stop for a fresh audit")

    protected = set((await db.scalars(select(TechnologyMaterialRequirement.canonical_material_id)
        .where(TechnologyMaterialRequirement.canonical_material_id.is_not(None)))).all())
    protected.update(await _externally_referenced_material_ids(db))
    protected.update((await db.scalars(select(Module2MaterialGap.resolved_material_id)
        .where(Module2MaterialGap.resolved_material_id.is_not(None)))).all())
    assumptions = (await db.scalars(select(TechnologyDefaultAssumption).where(
        TechnologyDefaultAssumption.status == "ACTIVE", TechnologyDefaultAssumption.value_type == "MATERIAL"))).all()
    for item in assumptions:
        try:
            protected.add(UUID(str((item.default_value or {}).get("value"))))
        except (ValueError, TypeError):
            raise ValueError("invalid active M2 material default; stop before archiving")

    resolved: dict[str, Material] = {}
    for target in targets():
        _normalized(target)
        matches = [item for item in materials if _target_match(item, target)]
        if len(matches) > 1:
            raise ValueError(f"multiple possible M1 identities require review: {target.key}")
        if matches:
            item = matches[0]
            marker = {a.attribute_name: a.attribute_value for a in item.attributes}
            if marker.get("registry_origin") != PACKAGE:
                raise ValueError(f"existing candidate needs manual identity review: {target.key}")
            if item.status != MaterialStatus.DRAFT:
                raise ValueError(f"target status changed; manual review required: {target.key}")
            if any(marker.get(name) != value for name, value in target.expected.items()):
                raise ValueError(f"existing target identity changed; manual review required: {target.key}")
            resolved[target.key] = item

    slugs = {item.category_slug for item in targets() if item.category_slug}
    categories = {item.slug: item for item in (await db.scalars(select(MaterialCategory).where(
        MaterialCategory.slug.in_(slugs), MaterialCategory.status == "ACTIVE"))).all()}
    if set(categories) != slugs:
        raise ValueError("required active M1 foundation categories are missing")
    units = {"m": await _unit(db, "m", UnitType.LENGTH), "m2": await _unit(db, "m2", UnitType.AREA),
             "m3": await _unit(db, "m3", UnitType.VOLUME), "piece": await _unit(db, "piece", UnitType.QUANTITY)}

    archived = 0
    for material in materials:
        if material.id in protected or material.status in {MaterialStatus.ARCHIVED, MaterialStatus.REJECTED, MaterialStatus.VERIFIED}:
            continue
        if any(item.id == material.id for item in resolved.values()):
            continue
        old_status = material.status.value
        material.status = MaterialStatus.ARCHIVED
        await log_event(db, "M1_TEST_MATERIAL_ARCHIVED", "Material", material.id, None,
                        {"package": PACKAGE, "old_status": old_status, "reversible": True})
        archived += 1

    created = 0
    enriched = 0
    for target in targets():
        if target.key in resolved:
            material = resolved[target.key]
            if target.category_slug and material.category_id != categories[target.category_slug].id:
                raise ValueError(f"existing target category changed; manual review required: {target.key}")
            if target.unit and material.base_unit_id != units[target.unit].id:
                raise ValueError(f"existing target unit changed; manual review required: {target.key}")
            present = {item.attribute_name: item.attribute_value for item in material.attributes}
            added = []
            for name, value in target.properties:
                if name in present and present[name] != value:
                    raise ValueError(f"existing target property needs review: {target.key}/{name}")
                if name not in present:
                    material.attributes.append(MaterialAttribute(attribute_name=name, attribute_value=value))
                    added.append(name)
                    enriched += 1
            if added:
                await log_event(db, "M1_FOUNDATION_TARGET_DRAFT_ENRICHED", "Material", material.id, None,
                                {"package": PACKAGE, "key": target.key, "added_fields": added})
            continue
        material = Material(
            id=uuid5(NAMESPACE_URL, f"atom/{PACKAGE}/{target.key}"), canonical_name=target.title,
            category_id=categories[target.category_slug].id if target.category_slug else None,
            base_unit_id=units[target.unit].id if target.unit else None, status=MaterialStatus.DRAFT,
            description="Технический черновик без товара и цены. Характеристики и применимость требуют проверки.",
        )
        material.attributes = [MaterialAttribute(attribute_name=name, attribute_value=value)
            for name, value in {**target.expected, **dict(target.properties), "registry_origin": PACKAGE,
                                                   "registry_key": target.key}.items()]
        material.quality_issues = [MaterialQualityIssue(
            issue_type="TECHNICAL_REVIEW_REQUIRED", severity="HIGH", status="OPEN",
            reason="Не завершена техническая проверка и уточнение характеристик.",
            details={"missing": list(target.missing), "source": "техническое задание; проверка источника обязательна"},
        )]
        db.add(material)
        await db.flush()
        await log_event(db, "M1_FOUNDATION_TARGET_DRAFT_CREATED", "Material", material.id, None,
                        {"package": PACKAGE, "key": target.key, "technical_review": "required"})
        resolved[target.key] = material
        created += 1

    await db.flush()
    return {"archived": archived, "created": created, "reused": len(resolved) - created,
            "enriched_attributes": enriched, "protected_materials": len(protected),
            "target_ids": {key: str(value.id) for key, value in resolved.items()}}
