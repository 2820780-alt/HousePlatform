from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog_product import CatalogProduct
from app.models.enums import (
    CatalogProductStatus,
    DocumentStatus,
    DocumentType,
    MaterialStatus,
    SourceActionType,
    SourceStatus,
    TaskLogLevel,
    TaskResultType,
    TaskStatus,
)
from app.models.manufacturer import Manufacturer
from app.models.material import Material
from app.models.material_alias import MaterialAlias
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.source_task import SourceTask
from app.models.source_task_log import SourceTaskLog
from app.models.source_task_result import SourceTaskResult
from app.source_integrations import get_integration
from app.source_integrations.base import SourceDocument, SourceProduct
from app.services.material_classification import (
    assess_material_quality,
    apply_classification_categories,
    classify_catalog_product,
)
from app.services.material_taxonomy import (
    infer_baucenter_taxonomy,
    sync_extracted_specifications,
)
from app.services.rule_memory import find_rule_for_product


async def run_source_task(db: AsyncSession, task_id: UUID) -> SourceTask:
    result = await db.execute(
        select(SourceTask)
        .options(selectinload(SourceTask.source))
        .where(SourceTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise ValueError(f"SourceTask not found: {task_id}")
    if not task.source:
        raise ValueError("SourceTask has no source")

    integration = get_integration(task.source)
    if not integration:
        await _fail_task(db, task, f"No integration registered for source: {task.source.name}")
        return task

    if task.action_type not in integration.supported_actions:
        await _fail_task(db, task, f"Action {task.action_type.value} is not supported by this source")
        return task

    task.status = TaskStatus.RUNNING
    task.started_at = datetime.utcnow()
    task.error_message = None
    db.add(task)
    await _log(db, task, TaskLogLevel.INFO, f"Started {task.action_type.value}")

    try:
        if task.action_type == SourceActionType.CHECK_SOURCE_HEALTH:
            await _run_health_check(db, task, integration)
        elif task.action_type in {
            SourceActionType.INITIAL_MATERIAL_SCAN,
            SourceActionType.UPDATE_PRICES,
            SourceActionType.FIND_NEW_PRODUCTS,
            SourceActionType.UPDATE_SPECIFICATIONS,
        }:
            await _run_product_scan(db, task, integration)
        elif task.action_type in {
            SourceActionType.UPDATE_CERTIFICATES,
            SourceActionType.UPDATE_TECH_DOCUMENTS,
        }:
            await _run_document_scan(db, task, integration)
        else:
            await _fail_task(db, task, f"Runner is not implemented for action {task.action_type.value}")
            return task

        task.status = TaskStatus.COMPLETED
        task.finished_at = datetime.utcnow()
        db.add(task)
        await _log(db, task, TaskLogLevel.INFO, "Task completed")
    except Exception as exc:
        await _fail_task(db, task, str(exc))

    await db.flush()
    await db.refresh(task)
    return task


async def _run_health_check(db: AsyncSession, task: SourceTask, integration) -> None:
    health = await integration.check_health()
    await _result(
        db,
        task,
        TaskResultType.UNCHANGED if health.ok else TaskResultType.ERROR,
        entity_type="Source",
        entity_id=task.source_id,
        status="ok" if health.ok else "error",
        new_value={
            "ok": health.ok,
            "status_code": health.status_code,
            "message": health.message,
        },
    )
    if not health.ok:
        task.source.status = SourceStatus.ERROR
    await _log(db, task, TaskLogLevel.INFO if health.ok else TaskLogLevel.ERROR, health.message or "health checked")


async def _run_product_scan(db: AsyncSession, task: SourceTask, integration) -> None:
    products = await integration.fetch_products(task.action_type, task.parameters)
    await _log(db, task, TaskLogLevel.INFO, f"Fetched products: {len(products)}")

    created = 0
    updated = 0
    unchanged = 0
    price_changes = 0
    candidates = 0

    for product in products:
        catalog_product, result_type, price_changed = await _upsert_catalog_product(db, task, product)
        if result_type == TaskResultType.CREATED:
            created += 1
        elif result_type == TaskResultType.UPDATED:
            updated += 1
        else:
            unchanged += 1
        if price_changed:
            price_changes += 1

        matched = await _match_or_create_material(db, catalog_product)
        if matched in {"candidate", "needs_review"}:
            candidates += 1
        if price_changed and catalog_product.material_id and catalog_product.price is not None:
            await _write_price_history(db, catalog_product, catalog_product.price)

        await _result(
            db,
            task,
            result_type,
            entity_type="CatalogProduct",
            entity_id=catalog_product.id,
            status=catalog_product.status.value,
            new_value=_product_snapshot(catalog_product),
        )

    task.result_summary = {
        "fetched": len(products),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "price_changes": price_changes,
        "match_candidates": candidates,
    }
    _mark_source_timestamp(task)
    db.add(task.source)


async def _run_document_scan(db: AsyncSession, task: SourceTask, integration) -> None:
    documents = await integration.fetch_documents(task.action_type, task.parameters)
    await _log(db, task, TaskLogLevel.INFO, f"Fetched documents: {len(documents)}")

    created = 0
    unchanged = 0
    manufacturer = await _get_or_create_manufacturer(db, task.source.name, task.source.url)

    for document in documents:
        material_document, result_type = await _upsert_material_document(db, task, document, manufacturer.id)
        if result_type == TaskResultType.CREATED:
            created += 1
        else:
            unchanged += 1

        await _result(
            db,
            task,
            result_type,
            entity_type="MaterialDocument",
            entity_id=material_document.id,
            status=material_document.status.value,
            new_value=_document_snapshot(material_document),
        )

    task.result_summary = {
        "fetched": len(documents),
        "created": created,
        "unchanged": unchanged,
    }
    _mark_source_timestamp(task)
    db.add(task.source)


async def _upsert_catalog_product(
    db: AsyncSession,
    task: SourceTask,
    product: SourceProduct,
) -> tuple[CatalogProduct, TaskResultType, bool]:
    existing = await _find_catalog_product(db, task.source_id, product)
    if not existing:
        catalog_product = CatalogProduct(
            source_id=task.source_id,
            external_id=product.external_id,
            external_url=product.external_url,
            raw_name=product.raw_name,
            normalized_name=product.normalized_name,
            raw_category=product.raw_category,
            raw_brand=product.raw_brand,
            raw_manufacturer=product.raw_manufacturer,
            price=product.price,
            currency=product.currency,
            unit=product.unit,
            availability=product.availability,
            region=product.region,
            status=CatalogProductStatus.NEEDS_REVIEW,
        )
        db.add(catalog_product)
        await db.flush()
        return catalog_product, TaskResultType.CREATED, product.price is not None

    price_changed = _price_changed(existing.price, product.price)
    changed = price_changed or any([
        existing.raw_name != product.raw_name,
        existing.normalized_name != product.normalized_name,
        existing.raw_category != product.raw_category,
        existing.raw_brand != product.raw_brand,
        existing.raw_manufacturer != product.raw_manufacturer,
        existing.unit != product.unit,
        existing.availability != product.availability,
        existing.region != product.region,
    ])

    if not changed:
        return existing, TaskResultType.UNCHANGED, False

    old_snapshot = _product_snapshot(existing)
    existing.raw_name = product.raw_name
    existing.normalized_name = product.normalized_name
    existing.raw_category = product.raw_category
    existing.raw_brand = product.raw_brand
    existing.raw_manufacturer = product.raw_manufacturer
    existing.price = product.price
    existing.currency = product.currency
    existing.unit = product.unit
    existing.availability = product.availability
    existing.region = product.region
    db.add(existing)
    await db.flush()

    await _result(
        db,
        task,
        TaskResultType.UPDATED,
        entity_type="CatalogProduct",
        entity_id=existing.id,
        status="price_changed" if price_changed else "updated",
        old_value=old_snapshot,
        new_value=_product_snapshot(existing),
    )
    return existing, TaskResultType.UPDATED, price_changed


async def _upsert_material_document(
    db: AsyncSession,
    task: SourceTask,
    document: SourceDocument,
    default_manufacturer_id: UUID | None,
) -> tuple[MaterialDocument, TaskResultType]:
    document_type = DocumentType(document.document_type)
    result = await db.execute(
        select(MaterialDocument).where(
            MaterialDocument.source_id == task.source_id,
            MaterialDocument.file_url == document.file_url,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, TaskResultType.UNCHANGED

    material_document = MaterialDocument(
        material_id=document.material_id,
        manufacturer_id=document.manufacturer_id or default_manufacturer_id,
        source_id=task.source_id,
        document_type=document_type,
        title=document.title,
        file_url=document.file_url,
        source_url=document.source_url,
        status=DocumentStatus.ACTIVE,
    )
    db.add(material_document)
    await db.flush()
    return material_document, TaskResultType.CREATED


async def _find_catalog_product(
    db: AsyncSession,
    source_id: UUID,
    product: SourceProduct,
) -> CatalogProduct | None:
    if product.external_id:
        result = await db.execute(
            select(CatalogProduct).where(
                CatalogProduct.source_id == source_id,
                CatalogProduct.external_id == product.external_id,
            )
        )
        found = result.scalar_one_or_none()
        if found:
            return found

    if product.external_url:
        result = await db.execute(
            select(CatalogProduct).where(
                CatalogProduct.source_id == source_id,
                CatalogProduct.external_url == product.external_url,
            )
        )
        return result.scalar_one_or_none()
    return None


async def _get_or_create_manufacturer(db: AsyncSession, name: str | None, official_site: str | None) -> Manufacturer:
    manufacturer_name = (name or "Unknown manufacturer").strip()
    result = await db.execute(select(Manufacturer).where(Manufacturer.name == manufacturer_name))
    manufacturer = result.scalar_one_or_none()
    if manufacturer:
        return manufacturer

    manufacturer = Manufacturer(
        name=manufacturer_name,
        official_site=official_site,
        country="RU",
        status="ACTIVE",
    )
    db.add(manufacturer)
    await db.flush()
    await db.refresh(manufacturer)
    return manufacturer


async def _match_or_create_material(db: AsyncSession, catalog_product: CatalogProduct) -> str:
    normalized = catalog_product.normalized_name or _normalize(catalog_product.raw_name)
    classification = classify_catalog_product(catalog_product)
    quality = assess_material_quality(catalog_product, classification)
    category, subcategory = await apply_classification_categories(db, classification)
    taxonomy_path = infer_baucenter_taxonomy(
        catalog_product.raw_name,
        catalog_product.raw_category,
        catalog_product.external_url,
    )
    specification_category = subcategory or category
    if classification.region and not catalog_product.region:
        catalog_product.region = classification.region

    allowed_category_ids = {item.id for item in (category, subcategory) if item}
    rule = await find_rule_for_product(db, catalog_product, allowed_category_ids)
    if rule and rule.material:
        material = rule.material
        catalog_product.material_id = material.id
        catalog_product.match_confidence = min(Decimal("1.0"), Decimal("0.85") + rule.get_confidence_boost())
        catalog_product.status = CatalogProductStatus.ACTIVE
        if rule.category_id:
            if material.subcategory_id != rule.category_id and material.category_id != rule.category_id:
                material.subcategory_id = rule.category_id
                db.add(material)
        await sync_extracted_specifications(
            db,
            material,
            catalog_product.source_id,
            specification_category,
            taxonomy_path,
            catalog_product.raw_name,
            catalog_product.raw_category,
        )
        db.add(catalog_product)
        await db.flush()
        return "matched_by_rule_memory"

    if not quality.can_create_material:
        catalog_product.material_id = None
        catalog_product.match_confidence = Decimal(str(classification.confidence))
        catalog_product.status = CatalogProductStatus.NEEDS_REVIEW
        db.add(catalog_product)
        await db.flush()
        return "needs_review"

    alias_result = await db.execute(
        select(MaterialAlias)
        .options(selectinload(MaterialAlias.material))
        .where(MaterialAlias.normalized_name == normalized)
        .limit(1)
    )
    alias = alias_result.scalar_one_or_none()
    material = alias.material if alias else None

    if not material:
        result = await db.execute(
            select(Material)
            .where(func.lower(Material.canonical_name) == normalized)
            .limit(1)
        )
        material = result.scalar_one_or_none()

    if material:
        catalog_product.material_id = material.id
        catalog_product.match_confidence = Decimal("1.0")
        catalog_product.status = CatalogProductStatus.ACTIVE
        await sync_extracted_specifications(
            db,
            material,
            catalog_product.source_id,
            specification_category,
            taxonomy_path,
            catalog_product.raw_name,
            catalog_product.raw_category,
        )
        db.add(catalog_product)
        await db.flush()
        return "matched"

    material = Material(
        canonical_name=classification.canonical_name,
        category_id=category.id if category else None,
        subcategory_id=subcategory.id if subcategory else None,
        brand=classification.brand,
        manufacturer=classification.manufacturer,
        status=MaterialStatus.AUTO_CREATED,
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)

    alias = MaterialAlias(
        material_id=material.id,
        original_name=catalog_product.raw_name,
        normalized_name=normalized,
        confidence_score=Decimal("0.75"),
    )
    db.add(alias)

    catalog_product.material_id = material.id
    catalog_product.match_confidence = Decimal("1.0")
    catalog_product.status = CatalogProductStatus.ACTIVE
    db.add(catalog_product)
    await sync_extracted_specifications(
        db,
        material,
        catalog_product.source_id,
        specification_category,
        taxonomy_path,
        catalog_product.raw_name,
        catalog_product.raw_category,
    )
    await db.flush()
    return "created"


async def _write_price_history(db: AsyncSession, catalog_product: CatalogProduct, price) -> None:
    history = PriceHistory(
        material_id=catalog_product.material_id,
        catalog_product_id=catalog_product.id,
        source_id=catalog_product.source_id,
        price=price,
        currency=catalog_product.currency,
        unit=catalog_product.unit,
        region=catalog_product.region,
        availability=catalog_product.availability,
    )
    db.add(history)


def _price_changed(old, new) -> bool:
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return Decimal(old) != Decimal(new)


def _product_snapshot(product: CatalogProduct) -> dict:
    return {
        "external_id": product.external_id,
        "external_url": product.external_url,
        "raw_name": product.raw_name,
        "normalized_name": product.normalized_name,
        "raw_category": product.raw_category,
        "raw_brand": product.raw_brand,
        "raw_manufacturer": product.raw_manufacturer,
        "price": str(product.price) if product.price is not None else None,
        "currency": product.currency,
        "unit": product.unit,
        "availability": product.availability,
        "region": product.region,
        "material_id": str(product.material_id) if product.material_id else None,
    }


def _document_snapshot(document: MaterialDocument) -> dict:
    return {
        "material_id": str(document.material_id) if document.material_id else None,
        "manufacturer_id": str(document.manufacturer_id) if document.manufacturer_id else None,
        "source_id": str(document.source_id) if document.source_id else None,
        "document_type": document.document_type.value,
        "title": document.title,
        "file_url": document.file_url,
        "source_url": document.source_url,
        "status": document.status.value,
    }


async def _log(db: AsyncSession, task: SourceTask, level: TaskLogLevel, message: str, metadata: dict | None = None) -> None:
    db.add(SourceTaskLog(
        task_id=task.id,
        level=level,
        message=message,
        metadata_=metadata,
    ))
    await db.flush()


async def _result(
    db: AsyncSession,
    task: SourceTask,
    result_type: TaskResultType,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    status: str | None = None,
) -> None:
    db.add(SourceTaskResult(
        task_id=task.id,
        result_type=result_type,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        status=status,
    ))
    await db.flush()


async def _fail_task(db: AsyncSession, task: SourceTask, message: str) -> None:
    task.status = TaskStatus.FAILED
    task.finished_at = datetime.utcnow()
    task.error_message = message
    db.add(task)
    await _log(db, task, TaskLogLevel.ERROR, message)
    await db.flush()


def _mark_source_timestamp(task: SourceTask) -> None:
    now = datetime.utcnow()
    if task.action_type == SourceActionType.INITIAL_MATERIAL_SCAN:
        task.source.last_full_scan_at = now
    elif task.action_type == SourceActionType.UPDATE_PRICES:
        task.source.last_price_update_at = now
    elif task.action_type == SourceActionType.FIND_NEW_PRODUCTS:
        task.source.last_full_scan_at = now
    elif task.action_type in {
        SourceActionType.UPDATE_CERTIFICATES,
        SourceActionType.UPDATE_TECH_DOCUMENTS,
    }:
        task.source.last_document_update_at = now


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("\xa0", " ").split())
