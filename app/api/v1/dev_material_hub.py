from datetime import datetime
from decimal import Decimal
from uuid import UUID
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.config import settings
from app.models.catalog_product import CatalogProduct
from app.models.enums import (
    AdminDecision,
    CatalogProductStatus,
    MatchCandidateStatus,
    MaterialStatus,
    SourceActionType,
    SourceStatus,
    SourceType,
    TaskStatus,
)
from app.models.material import Material
from app.models.material_alias import MaterialAlias
from app.models.material_category import MaterialCategory
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.source import Source
from app.models.source_task import SourceTask
from app.schemas.material_hub import SourceRead, SourceTaskRead
from app.services.source_task_runner import run_source_task
from app.services.material_classification import (
    apply_classification_categories,
    classify_catalog_product,
    needs_specification_review,
)
from app.services.material_taxonomy import (
    infer_baucenter_taxonomy,
    sync_extracted_specifications,
)
from app.services.rule_memory import build_rule_patterns, remember_material_rule
from app.services.audit_service import log_event


router = APIRouter(prefix="/dev/material-hub", tags=["dev-material-hub"])


DEFAULT_SOURCES = [
    {
        "name": "Baucenter",
        "source_type": SourceType.RETAIL,
        "url": "https://baucenter.ru/",
        "priority": 10,
    },
    {
        "name": "Bonolit",
        "source_type": SourceType.MANUFACTURER,
        "url": "https://bonolit.ru/",
        "priority": 20,
    },
    {
        "name": "Technonikol",
        "source_type": SourceType.MANUFACTURER,
        "url": "https://www.tn.ru/",
        "priority": 30,
    },
    {
        "name": "VseInstrumenti",
        "source_type": SourceType.RETAIL,
        "url": "https://www.vseinstrumenti.ru/",
        "priority": 40,
    },
    {
        "name": "Grand Line",
        "source_type": SourceType.MANUFACTURER,
        "url": "https://www.grandline.ru/katalog/",
        "priority": 50,
    },
    {
        "name": "YugKabel",
        "source_type": SourceType.RETAIL,
        "url": "https://yugkabel.ru/",
        "priority": 60,
    },
    {
        "name": "Tegola",
        "source_type": SourceType.MANUFACTURER,
        "url": "https://www.tegola.ru/",
        "priority": 70,
    },
    {
        "name": "VKBlock",
        "source_type": SourceType.MANUFACTURER,
        "url": "https://vkblock.ru/",
        "priority": 80,
    },
    {
        "name": "ETM",
        "source_type": SourceType.RETAIL,
        "url": "https://www.etm.ru/",
        "priority": 90,
    },
    {
        "name": "Knauf",
        "source_type": SourceType.MANUFACTURER,
        "url": "https://www.knauf.ru/",
        "priority": 100,
    },
    {
        "name": "Saturn-Yug",
        "source_type": SourceType.RETAIL,
        "url": "https://saturn-yug.ru/",
        "priority": 110,
    },
]


class DevRunTaskRequest(BaseModel):
    action_type: SourceActionType = SourceActionType.INITIAL_MATERIAL_SCAN
    source_id: UUID | None = None
    source_name: str | None = "Baucenter"
    parameters: dict | None = None


class DevRunBatchTaskRequest(BaseModel):
    action_type: SourceActionType = SourceActionType.INITIAL_MATERIAL_SCAN
    source_names: list[str] | None = None
    all_sources: bool = False
    parameters: dict | None = None


class DevRunTaskResponse(BaseModel):
    source: SourceRead
    task: SourceTaskRead


class DevRunBatchTaskResponse(BaseModel):
    tasks: list[DevRunTaskResponse]


class DevSourceManageRequest(BaseModel):
    name: str
    source_type: SourceType = SourceType.RETAIL
    url: str | None = None
    priority: int = 100
    status: SourceStatus = SourceStatus.ACTIVE


class DevSourceUpdateRequest(BaseModel):
    name: str | None = None
    source_type: SourceType | None = None
    url: str | None = None
    priority: int | None = None
    status: SourceStatus | None = None


class DevModerationDecision(BaseModel):
    reason: str | None = None
    canonical_name_choice: str | None = "material"
    canonical_name: str | None = None


class DevReclassifyResponse(BaseModel):
    processed: int
    updated: int


