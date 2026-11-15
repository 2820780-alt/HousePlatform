"""Idempotent preliminary blocks for the existing monolithic slab draft."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_SLAB_MONOLITHIC_RC"
CONCRETE_ROLE = "FND2_BT_02"
CONCRETE_WORK = "foundations_concrete_betonirovanie_konstrukciy"
REBAR_WORK = "reinforcement_armirovanie_plity"
FORMWORK_WORK = "foundations_concrete_montazh_opalubki_fundamenta"
REBAR_ROLES = {"LOWER_X": "Нижняя сетка, направление X", "LOWER_Y": "Нижняя сетка, направление Y",
               "UPPER_X": "Верхняя сетка, направление X", "UPPER_Y": "Верхняя сетка, направление Y"}


def _id(technology_id: uuid.UUID, part: str, group: str = "concrete") -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/slab/{group}/{part}"))


def concrete_block(technology_id: uuid.UUID, role, step) -> CalculationBlock:
    area = CalculationNode(_id(technology_id, "area"), "INPUT", "m2", input_key="geometry.net_area")
    thickness = CalculationNode(_id(technology_id, "thickness"), "INPUT", "m", input_key="geometry.slab_thickness")
    volume = CalculationNode(_id(technology_id, "volume"), "MULTIPLY", "m3", inputs=(area.id, thickness.id))
    return CalculationBlock(id=_id(technology_id, "block"), name="Бетон плитной части",
        nodes=(area, thickness, volume), outputs=(volume.id,),
        parameters=(BlockParameter("geometry.net_area", "Площадь плиты с учётом вырезов", "m2", minimum=Decimal(0)),
                    BlockParameter("geometry.slab_thickness", "Толщина плиты", "m", minimum=Decimal(0))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=volume.id, work_output_id=volume.id)


def reinforcement_block(technology_id: uuid.UUID, code: str, role, step) -> CalculationBlock:
    key = code.lower()
    def node(part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id, part, key), operation, unit, **kwargs)
    length = node("length", "INPUT", "m", input_key=f"{key}.length")
    count = node("count", "INPUT", "piece", input_key=f"{key}.count")
    lap = node("lap", "INPUT", "m", input_key=f"{key}.lap_length")
    joints = node("joints", "INPUT", "piece", input_key=f"{key}.lap_count")
    mass_per_m = node("mass_per_m", "INPUT", "kg_per_m", input_key=f"{key}.mass_per_m")
    bars = node("bars", "MULTIPLY", "m", inputs=(length.id, count.id))
    lap_total = node("lap_total", "MULTIPLY", "m", inputs=(lap.id, joints.id))
    total = node("total", "ADD", "m", inputs=(bars.id, lap_total.id))
    mass = node("mass", "MULTIPLY", "kg", inputs=(total.id, mass_per_m.id))
    return CalculationBlock(id=_id(technology_id, "block", key), name=REBAR_ROLES[code],
        nodes=(length, count, lap, joints, mass_per_m, bars, lap_total, total, mass), outputs=(total.id, mass.id),
        parameters=(BlockParameter(f"{key}.length", "Длина одного стержня", "m", minimum=Decimal(0)),
                    BlockParameter(f"{key}.count", "Количество стержней", "piece", minimum=Decimal(0)),
                    BlockParameter(f"{key}.lap_length", "Длина одного нахлёста", "m", minimum=Decimal(0)),
                    BlockParameter(f"{key}.lap_count", "Общее число нахлёстов", "piece", minimum=Decimal(0)),
                    BlockParameter(f"{key}.mass_per_m", "Масса погонного метра", "kg_per_m", minimum=Decimal("0.000001"))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=total.id, work_output_id=mass.id)


def formwork_block(technology_id: uuid.UUID, role, step) -> CalculationBlock:
    material = CalculationNode(_id(technology_id, "material", "formwork"), "INPUT", "m2",
                               input_key="formwork.material_area")
    work = CalculationNode(_id(technology_id, "work", "formwork"), "INPUT", "m2",
                           input_key="formwork.installation_area")
    return CalculationBlock(id=_id(technology_id, "block", "formwork"), name="Краевая опалубка",
        nodes=(material, work), outputs=(material.id, work.id),
        parameters=(BlockParameter("formwork.material_area", "Площадь приобретаемой фанеры", "m2", minimum=Decimal(0)),
                    BlockParameter("formwork.installation_area", "Площадь монтажа опалубки", "m2", minimum=Decimal(0))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=material.id, work_output_id=work.id)


async def add_slab_concrete_block(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Slab setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.slab.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one slab-foundation draft")
    technology = technologies[0]
    role = await db.scalar(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id, TechnologyMaterialRequirement.code == CONCRETE_ROLE))
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == CONCRETE_WORK))).all()
    if role is None or role.canonical_material_id is None or len(steps) != 1:
        raise ValueError("Slab concrete role or work requires an explicit M1 selection")
    block = concrete_block(technology.id, role, steps[0])
    existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
    if existing:
        edited = (existing.technology_id != technology.id or existing.definition != encode_definition(block) or
                  existing.name != block.name or str(existing.material_id or "") != block.material_id or
                  existing.work_code != block.work_code)
        return {"technology_id": str(technology.id), "created": 0, "reused": int(not edited),
                "edited": [block.name] if edited else []}
    await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
    return {"technology_id": str(technology.id), "created": 1, "reused": 0, "edited": []}


async def add_slab_reinforcement_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Slab setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.slab.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one slab-foundation draft")
    technology = technologies[0]
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(REBAR_ROLES)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == REBAR_WORK))).all()
    if set(roles) != set(REBAR_ROLES) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        raise ValueError("Slab reinforcement roles or work require explicit M1 selections")
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


async def add_slab_formwork_block(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Slab setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.slab.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one slab-foundation draft")
    technology = technologies[0]
    role = await db.scalar(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code == "FND2_FORM_01"))
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == FORMWORK_WORK))).all()
    if role is None or role.canonical_material_id is None or len(steps) != 1:
        raise ValueError("Slab formwork role or work requires an explicit M1 selection")
    block = formwork_block(technology.id, role, steps[0])
    existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
    if existing:
        edited = (existing.technology_id != technology.id or existing.definition != encode_definition(block) or
                  existing.name != block.name or str(existing.material_id or "") != block.material_id or
                  existing.work_code != block.work_code)
        return {"technology_id": str(technology.id), "created": 0, "reused": int(not edited),
                "edited": [block.name] if edited else []}
    await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
    return {"technology_id": str(technology.id), "created": 1, "reused": 0, "edited": []}
