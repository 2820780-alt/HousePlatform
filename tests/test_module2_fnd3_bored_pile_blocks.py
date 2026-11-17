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
from app.services.module2_fnd3_bored_pile_blocks import (REBAR_ROLES, TECHNOLOGY_CODE, _id, add_bored_pile_blocks,
                                                        add_bored_pile_reinforcement_blocks)
from app.services.module2_fnd3_bored_casing import _id as casing_id, add_bored_casing_block
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_bored_pile_concrete_and_drilling_are_separate_on_restored_qa():
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
            first = await add_bored_pile_blocks(db, actor=user)
            second = await add_bored_pile_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 2 and not first["edited"]
            assert second["reused"] == 2 and not second["edited"]
            casing = await add_bored_casing_block(db, actor=user)
            assert casing["created"] + casing["reused"] == 1 and not casing["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA bored piles")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"pile.diameter":"0.4", "pile.length":"2", "pile.count":"5", "pile.casing_length":"0"},
                project_values={}, expected_version=0)
            first_id = _id(tech.id, "concrete-drilling", "block")
            second_id = _id(tech.id, "pouring", "block")
            keys = {(first_id,"MATERIAL"):"pile-concrete", (first_id,"WORK"):"pile-drilling",
                    (second_id,"WORK"):"pile-pouring"}
            keys[(casing_id(tech.id, "block"), "WORK")] = "pile-casing"
            for code in REBAR_ROLES:
                key = code.lower()
                block_id = _id(tech.id, key, "block")
                keys[(block_id, "MATERIAL")] = "material-" + key
                keys[(block_id, "WORK")] = "work-" + key
            snapshot = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys)
            material = snapshot.payload["result"]["materials"]
            work = snapshot.payload["result"]["works"]
            concrete = [line for line in material if line["unit"] == "m3"]
            assert len(concrete) == 1 and abs(Decimal(concrete[0]["quantity"]) - Decimal("1.256637061435917")) < Decimal("0.000000000001")
            assert any(line["unit"] == "piece" and line["quantity"] == "5" for line in work)
            assert any(line["unit"] == "m3" and line["quantity"] == concrete[0]["quantity"] for line in work)
            assert not snapshot.payload["result"]["complete"] and snapshot.payload["missing_required_roles"]
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in work if line["unit"] in {"m3", "piece"})
            first_rebar = await add_bored_pile_reinforcement_blocks(db, actor=user)
            second_rebar = await add_bored_pile_reinforcement_blocks(db, actor=user)
            assert first_rebar["created"] + first_rebar["reused"] == 2 and not first_rebar["edited"]
            assert second_rebar["reused"] == 2 and not second_rebar["edited"]
            params = {}
            for code in REBAR_ROLES:
                key = code.lower()
                block_id = _id(tech.id, key, "block")
                keys[(block_id, "MATERIAL")] = "material-" + key
                keys[(block_id, "WORK")] = "work-" + key
                for suffix, value in {"length":"2", "count":"20", "lap_length":"0.5",
                                      "lap_count":"4", "mass_per_m":"0.888"}.items():
                    params[(block_id, f"{key}.{suffix}")] = value
            unconfirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params)
            assert sum("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in
                       unconfirmed.payload["result"]["works"]) == 2
            confirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params, pile_roles_confirmed=True)
            rebar = [line for line in confirmed.payload["result"]["materials"] if line["unit"] == "m"]
            assert len(rebar) == 2 and all(line["quantity"] == "42.0" for line in rebar)
            reinforcement_work = [line for line in confirmed.payload["result"]["works"] if line["unit"] == "kg"]
            assert len(reinforcement_work) == 2 and all(line["quantity"] == "37.2960" for line in reinforcement_work)
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in reinforcement_work)
            assert not confirmed.payload["result"]["complete"]
            row = await db.get(TechnologyCalculationBlock, uuid.UUID(_id(tech.id, "pile_longitudinal", "block")))
            altered = copy.deepcopy(row.definition)
            altered["parameters"][0]["label"] = "Изменённый параметр"
            row.definition = altered
            await db.flush()
            changed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params, pile_roles_confirmed=True)
            assert sum("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in
                       changed.payload["result"]["works"]) == 2
            await db.rollback()
    finally:
        await engine.dispose()
