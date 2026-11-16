import os
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_base_preparation import add_base_preparation_blocks
from app.services.module2_fnd3_ribbed_slab_blocks import (REBAR_ROLES, TECHNOLOGY_CODE, _id, add_ribbed_slab_blocks,
                                                          add_ribbed_slab_detail_blocks)
from app.services.module2_fnd3_slab_blocks import _id as slab_id
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_ribbed_slab_disjoint_volumes_on_restored_qa():
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
            first, second = await add_ribbed_slab_blocks(db, actor=user), await add_ribbed_slab_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 2 and not first["edited"]
            assert second["reused"] == 2 and not second["edited"]
            prep = await add_base_preparation_blocks(db, actor=user, technology_code=TECHNOLOGY_CODE)
            again = await add_base_preparation_blocks(db, actor=user, technology_code=TECHNOLOGY_CODE)
            assert prep["created"] + prep["reused"] == 2 and not prep["edited"]
            assert again["reused"] == 2 and not again["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA ribbed slab")
            values = {"geometry.net_area":"50", "geometry.slab_thickness":"0.2", "geometry.rib_length":"20",
                      "geometry.rib_width":"0.4", "geometry.rib_height":"0.3", "geometry.rib_overlap_volume":"0.1"}
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values=values, project_values={}, expected_version=0)
            slab, ribs = (_id(tech.id, name, "block") for name in ("slab", "ribs"))
            keys = {(slab,"MATERIAL"):"slab-concrete", (ribs,"MATERIAL"):"rib-concrete",
                    (slab,"WORK"):"slab-pouring", (ribs,"WORK"):"rib-pouring"}
            for code in REBAR_ROLES:
                block_id = _id(tech.id, code.lower(), "block")
                keys[(block_id,"MATERIAL")] = "material-"+code
                keys[(block_id,"WORK")] = "work-"+code
            formwork = slab_id(tech.id,"block","formwork")
            keys[(formwork,"MATERIAL")] = "formwork-material"
            keys[(formwork,"WORK")] = "formwork-work"
            prep_ids = {code: str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{tech.id}/ribbed/preparation/{code}/block"))
                        for code in ("sand", "gravel")}
            for code, identifier in prep_ids.items():
                keys[(identifier, "MATERIAL")] = f"{code}-material"
                keys[(identifier, "WORK")] = f"{code}-work"
            unconfirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys)
            assert all("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in
                       unconfirmed.payload["result"]["materials"] + unconfirmed.payload["result"]["works"]
                       if line["binding"]["block_id"] in {slab,ribs})
            confirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, ribbed_concrete_disjoint_confirmed=True)
            assert sorted(line["quantity"] for line in confirmed.payload["result"]["materials"]
                          if line["binding"]["block_id"] in {slab,ribs}) == ["10.0", "2.30"]
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in
                       confirmed.payload["result"]["materials"] + confirmed.payload["result"]["works"]
                       if line["binding"]["block_id"] in {slab,ribs})
            assert not confirmed.payload["result"]["complete"]
            bad = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={**values, "geometry.rib_overlap_volume":"3"}, project_values={}, expected_version=1)
            invalid = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=bad.id,
                region="qa", terms="qa", accounting_keys=keys, ribbed_concrete_disjoint_confirmed=True)
            rib_line = next(line for line in invalid.payload["result"]["materials"] if line["binding"]["block_id"] == ribs)
            assert rib_line["quantity"] is None and "NEGATIVE_QUANTITY" in rib_line["issues"]
            detail, repeat = await add_ribbed_slab_detail_blocks(db, actor=user), await add_ribbed_slab_detail_blocks(db, actor=user)
            assert detail["created"] + detail["reused"] == 5 and not detail["edited"]
            assert repeat["reused"] == 5 and not repeat["edited"]
            params = {(formwork,"formwork.material_area"):"8", (formwork,"formwork.installation_area"):"20"}
            for code, identifier in prep_ids.items():
                for name, value in (("area", "50"), ("thickness", "0.2"), ("supply_factor", "1.2")):
                    params[(identifier, f"preparation.{code}.{name}")] = value
            for code in REBAR_ROLES:
                key = code.lower()
                block_id = _id(tech.id,key,"block")
                for suffix,value in {"length":"12", "count":"4", "lap_length":"0.5",
                                     "lap_count":"2", "mass_per_m":"0.888"}.items():
                    params[(block_id,f"{key}.{suffix}")] = value
            details = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params,
                ribbed_concrete_disjoint_confirmed=True, ribbed_rebar_disjoint_confirmed=True)
            rebar = [line for line in details.payload["result"]["materials"] if line["unit"] == "m"]
            rebar_work = [line for line in details.payload["result"]["works"] if line["unit"] == "kg"]
            assert len(rebar) == len(rebar_work) == 4
            assert all(line["quantity"] == "49.0" for line in rebar)
            assert all(line["quantity"] == "43.5120" for line in rebar_work)
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in rebar + rebar_work)
            assert any(line["quantity"] == "8" and line["unit"] == "m2" for line in details.payload["result"]["materials"])
            assert any(line["quantity"] == "20" and line["unit"] == "m2" for line in details.payload["result"]["works"])
            for identifier in prep_ids.values():
                assert Decimal(next(line["quantity"] for line in details.payload["result"]["materials"]
                                    if line["binding"]["block_id"] == identifier)) == 12
                assert Decimal(next(line["quantity"] for line in details.payload["result"]["works"]
                                    if line["binding"]["block_id"] == identifier)) == 10
            await db.rollback()
    finally:
        await engine.dispose()
