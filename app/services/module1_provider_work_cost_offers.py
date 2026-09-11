from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.permission_guard import can
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.services.module1_work_catalog import get_work_item, list_work_items


MODULE_01_MATERIAL_HUB = "MODULE_01_MATERIAL_HUB"
MODULE_04_WORKS_COSTS = "MODULE_04_WORKS_COSTS"

PRICING_MODES = frozenset({"fixed", "range"})
STATUSES = frozenset({"draft", "active", "inactive"})
SUPPORTED_CURRENCIES = frozenset({"RUB"})
MIN_COMPARABLE_OFFERS = 5
MARKET_SANITY_IQR_MULTIPLIER = Decimal("1.5")


@dataclass(frozen=True)
class ProviderWorkCostOfferPayload:
    work_code: str
    region: str
    pricing_mode: str
    pricing_unit: str
    currency: str = "RUB"
    fixed_amount: Decimal | str | int | float | None = None
    minimum_amount: Decimal | str | int | float | None = None
    maximum_amount: Decimal | str | int | float | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    status: str = "draft"
    comment: str | None = None


@dataclass(frozen=True)
class ProviderWorkCostOfferListResult:
    items: tuple[ProviderWorkCostOffer, ...]
    total: int
    offset: int
    limit: int


class ProviderWorkCostMarketSanityStatus(str, Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    WITHIN_COMPARABLE_RANGE = "WITHIN_COMPARABLE_RANGE"
    LOW_OUTLIER = "LOW_OUTLIER"
    HIGH_OUTLIER = "HIGH_OUTLIER"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class ProviderWorkCostMarketReferenceStats:
    median: Decimal
    q1: Decimal
    q3: Decimal
    lower_bound: Decimal
    upper_bound: Decimal


@dataclass(frozen=True)
class ProviderWorkCostMarketSanity:
    status: ProviderWorkCostMarketSanityStatus
    comparable_offer_count: int
    reason: str
    explanation: str
    as_of: date
    reference_stats: ProviderWorkCostMarketReferenceStats | None = None


async def create_provider_work_cost_offer(
    db: AsyncSession,
    payload: ProviderWorkCostOfferPayload,
    user: Any,
) -> ProviderWorkCostOffer:
    owner_user_id = _require_create_permission(user)
    normalized = validate_provider_work_cost_payload(payload)
    offer = ProviderWorkCostOffer(
        work_code=normalized.work_code,
        owner_user_id=owner_user_id,
        region=normalized.region,
        pricing_mode=normalized.pricing_mode,
        fixed_amount=_decimal_or_none(normalized.fixed_amount),
        minimum_amount=_decimal_or_none(normalized.minimum_amount),
        maximum_amount=_decimal_or_none(normalized.maximum_amount),
        currency=normalized.currency,
        pricing_unit=normalized.pricing_unit,
        valid_from=normalized.valid_from,
        valid_until=normalized.valid_until,
        status=normalized.status,
        comment=normalized.comment,
        created_by=owner_user_id,
        updated_by=owner_user_id,
    )
    db.add(offer)
    await db.flush()
    await db.refresh(offer)
    return offer


async def get_provider_work_cost_offer(
    db: AsyncSession,
    offer_id: UUID,
    user: Any,
) -> ProviderWorkCostOffer:
    offer = await _get_offer_or_404(db, offer_id)
    _require_read_permission(user, offer)
    return offer


async def list_provider_work_cost_offers(
    db: AsyncSession,
    user: Any,
    *,
    work_code: str | None = None,
    owner_user_id: UUID | None = None,
    region: str | None = None,
    status: str | None = None,
    pricing_mode: str | None = None,
    currency: str | None = None,
    pricing_unit: str | None = None,
    updated_since: datetime | None = None,
    offset: int = 0,
    limit: int = 50,
) -> ProviderWorkCostOfferListResult:
    query = select(ProviderWorkCostOffer).options(selectinload(ProviderWorkCostOffer.owner))
    query = _apply_list_permissions(query, user, owner_user_id=owner_user_id)
    query = _apply_filters(
        query,
        work_code=work_code,
        region=region,
        status=status,
        pricing_mode=pricing_mode,
        currency=currency,
        pricing_unit=pricing_unit,
        updated_since=updated_since,
    )

    total_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(total_query)
    total = int(total_result.scalar() or 0)

    result = await db.execute(
        query.order_by(ProviderWorkCostOffer.updated_at.desc()).offset(offset).limit(limit)
    )
    return ProviderWorkCostOfferListResult(
        items=tuple(result.scalars().all()),
        total=total,
        offset=offset,
        limit=limit,
    )


def evaluate_provider_work_cost_market_sanity(
    target: ProviderWorkCostOffer,
    offers: Iterable[ProviderWorkCostOffer],
    *,
    as_of: date | datetime | None = None,
) -> ProviderWorkCostMarketSanity:
    as_of_date = _market_as_of_date(as_of)
    cohort_key = _market_cohort_key(target)
    if cohort_key is None:
        return _market_sanity_result(
            ProviderWorkCostMarketSanityStatus.REVIEW,
            0,
            "invalid_target_cohort",
            "Нельзя определить точную сопоставимую группу предложения.",
            as_of_date,
        )

    cohort_offers = tuple(
        offer
        for offer in offers
        if _market_cohort_key(offer) == cohort_key and _is_market_offer_effective(offer, as_of_date)
    )
    return _evaluate_market_sanity_for_cohort(target, cohort_offers, as_of_date)


def evaluate_provider_work_cost_market_sanity_batch(
    targets: Iterable[ProviderWorkCostOffer],
    offers: Iterable[ProviderWorkCostOffer],
    *,
    as_of: date | datetime | None = None,
) -> dict[str, ProviderWorkCostMarketSanity]:
    as_of_date = _market_as_of_date(as_of)
    target_items = tuple(targets)
    cohorts: dict[tuple[str, str, str, str], list[ProviderWorkCostOffer]] = {}

    for offer in offers:
        cohort_key = _market_cohort_key(offer)
        if cohort_key is None or not _is_market_offer_effective(offer, as_of_date):
            continue
        cohorts.setdefault(cohort_key, []).append(offer)

    return {
        _market_offer_result_key(target): (
            _evaluate_market_sanity_for_cohort(target, cohorts.get(cohort_key, ()), as_of_date)
            if (cohort_key := _market_cohort_key(target)) is not None
            else _market_sanity_result(
                ProviderWorkCostMarketSanityStatus.REVIEW,
                0,
                "invalid_target_cohort",
                "Нельзя определить точную сопоставимую группу предложения.",
                as_of_date,
            )
        )
        for target in target_items
    }


async def build_provider_work_cost_market_sanity_map(
    db: AsyncSession,
    targets: Iterable[ProviderWorkCostOffer],
    *,
    as_of: date | datetime | None = None,
) -> dict[str, ProviderWorkCostMarketSanity]:
    target_items = tuple(targets)
    as_of_date = _market_as_of_date(as_of)
    cohort_keys = {
        cohort_key
        for target in target_items
        if (cohort_key := _market_cohort_key(target)) is not None
    }

    peer_offers: Sequence[ProviderWorkCostOffer] = ()
    if cohort_keys:
        cohort_clauses = tuple(
            and_(
                ProviderWorkCostOffer.work_code == work_code,
                ProviderWorkCostOffer.pricing_unit == pricing_unit,
                ProviderWorkCostOffer.currency == currency,
                ProviderWorkCostOffer.region == region,
            )
            for work_code, pricing_unit, currency, region in cohort_keys
        )
        result = await db.execute(
            select(ProviderWorkCostOffer).where(
                ProviderWorkCostOffer.status == "active",
                or_(ProviderWorkCostOffer.valid_from.is_(None), ProviderWorkCostOffer.valid_from <= as_of_date),
                or_(ProviderWorkCostOffer.valid_until.is_(None), ProviderWorkCostOffer.valid_until >= as_of_date),
                or_(*cohort_clauses),
            )
        )
        peer_offers = tuple(result.scalars().all())

    return evaluate_provider_work_cost_market_sanity_batch(
        target_items,
        peer_offers,
        as_of=as_of_date,
    )


def provider_work_cost_market_sanity_to_dict(
    signal: ProviderWorkCostMarketSanity,
) -> dict[str, Any]:
    reference_stats = signal.reference_stats
    return {
        "status": signal.status.value,
        "statusLabel": _market_sanity_status_label(signal.status),
        "comparableOfferCount": signal.comparable_offer_count,
        "reason": signal.reason,
        "explanation": signal.explanation,
        "asOf": signal.as_of,
        "referenceStats": (
            {
                "median": reference_stats.median,
                "q1": reference_stats.q1,
                "q3": reference_stats.q3,
                "lowerBound": reference_stats.lower_bound,
                "upperBound": reference_stats.upper_bound,
            }
            if reference_stats is not None
            else None
        ),
    }


def _evaluate_market_sanity_for_cohort(
    target: ProviderWorkCostOffer,
    cohort_offers: Sequence[ProviderWorkCostOffer],
    as_of: date,
) -> ProviderWorkCostMarketSanity:
    representatives = _market_peer_representatives(target, cohort_offers)
    comparable_count = len(representatives)
    if comparable_count < MIN_COMPARABLE_OFFERS:
        return _market_sanity_result(
            ProviderWorkCostMarketSanityStatus.INSUFFICIENT_DATA,
            comparable_count,
            "minimum_comparable_offers_not_met",
            (
                f"Нужно не менее {MIN_COMPARABLE_OFFERS} актуальных предложений "
                f"других исполнителей; найдено: {comparable_count}."
            ),
            as_of,
        )

    stats = _market_reference_stats(representatives)
    target_interval = _market_amount_interval(target)
    if target_interval is None:
        return _market_sanity_result(
            ProviderWorkCostMarketSanityStatus.REVIEW,
            comparable_count,
            "invalid_target_amount",
            "Сумма или диапазон предложения не соответствует контракту стоимости работ.",
            as_of,
            stats,
        )

    target_minimum, target_maximum = target_interval
    if stats.q1 == stats.q3:
        if target_minimum <= stats.median <= target_maximum:
            return _market_sanity_result(
                ProviderWorkCostMarketSanityStatus.WITHIN_COMPARABLE_RANGE,
                comparable_count,
                "target_overlaps_zero_iqr_reference",
                "Предложение включает единственное устойчивое значение сопоставимой группы.",
                as_of,
                stats,
            )
        return _market_sanity_result(
            ProviderWorkCostMarketSanityStatus.REVIEW,
            comparable_count,
            "zero_iqr_requires_review",
            "У сопоставимых предложений нулевой межквартильный размах; отклонение нельзя надежно классифицировать.",
            as_of,
            stats,
        )

    if target_maximum < stats.lower_bound:
        return _market_sanity_result(
            ProviderWorkCostMarketSanityStatus.LOW_OUTLIER,
            comparable_count,
            "target_fully_below_lower_bound",
            "Предложение полностью ниже устойчивого диапазона сопоставимой группы.",
            as_of,
            stats,
        )
    if target_minimum > stats.upper_bound:
        return _market_sanity_result(
            ProviderWorkCostMarketSanityStatus.HIGH_OUTLIER,
            comparable_count,
            "target_fully_above_upper_bound",
            "Предложение полностью выше устойчивого диапазона сопоставимой группы.",
            as_of,
            stats,
        )
    return _market_sanity_result(
        ProviderWorkCostMarketSanityStatus.WITHIN_COMPARABLE_RANGE,
        comparable_count,
        "target_overlaps_comparable_range",
        "Предложение пересекает устойчивый диапазон сопоставимой группы.",
        as_of,
        stats,
    )


def _market_peer_representatives(
    target: ProviderWorkCostOffer,
    cohort_offers: Sequence[ProviderWorkCostOffer],
) -> tuple[Decimal, ...]:
    latest_by_owner: dict[str, ProviderWorkCostOffer] = {}
    target_owner = _market_owner_key(target)

    for offer in cohort_offers:
        if _is_same_market_offer(target, offer):
            continue
        owner_key = _market_owner_key(offer)
        if owner_key is None or owner_key == target_owner:
            continue
        current = latest_by_owner.get(owner_key)
        if current is None or _market_offer_recency_key(offer) > _market_offer_recency_key(current):
            latest_by_owner[owner_key] = offer

    representatives: list[Decimal] = []
    for offer in latest_by_owner.values():
        interval = _market_amount_interval(offer)
        if interval is None:
            continue
        minimum, maximum = interval
        representatives.append((minimum + maximum) / Decimal("2"))
    return tuple(representatives)


def _market_reference_stats(values: Sequence[Decimal]) -> ProviderWorkCostMarketReferenceStats:
    ordered = tuple(sorted(values))
    midpoint = len(ordered) // 2
    lower_half = ordered[:midpoint]
    upper_half = ordered[midpoint + 1 :] if len(ordered) % 2 else ordered[midpoint:]
    median = _market_median(ordered)
    q1 = _market_median(lower_half)
    q3 = _market_median(upper_half)
    iqr = q3 - q1
    return ProviderWorkCostMarketReferenceStats(
        median=median,
        q1=q1,
        q3=q3,
        lower_bound=q1 - MARKET_SANITY_IQR_MULTIPLIER * iqr,
        upper_bound=q3 + MARKET_SANITY_IQR_MULTIPLIER * iqr,
    )


def _market_median(values: Sequence[Decimal]) -> Decimal:
    midpoint = len(values) // 2
    if len(values) % 2:
        return values[midpoint]
    return (values[midpoint - 1] + values[midpoint]) / Decimal("2")


def _market_amount_interval(offer: ProviderWorkCostOffer) -> tuple[Decimal, Decimal] | None:
    pricing_mode = _get_value(offer, "pricing_mode")
    if pricing_mode == "fixed":
        fixed_amount = _market_decimal(_get_value(offer, "fixed_amount"))
        if fixed_amount is None or fixed_amount <= 0:
            return None
        return fixed_amount, fixed_amount
    if pricing_mode == "range":
        minimum_amount = _market_decimal(_get_value(offer, "minimum_amount"))
        maximum_amount = _market_decimal(_get_value(offer, "maximum_amount"))
        if (
            minimum_amount is None
            or maximum_amount is None
            or minimum_amount <= 0
            or maximum_amount <= 0
            or minimum_amount > maximum_amount
        ):
            return None
        return minimum_amount, maximum_amount
    return None


def _market_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() else None


def _market_cohort_key(offer: ProviderWorkCostOffer) -> tuple[str, str, str, str] | None:
    values = (
        _get_value(offer, "work_code"),
        _get_value(offer, "pricing_unit"),
        _get_value(offer, "currency"),
        _get_value(offer, "region"),
    )
    if not all(isinstance(value, str) and value for value in values):
        return None
    return values


def _is_market_offer_effective(offer: ProviderWorkCostOffer, as_of: date) -> bool:
    if _get_value(offer, "status") != "active":
        return False
    valid_from = _get_value(offer, "valid_from")
    valid_until = _get_value(offer, "valid_until")
    if valid_from is not None and valid_from > as_of:
        return False
    if valid_until is not None and valid_until < as_of:
        return False
    return True


def _is_same_market_offer(target: ProviderWorkCostOffer, offer: ProviderWorkCostOffer) -> bool:
    if target is offer:
        return True
    target_id = _get_value(target, "id")
    offer_id = _get_value(offer, "id")
    return target_id is not None and offer_id is not None and str(target_id) == str(offer_id)


def _market_owner_key(offer: ProviderWorkCostOffer) -> str | None:
    owner_user_id = _get_value(offer, "owner_user_id")
    return str(owner_user_id) if owner_user_id is not None else None


def _market_offer_result_key(offer: ProviderWorkCostOffer) -> str:
    offer_id = _get_value(offer, "id")
    return str(offer_id) if offer_id is not None else f"object:{id(offer)}"


def _market_offer_recency_key(offer: ProviderWorkCostOffer) -> tuple[datetime, datetime, date, str]:
    return (
        _market_sortable_datetime(_get_value(offer, "updated_at")),
        _market_sortable_datetime(_get_value(offer, "created_at")),
        _get_value(offer, "valid_from") or date.min,
        str(_get_value(offer, "id") or ""),
    )


def _market_sortable_datetime(value: Any) -> datetime:
    if not isinstance(value, datetime):
        return datetime.min
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _market_as_of_date(value: date | datetime | None) -> date:
    if value is None:
        return date.today()
    return value.date() if isinstance(value, datetime) else value


def _market_sanity_status_label(status: ProviderWorkCostMarketSanityStatus) -> str:
    return {
        ProviderWorkCostMarketSanityStatus.INSUFFICIENT_DATA: "Недостаточно данных",
        ProviderWorkCostMarketSanityStatus.WITHIN_COMPARABLE_RANGE: "В сопоставимом диапазоне",
        ProviderWorkCostMarketSanityStatus.LOW_OUTLIER: "Ниже сопоставимого диапазона",
        ProviderWorkCostMarketSanityStatus.HIGH_OUTLIER: "Выше сопоставимого диапазона",
        ProviderWorkCostMarketSanityStatus.REVIEW: "Требует проверки",
    }[status]


def _market_sanity_result(
    status: ProviderWorkCostMarketSanityStatus,
    comparable_offer_count: int,
    reason: str,
    explanation: str,
    as_of: date,
    reference_stats: ProviderWorkCostMarketReferenceStats | None = None,
) -> ProviderWorkCostMarketSanity:
    return ProviderWorkCostMarketSanity(
        status=status,
        comparable_offer_count=comparable_offer_count,
        reason=reason,
        explanation=explanation,
        as_of=as_of,
        reference_stats=reference_stats,
    )

async def update_provider_work_cost_offer(
    db: AsyncSession,
    offer_id: UUID,
    payload: ProviderWorkCostOfferPayload,
    user: Any,
) -> ProviderWorkCostOffer:
    offer = await _get_offer_or_404(db, offer_id)
    _require_update_permission(user, offer)
    normalized = validate_provider_work_cost_payload(payload)

    offer.work_code = normalized.work_code
    offer.region = normalized.region
    offer.pricing_mode = normalized.pricing_mode
    offer.fixed_amount = _decimal_or_none(normalized.fixed_amount)
    offer.minimum_amount = _decimal_or_none(normalized.minimum_amount)
    offer.maximum_amount = _decimal_or_none(normalized.maximum_amount)
    offer.currency = normalized.currency
    offer.pricing_unit = normalized.pricing_unit
    offer.valid_from = normalized.valid_from
    offer.valid_until = normalized.valid_until
    offer.status = normalized.status
    offer.comment = normalized.comment
    offer.updated_by = _user_id(user)
    db.add(offer)
    await db.flush()
    await db.refresh(offer)
    return offer


async def deactivate_provider_work_cost_offer(
    db: AsyncSession,
    offer_id: UUID,
    user: Any,
) -> ProviderWorkCostOffer:
    offer = await _get_offer_or_404(db, offer_id)
    _require_update_permission(user, offer)
    offer.status = "inactive"
    offer.updated_by = _user_id(user)
    db.add(offer)
    await db.flush()
    await db.refresh(offer)
    return offer


def validate_provider_work_cost_payload(payload: ProviderWorkCostOfferPayload) -> ProviderWorkCostOfferPayload:
    work_code = _required_str(payload.work_code, "work_code")
    work_item = get_work_item(work_code)
    if work_item is None:
        raise ValidationError("work_code must reference an existing Work Catalog item")

    region = _required_str(payload.region, "region")
    pricing_mode = _required_str(payload.pricing_mode, "pricing_mode").lower()
    if pricing_mode not in PRICING_MODES:
        raise ValidationError("pricing_mode must be fixed or range")

    currency = _required_str(payload.currency, "currency").upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise ValidationError("currency is not supported for provider work cost offers")

    pricing_unit = _required_str(payload.pricing_unit, "pricing_unit")
    if pricing_unit not in work_item.allowed_units:
        raise ValidationError("pricing_unit must be allowed by the Work Catalog item")

    fixed_amount = _decimal_or_none(payload.fixed_amount)
    minimum_amount = _decimal_or_none(payload.minimum_amount)
    maximum_amount = _decimal_or_none(payload.maximum_amount)
    if pricing_mode == "fixed":
        if fixed_amount is None or fixed_amount <= 0:
            raise ValidationError("fixed_amount must be positive for fixed pricing")
        if minimum_amount is not None or maximum_amount is not None:
            raise ValidationError("minimum_amount and maximum_amount must be empty for fixed pricing")
    else:
        if not work_item.is_range_allowed:
            raise ValidationError("range pricing is not allowed for this work_code")
        if minimum_amount is None or maximum_amount is None:
            raise ValidationError("minimum_amount and maximum_amount are required for range pricing")
        if minimum_amount <= 0 or maximum_amount <= 0:
            raise ValidationError("range amounts must be positive")
        if minimum_amount > maximum_amount:
            raise ValidationError("minimum_amount must be less than or equal to maximum_amount")
        if fixed_amount is not None:
            raise ValidationError("fixed_amount must be empty for range pricing")

    if payload.valid_from and payload.valid_until and payload.valid_until < payload.valid_from:
        raise ValidationError("valid_until must be greater than or equal to valid_from")

    status = _required_str(payload.status, "status").lower()
    if status not in STATUSES:
        raise ValidationError("status must be draft, active or inactive")

    return ProviderWorkCostOfferPayload(
        work_code=work_code,
        region=region,
        pricing_mode=pricing_mode,
        pricing_unit=pricing_unit,
        currency=currency,
        fixed_amount=fixed_amount,
        minimum_amount=minimum_amount,
        maximum_amount=maximum_amount,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        status=status,
        comment=_optional_str(payload.comment),
    )


def list_work_catalog_options() -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "workCode": item.work_code,
            "workTitle": item.work_name,
            "workGroup": item.work_group,
            "workGroupTitle": item.work_category,
            "defaultUnit": item.default_unit,
            "allowedUnits": tuple(
                {"code": unit, "label": pricing_unit_label(unit)}
                for unit in item.allowed_units
            ),
            "isRangeAllowed": item.is_range_allowed,
        }
        for item in list_work_items()
    )