class DevManualPriceRequest(BaseModel):
    material_id: UUID
    price: Decimal
    currency: str = "RUB"
    unit: str | None = None
    region: str | None = None
    availability: str | None = None
    source_name: str = "Manual Price"


class DevManualPriceResponse(BaseModel):
    catalog_product_id: UUID
    price_history_id: UUID
    status: str


class DevMaterialEditRequest(BaseModel):
    material_id: UUID
    canonical_name: str
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    brand: str | None = None
    manufacturer: str | None = None
    comment: str | None = None


class DevMaterialEditResponse(BaseModel):
    material_id: UUID
    status: str


class DevMaterialBulkEditRequest(BaseModel):
    material_ids: list[UUID]
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    brand: str | None = None
    manufacturer: str | None = None
    comment: str | None = None


class DevMaterialBulkEditResponse(BaseModel):
    updated: int
    status: str


class DevCategoryManageRequest(BaseModel):
    name: str
    parent_id: UUID | None = None
    description: str | None = None
    sort_order: int = 0
    status: str = "ACTIVE"


class DevCategoryMergeRequest(BaseModel):
    target_category_id: UUID
    comment: str | None = None


class DevCategoryResponse(BaseModel):
    category_id: UUID
    status: str


class DevCategoryMergeResponse(BaseModel):
    source_category_id: UUID
    target_category_id: UUID
    moved_material_categories: int
    moved_material_subcategories: int
    moved_children: int
    status: str


def _ensure_development() -> None:
    if settings.APP_ENV != "development":
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/sources/defaults", response_model=list[SourceRead], status_code=201)
async def create_dev_default_sources(db: DBSession):
    _ensure_development()
    sources: list[Source] = []

    for source_data in DEFAULT_SOURCES:
        result = await db.execute(select(Source).where(Source.name == source_data["name"]))
        source = result.scalar_one_or_none()
        if not source:
            source = Source(
                name=source_data["name"],
                source_type=source_data["source_type"],
                url=source_data["url"],
                priority=source_data["priority"],
                status=SourceStatus.ACTIVE,
            )
            db.add(source)
            await db.flush()
            await db.refresh(source)
        sources.append(source)

    return sources


@router.post("/sources", response_model=SourceRead, status_code=201)
async def create_dev_source(data: DevSourceManageRequest, db: DBSession):
    _ensure_development()
    result = await db.execute(select(Source).where(Source.name == data.name))
    source = result.scalar_one_or_none()
    if source:
        raise HTTPException(status_code=409, detail="Source with this name already exists")
    source = Source(**data.model_dump())
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


@router.patch("/sources/{source_id}", response_model=SourceRead)
async def update_dev_source(source_id: UUID, data: DevSourceUpdateRequest, db: DBSession):
    _ensure_development()
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


@router.post("/sources/{source_id}/status/{status}", response_model=SourceRead)
async def set_dev_source_status(source_id: UUID, status: SourceStatus, db: DBSession):
    _ensure_development()
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.status = status
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


@router.post("/run", response_model=DevRunTaskResponse, status_code=201)
async def run_dev_material_hub_task(data: DevRunTaskRequest, db: DBSession):
    _ensure_development()
    source = await _get_or_create_source(db, data)
    parameters = _sanitize_task_parameters(data.action_type, data.parameters or _default_parameters(data.action_type))

    task = await _create_and_run_task(db, source, data.action_type, parameters)
    return DevRunTaskResponse(source=source, task=task)


@router.post("/run-batch", response_model=DevRunBatchTaskResponse, status_code=201)
async def run_dev_material_hub_batch(data: DevRunBatchTaskRequest, db: DBSession):
    _ensure_development()
    sources = await _resolve_batch_sources(db, data)
    if not sources:
        raise HTTPException(status_code=400, detail="No sources selected")
    parameters = _sanitize_task_parameters(data.action_type, data.parameters or _default_parameters(data.action_type))

    results: list[DevRunTaskResponse] = []
    for source in sources:
        task = await _create_and_run_task(db, source, data.action_type, parameters)
        results.append(DevRunTaskResponse(source=source, task=task))
    return DevRunBatchTaskResponse(tasks=results)


