"""Conservative writes for the M1 materials workspace."""

from decimal import Decimal
from decimal import InvalidOperation
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import selectinload

from app.models.catalog_product import CatalogProduct
from app.models.enums import MaterialStatus, VerificationStatus
from app.models.material import Material
from app.models.material_analog import MaterialAnalog
from app.models.material_attribute import MaterialAttribute
from app.models.material_category import MaterialCategory
from app.models.material_specification import MaterialSpecification
from app.models.module1_work_item import ManualCalculationPriceRevision
from app.models.module2_calculation_block import CalculationBlockTemplate, TechnologyCalculationBlock
from app.models.price_history import PriceHistory
from app.models.supplier_price import SupplierPrice
from app.models.unit import Unit
from app.models.unit_conversion_rule import UnitConversionRule
from app.services.audit_service import log_event
from app.services.module1_material_normalizer import normalize_raw_ingestion_item
from app.services.module1_material_ui_catalog import MATERIAL_UI_CATEGORIES
from app.services.module1_matching_dedup import build_match_candidate
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem

IDENTITY_FIELDS = frozenset({"concrete_class", "steel_class", "diameter_mm", "length_mm", "width_mm",
                             "height_mm", "thickness_mm", "density_class", "strength_class", "declared_mark"})


async def _has_vertical_unit_references(db, material_id: UUID) -> bool:
    # During staged rollout these tables may not exist yet. Never skip a table that does exist.
    connection = await db.connection()
    models = (ManualCalculationPriceRevision, TechnologyCalculationBlock, CalculationBlockTemplate)
    existing = await connection.run_sync(lambda sync: {model.__tablename__ for model in models
                                                        if inspect(sync).has_table(model.__tablename__)})
    for model in models:
        if model.__tablename__ in existing and await db.scalar(
                select(model.id).where(model.material_id == material_id).limit(1)):
            return True
    return False


class MaterialUIAttribute(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)
    unit_id: UUID | None = None
    value_type: Literal["text", "number", "dimension", "class", "unit"] = "text"


class MaterialUIConversion(BaseModel):
    from_unit_id: UUID
    coefficient: Decimal = Field(gt=0, max_digits=18, decimal_places=8)
    source: str = Field(min_length=1, max_length=500)


class MaterialUISpecification(BaseModel):
    id: UUID
    value: str = Field(min_length=1, max_length=500)


