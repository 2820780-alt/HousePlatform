"""Additional explicitly parameterised XPS and rebar blocks for the USHP draft."""
from __future__ import annotations

import uuid
from dataclasses import replace

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_fnd3_ribbed_slab_blocks import USHP_CODE
from app.services.module2_fnd3_slab_blocks import reinforcement_block
from app.services.module2_fnd3_xps_blocks import material_block, work_block

XPS_WORK = "foundations_concrete_uteplenie_fundamenta"
REBAR_WORK = "reinforcement_armirovanie_plity"
ROLES = ("UNDER_SLAB_XPS", "EDGE_XPS", "SLAB_REBAR")


def ushp_blocks(technology_id: uuid.UUID, roles, steps):
    rebar = replace(reinforcement_block(technology_id, "LOWER_X", roles["SLAB_REBAR"], steps[REBAR_WORK]),
                    name="Арматура плиты УШП")
    return (material_block(technology_id, "UNDER_SLAB_XPS", roles["UNDER_SLAB_XPS"]),
            material_block(technology_id, "EDGE_XPS", roles["EDGE_XPS"]),
            work_block(technology_id, steps[XPS_WORK]), rebar)


async def add_ushp_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("USHP setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.ushp.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == USHP_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one USHP draft")
    technology = technologies[0]
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(ROLES)))).all()}
    rows = (await db.scalars(select(TechnologyWorkStep).where(TechnologyWorkStep.technology_id == technology.id,
        TechnologyWorkStep.work_code.in_((XPS_WORK, REBAR_WORK))))).all()
    steps = {row.work_code: row for row in rows}
    if (set(roles) != set(ROLES) or any(role.canonical_material_id is None for role in roles.values()) or
            len(rows) != 2 or set(steps) != {XPS_WORK, REBAR_WORK}):
        raise ValueError("USHP insulation or reinforcement requires explicit M1 selections")
    created, reused, edited = 0, 0, []
    for block in ushp_blocks(technology.id, roles, steps):
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
