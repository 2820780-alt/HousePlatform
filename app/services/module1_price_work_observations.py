from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from app.services.module1_canonical_material_store import MaterialCanonicalView
from app.services.module1_participants_directory import (
    MaterialParticipantRecord,
    build_participant_record_from_price_ref,
)
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


OBSERVATION_TYPES = frozenset(
    {
        "material_price",
        "supplier_price",
        "catalog_price",
        "regional_average_hint",
        "work_rate",
        "delivery_price_hint",
        "unknown",
    }
)

OBSERVATION_TYPE_ALIASES: Mapping[str, str] = {
    "price": "material_price",
    "supplierprice": "supplier_price",
    "supplier_price_ref": "supplier_price",
    "catalogproduct": "catalog_price",
    "catalog_product": "catalog_price",
    "raw_ingestion": "catalog_price",
    "regional_average": "regional_average_hint",
    "average": "regional_average_hint",
    "work": "work_rate",
    "rate": "work_rate",
    "delivery": "delivery_price_hint",
}


@dataclass(frozen=True)
class ObservationSourceRef:
    source_id: str | None = None
    source_code: str | None = None
    source_name: str | None = None
    source_type: str | None = None
    url: str | None = None
    participant_ref: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ObservationRegion:
    country: str | None = None
    region: str | None = None
    city: str | None = None


@dataclass(frozen=True)
class ObservationUnitInfo:
    raw_unit: str | None
    normalized_unit: str | None
    is_supported: bool
    conversion_requires_material_profile: bool = False
    warnings: tuple[str, ...] = tuple()


@dataclass(frozen=True)
class MaterialPriceObservation:
    observation_id: str | None
    stable_key: str
    observation_type: str
    material_id: str | None
    material_group: str | None
    material_name: str | None
    participant: MaterialParticipantRecord | None
    source_ref: ObservationSourceRef | None
    region: ObservationRegion
    price_value: Decimal | None
    currency: str | None
    price_unit: str | None
    unit_info: ObservationUnitInfo
    vat_included: bool | None
    delivery_included: bool | None
    observed_at: str | None
    valid_from: str | None
    valid_to: str | None
    confidence: Decimal
    warnings: tuple[str, ...]
    provenance_refs: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class WorkRateObservation:
    observation_id: str | None
    stable_key: str
    work_type: str
    work_code: str | None
    usage_context: str | None
    region: ObservationRegion
    rate_value: Decimal | None
    currency: str | None
    unit: str | None
    unit_info: ObservationUnitInfo
    source_ref: ObservationSourceRef | None
    observed_at: str | None
    confidence: Decimal
    warnings: tuple[str, ...]
    provenance_refs: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ObservationValidationReport:
    is_valid: bool
    observation_id: str | None
    observation_type: str
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    suspicious: bool
    message: str


@dataclass(frozen=True)
class ObservationReadinessReport:
    material_id: str | None
    material_name: str | None
    material_group: str | None
    price_observation_count: int
    work_rate_observation_count: int
    has_prices: bool
    has_region: bool
    has_source: bool
    has_observed_date: bool
    has_supported_units: bool
    duplicate_stable_keys: tuple[str, ...]
    suspicious_observations: tuple[str, ...]
    missing_details: tuple[str, ...]
    warnings: tuple[str, ...]
    status: str
    message: str


@dataclass(frozen=True)
class PriceObservationPackage:
    material_id: str | None
    material_name: str
    material_group: str | None
    observations: tuple[MaterialPriceObservation, ...]
    readiness: ObservationReadinessReport
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class WorkRateObservationPackage:
    observations: tuple[WorkRateObservation, ...]
    validation_reports: tuple[ObservationValidationReport, ...]
    warnings: tuple[str, ...]