class MaterialUIWrite(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    category_id: UUID
    subcategory: str = Field(default="", max_length=255)
    description: str = ""
    purpose: str = Field(default="", max_length=500)
    base_unit_id: UUID
    attributes: list[MaterialUIAttribute] = Field(default_factory=list, max_length=100)
    conversions: list[MaterialUIConversion] = Field(default_factory=list, max_length=20)
    specifications: list[MaterialUISpecification] = Field(default_factory=list, max_length=100)
    analog_ids: list[UUID] | None = Field(default=None, max_length=100)


async def save_material_ui(db, payload: MaterialUIWrite, *, actor_id: UUID, material_id: UUID | None = None) -> Material:
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.m1.material.ui.write'))"))
    name = " ".join(payload.name.split())
    if not name:
        raise HTTPException(400, "Укажите наименование материала.")
    category = await db.get(MaterialCategory, payload.category_id)
    if not category or category.parent_id or category.status != "ACTIVE" or category.name not in MATERIAL_UI_CATEGORIES:
        raise HTTPException(400, "Выберите одну из утверждённых категорий.")
    unit = await db.get(Unit, payload.base_unit_id)
    if not unit:
        raise HTTPException(400, "Выберите существующую единицу измерения.")

    items = list((await db.scalars(select(Material).options(
        selectinload(Material.attributes), selectinload(Material.base_unit),
        selectinload(Material.specifications).selectinload(MaterialSpecification.template))
                                  .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED])))).all())
    current = next((item for item in items if item.id == material_id), None) if material_id else None
    if material_id and current is None:
        raise HTTPException(404, "Материал не найден.")
    if current:
        await db.execute(select(Material.id).where(Material.id == current.id).with_for_update())
    previous = ({"name": current.canonical_name, "category_id": str(current.category_id or ""),
                 "subcategory_id": str(current.subcategory_id or ""), "base_unit_id": str(current.base_unit_id or "")}
                if current else None)
    normalized_name = name.casefold()
    candidates = [item for item in items if item.id != material_id]
    if any(" ".join(item.canonical_name.split()).casefold() == normalized_name for item in candidates):
        raise HTTPException(409, "Материал с таким названием уже существует. Откройте его карточку.")
    candidate = normalize_raw_ingestion_item(Module1RawIngestionItem(
        legacy_source="raw_payload", raw_title=name, raw_category=category.name, raw_unit=unit.abbreviation,
    ))
    if current:
        original = normalize_raw_ingestion_item(Module1RawIngestionItem(
            legacy_source="raw_payload", raw_title=current.canonical_name,
            raw_unit=current.base_unit.abbreviation if current.base_unit else None,
        ))
        if (original.suggested_group_code and candidate.suggested_group_code
                and original.suggested_group_code != "unclassified" and candidate.suggested_group_code != "unclassified"
                and original.suggested_group_code != candidate.suggested_group_code):
            raise HTTPException(409, "Изменение меняет тип материала. Создайте отдельную карточку.")
        old_attributes = {item.attribute_name: item.attribute_value for item in current.attributes}
        for field in payload.attributes:
            if (field.name in IDENTITY_FIELDS and field.name in old_attributes
                    and field.value.strip().casefold() != old_attributes[field.name].strip().casefold()):
                raise HTTPException(409, "Изменение определяющей характеристики требует отдельной карточки.")
        specifications = {item.id: item for item in current.specifications}
        seen_specifications = set()
        for field in payload.specifications:
            specification = specifications.get(field.id)
            if not specification or field.id in seen_specifications or not field.value.strip():
                raise HTTPException(400, "Характеристика не принадлежит материалу или указана повторно.")
            seen_specifications.add(field.id)
            key = specification.template.field_key if specification.template else ""
            if key in IDENTITY_FIELDS and field.value.strip().casefold() != specification.value.strip().casefold():
                raise HTTPException(409, "Изменение определяющей характеристики требует отдельной карточки.")
            if field.value.strip() != specification.value:
                specification.value = field.value.strip()
                specification.verified_status = VerificationStatus.NEEDS_REVIEW
    elif payload.specifications:
        raise HTTPException(400, "Новая карточка не может использовать чужие характеристики.")
    snapshots = []
    for item in candidates:
        unit_code = item.base_unit.abbreviation if item.base_unit else None
        normalized = normalize_raw_ingestion_item(Module1RawIngestionItem(
            legacy_source="raw_payload", raw_title=item.canonical_name, raw_unit=unit_code,
        ))
        snapshots.append({
            "id": str(item.id), "canonical_name": item.canonical_name,
            "group_code": normalized.suggested_group_code,
            "normalized_characteristics": {a.attribute_name: a.attribute_value for a in item.attributes},
            "normalized_unit": normalized.normalized_unit,
            "manufacturer": item.manufacturer, "brand": item.brand,
        })
    match = build_match_candidate(candidate, snapshots)
    if match.confidence >= 90 and not match.conflicting_fields:
        raise HTTPException(409, "Найден похожий материал. Проверьте существующий каталог перед сохранением.")

    if current and current.base_unit_id != unit.id:
        for model in (SupplierPrice, CatalogProduct, PriceHistory, UnitConversionRule):
            if await db.scalar(select(model.id).where(model.material_id == current.id).limit(1)):
                raise HTTPException(409, "Нельзя изменить базовую единицу: есть цены, история или правила пересчёта.")
        if await _has_vertical_unit_references(db, current.id):
            raise HTTPException(409, "Нельзя изменить базовую единицу: есть расчётные цены или связи технологии.")

    subcategory_name = " ".join(payload.subcategory.split())
    selected_subcategory = None
    if subcategory_name:
        selected_subcategory = await db.scalar(select(MaterialCategory).where(
            MaterialCategory.parent_id == category.id,
            func.lower(MaterialCategory.name) == subcategory_name.lower(),
            MaterialCategory.status == "ACTIVE").limit(1))
        if selected_subcategory is None:
            slug = "m1-manual-" + uuid5(NAMESPACE_URL, f"{category.id}/{subcategory_name.casefold()}").hex
            if await db.scalar(select(MaterialCategory.id).where(MaterialCategory.slug == slug)):
                raise HTTPException(409, "Подкатегория с таким именем уже существует и недоступна.")
            selected_subcategory = MaterialCategory(name=subcategory_name, slug=slug, parent_id=category.id,
                                                    status="ACTIVE", level=1, sort_order=0)
            db.add(selected_subcategory)
            await db.flush()

    if current is None:
        current = Material(canonical_name=name, category_id=category.id, base_unit_id=unit.id,
                           status=MaterialStatus.DRAFT)
        db.add(current)
        await db.flush()
        await db.refresh(current, attribute_names=["attributes"])
    current.canonical_name = name
    current.category_id = category.id
    current.subcategory_id = selected_subcategory.id if selected_subcategory else None
    current.base_unit_id = unit.id
    current.description = payload.description.strip() or None

    values = list(payload.attributes)
    if payload.purpose.strip():
        values.append(MaterialUIAttribute(name="ui_purpose", value=payload.purpose.strip()))
    else:
        existing_purpose = next((item for item in current.attributes if item.attribute_name == "ui_purpose"), None)
        if existing_purpose:
            existing_purpose.attribute_value = ""
    names = set()
    for index, field in enumerate(values):
        key = field.name.strip()
        if not key or not field.value.strip() or key in names or (key.startswith(("registry_", "declared_")) and key != "ui_purpose") or key.endswith("_id"):
            raise HTTPException(400, "Некорректное или повторяющееся название характеристики.")
        names.add(key)
        if field.unit_id and not await db.get(Unit, field.unit_id):
            raise HTTPException(400, "Единица характеристики не найдена.")
        if field.value_type in {"number", "dimension"}:
            try:
                numeric = Decimal(field.value.strip().replace(",", "."))
                if not numeric.is_finite() or (field.value_type == "dimension" and numeric <= 0):
                    raise ValueError("invalid numeric characteristic")
            except (InvalidOperation, ValueError):
                raise HTTPException(400, "Укажите корректное числовое значение характеристики.")
            if field.value_type == "dimension" and not field.unit_id:
                raise HTTPException(400, "Для размера укажите единицу измерения.")
        existing = next((item for item in current.attributes if item.attribute_name == key), None)
        if existing:
            if existing.unit_id is not None and existing.unit_id != field.unit_id:
                raise HTTPException(409, "Нельзя изменить сохранённую единицу характеристики без проверки пересчёта.")
            existing.attribute_value, existing.unit_id, existing.value_type = field.value.strip(), field.unit_id, field.value_type
        else:
            current.attributes.append(MaterialAttribute(attribute_name=key, attribute_value=field.value.strip(),
                                                        unit_id=field.unit_id, value_type=field.value_type, sort_order=index))
    seen_units = set()
    for conversion in payload.conversions:
        from_unit = await db.get(Unit, conversion.from_unit_id)
        if not from_unit or from_unit.id == unit.id or from_unit.id in seen_units or not conversion.source.strip():
            raise HTTPException(400, "Укажите другую единицу, положительный коэффициент и его источник.")
        seen_units.add(from_unit.id)
        existing = await db.scalar(select(UnitConversionRule).where(
            UnitConversionRule.material_id == current.id, UnitConversionRule.from_unit == from_unit.abbreviation,
            UnitConversionRule.to_unit == unit.abbreviation, UnitConversionRule.status != "ARCHIVED").limit(1))
        if existing:
            if (existing.formula_type != "LINEAR_COEFFICIENT" or existing.coefficient != conversion.coefficient
                    or (existing.source or "") != conversion.source.strip()):
                if existing.status != "NEEDS_REVIEW" or existing.formula_type != "LINEAR_COEFFICIENT":
                    raise HTTPException(409, "Действующее правило пересчёта нельзя менять без отдельной проверки.")
                existing.coefficient = conversion.coefficient
                existing.source = conversion.source.strip()
            continue
        conversion_rule = UnitConversionRule(material_id=current.id, from_unit=from_unit.abbreviation,
                                             to_unit=unit.abbreviation, formula_type="LINEAR_COEFFICIENT",
                                             coefficient=conversion.coefficient, source=conversion.source.strip(),
                                             status="NEEDS_REVIEW")
        db.add(conversion_rule)
    if payload.analog_ids is not None:
        desired = set(payload.analog_ids)
        available = {item.id for item in items}
        if len(desired) != len(payload.analog_ids) or current.id in desired or not desired.issubset(available):
            raise HTTPException(400, "Проверьте выбранные аналоги материала.")
        links = (await db.scalars(select(MaterialAnalog).where(MaterialAnalog.material_id == current.id)
                                  .with_for_update())).all()
        active = [link for link in links if link.status not in {"ARCHIVED", "REJECTED"}]
        for link in active:
            if link.analog_material_id in available and link.analog_material_id not in desired:
                link.status = "ARCHIVED"
        for target in desired - {link.analog_material_id for link in active}:
            analog = MaterialAnalog(material_id=current.id, analog_material_id=target,
                                    relation_type="ANALOG", status="NEEDS_REVIEW")
            db.add(analog)
    await db.flush()
    await log_event(db, "material_ui_updated" if material_id else "material_ui_created", "Material", current.id,
                    actor_id, {"before": previous, "after": {"name": name, "category_id": str(category.id),
                     "subcategory_id": str(current.subcategory_id or ""), "base_unit_id": str(unit.id)},
                     "attribute_names": sorted(names), "conversion_count": len(payload.conversions),
                     "specification_ids": [str(item.id) for item in payload.specifications],
                     "analog_count": len(payload.analog_ids) if payload.analog_ids is not None else None})
    return current
