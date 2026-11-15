"""Preliminary bored-pile concrete and drilling blocks, without design defaults."""
from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_presets import cylindrical_piles_volume_block
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_PILE_BORED_RC"
CONCRETE_ROLE = "FND2_BT_03"
DRILLING_WORK = "foundations_concrete_burenie_pod_svai"
POURING_WORK = "foundations_concrete_betonirovanie_konstrukciy"
REBAR_WORK = "reinforcement_armirovanie_fundamenta"
REBAR_ROLES = {"PILE_LONGITUDINAL": "Продольная арматура свай", "STIRRUPS": "Хомуты свай"}


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/bored-pile/{group}/{part}"))


def pile_blocks(technology_id: uuid.UUID, role, drilling, pouring):
    def build(group, name, material, step, material_output, work_output):
        preset = cylindrical_piles_volume_block(name=name)
        mapping = {node.id: _id(technology_id, group, str(index)) for index, node in enumerate(preset.nodes)}
        nodes = tuple(replace(node, id=mapping[node.id], inputs=tuple(mapping[item] for item in node.inputs))
                      for node in preset.nodes)
        return replace(preset, id=_id(technology_id, group, "block"), name=name, nodes=nodes,
            outputs=tuple(mapping[item] for item in preset.outputs),
            material_id=str(material.canonical_material_id) if material else None,
            material_requirement_id=str(material.id) if material else None,
            work_code=step.work_code, work_step_id=str(step.id),
            material_output_id=mapping[preset.outputs[material_output]] if material_output is not None else None,
            work_output_id=mapping[preset.outputs[work_output]])
    return (build("concrete-drilling", "Бетон и бурение свай", role, drilling, 0, 1),
            build("pouring", "Бетонирование свай", None, pouring, None, 0))


def reinforcement_block(technology_id: uuid.UUID, code: str, role, step) -> CalculationBlock:
    key = code.lower()
    def node(part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id, key, part), operation, unit, **kwargs)
    length = node("length", "INPUT", "m", input_key=f"{key}.length")
    count = node("count", "INPUT", "piece", input_key=f"{key}.count")
    lap = node("lap", "INPUT", "m", input_key=f"{key}.lap_length")
    joints = node("joints", "INPUT", "piece", input_key=f"{key}.lap_count")
    mass_per_m = node("mass_per_m", "INPUT", "kg_per_m", input_key=f"{key}.mass_per_m")
    bars = node("bars", "MULTIPLY", "m", inputs=(length.id, count.id))
    laps = node("laps", "MULTIPLY", "m", inputs=(lap.id, joints.id))
    total = node("total", "ADD", "m", inputs=(bars.id, laps.id))
    mass = node("mass", "MULTIPLY", "kg", inputs=(total.id, mass_per_m.id))
    return CalculationBlock(id=_id(technology_id, key, "block"), name=REBAR_ROLES[code],
        nodes=(length, count, lap, joints, mass_per_m, bars, laps, total, mass), outputs=(total.id, mass.id),
        parameters=(BlockParameter(f"{key}.length", "Длина одного элемента", "m", minimum=Decimal(0)),
                    BlockParameter(f"{key}.count", "Общее количество элементов", "piece", minimum=Decimal(0)),
                    BlockParameter(f"{key}.lap_length", "Длина одного нахлёста", "m", minimum=Decimal(0)),
                    BlockParameter(f"{key}.lap_count", "Общее число нахлёстов", "piece", minimum=Decimal(0)),
                    BlockParameter(f"{key}.mass_per_m", "Масса погонного метра", "kg_per_m", minimum=Decimal("0.000001"))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=total.id, work_output_id=mass.id)


async def add_bored_pile_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Bored-pile setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.bored-pile.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one bored-pile draft")
    technology = technologies[0]
    role = await db.scalar(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id, TechnologyMaterialRequirement.code == CONCRETE_ROLE))
    rows = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id,
        TechnologyWorkStep.work_code.in_((DRILLING_WORK, POURING_WORK))))).all()
    steps = {row.work_code: row for row in rows}
    if role is None or role.canonical_material_id is None or len(rows) != 2 or set(steps) != {DRILLING_WORK, POURING_WORK}:
        raise ValueError("Bored-pile concrete or work requires explicit M1 selections")
    created, reused, edited = 0, 0, []
    for block in pile_blocks(technology.id, role, steps[DRILLING_WORK], steps[POURING_WORK]):
        existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
        if existing:
            changed = (existing.technology_id != technology.id or existing.definition != encode_definition(block) or
                       existing.name != block.name or str(existing.material_id or "") != (block.material_id or "") or
                       existing.work_code != block.work_code)
            if changed:
                edited.append(block.name)
            else:
                reused += 1
            continue
        await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
        created += 1
    return {"technology_id": str(technology.id), "created": created, "reused": reused, "edited": edited}


async def add_bored_pile_reinforcement_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Bored-pile setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.bored-pile.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one bored-pile draft")
    technology = technologies[0]
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(REBAR_ROLES)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == REBAR_WORK))).all()
    if set(roles) != set(REBAR_ROLES) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        raise ValueError("Bored-pile reinforcement roles or work require explicit M1 selections")
    created, reused, edited = 0, 0, []
    for code in REBAR_ROLES:
        block = reinforcement_block(technology.id, code, roles[code], steps[0])
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