def build_price_observation_from_supplier_price(
    supplier_price: Any,
    *,
    material_id: str | None = None,
    material_group: str | None = None,
    material_name: str | None = None,
) -> MaterialPriceObservation:
    supplier = _value(supplier_price, "supplier")
    price_ref = {
        "priceId": _value(supplier_price, "id", "priceId", "price_id"),
        "supplierId": _value(supplier_price, "supplier_id", "supplierId") or _value(supplier, "id"),
        "supplierName": _value(supplier, "name", "display_name") or _value(supplier_price, "supplierName", "supplier_name"),
        "region": _value(supplier_price, "region"),
    }
    participant = build_participant_record_from_price_ref(
        price_ref,
        material_id=material_id or _as_string(_value(supplier_price, "material_id", "materialId")),
        material_group=material_group,
        material_name=material_name,
    )
    source_ref = _source_ref_from_price(supplier_price, participant)
    price_value = _decimal(_value(supplier_price, "price", "price_value", "priceValue"))
    currency = normalize_observation_currency(_value(supplier_price, "currency"))
    unit = _as_string(_value(supplier_price, "unit", "price_unit", "priceUnit"))
    unit_info = normalize_observation_unit(unit, material_group=material_group)
    observed_at = _date_string(_value(supplier_price, "collected_at", "created_at", "updated_at", "observedAt"))
    valid_to = _date_string(_value(supplier_price, "valid_until", "validUntil", "valid_to", "validTo"))
    warnings = _price_warnings(price_value, unit_info)
    return _price_observation(
        observation_id=_as_string(_value(supplier_price, "id", "priceId", "price_id")),
        observation_type="supplier_price",
        material_id=material_id or _as_string(_value(supplier_price, "material_id", "materialId")),
        material_group=material_group,
        material_name=material_name,
        participant=participant,
        source_ref=source_ref,
        region=normalize_observation_region(supplier_price),
        price_value=price_value,
        currency=currency,
        price_unit=unit,
        unit_info=unit_info,
        vat_included=_bool_or_none(_value(supplier_price, "vat_included", "vatIncluded")),
        delivery_included=_bool_or_none(_value(supplier_price, "delivery_included", "deliveryIncluded")),
        observed_at=observed_at,
        valid_from=_date_string(_value(supplier_price, "valid_from", "validFrom")),
        valid_to=valid_to,
        confidence=classify_observation_confidence({"source": "SupplierPrice", "price": price_value, "unit": unit}),
        warnings=warnings,
        provenance_refs=(MappingProxyType({"source": "SupplierPrice", "priceId": _as_string(_value(supplier_price, "id"))}),),
    )

def build_price_observation_from_price_history(
    history: Any,
    *,
    material_id: str | None = None,
    material_group: str | None = None,
    material_name: str | None = None,
) -> MaterialPriceObservation:
    price_value = _decimal(_value(history, "price", "price_value", "priceValue"))
    currency = normalize_observation_currency(_value(history, "currency"))
    unit = _as_string(_value(history, "unit", "price_unit", "priceUnit"))
    unit_info = normalize_observation_unit(unit, material_group=material_group)
    participant = None
    if _value(history, "supplier_id", "supplierId") or _value(history, "supplierName", "supplier_name"):
        participant = build_participant_record_from_price_ref(
            {
                "priceId": _value(history, "id", "priceId", "price_id"),
                "supplierId": _value(history, "supplier_id", "supplierId"),
                "supplierName": _value(history, "supplierName", "supplier_name"),
                "region": _value(history, "region"),
            },
            material_id=material_id or _as_string(_value(history, "material_id", "materialId")),
            material_group=material_group,
            material_name=material_name,
        )
    source_ref = ObservationSourceRef(
        source_id=_as_string(_value(history, "source_id", "sourceId")),
        source_code=_as_string(_value(history, "source_code", "sourceCode")),
        source_name=_as_string(_value(history, "sourceName", "source_name")),
        source_type=_as_string(_value(history, "sourceType", "source_type")),
        url=_as_string(_value(history, "source_url", "sourceUrl")),
        participant_ref=MappingProxyType(
            {
                "stableKey": participant.stable_key,
                "participantType": participant.participant_type,
                "displayName": participant.display_name,
            }
        )
        if participant
        else None,
        provenance=MappingProxyType({"source": "PriceHistory"}),
    )
    if not any((source_ref.source_id, source_ref.source_code, source_ref.source_name, source_ref.url, participant)):
        source_ref = None
    return _price_observation(
        observation_id=_as_string(_value(history, "id", "priceId", "price_id")),
        observation_type="material_price",
        material_id=material_id or _as_string(_value(history, "material_id", "materialId")),
        material_group=material_group,
        material_name=material_name,
        participant=participant,
        source_ref=source_ref,
        region=normalize_observation_region(history),
        price_value=price_value,
        currency=currency,
        price_unit=unit,
        unit_info=unit_info,
        vat_included=_bool_or_none(_value(history, "vat_included", "vatIncluded")),
        delivery_included=_bool_or_none(_value(history, "delivery_included", "deliveryIncluded")),
        observed_at=_date_string(_value(history, "collected_at", "observedAt", "created_at")),
        valid_from=_date_string(_value(history, "price_date", "priceDate")),
        valid_to=None,
        confidence=classify_observation_confidence({"source": "PriceHistory", "price": price_value, "unit": unit}),
        warnings=_price_warnings(price_value, unit_info),
        provenance_refs=(MappingProxyType({"source": "PriceHistory", "historyId": _as_string(_value(history, "id"))}),),
    )

