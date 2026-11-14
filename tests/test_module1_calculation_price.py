from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.services.module1_calculation_price import CalculationPriceContext, PriceCandidate, calculate_price


CONTEXT = CalculationPriceContext("m3", "RUB", "Краснодарский край", "без доставки", date(2026, 11, 13))


def candidate(offer_id: str, text_amount: str, **changes) -> PriceCandidate:
    base = PriceCandidate(offer_id, Decimal(text_amount), "m3", "RUB", "Краснодарский край", "без доставки",
                          "active", True)
    return replace(base, **changes)


def test_arithmetic_mean_preserves_manual_fallback():
    offers = [candidate("1", "7500"), candidate("2", "8000"), candidate("3", "8500")]
    quote = calculate_price(CONTEXT, offers, manual_price=Decimal("7000"))
    assert quote.amount == Decimal("8000")
    assert quote.source == "AVERAGE"
    assert len(quote.contributors) == 3
    fallback = calculate_price(CONTEXT, [replace(item, status="inactive") for item in offers],
                               manual_price=Decimal("7000"))
    assert fallback.amount == Decimal("7000") and fallback.source == "MANUAL"
    missing = calculate_price(CONTEXT, [])
    assert missing.amount is None and missing.source == "NO_PRICE"


@pytest.mark.parametrize(("changes", "reason"), [
    ({"identity_confirmed": False}, "IDENTITY_UNCONFIRMED"),
    ({"pricing_mode": "range"}, "RANGE_PRICE"),
    ({"region": "Другой регион"}, "REGION_MISMATCH"),
    ({"terms": "с доставкой"}, "TERMS_MISMATCH"),
    ({"currency": "USD"}, "CURRENCY_MISMATCH"),
    ({"valid_until": date(2026, 11, 12)}, "OUTSIDE_VALIDITY"),
    ({"unit": "piece"}, "UNCONFIRMED_CONVERSION"),
    ({"amount": Decimal("0")}, "INVALID_PRICE"),
])
def test_ineligible_offer_does_not_affect_price(changes, reason):
    quote = calculate_price(CONTEXT, [candidate("bad", "5000", **changes), candidate("ok", "8000")])
    assert quote.amount == Decimal("8000")
    assert quote.excluded == (("bad", reason),)


def test_conversion_requires_explicit_positive_factor_and_source():
    offer = candidate("1", "6000", unit="piece", base_units_per_sale_unit=Decimal("0.75"))
    assert calculate_price(CONTEXT, [offer]).excluded == (("1", "INVALID_CONVERSION"),)
    result = calculate_price(CONTEXT, [replace(offer, conversion_source="verified specification")])
    assert result.amount == Decimal("8000")


def test_same_offer_is_never_counted_twice():
    with pytest.raises(ValueError, match="unique"):
        calculate_price(CONTEXT, [candidate("same", "7500"), candidate("same", "8500")])


def test_catalog_work_unit_without_conversion_is_comparable_only_to_itself():
    context = replace(CONTEXT, base_unit="visit")
    offer = candidate("work", "1200", unit="visit")
    assert calculate_price(context, [offer]).amount == Decimal("1200")
    assert calculate_price(context, [replace(offer, unit="hour")]).source == "NO_PRICE"


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1"), Decimal("NaN"), 1.2])
def test_invalid_manual_price_is_not_confused_with_free(value):
    with pytest.raises(ValueError, match="manual price"):
        calculate_price(CONTEXT, [], manual_price=value)
