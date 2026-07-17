from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1 import module1_work_cost_offers as work_cost_api
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.services import module1_work_cost_export_contract as export_service
from app.services.module1_work_catalog import list_work_items
from app.services.module1_work_cost_export_contract import (
    OVERLAP_WARNING,
    WORK_COST_EXPORT_CONSUMER,
    WORK_COST_EXPORT_SCHEMA_VERSION,
    WORK_COST_EXPORT_SOURCE_MODULE,
    build_work_cost_offer_export_package,
    build_work_cost_offer_export_package_from_offers,
    work_cost_export_package_to_dict,
    work_cost_offer_eligibility,
)

RANGE_WORK = next(work for work in list_work_items() if work.is_range_allowed)
REGION = "Р С™РЎР‚Р В°РЎРѓР Р…Р С•Р Т‘Р В°РЎР‚РЎРѓР С”Р С‘Р в„– Р С”РЎР‚Р В°Р в„–"
GENERATED_AT = datetime(2026, 7, 17, 12, 30, tzinfo=UTC)


def _offer(**overrides):
    data = {
        "id": uuid4(),
        "work_code": RANGE_WORK.work_code,
        "owner_user_id": uuid4(),
        "region": REGION,
        "pricing_mode": "fixed",
        "fixed_amount": Decimal("1500.00"),
        "minimum_amount": None,
        "maximum_amount": None,
        "currency": "RUB",
        "pricing_unit": RANGE_WORK.allowed_units[0],
        "valid_from": date(2026, 1, 1),
        "valid_until": date(2026, 12, 31),
        "status": "active",
        "created_at": datetime(2026, 7, 17, 10, 0),
        "updated_at": datetime(2026, 7, 17, 11, 0),
    }
    data.update(overrides)
    return ProviderWorkCostOffer(**data)


def _range_offer(**overrides):
    data = {
        "pricing_mode": "range",
        "fixed_amount": None,
        "minimum_amount": Decimal("1200.00"),
        "maximum_amount": Decimal("1800.00"),
    }
    data.update(overrides)
    return _offer(**data)


def test_eligibility_accepts_active_fixed_and_range_offers():
    fixed = work_cost_offer_eligibility(_offer())
    ranged = work_cost_offer_eligibility(_range_offer())

    assert fixed.is_eligible is True
    assert fixed.reason_codes == ()
    assert ranged.is_eligible is True
    assert ranged.reason_codes == ()
    assert fixed.no_side_effects is True


@pytest.mark.parametrize(
    ("offer", "reason_code"),
    [
        (_offer(status="draft"), "draft"),
        (_offer(status="inactive"), "inactive"),
        (_offer(valid_until=date(2020, 1, 1)), "expired"),
        (_offer(work_code="missing_work"), "missing_work"),
        (_offer(pricing_mode="unknown"), "invalid_pricing_mode"),
        (_offer(fixed_amount=Decimal("0")), "invalid_fixed"),
        (_range_offer(minimum_amount=Decimal("2000"), maximum_amount=Decimal("1000")), "invalid_range"),
        (_offer(currency="USD"), "invalid_currency"),
        (_offer(pricing_unit="unknown_unit"), "invalid_pricing_unit"),
    ],
)
def test_eligibility_excludes_non_exportable_offers(offer, reason_code):
    report = work_cost_offer_eligibility(offer)

    assert report.is_eligible is False
    assert reason_code in report.reason_codes
    assert report.reasons


def test_eligibility_excludes_offer_without_owner_reference():
    offer = _offer()
    offer.owner_user_id = None

    report = work_cost_offer_eligibility(offer)

    assert report.is_eligible is False
    assert "missing_owner" in report.reason_codes


def test_package_exports_versioned_records_without_selecting_best_offer_or_material_fields():
    fixed = _offer(fixed_amount=Decimal("1500.00"), updated_at=datetime(2026, 7, 17, 11, 0))
    ranged = _range_offer(minimum_amount=Decimal("1200.00"), maximum_amount=Decimal("1800.00"))

    package = build_work_cost_offer_export_package_from_offers(
        [fixed, ranged],
        generated_at=GENERATED_AT,
        filters={"region": REGION},
        scope={"purpose": "preview"},
        total_scanned=2,
    )
    payload = work_cost_export_package_to_dict(package)

    assert payload["schema_version"] == WORK_COST_EXPORT_SCHEMA_VERSION
    assert payload["source_module"] == WORK_COST_EXPORT_SOURCE_MODULE
    assert payload["consumer"] == WORK_COST_EXPORT_CONSUMER
    assert payload["record_count"] == 2
    assert payload["no_module5_write"] is True
    assert payload["no_estimate_total"] is True
    assert payload["no_selected_offer"] is True
    assert {record["pricing_mode"] for record in payload["records"]} == {"fixed", "range"}
    assert any(record["fixed_amount"] == "1500.00" for record in payload["records"])
    assert any(record["minimum_amount"] == "1200.00" for record in payload["records"])
    text = repr(payload).lower()
    for forbidden in (
        "material_id",
        "catalog_product_id",
        "price_observation",
        "material_match_candidate",
        "source_task",
        "adapter",
        "raw_payload",
        "module5_estimate_id",
    ):
        assert forbidden not in text


