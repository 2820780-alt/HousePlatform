from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1 import module1_work_cost_offers as work_cost_api
from app.core.exceptions import ForbiddenError, ValidationError
from app.models.catalog_product import CatalogProduct
from app.models.material import Material
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.schemas.module1_work_cost import ProviderWorkCostOfferCreate
from app.services import module1_provider_work_cost_offers as service
from app.services.module1_provider_work_cost_offers import (
    ProviderWorkCostOfferPayload,
    create_provider_work_cost_offer,
    deactivate_provider_work_cost_offer,
    provider_work_cost_offer_to_dict,
    update_provider_work_cost_offer,
    validate_provider_work_cost_payload,
)
from app.services.module1_work_catalog import list_work_items


RANGE_WORK = next(work for work in list_work_items() if work.is_range_allowed)


class FakeResult:
    def __init__(self, one=None, items=None, scalar_value=None):
        self._one = one
        self._items = items or []
        self._scalar_value = scalar_value

    def scalar_one_or_none(self):
        return self._one

    def scalar(self):
        return self._scalar_value

    def scalars(self):
        return self

    def all(self):
        return list(self._items)


class FakeDB:
    async def connection(self):
        class UnmigratedConnection:
            async def run_sync(self, _operation):
                return False
        return UnmigratedConnection()

    def __init__(self, offer=None, items=None):
        self.added = []
        self.offer = offer
        self.items = items or ([] if offer is None else [offer])
        self.statements = []

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid4()
            if getattr(item, "created_at", None) is None:
                item.created_at = datetime(2026, 7, 17, 10, 0)
            if getattr(item, "updated_at", None) is None:
                item.updated_at = datetime(2026, 7, 17, 10, 0)

    async def refresh(self, item):
        return None

    async def execute(self, statement):
        self.statements.append(statement)
        sql = str(statement).lower()
        if "count" in sql:
            return FakeResult(scalar_value=len(self.items))
        if self.offer is not None:
            return FakeResult(one=self.offer, items=self.items)
        return FakeResult(items=self.items)


def _contractor(user_id=None):
    return {"id": user_id or uuid4(), "roleCode": "CONTRACTOR"}


def _admin(user_id=None):
    return {"id": user_id or uuid4(), "roleCode": "PLATFORM_ADMIN"}


def _customer(user_id=None):
    return {"id": user_id or uuid4(), "roleCode": "CUSTOMER"}


def _fixed_payload(**overrides):
    data = {
        "work_code": RANGE_WORK.work_code,
        "region": "Краснодарский край",
        "pricing_mode": "fixed",
        "pricing_unit": RANGE_WORK.allowed_units[0],
        "currency": "RUB",
        "fixed_amount": Decimal("1500.00"),
        "status": "draft",
    }
    data.update(overrides)
    return ProviderWorkCostOfferPayload(**data)


def _range_payload(**overrides):
    data = {
        "work_code": RANGE_WORK.work_code,
        "region": "Краснодарский край",
        "pricing_mode": "range",
        "pricing_unit": RANGE_WORK.allowed_units[0],
        "currency": "RUB",
        "minimum_amount": Decimal("1000.00"),
        "maximum_amount": Decimal("1800.00"),
        "status": "active",
    }
    data.update(overrides)
    return ProviderWorkCostOfferPayload(**data)


def _offer(owner_user_id):
    return ProviderWorkCostOffer(
        id=uuid4(),
        work_code=RANGE_WORK.work_code,
        owner_user_id=owner_user_id,
        region="Краснодарский край",
        pricing_mode="fixed",
        fixed_amount=Decimal("1500.00"),
        currency="RUB",
        pricing_unit=RANGE_WORK.allowed_units[0],
        status="active",
        created_at=datetime(2026, 7, 17, 10, 0),
        updated_at=datetime(2026, 7, 17, 10, 0),
    )


def test_validate_fixed_and_range_contracts_use_work_catalog():
    fixed = validate_provider_work_cost_payload(_fixed_payload())
    ranged = validate_provider_work_cost_payload(_range_payload())

    assert fixed.work_code == RANGE_WORK.work_code
    assert fixed.fixed_amount == Decimal("1500.00")
    assert fixed.minimum_amount is None
    assert ranged.minimum_amount == Decimal("1000.00")
    assert ranged.maximum_amount == Decimal("1800.00")

    with pytest.raises(ValidationError):
        validate_provider_work_cost_payload(_fixed_payload(work_code="missing_work_code"))
    with pytest.raises(ValidationError):
        validate_provider_work_cost_payload(_fixed_payload(fixed_amount=Decimal("0")))
    with pytest.raises(ValidationError):
        validate_provider_work_cost_payload(_range_payload(minimum_amount=Decimal("2000"), maximum_amount=Decimal("1000")))
    with pytest.raises(ValidationError):
        validate_provider_work_cost_payload(_fixed_payload(pricing_unit="unknown_unit"))


