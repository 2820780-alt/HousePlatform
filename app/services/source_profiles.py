from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.models.enums import SourceActionType, SourceStatus, SourceType
from app.models.source import Source
from app.schemas.material_hub_contracts import (
    CategoryMappingRule,
    CharacteristicAliasRule,
    CollectionObject,
    DataSourceKind,
    ExtractionProfile,
    FieldMappingRule,
    SourceAdapter,
    SourceAdapterStatus,
    SourceMappingProfile,
    SourceParsingRules,
    SourceProfile,
    SourceProfileStatus,
    UnitNormalizationRule,
)


SOURCE_PROFILE_SNAPSHOT_VERSION = "MODULE_01_SOURCE_PROFILE_SNAPSHOT_V1"


def attach_source_profile_snapshot(
    source: Source | None,
    action_type: SourceActionType,
    parameters: dict | None,
    *,
    adapter_code: str | None = None,
    supported_actions: set[SourceActionType] | None = None,
    force: bool = False,
) -> dict:
    payload = dict(parameters or {})
    if payload.get("source_profile_snapshot") and not force:
        return payload
    payload["source_profile_snapshot"] = build_source_profile_snapshot(
        source,
        action_type,
        payload,
        adapter_code=adapter_code,
        supported_actions=supported_actions,
    )
    return payload


def build_source_profile_snapshot(
    source: Source | None,
    action_type: SourceActionType,
    parameters: dict | None = None,
    *,
    adapter_code: str | None = None,
    supported_actions: set[SourceActionType] | None = None,
) -> dict:
    payload = dict(parameters or {})
    data_source_kind = _resolve_data_source_kind(source, action_type, payload)
    collectable_objects = _resolve_collectable_objects(action_type, payload)
    parsing_rules = _build_parsing_rules(payload)
    mapping_profile = _build_mapping_profile(payload)
    source_profile = _build_source_profile(
        source,
        data_source_kind,
        collectable_objects,
        parsing_rules,
        mapping_profile,
        payload,
    )
    extraction_profile = _build_extraction_profile(
        source,
        data_source_kind,
        collectable_objects,
        parsing_rules,
        mapping_profile,
        payload,
        adapter_code=adapter_code,
    )
    source_adapter = SourceAdapter(
        adapter_code=adapter_code or "pending_source_adapter",
        source_id=getattr(source, "id", None),
        source_name=getattr(source, "name", None),
        data_source_kind=data_source_kind,
        supported_actions=sorted(action.value for action in (supported_actions or set())),
        source_profile_snapshot={
            "profile_code": source_profile.profile_code,
            "extraction_profile_code": extraction_profile.profile_code,
        },
        status=SourceAdapterStatus.ACTIVE if adapter_code else SourceAdapterStatus.PLANNED,
    )
    return {
        "version": SOURCE_PROFILE_SNAPSHOT_VERSION,
        "source_profile": source_profile.model_dump(mode="json"),
        "extraction_profile": extraction_profile.model_dump(mode="json"),
        "source_adapter": source_adapter.model_dump(mode="json"),
        "moderator_update_ready": True,
        "notes": [
            "Profile snapshot is a preparation layer; existing source integrations still own extraction.",
            "Moderator decisions may update mapping_profile and parsing_rules later.",
            "Canonical Material must not be created directly from source/API/file data.",
        ],
    }


def _build_source_profile(
    source: Source | None,
    data_source_kind: DataSourceKind,
    collectable_objects: list[CollectionObject],
    parsing_rules: SourceParsingRules,
    mapping_profile: SourceMappingProfile,
    parameters: dict,
) -> SourceProfile:
    source_name = getattr(source, "name", None) or parameters.get("source_name") or "manual-upload"
    source_type = getattr(source, "source_type", None) or SourceType.MANUAL_UPLOAD
    region_refs = _region_refs(parameters)
    return SourceProfile(
        source_id=getattr(source, "id", None),
        name=str(source_name),
        profile_code=_profile_code(source_name, parameters.get("source_section_code")),
        section_code=parameters.get("source_section_code"),
        source_type=source_type,
        data_source_kind=data_source_kind,
        url=getattr(source, "url", None),
        priority=getattr(source, "priority", None) or 100,
        collectable_objects=collectable_objects,
        parsing_rules=parsing_rules,
        mapping_profile=mapping_profile,
        restrictions=[
            "Do not create canonical Material directly from source/API/file data.",
            "Sites, site pages and site sections are not DocumentRecord.",
            "Documents are detected only by explicit file/external-link rules.",
        ],
        confidence=Decimal("0.50"),
        status=_source_profile_status(source),
        source_region_id=region_refs["source_region_id"],
        source_city_id=region_refs["source_city_id"],
        source_delivery_zone_id=region_refs["delivery_zone_id"],
        region_status=_region_status_or_none(parameters.get("region_status")),
        region_coverage=_uuid_list(parameters.get("region_coverage") or parameters.get("source_region_id")),
        city_coverage=_uuid_list(parameters.get("city_coverage") or parameters.get("source_city_id")),
        delivery_zone_coverage=_uuid_list(
            parameters.get("delivery_zone_coverage") or parameters.get("delivery_zone_id")
        ),
        default_region_id=region_refs["source_region_id"],
        default_city_id=region_refs["source_city_id"],
        region_detection_rules=parsing_rules.region_detection_rules,
    )