def build_price_observation_from_catalog_product(
    product: Any,
    *,
    material_id: str | None = None,
    material_group: str | None = None,
    material_name: str | None = None,
) -> MaterialPriceObservation:
    payload = _mapping(_value(product, "raw_payload", "payload"))
    price_value = _decimal(_first(_value(product, "price"), payload.get("price"), payload.get("raw_price")))
    unit = _as_string(_first(_value(product, "unit"), payload.get("unit"), payload.get("raw_unit")))
    source = _value(product, "source")
    source_ref = ObservationSourceRef(
        source_id=_as_string(_value(product, "source_id") or _value(source, "id")),
        source_code=_as_string(_value(product, "source_code", "sourceCode") or payload.get("source_code") or payload.get("sourceCode")),
        source_name=_as_string(_value(source, "name", "display_name") or payload.get("source_name")),
        source_type=_enum_value(_value(source, "source_type")),
        url=_as_string(_first(_value(product, "external_url"), payload.get("url"), payload.get("external_url"))),
        participant_ref=None,
        provenance=MappingProxyType({"source": "CatalogProduct"}),
    )
    unit_info = normalize_observation_unit(unit, material_group=material_group)
    return _price_observation(
        observation_id=_as_string(_value(product, "id", "catalogProductId")),
        observation_type="catalog_price",
        material_id=material_id or _as_string(_value(product, "material_id", "materialId")),
        material_group=material_group,
        material_name=material_name or _as_string(_first(_value(product, "normalized_name"), _value(product, "raw_name"), payload.get("title"))),
        participant=None,
        source_ref=source_ref,
        region=normalize_observation_region({"region": _first(_value(product, "region"), payload.get("region")), "city": _first(_value(product, "city"), payload.get("city"))}),
        price_value=price_value,
        currency=normalize_observation_currency(_first(_value(product, "currency"), payload.get("currency"))),
        price_unit=unit,
        unit_info=unit_info,
        vat_included=_bool_or_none(_first(_value(product, "vat_included"), payload.get("vat_included"), payload.get("vatIncluded"))),
        delivery_included=_bool_or_none(_first(_value(product, "delivery_included"), payload.get("delivery_included"), payload.get("deliveryIncluded"))),
        observed_at=_date_string(_first(_value(product, "updated_at"), payload.get("observed_at"), payload.get("observedAt"))),
        valid_from=_date_string(_first(payload.get("valid_from"), payload.get("validFrom"))),
        valid_to=_date_string(_first(payload.get("valid_to"), payload.get("validTo"))),
        confidence=classify_observation_confidence({"source": "CatalogProduct", "confidence": _value(product, "match_confidence"), "price": price_value, "unit": unit}),
        warnings=_price_warnings(price_value, unit_info),
        provenance_refs=(MappingProxyType({"source": "CatalogProduct", "catalogProductId": _as_string(_value(product, "id"))}),),
    )