def provider_work_cost_offer_to_dict(
    offer: ProviderWorkCostOffer,
    user: Any | None = None,
    market_sanity: ProviderWorkCostMarketSanity | None = None,
) -> dict[str, Any]:
    work_item = get_work_item(offer.work_code)
    can_edit = _can_edit_offer(user, offer)
    return {
        "id": str(offer.id),
        "workCode": offer.work_code,
        "workName": work_item.work_name if work_item else None,
        "workGroup": work_item.work_group if work_item else None,
        "workTitle": work_item.work_name if work_item else "Работа требует проверки",
        "workGroupTitle": work_item.work_category if work_item else "Раздел требует проверки",
        "ownerUserId": str(offer.owner_user_id),
        "ownerDisplayName": _owner_display_name(offer, user),
        "region": offer.region,
        "regionDisplayName": offer.region,
        "pricingMode": offer.pricing_mode,
        "pricingModeLabel": pricing_mode_label(offer.pricing_mode),
        "fixedAmount": offer.fixed_amount,
        "minimumAmount": offer.minimum_amount,
        "maximumAmount": offer.maximum_amount,
        "currency": offer.currency,
        "pricingUnit": offer.pricing_unit,
        "pricingUnitLabel": pricing_unit_label(offer.pricing_unit),
        "priceLabel": price_label(offer),
        "validFrom": offer.valid_from,
        "validUntil": offer.valid_until,
        "validityLabel": validity_label(offer),
        "status": offer.status,
        "statusLabel": status_label(offer),
        "qualityFlags": quality_flags(offer),
        "marketSanity": (
            provider_work_cost_market_sanity_to_dict(market_sanity)
            if market_sanity is not None
            else None
        ),
        "canEdit": can_edit,
        "canActivate": can_edit and offer.status != "active",
        "canDeactivate": can_edit and offer.status != "inactive",
        "comment": offer.comment,
        "createdAt": offer.created_at,
        "updatedAt": offer.updated_at,
    }


