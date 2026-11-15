"""Preliminary bored-pile concrete and drilling blocks, without design defaults."""
from __future__ import annotations

import uuid
from dataclasses import replace

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_presets import cylindrical_piles_volume_block

TECHNOLOGY_CODE = "FND_PILE_BORED_RC"
CONCRETE_ROLE = "FND2_BT_03"
DRILLING_WORK = "foundations_concrete_burenie_pod_svai"
POURING_WORK = "foundations_concrete_betonirovanie_konstrukciy"


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
