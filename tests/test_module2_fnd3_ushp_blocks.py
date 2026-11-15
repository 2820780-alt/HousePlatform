import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_ribbed_slab_blocks import USHP_CODE, _id as rib_id, add_ribbed_slab_blocks
from app.services.module2_fnd3_slab_blocks import _id as slab_id
from app.services.module2_fnd3_ushp_blocks import add_ushp_blocks
from app.services.module2_fnd3_xps_blocks import _id as xps_id
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_ushp_disjoint_concrete_and_xps_zones_on_restored_qa():
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
            first = await add_ribbed_slab_blocks(db, actor=user, technology_code=USHP_CODE)
            second = await add_ribbed_slab_blocks(db, actor=user, technology_code=USHP_CODE)
            assert first["created"] + first["reused"] == 2 and second["reused"] == 2 and not first["edited"]
            first = await add_ushp_blocks(db, actor=user)
            second = await add_ushp_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 4 and second["reused"] == 4 and not first["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == USHP_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA USHP")
            values = {"geometry.net_area":"50", "geometry.slab_thickness":"0.2", "geometry.rib_length":"20",
                      "geometry.rib_width":"0.4", "geometry.rib_height":"0.3", "geometry.rib_overlap_volume":"0.1",
                      "geometry.wall_area":"0", "geometry.slab_area":"6", "geometry.edge_area":"2"}
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values=values, project_values={}, expected_version=0)
            slab, ribs = (rib_id(tech.id, key, "block") for key in ("slab", "ribs"))
            insulation, edge, install = (xps_id(tech.id, key, "block") for key in ("slab", "edge", "work"))
            rebar = slab_id(tech.id, "block", "lower_x")
            keys = {(slab,"MATERIAL"):"slab-concrete", (ribs,"MATERIAL"):"rib-concrete",
                    (slab,"WORK"):"slab-pouring", (ribs,"WORK"):"rib-pouring",
                    (insulation,"MATERIAL"):"underslab-xps", (edge,"MATERIAL"):"edge-xps",
                    (install,"WORK"):"xps-install", (rebar,"MATERIAL"):"slab-rebar", (rebar,"WORK"):"rebar-work"}
            params = {(insulation,"xps_slab.sheet_length"):"1.2", (insulation,"xps_slab.sheet_width"):"0.6",
                      (edge,"xps_edge.sheet_length"):"1.2", (edge,"xps_edge.sheet_width"):"0.6"}
            for suffix,value in {"length":"12", "count":"4", "lap_length":"0.5",
                                 "lap_count":"2", "mass_per_m":"0.888"}.items():
                params[(rebar, f"lower_x.{suffix}")] = value
            result = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params,
                ribbed_concrete_disjoint_confirmed=True)
            materials, works = result.payload["result"]["materials"], result.payload["result"]["works"]
            quantities = {line["binding"]["block_id"]:line["quantity"] for line in materials}
            assert quantities == {slab:"10.0", ribs:"2.30", insulation:"6.48", edge:"2.16", rebar:"49.0"}
            assert any(line["binding"]["block_id"] == install and line["quantity"] == "8" for line in works)
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in materials + works)
            assert not result.payload["result"]["complete"] and result.payload["missing_required_roles"]
            wall = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={**values, "geometry.wall_area":"1"}, project_values={}, expected_version=1)
            with_wall = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=wall.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params,
                ribbed_concrete_disjoint_confirmed=True)
            assert "Материал утепления стен не выбран" in with_wall.payload["missing_required_roles"]
            await db.rollback()
    finally:
        await engine.dispose()