def pricing_mode_label(value: str | None) -> str:
    return {
        "fixed": "Фиксированная",
        "range": "Диапазон",
    }.get((value or "").lower(), "Требует проверки")


def pricing_unit_label(value: str | None) -> str:
    labels = {
        "work": "за работу",
        "object": "за объект",
        "m2": "за м²",
        "m3": "за м³",
        "linear_meter": "за пог. м",
        "lm": "за пог. м",
        "point": "за точку",
        "visit": "за выезд",
        "piece": "за шт.",
        "hour": "за час",
        "day": "за день",
        "kg": "за кг",
        "ton": "за т",
        "set": "за комплект",
    }
    if not value:
        return "единица не указана"
    return labels.get(value, f"за {value}")


def price_label(offer: ProviderWorkCostOffer) -> str:
    if offer.pricing_mode == "fixed":
        return f"{_format_money(offer.fixed_amount)} ₽"
    if offer.pricing_mode == "range":
        return f"от {_format_money(offer.minimum_amount)} до {_format_money(offer.maximum_amount)} ₽"
    return "Требует проверки"


def validity_label(offer: ProviderWorkCostOffer) -> str:
    if _is_expired(offer):
        return "Срок истёк"
    if offer.valid_until is None:
        return "Срок не ограничен"
    return offer.valid_until.strftime("%Y.%m.%d")


