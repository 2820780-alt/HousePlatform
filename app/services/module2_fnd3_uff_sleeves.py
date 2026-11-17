"""Explicitly selected UFF sleeves and their shared installation quantity."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.material import Material
from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.models.unit import Unit
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode
from app.services.module2_fnd3_uff_blocks import TECHNOLOGY_CODE

SLEEVE_WORK = "fnd2_3749943b73115afe81531337383db41e"
ROLES = {"FND2_PEN_01": ("dn110", "Гильза DN110"), "FND2_PEN_02": ("dn160", "Гильза DN160")}


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/uff-sleeves/{group}/{part}"))


def sleeve_material(technology_id: uuid.UUID, code: str, role) -> CalculationBlock:
    key, label = ROLES[code]
    input_key = f"uff.sleeves_{key}"
    node_id = _id(technology_id, key, "quantity")
    return CalculationBlock(id=_id(technology_id, key, "block"), name=label,
        nodes=(CalculationNode(node_id, "INPUT", "piece", input_key=input_key),), outputs=(node_id,),
        parameters=(BlockParameter(input_key, f"Количество: {label.lower()}", "piece", minimum=Decimal(0)),),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id), material_output_id=node_id)


def sleeve_work(technology_id: uuid.UUID, step) -> CalculationBlock:
    inputs = tuple(CalculationNode(_id(technology_id, key, "work-input"), "INPUT", "piece",
                                   input_key=f"uff.sleeves_{key}") for key, _ in ROLES.values())
    total = CalculationNode(_id(technology_id, "work", "total"), "ADD", "piece", inputs=tuple(node.id for node in inputs))
    return CalculationBlock(id=_id(technology_id, "work", "block"), name="Монтаж гильз вводов",
        nodes=inputs + (total,), outputs=(total.id,),
        parameters=tuple(BlockParameter(f"uff.sleeves_{key}", f"Количество: {label.lower()}", "piece", minimum=Decimal(0))
                         for key, label in ROLES.values()),
        work_code=step.work_code, work_step_id=str(step.id), work_output_id=total.id)


async def expected_sleeve_blocks(db, technology):
    rows = (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(ROLES)))).all()
    roles = {row.code: row for row in rows}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == SLEEVE_WORK))).all()
    if len(rows) != len(ROLES) or set(roles) != set(ROLES) or any(
        role.canonical_material_id is None for role in roles.values()
    ) or len(steps) != 1:
        raise ValueError("UFF sleeves require explicit M1 materials and installation work")
    units = dict((await db.execute(select(Material.id, Unit.abbreviation).join(
        Unit, Unit.id == Material.base_unit_id).where(
            Material.id.in_([role.canonical_material_id for role in roles.values()])))).all())
    if len(units) != len(roles) or any(units.get(role.canonical_material_id) != "piece" for role in roles.values()):
        raise ValueError("UFF sleeve materials require distinct M1 cards measured in pieces")
    work = await db.get(WorkCatalogItem, SLEEVE_WORK)
    if work is None or work.default_unit != "piece":
        raise ValueError("UFF sleeve installation work must be measured in pieces")
    return tuple(sleeve_material(technology.id, code, roles[code]) for code in ROLES) + (sleeve_work(technology.id, steps[0]),)


async def add_uff_sleeve_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("UFF sleeve setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.uff.sleeves'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one UFF draft")
    technology = technologies[0]
    created, reused, edited = 0, 0, []
    for block in await expected_sleeve_blocks(db, technology):
        existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
        if existing:
            changed = (existing.technology_id != technology.id or existing.definition != encode_definition(block)
                       or existing.name != block.name or str(existing.material_id or "") != (block.material_id or "")
                       or (existing.work_code or None) != block.work_code)
            if changed:
                edited.append(block.name)
            else:
                reused += 1
            continue
        await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
        created += 1
    return {"technology_id": str(technology.id), "created": created, "reused": reused, "edited": edited}
