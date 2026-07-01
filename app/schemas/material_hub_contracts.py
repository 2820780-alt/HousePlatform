from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    AdminDecision,
    CatalogProductStatus,
    DocumentStatus,
    DocumentType,
    MatchCandidateStatus,
    MaterialStatus,
    RegionStatus,
    SourceStatus,
    SourceType,
    SupplierStatus,
    VerificationStatus,
)


MODULE_01_MATERIAL_HUB = "MODULE_01_MATERIAL_HUB"
RegionStatusValue = RegionStatus | Literal["needs_review"]


class AuthMode(str, Enum):
    DEV = "DEV"
    MOCK = "MOCK"
    USER = "USER"
    SERVICE = "SERVICE"


class CharacteristicValueType(str, Enum):
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    RANGE = "RANGE"
    ENUM = "ENUM"
    JSON = "JSON"


class DocumentFileType(str, Enum):
    PDF = "PDF"
    XLSX = "XLSX"
    CSV = "CSV"
    JPG = "JPG"
    JPEG = "JPEG"
    PNG = "PNG"
    DOC = "DOC"
    DOCX = "DOCX"
    IMAGE = "IMAGE"
    HTML = "HTML"
    URL = "URL"
    OTHER = "OTHER"


class TextExtractionSuitability(str, Enum):
    TEXT_READY = "TEXT_READY"
    OCR_REQUIRED = "OCR_REQUIRED"
    NOT_EXTRACTABLE = "NOT_EXTRACTABLE"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    UNKNOWN = "UNKNOWN"


class DocumentOrigin(str, Enum):
    NATIVE_PDF = "native_pdf"
    SCAN = "scan"
    PHOTO = "photo"
    HTML_PAGE = "html_page"
    UPLOADED_FILE = "uploaded_file"
    EXTERNAL_LINK = "external_link"


class DocumentParseStatus(str, Enum):
    NOT_PROCESSED = "not_processed"
    PROCESSED = "processed"
    ERROR = "error"
    SKIPPED = "skipped"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class ExtendedDocumentKind(str, Enum):
    CERTIFICATE = "CERTIFICATE"
    DECLARATION = "DECLARATION"
    TECH_CARD = "TECH_CARD"
    INSTRUCTION = "INSTRUCTION"
    PASSPORT = "PASSPORT"
    MANUAL = "MANUAL"
    NODE = "NODE"
    ARTICLE = "ARTICLE"
    NORMATIVE_MATERIAL = "NORMATIVE_MATERIAL"
    REFERENCE_MATERIAL = "REFERENCE_MATERIAL"


class SourceAdapterStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class SourceProfileStatus(str, Enum):
    ACTIVE = "ACTIVE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ERROR = "ERROR"
    ARCHIVED = "ARCHIVED"


class SourceTrustLevel(str, Enum):
    TRUSTED = "TRUSTED"
    NORMAL = "NORMAL"
    TEST = "TEST"
    PROBLEM = "PROBLEM"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"


class AutomationAction(str, Enum):
    PREVIEW_ONLY = "PREVIEW_ONLY"
    CATALOG_PRODUCT_CREATED = "CATALOG_PRODUCT_CREATED"
    AUTO_PRICE_UPDATED = "AUTO_PRICE_UPDATED"
    AUTO_LINKED_TO_MATERIAL = "AUTO_LINKED_TO_MATERIAL"
    BATCH_READY = "BATCH_READY"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NEEDS_CLASSIFICATION = "NEEDS_CLASSIFICATION"
    NEEDS_REGION_REVIEW = "NEEDS_REGION_REVIEW"
    NEEDS_UNIT_REVIEW = "NEEDS_UNIT_REVIEW"
    NEEDS_DOCUMENT_REVIEW = "NEEDS_DOCUMENT_REVIEW"
    IGNORED_CANDIDATE = "IGNORED_CANDIDATE"
    DRAFT_MATERIAL_CREATED = "DRAFT_MATERIAL_CREATED"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED_BY_MODERATOR = "CONFIRMED_BY_MODERATOR"
    REJECTED_BY_MODERATOR = "REJECTED_BY_MODERATOR"
    SOURCE_STRUCTURE_ERROR = "SOURCE_STRUCTURE_ERROR"


