from __future__ import annotations

import os
import uuid
from dataclasses import replace
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.services.module2_calculation_blocks import decode_definition, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode, evaluate_block


def _block(material_id=None, work_code=None):
    return CalculationBlock(str(uuid.uuid4()), "Объём", (
        CalculationNode(str(uuid.uuid4()), "INPUT", "m", input_key="geometry.length"),
        CalculationNode(str(uuid.uuid4()), "INPUT", "m", input_key="geometry.width"),
        CalculationNode(str(uuid.uuid4()), "INPUT", "m", input_key="geometry.height"),
    ), (), material_id=material_id, work_code=work_code)


def _complete_block(material_id=None, work_code=None):
    original = _block(material_id, work_code)
    volume = CalculationNode(str(uuid.uuid4()), "PRISM_VOLUME", "m3",
                             inputs=tuple(node.id for node in original.nodes))
    return replace(original, nodes=(*original.nodes, volume), outputs=(volume.id,),
                   material_output_id=volume.id, work_output_id=volume.id, parameters=(
        BlockParameter("geometry.width", "Ширина", "m", Decimal("0.4"), Decimal("0.1"), Decimal("1"),
                       "test fixture", "PRELIMINARY", True),
    ))


def test_definition_round_trip_preserves_decimal_values_and_parameter_provenance():
    original = _complete_block()
    payload = encode_definition(original)
    assert payload["parameters"][0]["default"] == "0.4"
    restored = decode_definition(payload, block_id=original.id, name=original.name)
    assert restored == original
    result = evaluate_block(restored, {"geometry.length": ("10", "m"), "geometry.height": ("0.6", "m")},
                            allow_preliminary_defaults=True)
    assert result[restored.outputs[0]].value == Decimal("2.4")


def test_definition_rejects_unknown_fields_and_float_defaults():
    block = _complete_block()
    payload = encode_definition(block)
    payload["unexpected"] = "code"
    with pytest.raises(ValidationError):
        decode_definition(payload, block_id=block.id, name=block.name)
    payload = encode_definition(block)
    payload["parameters"][0]["default"] = 0.4
    with pytest.raises(ValidationError):
        decode_definition(payload, block_id=block.id, name=block.name)


