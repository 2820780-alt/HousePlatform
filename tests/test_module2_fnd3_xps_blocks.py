import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_xps_blocks import TECHNOLOGY_CODE, _id, add_xps_blocks
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_xps_zones_round_panels_and_single_work_on_restored_qa():
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
            first = await add_xps_blocks(db, actor=user)
            second = await add_xps_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 3 and not first["edited"]
            assert second["reused"] == 3 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA XPS")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"geometry.wall_area":"10", "geometry.slab_area":"6", "geometry.edge_area":"0"},
                project_values={}, expected_version=0)
            wall, slab, work = (_id(tech.id, name, "block") for name in ("wall", "slab", "work"))
            keys = {(wall,"MATERIAL"):"xps-wall", (slab,"MATERIAL"):"xps-slab", (work,"WORK"):"xps-install"}
            params = {(wall,"xps_wall.sheet_length"):"1.2", (wall,"xps_wall.sheet_width"):"0.6",
                      (slab,"xps_slab.sheet_length"):"1.2", (slab,"xps_slab.sheet_width"):"0.6"}
            result = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params)
            materials, works = result.payload["result"]["materials"], result.payload["result"]["works"]
            assert sorted(line["quantity"] for line in materials) == ["10.08", "6.48"]
            assert len(works) == 1 and works[0]["quantity"] == "16" and works[0]["unit"] == "m2"
            assert not result.payload["result"]["complete"] and result.payload["missing_required_roles"]
            new_geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"geometry.wall_area":"10", "geometry.slab_area":"0", "geometry.edge_area":"0"},
                project_values={}, expected_version=1)
            only_wall = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=new_geometry.id,
                region="qa", terms="qa", accounting_keys=keys,
                parameter_values={key:value for key,value in params.items() if key[0] == wall})
            slab_line = next(line for line in only_wall.payload["result"]["materials"] if line["binding"]["block_id"] == slab)
            assert slab_line["quantity"] == "0" and not any(issue.startswith("MISSING_INPUT:") for issue in slab_line["issues"])
            await db.rollback()
    finally:
        await engine.dispose()
