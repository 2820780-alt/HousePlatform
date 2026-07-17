from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.permission_guard import can
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.services.module1_work_catalog import get_work_item, list_work_items


MODULE_01_MATERIAL_HUB = "MODULE_01_MATERIAL_HUB"
MODULE_04_WORKS_COSTS = "MODULE_04_WORKS_COSTS"

PRICING_MODES = frozenset({"fixed", "range"})
STATUSES = frozenset({"draft", "active", "inactive"})
SUPPORTED_CURRENCIES = frozenset({"RUB"})


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
    offset: int = 0,
    limit: int = 50,
) -> ProviderWorkCostOfferListResult:
    query = select(ProviderWorkCostOffer)
    query = _apply_list_permissions(query, user, owner_user_id=owner_user_id)
    query = _apply_filters(query, work_code=work_code, region=region, status=status, pricing_mode=pricing_mode)

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


def provider_work_cost_offer_to_dict(offer: ProviderWorkCostOffer, user: Any | None = None) -> dict[str, Any]:
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
    result = await db.execute(select(ProviderWorkCostOffer).where(ProviderWorkCostOffer.id == offer_id))
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
) -> Select:
    if work_code:
        query = query.where(ProviderWorkCostOffer.work_code == work_code)
    if region:
        query = query.where(ProviderWorkCostOffer.region == region)
    if status:
        query = query.where(ProviderWorkCostOffer.status == status.lower())
    if pricing_mode:
        query = query.where(ProviderWorkCostOffer.pricing_mode == pricing_mode.lower())
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
