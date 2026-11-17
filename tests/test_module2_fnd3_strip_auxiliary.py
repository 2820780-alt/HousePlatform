import os
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import TechnologyMaterialRequirement
from app.models.user import User
from app.services.module2_calculation_blocks import decode_definition
from app.services.module2_calculation_graph import evaluate_block
from app.services.module2_fnd3_strip_auxiliary import add_strip_auxiliary_blocks
from app.services.module5_estimate_snapshots import create_estimate_preview, read_estimate_preview
from app.services.module7_strip_geometry import create_object, save_strip_geometry


@pytest.mark.asyncio
async def test_strip_auxiliary_materials_use_explicit_quantities_without_duplicate_work():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = await db.scalar(select(User.id).limit(1))
            actor = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                {"moduleCode": code, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
                for code in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                             "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE")])
            first = await add_strip_auxiliary_blocks(db, actor=actor)
            second = await add_strip_auxiliary_blocks(db, actor=actor)
            assert first["created"] + first["reused"] == 2 and not first["edited"]
            assert second["created"] == 0 and second["reused"] == 2 and not second["edited"]
            rows = (await db.scalars(select(TechnologyCalculationBlock).where(
                TechnologyCalculationBlock.technology_id == uuid.UUID(first["technology_id"])))).all()
            selected = {row.name: row for row in rows if row.name in
                        {"Вязальная проволока", "Фиксаторы защитного слоя"}}
            assert len(selected) == 2 and all(row.work_code is None for row in selected.values())
            wire_role = await db.scalar(select(TechnologyMaterialRequirement).where(
                TechnologyMaterialRequirement.technology_id == uuid.UUID(first["technology_id"]),
                TechnologyMaterialRequirement.code == "FND2_ARM_AUX_01"))
            original_material = wire_role.canonical_material_id
            wire_role.canonical_material_id = selected["Фиксаторы защитного слоя"].material_id
            await db.flush()
            with pytest.raises(ValueError, match="unit does not match"):
                await add_strip_auxiliary_blocks(db, actor=actor)
            wire_role.canonical_material_id = original_material
            await db.flush()
            for name, key, unit, value in (
                ("Вязальная проволока", "wire", "kg", "3.5"),
                ("Фиксаторы защитного слоя", "spacers", "piece", "40"),
            ):
                row = selected[name]
                block = decode_definition(row.definition, block_id=str(row.id), name=row.name,
                                          material_id=str(row.material_id))
                input_key = f"strip_auxiliary.{key}.quantity"
                assert evaluate_block(block, {input_key: (value, unit)})[block.material_output_id].value == Decimal(value)
                assert evaluate_block(block, {})[block.material_output_id].value is None
                assert evaluate_block(block, {input_key: ("0", unit)})[block.material_output_id].value == 0
            obj = await create_object(db, actor=actor, name="QA strip auxiliary")
            geometry = await save_strip_geometry(db, actor=actor, object_id=obj.id,
                technology_id=uuid.UUID(first["technology_id"]), length_m="12", width_m="0.4", height_m="0.8",
                expected_version=0)
            keys = {(str(row.id), kind): f"qa:{row.id}:{kind}" for row in rows for kind in ("MATERIAL", "WORK")}
            wire = str(selected["Вязальная проволока"].id)
            spacers = str(selected["Фиксаторы защитного слоя"].id)
            params = {(wire, "strip_auxiliary.wire.quantity"): "3.5",
                      (spacers, "strip_auxiliary.spacers.quantity"): "40"}
            snapshot = await create_estimate_preview(db, actor=actor, geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params, strip_roles_confirmed=True)
            materials = {line["binding"]["block_id"]: line for line in snapshot.payload["result"]["materials"]}
            assert Decimal(materials[wire]["quantity"]) == Decimal("3.5")
            assert Decimal(materials[spacers]["quantity"]) == Decimal("40")
            assert all(line["binding"]["block_id"] not in {wire, spacers} for line in snapshot.payload["result"]["works"])
            saved = await read_estimate_preview(db, actor=actor, snapshot_id=snapshot.id)
            assert saved.payload["result"]["materials"] == snapshot.payload["result"]["materials"]
            await db.rollback()
    finally:
        await engine.dispose()
