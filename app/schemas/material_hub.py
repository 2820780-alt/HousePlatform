from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import (
    AdminDecision,
    CatalogProductStatus,
    DocumentStatus,
    DocumentType,
    MatchCandidateStatus,
    SourceActionType,
    SourceStatus,
    SourceType,
    TaskLogLevel,
    TaskResultType,
    TaskStatus,
    UploadFileType,
    UploadRowStatus,
    UploadStatus,
    VerificationStatus,
)


class SourceRead(BaseModel):
    id: UUID
    name: str
    source_type: SourceType
    url: str | None = None
    priority: int
    status: SourceStatus
    last_full_scan_at: datetime | None = None
    last_price_update_at: datetime | None = None
    last_document_update_at: datetime | None = None
    last_knowledge_scan_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceCreate(BaseModel):
    name: str
    source_type: SourceType
    url: str | None = None
    priority: int = 100
    status: SourceStatus = SourceStatus.ACTIVE


class SourceUpdate(BaseModel):
    name: str | None = None
    source_type: SourceType | None = None
    url: str | None = None
    priority: int | None = None
    status: SourceStatus | None = None


class SourceTaskCreate(BaseModel):
    action_type: SourceActionType
    source_ids: list[UUID] | None = None
    all_sources: bool = False
    parameters: dict | None = None


class ManufacturerRead(BaseModel):
    id: UUID
    name: str
    official_site: str | None = None
    country: str | None = None
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrandRead(BaseModel):
    id: UUID
    manufacturer_id: UUID | None = None
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CatalogProductRead(BaseModel):
    id: UUID
    source_id: UUID
    material_id: UUID | None = None
    external_id: str | None = None
    external_url: str | None = None
    raw_name: str
    normalized_name: str | None = None
    raw_category: str | None = None
    raw_brand: str | None = None
    raw_manufacturer: str | None = None
    price: Decimal | None = None
    currency: str
    unit: str | None = None
    availability: str | None = None
    region: str | None = None
    match_confidence: Decimal | None = None
    status: CatalogProductStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SpecificationTemplateRead(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    field_key: str
    field_type: str
    unit: str | None = None
    is_required: bool
    weight_for_matching: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialSpecificationRead(BaseModel):
    id: UUID
    material_id: UUID
    template_id: UUID | None = None
    value: str
    unit: str | None = None
    source_id: UUID | None = None
    confidence: Decimal | None = None
    verified_status: VerificationStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialDocumentRead(BaseModel):
    id: UUID
    material_id: UUID | None = None
    manufacturer_id: UUID | None = None
    source_id: UUID | None = None
    document_type: DocumentType
    title: str
    file_url: str | None = None
    source_url: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialDocumentCreate(BaseModel):
    material_id: UUID | None = None
    manufacturer_id: UUID | None = None
    source_id: UUID | None = None
    document_type: DocumentType
    title: str
    file_url: str | None = None
    source_url: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    status: DocumentStatus = DocumentStatus.NEEDS_REVIEW


class MaterialMatchCandidateRead(BaseModel):
    id: UUID
    catalog_product_id: UUID
    candidate_material_id: UUID | None = None
    match_score: Decimal | None = None
    match_reason: str | None = None
    ai_suggestion: str | None = None
    admin_decision: AdminDecision | None = None
    status: MatchCandidateStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceTaskRead(BaseModel):
    id: UUID
    source_id: UUID | None = None
    action_type: SourceActionType
    status: TaskStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_by: UUID | None = None
    parameters: dict | None = None
    result_summary: dict | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceTaskLogRead(BaseModel):
    id: UUID
    task_id: UUID
    level: TaskLogLevel
    message: str
    metadata_: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceTaskResultRead(BaseModel):
    id: UUID
    task_id: UUID
    result_type: TaskResultType
    entity_type: str | None = None
    entity_id: UUID | None = None
    old_value: dict | None = None
    new_value: dict | None = None
    status: str | None = None
    admin_decision: AdminDecision | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierUploadRead(BaseModel):
    id: UUID
    supplier_id: UUID | None = None
    uploaded_by_user_id: UUID | None = None
    source_id: UUID | None = None
    file_name: str
    file_type: UploadFileType
    file_url: str | None = None
    status: UploadStatus
    rows_total: int
    rows_processed: int
    rows_matched: int
    rows_needs_review: int
    rows_errors: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierUploadRowRead(BaseModel):
    id: UUID
    upload_id: UUID
    row_number: int | None = None
    raw_name: str | None = None
    normalized_name: str | None = None
    raw_category: str | None = None
    raw_brand: str | None = None
    raw_manufacturer: str | None = None
    raw_unit: str | None = None
    raw_price: Decimal | None = None
    raw_quantity: Decimal | None = None
    raw_article: str | None = None
    parsed_data: dict | None = None
    material_id: UUID | None = None
    match_confidence: Decimal | None = None
    status: UploadRowStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierPriceRead(BaseModel):
    id: UUID
    supplier_id: UUID
    material_id: UUID
    catalog_product_id: UUID | None = None
    price: Decimal | None = None
    currency: str
    unit: str | None = None
    region: str | None = None
    availability: str | None = None
    min_order_quantity: Decimal | None = None
    delivery_terms: str | None = None
    valid_until: date | None = None
    source_upload_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
