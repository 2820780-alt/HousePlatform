from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.models.enums import CatalogProductStatus, SupplierStatus
from app.models.user import User
from app.services.module1_manual_calculation_price import append_manual_price
from app.services.module1_offer_qualification import (
    _material_offer_context_valid, offer_fingerprint, quote_current_offers, review_offer,
)
from app.services.module1_work_catalog import get_work_catalog_registry
from app.services.module1_work_catalog_store import WorkCatalogWrite, save_work_item


def test_offer_fingerprint_tracks_identity_not_price():
    offer = ProviderWorkCostOffer(id=uuid.uuid4(), owner_user_id=uuid.uuid4(), work_code="qa_work",
                                  region="region", status="active", pricing_mode="fixed", pricing_unit="m3",
                                  currency="RUB", fixed_amount=Decimal("100"))
    original = offer_fingerprint(offer)
    offer.fixed_amount = Decimal("120")
    assert offer_fingerprint(offer) == original
    offer.pricing_unit = "m2"
    assert offer_fingerprint(offer) != original


def test_material_offer_rejects_uncomparable_or_stale_catalog_terms():
    material_id = uuid.uuid4()
    product_id = uuid.uuid4()
    supplier = SimpleNamespace(status=SupplierStatus.VERIFIED)
    offer = SimpleNamespace(material_id=material_id, catalog_product_id=product_id, min_order_quantity=None)
    product = SimpleNamespace(material_id=material_id, status=CatalogProductStatus.ACTIVE)
    assert _material_offer_context_valid(offer, supplier, product)
    offer.min_order_quantity = Decimal("10")
    assert not _material_offer_context_valid(offer, supplier, product)
    offer.min_order_quantity = None
    product.material_id = uuid.uuid4()
    assert not _material_offer_context_valid(offer, supplier, product)
    product.material_id = material_id
    product.status = CatalogProductStatus.UNAVAILABLE
    assert not _material_offer_context_valid(offer, supplier, product)
    assert not _material_offer_context_valid(offer, supplier, None)
    offer.catalog_product_id = None
    assert _material_offer_context_valid(offer, supplier, None)
    supplier.status = SupplierStatus.BLOCKED
    assert not _material_offer_context_valid(offer, supplier, None)


@pytest.mark.asyncio
async def test_reviewed_offers_are_resolved_from_restored_qa_and_fallback_safely():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner_id = await db.scalar(select(User.id).limit(1))
            assert owner_id is not None
            user = SimpleNamespace(id=owner_id, role="ADMIN")
            group = get_work_catalog_registry().groups[0]
            code = "qa_work_" + uuid.uuid4().hex
            await save_work_item(db, WorkCatalogWrite(work_code=code, work_group=group.work_group,
                                 work_category=group.work_category, work_name="QA temporary work",
                                 default_unit="m3", allowed_units=["m3"]), actor_id=None)
            today = date.today()
            await append_manual_price(db, work_code=code, amount=Decimal("1000"), region="region",
                                      terms="terms", effective_from=today, actor_id=None)
            offers = [ProviderWorkCostOffer(id=uuid.uuid4(), owner_user_id=owner_id, work_code=code,
                        region="region", status="active", pricing_mode="fixed", pricing_unit="m3",
                        currency="RUB", fixed_amount=Decimal(amount)) for amount in ("1200", "1400")]
            db.add_all(offers)
            await db.flush()
            kwargs = dict(work_code=code, region="region", terms="terms", as_of=today, actor=user)
            assert (await quote_current_offers(db, **kwargs)).amount == Decimal("1000")
            for offer in offers:
                await review_offer(db, work_offer_id=offer.id, terms="terms", status="CONFIRMED", actor=user)
            quote = await quote_current_offers(db, **kwargs)
            assert quote.source == "AVERAGE" and quote.amount == Decimal("1300")
            offers[0].fixed_amount = Decimal("1600")
            await db.flush()
            assert (await quote_current_offers(db, **kwargs)).amount == Decimal("1500")
            offers[0].comment = "terms changed"
            await db.flush()
            assert (await quote_current_offers(db, **kwargs)).amount == Decimal("1400")
            await review_offer(db, work_offer_id=offers[1].id, terms="terms", status="WITHDRAWN", actor=user)
            fallback = await quote_current_offers(db, **kwargs)
            assert fallback.source == "MANUAL" and fallback.amount == Decimal("1000")
            with pytest.raises(ValueError, match="historical"):
                await quote_current_offers(db, **{**kwargs, "as_of": today - timedelta(days=1)})
            await db.rollback()
    finally:
        await engine.dispose()
