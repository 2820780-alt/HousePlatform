from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from app.services.module1_extraction_blueprint_registry import ExtractionBlueprintRegistry
from app.services.module1_source_profile_registry import Module1SourceProfileRegistry
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


SUPPORTED_RAW_SOURCES = ("CatalogProduct", "SupplierUploadRow", "SourceTaskResult", "raw_payload")


@dataclass(frozen=True)
class Module1RawIngestionItem:
    legacy_source: str
    source_id: Any | None = None
    source_code: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    raw_title: str | None = None
    raw_description: str | None = None
    raw_category: str | None = None
    raw_price: Decimal | None = None
    raw_unit: str | None = None
    raw_characteristics: Mapping[str, Any] | None = None
    raw_documents: tuple[Mapping[str, Any], ...] = ()
    raw_images: tuple[str, ...] = ()
    raw_availability: str | None = None
    raw_supplier: str | None = None
    raw_manufacturer: str | None = None
    region: str | None = None
    city: str | None = None
    captured_at: datetime | None = None
    observed_at: datetime | None = None
    extraction_profile_reference: str | None = None
    adapter_version: str | None = None
    source_task_version: str | None = None
    confidence: Decimal | None = None
    warnings: tuple[str, ...] = ()
    raw_payload: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class RawIngestionValidationReport:
    is_valid: bool
    missing_fields: tuple[str, ...]
    unit_warnings: tuple[str, ...]
    warnings: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class RawIngestionReadinessReport:
    ready: bool
    legacy_source: str
    source_code: str | None
    material_group: str | None
    has_raw_item: bool
    has_source_profile: bool
    has_extraction_profile: bool
    has_extraction_blueprint: bool
    missing_raw_fields: tuple[str, ...]
    missing_blueprint_fields: tuple[str, ...]
    unit_warnings: tuple[str, ...]
    warnings: tuple[str, ...]
    message: str


def build_raw_ingestion_item_from_catalog_product(product: Any) -> Module1RawIngestionItem:
    payload = _mapping(_first(_get(product, "raw_payload"), _get(product, "payload"), {}))
    source_code = _source_code(product, payload)
    source = _get(product, "source")
    return Module1RawIngestionItem(
        legacy_source="CatalogProduct",
        source_id=_get(product, "source_id"),
        source_code=source_code,
        source_type=_source_type(source_code),
        source_url=_text(_first(_get(product, "external_url"), _get(source, "url"), payload.get("source_url"))),
        raw_title=_text(_first(_get(product, "raw_name"), _get(product, "name"), payload.get("title"), payload.get("raw_name"))),
        raw_description=_text(_first(_get(product, "description"), payload.get("description"))),
        raw_category=_text(_first(_get(product, "raw_category"), payload.get("category"), payload.get("raw_category"))),
        raw_price=_decimal(_first(_get(product, "price"), payload.get("price"), payload.get("raw_price"))),
        raw_unit=_text(_first(_get(product, "unit"), payload.get("unit"), payload.get("raw_unit"))),
        raw_characteristics=_characteristics(product, payload),
        raw_documents=_documents(payload),
        raw_images=_images(payload),
        raw_availability=_text(_first(_get(product, "availability"), payload.get("availability"))),
        raw_supplier=_text(_first(_get(product, "supplier_name"), payload.get("supplier"))),
        raw_manufacturer=_text(_first(_get(product, "raw_manufacturer"), payload.get("manufacturer"))),
        region=_text(_first(_get(product, "region"), payload.get("region"))),
        city=_text(_first(_get(product, "city"), payload.get("city"))),
        captured_at=_dt(_get(product, "created_at")),
        observed_at=_dt(_first(_get(product, "updated_at"), payload.get("observed_at"))),
        adapter_version=_text(_first(payload.get("adapter_version"), payload.get("adapterVersion"))),
        confidence=_decimal(_get(product, "match_confidence")),
        raw_payload={"legacy_entity": "CatalogProduct", **payload},
    )


def build_raw_ingestion_item_from_supplier_upload_row(row: Any) -> Module1RawIngestionItem:
    payload = _mapping(_first(_get(row, "parsed_data"), _get(row, "raw_payload"), {}))
    source_code = _source_code(row, payload) or "SUPPLIER_FILE_UPLOAD"
    return Module1RawIngestionItem(
        legacy_source="SupplierUploadRow",
        source_id=_first(_get(row, "upload_id"), _get(row, "supplier_upload_id")),
        source_code=source_code,
        source_type="file",
        raw_title=_text(_first(_get(row, "raw_name"), payload.get("title"), payload.get("raw_name"))),
        raw_description=_text(payload.get("description")),
        raw_category=_text(_first(_get(row, "raw_category"), payload.get("category"))),
        raw_price=_decimal(_first(_get(row, "raw_price"), payload.get("price"))),
        raw_unit=_text(_first(_get(row, "raw_unit"), payload.get("unit"))),
        raw_characteristics=_characteristics(row, payload),
        raw_documents=_documents(payload),
        raw_images=_images(payload),
        raw_availability=_text(payload.get("availability")),
        raw_supplier=_text(_first(payload.get("supplier"), payload.get("supplier_name"))),
        raw_manufacturer=_text(_first(_get(row, "raw_manufacturer"), payload.get("manufacturer"))),
        region=_text(payload.get("region")),
        city=_text(payload.get("city")),
        captured_at=_dt(_get(row, "created_at")),
        observed_at=_dt(_get(row, "updated_at")),
        source_task_version=_text(_first(payload.get("parser_version"), payload.get("parserVersion"))),
        raw_payload={"legacy_entity": "SupplierUploadRow", "row_number": _get(row, "row_number"), "parsed_data": payload},
    )


