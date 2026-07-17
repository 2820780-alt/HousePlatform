from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Any

from app.models.catalog_product import CatalogProduct
from app.models.enums import (
    CatalogProductStatus,
    DocumentStatus,
    SourceStatus,
    TaskStatus,
    UploadRowStatus,
)
from app.models.material import Material
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.source_task_result import SourceTaskResult
from app.models.supplier_price import SupplierPrice
from app.models.supplier_upload_row import SupplierUploadRow
from app.schemas.material_hub_contracts import (
    CollectionObject,
    DocumentFileMeta,
    DocumentFileType,
    DocumentOrigin,
    DocumentRecord,
    ExtractionProfile,
    IngestionRecordStatus,
    MaterialCanonicalObject,
    MaterialMatchCandidateContract,
    PriceObservation,
    RawIngestionItem,
    SourceAdapterStatus,
    SourceProfile,
    SourceProfileStatus,
)


@dataclass(frozen=True)
class LegacyCompatibilityMapping:
    target_entity: str
    legacy_entities: tuple[str, ...]
    status: str
    keep: str
    adapt: str
    risk: str


MODULE1_LEGACY_COMPATIBILITY_MAP: tuple[LegacyCompatibilityMapping, ...] = (
    LegacyCompatibilityMapping(
        "CanonicalMaterial",
        ("Material", "MaterialAlias", "MaterialAttribute", "MaterialSpecification", "MaterialCategory", "MaterialType"),
        "reuse_as_base",
        "Existing material catalog and normalized characteristic relations.",
        "Expose Material through CanonicalMaterial DTO without creating a second material table.",
        "Duplicate canonical materials if a parallel model is introduced.",
    ),
    LegacyCompatibilityMapping(
        "RawIngestionItem",
        ("CatalogProduct", "SupplierUploadRow", "SourceTaskResult"),
        "compatibility_layer",
        "Raw source/upload rows and task payloads.",
        "Expose raw records as ingestion DTOs; do not promote them to canonical data directly.",
        "Raw/import data can be mistaken for canonical material data.",
    ),
    LegacyCompatibilityMapping(
        "PriceObservation",
        ("SupplierPrice", "PriceHistory"),
        "compatibility_layer",
        "Supplier prices and append-only price history.",
        "Expose price rows as observations while preserving history.",
        "Price history may be overwritten or flattened.",
    ),
    LegacyCompatibilityMapping(
        "WorkRateObservation",
        ("ProviderWorkCostOffer", "WorkRateObservation"),
        "separate_persistence_contract",
        "Keep WorkRateObservation as a diagnostic/in-memory observation and store provider offers separately.",
        "Use ProviderWorkCostOffer for owned editable work cost offers; never promote observations automatically.",
        "Work rates can be mixed with material prices or Module №5 estimate logic if the boundary is bypassed.",
    ),
    LegacyCompatibilityMapping(
        "DocumentEvidence",
        ("MaterialDocument", "KnowledgeResource", "KnowledgeResourceLink"),
        "partial_reuse",
        "Material document records and knowledge links.",
        "Expose documents as evidence; site pages are not documents.",
        "Evidence can lose its link to the material fact it proves.",
    ),
    LegacyCompatibilityMapping(
        "SourcePipeline",
        ("Source", "SourceTask", "SourceTaskResult"),
        "reuse_as_base",
        "Sources, source tasks, and task result payloads.",
        "Keep adapters returning raw extraction/task results, not canonical materials.",
        "Source adapters can accidentally create business entities directly.",
    ),
    LegacyCompatibilityMapping(
        "MatchingModeration",
        ("MaterialMatchCandidate",),
        "reuse_as_base",
        "Existing matching/moderation candidate queue.",
        "Keep canonical writes behind moderator decision or verified rule.",
        "Low-confidence auto merge can create duplicate or wrong materials.",
    ),
)


def get_module1_legacy_compatibility_map() -> tuple[LegacyCompatibilityMapping, ...]:
    return MODULE1_LEGACY_COMPATIBILITY_MAP


