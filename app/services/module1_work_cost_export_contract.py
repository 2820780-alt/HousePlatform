
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.services.module1_provider_work_cost_offers import (
    SUPPORTED_CURRENCIES,
    list_provider_work_cost_offers,
    pricing_unit_label,
)
from app.services.module1_work_catalog import get_work_item

WORK_COST_EXPORT_SCHEMA_VERSION = "module1.work_cost_offer_export.v1"
WORK_COST_EXPORT_SOURCE_MODULE = "MODULE_01_MATERIAL_HUB"
WORK_COST_EXPORT_CONSUMER = "MODULE_05_ESTIMATES_PREVIEW"
WORK_COST_EXPORT_RECORD_CONTRACT_VERSION = "provider_work_cost_offer.v1"

EXCLUSION_REASONS = {
    "draft": "\u0427\u0435\u0440\u043d\u043e\u0432\u0438\u043a",
    "inactive": "\u041d\u0435\u0430\u043a\u0442\u0438\u0432\u043d\u043e",
    "expired": "\u0421\u0440\u043e\u043a \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u0438\u0441\u0442\u0451\u043a",
    "missing_work": "\u0420\u0430\u0431\u043e\u0442\u0430 \u0431\u043e\u043b\u044c\u0448\u0435 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430",
    "invalid_pricing_mode": "\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u0442\u0438\u043f \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u0438",
    "invalid_fixed": "\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u0430\u044f \u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u0430\u044f \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c",
    "invalid_range": "\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u0434\u0438\u0430\u043f\u0430\u0437\u043e\u043d",
    "missing_currency": "\u041d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d\u0430 \u0432\u0430\u043b\u044e\u0442\u0430",
    "invalid_currency": "\u041d\u0435\u043f\u043e\u0434\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0435\u043c\u0430\u044f \u0432\u0430\u043b\u044e\u0442\u0430",
    "missing_pricing_unit": "\u041d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d\u0430 \u0435\u0434\u0438\u043d\u0438\u0446\u0430 \u0440\u0430\u0441\u0447\u0451\u0442\u0430",
    "invalid_pricing_unit": "\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u0430\u044f \u0435\u0434\u0438\u043d\u0438\u0446\u0430 \u0440\u0430\u0441\u0447\u0451\u0442\u0430",
    "missing_owner": "\u041d\u0435 \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u0451\u043d \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c",
}

OVERLAP_WARNING = "\u0415\u0441\u0442\u044c \u043f\u0435\u0440\u0435\u0441\u0435\u043a\u0430\u044e\u0449\u0435\u0435\u0441\u044f \u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0435 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u044d\u0442\u043e\u0433\u043e \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044f"


@dataclass(frozen=True)
class WorkCostOfferEligibilityReport:
    offer_id: str | None
    is_eligible: bool
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    no_side_effects: bool = True


@dataclass(frozen=True)
class WorkCostOfferExportRecordV1:
    offer_id: str
    work_code: str
    work_title: str
    work_group_code: str
    work_group_title: str
    provider_reference: str
    provider_display_name: str
    region_reference: str
    region_display_name: str
    pricing_mode: str
    fixed_amount: str | None
    minimum_amount: str | None
    maximum_amount: str | None
    currency: str
    pricing_unit: str
    pricing_unit_label: str
    valid_from: str | None
    valid_until: str | None
    updated_at: str | None
    quality_warnings: tuple[str, ...]
    source_contract_version: str = WORK_COST_EXPORT_RECORD_CONTRACT_VERSION
    no_side_effects: bool = True


@dataclass(frozen=True)
class WorkCostOfferExportPackageV1:
    schema_version: str
    source_module: str
    consumer: str
    generated_at: datetime
    record_count: int
    records: tuple[WorkCostOfferExportRecordV1, ...]
    warnings: tuple[str, ...]
    filters: Mapping[str, Any]
    scope: Mapping[str, Any]
    exclusion_counts: Mapping[str, int]
    excluded_count: int
    total_scanned: int
    limit: int
    offset: int
    no_module5_write: bool = True
    no_estimate_total: bool = True
    no_selected_offer: bool = True
    no_side_effects: bool = True


