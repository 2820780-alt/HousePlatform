"""Import the explicitly reviewed FND-2 material candidates into M1."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.material_attribute import MaterialAttribute
from app.models.material_category import MaterialCategory
from app.models.unit import Unit
from app.services.audit_service import log_event
from app.services.module1_material_normalizer import normalize_title
from app.services.module1_unit_conversion_registry import normalize_unit


PACKAGE = "fnd2-materials-20261114"


@dataclass(frozen=True)
class MaterialCandidate:
    key: str
    name: str
    group: str
    unit: str
    characteristics: str


def category_slug(candidate: MaterialCandidate) -> str:
    key = candidate.key
    if key in {"BASE-04", "BASE-05"} or key.startswith("WPR-"):
        return "m1-ui-insulation"
    if key.startswith("BASE-"):
        return "m1-ui-bulk-materials"
    if key == "FORM-10":
        return "m1-ui-mixes-chemicals"
    if key.startswith("FORM-"):
        return "m1-ui-timber-sheets"
    if key.startswith("ARM-AUX-"):
        return "m1-ui-rebar-metal" if key in {"ARM-AUX-01", "ARM-AUX-02"} else "m1-ui-fasteners"
    if key.startswith(("DRN-", "PEN-")):
        return "m1-ui-pipes-drainage"
    raise ValueError(f"Unmapped material category: {key}")


def candidate_attributes(candidate: MaterialCandidate) -> dict[str, str]:
    result = {}
    for part in candidate.characteristics.split(";"):
        part = part.strip()
        if not part:
            continue
        key, separator, value = part.partition("=")
        if separator and key.strip() and value.strip():
            key = key.strip()
            if key in result:
                raise ValueError(f"Duplicate characteristic for {candidate.key}: {key}")
            result[key] = value.strip()
        else:
            result[f"Описание {len(result) + 1}"] = part
    return result


async def import_material_candidates(db, candidates: list[MaterialCandidate]) -> dict:
    """Stage drafts only; the caller controls transaction, backup and release."""
    if len(candidates) != 34 or len({c.key for c in candidates}) != 34:
        raise ValueError("Expected exactly 34 distinct reviewed material candidates")
    if any(not all((c.key, c.name, c.group, c.unit, c.characteristics)) for c in candidates):
        raise ValueError("Incomplete input row")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd2.materials'))"))
    await db.execute(text("SET LOCAL lock_timeout = '3s'"))
    await db.execute(text("LOCK TABLE materials, material_attributes, material_categories, units IN EXCLUSIVE MODE"))
    existing = list((await db.scalars(select(Material).options(selectinload(Material.attributes)).where(
        Material.status.not_in((MaterialStatus.ARCHIVED, MaterialStatus.REJECTED))))).all())
    categories = {c.slug: c for c in (await db.scalars(select(MaterialCategory).where(
        MaterialCategory.parent_id.is_(None), MaterialCategory.status == "ACTIVE"))).all()}
    subcategories = list((await db.scalars(select(MaterialCategory).where(
        MaterialCategory.parent_id.is_not(None), MaterialCategory.status == "ACTIVE"))).all())
    units = {u.abbreviation: u for u in (await db.scalars(select(Unit))).all()}
    result = {"created": 0, "reused": 0, "material_ids": {}}
    for candidate in candidates:
        slug = category_slug(candidate)
        root = categories.get(slug)
        unit_code = normalize_unit(candidate.unit)
        unit = units.get(unit_code)
        if root is None or unit is None:
            raise ValueError(f"Missing category or unit for {candidate.key}")
        subgroup = [s for s in subcategories if s.parent_id == root.id and s.name.casefold() == candidate.group.casefold()]
        if len(subgroup) > 1:
            raise ValueError(f"Ambiguous subcategory for {candidate.key}")
        if not subgroup:
            subgroup_id = uuid5(NAMESPACE_URL, f"atom/fnd2/subcategory/{slug}/{candidate.group}")
            sub = MaterialCategory(id=subgroup_id, name=candidate.group, slug="fnd2-" + subgroup_id.hex,
                                   parent_id=root.id, status="ACTIVE", level=1, sort_order=0)
            db.add(sub)
            await db.flush()
            subcategories.append(sub)
        else:
            sub = subgroup[0]
        attrs = candidate_attributes(candidate)
        matches = [m for m in existing if normalize_title(m.canonical_name).casefold() == normalize_title(candidate.name).casefold()]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous existing material: {candidate.key}")
        if matches:
            material = matches[0]
            stored = {a.attribute_name: a.attribute_value for a in material.attributes}
            if material.base_unit_id != unit.id or any(stored.get(k) != v for k, v in attrs.items()):
                raise ValueError(f"Existing material requires technical identity review: {candidate.key}")
            result["reused"] += 1
        else:
            material = Material(id=uuid5(NAMESPACE_URL, f"atom/{PACKAGE}/{candidate.key}"),
                canonical_name=candidate.name, category_id=root.id, subcategory_id=sub.id,
                base_unit_id=unit.id, status=MaterialStatus.DRAFT,
                description="Техническая карточка для фундаментов; отсутствующие характеристики требуют уточнения.")
            material.attributes = [MaterialAttribute(attribute_name=k, attribute_value=v, sort_order=i)
                                   for i, (k, v) in enumerate(attrs.items())]
            material.attributes.extend((MaterialAttribute(attribute_name="registry_origin", attribute_value=PACKAGE),
                                        MaterialAttribute(attribute_name="registry_key", attribute_value=candidate.key)))
            db.add(material)
            await db.flush()
            await log_event(db, "M1_FND2_DRAFT_CREATED", "Material", material.id, None,
                            {"package": PACKAGE, "key": candidate.key})
            existing.append(material)
            result["created"] += 1
        result["material_ids"][candidate.key] = str(material.id)
    return result
