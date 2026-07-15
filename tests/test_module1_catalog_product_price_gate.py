from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.catalog_product import CatalogProduct
from app.models.enums import CatalogProductStatus, SourceActionType, TaskResultType
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.source_task_result import SourceTaskResult
from app.services import source_task_runner as runner
from app.source_integrations.base import SourceProduct


class FakeDB:
    def __init__(self):
        self.added = []
        self.flushes = 0

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushes += 1


class FakeIntegration:
    def __init__(self, products):
        self._products = products

    async def fetch_products(self, action_type, parameters):
        return list(self._products)


def _task():
    source = SimpleNamespace(
        id=uuid4(),
        name="Test Source",
        url="https://example.test/catalog",
        source_type="supplier_site",
        status=None,
        last_price_update_at=None,
    )
    return SimpleNamespace(
        id=uuid4(),
        source_id=source.id,
        source=source,
        action_type=SourceActionType.UPDATE_PRICES,
        parameters={},
        result_summary=None,
    )


def _product(price):
    return SourceProduct(
        external_id="p-1",
        external_url="https://example.test/product/p-1",
        raw_name="Газоблок D500",
        raw_category="Газоблоки",
        price=price,
        currency="RUB",
        unit="м3",
        availability="in_stock",
        region="Краснодарский край",
    )


@pytest.mark.parametrize(
    ("price", "reason"),
    [
        (None, "missing_price"),
        (Decimal("0"), "invalid_or_non_positive_price"),
        (Decimal("-1"), "invalid_or_non_positive_price"),
        ("not-a-number", "invalid_or_non_positive_price"),
    ],
)
@pytest.mark.asyncio
async def test_no_price_source_product_is_kept_as_source_evidence_without_catalog_product(monkeypatch, price, reason):
    async def fail_upsert(*args, **kwargs):
        pytest.fail("No-price SourceProduct must not reach CatalogProduct upsert")

    async def fail_match(*args, **kwargs):
        pytest.fail("No-price SourceProduct must not reach material matching")

    monkeypatch.setattr(runner, "_upsert_catalog_product", fail_upsert)
    monkeypatch.setattr(runner, "_match_or_queue_material", fail_match)

    db = FakeDB()
    task = _task()

    await runner._run_product_scan(db, task, FakeIntegration([_product(price)]))

    assert not any(isinstance(item, CatalogProduct) for item in db.added)
    assert not any(isinstance(item, MaterialMatchCandidate) for item in db.added)

    results = [item for item in db.added if isinstance(item, SourceTaskResult)]
    assert len(results) == 1
    result = results[0]
    assert result.result_type == TaskResultType.NEEDS_REVIEW
    assert result.entity_type == "SourceProduct"
    assert result.entity_id is None
    assert result.status == "rejected_no_positive_price"
    assert result.new_value["rejection_reason"] == reason
    assert result.new_value["external_url"] == "https://example.test/product/p-1"

    assert task.result_summary["created"] == 0
    assert task.result_summary["updated"] == 0
    assert task.result_summary["match_candidates"] == 0
    assert task.result_summary["rejected_no_price"] == 1


@pytest.mark.asyncio
async def test_positive_price_keeps_catalog_product_flow(monkeypatch):
    calls = {"upsert": 0, "match": 0}
    catalog_product = CatalogProduct(
        id=uuid4(),
        source_id=uuid4(),
        external_id="p-1",
        external_url="https://example.test/product/p-1",
        raw_name="Газоблок D500",
        normalized_name="газоблок d500",
        price=Decimal("1250.00"),
        currency="RUB",
        unit="м3",
        status=CatalogProductStatus.NEEDS_REVIEW,
    )

    async def fake_upsert(db, task, product):
        calls["upsert"] += 1
        return catalog_product, TaskResultType.CREATED, False

    async def fake_match(db, product):
        calls["match"] += 1
        return "matched"

    monkeypatch.setattr(runner, "_upsert_catalog_product", fake_upsert)
    monkeypatch.setattr(runner, "_match_or_queue_material", fake_match)

    db = FakeDB()
    task = _task()

    await runner._run_product_scan(db, task, FakeIntegration([_product(Decimal("1250.00"))]))

    assert calls == {"upsert": 1, "match": 1}
    results = [item for item in db.added if isinstance(item, SourceTaskResult) and item.entity_type == "CatalogProduct"]
    assert len(results) == 1
    assert results[0].entity_id == catalog_product.id
    assert task.result_summary["created"] == 1
    assert task.result_summary["rejected_no_price"] == 0


@pytest.mark.asyncio
async def test_existing_positive_catalog_product_is_not_zeroed_by_later_no_price_scan(monkeypatch):
    existing = CatalogProduct(
        id=uuid4(),
        source_id=uuid4(),
        external_id="p-1",
        external_url="https://example.test/product/p-1",
        raw_name="Газоблок D500",
        normalized_name="газоблок d500",
        price=Decimal("1250.00"),
        currency="RUB",
        unit="м3",
        status=CatalogProductStatus.ACTIVE,
    )

    async def fake_find_catalog_product(db, source_id, product):
        return existing

    monkeypatch.setattr(runner, "_find_catalog_product", fake_find_catalog_product)

    db = FakeDB()
    task = _task()
    product_without_price = _product(None)

    result, result_type, price_changed = await runner._upsert_catalog_product(db, task, product_without_price)

    assert result is existing
    assert result_type == TaskResultType.UNCHANGED
    assert price_changed is False
    assert existing.price == Decimal("1250.00")
    assert not any(isinstance(item, MaterialMatchCandidate) for item in db.added)
