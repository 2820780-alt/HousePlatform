import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_precast_blocks import TECHNOLOGY_CODE, _id, add_precast_blocks
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_precast_layout_and_explicit_mortar_on_restored_qa():
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
            first, second = await add_precast_blocks(db, actor=user), await add_precast_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 6 and not first["edited"]
            assert second["reused"] == 6 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA precast")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"layout.fbs_main":"10", "layout.fbs_short":"4", "layout.fbs_shorter":"2", "layout.fl":"8"},
                project_values={}, expected_version=0)
            ids = {key:_id(tech.id,key,"block") for key in ("main","short","shorter","fbs-work","fl","mortar")}
            keys = {(ids[key],"MATERIAL"):key for key in ("main","short","shorter","fl","mortar")}
            keys.update({(ids[key],"WORK"):"work-"+key for key in ("fbs-work","fl","mortar")})
            missing = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys)
            mortar = next(line for line in missing.payload["result"]["materials"] if line["binding"]["block_id"] == ids["mortar"])
            assert mortar["quantity"] is None and "MISSING_INPUT:mortar.volume" in mortar["issues"]
            result = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys,
                parameter_values={(ids["mortar"],"mortar.volume"):"0.75"})
            materials, works = result.payload["result"]["materials"], result.payload["result"]["works"]
            assert len(materials) == 5 and len(works) == 3
            assert {line["binding"]["block_id"]:line["quantity"] for line in materials} == {
                ids["main"]:"10", ids["short"]:"4", ids["shorter"]:"2", ids["fl"]:"8", ids["mortar"]:"0.75"}
            assert {line["binding"]["block_id"]:line["quantity"] for line in works} == {
                ids["fbs-work"]:"16", ids["fl"]:"8", ids["mortar"]:"0.75"}
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in materials + works)
            assert not result.payload["result"]["complete"]
            await db.rollback()
    finally:
        await engine.dispose()