@router.post("/reclassify", response_model=DevReclassifyResponse)
async def reclassify_dev_materials(db: DBSession):
    _ensure_development()
    result = await db.execute(
        select(CatalogProduct)
        .options(selectinload(CatalogProduct.material))
        .where(CatalogProduct.material_id.is_not(None))
    )
    products = list(result.scalars().all())
    updated = 0
    for product in products:
        if not product.material:
            continue
        classification = classify_catalog_product(product)
        needs_review = needs_specification_review(product, classification)
        category, subcategory = await apply_classification_categories(db, classification)
        taxonomy_path = infer_baucenter_taxonomy(product.raw_name, product.raw_category, product.external_url)
        specification_category = subcategory or category
        changed = False
        material_is_locked = product.material.status == MaterialStatus.VERIFIED
        if (
            not material_is_locked
            and classification.canonical_name
            and product.material.canonical_name != classification.canonical_name
        ):
            product.material.canonical_name = classification.canonical_name
            changed = True
        if not material_is_locked and category and product.material.category_id != category.id:
            product.material.category_id = category.id
            changed = True
        if not material_is_locked and subcategory and product.material.subcategory_id != subcategory.id:
            product.material.subcategory_id = subcategory.id
            changed = True
        if not material_is_locked and classification.brand and product.material.brand != classification.brand:
            product.material.brand = classification.brand
            changed = True
        if not material_is_locked and classification.manufacturer and product.material.manufacturer != classification.manufacturer:
            product.material.manufacturer = classification.manufacturer
            changed = True
        if classification.region and product.region != classification.region:
            product.region = classification.region
            changed = True
        if needs_review and product.status == CatalogProductStatus.ACTIVE:
            product.status = CatalogProductStatus.NEEDS_REVIEW
            changed = True
        if needs_review and product.material.status == MaterialStatus.AUTO_CREATED:
            product.material.status = MaterialStatus.NEEDS_REVIEW
            changed = True
        await sync_extracted_specifications(
            db,
            product.material,
            product.source_id,
            specification_category,
            taxonomy_path,
            product.raw_name,
            product.raw_category,
        )
        if changed:
            db.add(product.material)
            db.add(product)
            updated += 1
    await db.flush()
    return DevReclassifyResponse(processed=len(products), updated=updated)


@router.post("/manual-price", response_model=DevManualPriceResponse, status_code=201)
async def save_dev_manual_price(data: DevManualPriceRequest, db: DBSession):
    _ensure_development()
    if data.price < 0:
        raise HTTPException(status_code=400, detail="Price must be positive")

    material_result = await db.execute(
        select(Material)
        .options(selectinload(Material.category))
        .where(Material.id == data.material_id)
    )
    material = material_result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    material_id = material.id
    material_name = material.canonical_name
    material_category_name = material.category.name if material.category else None
    material_brand = material.brand
    material_manufacturer = material.manufacturer

    source = await _get_or_create_manual_price_source(db, data.source_name)
    source_id = source.id
    external_id = _manual_price_external_id(material_id, data.region, data.unit, source_id)
    product_result = await db.execute(
        select(CatalogProduct).where(
            CatalogProduct.source_id == source_id,
            CatalogProduct.external_id == external_id,
        )
    )
    product = product_result.scalar_one_or_none()
    status = "updated" if product else "created"
    now = datetime.utcnow()

    if not product:
        product = CatalogProduct(
            source_id=source_id,
            material_id=material_id,
            external_id=external_id,
            raw_name=material_name,
            normalized_name=material_name.lower(),
            raw_category=material_category_name,
            raw_brand=material_brand,
            raw_manufacturer=material_manufacturer,
            match_confidence=Decimal("1.0"),
            status=CatalogProductStatus.ACTIVE,
        )
        db.add(product)

    product.material_id = material_id
    product.raw_name = material_name
    product.normalized_name = material_name.lower()
    product.price = data.price
    product.currency = (data.currency or "RUB").upper()
    product.unit = data.unit
    product.region = data.region
    product.availability = data.availability
    product.status = CatalogProductStatus.ACTIVE
    product.updated_at = now
    db.add(product)
    await db.flush()
    await db.refresh(product)

    history = PriceHistory(
        material_id=material_id,
        catalog_product_id=product.id,
        source_id=source_id,
        price=data.price,
        currency=product.currency,
        unit=data.unit,
        region=data.region,
        availability=data.availability,
        collected_at=now,
    )
    db.add(history)
    await db.flush()
    await db.refresh(history)

    return DevManualPriceResponse(
        catalog_product_id=product.id,
        price_history_id=history.id,
        status=status,
    )