def build_raw_ingestion_item_from_source_task_result(result: Any) -> Module1RawIngestionItem:
    payload = _mapping(_first(_get(result, "new_value"), _get(result, "old_value"), _get(result, "payload"), {}))
    task = _get(result, "task")
    source_code = _source_code(result, payload) or _source_code(task, {})
    return Module1RawIngestionItem(
        legacy_source="SourceTaskResult",
        source_id=_first(_get(result, "source_id"), _get(task, "source_id")),
        source_code=source_code,
        source_type=_source_type(source_code),
        source_url=_text(_first(payload.get("source_url"), payload.get("sourceUrl"), payload.get("url"), payload.get("external_url"))),
        raw_title=_text(_first(payload.get("raw_name"), payload.get("rawName"), payload.get("name"), payload.get("title"))),
        raw_description=_text(_first(payload.get("description"), payload.get("raw_description"))),
        raw_category=_text(_first(payload.get("raw_category"), payload.get("rawCategory"), payload.get("category"))),
        raw_price=_decimal(_first(payload.get("raw_price"), payload.get("rawPrice"), payload.get("price"))),
        raw_unit=_text(_first(payload.get("raw_unit"), payload.get("rawUnit"), payload.get("unit"))),
        raw_characteristics=_characteristics(result, payload),
        raw_documents=_documents(payload),
        raw_images=_images(payload),
        raw_availability=_text(_first(payload.get("availability"), payload.get("stock"))),
        raw_supplier=_text(_first(payload.get("supplier"), payload.get("supplier_name"))),
        raw_manufacturer=_text(_first(payload.get("manufacturer"), payload.get("raw_manufacturer"))),
        region=_text(payload.get("region")),
        city=_text(payload.get("city")),
        captured_at=_dt(_get(result, "created_at")),
        observed_at=_dt(_first(payload.get("observed_at"), _get(result, "updated_at"))),
        adapter_version=_text(_first(payload.get("adapter_version"), payload.get("adapterVersion"))),
        source_task_version=_text(_first(_get(task, "task_version"), payload.get("source_task_version"))),
        confidence=_decimal(payload.get("confidence")),
        raw_payload={"legacy_entity": "SourceTaskResult", "entity_type": _get(result, "entity_type"), "payload": payload},
    )


def validate_raw_ingestion_item(item: Module1RawIngestionItem) -> RawIngestionValidationReport:
    missing = tuple(name for name, value in (("legacy_source", item.legacy_source), ("source_code", item.source_code), ("raw_title", item.raw_title)) if not value)
    unit_warnings = ()
    if item.raw_unit and UnitConversionRegistry().normalize_unit(item.raw_unit) is None:
        unit_warnings = (f"raw_unit '{item.raw_unit}' is not recognized",)
    warnings = item.warnings
    if item.legacy_source not in SUPPORTED_RAW_SOURCES:
        warnings = warnings + (f"legacy_source '{item.legacy_source}' is not supported",)
    is_valid = not missing and not unit_warnings
    return RawIngestionValidationReport(
        is_valid=is_valid,
        missing_fields=missing,
        unit_warnings=unit_warnings,
        warnings=tuple(dict.fromkeys(warnings)),
        message="Raw ingestion item is valid for compatibility pipeline." if is_valid else "Raw ingestion item needs review.",
    )


def enrich_raw_ingestion_with_source_profile(item: Module1RawIngestionItem) -> Module1RawIngestionItem:
    if not item.source_code:
        return _warn(item, "source_code is missing; source profile cannot be attached")
    registry = Module1SourceProfileRegistry()
    profile = registry.get_source_profile(item.source_code)
    if profile is None:
        return _warn(item, f"source profile is not registered for {item.source_code}")
    extraction = registry.get_extraction_profile(item.source_code)
    return replace(
        item,
        source_type=item.source_type or profile.source_type,
        source_url=item.source_url or profile.base_url,
        region=item.region or profile.region,
        city=item.city or profile.city,
        extraction_profile_reference=item.extraction_profile_reference or (extraction.profile_code if extraction else None),
    )