@pytest.mark.asyncio
async def test_create_assigns_owner_server_side_and_does_not_create_material_price_entities():
    user_id = uuid4()
    db = FakeDB()

    offer = await create_provider_work_cost_offer(db, _fixed_payload(), _contractor(user_id))

    assert offer.owner_user_id == user_id
    assert offer.created_by == user_id
    assert offer.updated_by == user_id
    assert offer in db.added
    assert not any(isinstance(item, (Material, CatalogProduct, PriceHistory, MaterialMatchCandidate)) for item in db.added)
    assert not hasattr(offer, "material_id")
    assert not hasattr(offer, "catalog_product_id")
    assert not hasattr(offer, "source_task_id")


@pytest.mark.asyncio
async def test_ordinary_user_cannot_create_work_cost_offer():
    with pytest.raises(ForbiddenError):
        await create_provider_work_cost_offer(FakeDB(), _fixed_payload(), _customer())


@pytest.mark.asyncio
async def test_owner_can_update_own_offer_and_cannot_update_foreign_offer():
    owner_id = uuid4()
    offer = _offer(owner_id)

    updated = await update_provider_work_cost_offer(
        FakeDB(offer=offer),
        offer.id,
        _range_payload(),
        _contractor(owner_id),
    )
    assert updated.pricing_mode == "range"
    assert updated.fixed_amount is None
    assert updated.minimum_amount == Decimal("1000.00")

    with pytest.raises(ForbiddenError):
        await update_provider_work_cost_offer(
            FakeDB(offer=offer),
            offer.id,
            _fixed_payload(),
            _contractor(uuid4()),
        )


@pytest.mark.asyncio
async def test_deactivate_archives_without_physical_delete():
    owner_id = uuid4()
    offer = _offer(owner_id)
    db = FakeDB(offer=offer)

    result = await deactivate_provider_work_cost_offer(db, offer.id, _contractor(owner_id))

    assert result.status == "inactive"
    assert offer in db.added


def test_list_permissions_scope_admin_and_owner():
    owner_id = uuid4()
    owner_query = service._apply_list_permissions(
        service.select(ProviderWorkCostOffer),
        _contractor(owner_id),
        owner_user_id=None,
    )
    admin_query = service._apply_list_permissions(
        service.select(ProviderWorkCostOffer),
        _admin(),
        owner_user_id=owner_id,
    )

    assert "provider_work_cost_offers.owner_user_id" in str(owner_query.whereclause)
    assert "provider_work_cost_offers.owner_user_id" in str(admin_query.whereclause)
    with pytest.raises(ForbiddenError):
        service._apply_list_permissions(service.select(ProviderWorkCostOffer), _customer(), owner_user_id=None)


@pytest.mark.asyncio
async def test_work_cost_read_queries_eager_load_owner_for_async_serialization():
    owner_id = uuid4()
    offer = _offer(owner_id)

    list_db = FakeDB(offer=offer)
    await service.list_provider_work_cost_offers(list_db, _admin())
    list_query = list_db.statements[-1]

    get_db = FakeDB(offer=offer)
    await service.get_provider_work_cost_offer(get_db, offer.id, _admin())
    get_query = get_db.statements[-1]

    assert "ProviderWorkCostOffer.owner" in str(list_query._with_options[0].path)
    assert "ProviderWorkCostOffer.owner" in str(get_query._with_options[0].path)


def test_read_dto_enriches_from_work_catalog_and_hides_raw_internals():
    offer = _offer(uuid4())
    payload = provider_work_cost_offer_to_dict(offer)

    assert payload["workName"] == RANGE_WORK.work_name
    assert payload["workGroup"] == RANGE_WORK.work_group
    assert "materialId" not in payload
    assert "catalogProductId" not in payload
    assert "sourceTaskId" not in payload
    assert "rawPayload" not in payload


def test_api_schema_does_not_accept_owner_or_material_fields():
    data = ProviderWorkCostOfferCreate(
        workCode=RANGE_WORK.work_code,
        region="Краснодарский край",
        pricingMode="fixed",
        pricingUnit=RANGE_WORK.allowed_units[0],
        fixedAmount=Decimal("1500.00"),
        ownerUserId=str(uuid4()),
        materialId=str(uuid4()),
        analyzerResultId="analyzer-1",
    )

    dumped = data.model_dump()
    assert "ownerUserId" not in dumped
    assert "materialId" not in dumped
    assert "analyzerResultId" not in dumped


@pytest.mark.asyncio
async def test_api_create_passes_current_user_to_service_without_owner_spoofing(monkeypatch):
    captured = {}
    user = SimpleNamespace(id=uuid4(), roleCode="CONTRACTOR")
    created_offer = _offer(user.id)

    async def fake_create(db, payload, current_user):
        captured["payload"] = payload
        captured["user"] = current_user
        return created_offer

    monkeypatch.setattr(work_cost_api, "create_provider_work_cost_offer", fake_create)

    result = await work_cost_api.create_work_cost_offer(
        ProviderWorkCostOfferCreate(
            workCode=RANGE_WORK.work_code,
            region="Краснодарский край",
            pricingMode="fixed",
            pricingUnit=RANGE_WORK.allowed_units[0],
            fixedAmount=Decimal("1500.00"),
        ),
        FakeDB(),
        user,
    )

    assert captured["user"] is user
    assert captured["payload"].work_code == RANGE_WORK.work_code
    assert result["ownerUserId"] == str(user.id)
