from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.api.v1 import material_hub_view
from app.api.v1 import module1_work_cost_offers as work_cost_api
from app.models.price_history import PriceHistory
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.schemas.module1_work_cost import ProviderWorkCostOfferRead
from app.services.module1_provider_work_cost_offers import (
    MIN_COMPARABLE_OFFERS,
    ProviderWorkCostMarketSanityStatus,
    build_provider_work_cost_market_sanity_map,
    evaluate_provider_work_cost_market_sanity,
    provider_work_cost_market_sanity_to_dict,
    provider_work_cost_offer_to_dict,
)


AS_OF = date(2026, 9, 10)
WORK_CODE = "wall_finishing_plaster"
UNIT = "m2"
CURRENCY = "RUB"
REGION = "Краснодарский край"
TARGET_OWNER = UUID(int=1)


class QueryResult:
    def __init__(self, items):
        self._items = tuple(items)

    def scalars(self):
        return self

    def all(self):
        return list(self._items)


class QueryOnlyDB:
    async def connection(self):
        class UnmigratedConnection:
            async def run_sync(self, _operation):
                return False
        return UnmigratedConnection()

    def __init__(self, items):
        self.items = tuple(items)
        self.execute_count = 0

    async def execute(self, statement):
        self.execute_count += 1
        return QueryResult(self.items)

    def add(self, item):
        raise AssertionError("Market sanity must not write to the database")

    async def flush(self):
        raise AssertionError("Market sanity must not flush the database")

    async def commit(self):
        raise AssertionError("Market sanity must not commit the database")


def _offer(amount="100", **overrides):
    data = {
        "id": uuid4(),
        "work_code": WORK_CODE,
        "owner_user_id": TARGET_OWNER,
        "region": REGION,
        "pricing_mode": "fixed",
        "fixed_amount": Decimal(str(amount)) if amount is not None else None,
        "minimum_amount": None,
        "maximum_amount": None,
        "currency": CURRENCY,
        "pricing_unit": UNIT,
        "valid_from": AS_OF - timedelta(days=30),
        "valid_until": AS_OF + timedelta(days=30),
        "status": "active",
        "created_at": datetime(2026, 8, 1, 9, 0),
        "updated_at": datetime(2026, 8, 1, 9, 0),
    }
    data.update(overrides)
    return ProviderWorkCostOffer(**data)


def _range_offer(minimum, maximum, **overrides):
    return _offer(
        None,
        pricing_mode="range",
        fixed_amount=None,
        minimum_amount=Decimal(str(minimum)),
        maximum_amount=Decimal(str(maximum)),
        **overrides,
    )


def _peers(values=(80, 90, 100, 110, 120), *, owner_offset=10, **overrides):
    return [
        _offer(
            value,
            owner_user_id=UUID(int=owner_offset + index),
            updated_at=datetime(2026, 8, index + 1, 9, 0),
            **overrides,
        )
        for index, value in enumerate(values)
    ]


def _evaluate(target=None, peers=None):
    return evaluate_provider_work_cost_market_sanity(
        target or _offer(),
        _peers() if peers is None else peers,
        as_of=AS_OF,
    )


def test_minimum_comparable_offer_constant_is_explicit():
    assert MIN_COMPARABLE_OFFERS == 5


def test_no_comparable_offers_is_insufficient_data():
    result = _evaluate(peers=[])

    assert result.status is ProviderWorkCostMarketSanityStatus.INSUFFICIENT_DATA
    assert result.comparable_offer_count == 0
    assert result.reference_stats is None


@pytest.mark.parametrize("peer_count", [1, 2, 3, 4])
def test_one_to_four_comparable_offers_are_insufficient(peer_count):
    result = _evaluate(peers=_peers()[:peer_count])

    assert result.status is ProviderWorkCostMarketSanityStatus.INSUFFICIENT_DATA
    assert result.comparable_offer_count == peer_count


def test_five_normal_comparable_offers_produce_robust_reference_stats():
    result = _evaluate()

    assert result.status is ProviderWorkCostMarketSanityStatus.WITHIN_COMPARABLE_RANGE
    assert result.comparable_offer_count == 5
    assert result.reference_stats is not None
    assert result.reference_stats.median == Decimal("100")
    assert result.reference_stats.q1 == Decimal("85")
    assert result.reference_stats.q3 == Decimal("115")
    assert result.reference_stats.lower_bound == Decimal("40.0")
    assert result.reference_stats.upper_bound == Decimal("160.0")


@pytest.mark.parametrize(
    ("amount", "expected_status"),
    [
        ("39.99", ProviderWorkCostMarketSanityStatus.LOW_OUTLIER),
        ("160.01", ProviderWorkCostMarketSanityStatus.HIGH_OUTLIER),
    ],
)
def test_fixed_target_outliers_are_classified_against_tukey_fences(amount, expected_status):
    assert _evaluate(target=_offer(amount)).status is expected_status


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("work_code", "other_work"),
        ("pricing_unit", "hour"),
        ("currency", "USD"),
        ("region", "Москва"),
    ],
)
def test_exact_cohort_mismatches_are_excluded(field, value):
    peers = _peers()[:4]
    peers.append(_offer("100", owner_user_id=UUID(int=99), **{field: value}))

    result = _evaluate(peers=peers)

    assert result.status is ProviderWorkCostMarketSanityStatus.INSUFFICIENT_DATA
    assert result.comparable_offer_count == 4