def build_price_observation_from_raw_ingestion(
    raw_item: Module1RawIngestionItem | Any,
    *,
    material_id: str | None = None,
    material_group: str | None = None,
    material_name: str | None = None,
) -> MaterialPriceObservation:
    price_value = _decimal(_value(raw_item, "raw_price", "price"))
    unit = _as_string(_value(raw_item, "raw_unit", "unit"))
    source_ref = ObservationSourceRef(
        source_id=_as_string(_value(raw_item, "source_id")),
        source_code=_as_string(_value(raw_item, "source_code")),
        source_name=_as_string(_value(raw_item, "source_name")),
        source_type=_as_string(_value(raw_item, "source_type")),
        url=_as_string(_value(raw_item, "source_url")),
        participant_ref=None,
        provenance=MappingProxyType({"source": "RawIngestionItem", "legacySource": _value(raw_item, "legacy_source")}),
    )
    unit_info = normalize_observation_unit(unit, material_group=material_group)
    return _price_observation(
        observation_id=None,
        observation_type=classify_observation_type("raw_ingestion"),
        material_id=material_id,
        material_group=material_group,
        material_name=material_name or _as_string(_value(raw_item, "raw_title")),
        participant=None,
        source_ref=source_ref,
        region=normalize_observation_region(raw_item),
        price_value=price_value,
        currency=normalize_observation_currency(_value(raw_item, "currency")),
        price_unit=unit,
        unit_info=unit_info,
        vat_included=None,
        delivery_included=None,
        observed_at=_date_string(_first(_value(raw_item, "observed_at"), _value(raw_item, "captured_at"))),
        valid_from=None,
        valid_to=None,
        confidence=classify_observation_confidence({"source": "RawIngestionItem", "confidence": _value(raw_item, "confidence"), "price": price_value, "unit": unit}),
        warnings=_price_warnings(price_value, unit_info),
        provenance_refs=(MappingProxyType({"source": "RawIngestionItem", "sourceCode": _as_string(_value(raw_item, "source_code"))}),),
    )


def build_work_rate_observation(observation: Any | None = None, **overrides: Any) -> WorkRateObservation:
    data = {**(_mapping(observation)), **overrides}
    work_type = _as_string(_first(data.get("work_type"), data.get("workType"), data.get("type"))) or "unknown_work"
    work_code = _as_string(_first(data.get("work_code"), data.get("workCode"), data.get("code")))
    unit = _as_string(data.get("unit"))
    unit_info = normalize_observation_unit(unit)
    rate_value = _decimal(_first(data.get("rate_value"), data.get("rateValue"), data.get("price"), data.get("value")))
    source_ref = ObservationSourceRef(
        source_id=_as_string(_first(data.get("source_id"), data.get("sourceId"))),
        source_code=_as_string(_first(data.get("source_code"), data.get("sourceCode"))),
        source_name=_as_string(_first(data.get("source_name"), data.get("sourceName"))),
        source_type=_as_string(_first(data.get("source_type"), data.get("sourceType"))),
        url=_as_string(data.get("url")),
        participant_ref=None,
        provenance=MappingProxyType({"source": "WorkRateObservation"}),
    )
    warnings = []
    if rate_value is not None and rate_value <= 0:
        warnings.append("Work rate value must be positive.")
    warnings.extend(unit_info.warnings)
    stable_key = _stable_key(
        "work_rate",
        _as_string(_first(data.get("id"), data.get("observation_id"), data.get("observationId"))),
        work_type,
        rate_value,
        unit_info.normalized_unit or unit,
        _as_string(_first(data.get("region"), data.get("city"))),
        _date_string(_first(data.get("observed_at"), data.get("observedAt"))),
    )
    return WorkRateObservation(
        observation_id=_as_string(_first(data.get("id"), data.get("observation_id"), data.get("observationId"))),
        stable_key=stable_key,
        work_type=work_type,
        work_code=work_code,
        usage_context=_as_string(_first(data.get("usage_context"), data.get("usageContext"))),
        region=normalize_observation_region(data),
        rate_value=rate_value,
        currency=normalize_observation_currency(data.get("currency")),
        unit=unit,
        unit_info=unit_info,
        source_ref=source_ref if any((source_ref.source_id, source_ref.source_code, source_ref.source_name, source_ref.url)) else None,
        observed_at=_date_string(_first(data.get("observed_at"), data.get("observedAt"))),
        confidence=classify_observation_confidence({"source": "work_rate", "confidence": data.get("confidence"), "price": rate_value, "unit": unit}),
        warnings=tuple(dict.fromkeys(warnings)),
        provenance_refs=(MappingProxyType({"source": "work_rate_observation"}),),
    )


