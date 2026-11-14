from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from starlette.datastructures import FormData

from app.api.deps import get_current_user
from app.api.v1.module2_calculation_builder import router
from app.config import settings
from app.core.exceptions import ForbiddenError
from app.database import engine as configured_engine, get_db
from app.models.module2_calculation_block import CalculationBlockTemplate, TechnologyCalculationBlock
from app.models.module2_technology import MODULE2_OWNER_CODE, Technology
from app.models.enums import MaterialStatus


def _actor(level):
    return SimpleNamespace(id=None, role="SUPPLIER", moduleAccessRules=[{
        "moduleCode": MODULE2_OWNER_CODE, "accessLevel": level, "accessScope": "GLOBAL",
    }, {"moduleCode": "MODULE_01_MATERIAL_HUB", "accessLevel": "VIEW", "accessScope": "GLOBAL"}])


@pytest.mark.asyncio
async def test_m2_requirement_accepts_only_accessible_nonarchived_m1_material(monkeypatch):
    from app.api.v1.module2_workbench import _perform_action

    monkeypatch.setattr(settings, "VERTICAL_CALCULATION_PREVIEW_ENABLED", True)
    material_id = uuid.uuid4()
    material = SimpleNamespace(id=material_id, status=MaterialStatus.VERIFIED)

    class Database:
        async def get(self, _model, _id):
            return material if _id == material_id else None

    technology = Technology(id=uuid.uuid4(), technology_code="QA", revision=1,
                            name="QA", status="DRAFT", requirements=[])
    data = FormData({"code": "QA_MATERIAL", "selector_kind": "CANONICAL_MATERIAL",
                     "canonical_material_id": str(material_id)})
    actor = SimpleNamespace(id=None, role="ADMIN")
    await _perform_action("save-requirement", data, technology=technology, db=Database(),
                          role_code=actor, user_id=None)
    assert technology.requirements[0].canonical_material_id == material_id
    material.status = MaterialStatus.ARCHIVED
    with pytest.raises(ValueError):
        await _perform_action("save-requirement", data, technology=technology, db=Database(),
                              role_code=actor, user_id=None)
    without_m1 = SimpleNamespace(id=None, role="SUPPLIER", moduleAccessRules=[{
        "moduleCode": MODULE2_OWNER_CODE, "accessLevel": "EDIT", "accessScope": "GLOBAL",
    }])
    with pytest.raises(ForbiddenError):
        await _perform_action("save-requirement", data, technology=technology, db=Database(),
                              role_code=without_m1, user_id=None)


@pytest.mark.asyncio
async def test_builder_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "VERTICAL_CALCULATION_PREVIEW_ENABLED", False)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: _actor("ADMIN")
    app.dependency_overrides[get_db] = lambda: None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(f"/api/v1/admin/module2/calculation-builder/{uuid.uuid4()}")).status_code == 404


