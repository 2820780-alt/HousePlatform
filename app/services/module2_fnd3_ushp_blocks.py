"""Additional explicitly parameterised XPS and rebar blocks for the USHP draft."""
from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode
from app.services.module2_fnd3_ribbed_slab_blocks import USHP_CODE
from app.services.module2_fnd3_slab_blocks import reinforcement_block
from app.services.module2_fnd3_xps_blocks import material_block, work_block

XPS_WORK = "foundations_concrete_uteplenie_fundamenta"
REBAR_WORK = "reinforcement_armirovanie_plity"
ROLES = ("UNDER_SLAB_XPS", "EDGE_XPS", "SLAB_REBAR")
PREPARATION_WORKS = {"SAND": "earthworks_ustroystvo_peschanoy_podushki",
                     "GRAVEL": "earthworks_ustroystvo_schebenochnoy_podushki"}
PREPARATION_ROLES = {"SAND": "FND2_BASE_01", "GRAVEL": "FND2_BASE_02"}


def preparation_block(technology_id: uuid.UUID, code: str, role, step) -> CalculationBlock:
    labels = {"SAND": "Песчаная подготовка", "GRAVEL": "Щебёночная подготовка"}
    label = labels[code]
    prefix = code.lower()
    def node(part, operation, unit, **kwargs):
        identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/ushp/preparation/{prefix}/{part}"))
        return CalculationNode(identifier, operation, unit, **kwargs)
    area = node("area", "INPUT", "m2", input_key=f"preparation.{prefix}.area")
    thickness = node("thickness", "INPUT", "m", input_key=f"preparation.{prefix}.thickness")
    factor = node("factor", "INPUT", "1", input_key=f"preparation.{prefix}.supply_factor")
    work_volume = node("work_volume", "MULTIPLY", "m3", inputs=(area.id, thickness.id))
    material_volume = node("material_volume", "MULTIPLY", "m3", inputs=(work_volume.id, factor.id))
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/ushp/preparation/{prefix}/block"))
    return CalculationBlock(id=identifier, name=label, nodes=(area, thickness, factor, work_volume, material_volume),
        outputs=(material_volume.id, work_volume.id),
        parameters=(BlockParameter(f"preparation.{prefix}.area", "Площадь слоя", "m2", minimum=Decimal(0)),
                    BlockParameter(f"preparation.{prefix}.thickness", "Толщина уплотнённого слоя", "m", minimum=Decimal(0)),
                    BlockParameter(f"preparation.{prefix}.supply_factor", "Коэффициент объёма поставки", "1", minimum=Decimal("0.000001"))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=material_volume.id,
        work_output_id=work_volume.id)


async def add_ushp_preparation_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("USHP setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.ushp.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == USHP_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one USHP draft")
    technology = technologies[0]
    rows = (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(PREPARATION_ROLES.values())))).all()
    roles = {row.code: row for row in rows}
    work_rows = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id,
        TechnologyWorkStep.work_code.in_(PREPARATION_WORKS.values())))).all()
    steps = {row.work_code: row for row in work_rows}
    if (len(rows) != 2 or set(roles) != set(PREPARATION_ROLES.values()) or
            any(role.canonical_material_id is None for role in roles.values()) or
            len(work_rows) != 2 or set(steps) != set(PREPARATION_WORKS.values())):
        raise ValueError(f"USHP preparation selections unavailable: roles={sorted(roles)}, "
                         f"bound={[code for code, role in roles.items() if role.canonical_material_id]}, "
                         f"works={sorted(steps)}, role_count={len(rows)}, work_count={len(work_rows)}")
    created, reused, edited = 0, 0, []
    for code, work_code in PREPARATION_WORKS.items():
        block = preparation_block(technology.id, code, roles[PREPARATION_ROLES[code]], steps[work_code])
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