@pytest.mark.parametrize("status", ["draft", "inactive"])
def test_non_active_peer_statuses_are_excluded(status):
    peers = _peers()[:4]
    peers.append(_offer("100", owner_user_id=UUID(int=99), status=status))

    assert _evaluate(peers=peers).comparable_offer_count == 4


def test_expired_peer_is_excluded():
    peers = _peers()[:4]
    peers.append(
        _offer(
            "100",
            owner_user_id=UUID(int=99),
            valid_until=AS_OF - timedelta(days=1),
        )
    )

    assert _evaluate(peers=peers).comparable_offer_count == 4


def test_future_peer_is_excluded():
    peers = _peers()[:4]
    peers.append(
        _offer(
            "100",
            owner_user_id=UUID(int=99),
            valid_from=AS_OF + timedelta(days=1),
        )
    )

    assert _evaluate(peers=peers).comparable_offer_count == 4


def test_target_offer_is_never_its_own_peer():
    target = _offer("100", owner_user_id=None)
    peers = _peers()[:4] + [target]

    result = _evaluate(target=target, peers=peers)

    assert result.comparable_offer_count == 4


def test_other_offer_from_target_owner_is_not_an_independent_market_peer():
    target = _offer("100")
    peers = _peers()[:4] + [_offer("130", owner_user_id=TARGET_OWNER)]

    assert _evaluate(target=target, peers=peers).comparable_offer_count == 4


def test_same_owner_contributes_only_latest_effective_offer():
    owner = UUID(int=20)
    peers = [
        _offer("100", owner_user_id=owner, updated_at=datetime(2026, 8, 1, 9, 0)),
        _offer("300", owner_user_id=owner, updated_at=datetime(2026, 8, 2, 9, 0)),
        *_peers((90, 100, 110, 120), owner_offset=30),
    ]

    result = _evaluate(peers=peers)

    assert result.comparable_offer_count == 5
    assert result.reference_stats is not None
    assert result.reference_stats.median == Decimal("110")
    assert result.reference_stats.q3 == Decimal("210")


def test_fixed_peer_uses_fixed_amount_as_representative():
    result = _evaluate(peers=_peers((80, 90, 100, 110, 120)))

    assert result.reference_stats is not None
    assert result.reference_stats.median == Decimal("100")


def test_range_peer_uses_decimal_midpoint_as_representative():
    peers = [
        _range_offer(
            value - 10,
            value + 10,
            owner_user_id=UUID(int=40 + index),
        )
        for index, value in enumerate((80, 90, 100, 110, 120))
    ]

    result = _evaluate(peers=peers)

    assert result.reference_stats is not None
    assert result.reference_stats.median == Decimal("100")


@pytest.mark.parametrize(
    ("minimum", "maximum", "expected_status"),
    [
        ("20", "39.99", ProviderWorkCostMarketSanityStatus.LOW_OUTLIER),
        ("160.01", "180", ProviderWorkCostMarketSanityStatus.HIGH_OUTLIER),
        ("30", "50", ProviderWorkCostMarketSanityStatus.WITHIN_COMPARABLE_RANGE),
    ],
)
def test_target_range_uses_full_interval_against_reference_band(minimum, maximum, expected_status):
    target = _range_offer(minimum, maximum)

    assert _evaluate(target=target).status is expected_status


@pytest.mark.parametrize(
    ("target", "expected_status"),
    [
        (_offer("100"), ProviderWorkCostMarketSanityStatus.WITHIN_COMPARABLE_RANGE),
        (_offer("101"), ProviderWorkCostMarketSanityStatus.REVIEW),
    ],
)
def test_zero_iqr_is_handled_conservatively(target, expected_status):
    result = _evaluate(target=target, peers=_peers((100, 100, 100, 100, 100)))

    assert result.status is expected_status
    assert result.reference_stats is not None
    assert result.reference_stats.lower_bound == Decimal("100")
    assert result.reference_stats.upper_bound == Decimal("100")


def test_decimal_values_remain_exact_without_float_rounding():
    peers = _peers(("0.10", "0.20", "0.30", "0.40", "0.50"))
    result = _evaluate(target=_offer("0.30"), peers=peers)

    assert result.reference_stats is not None
    assert result.reference_stats.median == Decimal("0.30")
    assert isinstance(result.reference_stats.upper_bound, Decimal)


def test_evaluation_does_not_mutate_target_offer():
    target = _range_offer("80.25", "120.75")
    before = {
        "status": target.status,
        "fixed_amount": target.fixed_amount,
        "minimum_amount": target.minimum_amount,
        "maximum_amount": target.maximum_amount,
        "valid_from": target.valid_from,
        "valid_until": target.valid_until,
    }

    _evaluate(target=target)

    assert before == {
        "status": target.status,
        "fixed_amount": target.fixed_amount,
        "minimum_amount": target.minimum_amount,
        "maximum_amount": target.maximum_amount,
        "valid_from": target.valid_from,
        "valid_until": target.valid_until,
    }


