import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_coating_blocks import TECHNOLOGY_CODE, _id, add_coating_blocks
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
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA coating")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"geometry.area":"20"}, project_values={}, expected_version=0)
            primer, mastic = _id(tech.id, "primer", "block"), _id(tech.id, "mastic", "block")
            keys = {(primer,"MATERIAL"):"primer", (mastic,"MATERIAL"):"mastic", (mastic,"WORK"):"coating-work"}
            missing = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys)
            assert all(line["quantity"] is None for line in missing.payload["result"]["materials"])
            assert not missing.payload["result"]["complete"]
            calculated = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys,
                parameter_values={(primer,"primer.consumption"):"0.25", (mastic,"mastic.consumption"):"1.5"})
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
