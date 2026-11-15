"""Disjoint slab and rib concrete volumes for the existing ribbed-slab draft."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_SLAB_RIBBED_RC"
CONCRETE_WORK = "foundations_concrete_betonirovanie_konstrukciy"
ROLES = {"SLAB_CONCRETE": "slab", "RIB_CONCRETE": "ribs"}


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/ribbed-slab/{group}/{part}"))


def concrete_block(technology_id: uuid.UUID, code: str, role, step) -> CalculationBlock:
    key = ROLES[code]
    def node(part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id, key, part), operation, unit, **kwargs)
    if code == "SLAB_CONCRETE":
        area = node("area", "INPUT", "m2", input_key="geometry.net_area")
        thickness = node("thickness", "INPUT", "m", input_key="geometry.slab_thickness")
        result = node("volume", "MULTIPLY", "m3", inputs=(area.id, thickness.id))
        nodes = (area, thickness, result)
        params = (BlockParameter("geometry.net_area", "Площадь плиты с учётом вырезов", "m2", minimum=Decimal(0)),
                  BlockParameter("geometry.slab_thickness", "Толщина плиты", "m", minimum=Decimal(0)))
        name = "Бетон плитной части"
    else:
        length = node("length", "INPUT", "m", input_key="geometry.rib_length")
        width = node("width", "INPUT", "m", input_key="geometry.rib_width")
        height = node("height", "INPUT", "m", input_key="geometry.rib_height")
        overlaps = node("overlaps", "INPUT", "m3", input_key="geometry.rib_overlap_volume")
        gross = node("gross", "PRISM_VOLUME", "m3", inputs=(length.id, width.id, height.id))
        result = node("volume", "SUBTRACT", "m3", inputs=(gross.id, overlaps.id))
        nodes = (length, width, height, overlaps, gross, result)
        params = (BlockParameter("geometry.rib_length", "Суммарная длина рёбер", "m", minimum=Decimal(0)),
                  BlockParameter("geometry.rib_width", "Ширина ребра", "m", minimum=Decimal(0)),
                  BlockParameter("geometry.rib_height", "Высота ребра вне плиты", "m", minimum=Decimal(0)),
                  BlockParameter("geometry.rib_overlap_volume", "Объём пересечений рёбер", "m3", minimum=Decimal(0)))
        name = "Бетон рёбер вне плиты"
    return CalculationBlock(id=_id(technology_id, key, "block"), name=name, nodes=nodes, outputs=(result.id,),
        parameters=params, material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=result.id, work_output_id=result.id)


async def expected_blocks(db, technology):
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(ROLES)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == CONCRETE_WORK))).all()
    if set(roles) != set(ROLES) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        raise ValueError("Ribbed-slab concrete roles or work require explicit M1 selections")
    return tuple(concrete_block(technology.id, code, roles[code], steps[0]) for code in ROLES)


async def add_ribbed_slab_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Ribbed-slab setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.ribbed-slab.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one ribbed-slab draft")
    technology = technologies[0]
    created, reused, edited = 0, 0, []
    for block in await expected_blocks(db, technology):
        existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
        if existing:
            changed = (existing.technology_id != technology.id or existing.definition != encode_definition(block) or
                       existing.name != block.name or str(existing.material_id or "") != block.material_id or
                       existing.work_code != block.work_code)
            if changed:
                edited.append(block.name)
            else:
                reused += 1
            continue
        await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
        created += 1
    return {"technology_id": str(technology.id), "created": created, "reused": reused, "edited": edited}