def test_material_price_record_is_not_a_work_cost_comparable():
    material_price = PriceHistory()
    result = _evaluate(peers=_peers()[:4] + [material_price])

    assert result.comparable_offer_count == 4


def test_invalid_target_amount_requires_review_when_reference_is_available():
    result = _evaluate(target=_offer(None))

    assert result.status is ProviderWorkCostMarketSanityStatus.REVIEW
    assert result.reason == "invalid_target_amount"
    assert result.reference_stats is not None


def test_serialized_signal_exposes_safe_advisory_contract():
    payload = provider_work_cost_market_sanity_to_dict(_evaluate())

    assert payload["status"] == "WITHIN_COMPARABLE_RANGE"
    assert payload["comparableOfferCount"] == 5
    assert payload["reason"] == "target_overlaps_comparable_range"
    assert payload["explanation"]
    assert payload["asOf"] == AS_OF
    assert payload["referenceStats"] == {
        "median": Decimal("100"),
        "q1": Decimal("85"),
        "q3": Decimal("115"),
        "lowerBound": Decimal("40.0"),
        "upperBound": Decimal("160.0"),
    }


@pytest.mark.asyncio
async def test_batch_loader_uses_one_read_query_for_multiple_targets_and_never_writes():
    second_work = "floor_installation"
    targets = [_offer("100"), _offer("200", work_code=second_work, owner_user_id=UUID(int=2))]
    peers = [
        *_peers(),
        *_peers((180, 190, 200, 210, 220), owner_offset=100, work_code=second_work),
    ]
    db = QueryOnlyDB(peers)

    result = await build_provider_work_cost_market_sanity_map(db, targets, as_of=AS_OF)

    assert db.execute_count == 1
    assert set(result) == {str(target.id) for target in targets}
    assert all(signal.comparable_offer_count == 5 for signal in result.values())


@pytest.mark.asyncio
async def test_batch_loader_with_no_targets_does_not_query_database():
    db = QueryOnlyDB([])

    result = await build_provider_work_cost_market_sanity_map(db, [], as_of=AS_OF)

    assert result == {}
    assert db.execute_count == 0


def test_service_has_no_material_price_or_automatic_action_dependency():
    source = Path("app/services/module1_provider_work_cost_offers.py").read_text(encoding="utf-8")
    market_section = source.split("def evaluate_provider_work_cost_market_sanity(", 1)[1].split(
        "async def update_provider_work_cost_offer(",
        1,
    )[0]

    for forbidden in [
        "PriceHistory",
        "Material(",
        "SupplierPrice",
        "deactivate_provider_work_cost_offer",
        "db.add",
        "db.flush",
        "db.commit",
    ]:
        assert forbidden not in market_section


def test_existing_work_cost_ui_exposes_compact_market_signal():
    template = Path("templates/material_hub_work_costs.html").read_text(encoding="utf-8")

    assert 'data-field="market"' in template
    assert "Сопоставимость" in template
    assert "marketSanityTone" in template
    assert "comparableOfferCount" in template

def test_offer_read_schema_accepts_nested_market_sanity_contract():
    target = _offer("100")
    payload = provider_work_cost_offer_to_dict(target, market_sanity=_evaluate(target=target))

    validated = ProviderWorkCostOfferRead.model_validate(payload)

    assert validated.marketSanity is not None
    assert validated.marketSanity.status == "WITHIN_COMPARABLE_RANGE"
    assert validated.marketSanity.referenceStats is not None
    assert validated.marketSanity.referenceStats.median == Decimal("100")

@pytest.mark.asyncio
async def test_list_api_calculates_market_sanity_once_for_the_page(monkeypatch):
    target = _offer("100")
    signal = _evaluate(target=target)
    calls = {"market": 0}

    async def fake_list(db, user, **filters):
        return SimpleNamespace(items=(target,), total=1, offset=0, limit=50)

    async def fake_market(db, targets):
        calls["market"] += 1
        assert tuple(targets) == (target,)
        return {str(target.id): signal}

    monkeypatch.setattr(work_cost_api, "list_provider_work_cost_offers", fake_list)
    monkeypatch.setattr(work_cost_api, "build_provider_work_cost_market_sanity_map", fake_market)

    response = await work_cost_api.list_work_cost_offers(
        QueryOnlyDB([]),
        SimpleNamespace(id=uuid4(), roleCode="PLATFORM_ADMIN"),
    )

    assert calls["market"] == 1
    assert response.model_dump()["items"][0]["marketSanity"]["status"] == "WITHIN_COMPARABLE_RANGE"


@pytest.mark.asyncio
async def test_server_work_cost_loader_uses_constant_two_queries_for_all_rows():
    offers = _peers()
    db = QueryOnlyDB(offers)

    rows = await material_hub_view._load_provider_work_cost_offer_rows(db)

    assert len(rows) == len(offers)
    assert db.execute_count == 2
    assert all(row["marketSanity"]["status"] == "INSUFFICIENT_DATA" for row in rows)
