import os
import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology, TechnologyWorkStep
from app.models.user import User
from app.services.module2_fnd3_grillage_blocks import PILE_ROLES, REBAR_ROLES, TECHNOLOGY_CODE, _id, add_grillage_blocks
from app.services.module2_calculation_blocks import add_block
from app.services.module2_calculation_presets import rectangular_volume_block
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_grillage_selection_and_bundle_guards_on_restored_qa():
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
            first, second = await add_grillage_blocks(db, actor=user), await add_grillage_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 10 and not first["edited"]
            assert second["reused"] == 10 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA grillage")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"geometry.length":"12", "geometry.width":"0.4", "geometry.height":"0.8",
                             "strip.overlap_volume":"0.2", "pile.count":"5"}, project_values={}, expected_version=0)
            keys = {}
            for key in (*PILE_ROLES.values(), *(code.lower() for code in REBAR_ROLES), "concrete"):
                keys[(_id(tech.id,key,"block"),"MATERIAL")] = "material-"+key
            bundle = _id(tech.id,"bundle","block")
            keys[(bundle,"WORK")] = "bundle-work"
            counts = {"factory_6":"3", "factory_8":"2", "screw_89":"0", "screw_108":"0", "screw_108_long":"0"}
            params = {(_id(tech.id,key,"block"), f"{key}.count"):value for key,value in counts.items()}
            for code in REBAR_ROLES:
                key=code.lower()
                for suffix,value in {"length":"12", "count":"4", "lap_length":"0.5", "lap_count":"2"}.items():
                    params[(_id(tech.id,key,"block"),f"{key}.{suffix}")] = value
            unconfirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params)
            work = unconfirmed.payload["result"]["works"][0]
            assert work["quantity"] == "12" and "BUNDLE_SCOPE_UNVERIFIED" in work["issues"]
            assert sum("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in
                       unconfirmed.payload["result"]["materials"]) == 2
            confirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params,
                grillage_rebar_disjoint_confirmed=True, grillage_bundle_scope_confirmed=True)
            materials, work = confirmed.payload["result"]["materials"], confirmed.payload["result"]["works"][0]
            assert any(line["unit"] == "m3" and line["quantity"] == "3.64" for line in materials)
            assert sum(line["unit"] == "m" and line["quantity"] == "49.0" for line in materials) == 3
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in materials)
            assert "BUNDLE_SCOPE_UNVERIFIED" not in work["issues"] and not confirmed.payload["result"]["complete"]
            mismatch = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys,
                parameter_values={**params,(_id(tech.id,"factory_6","block"),"factory_6.count"):"4"},
                grillage_rebar_disjoint_confirmed=True, grillage_bundle_scope_confirmed=True)
            assert all("PILE_ALLOCATION_UNVERIFIED" in line["issues"] for line in
                       mismatch.payload["result"]["materials"] + mismatch.payload["result"]["works"])
            detailed_code = "foundations_concrete_betonirovanie_konstrukciy"
            step = TechnologyWorkStep(id=uuid.uuid4(), technology_id=tech.id, position=9999,
                                      work_code=detailed_code, dependency_step_codes=[])
            db.add(step)
            await db.flush()
            detail = replace(rectangular_volume_block(name="QA detailed work"), material_output_id=None,
                             work_code=detailed_code, work_step_id=str(step.id))
            await add_block(db, technology_id=tech.id, block=detail, actor=user, actor_id=owner)
            with_detail = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys={**keys,(detail.id,"WORK"):"detailed-work"},
                parameter_values=params, grillage_rebar_disjoint_confirmed=True, grillage_bundle_scope_confirmed=True)
            assert len(with_detail.payload["result"]["works"]) == 2
            assert all("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in with_detail.payload["result"]["works"])
            await db.rollback()
    finally:
        await engine.dispose()
