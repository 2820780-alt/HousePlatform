"""Deterministic M1 calculation prices for explicitly comparable offers.

This pure service does not create materials, modify offers, or persist snapshots.
Callers must supply the eligibility decisions and pricing context from M1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Iterable, Literal

from app.services.module1_material_ui_prices import comparable_unit_price
from app.services.module1_unit_conversion_registry import UnitConversionRegistry
from app.services.module1_work_catalog import get_work_catalog_registry


@dataclass(frozen=True)
class CalculationPriceContext:
    base_unit: str
    currency: str
    region: str
    terms: str
    as_of: date


@dataclass(frozen=True)
class PriceCandidate:
    offer_id: str
    amount: Decimal | None
    unit: str
    currency: str
    region: str
    terms: str
    status: str
    identity_confirmed: bool
    valid_from: date | None = None
    valid_until: date | None = None
    pricing_mode: Literal["fixed", "range"] = "fixed"
    # An explicitly confirmed count of base units per one sale unit.
    base_units_per_sale_unit: Decimal | None = None
    conversion_source: str | None = None


@dataclass(frozen=True)
class PriceContribution:
    offer_id: str
    normalized_amount: Decimal


@dataclass(frozen=True)
class CalculationPrice:
    amount: Decimal | None
    source: Literal["AVERAGE", "MANUAL", "NO_PRICE"]
    context: CalculationPriceContext
    contributors: tuple[PriceContribution, ...] = ()
    excluded: tuple[tuple[str, str], ...] = ()


def _positive_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, (float, bool)):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() and result > 0 else None


def _normalized_unit(unit: str) -> str | None:
    unit = unit.strip()
    if unit == "шт.":
        unit = "шт"
    normalized = UnitConversionRegistry().normalize_unit(unit)
    if normalized:
        return normalized
    # Some existing work units (e.g. visits and shifts) have no conversion rule.
    # They may be compared only by exact catalog identity.
    return unit if unit in get_work_catalog_registry().units else None


def calculate_price(
    context: CalculationPriceContext,
    offers: Iterable[PriceCandidate],
    *,
    manual_price: Decimal | None = None,
) -> CalculationPrice:
    """Compute one unweighted price per context, never using ranges or guesses.

    Manual price is already denominated in the context currency and base unit.
    Cross-unit offer prices need an explicit confirmed base-units coefficient;
    built-in unit conversions are used only for equivalent physical units.
    """
    if not context.base_unit.strip() or not context.region.strip() or not context.terms.strip():
        raise ValueError("base unit, region and comparable terms are required")
    if context.currency.upper() != "RUB":
        raise ValueError("only RUB is supported without an approved exchange-rate policy")
    if not isinstance(context.as_of, date):
        raise ValueError("as_of must be a date")
    base = _normalized_unit(context.base_unit)
    if not base:
        raise ValueError("unknown base unit")
    candidates = tuple(offers)
    ids = [candidate.offer_id for candidate in candidates]
    if any(not offer_id or not offer_id.strip() for offer_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("offer identifiers must be present and unique")
    manual = _positive_decimal(manual_price)
    if manual_price is not None and manual is None:
        raise ValueError("manual price must be a positive finite decimal")
    contributions: list[PriceContribution] = []
    excluded: list[tuple[str, str]] = []
    with localcontext() as decimal_context:
        decimal_context.prec = 34
        for offer in candidates:
            reason = None
            if offer.status.lower() != "active":
                reason = "INACTIVE"
            elif offer.pricing_mode != "fixed":
                reason = "RANGE_PRICE"
            elif offer.identity_confirmed is not True:
                reason = "IDENTITY_UNCONFIRMED"
            elif offer.currency.upper() != context.currency.upper():
                reason = "CURRENCY_MISMATCH"
            elif offer.region.strip().casefold() != context.region.strip().casefold():
                reason = "REGION_MISMATCH"
            elif offer.terms.strip().casefold() != context.terms.strip().casefold():
                reason = "TERMS_MISMATCH"
            elif (offer.valid_from and offer.valid_from > context.as_of) or (
                offer.valid_until and offer.valid_until < context.as_of
            ):
                reason = "OUTSIDE_VALIDITY"
            amount = _positive_decimal(offer.amount)
            if reason is None and amount is None:
                reason = "INVALID_PRICE"
            normalized = None
            if reason is None:
                sale = _normalized_unit(offer.unit)
                if not sale:
                    reason = "UNKNOWN_UNIT"
                elif sale == base:
                    normalized = amount
                elif offer.base_units_per_sale_unit is not None:
                    factor = _positive_decimal(offer.base_units_per_sale_unit)
                    if factor is None or not (offer.conversion_source or "").strip():
                        reason = "INVALID_CONVERSION"
                    else:
                        normalized = amount / factor
                else:
                    # The established registry permits dimensional unit aliases,
                    # but requires an explicit verified profile for cross-dimension cases.
                    normalized = comparable_unit_price(amount, offer.unit, context.base_unit, currency=context.currency)
                    if normalized is None:
                        reason = "UNCONFIRMED_CONVERSION"
            if reason:
                excluded.append((offer.offer_id, reason))
            else:
                contributions.append(PriceContribution(offer.offer_id, normalized))
        if contributions:
            amount = sum((item.normalized_amount for item in contributions), Decimal(0)) / len(contributions)
            return CalculationPrice(amount, "AVERAGE", context, tuple(contributions), tuple(excluded))
    if manual is not None:
        return CalculationPrice(manual, "MANUAL", context, excluded=tuple(excluded))
    return CalculationPrice(None, "NO_PRICE", context, excluded=tuple(excluded))