def canonical_material_from_material(material: Material) -> MaterialCanonicalObject:
    return MaterialCanonicalObject(
        id=material.id,
        canonical_name=material.canonical_name,
        category_id=material.category_id,
        subcategory_id=material.subcategory_id,
        material_type_id=material.material_type_id,
        manufacturer_id=material.manufacturer_id,
        brand_id=material.brand_id,
        base_unit_id=material.base_unit_id,
        article=material.article,
        brand=material.brand,
        manufacturer=material.manufacturer,
        description=material.description,
        status=material.status,
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


def raw_ingestion_from_catalog_product(product: CatalogProduct) -> RawIngestionItem:
    return RawIngestionItem(
        id=product.id,
        source_id=product.source_id,
        external_id=product.external_id,
        external_url=product.external_url,
        raw_name=product.raw_name,
        normalized_name=product.normalized_name,
        raw_category=product.raw_category,
        raw_brand=product.raw_brand,
        raw_manufacturer=product.raw_manufacturer,
        raw_unit=product.unit,
        raw_price=product.price,
        raw_payload={
            "legacy_entity": "CatalogProduct",
            "availability": product.availability,
            "currency": product.currency,
            "region": product.region,
            "match_confidence": str(product.match_confidence) if product.match_confidence is not None else None,
        },
        status=_catalog_product_status_to_ingestion_status(product.status),
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def raw_ingestion_from_supplier_upload_row(row: SupplierUploadRow) -> RawIngestionItem:
    return RawIngestionItem(
        id=row.id,
        supplier_upload_id=row.upload_id,
        raw_name=row.raw_name or "",
        normalized_name=row.normalized_name,
        raw_category=row.raw_category,
        raw_brand=row.raw_brand,
        raw_manufacturer=row.raw_manufacturer,
        raw_unit=row.raw_unit,
        raw_price=row.raw_price,
        raw_quantity=row.raw_quantity,
        raw_article=row.raw_article,
        raw_payload={
            "legacy_entity": "SupplierUploadRow",
            "row_number": row.row_number,
            "parsed_data": row.parsed_data or {},
            "error_message": row.error_message,
        },
        status=_upload_row_status_to_ingestion_status(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def raw_ingestion_from_source_task_result(result: SourceTaskResult) -> RawIngestionItem:
    payload = result.new_value or result.old_value or {}
    raw_name = _first_payload_value(payload, "raw_name", "rawName", "name", "title")
    if not raw_name:
        raise ValueError("SourceTaskResult cannot be exposed as RawIngestionItem without raw name/title.")

    task = getattr(result, "task", None)
    return RawIngestionItem(
        id=result.id,
        source_id=getattr(task, "source_id", None),
        raw_name=str(raw_name),
        normalized_name=_optional_str(_first_payload_value(payload, "normalized_name", "normalizedName")),
        raw_category=_optional_str(_first_payload_value(payload, "raw_category", "rawCategory", "category")),
        raw_brand=_optional_str(_first_payload_value(payload, "raw_brand", "rawBrand", "brand")),
        raw_manufacturer=_optional_str(_first_payload_value(payload, "raw_manufacturer", "rawManufacturer", "manufacturer")),
        raw_unit=_optional_str(_first_payload_value(payload, "raw_unit", "rawUnit", "unit")),
        raw_price=_optional_decimal(_first_payload_value(payload, "raw_price", "rawPrice", "price")),
        raw_payload={
            "legacy_entity": "SourceTaskResult",
            "entity_type": result.entity_type,
            "entity_id": str(result.entity_id) if result.entity_id else None,
            "status": result.status,
            "admin_decision": _enum_value(result.admin_decision),
            "payload": payload,
        },
        status=IngestionRecordStatus.NEEDS_REVIEW,
        created_at=result.created_at,
        updated_at=result.updated_at,
    )


def price_observation_from_supplier_price(price: SupplierPrice) -> PriceObservation:
    if price.price is None:
        raise ValueError("SupplierPrice cannot be exposed as PriceObservation without price.")

    return PriceObservation(
        id=price.id,
        material_id=price.material_id,
        catalog_product_id=price.catalog_product_id,
        supplier_id=price.supplier_id,
        supplier_upload_id=price.source_upload_id,
        price=price.price,
        currency=price.currency,
        unit=price.unit,
        availability=price.availability,
        price_date=_date_to_datetime(price.valid_until),
        collected_at=price.created_at,
        created_at=price.created_at,
        updated_at=price.updated_at,
    )


def price_observation_from_price_history(history: PriceHistory) -> PriceObservation:
    return PriceObservation(
        id=history.id,
        material_id=history.material_id,
        catalog_product_id=history.catalog_product_id,
        supplier_id=history.supplier_id,
        source_id=history.source_id,
        supplier_upload_id=history.supplier_upload_id,
        price=history.price,
        currency=history.currency,
        unit=history.unit,
        availability=history.availability,
        price_date=_date_to_datetime(history.price_date),
        collected_at=history.collected_at,
        created_at=history.created_at,
    )


def document_record_from_material_document(document: MaterialDocument) -> DocumentRecord:
    return DocumentRecord(
        id=document.id,
        material_id=document.material_id,
        manufacturer_id=document.manufacturer_id,
        source_id=document.source_id,
        document_type=document.document_type,
        title=document.title,
        file_url=document.file_url,
        source_url=document.source_url,
        origin=DocumentOrigin.UPLOADED_FILE if document.file_url else DocumentOrigin.EXTERNAL_LINK,
        file_meta=DocumentFileMeta(file_type=_document_file_type(document.file_url or document.source_url)),
        issue_date=_date_to_datetime(document.issue_date),
        expiry_date=_date_to_datetime(document.expiry_date),
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def source_profile_from_source(source: Source) -> SourceProfile:
    return SourceProfile(
        id=source.id,
        source_id=source.id,
        name=source.name,
        display_name=source.name,
        source_type=source.source_type,
        url=source.url,
        base_url=source.url,
        priority=source.priority,
        parser_status=_source_status_to_profile_status(source.status),
        status=_source_status_to_profile_status(source.status),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def extraction_profile_from_source_task(task: SourceTask) -> ExtractionProfile:
    action = _enum_value(task.action_type) or "UNKNOWN"
    return ExtractionProfile(
        id=task.id,
        source_id=task.source_id,
        profile_code=f"legacy-task-{str(action).lower()}",
        title=f"Legacy source task: {action}",
        collectable_objects=_collectable_objects_for_task_action(action),
        status=_task_status_to_adapter_status(task.status),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def match_candidate_contract_from_material_match_candidate(
    candidate: MaterialMatchCandidate,
) -> MaterialMatchCandidateContract:
    return MaterialMatchCandidateContract(
        id=candidate.id,
        catalog_product_id=candidate.catalog_product_id,
        candidate_material_id=candidate.candidate_material_id,
        match_score=candidate.match_score,
        match_reason=candidate.match_reason,
        ai_suggestion=candidate.ai_suggestion,
        admin_decision=candidate.admin_decision,
        status=candidate.status,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def _catalog_product_status_to_ingestion_status(status: CatalogProductStatus) -> IngestionRecordStatus:
    return {
        CatalogProductStatus.ACTIVE: IngestionRecordStatus.NORMALIZED,
        CatalogProductStatus.UNAVAILABLE: IngestionRecordStatus.NEEDS_REVIEW,
        CatalogProductStatus.NEW_PRODUCT_FOUND: IngestionRecordStatus.RAW,
        CatalogProductStatus.NEEDS_REVIEW: IngestionRecordStatus.NEEDS_REVIEW,
        CatalogProductStatus.REJECTED: IngestionRecordStatus.REJECTED,
        CatalogProductStatus.ARCHIVED: IngestionRecordStatus.REJECTED,
    }[status]


def _upload_row_status_to_ingestion_status(status: UploadRowStatus) -> IngestionRecordStatus:
    return {
        UploadRowStatus.EXTRACTED: IngestionRecordStatus.RAW,
        UploadRowStatus.NORMALIZED: IngestionRecordStatus.NORMALIZED,
        UploadRowStatus.MATCHED: IngestionRecordStatus.MATCH_CANDIDATE,
        UploadRowStatus.NEEDS_REVIEW: IngestionRecordStatus.NEEDS_REVIEW,
        UploadRowStatus.ERROR: IngestionRecordStatus.ERROR,
        UploadRowStatus.REJECTED: IngestionRecordStatus.REJECTED,
    }[status]


def _source_status_to_profile_status(status: SourceStatus) -> SourceProfileStatus:
    return {
        SourceStatus.ACTIVE: SourceProfileStatus.ACTIVE,
        SourceStatus.PAUSED: SourceProfileStatus.PAUSED,
        SourceStatus.DISABLED: SourceProfileStatus.ARCHIVED,
        SourceStatus.ERROR: SourceProfileStatus.ERROR,
    }[status]


def _task_status_to_adapter_status(status: TaskStatus) -> SourceAdapterStatus:
    return {
        TaskStatus.PENDING: SourceAdapterStatus.PLANNED,
        TaskStatus.RUNNING: SourceAdapterStatus.TEST,
        TaskStatus.COMPLETED: SourceAdapterStatus.ACTIVE,
        TaskStatus.FAILED: SourceAdapterStatus.ERROR,
        TaskStatus.CANCELLED: SourceAdapterStatus.DISABLED,
        TaskStatus.NEEDS_REVIEW: SourceAdapterStatus.TEST,
    }[status]


def _collectable_objects_for_task_action(action: str) -> list[CollectionObject]:
    if "PRICE" in action:
        return [CollectionObject.PRICES]
    if "CERTIFICATE" in action or "DOCUMENT" in action or "TECH" in action:
        return [CollectionObject.DOCUMENTS]
    return [CollectionObject.MATERIALS]


def _document_file_type(url: str | None) -> DocumentFileType:
    if not url:
        return DocumentFileType.URL
    suffix = PurePosixPath(url.split("?", 1)[0]).suffix.lower().lstrip(".")
    return {
        "pdf": DocumentFileType.PDF,
        "xlsx": DocumentFileType.XLSX,
        "csv": DocumentFileType.CSV,
        "jpg": DocumentFileType.JPG,
        "jpeg": DocumentFileType.JPEG,
        "png": DocumentFileType.PNG,
        "doc": DocumentFileType.DOC,
        "docx": DocumentFileType.DOCX,
    }.get(suffix, DocumentFileType.URL)


def _date_to_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def _first_payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _optional_str(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _optional_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", str(value))