def _build_extraction_profile(
    source: Source | None,
    data_source_kind: DataSourceKind,
    collectable_objects: list[CollectionObject],
    parsing_rules: SourceParsingRules,
    mapping_profile: SourceMappingProfile,
    parameters: dict,
    *,
    adapter_code: str | None,
) -> ExtractionProfile:
    source_name = getattr(source, "name", None) or parameters.get("source_name") or "manual-upload"
    region_refs = _region_refs(parameters)
    return ExtractionProfile(
        source_id=getattr(source, "id", None),
        profile_code=_profile_code(source_name, parameters.get("source_section_code"), suffix="extraction"),
        title=f"{source_name} extraction profile",
        description="Preparation layer for source-specific parsing and mapping rules.",
        adapter_code=adapter_code,
        data_source_kind=data_source_kind,
        collectable_objects=collectable_objects,
        parsing_rules=parsing_rules,
        mapping_profile=mapping_profile,
        field_mapping_rules=mapping_profile.field_mapping_rules,
        region_coverage=_uuid_list(parameters.get("region_coverage") or parameters.get("source_region_id")),
        city_coverage=_uuid_list(parameters.get("city_coverage") or parameters.get("source_city_id")),
        delivery_zone_coverage=_uuid_list(
            parameters.get("delivery_zone_coverage") or parameters.get("delivery_zone_id")
        ),
        default_region_id=region_refs["source_region_id"],
        default_city_id=region_refs["source_city_id"],
        region_detection_rules=parsing_rules.region_detection_rules,
        status=SourceAdapterStatus.ACTIVE if adapter_code else SourceAdapterStatus.PLANNED,
    )


def _build_parsing_rules(parameters: dict) -> SourceParsingRules:
    category_filters = parameters.get("category_url_contains") or parameters.get("category_filters") or []
    return SourceParsingRules(
        pagination_rules={
            "scan_mode": parameters.get("scan_mode"),
            "max_pages": parameters.get("max_pages"),
            "max_attempts": parameters.get("max_attempts"),
            "max_documents": parameters.get("max_documents"),
        },
        product_card_rules={
            "category_url_contains": category_filters,
            "product_card_selector": parameters.get("product_card_selector"),
            "product_url_markers": parameters.get("product_url_markers"),
        },
        price_rules={
            "price_selector": parameters.get("price_selector"),
            "currency": parameters.get("currency", "RUB"),
            "delivery_included": parameters.get("delivery_included"),
            "pickup_available": parameters.get("pickup_available"),
        },
        characteristic_rules={
            "characteristic_table_selector": parameters.get("characteristic_table_selector"),
            "characteristic_aliases_source": "mapping_profile.characteristic_aliases",
        },
        document_rules={
            "document_type": parameters.get("document_type"),
            "document_title_selector": parameters.get("document_title_selector"),
            "site_page_is_document": False,
        },
        file_link_rules={
            "allowed_extensions": parameters.get("document_extensions")
            or ["pdf", "csv", "xlsx", "jpg", "jpeg", "png", "doc", "docx", "html"],
            "pdf_link_selector": parameters.get("pdf_link_selector"),
        },
        category_detection_rules={
            "source_category_selector": parameters.get("source_category_selector"),
            "category_url_contains": category_filters,
        },
        region_detection_rules={
            "activeRegionCode": parameters.get("activeRegionCode"),
            "source_region_id": parameters.get("source_region_id"),
            "source_city_id": parameters.get("source_city_id"),
            "delivery_zone_id": parameters.get("delivery_zone_id"),
            "region_status": parameters.get("region_status") or "needs_review",
        },
    )


