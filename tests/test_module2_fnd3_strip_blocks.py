import os
import uuid
import copy
from decimal import Decimal
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.user import User
from app.services.module2_calculation_blocks import decode_definition
from app.services.module2_calculation_graph import evaluate_block
from app.services.module2_fnd3_base_preparation import add_base_preparation_blocks
from app.services.module2_fnd3_strip_blocks import add_strip_blocks
from app.services.module2_fnd3_strip_auxiliary import add_strip_auxiliary_blocks
from app.services.module1_manual_calculation_price import append_manual_price
from app.services.module5_estimate_snapshots import create_estimate_preview, read_estimate_preview
from app.services.module7_strip_geometry import create_object, save_strip_geometry


@pytest.mark.asyncio
async def test_strip_blocks_bind_real_draft_roles_recalculate_and_are_idempotent():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
                owner = await db.scalar(select(User.id).limit(1))
                actor = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                    {"moduleCode": module, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
                    for module in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                                   "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE")])
                first = await add_strip_blocks(db, actor=actor)
                assert first["created"] + first["reused"] == 5 and not first["edited"]
                second = await add_strip_blocks(db, actor=actor)
                assert second["created"] == 0 and second["reused"] == 5 and not second["edited"]
                prep = await add_base_preparation_blocks(db, actor=actor, technology_code="FND_STRIP_MONOLITHIC_RC")
                again = await add_base_preparation_blocks(db, actor=actor, technology_code="FND_STRIP_MONOLITHIC_RC")
                assert prep["created"] + prep["reused"] == 3 and not prep["edited"]
                assert again["created"] == 0 and again["reused"] == 3 and not again["edited"]
                auxiliary = await add_strip_auxiliary_blocks(db, actor=actor)
                assert auxiliary["created"] + auxiliary["reused"] == 2 and not auxiliary["edited"]
                rows = (await db.scalars(select(TechnologyCalculationBlock).where(
                    TechnologyCalculationBlock.technology_id == uuid.UUID(first["technology_id"])))).all()
                blocks = {row.name: decode_definition(row.definition, block_id=str(row.id), name=row.name,
                          material_id=str(row.material_id) if row.material_id else None,
                          work_code=row.work_code) for row in rows}
                concrete = blocks["Бетон ленты"]
                values = {"geometry.length": ("12", "m"), "geometry.width": ("0.4", "m"),
                          "geometry.height": ("0.8", "m"), "strip.overlap_volume": ("0.2", "m3")}
                assert evaluate_block(concrete, values)[concrete.material_output_id].value == Decimal("3.64")
                assert evaluate_block(concrete, {**values, "geometry.width": ("0.5", "m")})[
                    concrete.work_output_id].value == Decimal("4.60")
                assert evaluate_block(concrete, {key: value for key, value in values.items() if key != "strip.overlap_volume"})[
                    concrete.material_output_id].value is None
                top = blocks["Верхняя продольная арматура"]
                top_values = {"rebar_top.length": ("12", "m"), "rebar_top.count": ("4", "piece"),
                              "rebar_top.lap_length": ("0.5", "m"), "rebar_top.lap_count": ("2", "piece"),
                              "rebar_top.mass_per_m": ("0.888", "kg_per_m")}
                assert evaluate_block(top, top_values)[top.material_output_id].value == Decimal("49")
                assert evaluate_block(top, top_values)[top.work_output_id].value == Decimal("43.512")
                assert top.material_requirement_id and top.material_id and top.work_step_id
                stirrups = blocks["Поперечная арматура и хомуты"]
                stirrup_values = {"stirrups.length": ("2", "m"), "stirrups.count": ("30", "piece"),
                                  "stirrups.lap_length": ("0.1", "m"), "stirrups.lap_count": ("30", "piece")}
                assert evaluate_block(stirrups, stirrup_values)[stirrups.material_output_id].value == Decimal("63")
                formwork = blocks["Опалубка"]
                formwork_values = {"formwork.material_area": ("8", "m2"), "formwork.installation_area": ("20", "m2")}
                result = evaluate_block(formwork, formwork_values)
                assert result[formwork.material_output_id].value == Decimal("8")
                assert result[formwork.work_output_id].value == Decimal("20")
                sand = blocks["Песчаная подготовка"]
                sand_values = {"preparation.sand.area": ("20", "m2"), "preparation.sand.thickness": ("0.2", "m"),
                               "preparation.sand.supply_factor": ("1.2", "1")}
                assert evaluate_block(sand, sand_values)[sand.material_output_id].value == Decimal("4.8")
                assert evaluate_block(sand, sand_values)[sand.work_output_id].value == Decimal("4")
                obj = await create_object(db, actor=actor, name="QA strip")
                geometry = await save_strip_geometry(db, actor=actor, object_id=obj.id,
                    technology_id=uuid.UUID(first["technology_id"]), length_m="12", width_m="0.4",
                    height_m="0.8", expected_version=0)
                by_name = {row.name: row for row in rows}
                params = {(str(by_name["Бетон ленты"].id), "strip.overlap_volume"): "0.2",
                          (str(by_name["Опалубка"].id), "formwork.material_area"): "8",
                          (str(by_name["Опалубка"].id), "formwork.installation_area"): "20",
                          (str(by_name["Вязальная проволока"].id), "strip_auxiliary.wire.quantity"): "3.5",
                          (str(by_name["Фиксаторы защитного слоя"].id), "strip_auxiliary.spacers.quantity"): "40"}
                for name, prefix, length, count, lap, laps, mass in (
                    ("Верхняя продольная арматура", "rebar_top", "12", "4", "0.5", "2", "0.888"),
                    ("Нижняя продольная арматура", "rebar_bottom", "12", "4", "0.5", "2", "0.888"),
                    ("Поперечная арматура и хомуты", "stirrups", "2", "30", "0.1", "30", "0.395"),
                ):
                    for key, value in (("length", length), ("count", count), ("lap_length", lap),
                                       ("lap_count", laps), ("mass_per_m", mass)):
                        params[(str(by_name[name].id), f"{prefix}.{key}")] = value
                keys = {(str(row.id), kind): f"qa:{row.id}:{kind}" for row in rows for kind in ("MATERIAL", "WORK")}
                region, terms = "qa-" + uuid.uuid4().hex, "test only"
                no_price = await create_estimate_preview(db, actor=actor, geometry_revision_id=geometry.id,
                    region=region, terms=terms, accounting_keys=keys, parameter_values=params,
                    strip_roles_confirmed=True)
                assert not no_price.payload["result"]["complete"]
                assert all(line["unit_price"] is None and line["line_amount"] is None
                           for line in no_price.payload["result"]["materials"] + no_price.payload["result"]["works"])
                for name, amount in (("Бетон ленты", "1000"), ("Верхняя продольная арматура", "100"),
                                     ("Поперечная арматура и хомуты", "50"), ("Опалубка", "200")):
                    await append_manual_price(db, material_id=by_name[name].material_id, amount=Decimal(amount),
                                              region=region, terms=terms, effective_from=date.today(), actor_id=owner)
                for name, amount in (("Бетон ленты", "500"), ("Верхняя продольная арматура", "40"),
                                     ("Опалубка", "300")):
                    await append_manual_price(db, work_code=by_name[name].work_code, amount=Decimal(amount),
                                              region=region, terms=terms, effective_from=date.today(), actor_id=owner)
                unsafe = await create_estimate_preview(db, actor=actor, geometry_revision_id=geometry.id,
                    region=region, terms=terms, accounting_keys=keys, parameter_values=params)
                assert not unsafe.payload["result"]["complete"]
                assert any("POTENTIAL_DOUBLE_COUNT" in line["issues"]
                           for line in unsafe.payload["result"]["materials"])
                snapshot = await create_estimate_preview(db, actor=actor, geometry_revision_id=geometry.id,
                    region=region, terms=terms, accounting_keys=keys, parameter_values=params,
                    strip_roles_confirmed=True)
                assert not snapshot.payload["result"]["complete"]
                assert "Состав вспомогательных материалов и работ" in snapshot.payload["missing_required_roles"]
                assert snapshot.payload["result"]["known_total"] == "30486.36"
                assert len(snapshot.payload["result"]["materials"]) == 10
                assert len(snapshot.payload["result"]["works"]) == 8
                changed = await save_strip_geometry(db, actor=actor, object_id=obj.id,
                    technology_id=uuid.UUID(first["technology_id"]), length_m="12", width_m="0.5",
                    height_m="0.8", expected_version=1)
                recalculated = await create_estimate_preview(db, actor=actor, geometry_revision_id=changed.id,
                    region=region, terms=terms, accounting_keys=keys, parameter_values=params,
                    strip_roles_confirmed=True)
                assert recalculated.payload["result"]["known_total"] == "31926.36"
                assert (await read_estimate_preview(db, actor=actor, snapshot_id=snapshot.id)).payload[
                    "result"]["known_total"] == "30486.36"
                changed_block = by_name["Верхняя продольная арматура"]
                original_definition = copy.deepcopy(changed_block.definition)
                edited_definition = copy.deepcopy(original_definition)
                edited_definition["parameters"][0]["label"] = "Изменённый пользователем параметр"
                changed_block.definition = edited_definition
                await db.flush()
                altered = await create_estimate_preview(db, actor=actor, geometry_revision_id=geometry.id,
                    region=region, terms=terms, accounting_keys=keys, parameter_values=params,
                    strip_roles_confirmed=True)
                assert not altered.payload["result"]["complete"]
                assert any("POTENTIAL_DOUBLE_COUNT" in line["issues"]
                           for line in altered.payload["result"]["materials"])
                changed_block.definition = original_definition
                await db.flush()
                await db.delete(by_name["Опалубка"])
                await db.flush()
                incomplete = await create_estimate_preview(db, actor=actor, geometry_revision_id=geometry.id,
                    region=region, terms=terms, accounting_keys=keys,
                    parameter_values={key: value for key, value in params.items()
                                      if key[0] != str(by_name["Опалубка"].id)}, strip_roles_confirmed=True)
                assert not incomplete.payload["result"]["complete"]
                assert "Опалубка" in incomplete.payload["missing_required_roles"]
            await transaction.rollback()
    finally:
        await engine.dispose()
