"""Separate foundation and ground-floor volumes for the existing UFF draft."""
from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode
from app.services.module2_fnd3_slab_blocks import reinforcement_block
from app.services.module2_fnd3_base_preparation import add_base_preparation_blocks
from app.services.module2_fnd3_xps_blocks import material_block, work_block

TECHNOLOGY_CODE = "FND_UFF"
FOUNDATION_WORK = "foundations_concrete_betonirovanie_konstrukciy"
FLOOR_WORK = "fnd2_d0708e07f78c544d821e823b99136780"
XPS_WORK = "foundations_concrete_uteplenie_fundamenta"
REBAR_WORK = "reinforcement_armirovanie_fundamenta"
ROLES = ("FND2_BT_02", "FLOOR_CONCRETE", "FOUNDATION_XPS", "FND2_RA_04")


async def add_uff_preparation_blocks(db, *, actor: object) -> dict:
    return await add_base_preparation_blocks(db, actor=actor, technology_code=TECHNOLOGY_CODE)


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/uff/{group}/{part}"))


def concrete_blocks(technology_id: uuid.UUID, roles, steps):
    def node(group, part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id, group, part), operation, unit, **kwargs)
    length = node("foundation", "length", "INPUT", "m", input_key="geometry.length")
    width = node("foundation", "width", "INPUT", "m", input_key="geometry.width")
    height = node("foundation", "height", "INPUT", "m", input_key="geometry.height")
    overlap = node("foundation", "overlap", "INPUT", "m3", input_key="strip.overlap_volume")
    gross = node("foundation", "gross", "PRISM_VOLUME", "m3", inputs=(length.id, width.id, height.id))
    foundation_volume = node("foundation", "volume", "SUBTRACT", "m3", inputs=(gross.id, overlap.id))
    role, step = roles["FND2_BT_02"], steps[FOUNDATION_WORK]
    foundation = CalculationBlock(id=_id(technology_id, "foundation", "block"), name="Бетон фундаментной части",
        nodes=(length,width,height,overlap,gross,foundation_volume), outputs=(foundation_volume.id,),
        parameters=tuple(BlockParameter(key,label,unit,minimum=Decimal(0)) for key,label,unit in (
            ("geometry.length","Суммарная длина фундаментных участков","m"),
            ("geometry.width","Ширина фундаментной части","m"), ("geometry.height","Высота фундаментной части","m"),
            ("strip.overlap_volume","Объём пересечений фундаментных участков","m3"))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=foundation_volume.id,
        work_output_id=foundation_volume.id)
    area = node("floor", "area", "INPUT", "m2", input_key="geometry.net_area")
    thickness = node("floor", "thickness", "INPUT", "m", input_key="geometry.slab_thickness")
    floor_volume = node("floor", "volume", "MULTIPLY", "m3", inputs=(area.id, thickness.id))
    role, step = roles["FLOOR_CONCRETE"], steps[FLOOR_WORK]
    floor = CalculationBlock(id=_id(technology_id, "floor", "block"), name="Бетон пола по грунту",
        nodes=(area,thickness,floor_volume), outputs=(floor_volume.id,),
        parameters=(BlockParameter("geometry.net_area","Площадь пола без фундаментной части","m2",minimum=Decimal(0)),
                    BlockParameter("geometry.slab_thickness","Толщина пола","m",minimum=Decimal(0))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=floor_volume.id,
        work_output_id=floor_volume.id)
    return foundation, floor


async def expected_blocks(db, technology):
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id, TechnologyMaterialRequirement.code.in_(ROLES)))).all()}
    rows = (await db.scalars(select(TechnologyWorkStep).where(TechnologyWorkStep.technology_id == technology.id,
        TechnologyWorkStep.work_code.in_((FOUNDATION_WORK, FLOOR_WORK, XPS_WORK, REBAR_WORK))))).all()
    steps = {row.work_code: row for row in rows}
    if (set(roles) != set(ROLES) or any(role.canonical_material_id is None for role in roles.values()) or
            len(rows) != 4 or set(steps) != {FOUNDATION_WORK, FLOOR_WORK, XPS_WORK, REBAR_WORK}):
        raise ValueError("UFF roles or work require explicit M1 selections")
    return roles, steps


async def add_uff_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("UFF setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.uff.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one UFF draft")
    technology = technologies[0]
    roles, steps = await expected_blocks(db, technology)
    rebar = replace(reinforcement_block(technology.id, "LOWER_X", roles["FND2_RA_04"], steps[REBAR_WORK]),
                    name="Арматура фундаментной части")
    blocks = concrete_blocks(technology.id, roles, steps) + (
        material_block(technology.id, "FOUNDATION_XPS", roles["FOUNDATION_XPS"]),
        work_block(technology.id, steps[XPS_WORK]), rebar)
    created, reused, edited = 0, 0, []
    for block in blocks:
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