def enrich_raw_ingestion_with_extraction_blueprint(item: Module1RawIngestionItem, material_group: str | None = None) -> Module1RawIngestionItem:
    if not material_group:
        return _warn(item, "material_group is required to attach extraction blueprint")
    registry = ExtractionBlueprintRegistry()
    blueprint = registry.get_blueprint(material_group)
    if blueprint is None:
        return _warn(item, f"extraction blueprint is not registered for {material_group}")
    payload = dict(item.raw_characteristics or {})
    if item.raw_unit:
        payload.setdefault("unit", item.raw_unit)
    report = registry.validate_extracted_payload(material_group, payload)
    warnings = item.warnings
    if report.missing_required:
        warnings += (f"missing required extraction fields: {', '.join(report.missing_required)}",)
    warnings += tuple(f"unit warning for {warning.field}: {warning.unit}" for warning in report.unit_warnings)
    return replace(item, extraction_profile_reference=item.extraction_profile_reference or f"{blueprint.group_code}_blueprint", warnings=tuple(dict.fromkeys(warnings)))


def build_raw_ingestion_readiness_report(item: Module1RawIngestionItem, material_group: str | None = None) -> RawIngestionReadinessReport:
    validation = validate_raw_ingestion_item(item)
    source_registry = Module1SourceProfileRegistry()
    blueprint_registry = ExtractionBlueprintRegistry()
    source_profile = source_registry.get_source_profile(item.source_code) if item.source_code else None
    extraction_profile = source_registry.get_extraction_profile(item.source_code, material_group) if item.source_code else None
    blueprint = blueprint_registry.get_blueprint(material_group) if material_group else None
    missing_blueprint_fields: tuple[str, ...] = ()
    blueprint_unit_warnings: tuple[str, ...] = ()
    if blueprint and material_group:
        payload = dict(item.raw_characteristics or {})
        if item.raw_unit:
            payload.setdefault("unit", item.raw_unit)
        report = blueprint_registry.validate_extracted_payload(material_group, payload)
        missing_blueprint_fields = report.missing_required
        blueprint_unit_warnings = tuple(f"{warning.field}: {warning.unit}" for warning in report.unit_warnings)
    unit_warnings = validation.unit_warnings + blueprint_unit_warnings
    ready = validation.is_valid and source_profile is not None and extraction_profile is not None and blueprint is not None and not missing_blueprint_fields and not unit_warnings
    return RawIngestionReadinessReport(
        ready=ready,
        legacy_source=item.legacy_source,
        source_code=item.source_code,
        material_group=blueprint.group_code if blueprint else material_group,
        has_raw_item=True,
        has_source_profile=source_profile is not None,
        has_extraction_profile=extraction_profile is not None,
        has_extraction_blueprint=blueprint is not None,
        missing_raw_fields=validation.missing_fields,
        missing_blueprint_fields=missing_blueprint_fields,
        unit_warnings=unit_warnings,
        warnings=tuple(dict.fromkeys(validation.warnings + item.warnings)),
        message="Raw ingestion item is ready for matching/moderation." if ready else "Raw ingestion item needs compatibility review.",
    )


def list_supported_raw_sources() -> tuple[str, ...]:
    return SUPPORTED_RAW_SOURCES


def _warn(item: Module1RawIngestionItem, warning: str) -> Module1RawIngestionItem:
    return replace(item, warnings=tuple(dict.fromkeys(item.warnings + (warning,))))


def _source_code(obj: Any, payload: Mapping[str, Any]) -> str | None:
    value = _text(_first(_get(obj, "source_code"), _get(obj, "sourceCode"), payload.get("sourceCode"), payload.get("source_code")))
    if value:
        return value.upper()
    source = _get(obj, "source")
    value = _text(_first(_get(source, "source_code"), _get(source, "sourceCode"), _get(source, "name")))
    return value.upper() if value else None


def _source_type(source_code: str | None) -> str | None:
    profile = Module1SourceProfileRegistry().get_source_profile(source_code) if source_code else None
    return profile.source_type if profile else None


def _characteristics(obj: Any, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(_first(payload.get("characteristics"), payload.get("raw_characteristics"), payload.get("specifications"), payload.get("attributes"), _get(obj, "characteristics"), _get(obj, "specifications")))


def _documents(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = _first(payload.get("documents"), payload.get("document_links"), payload.get("raw_documents"), ())
    if isinstance(raw, Mapping):
        return (raw,)
    if isinstance(raw, (list, tuple)):
        return tuple(item for item in raw if isinstance(item, Mapping))
    return ()


def _images(payload: Mapping[str, Any]) -> tuple[str, ...]:
    raw = _first(payload.get("images"), payload.get("image_urls"), payload.get("raw_images"), ())
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw if item)
    return ()


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _text(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", ".").strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
