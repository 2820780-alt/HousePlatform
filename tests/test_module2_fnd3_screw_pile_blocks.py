import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_screw_pile_blocks import ROLES, TECHNOLOGY_CODE, _id, add_screw_pile_blocks
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_screw_pile_allocations_require_explicit_head_confirmation():
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
            first = await add_screw_pile_blocks(db, actor=user)
            second = await add_screw_pile_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 7 and not first["edited"]
            assert second["reused"] == 7 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA screw piles")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"pile.count":"5", "pile.head_count":"5"}, project_values={}, expected_version=0)
            keys = {(_id(tech.id, key, "block"), "MATERIAL"): "material-" + key for key in ROLES.values()}
            keys[(_id(tech.id, "pile_work", "block"), "WORK")] = "screw-install"
            keys[(_id(tech.id, "head_work", "block"), "WORK")] = "head-install"
            counts = {"screw_89":"3", "screw_108_long":"2", "screw_108":"0", "head_89":"3", "head_108":"2"}
            params = {(_id(tech.id, key, "block"), f"{key}.count"):value for key,value in counts.items()}
            unconfirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params)
            assert all("PILE_ALLOCATION_UNVERIFIED" in line["issues"] for line in
                       unconfirmed.payload["result"]["materials"] + unconfirmed.payload["result"]["works"])
            confirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params, screw_head_match_confirmed=True)
            assert sorted(line["quantity"] for line in confirmed.payload["result"]["materials"]) == ["0", "2", "2", "3", "3"]
            assert [line["quantity"] for line in confirmed.payload["result"]["works"]] == ["5", "5"]
            assert all("PILE_ALLOCATION_UNVERIFIED" not in line["issues"] for line in
                       confirmed.payload["result"]["materials"] + confirmed.payload["result"]["works"])
            assert not confirmed.payload["result"]["complete"]
            invalid_params = {**params, (_id(tech.id, "head_89", "block"), "head_89.count"): "4"}
            mismatch = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=invalid_params,
                screw_head_match_confirmed=True)
            assert all("PILE_ALLOCATION_UNVERIFIED" in line["issues"] for line in
                       mismatch.payload["result"]["materials"] + mismatch.payload["result"]["works"])
            zero_geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"pile.count":"5", "pile.head_count":"0"}, project_values={}, expected_version=1)
            zero_params = {**params, (_id(tech.id, "head_89", "block"), "head_89.count"): "0",
                           (_id(tech.id, "head_108", "block"), "head_108.count"): "0"}
            zero = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=zero_geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=zero_params)
            assert all("PILE_ALLOCATION_UNVERIFIED" not in line["issues"] for line in
                       zero.payload["result"]["materials"] + zero.payload["result"]["works"])
            await db.rollback()
    finally:
        await engine.dispose()
