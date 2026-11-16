"""Attach explicitly selected base-preparation blocks to foundation drafts."""
from __future__ import annotations

import uuid

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_fnd3_ushp_blocks import (GEOTEXTILE_WORK, PREPARATION_ROLES, PREPARATION_WORKS,
                                                    geotextile_block, preparation_block)

SCOPES = {"FND_UFF": "uff", "FND_STRIP_MONOLITHIC_RC": "strip", "FND_SLAB_MONOLITHIC_RC": "slab"}


async def add_base_preparation_blocks(db, *, actor: object, technology_code: str) -> dict:
    if db.bind.dialect.name != "postgresql" or technology_code not in SCOPES:
        raise ValueError("Base preparation requires an explicitly supported PostgreSQL foundation draft")
    scope = SCOPES[technology_code]
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:lock))"), {"lock": f"atom.fnd3.{scope}.blocks"})
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == technology_code, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one foundation draft")
    technology = technologies[0]
    role_codes = (*PREPARATION_ROLES.values(), "FND2_BASE_04")
    work_codes = (*PREPARATION_WORKS.values(), GEOTEXTILE_WORK)
    role_rows = (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(role_codes)))).all()
    work_rows = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code.in_(work_codes)))).all()
    roles = {row.code: row for row in role_rows}
    steps = {row.work_code: row for row in work_rows}
    if (len(role_rows) != len(role_codes) or set(roles) != set(role_codes) or
            any(role.canonical_material_id is None for role in roles.values()) or
            len(work_rows) != len(work_codes) or set(steps) != set(work_codes)):
        raise ValueError("Base preparation requires explicit M1 materials and work selections")
    blocks = [preparation_block(technology.id, code, roles[PREPARATION_ROLES[code]], steps[work_code], scope=scope)
              for code, work_code in PREPARATION_WORKS.items()]
    blocks.append(geotextile_block(technology.id, roles["FND2_BASE_04"], steps[GEOTEXTILE_WORK], scope=scope))
    created, reused, edited = 0, 0, []
    for block in blocks:
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