def normalize_observation_unit(unit: str | None, *, material_group: str | None = None) -> ObservationUnitInfo:
    registry = UnitConversionRegistry()
    normalized = registry.normalize_unit(unit)
    warnings = []
    if unit and normalized is None:
        warnings.append(f"Unit '{unit}' is not supported by Module 1 unit dictionary.")
    return ObservationUnitInfo(
        raw_unit=unit,
        normalized_unit=normalized,
        is_supported=normalized is not None,
        conversion_requires_material_profile=False,
        warnings=tuple(warnings),
    )


def normalize_observation_currency(currency: Any) -> str | None:
    value = _as_string(currency)
    if not value:
        return "RUB"
    normalized = value.strip().upper()
    if normalized in {"RUR", "РУБ", "RUBLE", "RUBLES"}:
        return "RUB"
    return normalized


def normalize_observation_region(value: Any) -> ObservationRegion:
    return ObservationRegion(
        country=_as_string(_value(value, "country")),
        region=_as_string(_value(value, "region")),
        city=_as_string(_value(value, "city")),
    )


def classify_observation_type(value: Any) -> str:
    normalized = _normalize_key(_enum_value(value))
    if not normalized:
        return "unknown"
    normalized = OBSERVATION_TYPE_ALIASES.get(normalized, normalized)
    return normalized if normalized in OBSERVATION_TYPES else "unknown"


def classify_observation_confidence(observation: Any) -> Decimal:
    explicit = _decimal(_value(observation, "confidence"))
    if explicit is not None:
        return explicit
    source = _normalize_key(_value(observation, "source"))
    price = _decimal(_value(observation, "price"))
    unit = _value(observation, "unit")
    if source == "supplierprice":
        return Decimal("0.90") if price is not None and unit else Decimal("0.65")
    if source == "catalogproduct":
        return Decimal("0.74") if price is not None and unit else Decimal("0.55")
    if source == "rawingestionitem":
        return Decimal("0.66") if price is not None and unit else Decimal("0.45")
    if source == "work_rate":
        return Decimal("0.60") if price is not None and unit else Decimal("0.40")
    return Decimal("0.50")


def validate_price_observation(observation: MaterialPriceObservation) -> ObservationValidationReport:
    missing = []
    warnings = list(observation.warnings)
    if observation.price_value is None:
        missing.append("price_value")
    if not observation.currency:
        missing.append("currency")
    if not observation.price_unit:
        missing.append("price_unit")
    if not observation.unit_info.is_supported:
        missing.append("supported_unit")
    if not (observation.region.region or observation.region.city):
        missing.append("region")
    if observation.source_ref is None:
        missing.append("source_ref")
    if not observation.observed_at:
        missing.append("observed_at")
    suspicious = _is_suspicious_price(observation.price_value)
    if suspicious:
        warnings.append("Price value is suspicious and needs review.")
    return ObservationValidationReport(
        is_valid=not missing and not suspicious,
        observation_id=observation.observation_id,
        observation_type=observation.observation_type,
        missing_fields=tuple(missing),
        warnings=tuple(dict.fromkeys(warnings)),
        suspicious=suspicious,
        message="Price observation is valid read-only evidence." if not missing and not suspicious else "Price observation needs review.",
    )