def status_label(offer: ProviderWorkCostOffer) -> str:
    if _is_expired(offer):
        return "Срок истёк"
    return {
        "draft": "Черновик",
        "active": "Активно",
        "inactive": "Неактивно",
    }.get(offer.status, "Требует проверки")


def quality_flags(offer: ProviderWorkCostOffer) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if _is_expired(offer):
        flags.append({"code": "expired", "label": "Срок истёк", "tone": "warning"})
    if get_work_item(offer.work_code) is None:
        flags.append({"code": "catalog_work_missing", "label": "Работа требует проверки", "tone": "warning"})
    if offer.pricing_mode == "fixed" and (offer.fixed_amount is None or offer.fixed_amount <= 0):
        flags.append({"code": "invalid_amount", "label": "Стоимость требует проверки", "tone": "danger"})
    if offer.pricing_mode == "range" and (
        offer.minimum_amount is None
        or offer.maximum_amount is None
        or offer.minimum_amount <= 0
        or offer.maximum_amount <= 0
        or offer.minimum_amount > offer.maximum_amount
    ):
        flags.append({"code": "invalid_range", "label": "Диапазон требует проверки", "tone": "danger"})
    return flags


async def _get_offer_or_404(db: AsyncSession, offer_id: UUID) -> ProviderWorkCostOffer:
    result = await db.execute(
        select(ProviderWorkCostOffer)
        .options(selectinload(ProviderWorkCostOffer.owner))
        .where(ProviderWorkCostOffer.id == offer_id)
    )
    offer = result.scalar_one_or_none()
    if offer is None:
        raise NotFoundError("Provider work cost offer not found")
    return offer


