"""Explicit allocation of factory piles to existing M1 variants."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.material import Material
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_PILE_DRIVEN_RC"
INSTALL_WORK = "foundations_concrete_pogruzhenie_zhelezobetonnyh_svay"
ROLES = {"FACTORY_PILE": "pile_first", "FND2_PILE_RC_02": "pile_second"}


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/driven-pile/{group}/{part}"))


def material_block(technology_id: uuid.UUID, code: str, role, name: str) -> CalculationBlock:
    key = ROLES[code]
    count = CalculationNode(_id(technology_id, key, "count"), "INPUT", "piece", input_key=f"{key}.count")
    return CalculationBlock(id=_id(technology_id, key, "block"), name=name, nodes=(count,), outputs=(count.id,),
        parameters=(BlockParameter(f"{key}.count", "Количество изделий данного исполнения", "piece", minimum=Decimal(0)),),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id), material_output_id=count.id)


def work_block(technology_id: uuid.UUID, step) -> CalculationBlock:
    count = CalculationNode(_id(technology_id, "work", "count"), "INPUT", "piece", input_key="pile.count")
    return CalculationBlock(id=_id(technology_id, "work", "block"), name="Погружение заводских свай",
        nodes=(count,), outputs=(count.id,), parameters=(BlockParameter("pile.count", "Количество свай", "piece", minimum=Decimal(0)),),
        work_code=step.work_code, work_step_id=str(step.id), work_output_id=count.id)


async def expected_blocks(db, technology):
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(ROLES)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == INSTALL_WORK))).all()
    if set(roles) != set(ROLES) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        raise ValueError("Factory-pile roles or work require explicit M1 selections")
    materials = {row.id: row for row in (await db.scalars(select(Material).where(
        Material.id.in_([role.canonical_material_id for role in roles.values()])))).all()}
    if len(materials) != len(roles):
        raise ValueError("Factory-pile variants must refer to distinct existing materials")
    return tuple(material_block(technology.id, code, roles[code], materials[roles[code].canonical_material_id].canonical_name)
                 for code in ROLES) + (work_block(technology.id, steps[0]),)


async def add_driven_pile_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Factory-pile setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.driven-pile.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one factory-pile draft")
    technology = technologies[0]
    created, reused, edited = 0, 0, []
    for block in await expected_blocks(db, technology):
        existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
        if existing:
            changed = (existing.technology_id != technology.id or existing.definition != encode_definition(block) or
                       existing.name != block.name or str(existing.material_id or "") != (block.material_id or "") or
                       (existing.work_code or None) != block.work_code)
            if changed:
                edited.append(block.name)
            else:
                reused += 1
            continue
        await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
        created += 1
    return {"technology_id": str(technology.id), "created": created, "reused": reused, "edited": edited}
