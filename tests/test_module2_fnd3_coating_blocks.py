import os
import uuid
import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.user import User
from app.services.module2_fnd3_coating_blocks import TECHNOLOGY_CODE, _id, add_coating_blocks, add_coating_primer_work
from app.services.module2_calculation_blocks import add_block
from app.services.module2_calculation_graph import CalculationBlock, CalculationNode
from app.services.module2_fnd3_work_details import _resolve, add_foundation_work_details, candidates
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_coating_consumption_and_single_work_on_restored_qa():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = await db.scalar(select(User.id).limit(1))
            user = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                {"moduleCode": code, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
                for code in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                             "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE")])
            first = await add_coating_blocks(db, actor=user)
            second = await add_coating_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 2 and not first["edited"]
            assert second["reused"] == 2 and not second["edited"]
            await add_foundation_work_details(db)
            detail = await add_coating_primer_work(db, actor=user)
            repeated = await add_coating_primer_work(db, actor=user)
            assert detail["created"] + detail["reused"] == 1 and not detail["edited"]
            assert repeated["reused"] == 1 and not repeated["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA coating")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"geometry.area":"20"}, project_values={}, expected_version=0)
            primer, mastic = _id(tech.id, "primer", "block"), _id(tech.id, "mastic", "block")
            primer_work = _id(tech.id, "primer-work", "block")
            keys = {(primer,"MATERIAL"):"primer", (mastic,"MATERIAL"):"mastic", (mastic,"WORK"):"coating-work",
                    (primer_work,"WORK"):"primer-work"}
            missing = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, selected_work_block_ids=frozenset({mastic}))
            assert all(line["quantity"] is None for line in missing.payload["result"]["materials"])
            assert not missing.payload["result"]["complete"]
            calculated = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys,
                parameter_values={(primer,"primer.consumption"):"0.25", (mastic,"mastic.consumption"):"1.5"},
                selected_work_block_ids=frozenset({mastic}))
            materials = calculated.payload["result"]["materials"]
            work = calculated.payload["result"]["works"]
            assert any(line["unit"] == "liter" and line["quantity"] == "5.00" for line in materials)
            assert any(line["unit"] == "kg" and line["quantity"] == "30.0" for line in materials)
            assert len(work) == 1 and work[0]["unit"] == "m2" and work[0]["quantity"] == "20"
            assert "POTENTIAL_DOUBLE_COUNT" not in work[0]["issues"]
            assert not calculated.payload["result"]["complete"]
            await db.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_explicit_work_selection_preserves_materials_and_double_count_protection(monkeypatch):
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = await db.scalar(select(User.id).limit(1))
            user = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                {"moduleCode": code, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
                for code in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                             "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE")])
            await add_coating_blocks(db, actor=user)
            await add_foundation_work_details(db)
            primer_candidate = candidates()["FND-WK-035"]
            assert set(await _resolve(db, {"FND-WK-035": primer_candidate}, numbers={35})) == {"FND-WK-035"}
            await add_coating_primer_work(db, actor=user)
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            detail = SimpleNamespace(id=_id(tech.id, "primer-work", "block"))
            obj = await create_object(db, actor=user, name="QA work selection")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"geometry.area": "20"}, project_values={}, expected_version=0)
            primer, bundle = _id(tech.id, "primer", "block"), _id(tech.id, "mastic", "block")
            keys = {(primer, "MATERIAL"): "primer", (bundle, "MATERIAL"): "mastic",
                    (bundle, "WORK"): "bundle", (detail.id, "WORK"): "detail"}
            values = {(primer, "primer.consumption"): "0.25", (bundle, "mastic.consumption"): "1.5"}
            async def calculate(selection, confirmed=False):
                return await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                    region="qa", terms="qa", accounting_keys=keys, parameter_values=values,
                    selected_work_block_ids=selection, coating_work_scope_confirmed=confirmed)
            both = await calculate(frozenset({bundle, detail.id}))
            assert len(both.payload["result"]["works"]) == 2
            assert all("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in both.payload["result"]["works"])
            confirmed = await calculate(frozenset({bundle, detail.id}), confirmed=True)
            assert len(confirmed.payload["result"]["works"]) == 2
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in confirmed.payload["result"]["works"])
            assert confirmed.payload["coating_work_scope_confirmed"] is True
            detail_row = await db.get(TechnologyCalculationBlock, uuid.UUID(detail.id))
            original_definition = copy.deepcopy(detail_row.definition)
            altered = copy.deepcopy(original_definition)
            altered["parameters"][0]["label"] = "Изменённый параметр"
            detail_row.definition = altered
            await db.flush()
            changed_graph = await calculate(frozenset({bundle, detail.id}), confirmed=True)
            assert all("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in changed_graph.payload["result"]["works"])
            detail_row.definition = original_definition
            await db.flush()
            extra_node = CalculationNode(str(uuid.uuid4()), "INPUT", "m2", input_key="geometry.area")
            extra = CalculationBlock(id=str(uuid.uuid4()), name="QA дополнительная работа", nodes=(extra_node,),
                outputs=(extra_node.id,), work_code=detail_row.work_code, work_output_id=extra_node.id)
            extra_row = await add_block(db, technology_id=tech.id, block=extra, actor=user, actor_id=owner)
            keys[(extra.id, "WORK")] = "extra"
            with_extra = await calculate(frozenset({bundle, detail.id, extra.id}), confirmed=True)
            assert len(with_extra.payload["result"]["works"]) == 3
            assert all("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in with_extra.payload["result"]["works"])
            await db.delete(extra_row)
            await db.flush()
            for selected in (bundle, detail.id):
                snapshot = await calculate(frozenset({selected}))
                assert len(snapshot.payload["result"]["materials"]) == 2
                assert len(snapshot.payload["result"]["works"]) == 1
                assert snapshot.payload["result"]["works"][0]["binding"]["block_id"] == selected
                assert "POTENTIAL_DOUBLE_COUNT" not in snapshot.payload["result"]["works"][0]["issues"]
                assert snapshot.payload["selected_work_block_ids"] == [selected]
                assert not snapshot.payload["result"]["complete"]
            no_work = await calculate(frozenset())
            assert len(no_work.payload["result"]["materials"]) == 2
            assert not no_work.payload["result"]["works"] and "Не выбрана ни одна работа" in no_work.payload["missing_required_roles"]
            with pytest.raises(ValueError, match="unknown block"):
                await calculate(frozenset({str(uuid.uuid4())}))
            unbound_node = CalculationNode(str(uuid.uuid4()), "INPUT", "m2", input_key="geometry.area")
            unbound = CalculationBlock(id=str(uuid.uuid4()), name="QA работа не выбрана", nodes=(unbound_node,),
                outputs=(unbound_node.id,), work_output_id=unbound_node.id)
            unbound_row = await add_block(db, technology_id=tech.id, block=unbound, actor=user, actor_id=owner)
            keys[(unbound.id, "WORK")] = "unbound"
            with_unbound = await calculate(frozenset({bundle, unbound.id}))
            unresolved = next(line for line in with_unbound.payload["result"]["works"]
                              if line["binding"]["block_id"] == unbound.id)
            assert "WORK_UNRESOLVED" in unresolved["issues"] and not with_unbound.payload["result"]["complete"]
            explicitly_excluded = await calculate(frozenset({bundle}))
            assert all(line["binding"]["block_id"] != unbound.id for line in explicitly_excluded.payload["result"]["works"])
            await db.delete(unbound_row)
            await db.flush()
            import httpx
            from fastapi import FastAPI
            from app.api.deps import get_current_user
            from app.api.v1.vertical_calculation_preview import router
            from app.config import settings
            from app.database import get_db
            monkeypatch.setattr(settings, "VERTICAL_CALCULATION_PREVIEW_ENABLED", True)
            monkeypatch.setattr(db, "commit", db.flush)
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            app.dependency_overrides[get_current_user] = lambda: user
            app.dependency_overrides[get_db] = lambda: db
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                page = await client.get(f"/api/v1/admin/vertical-preview/foundation/{geometry.id}")
                assert page.status_code == 200 and "Работы в смете" in page.text
                form = {"region": "qa", "terms": "qa", "idempotency_key": str(uuid.uuid4()),
                        "work_selection_present": "yes",
                        "work_block_id": detail.id, f"parameter.{primer}.primer.consumption": "0.25",
                        f"parameter.{bundle}.mastic.consumption": "1.5"}
                response = await client.post(f"/api/v1/admin/vertical-preview/foundation/{geometry.id}", data=form)
                assert response.status_code == 303 and "snapshot=" in response.headers["location"]
                repeated = await client.post(f"/api/v1/admin/vertical-preview/foundation/{geometry.id}", data=form)
                assert repeated.headers["location"] == response.headers["location"]
                reopened = await client.get(response.headers["location"])
                assert reopened.status_code == 200
                assert f'name="work_block_id" value="{detail.id}" checked' in reopened.text
                assert f'name="work_block_id" value="{bundle}" checked' not in reopened.text
                assert "Нанесение праймера" in reopened.text
                changed = await client.post(f"/api/v1/admin/vertical-preview/foundation/{geometry.id}",
                                            data={**form, "work_block_id": bundle})
                assert "error=" in changed.headers["location"]
            await db.rollback()
    finally:
        await engine.dispose()