def test_duplicate_active_offers_are_warned_not_resolved_or_averaged():
    owner_id = uuid4()
    first = _offer(owner_user_id=owner_id, fixed_amount=Decimal("1500.00"))
    second = _offer(owner_user_id=owner_id, fixed_amount=Decimal("1700.00"))

    payload = work_cost_export_package_to_dict(
        build_work_cost_offer_export_package_from_offers([first, second], generated_at=GENERATED_AT)
    )

    assert payload["record_count"] == 2
    assert OVERLAP_WARNING in payload["warnings"]
    assert all(OVERLAP_WARNING in record["quality_warnings"] for record in payload["records"])
    exported_amounts = {record["fixed_amount"] for record in payload["records"]}
    assert exported_amounts == {"1500.00", "1700.00"}
    assert "1600" not in repr(payload)


@pytest.mark.asyncio
async def test_export_builder_delegates_to_permissioned_list_service(monkeypatch):
    captured = {}
    offer = _offer()

    async def fake_list_provider_work_cost_offers(db, user, **kwargs):
        captured["db"] = db
        captured["user"] = user
        captured["kwargs"] = kwargs
        return SimpleNamespace(items=[offer], total=1, offset=3, limit=7)

    monkeypatch.setattr(export_service, "list_provider_work_cost_offers", fake_list_provider_work_cost_offers)

    user = SimpleNamespace(id=uuid4(), roleCode="PLATFORM_ADMIN")
    package = await build_work_cost_offer_export_package(
        object(),
        user,
        work_code=RANGE_WORK.work_code,
        region=REGION,
        provider_user_id=offer.owner_user_id,
        currency="rub",
        pricing_unit=RANGE_WORK.allowed_units[0],
        updated_since=datetime(2026, 7, 1),
        offset=3,
        limit=7,
        generated_at=GENERATED_AT,
    )

    assert package.record_count == 1
    assert captured["user"] is user
    assert captured["kwargs"]["owner_user_id"] == offer.owner_user_id
    assert captured["kwargs"]["currency"] == "rub"
    assert captured["kwargs"]["pricing_unit"] == RANGE_WORK.allowed_units[0]
    assert package.offset == 3
    assert package.limit == 7


@pytest.mark.asyncio
async def test_preview_api_passes_filters_to_export_builder(monkeypatch):
    captured = {}
    offer = _offer()

    async def fake_build(db, user, **kwargs):
        captured["db"] = db
        captured["user"] = user
        captured["kwargs"] = kwargs
        return build_work_cost_offer_export_package_from_offers([offer], generated_at=GENERATED_AT)

    monkeypatch.setattr(work_cost_api, "build_work_cost_offer_export_package", fake_build)
    user = SimpleNamespace(id=uuid4(), roleCode="PLATFORM_ADMIN")
    updated_since = datetime(2026, 7, 1, 9, 15)

    payload = await work_cost_api.preview_work_cost_offer_export(
        object(),
        user,
        workCode=RANGE_WORK.work_code,
        region=REGION,
        providerUserId=offer.owner_user_id,
        currency="RUB",
        pricingUnit=RANGE_WORK.allowed_units[0],
        updatedSince=updated_since,
        offset=2,
        limit=20,
    )

    assert payload["schema_version"] == WORK_COST_EXPORT_SCHEMA_VERSION
    assert captured["user"] is user
    assert captured["kwargs"] == {
        "work_code": RANGE_WORK.work_code,
        "region": REGION,
        "provider_user_id": offer.owner_user_id,
        "currency": "RUB",
        "pricing_unit": RANGE_WORK.allowed_units[0],
        "updated_since": updated_since,
        "offset": 2,
        "limit": 20,
    }


def test_export_preview_route_is_declared_before_uuid_route():
    source = Path("app/api/v1/module1_work_cost_offers.py").read_text(encoding="utf-8")

    assert source.index('@router.get("/export-preview")') < source.index('@router.get("/{offer_id}"')


def test_export_service_is_read_only_and_does_not_import_material_or_module5_layers():
    source = Path("app/services/module1_work_cost_export_contract.py").read_text(encoding="utf-8")
    forbidden_fragments = (
        ".commit(",
        "db.add(",
        "insert(",
        "update(",
        "delete(",
        "from app.models.material",
        "from app.models.catalog_product",
        "from app.models.price_history",
        "MaterialMatchCandidate",
        "SourceTask",
        "source_task_runner",
        "from app.services.module5",
        "from app.api.v1.module5",
        "app.services.module5",
    )

    for forbidden in forbidden_fragments:
        assert forbidden not in source