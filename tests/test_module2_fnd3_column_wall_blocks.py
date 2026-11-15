import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_column_wall_blocks import (REBAR_ROLES, _id, add_column_wall_concrete,
                                                          add_column_wall_formwork, add_column_wall_reinforcement)
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
@pytest.mark.parametrize("code,values,expected", [
    ("FND_COLUMN_CONCRETE_RC", {"element.length":"0.4", "element.width":"0.4",
                                "element.height":"1.5", "element.count":"10"}, "2.400"),
    ("FND_BASEMENT_WALL_MONOLITHIC", {"geometry.wall_length":"20", "geometry.wall_height":"3",
        "geometry.wall_thickness":"0.3", "geometry.opening_area":"4", "geometry.wall_overlap_volume":"0.2"}, "16.6"),
])
async def test_concrete_geometry_and_single_work_on_restored_qa(code, values, expected):
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
            first = await add_column_wall_concrete(db, actor=user, technology_code=code)
            second = await add_column_wall_concrete(db, actor=user, technology_code=code)
            assert first["created"] + first["reused"] == 1 and not first["edited"]
            assert second["reused"] == 1 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == code, Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA concrete")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values=values, project_values={}, expected_version=0)
            block = _id(tech.id, "block")
            formwork_id = _id(tech.id, "formwork/block")
            keys = {(block,"MATERIAL"):"concrete", (block,"WORK"):"pouring",
                    (formwork_id,"MATERIAL"):"formwork-material", (formwork_id,"WORK"):"formwork-work"}
            for role in REBAR_ROLES[code]:
                key = role.lower()
                rebar_id = _id(tech.id, f"rebar/{key}/block")
                keys[(rebar_id,"MATERIAL")] = "material-" + key
                keys[(rebar_id,"WORK")] = "work-" + key
            result = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys)
            materials, works = result.payload["result"]["materials"], result.payload["result"]["works"]
            assert materials[0]["quantity"] == works[0]["quantity"] == expected
            assert not result.payload["result"]["complete"] and result.payload["missing_required_roles"]
            if code == "FND_BASEMENT_WALL_MONOLITHIC":
                invalid = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                    user_values={**values, "geometry.opening_area":"61"}, project_values={}, expected_version=1)
                bad = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=invalid.id,
                    region="qa", terms="qa", accounting_keys=keys)
                assert bad.payload["result"]["materials"][0]["quantity"] is None
                assert "NEGATIVE_QUANTITY" in bad.payload["result"]["materials"][0]["issues"]
            first_rebar = await add_column_wall_reinforcement(db, actor=user, technology_code=code)
            repeat_rebar = await add_column_wall_reinforcement(db, actor=user, technology_code=code)
            assert first_rebar["created"] + first_rebar["reused"] == len(REBAR_ROLES[code]) and not first_rebar["edited"]
            assert repeat_rebar["reused"] == len(REBAR_ROLES[code]) and not repeat_rebar["edited"]
            params = {}
            for role in REBAR_ROLES[code]:
                key = role.lower()
                rebar_id = _id(tech.id, f"rebar/{key}/block")
                keys[(rebar_id,"MATERIAL")] = "material-" + key
                keys[(rebar_id,"WORK")] = "work-" + key
                for suffix,value in {"length":"12", "count":"4", "lap_length":"0.5",
                                     "lap_count":"2", "mass_per_m":"0.888"}.items():
                    params[(rebar_id, f"{key}.{suffix}")] = value
            unconfirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params)
            assert sum("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in
                       unconfirmed.payload["result"]["works"]) == len(REBAR_ROLES[code])
            confirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params,
                column_wall_rebar_disjoint_confirmed=True)
            rebar = [line for line in confirmed.payload["result"]["materials"] if line["unit"] == "m"]
            assert len(rebar) == len(REBAR_ROLES[code]) and all(line["quantity"] == "49.0" for line in rebar)
            rebar_work = [line for line in confirmed.payload["result"]["works"] if line["unit"] == "kg"]
            assert len(rebar_work) == len(REBAR_ROLES[code]) and all(line["quantity"] == "43.5120" for line in rebar_work)
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in rebar + rebar_work)
            assert not confirmed.payload["result"]["complete"]
            formwork = await add_column_wall_formwork(db, actor=user, technology_code=code)
            repeat_formwork = await add_column_wall_formwork(db, actor=user, technology_code=code)
            assert formwork["created"] + formwork["reused"] == 1 and not formwork["edited"]
            assert repeat_formwork["reused"] == 1 and not repeat_formwork["edited"]
            params[(formwork_id,"formwork.material_area")] = "8"
            params[(formwork_id,"formwork.installation_area")] = "20"
            with_formwork = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params,
                column_wall_rebar_disjoint_confirmed=True)
            assert any(line["unit"] == "m2" and line["quantity"] == "8" for line in with_formwork.payload["result"]["materials"])
            assert any(line["unit"] == "m2" and line["quantity"] == "20" for line in with_formwork.payload["result"]["works"])
            await db.rollback()
    finally:
        await engine.dispose()
