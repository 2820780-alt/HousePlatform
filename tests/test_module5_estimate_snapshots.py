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
from app.models.material_attribute import MaterialAttribute
from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_technology import Technology
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.unit import Unit
from app.models.user import User
from app.services.module1_manual_calculation_price import append_manual_price
from app.services.module1_work_catalog import get_work_catalog_registry
from app.services.module1_work_catalog_store import WorkCatalogWrite, save_work_item
from app.services.module2_calculation_blocks import add_block
from app.services.module2_calculation_presets import rectangular_volume_block, slab_net_area_volume_block
from app.services.module2_calculation_composer import ComposerStep, compose_block
from app.services.module5_estimate_snapshots import create_estimate_preview, read_estimate_preview
from app.services.module7_strip_geometry import create_object, save_strip_geometry
from app.services.module7_foundation_geometry import save_foundation_geometry


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
            characteristic = MaterialAttribute(material_id=material.id, attribute_name="concrete_class", attribute_value="B25")
            internal = MaterialAttribute(material_id=material.id, attribute_name="registry_code", attribute_value="internal-only")
            db.add_all([characteristic, internal])
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
            no_price = await create_estimate_preview(db, actor=user, geometry_revision_id=first.id,
                region="qa-without-offers", terms="qa", accounting_keys=keys)
            assert not no_price.payload["result"]["complete"]
            no_price_material = no_price.payload["result"]["materials"][0]
            assert no_price_material["unit_price"] is None and "NO_PRICE" in no_price_material["issues"]
            assert "TECHNOLOGY_ROLE_INVALID" not in no_price_material["issues"]
            material.status = MaterialStatus.ARCHIVED
            await db.flush()
            archived = await create_estimate_preview(db, actor=user, geometry_revision_id=first.id,
                region="region", terms="terms", accounting_keys=keys)
            archived_material = archived.payload["result"]["materials"][0]
            assert "TECHNOLOGY_ROLE_INVALID" in archived_material["issues"]
            assert Decimal(archived_material["amount_for_total"]) == 0
            material.status = MaterialStatus.DRAFT
            await db.flush()
            catalog_work = await db.get(WorkCatalogItem, code)
            old_work_status = catalog_work.status
            catalog_work.status = "ARCHIVED"
            await db.flush()
            archived_work = await create_estimate_preview(db, actor=user, geometry_revision_id=first.id,
                region="region", terms="terms", accounting_keys=keys)
            work_line = archived_work.payload["result"]["works"][0]
            assert "TECHNOLOGY_ROLE_INVALID" in work_line["issues"]
            assert Decimal(work_line["amount_for_total"]) == 0
            catalog_work.status = old_work_status
            await db.flush()
            package = snap.payload["calculation_package_v2"]
            package_hash = snap.payload["calculation_package_sha256"]
            assert package["contract_version"] == "2" and package["technology_id"] == str(tech.id)
            assert package["technology_revision"] == tech.revision
            assert package["blocks"][0]["material_id"] == str(material.id)
            assert package["blocks"][0]["work_code"] == code
            assert snap.payload["result"]["complete"] is True
            original_name = material.canonical_name
            assert snap.payload["resource_names"][f"MATERIAL:{material.id}"] == original_name
            assert snap.payload["resource_names"][f"WORK:{code}"] == "QA temporary work"
            assert snap.payload["resource_characteristics"][str(material.id)] == [
                {"label": "Класс бетона", "value": "B25", "unit": "", "unit_inferred": False}]
            second = await save_strip_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                                               length_m="10", width_m="0.5", height_m="1", expected_version=1)
            recalculated = await create_estimate_preview(db, actor=user, geometry_revision_id=second.id,
                                                         region="region", terms="terms", accounting_keys=keys)
            assert recalculated.payload["result"]["known_total"] == "7500.00"
            assert (await read_estimate_preview(db, actor=user, snapshot_id=snap.id)).payload["result"]["known_total"] == "6000.00"
            stored_block = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
            stored_block.name = "QA revised block"
            stored_block.version += 1
            await db.flush()
            revised_package = await create_estimate_preview(db, actor=user, geometry_revision_id=second.id,
                                                             region="region", terms="terms", accounting_keys=keys)
            assert revised_package.payload["calculation_package_sha256"] != package_hash
            await db.refresh(snap)
            assert snap.payload["calculation_package_v2"] == package
            assert snap.payload["calculation_package_sha256"] == package_hash
            material.canonical_name = "QA renamed material"
            characteristic.attribute_value = "B30"
            work = await db.get(WorkCatalogItem, code)
            work.work_name = "QA renamed work"
            await db.flush()
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
                assert original_name in response.text and "QA temporary work" in response.text
                assert "QA renamed material" not in response.text and "QA renamed work" not in response.text
                assert "B25" in response.text and "B30" not in response.text and "internal-only" not in response.text
                monkeypatch.setattr(db, "commit", db.flush)
                form = {
                    "name": "QA via form", "length_m": "10", "width_m": "0,5", "height_m": "1",
                    "region": "region", "terms": "terms", f"scope.{block.id}.MATERIAL": "concrete",
                    f"scope.{block.id}.WORK": "placement", "idempotency_key": str(uuid.uuid4()),
                }
                response = await client.post(f"/api/v1/admin/vertical-preview/{tech.id}", data=form)
                assert response.status_code == 303 and "error=" not in response.headers["location"]
                repeated = await client.post(f"/api/v1/admin/vertical-preview/{tech.id}", data=form)
                assert repeated.headers["location"] == response.headers["location"]
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
                # The request rollback also rolls back the test's uncommitted fixture data.
                changed = await client.post(f"/api/v1/admin/vertical-preview/{tech.id}",
                                            data={**form, "width_m": "0,6"})
                assert "error=" in changed.headers["location"]
            await db.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_foundation_geometry_snapshot_and_recalculation_on_restored_qa(monkeypatch):
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = await db.scalar(select(User.id).limit(1))
            user = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                {"moduleCode": module, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
                for module in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                               "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE")])
            tech = Technology(id=uuid.uuid4(), technology_code="FND_SLAB_RIBBED_RC", revision=1000000000,
                              name="QA ribbed slab", status="DRAFT")
            unit = await db.scalar(select(Unit).where(Unit.abbreviation.in_(["m3", "м³", "м3"])).limit(1))
            material = Material(id=uuid.uuid4(), canonical_name="QA slab " + uuid.uuid4().hex,
                                base_unit_id=unit.id, status=MaterialStatus.DRAFT)
            db.add_all([material, tech])
            await db.flush()
            characteristic = MaterialAttribute(material_id=material.id, attribute_name="concrete_class", attribute_value="B25")
            db.add(characteristic)
            await db.flush()
            block = replace(slab_net_area_volume_block(), material_id=str(material.id), work_output_id=None)
            await add_block(db, technology_id=tech.id, block=block, actor=user, actor_id=owner)
            obj = await create_object(db, actor=user, name="QA slab M5")
            values = {"geometry.net_area": "50", "geometry.slab_thickness": "0.2",
                      "geometry.rib_length": "20", "geometry.rib_width": "0.4",
                      "geometry.rib_height": "0.3", "geometry.rib_overlap_volume": "0"}
            first = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values=values, project_values={}, expected_version=0)
            keys = {(block.id, "MATERIAL"): "slab"}
            snapshot = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=first.id,
                region="qa", terms="qa", accounting_keys=keys)
            assert snapshot.geometry_revision_id is None and snapshot.foundation_geometry_revision_id == first.id
            assert snapshot.payload["result"]["materials"][0]["quantity"] == "10.0"
            original_name = material.canonical_name
            assert snapshot.payload["resource_names"][f"MATERIAL:{material.id}"] == original_name
            assert not snapshot.payload["result"]["complete"]
            assert snapshot.payload["missing_required_roles"]
            second = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={**values, "geometry.net_area": "70"}, project_values={}, expected_version=1)
            revised = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=second.id,
                region="qa", terms="qa", accounting_keys=keys)
            assert revised.payload["result"]["materials"][0]["quantity"] == "14.0"
            assert (await read_estimate_preview(db, actor=user, snapshot_id=snapshot.id)).payload[
                "result"]["materials"][0]["quantity"] == "10.0"
            with pytest.raises(ValueError, match="unknown"):
                await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=first.id,
                    region="qa", terms="qa", accounting_keys=keys,
                    parameter_values={(block.id, "technology.slab_thickness"): "5"})
            with pytest.raises(ValueError, match="exactly one"):
                await create_estimate_preview(db, actor=user, region="qa", terms="qa", accounting_keys=keys)
            with pytest.raises(ValueError, match="work selection is unavailable"):
                await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=first.id,
                    region="qa", terms="qa", accounting_keys=keys, selected_work_block_ids=frozenset())
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
            monkeypatch.setattr(db, "commit", db.flush)
            material.canonical_name = "QA renamed slab material"
            characteristic.attribute_value = "B30"
            await db.flush()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                legacy_new = await client.get(f"/api/v1/admin/vertical-preview/{tech.id}")
                assert legacy_new.status_code == 303 and "/module7/foundations/view?technology=" in legacy_new.headers["location"]
                legacy_post = await client.post(f"/api/v1/admin/vertical-preview/{tech.id}", data={})
                assert legacy_post.status_code == 400
                page = await client.get(f"/api/v1/admin/vertical-preview/foundation/{first.id}")
                assert page.status_code == 200 and "Геометрия" in page.text
                saved_page = await client.get(f"/api/v1/admin/vertical-preview/foundation/{first.id}?snapshot={snapshot.id}")
                assert saved_page.status_code == 200 and original_name in saved_page.text
                assert "QA renamed slab material" not in saved_page.text
                assert "B25" in saved_page.text and "B30" not in saved_page.text
                saved_payload = snapshot.payload
                snapshot.payload = {key: value for key, value in saved_payload.items() if key != "resource_names"}
                await db.flush()
                old_page = await client.get(f"/api/v1/admin/vertical-preview/foundation/{first.id}?snapshot={snapshot.id}")
                assert old_page.status_code == 200 and "QA renamed slab material" in old_page.text
                snapshot.payload = saved_payload
                await db.flush()
                form = {"region": "qa", "terms": "qa", "idempotency_key": str(uuid.uuid4())}
                result = await client.post(f"/api/v1/admin/vertical-preview/foundation/{first.id}", data=form)
                assert result.status_code == 303 and "snapshot=" in result.headers["location"]
                repeated = await client.post(f"/api/v1/admin/vertical-preview/foundation/{first.id}", data=form)
                assert repeated.headers["location"] == result.headers["location"]
                result_page = await client.get(result.headers["location"])
                assert result_page.status_code == 200 and "Смета неполная" in result_page.text
                assert "Нет цены" in result_page.text
                wrong_route = await client.get(f"/api/v1/admin/vertical-preview/{tech.id}?snapshot={snapshot.id}")
                assert wrong_route.status_code == 404
            await db.rollback()
    finally:
        await engine.dispose()
