"""Explicit casing-work length for the existing bored-pile draft."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode
from app.services.module2_fnd3_bored_pile_blocks import TECHNOLOGY_CODE

CASING_WORK = "fnd2_ef2ce3b7c73656edb5314111f527383b"


def _id(technology_id: uuid.UUID, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/bored-casing/{part}"))


def casing_block(technology_id: uuid.UUID, step) -> CalculationBlock:
    node_id = _id(technology_id, "length")
    return CalculationBlock(id=_id(technology_id, "block"), name="Устройство обсадки скважин",
        nodes=(CalculationNode(node_id, "INPUT", "m", input_key="pile.casing_length"),), outputs=(node_id,),
        parameters=(BlockParameter("pile.casing_length", "Суммарная длина обсадки", "m", minimum=Decimal(0)),),
        work_code=step.work_code, work_step_id=str(step.id), work_output_id=node_id)


async def expected_casing_block(db, technology):
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == CASING_WORK))).all()
    work = await db.get(WorkCatalogItem, CASING_WORK)
    if len(steps) != 1 or work is None or work.default_unit != "linear_meter":
        raise ValueError("Bored casing requires its existing M1 work in linear meters")
    return casing_block(technology.id, steps[0])


async def add_bored_casing_block(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Bored casing setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.bored.casing'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one bored-pile draft")
    technology = technologies[0]
    block = await expected_casing_block(db, technology)
    existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
    if existing:
        changed = (existing.technology_id != technology.id or existing.definition != encode_definition(block)
                   or existing.name != block.name or existing.material_id is not None or existing.work_code != block.work_code)
        return {"technology_id": str(technology.id), "created": 0, "reused": int(not changed),
                "edited": [block.name] if changed else []}
    await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
    return {"technology_id": str(technology.id), "created": 1, "reused": 0, "edited": []}
