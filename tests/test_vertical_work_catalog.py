import os
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.models.enums import MaterialStatus, SupplierStatus, UnitType
from app.models.material import Material
from app.models.supplier import Supplier
from app.models.supplier_price import SupplierPrice
from app.models.unit import Unit

from app.api.deps import get_current_user
from app.api.v1.vertical_work_catalog import router
from app.config import settings
from app.database import engine as configured_engine, get_db
from app.models.module1_work_item import WorkCatalogItem
from app.models.user import User
from app.services.module1_work_catalog import get_work_catalog_registry


@pytest.mark.asyncio
async def test_manual_work_and_price_forms_on_restored_qa(monkeypatch):
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    monkeypatch.setattr(settings, "VERTICAL_CALCULATION_PREVIEW_ENABLED", True)
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
                owner = await db.scalar(select(User.id).limit(1))
                user = SimpleNamespace(id=owner, role="ADMIN")
                app = FastAPI()
                app.include_router(router, prefix="/api/v1")
                app.dependency_overrides[get_current_user] = lambda: user
                app.dependency_overrides[get_db] = lambda: db
                name = "QA work " + uuid.uuid4().hex
                group = get_work_catalog_registry().groups[0]
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    assert (await client.get("/api/v1/admin/vertical-m1/works")).status_code == 200
                    created = await client.post("/api/v1/admin/vertical-m1/works/save", data={
                        "name": name, "work_group": group.work_group, "unit": "m3"})
                    assert created.status_code == 303 and "error=" not in created.headers["location"]
                    work = await db.scalar(select(WorkCatalogItem).where(WorkCatalogItem.work_name == name))
                    assert work is not None
                    card = await client.get(created.headers["location"])
                    assert card.status_code == 200 and name in card.text
                    price_url = f"/api/v1/admin/vertical-m1/prices/work/{work.work_code}"
                    response = await client.post(price_url, data={"region": "region", "terms": "terms", "amount": "1500"})
                    assert response.status_code == 303 and "error=" not in response.headers["location"]
                    price = await client.get(response.headers["location"])
                    assert price.status_code == 200 and "1500" in price.text
            await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_material_offer_forms_average_and_withdraw_on_restored_qa(monkeypatch):
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    monkeypatch.setattr(settings, "VERTICAL_CALCULATION_PREVIEW_ENABLED", True)
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
                owner = await db.scalar(select(User.id).limit(1))
                user = SimpleNamespace(id=owner, role="ADMIN")
                unit = await db.scalar(select(Unit).where(Unit.abbreviation.in_(["m3", "м³", "м3"])).limit(1))
                if unit is None:
                    unit = Unit(id=uuid.uuid4(), name="QA cubic metre", abbreviation="m3", unit_type=UnitType.VOLUME)
                    db.add(unit)
                    await db.flush()
                material = Material(id=uuid.uuid4(), canonical_name="QA " + uuid.uuid4().hex,
                                    base_unit_id=unit.id, status=MaterialStatus.DRAFT)
                suppliers = [Supplier(id=uuid.uuid4(), name="QA supplier " + uuid.uuid4().hex,
                                      status=SupplierStatus.POTENTIAL) for _ in range(2)]
                db.add_all([material, *suppliers])
                await db.flush()
                app = FastAPI()
                app.include_router(router, prefix="/api/v1")
                app.dependency_overrides[get_current_user] = lambda: user
                app.dependency_overrides[get_db] = lambda: db
                base = f"/api/v1/admin/vertical-m1/prices/material/{material.id}"
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    manual = await client.post(base, data={"region": "region", "terms": "terms", "amount": "1000"})
                    assert "error=" not in manual.headers["location"]
                    for supplier, amount in zip(suppliers, ("1200", "1400")):
                        response = await client.post(base + "/offers", data={"supplier_id": str(supplier.id),
                            "region": "region", "terms": "terms", "amount": amount, "confirmed": "on"})
                        assert "error=" not in response.headers["location"]
                    page = await client.get(base, params={"region": "region", "terms": "terms"})
                    assert page.status_code == 200 and "средняя по предложениям" in page.text and "1300" in page.text
                    offers = (await db.scalars(select(SupplierPrice).where(SupplierPrice.material_id == material.id))).all()
                    assert len(offers) == 2
                    for offer in offers:
                        response = await client.post(base + f"/offers/{offer.id}/withdraw",
                                                     data={"region": "region", "terms": "terms"})
                        assert "error=" not in response.headers["location"]
                    page = await client.get(base, params={"region": "region", "terms": "terms"})
                    assert "ручная резервная" in page.text and "1000" in page.text
            await transaction.rollback()
    finally:
        await engine.dispose()
