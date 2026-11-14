from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.services.module1_work_catalog import get_work_catalog_registry
from app.services.module1_work_catalog_store import WorkCatalogWrite


def test_work_card_requires_approved_units_and_group():
    registry = get_work_catalog_registry()
    group = registry.groups[0]
    with pytest.raises(ValueError, match="units"):
        WorkCatalogWrite(work_code="new_work", work_group=group.work_group, work_category=group.work_category,
                         work_name="Работа", default_unit="m3", allowed_units=["piece"])


@pytest.mark.asyncio
async def test_empty_migrated_catalog_keeps_seed_but_archived_cards_stay_hidden():
    from types import SimpleNamespace
    from app.services.module1_work_catalog_store import load_work_catalog

    class Connection:
        async def run_sync(self, _callback):
            return True

    class Database:
        def __init__(self, items):
            self.items = items

        async def connection(self):
            return Connection()

        async def scalars(self, _statement):
            return SimpleNamespace(all=lambda: self.items)

    assert len(await load_work_catalog(Database([]))) == len(get_work_catalog_registry().works)
    assert await load_work_catalog(Database([SimpleNamespace(status="ARCHIVED")])) == ()
    active = SimpleNamespace(status="ACTIVE")
    assert await load_work_catalog(Database([active, SimpleNamespace(status="ARCHIVED")])) == (active,)


@pytest.mark.asyncio
async def test_work_catalog_and_manual_price_history_on_restored_qa():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.database import engine as configured_engine
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.models.module1_work_item import ManualCalculationPriceRevision, WorkCatalogItemRevision
    from app.services.module1_calculation_price import PriceCandidate
    from app.services.module1_manual_calculation_price import append_manual_price, quote_calculation_price
    from app.services.module1_material_ui_write import _has_vertical_unit_references
    from app.services.module1_work_catalog_store import save_work_item, seed_existing_work_catalog
    from app.services.module1_work_catalog_store import load_work_catalog
    from app.services.module1_provider_work_cost_offers import (
        ProviderWorkCostOfferPayload, create_provider_work_cost_offer, provider_work_cost_offer_to_dict,
    )
    from app.services.module1_work_cost_export_contract import build_work_cost_offer_export_package
    from app.models.user import User
    from types import SimpleNamespace

    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            baseline = get_work_catalog_registry()
            seeded = await seed_existing_work_catalog(db)
            assert seeded["created"] + seeded["reused"] == len(baseline.works)
            repeated = await seed_existing_work_catalog(db)
            assert repeated["created"] == 0 and repeated["reused"] == len(baseline.works)
            expected_codes = [item.work_code for item in baseline.works]
            expected_set = set(expected_codes)
            assert [item.work_code for item in await load_work_catalog(db) if item.work_code in expected_set] == expected_codes

            group = baseline.groups[0]
            code = "qa_work_" + uuid.uuid4().hex
            payload = WorkCatalogWrite(work_code=code, work_group=group.work_group,
                                       work_category=group.work_category, work_name="QA работа",
                                       default_unit="m3", allowed_units=["m3"])
            work = await save_work_item(db, payload, actor_id=None)
            assert work.work_code == code and work.status == "DRAFT"
            owner = await db.scalar(select(User.id).limit(1))
            user = SimpleNamespace(id=owner, role="ADMIN")
            offer = await create_provider_work_cost_offer(db, ProviderWorkCostOfferPayload(
                work_code=code, region="QA", pricing_mode="fixed", pricing_unit="m3",
                fixed_amount=Decimal("123"), status="active"), user)
            catalog = {item.work_code: item for item in await load_work_catalog(db)}
            assert provider_work_cost_offer_to_dict(offer, user, work_by_code=catalog)["workName"] == payload.work_name
            exported = await build_work_cost_offer_export_package(db, user, work_code=code)
            assert exported.record_count == 1 and exported.records[0].work_code == code
            work = await save_work_item(db, payload.model_copy(update={"description": "QA описание"}),
                                        actor_id=None, expected_version=1)
            assert work.version == 2
            revisions = (await db.scalars(select(WorkCatalogItemRevision).where(
                WorkCatalogItemRevision.work_code == code))).all()
            assert len(revisions) == 2

            today = date(2026, 11, 13)
            await append_manual_price(db, work_code=code, amount=Decimal("1000"), region="Краснодарский край",
                                      terms="без доставки", effective_from=today, actor_id=None)
            with pytest.raises(ValueError, match="unit or conditions cannot change"):
                await save_work_item(db, payload.model_copy(update={"conditions": {"scope": "changed"}}),
                                     actor_id=None, expected_version=2)
            offer = lambda ident, amount: PriceCandidate(ident, Decimal(amount), "m3", "RUB", "Краснодарский край",
                                                         "без доставки", "active", True)
            quote = await quote_calculation_price(db, work_code=code, region="Краснодарский край", terms="без доставки",
                                                  as_of=today, offers=[offer("a", "1200"), offer("b", "1400")])
            assert quote.source == "AVERAGE" and quote.amount == Decimal("1300")
            fallback = await quote_calculation_price(db, work_code=code, region="Краснодарский край",
                                                     terms="без доставки", as_of=today, offers=[])
            assert fallback.source == "MANUAL" and fallback.amount == Decimal("1000")
            await append_manual_price(db, work_code=code, amount=None, region="Краснодарский край",
                                      terms="без доставки", effective_from=today, actor_id=None)
            missing = await quote_calculation_price(db, work_code=code, region="Краснодарский край",
                                                    terms="без доставки", as_of=today, offers=[])
            assert missing.source == "NO_PRICE" and missing.amount is None
            assert len((await db.scalars(select(ManualCalculationPriceRevision).where(
                ManualCalculationPriceRevision.work_code == code))).all()) == 2

            material = await db.scalar(select(Material).where(
                Material.status == MaterialStatus.DRAFT, Material.base_unit_id.is_not(None)).limit(1))
            assert material is not None
            await append_manual_price(db, material_id=material.id, amount=Decimal("8000"), region="Краснодарский край",
                                      terms="без доставки", effective_from=today, actor_id=None)
            material_quote = await quote_calculation_price(db, material_id=material.id, region="Краснодарский край",
                                                            terms="без доставки", as_of=today, offers=[])
            assert material_quote.source == "MANUAL" and material_quote.amount == Decimal("8000")
            assert await _has_vertical_unit_references(db, material.id)
            await db.rollback()
    finally:
        await engine.dispose()
