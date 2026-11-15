"""Explicit non-overlapping membrane coverage with user-supplied laps and roll sizes."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.material import Material
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE"
INSTALL_WORK = "foundations_concrete_gidroizolyaciya_fundamenta"
ROLES = {"FND2_WPR_03": "roll", "FND2_WPR_04": "pvc"}


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/membrane/{group}/{part}"))


def material_block(technology_id: uuid.UUID, code: str, role, name: str) -> CalculationBlock:
    key = ROLES[code]
    def node(part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id, key, part), operation, unit, **kwargs)
    area = node("area", "INPUT", "m2", input_key=f"{key}.coverage_area")
    laps = node("laps", "INPUT", "m2", input_key=f"{key}.overlap_area")
    length = node("length", "INPUT", "m", input_key=f"{key}.roll_length")
    width = node("width", "INPUT", "m", input_key=f"{key}.roll_width")
    zero_area = node("zero_area", "CONSTANT", "m2", constant=Decimal(0))
    zero_count = node("zero_count", "CONSTANT", "piece", constant=Decimal(0))
    active = node("active", "LESS_THAN", "1", inputs=(zero_area.id, area.id))
    gross = node("gross", "ADD", "m2", inputs=(area.id, laps.id))
    roll_area = node("roll_area", "MULTIPLY", "m2", inputs=(length.id, width.id))
    raw = node("raw", "DIVIDE", "1", inputs=(gross.id, roll_area.id))
    rounded = node("rounded", "CEIL", "piece", inputs=(raw.id,))
    purchased = node("purchased", "MULTIPLY", "m2", inputs=(rounded.id, roll_area.id))
    count = node("count", "IF", "piece", inputs=(active.id, rounded.id, zero_count.id))
    material = node("material", "IF", "m2", inputs=(active.id, purchased.id, zero_area.id))
    return CalculationBlock(id=_id(technology_id, key, "block"), name=name,
        nodes=(area, laps, length, width, zero_area, zero_count, active, gross, roll_area, raw, rounded, purchased, count, material),
        outputs=(material.id, count.id),
        parameters=(BlockParameter(f"{key}.coverage_area", "Площадь участка этим материалом", "m2", minimum=Decimal(0)),
                    BlockParameter(f"{key}.overlap_area", "Суммарная площадь нахлёстов", "m2", minimum=Decimal(0)),
                    BlockParameter(f"{key}.roll_length", "Длина одного рулона", "m", minimum=Decimal("0.000001")),
                    BlockParameter(f"{key}.roll_width", "Ширина одного рулона", "m", minimum=Decimal("0.000001"))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id), material_output_id=material.id)


def work_block(technology_id: uuid.UUID, step) -> CalculationBlock:
    area = CalculationNode(_id(technology_id, "work", "area"), "INPUT", "m2", input_key="geometry.area")
    return CalculationBlock(id=_id(technology_id, "work", "block"), name="Монтаж гидроизоляции",
        nodes=(area,), outputs=(area.id,), parameters=(BlockParameter("geometry.area", "Площадь поверхности", "m2", minimum=Decimal(0)),),
        work_code=step.work_code, work_step_id=str(step.id), work_output_id=area.id)


async def expected_blocks(db, technology):
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(ROLES)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == INSTALL_WORK))).all()
    if set(roles) != set(ROLES) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        raise ValueError("Membrane roles or work require explicit M1 selections")
    materials = {row.id: row for row in (await db.scalars(select(Material).where(
        Material.id.in_([role.canonical_material_id for role in roles.values()])))).all()}
    if len(materials) != len(roles):
        raise ValueError("Membrane variants must refer to distinct existing materials")
    return tuple(material_block(technology.id, code, roles[code], materials[roles[code].canonical_material_id].canonical_name)
                 for code in ROLES) + (work_block(technology.id, steps[0]),)


async def add_membrane_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Membrane setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.membrane.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one membrane draft")
    technology = technologies[0]
    created, reused, edited = 0, 0, []
    for block in await expected_blocks(db, technology):
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
