from __future__ import annotations

import os
import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.enums import MaterialStatus, UnitType
from app.models.material import Material
from app.models.module2_technology import Technology
from app.models.unit import Unit
from app.models.user import User
from app.services.module1_manual_calculation_price import append_manual_price
from app.services.module1_work_catalog import get_work_catalog_registry
from app.services.module1_work_catalog_store import WorkCatalogWrite, save_work_item
from app.services.module2_calculation_blocks import add_block
from app.services.module2_calculation_presets import rectangular_volume_block
from app.services.module2_calculation_composer import ComposerStep, compose_block
from app.services.module5_estimate_snapshots import create_estimate_preview, read_estimate_preview
from app.services.module7_strip_geometry import create_object, save_strip_geometry


@pytest.mark.asyncio
async def test_persisted_previews_capture_prices_and_geometry_on_restored_qa(monkeypatch):
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = await db.scalar(select(User.id).limit(1))
            assert owner
            user = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                {"moduleCode": module, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
                for module in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                               "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE")
            ])
            unit = await db.scalar(select(Unit).where(Unit.abbreviation.in_(["m3", "м³", "м3"])).limit(1))
            if unit is None:
                unit = Unit(id=uuid.uuid4(), name="QA cubic metre", abbreviation="m3", unit_type=UnitType.VOLUME)
                db.add(unit)
                await db.flush()
            material = Material(id=uuid.uuid4(), canonical_name="QA material " + uuid.uuid4().hex,
                                base_unit_id=unit.id, status=MaterialStatus.DRAFT)
            tech = Technology(id=uuid.uuid4(), technology_code="QA_STRIP_" + uuid.uuid4().hex,
                              revision=1, name="QA strip", status="DRAFT")
            db.add_all([material, tech])
            await db.flush()
            group = get_work_catalog_registry().groups[0]
            code = "qa_work_" + uuid.uuid4().hex
            await save_work_item(db, WorkCatalogWrite(work_code=code, work_group=group.work_group,
                                 work_category=group.work_category, work_name="QA temporary work",
                                 default_unit="m3", allowed_units=["m3"]), actor_id=owner)
            for resource, amount in (({"material_id": material.id}, "1000"), ({"work_code": code}, "500")):
                await append_manual_price(db, **resource, amount=Decimal(amount), region="region", terms="terms",
                                          effective_from=date.today(), actor_id=owner)
            block = replace(rectangular_volume_block(), material_id=str(material.id), work_code=code)
            await add_block(db, technology_id=tech.id, block=block, actor=user, actor_id=owner)
            obj = await create_object(db, actor=user, name="QA object")
            first = await save_strip_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                                              length_m="10", width_m="0.4", height_m="1", expected_version=0)
            keys = {(block.id, "MATERIAL"): "concrete", (block.id, "WORK"): "placement"}
            snap = await create_estimate_preview(db, actor=user, geometry_revision_id=first.id,
                                                 region="region", terms="terms", accounting_keys=keys)
            assert snap.payload["result"]["known_total"] == "6000.00"
            assert snap.payload["result"]["complete"] is True
            second = await save_strip_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                                               length_m="10", width_m="0.5", height_m="1", expected_version=1)
            recalculated = await create_estimate_preview(db, actor=user, geometry_revision_id=second.id,
                                                         region="region", terms="terms", accounting_keys=keys)
            assert recalculated.payload["result"]["known_total"] == "7500.00"
            assert (await read_estimate_preview(db, actor=user, snapshot_id=snap.id)).payload["result"]["known_total"] == "6000.00"
            import httpx
            from fastapi import FastAPI
            from app.api.deps import get_current_user
            from app.api.v1.vertical_calculation_preview import router
            from app.config import settings
            from app.database import get_db
            monkeypatch.setattr(settings, "VERTICAL_CALCULATION_PREVIEW_ENABLED", True)
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_db] = lambda: db
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(f"/api/v1/admin/vertical-preview/{tech.id}?snapshot={snap.id}")
                assert response.status_code == 200
                assert "Материалы" in response.text and "Работы" in response.text and "6000.00" in response.text
                monkeypatch.setattr(db, "commit", db.flush)
                response = await client.post(f"/api/v1/admin/vertical-preview/{tech.id}", data={
                    "name": "QA via form", "length_m": "10", "width_m": "0,5", "height_m": "1",
                    "region": "region", "terms": "terms", f"scope.{block.id}.MATERIAL": "concrete",
                    f"scope.{block.id}.WORK": "placement",
                })
                assert response.status_code == 303 and "error=" not in response.headers["location"]
                calculated = await client.get(response.headers["location"])
                assert calculated.status_code == 200 and "7500.00" in calculated.text
                composed = compose_block("QA area", (
                    ComposerStep("Length", "INPUT", "m", source="geometry.length"),
                    ComposerStep("Width parameter", "INPUT", "m", source="PARAMETER"),
                    ComposerStep("Area", "MULTIPLY", "m2", (1, 2)),
                ), material_step=3, work_step=None)
                await add_block(db, technology_id=tech.id, block=composed, actor=user, actor_id=owner)
                parameter_key = composed.parameters[0].input_key
                with pytest.raises(ValueError, match="unknown"):
                    await create_estimate_preview(db, actor=user, geometry_revision_id=first.id,
                        region="region", terms="terms", accounting_keys={**keys, (composed.id, "MATERIAL"): "surface"},
                        parameter_values={(block.id, "geometry.width"): "20"})
                response = await client.post(f"/api/v1/admin/vertical-preview/{tech.id}", data={
                    "name": "QA with parameter", "length_m": "10", "width_m": "0,5", "height_m": "1",
                    "region": "region", "terms": "terms", f"scope.{block.id}.MATERIAL": "concrete",
                    f"scope.{block.id}.WORK": "placement", f"scope.{composed.id}.MATERIAL": "surface",
                    f"parameter.{composed.id}.{parameter_key}": "0,4",
                })
                assert response.status_code == 303 and "error=" not in response.headers["location"]
                calculated = await client.get(response.headers["location"])
                assert calculated.status_code == 200 and 'value="0.4"' in calculated.text
            with pytest.raises(ValueError, match="not found"):
                await read_estimate_preview(db, actor=SimpleNamespace(id=uuid.uuid4(), role="ADMIN",
                                                                       moduleAccessRules=user.moduleAccessRules),
                                            snapshot_id=snap.id)
            await db.rollback()
    finally:
        await engine.dispose()
