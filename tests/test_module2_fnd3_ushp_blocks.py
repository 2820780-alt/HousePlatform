import os
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_ribbed_slab_blocks import USHP_CODE, _id as rib_id, add_ribbed_slab_blocks
from app.services.module2_fnd3_slab_blocks import _id as slab_id
from app.services.module2_calculation_graph import evaluate_block, validate_block
from app.services.module2_fnd3_ushp_blocks import add_ushp_blocks, add_ushp_preparation_blocks, preparation_block
from app.services.module2_fnd3_xps_blocks import _id as xps_id
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


def test_ushp_preparation_keeps_supply_and_compacted_work_quantities_separate():
    role = SimpleNamespace(id=uuid.uuid4(), canonical_material_id=uuid.uuid4())
    step = SimpleNamespace(id=uuid.uuid4(), work_code="earthworks_ustroystvo_peschanoy_podushki")
    block = preparation_block(uuid.uuid4(), "SAND", role, step)
    validate_block(block)
    inputs = {"preparation.sand.area": ("50", "m2"), "preparation.sand.thickness": ("0.2", "m"),
              "preparation.sand.supply_factor": ("1.2", "1")}
    result = evaluate_block(block, inputs)
    assert result[block.work_output_id].value == Decimal("10.0")
    assert result[block.material_output_id].value == Decimal("12.00")
    changed = evaluate_block(block, {**inputs, "preparation.sand.thickness": ("0.3", "m")})
    assert changed[block.work_output_id].value == Decimal("15.0")
    assert changed[block.material_output_id].value == Decimal("18.00")
    missing = evaluate_block(block, {key: value for key, value in inputs.items() if not key.endswith("supply_factor")})
    assert missing[block.material_output_id].value is None
    assert missing[block.work_output_id].value == Decimal("10.0")


@pytest.mark.asyncio
async def test_ushp_preparation_uses_existing_roles_and_is_idempotent():
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
            first = await add_ushp_preparation_blocks(db, actor=user)
            second = await add_ushp_preparation_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 2 and not first["edited"]
            assert second["reused"] == 2 and not second["edited"]
            technology = await db.get(Technology, uuid.UUID(first["technology_id"]))
            obj = await create_object(db, actor=user, name="QA USHP preparation")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=technology.id,
                user_values={"geometry.net_area": "50", "geometry.slab_thickness": "0.2"},
                project_values={}, expected_version=0)
            identifiers = {code: str(uuid.uuid5(uuid.NAMESPACE_URL,
                f"atom/fnd3/{technology.id}/ushp/preparation/{code}/block")) for code in ("sand", "gravel")}
            blocks = (await db.scalars(select(TechnologyCalculationBlock).where(
                TechnologyCalculationBlock.technology_id == technology.id))).all()
            keys = {(str(item.id), kind): f"{item.id}-{kind.lower()}" for item in blocks
                    for kind, resource in (("MATERIAL", item.material_id), ("WORK", item.work_code)) if resource}
            params = {(identifiers[code], f"preparation.{code}.{key}"): value
                      for code in identifiers for key, value in (("area", "50"), ("thickness", "0.2"),
                                                                  ("supply_factor", "1.2"))}
            result = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params)
            for code, identifier in identifiers.items():
                material = next(line for line in result.payload["result"]["materials"]
                                if line["binding"]["block_id"] == identifier)
                work = next(line for line in result.payload["result"]["works"]
                            if line["binding"]["block_id"] == identifier)
                assert Decimal(material["quantity"]) == Decimal("12")
                assert Decimal(work["quantity"]) == Decimal("10")
                assert material["unit_price"] is None and "NO_PRICE" in material["issues"]
            await db.rollback()
    finally:
        await engine.dispose()


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
            await add_ushp_preparation_blocks(db, actor=user)
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
            for code in ("sand", "gravel"):
                block_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{tech.id}/ushp/preparation/{code}/block"))
                keys[(block_id, "MATERIAL")] = f"{code}-material"
                keys[(block_id, "WORK")] = f"{code}-work"
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
            assert all(quantities[key] == expected for key, expected in
                       {slab:"10.0", ribs:"2.30", insulation:"6.48", edge:"2.16", rebar:"49.0"}.items())
            assert sum(value is None for value in quantities.values()) == 2
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