def validate_work_rate_observation(observation: WorkRateObservation) -> ObservationValidationReport:
    missing = []
    warnings = list(observation.warnings)
    if not observation.work_type or observation.work_type == "unknown_work":
        missing.append("work_type")
    if observation.rate_value is None:
        missing.append("rate_value")
    if not observation.currency:
        missing.append("currency")
    if not observation.unit:
        missing.append("unit")
    if not observation.unit_info.is_supported:
        missing.append("supported_unit")
    if not (observation.region.region or observation.region.city):
        missing.append("region")
    if observation.source_ref is None:
        missing.append("source_ref")
    if not observation.observed_at:
        missing.append("observed_at")
    suspicious = _is_suspicious_price(observation.rate_value)
    if suspicious:
        warnings.append("Work rate value is suspicious and needs review.")
    return ObservationValidationReport(
        is_valid=not missing and not suspicious,
        observation_id=observation.observation_id,
        observation_type="work_rate",
        missing_fields=tuple(missing),
        warnings=tuple(dict.fromkeys(warnings)),
        suspicious=suspicious,
        message="Work rate observation is valid read-only evidence." if not missing and not suspicious else "Work rate observation needs review.",
    )


def list_price_observations_for_material(canonical_material_view: MaterialCanonicalView) -> tuple[MaterialPriceObservation, ...]:
    raw = _price_observations_for_material(canonical_material_view)
    return deduplicate_price_observations(raw)


def build_price_observation_package(canonical_material_view: MaterialCanonicalView) -> PriceObservationPackage:
    observations = list_price_observations_for_material(canonical_material_view)
    readiness = build_observation_readiness_report(canonical_material_view)
    warnings = tuple(
        dict.fromkeys(
            tuple(warning for observation in observations for warning in observation.warnings)
            + readiness.warnings
        )
    )
    return PriceObservationPackage(
        material_id=canonical_material_view.material_id,
        material_name=canonical_material_view.canonical_name,
        material_group=_group_code(canonical_material_view),
        observations=observations,
        readiness=readiness,
        warnings=warnings,
    )


def build_work_rate_observation_package(observations: Iterable[Any] | None = None) -> WorkRateObservationPackage:
    work_rates = tuple(
        item if isinstance(item, WorkRateObservation) else build_work_rate_observation(item)
        for item in observations or tuple()
    )
    reports = tuple(validate_work_rate_observation(item) for item in work_rates)
    warnings = tuple(dict.fromkeys(tuple(warning for item in work_rates for warning in item.warnings)))
    return WorkRateObservationPackage(
        observations=work_rates,
        validation_reports=reports,
        warnings=warnings,
    )


def build_observation_readiness_report(canonical_material_view: MaterialCanonicalView) -> ObservationReadinessReport:
    raw_observations = _price_observations_for_material(canonical_material_view)
    observations = deduplicate_price_observations(raw_observations)
    reports = tuple(validate_price_observation(item) for item in observations)
    duplicate_keys = _duplicate_keys(raw_observations)
    suspicious = tuple(item.stable_key for item, report in zip(observations, reports) if report.suspicious)
    has_prices = bool(observations)
    has_region = any(item.region.region or item.region.city for item in observations)
    has_source = any(item.source_ref is not None for item in observations)
    has_observed_date = any(item.observed_at for item in observations)
    has_supported_units = any(item.unit_info.is_supported for item in observations)
    missing = []
    if not has_prices:
        missing.append("price_observations")
    if not has_region:
        missing.append("regional_binding")
    if not has_source:
        missing.append("price_source")
    if not has_observed_date:
        missing.append("observed_date")
    if not has_supported_units:
        missing.append("supported_unit")
    warnings = []
    if duplicate_keys:
        warnings.append("Duplicate price observations were detected and merged read-only.")
    if suspicious:
        warnings.append("Suspicious price observations need review.")
    if missing:
        warnings.append("Observation package is missing details before Module 5 handoff.")
    status = "ready"
    if not has_prices:
        status = "missing_prices"
    elif duplicate_keys or suspicious or missing:
        status = "needs_review"
    return ObservationReadinessReport(
        material_id=canonical_material_view.material_id,
        material_name=canonical_material_view.canonical_name,
        material_group=_group_code(canonical_material_view),
        price_observation_count=len(observations),
        work_rate_observation_count=0,
        has_prices=has_prices,
        has_region=has_region,
        has_source=has_source,
        has_observed_date=has_observed_date,
        has_supported_units=has_supported_units,
        duplicate_stable_keys=duplicate_keys,
        suspicious_observations=suspicious,
        missing_details=tuple(missing),
        warnings=tuple(warnings),
        status=status,
        message="Observation readiness evaluated without estimates, procurement, analytics or parsing.",
    )