def _build_mapping_profile(parameters: dict) -> SourceMappingProfile:
    return SourceMappingProfile(
        field_mapping_rules=[
            FieldMappingRule(source_field="name", target_field="raw_name", target_path="raw_record.raw_name", is_required=True),
            FieldMappingRule(source_field="price", target_field="price", target_path="price_observation.price"),
            FieldMappingRule(source_field="unit", target_field="unit", target_path="material.characteristics.unit"),
            FieldMappingRule(source_field="category", target_field="raw_category", target_path="raw_record.raw_category"),
            FieldMappingRule(source_field="manufacturer", target_field="manufacturer", target_path="material.manufacturer"),
            FieldMappingRule(source_field="supplier", target_field="supplier", target_path="supplier.name"),
            FieldMappingRule(source_field="document_url", target_field="file_url", target_path="document.file_url"),
        ],
        category_mappings=[
            CategoryMappingRule(source_category=value, confidence=Decimal("0.50"))
            for value in _string_list(parameters.get("category_filters") or parameters.get("category_url_contains"))
        ],
        characteristic_aliases=[
            CharacteristicAliasRule(source_alias="расход", canonical_name="Норма расхода", confidence=Decimal("0.60")),
            CharacteristicAliasRule(source_alias="consumption", canonical_name="Норма расхода", confidence=Decimal("0.60")),
        ],
        unit_normalization_rules=[
            UnitNormalizationRule(source_unit="м2", canonical_unit="м²", multiplier=Decimal("1")),
            UnitNormalizationRule(source_unit="m2", canonical_unit="м²", multiplier=Decimal("1")),
            UnitNormalizationRule(source_unit="кг", canonical_unit="кг", multiplier=Decimal("1")),
            UnitNormalizationRule(source_unit="л", canonical_unit="л", multiplier=Decimal("1")),
        ],
        name_cleanup_rules=[
            "trim_whitespace",
            "collapse_spaces",
            "keep_brand_and_article_as_attributes",
        ],
        manufacturer_extraction_rules={"source_field": "manufacturer", "fallback": "brand"},
        supplier_extraction_rules={"source_field": "supplier", "fallback": parameters.get("supplier_name")},
        moderator_update_policy="Moderator decisions may append category mappings, aliases and transforms.",
    )


def _resolve_data_source_kind(
    source: Source | None,
    action_type: SourceActionType,
    parameters: dict,
) -> DataSourceKind:
    raw_kind = parameters.get("data_source_kind")
    if raw_kind:
        try:
            return DataSourceKind(str(raw_kind).upper())
        except ValueError:
            pass
    if action_type == SourceActionType.UPLOAD_SUPPLIER_FILE:
        return DataSourceKind.FILE
    if getattr(source, "source_type", None) == SourceType.MANUAL_UPLOAD:
        return DataSourceKind.FILE
    return DataSourceKind.SUPPLIER_SITE


def _resolve_collectable_objects(action_type: SourceActionType, parameters: dict) -> list[CollectionObject]:
    raw_object = parameters.get("collection_object")
    if raw_object:
        try:
            return [CollectionObject(str(raw_object).upper())]
        except ValueError:
            pass
    mapping = {
        SourceActionType.INITIAL_MATERIAL_SCAN: [CollectionObject.MATERIALS, CollectionObject.PRICES],
        SourceActionType.FIND_NEW_PRODUCTS: [CollectionObject.MATERIALS],
        SourceActionType.UPDATE_PRICES: [CollectionObject.PRICES],
        SourceActionType.UPDATE_SPECIFICATIONS: [CollectionObject.CHARACTERISTICS],
        SourceActionType.UPDATE_CERTIFICATES: [CollectionObject.DOCUMENTS],
        SourceActionType.UPDATE_TECH_DOCUMENTS: [CollectionObject.DOCUMENTS],
        SourceActionType.CHECK_SOURCE_HEALTH: [CollectionObject.SOURCE_HEALTH],
        SourceActionType.UPLOAD_SUPPLIER_FILE: [CollectionObject.MATERIALS, CollectionObject.PRICES],
    }
    return mapping.get(action_type, [CollectionObject.MATERIALS])


def _source_profile_status(source: Source | None) -> SourceProfileStatus:
    status = getattr(source, "status", None)
    if status == SourceStatus.ERROR:
        return SourceProfileStatus.ERROR
    if status == SourceStatus.ACTIVE or source is None:
        return SourceProfileStatus.ACTIVE
    return SourceProfileStatus.NEEDS_REVIEW


def _region_refs(parameters: dict) -> dict[str, UUID | None]:
    return {
        "source_region_id": _uuid_or_none(parameters.get("source_region_id")),
        "source_city_id": _uuid_or_none(parameters.get("source_city_id")),
        "delivery_zone_id": _uuid_or_none(parameters.get("delivery_zone_id")),
    }


def _uuid_list(value) -> list[UUID]:
    return [item for item in (_uuid_or_none(raw) for raw in _string_list(value)) if item]


def _uuid_or_none(value) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _region_status_or_none(value):
    if not value:
        return None
    try:
        from app.models.enums import RegionStatus

        return RegionStatus(str(value).upper())
    except ValueError:
        return None


def _string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _profile_code(source_name: str, section_code: str | None = None, *, suffix: str = "source") -> str:
    raw = "_".join(part for part in (source_name, section_code, suffix) if part)
    normalized = "".join(ch if ch.isalnum() else "_" for ch in raw.lower())
    return "_".join(part for part in normalized.split("_") if part)
