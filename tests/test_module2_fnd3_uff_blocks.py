import copy
import os
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.user import User
from app.services.module2_fnd3_slab_blocks import _id as slab_id
from app.services.module2_fnd3_uff_blocks import TECHNOLOGY_CODE, _id, add_uff_blocks, add_uff_preparation_blocks
from app.services.module2_fnd3_uff_sleeves import _id as sleeve_id, add_uff_sleeve_blocks
from app.services.module2_fnd3_xps_blocks import _id as xps_id
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_uff_foundation_floor_disjoint_and_xps_on_restored_qa():
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
            first, second = await add_uff_blocks(db, actor=user), await add_uff_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 5 and not first["edited"]
            assert second["reused"] == 5 and not second["edited"]
            first, second = await add_uff_preparation_blocks(db, actor=user), await add_uff_preparation_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 3 and not first["edited"]
            assert second["reused"] == 3 and not second["edited"]
            first, second = await add_uff_sleeve_blocks(db, actor=user), await add_uff_sleeve_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 3 and not first["edited"]
            assert second["reused"] == 3 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA UFF")
            values = {"geometry.length":"12", "geometry.width":"0.4", "geometry.height":"0.8",
                      "strip.overlap_volume":"0.2", "geometry.net_area":"50", "geometry.slab_thickness":"0.1",
                      "geometry.wall_area":"0", "geometry.slab_area":"6", "geometry.edge_area":"0",
                      "uff.sleeves_dn110":"0", "uff.sleeves_dn160":"0"}
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values=values, project_values={}, expected_version=0)
            foundation, floor = (_id(tech.id, name, "block") for name in ("foundation", "floor"))
            insulation, install = (xps_id(tech.id, name, "block") for name in ("slab", "work"))
            rebar = slab_id(tech.id, "block", "lower_x")
            keys = {(foundation,"MATERIAL"):"foundation", (foundation,"WORK"):"foundation-work",
                    (floor,"MATERIAL"):"floor", (floor,"WORK"):"floor-work", (insulation,"MATERIAL"):"xps",
                    (install,"WORK"):"xps-work", (rebar,"MATERIAL"):"rebar", (rebar,"WORK"):"rebar-work"}
            keys[(sleeve_id(tech.id, "dn110", "block"), "MATERIAL")] = "sleeve110"
            keys[(sleeve_id(tech.id, "dn160", "block"), "MATERIAL")] = "sleeve160"
            keys[(sleeve_id(tech.id, "work", "block"), "WORK")] = "sleeve-work"
            preparation = {code: str(uuid.uuid5(uuid.NAMESPACE_URL,
                f"atom/fnd3/{tech.id}/uff/preparation/{code}/block")) for code in ("sand", "gravel")}
            geo = str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{tech.id}/uff/geotextile/block"))
            for code, identifier in (*preparation.items(), ("geotextile", geo)):
                keys[(identifier, "MATERIAL")] = f"{code}-material"
                keys[(identifier, "WORK")] = f"{code}-work"
            params = {(insulation,"xps_slab.sheet_length"):"1.2", (insulation,"xps_slab.sheet_width"):"0.6"}
            for code, identifier in preparation.items():
                for name, value in (("area", "50"), ("thickness", "0.2"), ("supply_factor", "1.2")):
                    params[(identifier, f"preparation.{code}.{name}")] = value
            params[(geo, "geotextile.area")] = "50"
            params[(geo, "geotextile.overlap_area")] = "5"
            for suffix,value in {"length":"12", "count":"4", "lap_length":"0.5",
                                 "lap_count":"2", "mass_per_m":"0.888"}.items():
                params[(rebar, f"lower_x.{suffix}")] = value
            unconfirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params)
            for line in unconfirmed.payload["result"]["materials"] + unconfirmed.payload["result"]["works"]:
                if line["binding"]["block_id"] in {foundation, floor}:
                    assert "UFF_SCOPE_UNVERIFIED" in line["issues"]
            confirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params, uff_floor_disjoint_confirmed=True)
            quantities = {line["binding"]["block_id"]:line["quantity"] for line in confirmed.payload["result"]["materials"]}
            assert all(quantities[key] == value for key, value in
                       {foundation:"3.64", floor:"5.0", insulation:"6.48", rebar:"49.0"}.items())
            assert all(Decimal(quantities[identifier]) == 12 for identifier in preparation.values())
            assert Decimal(quantities[geo]) == 55
            work_quantities = {line["binding"]["block_id"]: line["quantity"] for line in confirmed.payload["result"]["works"]}
            assert all(Decimal(work_quantities[identifier]) == 10 for identifier in preparation.values())
            assert Decimal(work_quantities[geo]) == 50
            assert all("UFF_SCOPE_UNVERIFIED" not in line["issues"] for line in
                       confirmed.payload["result"]["materials"] + confirmed.payload["result"]["works"])
            assert not confirmed.payload["result"]["complete"]
            row = await db.get(TechnologyCalculationBlock, uuid.UUID(floor))
            altered = copy.deepcopy(row.definition)
            altered["parameters"][0]["label"] = "Изменённый параметр"
            row.definition = altered
            await db.flush()
            changed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params, uff_floor_disjoint_confirmed=True)
            assert all("UFF_SCOPE_UNVERIFIED" in line["issues"] for line in
                       changed.payload["result"]["materials"] + changed.payload["result"]["works"]
                       if line["binding"]["block_id"] in {foundation, floor})
            await db.rollback()
    finally:
        await engine.dispose()