def deduplicate_price_observations(
    observations: tuple[MaterialPriceObservation, ...] | list[MaterialPriceObservation],
) -> tuple[MaterialPriceObservation, ...]:
    merged: dict[str, MaterialPriceObservation] = {}
    order: list[str] = []
    for observation in observations:
        key = observation.stable_key
        if key not in merged:
            merged[key] = observation
            order.append(key)
            continue
        merged[key] = _merge_observation(merged[key], observation)
    return tuple(merged[key] for key in order)


def _price_observations_for_material(canonical_material_view: MaterialCanonicalView) -> tuple[MaterialPriceObservation, ...]:
    material_group = _group_code(canonical_material_view)
    observations = [
        build_price_observation_from_supplier_price(
            price_ref,
            material_id=canonical_material_view.material_id,
            material_group=material_group,
            material_name=canonical_material_view.canonical_name,
        )
        for price_ref in canonical_material_view.supplier_price_refs
    ]
    return tuple(observations)


def _price_observation(
    *,
    observation_id: str | None,
    observation_type: str,
    material_id: str | None,
    material_group: str | None,
    material_name: str | None,
    participant: MaterialParticipantRecord | None,
    source_ref: ObservationSourceRef | None,
    region: ObservationRegion,
    price_value: Decimal | None,
    currency: str | None,
    price_unit: str | None,
    unit_info: ObservationUnitInfo,
    vat_included: bool | None,
    delivery_included: bool | None,
    observed_at: str | None,
    valid_from: str | None,
    valid_to: str | None,
    confidence: Decimal,
    warnings: tuple[str, ...],
    provenance_refs: tuple[Mapping[str, Any], ...],
) -> MaterialPriceObservation:
    stable_key = _stable_key(
        observation_type,
        material_id,
        _participant_key(participant),
        price_value,
        currency,
        unit_info.normalized_unit or price_unit,
        region.region or region.city,
        observed_at or valid_to,
    )
    return MaterialPriceObservation(
        observation_id=observation_id,
        stable_key=stable_key,
        observation_type=classify_observation_type(observation_type),
        material_id=material_id,
        material_group=material_group,
        material_name=material_name,
        participant=participant,
        source_ref=source_ref,
        region=region,
        price_value=price_value,
        currency=currency,
        price_unit=price_unit,
        unit_info=unit_info,
        vat_included=vat_included,
        delivery_included=delivery_included,
        observed_at=observed_at,
        valid_from=valid_from,
        valid_to=valid_to,
        confidence=confidence,
        warnings=tuple(dict.fromkeys(warnings)),
        provenance_refs=provenance_refs,
    )


def _source_ref_from_price(supplier_price: Any, participant: MaterialParticipantRecord | None) -> ObservationSourceRef | None:
    catalog_product = _value(supplier_price, "catalog_product")
    source = _value(catalog_product, "source") or _value(supplier_price, "source")
    source_upload = _value(supplier_price, "source_upload")
    source_id = _as_string(_value(source, "id") or _value(supplier_price, "source_id", "sourceId"))
    source_name = _as_string(_value(source, "name", "display_name") or _value(source_upload, "filename", "file_name"))
    url = _as_string(_value(catalog_product, "external_url") or _value(source, "url"))
    if not any((source_id, source_name, url, participant)):
        return None
    participant_ref = None
    if participant:
        participant_ref = MappingProxyType(
            {
                "stableKey": participant.stable_key,
                "participantType": participant.participant_type,
                "displayName": participant.display_name,
            }
        )
    return ObservationSourceRef(
        source_id=source_id,
        source_code=_as_string(_value(source, "source_code", "sourceCode", "code")),
        source_name=source_name,
        source_type=_enum_value(_value(source, "source_type", "sourceType")),
        url=url,
        participant_ref=participant_ref,
        provenance=MappingProxyType({"source": "SupplierPrice"}),
    )


