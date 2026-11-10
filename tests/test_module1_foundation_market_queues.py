from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.enums import CatalogProductStatus, MaterialStatus
from app.services.module1_foundation_market_queues import classify_market_needs


AS_OF = date(2026, 11, 10)


def material(status=MaterialStatus.DRAFT):
    return SimpleNamespace(id=uuid4(), canonical_name="Материал", status=status)


def product(price=None, url="https://example.com/product", status=CatalogProductStatus.ACTIVE):
    return SimpleNamespace(price=price, external_url=url, status=status)


def supplier_price(price, valid_until=None):
    return SimpleNamespace(price=price, valid_until=valid_until)


def test_candidate_without_offers_needs_search_and_cannot_be_matched_automatically():
    items = classify_market_needs(material(), [], [], as_of=AS_OF)
    assert len(items) == 1
    assert (items[0].queue, items[0].reason, items[0].automatic_matching_allowed) == (
        "SEARCH", "NO_KNOWN_OFFER", False,
    )


def test_verified_material_with_priced_offer_goes_to_refresh():
    items = classify_market_needs(material(MaterialStatus.VERIFIED), [product(Decimal("150.00"))], [], as_of=AS_OF)
    assert len(items) == 1
    assert (items[0].queue, items[0].priced_product_count, items[0].automatic_matching_allowed) == (
        "REFRESH", 1, True,
    )


@pytest.mark.parametrize("price", [None, Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_missing_or_invalid_price_does_not_create_a_price(price):
    items = classify_market_needs(material(), [product(price)], [], as_of=AS_OF)
    assert [item.queue for item in items] == ["SEARCH"]
    assert items[0].priced_product_count == 0


def test_incomplete_offer_can_require_both_search_and_price_review():
    items = classify_market_needs(material(), [product(Decimal("100"), url=None)], [], as_of=AS_OF)
    assert [item.queue for item in items] == ["SEARCH", "REFRESH"]
    assert all(not item.automatic_matching_allowed for item in items)


def test_expired_supplier_price_is_reported_for_refresh_not_as_current_price():
    prices = [supplier_price(Decimal("100"), date(2026, 1, 1)), supplier_price(Decimal("0"))]
    items = classify_market_needs(material(), [], prices, as_of=AS_OF)
    assert [item.queue for item in items] == ["REFRESH"]
    assert items[0].supplier_price_count == 1
    assert items[0].expired_supplier_price_count == 1


def test_inactive_offers_and_archived_material_do_not_enter_refresh_queue():
    inactive = product(Decimal("50"), status=CatalogProductStatus.ARCHIVED)
    assert [item.queue for item in classify_market_needs(material(), [inactive], [], as_of=AS_OF)] == ["SEARCH"]
    assert classify_market_needs(material(MaterialStatus.ARCHIVED), [inactive], [], as_of=AS_OF) == ()


def test_assessment_date_is_explicit():
    with pytest.raises(ValueError):
        classify_market_needs(material(), [], [], as_of=None)