@pytest.mark.asyncio
async def test_builder_forms_copy_and_preserve_active_revision_in_restored_qa(monkeypatch):
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    monkeypatch.setattr(settings, "VERTICAL_CALCULATION_PREVIEW_ENABLED", True)
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
                first = Technology(id=uuid.uuid4(), technology_code="QA_STRIP_" + uuid.uuid4().hex,
                                   revision=1, name="QA strip", status="DRAFT")
                second = Technology(id=uuid.uuid4(), technology_code="QA_SLAB_" + uuid.uuid4().hex,
                                    revision=1, name="QA slab", status="DRAFT")
                db.add_all([first, second])
                await db.flush()
                app = FastAPI()
                app.include_router(router, prefix="/api/v1")
                app.add_exception_handler(ForbiddenError, lambda _request, _exc: JSONResponse({}, status_code=403))
                app.dependency_overrides[get_current_user] = lambda: _actor("ADMIN")
                app.dependency_overrides[get_db] = lambda: db
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    base = f"/api/v1/admin/module2/calculation-builder/{first.id}"
                    assert (await client.get(base)).status_code == 200
                    assert (await client.post(f"{base}/add", data={"preset": "volume"})).status_code == 303
                    original = await db.scalar(select(TechnologyCalculationBlock).where(
                        TechnologyCalculationBlock.technology_id == first.id))
                    assert original is not None
                    composed = await client.post(f"{base}/compose", data={
                        "name": "QA площадь", "step.1.label": "Длина", "step.1.operation": "INPUT",
                        "step.1.unit": "m", "step.1.source": "geometry.length",
                        "step.2.label": "Ширина", "step.2.operation": "INPUT", "step.2.unit": "m",
                        "step.2.source": "geometry.width", "step.3.label": "Площадь",
                        "step.3.operation": "MULTIPLY", "step.3.unit": "m2", "step.3.ref.1": "1",
                        "step.3.ref.2": "2", "material_step": "3", "rule_source": "QA only",
                    })
                    assert composed.status_code == 303 and "error=" not in composed.headers["location"]
                    custom = await db.scalar(select(TechnologyCalculationBlock).where(
                        TechnologyCalculationBlock.technology_id == first.id,
                        TechnologyCalculationBlock.name == "QA площадь"))
                    assert custom is not None and custom.definition["nodes"][-1]["label"] == "Площадь"
                    changed = await client.post(f"{base}/compose-update", data={
                        "block_id": str(custom.id), "version": str(custom.version), "name": "QA сумма",
                        "step.1.label": "Длина", "step.1.operation": "INPUT", "step.1.unit": "m",
                        "step.1.source": "geometry.length", "step.2.label": "Ширина",
                        "step.2.operation": "INPUT", "step.2.unit": "m", "step.2.source": "geometry.width",
                        "step.3.label": "Сумма", "step.3.operation": "ADD", "step.3.unit": "m",
                        "step.3.ref.1": "1", "step.3.ref.2": "2", "material_step": "3",
                        "rule_source": "QA only",
                    })
                    assert changed.status_code == 303 and "error=" not in changed.headers["location"]
                    assert custom.definition["nodes"][-1]["operation"] == "ADD" and custom.version == 2
                    assert (await client.post(f"{base}/save-template", data={"block_id": str(original.id),
                                                                              "template_name": "Объём"})).status_code == 303
                    template = await db.scalar(select(CalculationBlockTemplate).where(
                        CalculationBlockTemplate.name == "Объём"))
                    assert template is not None
                    second_url = f"/api/v1/admin/module2/calculation-builder/{second.id}"
                    response = await client.post(f"{second_url}/copy-template", data={
                        "source_id": str(template.id), "mapping.geometry.length": "slab.length",
                        "mapping.geometry.width": "slab.width", "mapping.geometry.height": "slab.height",
                    })
                    assert response.status_code == 303 and "error=" not in response.headers["location"]
                    copy = await db.scalar(select(TechnologyCalculationBlock).where(
                        TechnologyCalculationBlock.technology_id == second.id))
                    assert copy is not None and copy.id != original.id
                    assert (await client.get(second_url)).status_code == 200
                    bar = await client.post(f"{base}/add", data={"preset": "reinforcement", "rule_source": "QA only",
                        "range.0.lower": "350", "range.0.upper": "500", "range.0.count": "3",
                        "range.1.lower": "500", "range.1.upper": "501", "range.1.count": "4",
                        "range.1.inclusive": "on"})
                    assert bar.status_code == 303 and "error=" not in bar.headers["location"]
                    rows = (await db.scalars(select(TechnologyCalculationBlock).where(
                        TechnologyCalculationBlock.technology_id == first.id))).all()
                    reinforcement = next(item for item in rows if item.id not in {original.id, custom.id})
                    assert reinforcement.definition["rule_status"] == "PRELIMINARY"
                    assert "Диапазоны количества" in (await client.get(base)).text
                    first.status = "ACTIVE"
                    await db.flush()
                    forbidden_change = await client.post(f"{base}/add", data={"preset": "volume"})
                    assert "error=" in forbidden_change.headers["location"]
                    app.dependency_overrides[get_current_user] = lambda: _actor("VIEW")
                    assert (await client.get(second_url)).status_code == 403
                    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                        id=None, role="SUPPLIER", moduleAccessRules=[{"moduleCode": MODULE2_OWNER_CODE,
                        "accessLevel": "EDIT", "accessScope": "GLOBAL"}])
                    assert (await client.get(second_url)).status_code == 403
                    assert (await client.post(f"{second_url}/add", data={"preset": "volume"})).status_code == 403
            await transaction.rollback()
    finally:
        await engine.dispose()