def _apply_filters(
    query: Select,
    *,
    work_code: str | None,
    region: str | None,
    status: str | None,
    pricing_mode: str | None,
    currency: str | None,
    pricing_unit: str | None,
    updated_since: datetime | None,
) -> Select:
    if work_code:
        query = query.where(ProviderWorkCostOffer.work_code == work_code)
    if region:
        query = query.where(ProviderWorkCostOffer.region == region)
    if status:
        query = query.where(ProviderWorkCostOffer.status == status.lower())
    if pricing_mode:
        query = query.where(ProviderWorkCostOffer.pricing_mode == pricing_mode.lower())
    if currency:
        query = query.where(ProviderWorkCostOffer.currency == currency.upper())
    if pricing_unit:
        query = query.where(ProviderWorkCostOffer.pricing_unit == pricing_unit)
    if updated_since:
        query = query.where(ProviderWorkCostOffer.updated_at >= updated_since)
    return query


def _apply_list_permissions(query: Select, user: Any, *, owner_user_id: UUID | None) -> Select:
    if _has_global_work_cost_admin(user):
        if owner_user_id is not None:
            return query.where(ProviderWorkCostOffer.owner_user_id == owner_user_id)
        return query
    if _has_own_work_cost_access(user):
        return query.where(ProviderWorkCostOffer.owner_user_id == _user_id(user))
    raise ForbiddenError("Provider work cost access is required")


