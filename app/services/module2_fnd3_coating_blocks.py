"""Explicit primer and mastic consumption for the coating-waterproofing draft."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_SUBSTRUCTURE_WATERPROOFING_COATING"
COATING_WORK = "foundations_concrete_gidroizolyaciya_fundamenta"
ROLES = {"FND2_WPR_02": ("primer", "Битумный праймер", "liter_per_m2", "liter"),
         "FND2_WPR_01": ("mastic", "Мастика", "kg_per_m2", "kg")}


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/coating/{group}/{part}"))


def coating_block(technology_id: uuid.UUID, code: str, role, step) -> CalculationBlock:
    key, title, rate_unit, amount_unit = ROLES[code]
    area = CalculationNode(_id(technology_id, key, "area"), "INPUT", "m2", input_key="geometry.area")
    rate = CalculationNode(_id(technology_id, key, "rate"), "INPUT", rate_unit, input_key=f"{key}.consumption")
    amount = CalculationNode(_id(technology_id, key, "amount"), "MULTIPLY", amount_unit, inputs=(area.id, rate.id))
    with_work = code == "FND2_WPR_01"
    return CalculationBlock(id=_id(technology_id, key, "block"), name=title,
        nodes=(area, rate, amount), outputs=(amount.id, area.id) if with_work else (amount.id,),
        parameters=(BlockParameter("geometry.area", "Площадь поверхности", "m2", minimum=Decimal(0)),
                    BlockParameter(f"{key}.consumption", "Расход на единицу площади", rate_unit,
                                   minimum=Decimal("0.000001"))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code if with_work else None, work_step_id=str(step.id) if with_work else None,
        material_output_id=amount.id, work_output_id=area.id if with_work else None)


async def add_coating_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Coating setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.coating.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one coating-waterproofing draft")
    technology = technologies[0]
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(ROLES)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == COATING_WORK))).all()
    if set(roles) != set(ROLES) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        raise ValueError("Coating roles or work require explicit M1 selections")
    created, reused, edited = 0, 0, []
    for code in ROLES:
        block = coating_block(technology.id, code, roles[code], steps[0])
        existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
        if existing:
            changed = (existing.technology_id != technology.id or existing.definition != encode_definition(block) or
                       existing.name != block.name or str(existing.material_id or "") != block.material_id or
                       (existing.work_code or None) != block.work_code)
            if changed:
                edited.append(block.name)
            else:
                reused += 1
            continue
        await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
        created += 1
    return {"technology_id": str(technology.id), "created": created, "reused": reused, "edited": edited}