async def build_work_cost_offer_export_package(
    db: AsyncSession,
    user: Any,
    *,
    work_code: str | None = None,
    region: str | None = None,
    provider_user_id: UUID | None = None,
    currency: str | None = None,
    pricing_unit: str | None = None,
    updated_since: datetime | None = None,
    offset: int = 0,
    limit: int = 100,
    generated_at: datetime | None = None,
) -> WorkCostOfferExportPackageV1:
    normalized_limit = min(max(limit, 1), 200)
    result = await list_provider_work_cost_offers(
        db,
        user,
        work_code=work_code,
        owner_user_id=provider_user_id,
        region=region,
        currency=currency,
        pricing_unit=pricing_unit,
        updated_since=updated_since,
        offset=offset,
        limit=normalized_limit,
    )
    filters = {
        "work_code": work_code,
        "region": region,
        "provider_user_id": str(provider_user_id) if provider_user_id else None,
        "currency": currency,
        "pricing_unit": pricing_unit,
        "updated_since": updated_since,
    }
    from app.services.module1_work_catalog_store import load_work_catalog
    work_by_code = {item.work_code: item for item in await load_work_catalog(db)}
    return build_work_cost_offer_export_package_from_offers(
        result.items,
        generated_at=generated_at,
        filters=filters,
        scope={"current_user_id": str(_get_value(user, "id") or ""), "record_source": "provider_work_cost_offers"},
        offset=result.offset,
        limit=result.limit,
        total_scanned=result.total,
        work_by_code=work_by_code,
    )


def build_work_cost_offer_export_package_from_offers(
    offers: Iterable[ProviderWorkCostOffer],
    *,
    generated_at: datetime | None = None,
    filters: Mapping[str, Any] | None = None,
    scope: Mapping[str, Any] | None = None,
    offset: int = 0,
    limit: int = 100,
    total_scanned: int | None = None,
    work_by_code: Mapping[str, Any] | None = None,
) -> WorkCostOfferExportPackageV1:
    offer_list = tuple(offers)
    eligibility = tuple(work_cost_offer_eligibility(offer, work_by_code=work_by_code) for offer in offer_list)
    eligible_offers = tuple(offer for offer, report in zip(offer_list, eligibility) if report.is_eligible)
    duplicate_warnings = _duplicate_warning_map(eligible_offers)
    records = tuple(_record_from_offer(offer, duplicate_warnings.get(str(offer.id), tuple()), work_by_code=work_by_code) for offer in eligible_offers)
    records = tuple(sorted(records, key=_record_sort_key))
    exclusion_counts: dict[str, int] = {}
    for report in eligibility:
        for reason in report.reasons:
            exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
    warnings = _unique(warning for item in duplicate_warnings.values() for warning in item)
    generated = generated_at or datetime.now(UTC).replace(microsecond=0)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=UTC)
    return WorkCostOfferExportPackageV1(
        schema_version=WORK_COST_EXPORT_SCHEMA_VERSION,
        source_module=WORK_COST_EXPORT_SOURCE_MODULE,
        consumer=WORK_COST_EXPORT_CONSUMER,
        generated_at=generated,
        record_count=len(records),
        records=records,
        warnings=warnings,
        filters=_jsonable({key: value for key, value in (filters or {}).items() if value not in (None, "")}),
        scope=_jsonable(scope or {}),
        exclusion_counts=exclusion_counts,
        excluded_count=sum(exclusion_counts.values()),
        total_scanned=len(offer_list) if total_scanned is None else total_scanned,
        limit=limit,
        offset=offset,
    )


def work_cost_offer_eligibility(offer: ProviderWorkCostOffer, *, work_by_code: Mapping[str, Any] | None = None) -> WorkCostOfferEligibilityReport:
    reason_codes: list[str] = []
    status = (getattr(offer, "status", None) or "").lower()
    if status == "draft":
        reason_codes.append("draft")
    elif status == "inactive":
        reason_codes.append("inactive")
    elif status != "active":
        reason_codes.append("inactive")
    valid_until = getattr(offer, "valid_until", None)
    if valid_until is not None and valid_until < date.today():
        reason_codes.append("expired")
    code = getattr(offer, "work_code", "")
    work_item = work_by_code.get(code) if work_by_code is not None else get_work_item(code)
    if work_item is None:
        reason_codes.append("missing_work")
    pricing_mode = (getattr(offer, "pricing_mode", None) or "").lower()
    if pricing_mode not in {"fixed", "range"}:
        reason_codes.append("invalid_pricing_mode")
    elif pricing_mode == "fixed":
        if not _positive_decimal(getattr(offer, "fixed_amount", None)) or getattr(offer, "minimum_amount", None) is not None or getattr(offer, "maximum_amount", None) is not None:
            reason_codes.append("invalid_fixed")
    elif pricing_mode == "range":
        minimum = _decimal_or_none(getattr(offer, "minimum_amount", None))
        maximum = _decimal_or_none(getattr(offer, "maximum_amount", None))
        if minimum is None or maximum is None or minimum <= 0 or maximum <= 0 or minimum > maximum or getattr(offer, "fixed_amount", None) is not None:
            reason_codes.append("invalid_range")
    currency = getattr(offer, "currency", None)
    if not currency:
        reason_codes.append("missing_currency")
    elif str(currency).upper() not in SUPPORTED_CURRENCIES:
        reason_codes.append("invalid_currency")
    pricing_unit = getattr(offer, "pricing_unit", None)
    if not pricing_unit:
        reason_codes.append("missing_pricing_unit")
    elif work_item is not None and pricing_unit not in work_item.allowed_units:
        reason_codes.append("invalid_pricing_unit")
    if not getattr(offer, "owner_user_id", None):
        reason_codes.append("missing_owner")
    reason_codes = list(dict.fromkeys(reason_codes))
    return WorkCostOfferEligibilityReport(
        offer_id=str(getattr(offer, "id", "")) if getattr(offer, "id", None) else None,
        is_eligible=not reason_codes,
        reason_codes=tuple(reason_codes),
        reasons=tuple(EXCLUSION_REASONS[code] for code in reason_codes),
    )