def _require_create_permission(user: Any) -> UUID:
    if not (_has_global_work_cost_admin(user) or _has_own_work_cost_access(user)):
        raise ForbiddenError("Provider work cost create permission is required")
    return _user_id(user)


def _require_read_permission(user: Any, offer: ProviderWorkCostOffer) -> None:
    if _has_global_work_cost_admin(user):
        return
    if _has_own_work_cost_access(user) and str(offer.owner_user_id) == str(_user_id(user)):
        return
    raise ForbiddenError("Provider work cost access is required")


def _require_update_permission(user: Any, offer: ProviderWorkCostOffer) -> None:
    if _has_global_work_cost_admin(user):
        return
    if _has_own_work_cost_access(user) and str(offer.owner_user_id) == str(_user_id(user)):
        return
    raise ForbiddenError("Provider work cost ownership is required")


def _has_global_work_cost_admin(user: Any) -> bool:
    return can(user, MODULE_01_MATERIAL_HUB, "ADMIN", "GLOBAL") or can(
        user,
        MODULE_01_MATERIAL_HUB,
        "APPROVE",
        "GLOBAL",
    )


def _has_own_work_cost_access(user: Any) -> bool:
    return can(user, MODULE_04_WORKS_COSTS, "CREATE", "OWN") or can(
        user,
        MODULE_04_WORKS_COSTS,
        "EDIT",
        "OWN",
    )