@router.post("/material/edit", response_model=DevMaterialEditResponse)
async def edit_dev_material(data: DevMaterialEditRequest, db: DBSession):
    _ensure_development()
    canonical_name = data.canonical_name.strip()
    if not canonical_name:
        raise HTTPException(status_code=400, detail="Canonical name is required")

    result = await db.execute(
        select(Material)
        .options(selectinload(Material.catalog_products))
        .where(Material.id == data.material_id)
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    category = await _get_category_or_none(db, data.category_id)
    subcategory = await _get_category_or_none(db, data.subcategory_id)
    if subcategory and category and subcategory.parent_id != category.id:
        raise HTTPException(status_code=400, detail="Subcategory does not belong to category")

    old_values = {
        "canonical_name": material.canonical_name,
        "category_id": str(material.category_id) if material.category_id else None,
        "subcategory_id": str(material.subcategory_id) if material.subcategory_id else None,
        "brand": material.brand,
        "manufacturer": material.manufacturer,
        "status": material.status.value,
    }

    material.canonical_name = canonical_name
    material.category_id = category.id if category else None
    material.subcategory_id = subcategory.id if subcategory else None
    material.brand = data.brand.strip() if data.brand else None
    material.manufacturer = data.manufacturer.strip() if data.manufacturer else None
    material.status = MaterialStatus.VERIFIED
    db.add(material)

    normalized_name = canonical_name.lower()
    alias_result = await db.execute(
        select(MaterialAlias).where(
            MaterialAlias.material_id == material.id,
            MaterialAlias.normalized_name == normalized_name,
        )
    )
    alias = alias_result.scalar_one_or_none()
    if not alias:
        alias = MaterialAlias(
            material_id=material.id,
            original_name=canonical_name,
            normalized_name=normalized_name,
            confidence_score=Decimal("1.0"),
        )
        db.add(alias)

    patterns = build_rule_patterns(canonical_name, material.canonical_name)
    for product in material.catalog_products:
        patterns.extend(build_rule_patterns(product.raw_name, product.normalized_name, product.raw_category))
    await remember_material_rule(
        db,
        material,
        patterns,
        source="admin_edit",
        attributes={"comment": data.comment or ""},
    )
    await log_event(
        db,
        "material_admin_edit",
        "Material",
        material.id,
        details={
            "old": old_values,
            "new": {
                "canonical_name": material.canonical_name,
                "category_id": str(material.category_id) if material.category_id else None,
                "subcategory_id": str(material.subcategory_id) if material.subcategory_id else None,
                "brand": material.brand,
                "manufacturer": material.manufacturer,
                "status": material.status.value,
            },
            "comment": data.comment or "",
        },
    )

    await db.flush()
    return DevMaterialEditResponse(material_id=material.id, status="updated")


@router.post("/material/bulk-edit", response_model=DevMaterialBulkEditResponse)
async def bulk_edit_dev_materials(data: DevMaterialBulkEditRequest, db: DBSession):
    _ensure_development()
    if not data.material_ids:
        raise HTTPException(status_code=400, detail="No materials selected")

    category = await _get_category_or_none(db, data.category_id)
    subcategory = await _get_category_or_none(db, data.subcategory_id)
    if subcategory and category and subcategory.parent_id != category.id:
        raise HTTPException(status_code=400, detail="Subcategory does not belong to category")

    result = await db.execute(
        select(Material)
        .options(selectinload(Material.catalog_products))
        .where(Material.id.in_(data.material_ids))
    )
    materials = list(result.scalars().all())
    if not materials:
        raise HTTPException(status_code=404, detail="Materials not found")

    brand = data.brand.strip() if data.brand else None
    manufacturer = data.manufacturer.strip() if data.manufacturer else None
    audit_items: list[dict] = []
    for material in materials:
        old_values = {
            "material_id": str(material.id),
            "canonical_name": material.canonical_name,
            "category_id": str(material.category_id) if material.category_id else None,
            "subcategory_id": str(material.subcategory_id) if material.subcategory_id else None,
            "brand": material.brand,
            "manufacturer": material.manufacturer,
            "status": material.status.value,
        }
        if category:
            material.category_id = category.id
        if subcategory:
            material.subcategory_id = subcategory.id
        if brand is not None:
            material.brand = brand
        if manufacturer is not None:
            material.manufacturer = manufacturer
        material.status = MaterialStatus.VERIFIED
        db.add(material)
        patterns = build_rule_patterns(material.canonical_name)
        for product in material.catalog_products:
            patterns.extend(build_rule_patterns(product.raw_name, product.normalized_name, product.raw_category))
        await remember_material_rule(
            db,
            material,
            patterns,
            source="admin_bulk_edit",
            attributes={"comment": data.comment or ""},
        )
        audit_items.append({
            "old": old_values,
            "new": {
                "material_id": str(material.id),
                "category_id": str(material.category_id) if material.category_id else None,
                "subcategory_id": str(material.subcategory_id) if material.subcategory_id else None,
                "brand": material.brand,
                "manufacturer": material.manufacturer,
                "status": material.status.value,
            },
        })

    await log_event(
        db,
        "material_admin_bulk_edit",
        "Material",
        details={
            "count": len(materials),
            "items": audit_items,
            "comment": data.comment or "",
        },
    )

    await db.flush()
    return DevMaterialBulkEditResponse(updated=len(materials), status="updated")


@router.post("/categories", response_model=DevCategoryResponse, status_code=201)
async def create_dev_category(data: DevCategoryManageRequest, db: DBSession):
    _ensure_development()
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name is required")
    parent = await _get_category_or_none(db, data.parent_id)
    slug = await _unique_category_slug(db, name, data.parent_id)
    category = MaterialCategory(
        name=name,
        slug=slug,
        parent_id=parent.id if parent else None,
        level=(parent.level + 1) if parent else 0,
        description=data.description,
        sort_order=data.sort_order,
        status=_normalize_category_status(data.status),
    )
    db.add(category)
    await db.flush()
    await log_event(
        db,
        "category_created",
        "MaterialCategory",
        category.id,
        details={"name": category.name, "parent_id": str(category.parent_id) if category.parent_id else None},
    )
    return DevCategoryResponse(category_id=category.id, status="created")


@router.patch("/categories/{category_id}", response_model=DevCategoryResponse)
async def update_dev_category(category_id: UUID, data: DevCategoryManageRequest, db: DBSession):
    _ensure_development()
    category = await _get_category_or_none(db, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    parent = await _get_category_or_none(db, data.parent_id)
    if parent and parent.id == category.id:
        raise HTTPException(status_code=400, detail="Category cannot be parent of itself")

    old_values = _category_audit_values(category)
    category.name = data.name.strip() or category.name
    category.parent_id = parent.id if parent else None
    category.level = (parent.level + 1) if parent else 0
    category.description = data.description
    category.sort_order = data.sort_order
    category.status = _normalize_category_status(data.status)
    db.add(category)
    await db.flush()
    await log_event(
        db,
        "category_updated",
        "MaterialCategory",
        category.id,
        details={"old": old_values, "new": _category_audit_values(category)},
    )
    return DevCategoryResponse(category_id=category.id, status="updated")


@router.post("/categories/{category_id}/archive", response_model=DevCategoryResponse)
async def archive_dev_category(category_id: UUID, db: DBSession):
    _ensure_development()
    category = await _get_category_or_none(db, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    category.status = "ARCHIVED"
    db.add(category)
    await db.flush()
    await log_event(db, "category_archived", "MaterialCategory", category.id, details=_category_audit_values(category))
    return DevCategoryResponse(category_id=category.id, status="archived")


@router.delete("/categories/{category_id}", response_model=DevCategoryResponse)
async def delete_dev_category(category_id: UUID, db: DBSession):
    _ensure_development()
    category = await _get_category_or_none(db, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    linked_count = await _category_linked_count(db, category.id)
    child_count = await db.scalar(select(func.count(MaterialCategory.id)).where(MaterialCategory.parent_id == category.id))
    if linked_count or child_count:
        raise HTTPException(status_code=409, detail="Category has linked materials or child categories; archive or merge it")
    await db.execute(delete(MaterialCategory).where(MaterialCategory.id == category.id))
    await log_event(db, "category_deleted", "MaterialCategory", category.id, details=_category_audit_values(category))
    return DevCategoryResponse(category_id=category.id, status="deleted")


@router.post("/categories/{category_id}/merge", response_model=DevCategoryMergeResponse)
async def merge_dev_category(category_id: UUID, data: DevCategoryMergeRequest, db: DBSession):
    _ensure_development()
    source = await _get_category_or_none(db, category_id)
    target = await _get_category_or_none(db, data.target_category_id)
    if not source or not target:
        raise HTTPException(status_code=404, detail="Source or target category not found")
    if source.id == target.id:
        raise HTTPException(status_code=400, detail="Cannot merge category into itself")

    moved_material_categories = await _update_count(
        db,
        update(Material).where(Material.category_id == source.id).values(category_id=target.id),
    )
    moved_material_subcategories = await _update_count(
        db,
        update(Material).where(Material.subcategory_id == source.id).values(subcategory_id=target.id),
    )
    moved_children = await _update_count(
        db,
        update(MaterialCategory).where(MaterialCategory.parent_id == source.id).values(parent_id=target.id, level=target.level + 1),
    )
    source.status = "ARCHIVED"
    source.description = _append_note(source.description, f"Merged into {target.name}: {data.comment or ''}".strip())
    db.add(source)
    await db.flush()
    await log_event(
        db,
        "category_merged",
        "MaterialCategory",
        source.id,
        details={
            "source": _category_audit_values(source),
            "target": _category_audit_values(target),
            "moved_material_categories": moved_material_categories,
            "moved_material_subcategories": moved_material_subcategories,
            "moved_children": moved_children,
            "comment": data.comment or "",
        },
    )
    return DevCategoryMergeResponse(
        source_category_id=source.id,
        target_category_id=target.id,
        moved_material_categories=moved_material_categories,
        moved_material_subcategories=moved_material_subcategories,
        moved_children=moved_children,
        status="merged",
    )


@router.post("/candidates/{candidate_id}/approve")
async def approve_dev_match_candidate(candidate_id: UUID, data: DevModerationDecision, db: DBSession):
    _ensure_development()
    result = await db.execute(select(MaterialMatchCandidate).where(MaterialMatchCandidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not candidate.candidate_material_id:
        raise HTTPException(status_code=400, detail="Candidate has no material")

    product_result = await db.execute(select(CatalogProduct).where(CatalogProduct.id == candidate.catalog_product_id))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Catalog product not found")

    material_result = await db.execute(select(Material).where(Material.id == candidate.candidate_material_id))
    material = material_result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    selected_name = _select_canonical_name(data, product, material)
    if selected_name:
        material.canonical_name = selected_name

    product.material_id = material.id
    product.status = CatalogProductStatus.ACTIVE
    candidate.status = MatchCandidateStatus.APPROVED
    candidate.admin_decision = AdminDecision.APPROVE
    if data.reason:
        candidate.match_reason = f"{candidate.match_reason or ''}\nПринято: {data.reason}".strip()
    db.add(material)
    db.add(product)
    db.add(candidate)
    await db.flush()
    return {"status": "approved", "candidate_id": str(candidate.id)}


@router.post("/candidates/{candidate_id}/create-material")
async def create_dev_material_from_candidate(candidate_id: UUID, data: DevModerationDecision, db: DBSession):
    _ensure_development()
    result = await db.execute(select(MaterialMatchCandidate).where(MaterialMatchCandidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    product_result = await db.execute(select(CatalogProduct).where(CatalogProduct.id == candidate.catalog_product_id))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Catalog product not found")

    canonical_name = data.canonical_name or product.raw_name or product.normalized_name
    material = Material(
        canonical_name=canonical_name,
        brand=product.raw_brand,
        manufacturer=product.raw_manufacturer,
        status=MaterialStatus.AUTO_CREATED,
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)

    alias = MaterialAlias(
        material_id=material.id,
        original_name=product.raw_name,
        normalized_name=product.normalized_name or product.raw_name,
        confidence_score=candidate.match_score or Decimal("0.5"),
    )
    db.add(alias)

    product.material_id = material.id
    product.status = CatalogProductStatus.ACTIVE
    candidate.candidate_material_id = material.id
    candidate.status = MatchCandidateStatus.APPROVED
    candidate.admin_decision = AdminDecision.APPROVE
    if data.reason:
        candidate.match_reason = f"{candidate.match_reason or ''}\nСоздан новый Material: {data.reason}".strip()

    db.add(product)
    db.add(candidate)
    await db.flush()
    return {"status": "created", "candidate_id": str(candidate.id), "material_id": str(material.id)}


@router.post("/candidates/{candidate_id}/reject")
async def reject_dev_match_candidate(candidate_id: UUID, data: DevModerationDecision, db: DBSession):
    _ensure_development()
    result = await db.execute(select(MaterialMatchCandidate).where(MaterialMatchCandidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.status = MatchCandidateStatus.REJECTED
    candidate.admin_decision = AdminDecision.REJECT
    if data.reason:
        candidate.match_reason = f"{candidate.match_reason or ''}\nОтклонено: {data.reason}".strip()
    db.add(candidate)
    await db.flush()
    return {"status": "rejected", "candidate_id": str(candidate.id)}


@router.post("/candidates/{candidate_id}/undo")
async def undo_dev_match_candidate(candidate_id: UUID, data: DevModerationDecision, db: DBSession):
    _ensure_development()
    result = await db.execute(select(MaterialMatchCandidate).where(MaterialMatchCandidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    product_result = await db.execute(select(CatalogProduct).where(CatalogProduct.id == candidate.catalog_product_id))
    product = product_result.scalar_one_or_none()
    if product:
        product.material_id = None
        product.status = CatalogProductStatus.NEEDS_REVIEW
        db.add(product)

    candidate.status = MatchCandidateStatus.NEEDS_REVIEW
    candidate.admin_decision = None
    if data.reason:
        candidate.match_reason = f"{candidate.match_reason or ''}\nОтменено: {data.reason}".strip()
    db.add(candidate)
    await db.flush()
    return {"status": "undone", "candidate_id": str(candidate.id)}


async def _get_or_create_source(db: DBSession, data: DevRunTaskRequest) -> Source:
    if data.source_id:
        result = await db.execute(select(Source).where(Source.id == data.source_id))
    else:
        result = await db.execute(select(Source).where(Source.name == (data.source_name or "Baucenter")))
    source = result.scalar_one_or_none()

    if source:
        return source

    if data.source_id:
        raise HTTPException(status_code=404, detail="Source not found")

    for source_data in DEFAULT_SOURCES:
        if source_data["name"] == (data.source_name or "Baucenter"):
            source = Source(
                name=source_data["name"],
                source_type=source_data["source_type"],
                url=source_data["url"],
                priority=source_data["priority"],
                status=SourceStatus.ACTIVE,
            )
            db.add(source)
            await db.flush()
            await db.refresh(source)
            return source

    raise HTTPException(status_code=404, detail="Source not found")


async def _resolve_batch_sources(db: DBSession, data: DevRunBatchTaskRequest) -> list[Source]:
    await create_dev_default_sources(db)
    if data.all_sources:
        result = await db.execute(
            select(Source)
            .where(Source.status == SourceStatus.ACTIVE)
            .order_by(Source.priority.asc(), Source.name.asc())
        )
        return list(result.scalars().all())

    names = [name for name in (data.source_names or []) if name]
    if not names:
        return []
    result = await db.execute(
        select(Source)
        .where(Source.name.in_(names))
        .order_by(Source.priority.asc(), Source.name.asc())
    )
    found = list(result.scalars().all())
    found_names = {source.name for source in found}
    missing = [name for name in names if name not in found_names]
    if missing:
        raise HTTPException(status_code=404, detail=f"Sources not found: {', '.join(missing)}")
    return found


async def _get_or_create_manual_price_source(db: DBSession, source_name: str) -> Source:
    name = source_name.strip() if source_name else "Manual Price"
    result = await db.execute(select(Source).where(Source.name == name))
    source = result.scalar_one_or_none()
    if source:
        return source

    source = Source(
        name=name,
        source_type=SourceType.MANUAL_UPLOAD,
        priority=900,
        status=SourceStatus.ACTIVE,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


async def _get_category_or_none(db: DBSession, category_id: UUID | None) -> MaterialCategory | None:
    if not category_id:
        return None
    result = await db.execute(select(MaterialCategory).where(MaterialCategory.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


async def _unique_category_slug(db: DBSession, name: str, parent_id: UUID | None) -> str:
    base = _slugify(name)
    if parent_id:
        base = f"{base}-{str(parent_id)[:8]}"
    slug = base
    suffix = 2
    while True:
        existing = await db.scalar(select(MaterialCategory.id).where(MaterialCategory.slug == slug))
        if not existing:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def _slugify(value: str) -> str:
    translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
        "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
        "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
        "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    lowered = value.lower()
    converted = "".join(translit.get(char, char) for char in lowered)
    slug = re.sub(r"[^a-z0-9]+", "-", converted).strip("-")
    return slug or "category"


def _normalize_category_status(value: str | None) -> str:
    status = (value or "ACTIVE").upper()
    return status if status in {"ACTIVE", "ARCHIVED"} else "ACTIVE"


def _category_audit_values(category: MaterialCategory) -> dict:
    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "parent_id": str(category.parent_id) if category.parent_id else None,
        "status": category.status,
        "level": category.level,
        "sort_order": category.sort_order,
    }


async def _category_linked_count(db: DBSession, category_id: UUID) -> int:
    material_count = await db.scalar(
        select(func.count(Material.id)).where(
            (Material.category_id == category_id) | (Material.subcategory_id == category_id)
        )
    )
    return material_count or 0


async def _update_count(db: DBSession, statement) -> int:
    result = await db.execute(statement)
    return result.rowcount or 0


def _append_note(description: str | None, note: str) -> str:
    if not note:
        return description or ""
    if description:
        return f"{description}\n{note}"
    return note


def _manual_price_external_id(
    material_id: UUID,
    region: str | None,
    unit: str | None,
    source_id: UUID,
) -> str:
    region_key = (region or "default").strip().lower()
    unit_key = (unit or "unit").strip().lower()
    return f"manual-price:{source_id}:{material_id}:{region_key}:{unit_key}"


async def _create_and_run_task(
    db: DBSession,
    source: Source,
    action_type: SourceActionType,
    parameters: dict,
) -> SourceTask:
    task = SourceTask(
        source_id=source.id,
        action_type=action_type,
        status=TaskStatus.PENDING,
        parameters=parameters,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    task = await run_source_task(db, task.id)
    await db.refresh(source)
    return task


def _default_parameters(action_type: SourceActionType) -> dict:
    if action_type in {
        SourceActionType.INITIAL_MATERIAL_SCAN,
        SourceActionType.UPDATE_PRICES,
        SourceActionType.FIND_NEW_PRODUCTS,
        SourceActionType.UPDATE_SPECIFICATIONS,
    }:
        return {
            "scan_mode": "TEST",
            "max_pages": 5,
            "max_attempts": 20,
        }
    if action_type in {
        SourceActionType.UPDATE_CERTIFICATES,
        SourceActionType.UPDATE_TECH_DOCUMENTS,
    }:
        return {
            "scan_mode": "TEST",
            "max_documents": 10,
        }
    return {}


def _sanitize_task_parameters(action_type: SourceActionType, parameters: dict | None) -> dict:
    sanitized = dict(parameters or {})
    scan_mode = str(sanitized.get("scan_mode") or "TEST").upper()
    if scan_mode not in {"TEST", "CATEGORY", "FULL"}:
        scan_mode = "TEST"
    sanitized["scan_mode"] = scan_mode

    if action_type in {
        SourceActionType.UPDATE_CERTIFICATES,
        SourceActionType.UPDATE_TECH_DOCUMENTS,
    }:
        sanitized["max_documents"] = _bounded_int(sanitized.get("max_documents"), 10, 1, 100)
        return sanitized

    default_pages = 5 if scan_mode == "TEST" else 30 if scan_mode == "CATEGORY" else 50
    max_allowed_pages = 20 if scan_mode == "TEST" else 80 if scan_mode == "CATEGORY" else 150
    max_pages = _bounded_int(sanitized.get("max_pages"), default_pages, 1, max_allowed_pages)
    sanitized["max_pages"] = max_pages
    sanitized["max_attempts"] = _bounded_int(
        sanitized.get("max_attempts"),
        min(max_pages * 3, 150),
        1,
        min(max_pages * 4, 300),
    )
    return sanitized


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _select_canonical_name(data: DevModerationDecision, product: CatalogProduct, material: Material) -> str | None:
    if data.canonical_name_choice == "product":
        return product.raw_name or product.normalized_name
    if data.canonical_name_choice == "custom":
        return data.canonical_name
    return material.canonical_name
