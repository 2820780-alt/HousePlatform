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
from app.services.module2_fnd3_base_preparation import add_base_preparation_blocks
from app.services.module2_fnd3_slab_blocks import (REBAR_ROLES, TECHNOLOGY_CODE, add_slab_concrete_block,
                                                   add_slab_formwork_block, add_slab_reinforcement_blocks)
from app.services.module5_estimate_snapshots import create_estimate_preview, read_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_slab_concrete_block_is_idempotent_and_uses_saved_geometry():
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
            first = await add_slab_concrete_block(db, actor=user)
            second = await add_slab_concrete_block(db, actor=user)
            assert first["created"] + first["reused"] == 1 and not first["edited"]
            assert second["reused"] == 1 and not second["edited"]
            prep = await add_base_preparation_blocks(db, actor=user, technology_code=TECHNOLOGY_CODE)
            again = await add_base_preparation_blocks(db, actor=user, technology_code=TECHNOLOGY_CODE)
            assert prep["created"] + prep["reused"] == 3 and not prep["edited"]
            assert again["created"] == 0 and again["reused"] == 3 and not again["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA monolithic slab")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"geometry.net_area": "50", "geometry.slab_thickness": "0.2"},
                project_values={}, expected_version=0)
            from app.services.module2_fnd3_slab_blocks import _id
            block = _id(tech.id, "block")
            formwork_id = _id(tech.id, "block", "formwork")
            keys = {(block, "MATERIAL"): "slab-concrete", (block, "WORK"): "slab-pouring",
                    (formwork_id, "MATERIAL"): "slab-formwork-material", (formwork_id, "WORK"): "slab-formwork-work"}
            prep_ids = {}
            for code in ("sand", "gravel"):
                identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{tech.id}/slab/preparation/{code}/block"))
                prep_ids[code] = identifier
                keys[(identifier, "MATERIAL")] = f"{code}-material"
                keys[(identifier, "WORK")] = f"{code}-work"
            geo = str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{tech.id}/slab/geotextile/block"))
            keys[(geo, "MATERIAL")] = "geotextile-material"
            keys[(geo, "WORK")] = "geotextile-work"
            for code in REBAR_ROLES:
                key = code.lower()
                block_id = _id(tech.id, "block", key)
                keys[(block_id, "MATERIAL")] = "material-" + key
                keys[(block_id, "WORK")] = "work-" + key
            snapshot = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys)
            assert snapshot.payload["result"]["materials"][0]["quantity"] == "10.0"
            assert snapshot.payload["result"]["works"][0]["quantity"] == "10.0"
            assert not snapshot.payload["result"]["complete"]
            assert snapshot.payload["missing_required_roles"]
            first_rebar = await add_slab_reinforcement_blocks(db, actor=user)
            repeat_rebar = await add_slab_reinforcement_blocks(db, actor=user)
            assert first_rebar["created"] + first_rebar["reused"] == 4 and not first_rebar["edited"]
            assert repeat_rebar["reused"] == 4 and not repeat_rebar["edited"]
            params = {}
            for code, identifier in prep_ids.items():
                for name, value in (("area", "50"), ("thickness", "0.2"), ("supply_factor", "1.2")):
                    params[(identifier, f"preparation.{code}.{name}")] = value
            params[(geo, "geotextile.area")] = "50"
            params[(geo, "geotextile.overlap_area")] = "5"
            for code in REBAR_ROLES:
                key = code.lower()
                block_id = _id(tech.id, "block", key)
                keys[(block_id, "MATERIAL")] = "material-" + key
                keys[(block_id, "WORK")] = "work-" + key
                for suffix, value in {"length": "12", "count": "4", "lap_length": "0.5",
                                      "lap_count": "2", "mass_per_m": "0.888"}.items():
                    params[(block_id, f"{key}.{suffix}")] = value
            without_confirmation = await create_estimate_preview(db, actor=user,
                foundation_geometry_revision_id=geometry.id, region="qa", terms="qa", accounting_keys=keys,
                parameter_values=params)
            assert sum("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in
                       without_confirmation.payload["result"]["materials"]) == 4
            confirmed = await create_estimate_preview(db, actor=user,
                foundation_geometry_revision_id=geometry.id, region="qa", terms="qa", accounting_keys=keys,
                parameter_values=params, slab_roles_confirmed=True)
            rebar = [line for line in confirmed.payload["result"]["materials"] if line["unit"] == "m"]
            assert len(rebar) == 4 and all(line["quantity"] == "49.0" for line in rebar)
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in rebar)
            works = [line for line in confirmed.payload["result"]["works"] if line["unit"] == "kg"]
            assert len(works) == 4 and all(line["quantity"] == "43.5120" for line in works)
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in works)
            for code, identifier in (*prep_ids.items(), ("geotextile", geo)):
                material = next(line for line in confirmed.payload["result"]["materials"]
                                if line["binding"]["block_id"] == identifier)
                work = next(line for line in confirmed.payload["result"]["works"]
                            if line["binding"]["block_id"] == identifier)
                assert Decimal(material["quantity"]) == (55 if code == "geotextile" else 12)
                assert Decimal(work["quantity"]) == (50 if code == "geotextile" else 10)
            assert not confirmed.payload["result"]["complete"]
            first_formwork = await add_slab_formwork_block(db, actor=user)
            assert first_formwork["created"] + first_formwork["reused"] == 1 and not first_formwork["edited"]
            assert (await add_slab_formwork_block(db, actor=user))["reused"] == 1
            params[(formwork_id, "formwork.material_area")] = "8"
            params[(formwork_id, "formwork.installation_area")] = "20"
            with_formwork = await create_estimate_preview(db, actor=user,
                foundation_geometry_revision_id=geometry.id, region="qa", terms="qa", accounting_keys=keys,
                parameter_values=params, slab_roles_confirmed=True)
            assert any(line["unit"] == "m2" and line["quantity"] == "8" for line in
                       with_formwork.payload["result"]["materials"])
            assert any(line["unit"] == "m2" and line["quantity"] == "20" for line in
                       with_formwork.payload["result"]["works"])
            revised_geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"geometry.net_area": "60", "geometry.slab_thickness": "0.2"},
                project_values={}, expected_version=1)
            revised = await create_estimate_preview(db, actor=user,
                foundation_geometry_revision_id=revised_geometry.id, region="qa", terms="qa", accounting_keys=keys,
                parameter_values=params, slab_roles_confirmed=True)
            assert next(line["quantity"] for line in revised.payload["result"]["materials"]
                        if line["binding"]["block_id"] == block) == "12.0"
            assert next(line["quantity"] for line in revised.payload["result"]["works"]
                        if line["binding"]["block_id"] == block) == "12.0"
            saved = await read_estimate_preview(db, actor=user, snapshot_id=with_formwork.id)
            assert next(line["quantity"] for line in saved.payload["result"]["materials"]
                        if line["binding"]["block_id"] == block) == "10.0"
            assert not revised.payload["result"]["complete"]
            row = await db.get(TechnologyCalculationBlock, uuid.UUID(_id(tech.id, "block", "lower_x")))
            altered = copy.deepcopy(row.definition)
            altered["parameters"][0]["label"] = "Изменённый параметр"
            row.definition = altered
            await db.flush()
            changed = await create_estimate_preview(db, actor=user,
                foundation_geometry_revision_id=geometry.id, region="qa", terms="qa", accounting_keys=keys,
                parameter_values=params, slab_roles_confirmed=True)
            assert sum("POTENTIAL_DOUBLE_COUNT" in line["issues"] for line in
                       changed.payload["result"]["materials"]) == 4
            await db.rollback()
    finally:
        await engine.dispose()