def work_cost_export_package_to_dict(package: WorkCostOfferExportPackageV1) -> dict[str, Any]:
    return _jsonable(package)


def _record_from_offer(offer: ProviderWorkCostOffer, quality_warnings: tuple[str, ...], *, work_by_code: Mapping[str, Any] | None = None) -> WorkCostOfferExportRecordV1:
    work_item = work_by_code.get(offer.work_code) if work_by_code is not None else get_work_item(offer.work_code)
    return WorkCostOfferExportRecordV1(
        offer_id=str(offer.id),
        work_code=offer.work_code,
        work_title=work_item.work_name if work_item else "",
        work_group_code=work_item.work_group if work_item else "",
        work_group_title=work_item.work_category if work_item else "",
        provider_reference=f"user:{offer.owner_user_id}",
        provider_display_name=_provider_display_name(offer),
        region_reference=offer.region,
        region_display_name=offer.region,
        pricing_mode=offer.pricing_mode,
        fixed_amount=_decimal_string(offer.fixed_amount),
        minimum_amount=_decimal_string(offer.minimum_amount),
        maximum_amount=_decimal_string(offer.maximum_amount),
        currency=offer.currency,
        pricing_unit=offer.pricing_unit,
        pricing_unit_label=pricing_unit_label(offer.pricing_unit),
        valid_from=_date_string(offer.valid_from),
        valid_until=_date_string(offer.valid_until),
        updated_at=_datetime_string(offer.updated_at),
        quality_warnings=quality_warnings,
    )


def _duplicate_warning_map(offers: tuple[ProviderWorkCostOffer, ...]) -> dict[str, tuple[str, ...]]:
    warnings: dict[str, list[str]] = {}
    for index, left in enumerate(offers):
        for right in offers[index + 1:]:
            if _duplicate_key(left) != _duplicate_key(right):
                continue
            if _periods_overlap(left, right):
                warnings.setdefault(str(left.id), []).append(OVERLAP_WARNING)
                warnings.setdefault(str(right.id), []).append(OVERLAP_WARNING)
    return {offer_id: _unique(items) for offer_id, items in warnings.items()}


def _duplicate_key(offer: ProviderWorkCostOffer) -> tuple[Any, ...]:
    return (str(offer.owner_user_id), offer.work_code, offer.region, offer.pricing_unit, offer.currency)


def _periods_overlap(left: ProviderWorkCostOffer, right: ProviderWorkCostOffer) -> bool:
    left_start = left.valid_from or date.min
    left_end = left.valid_until or date.max
    right_start = right.valid_from or date.min
    right_end = right.valid_until or date.max
    return left_start <= right_end and right_start <= left_end


def _record_sort_key(record: WorkCostOfferExportRecordV1) -> tuple[str, ...]:
    return (
        record.work_group_title,
        record.work_title or record.work_code,
        record.region_display_name,
        record.provider_display_name,
        record.updated_at or "",
        record.offer_id,
    )


def _provider_display_name(offer: ProviderWorkCostOffer) -> str:
    owner = getattr(offer, "owner", None)
    if owner is not None:
        name = _optional_str(getattr(owner, "name", None))
        if name:
            return name
        email = _optional_str(getattr(owner, "email", None))
        if email:
            return email
    return "\u0418\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c"


def _positive_decimal(value: Any) -> bool:
    amount = _decimal_or_none(value)
    return amount is not None and amount > 0


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _decimal_string(value: Any) -> str | None:
    amount = _decimal_or_none(value)
    if amount is None:
        return None
    return format(amount, "f")


def _date_string(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _datetime_string(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _get_value(source: Any, field_name: str) -> Any:
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Decimal):
        return _decimal_string(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_jsonable(item) for item in value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _unique(values: Iterable[Any]) -> tuple[Any, ...]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)