@pytest.mark.asyncio
async def test_copy_template_and_edit_are_isolated_in_restored_qa_database():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.database import engine as configured_engine
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.models.module2_calculation_block import CalculationBlockTemplate, TechnologyCalculationBlock
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
    from app.services.module1_work_catalog import list_work_items
    from app.services.module1_work_catalog_store import seed_existing_work_catalog
    from app.services.module2_calculation_blocks import (
        add_block, copy_from_technology, copy_from_template, copy_revision_blocks,
        require_verified_calculation_blocks, save_template, update_block, verify_block,
    )

    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            await seed_existing_work_catalog(db)
            materials = (await db.scalars(select(Material).where(Material.status == MaterialStatus.DRAFT).limit(2))).all()
            works = list_work_items()[:2]
            assert len(materials) == len(works) == 2
            first = Technology(id=uuid.uuid4(), technology_code="QA_STRIP_" + uuid.uuid4().hex,
                               revision=1, name="QA strip", status="DRAFT")
            second = Technology(id=uuid.uuid4(), technology_code="QA_SLAB_" + uuid.uuid4().hex,
                                revision=1, name="QA slab", status="DRAFT")
            db.add_all([first, second])
            await db.flush()
            original = _complete_block(str(materials[0].id), works[0].work_code)
            row = await add_block(db, technology_id=first.id, block=original, actor="PLATFORM_ADMIN", actor_id=None)
            with pytest.raises(ValueError, match="Подтвердите источники"):
                await require_verified_calculation_blocks(db, first.id)
            await verify_block(db, technology_id=first.id, block_id=row.id, expected_version=1,
                               source="QA evidence only", actor="PLATFORM_ADMIN", actor_id=None)
            assert row.definition["rule_status"] == "VERIFIED"
            with pytest.raises(ValueError, match="проверенный материал"):
                await require_verified_calculation_blocks(db, first.id)
            materials[0].status = MaterialStatus.VERIFIED
            await db.flush()
            with pytest.raises(ValueError, match="материальную роль"):
                await require_verified_calculation_blocks(db, first.id)
            requirement = TechnologyMaterialRequirement(id=uuid.uuid4(), technology_id=first.id,
                code="QA_MATERIAL", selector_kind="CANONICAL_MATERIAL", canonical_material_id=materials[0].id,
                technical_constraints={})
            db.add(requirement)
            await db.flush()
            verified_graph = decode_definition(row.definition, block_id=str(row.id), name=row.name,
                                               material_id=str(row.material_id), work_code=row.work_code)
            verified_graph = replace(verified_graph, material_requirement_id=str(requirement.id))
            await update_block(db, technology_id=first.id, block_id=row.id, block=verified_graph,
                               expected_version=row.version, actor="PLATFORM_ADMIN", actor_id=None, reviewed=True)
            with pytest.raises(ValueError, match="этап работы"):
                await require_verified_calculation_blocks(db, first.id)
            work_step = TechnologyWorkStep(id=uuid.uuid4(), technology_id=first.id, position=1,
                                           work_code=works[0].work_code, dependency_step_codes=[])
            db.add(work_step)
            await db.flush()
            verified_graph = replace(verified_graph, work_step_id=str(work_step.id))
            await update_block(db, technology_id=first.id, block_id=row.id, block=verified_graph,
                               expected_version=row.version, actor="PLATFORM_ADMIN", actor_id=None, reviewed=True)
            await require_verified_calculation_blocks(db, first.id)
            db.add(TechnologyMaterialRequirement(id=uuid.uuid4(), technology_id=first.id,
                code="QA_AMBIGUOUS", selector_kind="CANONICAL_MATERIAL", canonical_material_id=materials[0].id,
                technical_constraints={}))
            await db.flush()
            await require_verified_calculation_blocks(db, first.id)
            foreign_role = TechnologyMaterialRequirement(id=uuid.uuid4(), technology_id=second.id,
                code="QA_FOREIGN", selector_kind="CANONICAL_MATERIAL", canonical_material_id=materials[0].id,
                technical_constraints={})
            db.add(foreign_role)
            await db.flush()
            with pytest.raises(ValueError, match="belong to this technology"):
                await update_block(db, technology_id=first.id, block_id=row.id,
                    block=replace(verified_graph, material_requirement_id=str(foreign_role.id)),
                    expected_version=row.version, actor="PLATFORM_ADMIN", actor_id=None)
            requirement.canonical_material_id = materials[1].id
            await db.flush()
            with pytest.raises(ValueError, match="differs from the technology requirement"):
                await require_verified_calculation_blocks(db, first.id)
            requirement.canonical_material_id = materials[0].id
            await db.flush()
            revision = Technology(id=uuid.uuid4(), technology_code=first.technology_code,
                                  revision=2, name="QA strip revision", status="DRAFT")
            db.add(revision)
            await db.flush()
            revision_requirement = TechnologyMaterialRequirement(id=uuid.uuid4(), technology_id=revision.id,
                code="QA_MATERIAL", selector_kind="CANONICAL_MATERIAL", canonical_material_id=materials[0].id,
                technical_constraints={})
            revision_step = TechnologyWorkStep(id=uuid.uuid4(), technology_id=revision.id, position=1,
                                               work_code=works[0].work_code, dependency_step_codes=[])
            db.add_all([revision_requirement, revision_step])
            await db.flush()
            assert await copy_revision_blocks(db, source_technology_id=first.id, technology_id=revision.id,
                                              actor="PLATFORM_ADMIN", actor_id=None) == 1
            revision_row = await db.scalar(select(TechnologyCalculationBlock).where(
                TechnologyCalculationBlock.technology_id == revision.id))
            assert revision_row.id != row.id and revision_row.definition["rule_status"] == "VERIFIED"
            assert revision_row.definition["material_requirement_id"] == str(revision_requirement.id)
            assert revision_row.definition["work_step_id"] == str(revision_step.id)
            assert {node["id"] for node in row.definition["nodes"]}.isdisjoint(
                {node["id"] for node in revision_row.definition["nodes"]})
            first.status = "ACTIVE"
            await db.flush()
            with pytest.raises(ValueError, match="only in a DRAFT"):
                await add_block(db, technology_id=first.id, block=_complete_block(),
                                actor="PLATFORM_ADMIN", actor_id=None)
            first.status = "DRAFT"
            await db.flush()
            template = await save_template(db, block_id=row.id, template_key="qa-" + uuid.uuid4().hex,
                                           name="Объём", description=None, actor="PLATFORM_ADMIN", actor_id=None)
            mapping = {"geometry.length": "slab.length", "geometry.width": "slab.width",
                       "geometry.height": "slab.height"}
            copied = await copy_from_template(db, technology_id=second.id, template_id=template.id,
                                              input_mapping=mapping, material_id=materials[1].id,
                                              work_code=works[1].work_code, actor="PLATFORM_ADMIN", actor_id=None)
            direct = await copy_from_technology(db, source_block_id=row.id, technology_id=second.id,
                                                input_mapping=mapping, material_id=materials[0].id,
                                                work_code=works[0].work_code, actor="PLATFORM_ADMIN", actor_id=None)
            direct_graph = decode_definition(direct.definition, block_id=str(direct.id), name=direct.name)
            assert {n.id for n in direct_graph.nodes}.isdisjoint({n.id for n in original.nodes})
            assert {n.id for n in direct_graph.nodes}.isdisjoint(
                {n.id for n in decode_definition(copied.definition, block_id=str(copied.id), name=copied.name).nodes})
            slab = decode_definition(copied.definition, block_id=str(copied.id), name=copied.name,
                                     material_id=str(copied.material_id), work_code=copied.work_code)
            assert {n.id for n in slab.nodes}.isdisjoint({n.id for n in original.nodes})
            slab = replace(slab, parameters=(replace(slab.parameters[0], default=Decimal("0.5")),))
            await update_block(db, technology_id=second.id, block_id=copied.id, block=slab,
                               expected_version=1, actor="PLATFORM_ADMIN", actor_id=None)
            assert decode_definition(row.definition, block_id=str(row.id), name=row.name).parameters[0].default == Decimal("0.4")
            assert slab.rule_status == "PRELIMINARY"
            second_template = await save_template(db, block_id=copied.id, template_key=template.template_key,
                                                  name="Объём", description=None, actor="PLATFORM_ADMIN", actor_id=None)
            assert second_template.version == 2 and template.definition != second_template.definition
            copied_id, template_id, material_id, work_code = copied.id, template.id, materials[1].id, works[1].work_code
            db.expire_all()
            stored = await db.get(TechnologyCalculationBlock, copied_id)
            stored_template = await db.get(CalculationBlockTemplate, template_id)
            assert stored.version == 2 and stored.template_id == stored_template.id
            assert stored.material_id == material_id and stored.work_code == work_code
            await db.rollback()
    finally:
        await engine.dispose()