class AccountLinkStatus(str, Enum):
    NOT_LINKED = "NOT_LINKED"
    LINK_REQUESTED = "LINK_REQUESTED"
    LINKED = "LINKED"
    SYNC_CONFLICT = "SYNC_CONFLICT"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"


class AccountSyncStatus(str, Enum):
    NOT_SYNCED = "NOT_SYNCED"
    IN_SYNC = "IN_SYNC"
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFLICT = "CONFLICT"
    ERROR = "ERROR"


class DataSourceKind(str, Enum):
    SUPPLIER_SITE = "SUPPLIER_SITE"
    API = "API"
    FILE = "FILE"
    OPEN_SOURCE = "OPEN_SOURCE"
    PLATFORM_INTERNAL = "PLATFORM_INTERNAL"


class CollectionObject(str, Enum):
    MATERIALS = "MATERIALS"
    PRICES = "PRICES"
    CHARACTERISTICS = "CHARACTERISTICS"
    DOCUMENTS = "DOCUMENTS"
    WORK_RATES = "WORK_RATES"
    SOURCE_HEALTH = "SOURCE_HEALTH"


class ProcessingScenario(str, Enum):
    INITIAL_FILL = "INITIAL_FILL"
    UPDATE_EXISTING = "UPDATE_EXISTING"
    FIND_NEW_RECORDS = "FIND_NEW_RECORDS"
    CHECK_SOURCE = "CHECK_SOURCE"
    EXTRACT_TECH_DATA = "EXTRACT_TECH_DATA"


class ResultWriteMode(str, Enum):
    PREVIEW = "PREVIEW"
    CREATE_CANDIDATES = "CREATE_CANDIDATES"
    WRITE_CONFIRMED = "WRITE_CONFIRMED"


