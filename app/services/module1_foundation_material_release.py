"""Release identifiable foundation material profiles without archiving existing data."""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.models.enums import MaterialStatus, UnitType
from app.models.material import Material
from app.models.material_attribute import MaterialAttribute
from app.models.material_category import MaterialCategory
from app.models.material_quality_issue import MaterialQualityIssue
from app.services.audit_service import log_event
from app.services.module1_foundation_target_package import (
    PACKAGE, _normalized, _target_match, _unit, material_inventory_fingerprint, targets,
)

CATEGORY_MAP = {
    "foundation-reinforcing-steel": ("m1-ui-rebar-metal", "Арматура"),
    "foundation-structural-concrete": ("m1-ui-concrete-cement-mortar", "Товарный бетон"),
    "foundation-masonry-mortar": ("m1-ui-concrete-cement-mortar", "Строительные растворы"),
    "foundation-fbs-blocks": ("m1-ui-wall-precast-products", "Фундаментные блоки ФБС"),
    "foundation-fl-slabs": ("m1-ui-wall-precast-products", "Фундаментные плиты ФЛ"),
    "foundation-xps-insulation": ("m1-ui-insulation", "Экструзионный пенополистирол XPS"),
    "foundation-screw-piles": ("m1-ui-rebar-metal", "Винтовые сваи"),
    "foundation-rc-piles": ("m1-ui-wall-precast-products", "Железобетонные сваи"),
}


def releasable_foundation_targets():
    """Return profiles with an explicit base unit and an identifiable material type."""
    result, blocked = [], []
    for target in targets():
        if target.key.startswith("concrete-"):
            blocked.append((target.key, "Указан только класс бетона, состав и назначение не определены"))
        elif target.key == "pile-s-06":
            blocked.append((target.key, "Групповая роль соединительных элементов без спецификации"))
        elif not target.unit:
            blocked.append((target.key, "Не задана базовая единица или конкретное исполнение"))
        else:
            result.append(target)
    return result, blocked


async def release_foundation_materials(db, *, expected_inventory_fingerprint: str) -> dict:
    """Prepare a review-only M1 release; caller owns commit and backup checks."""
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd.m1.targets.20261110'))"))
    await db.execute(text("SET LOCAL lock_timeout = '3s'"))
    await db.execute(text("LOCK TABLE public.materials, public.material_attributes, public.material_categories IN EXCLUSIVE MODE"))
    if await material_inventory_fingerprint(db) != expected_inventory_fingerprint:
        raise ValueError("material inventory changed since the reviewed snapshot")
    items = list((await db.scalars(select(Material).options(selectinload(Material.attributes)))).all())
    active = [item for item in items if item.status not in {MaterialStatus.ARCHIVED, MaterialStatus.REJECTED}]
    candidates, blocked = releasable_foundation_targets()
    roots = {item.slug: item for item in (await db.scalars(select(MaterialCategory).where(
        MaterialCategory.parent_id.is_(None), MaterialCategory.status == "ACTIVE"))).all()}
    subcategories = list((await db.scalars(select(MaterialCategory).where(
        MaterialCategory.parent_id.is_not(None), MaterialCategory.status == "ACTIVE"))).all())
    units = {code: await _unit(db, code, kind) for code, kind in (
        ("m", UnitType.LENGTH), ("m2", UnitType.AREA), ("m3", UnitType.VOLUME), ("piece", UnitType.QUANTITY))}
    created, reused, ids = 0, 0, {}
    for target in candidates:
        _normalized(target)
        root_slug, sub_name = CATEGORY_MAP.get(target.category_slug, (
            "m1-ui-rebar-metal", "Комплектующие винтовых свай") if target.key in {"pile-s-04", "pile-s-05"} else (None, None))
        if not root_slug or root_slug not in roots:
            raise ValueError(f"no approved category for {target.key}")
        root = roots[root_slug]
        matching_subcategories = [item for item in subcategories if item.parent_id == root.id and item.name.casefold() == sub_name.casefold()]
        if len(matching_subcategories) > 1:
            raise ValueError(f"ambiguous subcategory for {target.key}")
        subcategory = matching_subcategories[0] if matching_subcategories else None
        if subcategory is None:
            subcategory = MaterialCategory(id=uuid5(NAMESPACE_URL, f"atom/foundation-subcategory/{root_slug}/{sub_name}"),
                name=sub_name, slug="fnd-ui-" + uuid5(NAMESPACE_URL, f"{root_slug}/{sub_name}").hex,
                parent_id=root.id, status="ACTIVE", level=1, sort_order=0)
            db.add(subcategory)
            await db.flush()
            subcategories.append(subcategory)
        matches = [item for item in active if _target_match(item, target)]
        if len(matches) > 1:
            raise ValueError(f"ambiguous existing identity: {target.key}")
        if matches:
            material = matches[0]
            attributes = {item.attribute_name: item.attribute_value for item in material.attributes}
            if attributes.get("registry_origin") != PACKAGE or attributes.get("registry_key") != target.key:
                raise ValueError(f"existing candidate requires identity review: {target.key}")
            if (material.category_id != root.id or material.subcategory_id != subcategory.id
                    or material.base_unit_id != units[target.unit].id
                    or any(attributes.get(name) != value for name, value in (*target.expected.items(), *target.properties))):
                raise ValueError(f"existing target changed and requires review: {target.key}")
            reused += 1
        else:
            material = Material(id=uuid5(NAMESPACE_URL, f"atom/{PACKAGE}/{target.key}"),
                canonical_name=target.title, category_id=root.id, subcategory_id=subcategory.id,
                base_unit_id=units[target.unit].id, status=MaterialStatus.DRAFT,
                description="Технический профиль для фундаментов. Характеристики и применимость требуют проверки.")
            material.attributes = [MaterialAttribute(attribute_name=name, attribute_value=value)
                for name, value in {**target.expected, **dict(target.properties), "registry_origin": PACKAGE,
                                    "registry_key": target.key}.items()]
            material.quality_issues = [MaterialQualityIssue(issue_type="TECHNICAL_REVIEW_REQUIRED", severity="HIGH",
                status="OPEN", reason="Не завершена техническая проверка и уточнение характеристик.",
                details={"missing": list(target.missing), "source": "техническое задание; проверка источника обязательна"})]
            db.add(material)
            await db.flush()
            await log_event(db, "M1_FOUNDATION_TARGET_DRAFT_CREATED", "Material", material.id, None,
                            {"package": PACKAGE, "key": target.key, "technical_review": "required"})
            active.append(material)
            created += 1
        ids[target.key] = str(material.id)
    await db.flush()
    return {"created": created, "reused": reused, "blocked": blocked, "target_ids": ids}