def _user_id(user: Any) -> UUID:
    value = _get_value(user, "id") or _get_value(user, "user_id") or _get_value(user, "userId")
    if value is None:
        raise ForbiddenError("Current user id is required")
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ForbiddenError("Current user id is invalid") from exc


def _required_str(value: Any, field_name: str) -> str:
    if value is None:
        raise ValidationError(f"{field_name} is required")
    text = str(value).strip()
    if not text:
        raise ValidationError(f"{field_name} is required")
    return text


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("amount values must be valid decimals") from exc


def _is_expired(offer: ProviderWorkCostOffer) -> bool:
    return offer.status == "active" and offer.valid_until is not None and offer.valid_until < date.today()


def _format_money(value: Any) -> str:
    if value is None:
        return "не указано"
    amount = _decimal_or_none(value)
    if amount is None:
        return "не указано"
    if amount == amount.to_integral_value():
        formatted = f"{int(amount):,}".replace(",", " ")
    else:
        formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return formatted


def _owner_display_name(offer: ProviderWorkCostOffer, user: Any | None) -> str:
    if user is not None:
        try:
            if str(_user_id(user)) == str(offer.owner_user_id):
                return "Моё предложение"
        except ForbiddenError:
            pass
    owner = getattr(offer, "owner", None)
    if owner is not None:
        name = _optional_str(getattr(owner, "name", None))
        if name:
            return name
        email = _optional_str(getattr(owner, "email", None))
        if email:
            return email
    return "Исполнитель"


def _can_edit_offer(user: Any | None, offer: ProviderWorkCostOffer) -> bool:
    if user is None:
        return False
    try:
        _require_update_permission(user, offer)
        return True
    except ForbiddenError:
        return False


def _get_value(source: Any, field_name: str) -> Any:
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)