class IngestionRecordStatus(str, Enum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    MATCH_CANDIDATE = "MATCH_CANDIDATE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class ModeratorDecisionAction(str, Enum):
    APPROVE_EXISTING = "APPROVE_EXISTING"
    CREATE_CANONICAL_FROM_CANDIDATE = "CREATE_CANONICAL_FROM_CANDIDATE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    REJECT = "REJECT"
    ARCHIVE = "ARCHIVE"


class ConstructionUsageStatus(str, Enum):
    ACTIVE = "ACTIVE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class ConstructionUsageModerationAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    UPDATE = "UPDATE"
    ARCHIVE = "ARCHIVE"


class SourceTrustPolicy(BaseModel):
    trusted_levels_for_auto_link: list[SourceTrustLevel] = Field(default_factory=lambda: [SourceTrustLevel.TRUSTED])
    allowed_levels_for_price_update: list[SourceTrustLevel] = Field(
        default_factory=lambda: [SourceTrustLevel.TRUSTED, SourceTrustLevel.NORMAL]
    )
    allowed_levels_for_draft_material: list[SourceTrustLevel] = Field(
        default_factory=lambda: [SourceTrustLevel.TRUSTED, SourceTrustLevel.NORMAL]
    )
    blocked_levels: list[SourceTrustLevel] = Field(
        default_factory=lambda: [SourceTrustLevel.PROBLEM, SourceTrustLevel.BLOCKED, SourceTrustLevel.ARCHIVED]
    )
    test_level_requires_preview: SourceTrustLevel = SourceTrustLevel.TEST


class AutoPriceUpdatePolicy(BaseModel):
    require_material_link: bool = True
    require_stable_source_identity: bool = True
    require_same_unit: bool = True
    allowed_change_fields: list[str] = Field(
        default_factory=lambda: [
            "price",
            "currency",
            "availability",
            "price_date",
            "collected_at",
            "region",
            "activeRegionCode",
            "source_region_id",
            "source_city_id",
            "delivery_zone_id",
            "region_status",
        ]
    )
    blocked_change_fields: list[str] = Field(
        default_factory=lambda: [
            "raw_name",
            "normalized_name",
            "raw_category",
            "raw_brand",
            "raw_manufacturer",
            "characteristics",
            "documents",
            "material_id",
        ]
    )
    minimum_confidence: Decimal = Decimal("0.90")


class AutoLinkPolicy(BaseModel):
    minimum_classification_confidence: Decimal = Decimal("0.95")
    minimum_matching_confidence: Decimal = Decimal("0.95")
    require_brand_or_manufacturer_match_if_present: bool = True
    require_unit_match_if_present: bool = True
    require_category_match_if_present: bool = True
    require_no_characteristic_conflict: bool = True
    require_moderator_memory_or_rule: bool = True


class DraftMaterialPolicy(BaseModel):
    allowed_write_modes: list[ResultWriteMode] = Field(
        default_factory=lambda: [ResultWriteMode.CREATE_CANDIDATES, ResultWriteMode.WRITE_CONFIRMED]
    )
    minimum_classification_confidence: Decimal = Decimal("0.90")
    require_category: bool = True
    require_unit: bool = True
    allow_active_material_creation: bool = False


class BatchModerationPolicy(BaseModel):
    minimum_group_size: int = 3
    minimum_batch_confidence: Decimal = Decimal("0.70")
    maximum_auto_decision_confidence_gap: Decimal = Decimal("0.15")
    group_by_fields: list[str] = Field(
        default_factory=lambda: [
            "category",
            "material_type",
            "brand",
            "manufacturer",
            "unit",
            "series",
            "sourceCode",
            "normalization_rule",
        ]
    )


class SafeAutomationPolicy(BaseModel):
    source_trust: SourceTrustPolicy = Field(default_factory=SourceTrustPolicy)
    auto_price_update: AutoPriceUpdatePolicy = Field(default_factory=AutoPriceUpdatePolicy)
    auto_link: AutoLinkPolicy = Field(default_factory=AutoLinkPolicy)
    draft_material: DraftMaterialPolicy = Field(default_factory=DraftMaterialPolicy)
    batch_moderation: BatchModerationPolicy = Field(default_factory=BatchModerationPolicy)
    system_user: str = "module01_safe_automation_policy"
    active_material_creation_allowed: bool = False


class AutomationDecision(BaseModel):
    model_config = {"populate_by_name": True, "use_enum_values": False}

    action: AutomationAction
    reason: str
    confidence: Decimal = Decimal("0")
    source_code: str | None = Field(default=None, alias="sourceCode")
    source_trust_level: SourceTrustLevel = Field(default=SourceTrustLevel.NORMAL, alias="sourceTrustLevel")
    applied_rule_id: UUID | str | None = Field(default=None, alias="appliedRuleId")
    moderator_rule_memory_id: UUID | str | None = Field(default=None, alias="moderatorRuleMemoryId")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    created_by: UUID | str | None = Field(default=None, alias="createdBy")
    system_user: str = Field(default="module01_safe_automation_policy", alias="systemUser")
    allowed: bool = False


class ModuleBoundaryFields(BaseModel):
    source_module_code: str | None = MODULE_01_MATERIAL_HUB
    target_module_code: str | None = None
    source_feature_code: str | None = None
    target_feature_code: str | None = None


class AuthReadyFields(BaseModel):
    created_by: UUID | None = None
    updated_by: UUID | None = None
    approved_by: UUID | None = None
    moderator_id: UUID | None = None
    workspace_id: UUID | None = None
    source_user_id: UUID | None = None
    auth_mode: AuthMode | None = None


class Module01Contract(ModuleBoundaryFields, AuthReadyFields):
    model_config = {"use_enum_values": False}


class RegionRef(BaseModel):
    id: UUID | None = None
    code: str | None = None
    name: str | None = None
    status: RegionStatus | None = None


class CityRef(BaseModel):
    id: UUID | None = None
    region_id: UUID | None = None
    name: str | None = None
    status: RegionStatus | None = None


class DeliveryZoneRef(BaseModel):
    id: UUID | None = None
    region_id: UUID | None = None
    city_id: UUID | None = None
    name: str | None = None
    status: RegionStatus | None = None


class CharacteristicSchema(Module01Contract):
    id: UUID | None = None
    schema_code: str
    title: str
    description: str | None = None
    value_type: CharacteristicValueType
    unit: str | None = None
    allowed_values: list[str] | None = None
    category_id: UUID | None = None
    material_type_id: UUID | None = None
    is_required: bool = False
    is_consumption_norm: bool = False
    weight_for_matching: Decimal | None = None
    status: VerificationStatus = VerificationStatus.NEEDS_REVIEW
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MaterialCharacteristic(Module01Contract):
    id: UUID | None = None
    material_id: UUID | None = None
    schema_code: str | None = None
    name: str
    value: str | Decimal | bool | dict[str, Any] | None = None
    unit: str | None = None
    confidence: Decimal | None = None
    is_consumption_norm: bool = False
    verified_status: VerificationStatus = VerificationStatus.NEEDS_REVIEW
    evidence_source_id: UUID | None = None
    evidence_raw_record_id: UUID | None = None
    verified_by_moderator: bool | None = None
    updated_by_moderator_at: datetime | None = None
    update_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConsumptionCharacteristic(MaterialCharacteristic):
    is_consumption_norm: bool = True
    consumption_per_unit: Decimal | None = None
    consumption_unit: str | None = None
    base_measure_unit: str | None = None
    applicable_work_type_code: str | None = None
    applicability_note: str | None = None


class RequiredCharacteristicRef(BaseModel):
    characteristic_name: str
    expected_value: str | Decimal | bool | None = None
    expected_unit: str | None = None
    condition: str | None = None


class MaterialConstructionUsage(Module01Contract):
    id: UUID | None = None
    material_id: UUID | None = None
    construction_group: str
    construction_subgroup: str | None = None
    construction_element: str | None = None
    technology_context: str | None = None
    usage_role: str | None = None
    condition: str | None = None
    required_characteristics: list[RequiredCharacteristicRef] = Field(default_factory=list)
    source_module: str | None = MODULE_01_MATERIAL_HUB
    source_reference_id: UUID | str | None = None
    confidence: Decimal | None = None
    verified_by_moderator: bool = False
    moderator_note: str | None = None
    status: ConstructionUsageStatus = ConstructionUsageStatus.NEEDS_REVIEW
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Module2TechnologyKnowledgeRef(Module01Contract):
    source_module_code: str | None = "MODULE_02_KNOWLEDGE_BASE"
    target_module_code: str | None = MODULE_01_MATERIAL_HUB
    technology: str | None = None
    construction: str | None = None
    node: str | None = None
    work_stage: str | None = None
    material_name: str | None = None
    material_role: str | None = None
    construction_group: str | None = None
    construction_subgroup: str | None = None
    usage_condition: str | None = None
    required_characteristics: list[RequiredCharacteristicRef] = Field(default_factory=list)
    linked_document_refs: list[str] = Field(default_factory=list)
    consumption_hint: str | None = None
    source_reference_id: UUID | str | None = None
    confidence: Decimal | None = None


class MaterialConstructionUsageCandidate(Module01Contract):
    id: UUID | None = None
    material_id: UUID | None = None
    material_name: str | None = None
    proposed_usage: MaterialConstructionUsage
    module2_knowledge_ref: Module2TechnologyKnowledgeRef | None = None
    status: ConstructionUsageStatus = ConstructionUsageStatus.NEEDS_REVIEW
    moderator_note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MaterialConstructionUsageModerationDecision(Module01Contract):
    id: UUID | None = None
    candidate_id: UUID | None = None
    material_id: UUID | None = None
    action: ConstructionUsageModerationAction
    updated_usage: MaterialConstructionUsage | None = None
    moderator_note: str | None = None
    decided_at: datetime | None = None


class MaterialCanonicalObject(Module01Contract):
    id: UUID | None = None
    canonical_name: str
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    material_type_id: UUID | None = None
    manufacturer_id: UUID | None = None
    brand_id: UUID | None = None
    base_unit_id: UUID | None = None
    article: str | None = None
    brand: str | None = None
    manufacturer: str | None = None
    description: str | None = None
    characteristics: list[MaterialCharacteristic] = Field(default_factory=list)
    consumption_characteristics: list[ConsumptionCharacteristic] = Field(default_factory=list)
    construction_usage: list[MaterialConstructionUsage] = Field(default_factory=list)
    status: MaterialStatus = MaterialStatus.DRAFT
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PriceObservation(Module01Contract):
    id: UUID | None = None
    material_id: UUID | None = None
    catalog_product_id: UUID | None = None
    supplier_id: UUID | None = None
    source_id: UUID | None = None
    supplier_upload_id: UUID | None = None
    price: Decimal
    currency: str = "RUB"
    unit: str | None = None
    availability: str | None = None
    price_date: datetime | None = None
    collected_at: datetime | None = None
    price_region_id: UUID | None = None
    price_city_id: UUID | None = None
    price_zone_id: UUID | None = None
    supplier_branch_id: UUID | None = None
    delivery_included: bool | None = None
    pickup_available: bool | None = None
    region_status: RegionStatusValue | None = None


class RawIngestionItem(Module01Contract):
    id: UUID | None = None
    source_id: UUID | None = None
    supplier_upload_id: UUID | None = None
    external_id: str | None = None
    external_url: str | None = None
    raw_name: str
    normalized_name: str | None = None
    raw_category: str | None = None
    raw_brand: str | None = None
    raw_manufacturer: str | None = None
    raw_unit: str | None = None
    raw_price: Decimal | None = None
    raw_quantity: Decimal | None = None
    raw_article: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    status: IngestionRecordStatus = IngestionRecordStatus.RAW
    data_source_kind: DataSourceKind | None = None
    collection_object: CollectionObject | None = None
    processing_scenario: ProcessingScenario | None = None
    write_mode: ResultWriteMode | None = None
    detected_region_id: UUID | None = None
    detected_city_id: UUID | None = None
    region_confidence: Decimal | None = None
    region_status: RegionStatusValue | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


IngestionRecord = RawIngestionItem
RawSourceRecord = RawIngestionItem


class MaterialMatchCandidateContract(Module01Contract):
    id: UUID | None = None
    catalog_product_id: UUID
    raw_record_id: UUID | None = None
    candidate_material_id: UUID | None = None
    match_score: Decimal | None = None
    match_reason: str | None = None
    ai_suggestion: str | None = None
    admin_decision: AdminDecision | None = None
    status: MatchCandidateStatus = MatchCandidateStatus.NEEDS_REVIEW
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentFileMeta(BaseModel):
    file_name: str | None = None
    file_type: DocumentFileType
    mime_type: str | None = None
    file_size_bytes: int | None = None
    checksum: str | None = None
    text_extraction_suitability: TextExtractionSuitability = TextExtractionSuitability.UNKNOWN
    is_text_extractable: bool | None = None
    page_count: int | None = None
    language: str | None = None


class DocumentRecord(Module01Contract):
    id: UUID | None = None
    material_id: UUID | None = None
    manufacturer_id: UUID | None = None
    source_id: UUID | None = None
    document_type: DocumentType | None = None
    document_kind: ExtendedDocumentKind | None = None
    title: str
    file_url: str | None = None
    source_url: str | None = None
    origin: DocumentOrigin = DocumentOrigin.EXTERNAL_LINK
    file_meta: DocumentFileMeta
    issue_date: datetime | None = None
    expiry_date: datetime | None = None
    received_at: datetime | None = None
    valid_until: datetime | None = None
    supplier_id: UUID | None = None
    linked_material_ids: list[UUID] = Field(default_factory=list)
    linked_category_ids: list[UUID] = Field(default_factory=list)
    linked_technology_refs: list[str] = Field(default_factory=list)
    regional_restrictions: str | None = None
    applicable_region_ids: list[UUID] = Field(default_factory=list)
    region_status: RegionStatusValue | None = None
    parse_status: DocumentParseStatus = DocumentParseStatus.NOT_PROCESSED
    summary: str | None = None
    change_history: list[dict[str, Any]] = Field(default_factory=list)
    status: DocumentStatus = DocumentStatus.NEEDS_REVIEW
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupplierContract(Module01Contract):
    id: UUID | None = None
    name: str
    inn: str | None = None
    site: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    contacts: dict[str, Any] = Field(default_factory=dict)
    manager_contacts: list[dict[str, Any]] = Field(default_factory=list)
    bank_details: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    supplier_account_id: UUID | None = None
    account_link_status: AccountLinkStatus = AccountLinkStatus.NOT_LINKED
    verified_account: bool = False
    linked_at: datetime | None = None
    sync_status: AccountSyncStatus = AccountSyncStatus.NOT_SYNCED
    last_synced_at: datetime | None = None
    supplier_region_id: UUID | None = None
    supplier_city_id: UUID | None = None
    delivery_zone_ids: list[UUID] = Field(default_factory=list)
    pickup_available: bool | None = None
    delivery_available: bool | None = None
    region_status: RegionStatusValue | None = None
    linked_material_ids: list[UUID] = Field(default_factory=list)
    linked_document_ids: list[UUID] = Field(default_factory=list)
    linked_source_ids: list[UUID] = Field(default_factory=list)
    upload_history_refs: list[UUID] = Field(default_factory=list)
    parsing_error_summary: list[dict[str, Any]] = Field(default_factory=list)
    status: SupplierStatus = SupplierStatus.POTENTIAL
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupplierBranchContract(Module01Contract):
    id: UUID | None = None
    supplier_id: UUID
    name: str | None = None
    branch_account_id: UUID | None = None
    account_link_status: AccountLinkStatus = AccountLinkStatus.NOT_LINKED
    verified_account: bool = False
    linked_at: datetime | None = None
    sync_status: AccountSyncStatus = AccountSyncStatus.NOT_SYNCED
    last_synced_at: datetime | None = None
    branch_region_id: UUID | None = None
    branch_city_id: UUID | None = None
    branch_delivery_zone_ids: list[UUID] = Field(default_factory=list)
    address: str | None = None
    contacts: dict[str, Any] | None = None
    manager_contacts: list[dict[str, Any]] = Field(default_factory=list)
    pickup_available: bool | None = None
    delivery_available: bool | None = None
    region_status: RegionStatusValue | None = None
    is_main: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupplierCard(Module01Contract):
    supplier: SupplierContract
    branches: list[SupplierBranchContract] = Field(default_factory=list)
    material_count: int = 0
    document_count: int = 0
    source_count: int = 0
    upload_count: int = 0
    parsing_error_count: int = 0
    archive_policy: str = "Archive instead of delete when supplier has linked prices, uploads, documents or sources."
    module8_todo: str = "Future cabinet link belongs to MODULE_08_PARTNER_PORTAL; Module 01 stores only link metadata."


class SourceSection(BaseModel):
    id: UUID | None = None
    source_id: UUID | None = None
    section_code: str | None = None
    title: str
    url: str | None = None
    category_url_contains: list[str] = Field(default_factory=list)
    status: SourceStatus | None = None


class SourceParsingRules(BaseModel):
    pagination_rules: dict[str, Any] = Field(default_factory=dict)
    product_card_rules: dict[str, Any] = Field(default_factory=dict)
    price_rules: dict[str, Any] = Field(default_factory=dict)
    characteristic_rules: dict[str, Any] = Field(default_factory=dict)
    document_rules: dict[str, Any] = Field(default_factory=dict)
    file_link_rules: dict[str, Any] = Field(default_factory=dict)
    category_detection_rules: dict[str, Any] = Field(default_factory=dict)
    region_detection_rules: dict[str, Any] = Field(default_factory=dict)


class FieldMappingRule(BaseModel):
    id: UUID | None = None
    source_field: str
    target_field: str
    target_path: str | None = None
    default_value: str | Decimal | bool | None = None
    transform: str | None = None
    confidence: Decimal | None = None
    is_required: bool = False


class CharacteristicAliasRule(BaseModel):
    source_alias: str
    canonical_name: str
    unit_hint: str | None = None
    confidence: Decimal | None = None


class UnitNormalizationRule(BaseModel):
    source_unit: str
    canonical_unit: str
    multiplier: Decimal | None = None
    note: str | None = None


class CategoryMappingRule(BaseModel):
    source_category: str
    material_hub_category_id: UUID | None = None
    material_hub_category_code: str | None = None
    confidence: Decimal | None = None
    requires_moderation: bool = True


class SourceMappingProfile(BaseModel):
    field_mapping_rules: list[FieldMappingRule] = Field(default_factory=list)
    category_mappings: list[CategoryMappingRule] = Field(default_factory=list)
    characteristic_aliases: list[CharacteristicAliasRule] = Field(default_factory=list)
    unit_normalization_rules: list[UnitNormalizationRule] = Field(default_factory=list)
    name_cleanup_rules: list[str] = Field(default_factory=list)
    manufacturer_extraction_rules: dict[str, Any] = Field(default_factory=dict)
    supplier_extraction_rules: dict[str, Any] = Field(default_factory=dict)
    moderator_update_policy: str | None = None


class SourceProfile(Module01Contract):
    id: UUID | None = None
    source_id: UUID | None = None
    name: str
    source_code: str | None = None
    display_name: str | None = None
    profile_code: str | None = None
    section_id: UUID | None = None
    section_code: str | None = None
    source_type: SourceType
    data_source_kind: DataSourceKind | None = None
    url: str | None = None
    base_url: str | None = None
    priority: int = 100
    focus_region: str | None = None
    cities: list[str] = Field(default_factory=list)
    directions: list[str] = Field(default_factory=list)
    trust_level: SourceTrustLevel = SourceTrustLevel.NORMAL
    parser_status: SourceProfileStatus | SourceAdapterStatus | None = None
    update_mode: str | None = None
    write_mode: ResultWriteMode | str | None = None
    has_prices: bool | None = None
    has_availability: bool | None = None
    has_documents: bool | None = None
    has_certificates: bool | None = None
    has_characteristics: bool | None = None
    has_region_selector: bool | None = None
    collectable_objects: list[CollectionObject] = Field(default_factory=list)
    parsing_rules: SourceParsingRules | None = None
    mapping_profile: SourceMappingProfile | None = None
    restrictions: list[str] = Field(default_factory=list)
    confidence: Decimal | None = None
    status: SourceProfileStatus = SourceProfileStatus.ACTIVE
    source_region_id: UUID | None = None
    source_city_id: UUID | None = None
    source_delivery_zone_id: UUID | None = None
    region_status: RegionStatusValue | None = None
    region_coverage: list[UUID] = Field(default_factory=list)
    city_coverage: list[UUID] = Field(default_factory=list)
    delivery_zone_coverage: list[UUID] = Field(default_factory=list)
    default_region_id: UUID | None = None
    default_city_id: UUID | None = None
    region_detection_rules: dict[str, Any] = Field(default_factory=dict)
    rate_limit_policy: dict[str, Any] = Field(default_factory=dict)
    robots_policy_note: str | None = None
    notes: str | None = None
    sections: list[SourceSection] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExtractionProfile(Module01Contract):
    id: UUID | None = None
    source_id: UUID | None = None
    source_profile_id: UUID | None = None
    profile_code: str
    title: str
    description: str | None = None
    adapter_code: str | None = None
    data_source_kind: DataSourceKind | None = None
    collectable_objects: list[CollectionObject] = Field(default_factory=list)
    parsing_rules: SourceParsingRules = Field(default_factory=SourceParsingRules)
    mapping_profile: SourceMappingProfile = Field(default_factory=SourceMappingProfile)
    field_mapping_rules: list[FieldMappingRule] = Field(default_factory=list)
    source_sections: list[SourceSection] = Field(default_factory=list)
    region_coverage: list[UUID] = Field(default_factory=list)
    city_coverage: list[UUID] = Field(default_factory=list)
    delivery_zone_coverage: list[UUID] = Field(default_factory=list)
    default_region_id: UUID | None = None
    default_city_id: UUID | None = None
    region_detection_rules: dict[str, Any] = Field(default_factory=dict)
    status: SourceAdapterStatus = SourceAdapterStatus.PLANNED
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SourceAdapter(Module01Contract):
    adapter_code: str
    source_id: UUID | None = None
    source_name: str | None = None
    data_source_kind: DataSourceKind | None = None
    supported_actions: list[str] = Field(default_factory=list)
    extraction_profile_id: UUID | None = None
    source_profile_snapshot: dict[str, Any] | None = None
    status: SourceAdapterStatus = SourceAdapterStatus.PLANNED
    last_error: str | None = None


class WorkRateObservation(Module01Contract):
    id: UUID | None = None
    source_module_code: str | None = MODULE_01_MATERIAL_HUB
    target_module_code: str | None = "MODULE_04_WORKS_COSTS"
    work_rate_source_id: UUID | None = None
    contractor_profile_ref: str | None = None
    work_producer_ref: str | None = None
    work_producer_account_id: UUID | None = None
    account_link_status: AccountLinkStatus = AccountLinkStatus.NOT_LINKED
    verified_account: bool = False
    sync_status: AccountSyncStatus = AccountSyncStatus.NOT_SYNCED
    last_synced_at: datetime | None = None
    work_name: str
    normalized_work_name: str | None = None
    raw_unit: str | None = None
    normalized_unit: str | None = None
    raw_price: Decimal | None = None
    currency: str = "RUB"
    source_price_date: datetime | None = None
    observed_at: datetime | None = None
    source_id: UUID | None = None
    source_url: str | None = None
    linked_material_ids: list[UUID] = Field(default_factory=list)
    linked_technology_refs: list[str] = Field(default_factory=list)
    linked_construction_refs: list[str] = Field(default_factory=list)
    linked_node_refs: list[str] = Field(default_factory=list)
    work_region_id: UUID | None = None
    work_city_id: UUID | None = None
    work_zone_id: UUID | None = None
    source_region_id: UUID | None = None
    region_status: RegionStatusValue | None = None
    moderation_note: str | None = None
    change_history: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal["RAW", "NORMALIZED", "NEEDS_REVIEW", "LINKED", "REJECTED"] = "RAW"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkProducerProfile(Module01Contract):
    id: UUID | None = None
    name: str
    work_producer_account_id: UUID | None = None
    account_link_status: AccountLinkStatus = AccountLinkStatus.NOT_LINKED
    verified_account: bool = False
    sync_status: AccountSyncStatus = AccountSyncStatus.NOT_SYNCED
    last_synced_at: datetime | None = None
    source_module_code: str | None = MODULE_01_MATERIAL_HUB
    target_module_code: str | None = "MODULE_04_WORKS_COSTS"
    source_refs: list[str] = Field(default_factory=list)
    status: Literal["DRAFT", "NEEDS_REVIEW", "ACTIVE", "BLOCKED", "ARCHIVED"] = "NEEDS_REVIEW"


class ModeratorDecision(Module01Contract):
    id: UUID | None = None
    decision: ModeratorDecisionAction
    admin_decision: AdminDecision | None = None
    candidate_id: UUID | None = None
    raw_record_id: UUID | None = None
    material_id: UUID | None = None
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    reason: str | None = None
    decided_at: datetime | None = None


# Backward-compatible names for sprint prompts that use short type names.
MaterialMatchCandidate = MaterialMatchCandidateContract
Supplier = SupplierContract
SupplierBranch = SupplierBranchContract
Source = SourceProfile