def _merge_observation(left: MaterialPriceObservation, right: MaterialPriceObservation) -> MaterialPriceObservation:
    warnings = tuple(dict.fromkeys(left.warnings + right.warnings + ("Duplicate price observation merged.",)))
    return MaterialPriceObservation(
        observation_id=left.observation_id or right.observation_id,
        stable_key=left.stable_key,
        observation_type=left.observation_type,
        material_id=left.material_id or right.material_id,
        material_group=left.material_group or right.material_group,
        material_name=left.material_name or right.material_name,
        participant=left.participant or right.participant,
        source_ref=left.source_ref or right.source_ref,
        region=left.region if (left.region.region or left.region.city) else right.region,
        price_value=left.price_value if left.price_value is not None else right.price_value,
        currency=left.currency or right.currency,
        price_unit=left.price_unit or right.price_unit,
        unit_info=left.unit_info if left.unit_info.is_supported else right.unit_info,
        vat_included=left.vat_included if left.vat_included is not None else right.vat_included,
        delivery_included=left.delivery_included if left.delivery_included is not None else right.delivery_included,
        observed_at=left.observed_at or right.observed_at,
        valid_from=left.valid_from or right.valid_from,
        valid_to=left.valid_to or right.valid_to,
        confidence=max(left.confidence, right.confidence),
        warnings=warnings,
        provenance_refs=_dedupe_mappings(left.provenance_refs + right.provenance_refs),
    )


def _price_warnings(price_value: Decimal | None, unit_info: ObservationUnitInfo) -> tuple[str, ...]:
    warnings = list(unit_info.warnings)
    if price_value is None:
        warnings.append("Price value is missing.")
    elif price_value <= 0:
        warnings.append("Price value must be positive.")
    elif price_value > Decimal("1000000000"):
        warnings.append("Price value is unusually high.")
    return tuple(warnings)


def _is_suspicious_price(value: Decimal | None) -> bool:
    return value is not None and (value <= 0 or value > Decimal("1000000000"))


def _duplicate_keys(observations: tuple[MaterialPriceObservation, ...]) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for observation in observations:
        counts[observation.stable_key] = counts.get(observation.stable_key, 0) + 1
    return tuple(key for key, count in counts.items() if count > 1)


def _participant_key(participant: MaterialParticipantRecord | None) -> str | None:
    return participant.stable_key if participant else None


def _stable_key(*parts: Any) -> str:
    return "|".join(_normalize_key(part) for part in parts if part not in (None, ""))


def _group_code(canonical_material_view: MaterialCanonicalView) -> str | None:
    group = canonical_material_view.group or {}
    category = canonical_material_view.category or {}
    return _as_string(group.get("code") or group.get("slug") or category.get("slug"))


def _dedupe_mappings(items: tuple[Mapping[str, Any], ...]) -> tuple[Mapping[str, Any], ...]:
    result = []
    seen = set()
    for item in items:
        key = tuple(sorted((str(k), str(v)) for k, v in item.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(MappingProxyType(dict(item)))
    return tuple(result)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _value(obj: Any, *names: str) -> Any:
    for name in names:
        if obj is None:
            return None
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        if not isinstance(obj, Mapping) and hasattr(obj, name):
            return getattr(obj, name)
    return None


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _as_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", ".").strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "included"}:
        return True
    if text in {"0", "false", "no", "n", "excluded"}:
        return False
    return None


def _date_string(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return value[:10] if len(value) >= 10 else value
    return None


def _normalize_key(value: Any) -> str:
    text = _as_string(value) or ""
    return "_".join(text.strip().lower().replace("-", "_").split())
