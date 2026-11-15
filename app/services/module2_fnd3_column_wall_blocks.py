"""Preliminary concrete volumes for column and basement-wall drafts."""
from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode
from app.services.module2_fnd3_slab_blocks import (formwork_block as slab_formwork_block,
                                                    reinforcement_block as slab_reinforcement_block)

CONCRETE_WORK = "foundations_concrete_betonirovanie_konstrukciy"
REBAR_WORK = "reinforcement_armirovanie_fundamenta"
FORMWORK_WORK = "foundations_concrete_montazh_opalubki_fundamenta"
ROLES = {"FND_COLUMN_CONCRETE_RC": "FND2_BT_02", "FND_BASEMENT_WALL_MONOLITHIC": "FND2_BT_03"}
REBAR_ROLES = {
    "FND_COLUMN_CONCRETE_RC": {"COLUMN_REBAR": ("LOWER_X", "Продольная арматура опор"),
                               "STIRRUPS": ("LOWER_Y", "Хомуты опор")},
    "FND_BASEMENT_WALL_MONOLITHIC": {
        "INNER_VERTICAL": ("LOWER_X", "Внутренняя вертикальная арматура"),
        "INNER_HORIZONTAL": ("LOWER_Y", "Внутренняя горизонтальная арматура"),
        "OUTER_VERTICAL": ("UPPER_X", "Наружная вертикальная арматура"),
        "OUTER_HORIZONTAL": ("UPPER_Y", "Наружная горизонтальная арматура")},
}


def _id(technology_id: uuid.UUID, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/concrete/{part}"))


def concrete_block(technology_id: uuid.UUID, code: str, role, step) -> CalculationBlock:
    def node(part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id, part), operation, unit, **kwargs)
    if code == "FND_COLUMN_CONCRETE_RC":
        length = node("length", "INPUT", "m", input_key="element.length")
        width = node("width", "INPUT", "m", input_key="element.width")
        height = node("height", "INPUT", "m", input_key="element.height")
        count = node("count", "INPUT", "piece", input_key="element.count")
        volume = node("one_volume", "PRISM_VOLUME", "m3", inputs=(length.id, width.id, height.id))
        result = node("total", "MULTIPLY", "m3", inputs=(volume.id, count.id))
        nodes = (length, width, height, count, volume, result)
        params = tuple(BlockParameter(key, label, unit, minimum=Decimal(0)) for key, label, unit in (
            ("element.length", "Длина опоры", "m"), ("element.width", "Ширина опоры", "m"),
            ("element.height", "Высота опоры", "m"), ("element.count", "Количество опор", "piece")))
        name = "Бетон одинаковых опор"
    elif code == "FND_BASEMENT_WALL_MONOLITHIC":
        length = node("length", "INPUT", "m", input_key="geometry.wall_length")
        height = node("height", "INPUT", "m", input_key="geometry.wall_height")
        thickness = node("thickness", "INPUT", "m", input_key="geometry.wall_thickness")
        openings = node("openings", "INPUT", "m2", input_key="geometry.opening_area")
        overlap = node("overlap", "INPUT", "m3", input_key="geometry.wall_overlap_volume")
        area = node("area", "MULTIPLY", "m2", inputs=(length.id, height.id))
        net = node("net", "SUBTRACT", "m2", inputs=(area.id, openings.id))
        gross = node("gross", "MULTIPLY", "m3", inputs=(net.id, thickness.id))
        result = node("total", "SUBTRACT", "m3", inputs=(gross.id, overlap.id))
        nodes = (length, height, thickness, openings, overlap, area, net, gross, result)
        params = tuple(BlockParameter(key, label, unit, minimum=Decimal(0)) for key, label, unit in (
            ("geometry.wall_length", "Суммарная длина стен", "m"), ("geometry.wall_height", "Высота стен", "m"),
            ("geometry.wall_thickness", "Толщина стен", "m"), ("geometry.opening_area", "Площадь проёмов", "m2"),
            ("geometry.wall_overlap_volume", "Объём пересечений стен", "m3")))
        name = "Бетон стен подвала"
    else:
        raise ValueError("Unsupported concrete technology")
    return CalculationBlock(id=_id(technology_id, "block"), name=name, nodes=nodes, outputs=(result.id,),
        parameters=params, material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=result.id, work_output_id=result.id)


def reinforcement_block(technology_id: uuid.UUID, technology_code: str, role_code: str, role, step) -> CalculationBlock:
    template_code, title = REBAR_ROLES[technology_code][role_code]
    template = slab_reinforcement_block(technology_id, template_code, role, step)
    key, old_key = role_code.lower(), template_code.lower()
    mapping = {item.id: _id(technology_id, f"rebar/{key}/{index}") for index, item in enumerate(template.nodes)}
    nodes = tuple(replace(item, id=mapping[item.id], inputs=tuple(mapping[value] for value in item.inputs),
                          input_key=item.input_key.replace(old_key + ".", key + ".", 1) if item.input_key else None)
                  for item in template.nodes)
    parameters = tuple(replace(item, input_key=item.input_key.replace(old_key + ".", key + ".", 1))
                       for item in template.parameters)
    return replace(template, id=_id(technology_id, f"rebar/{key}/block"), name=title, nodes=nodes,
                   outputs=tuple(mapping[value] for value in template.outputs), parameters=parameters,
                   material_output_id=mapping[template.material_output_id], work_output_id=mapping[template.work_output_id])


def formwork_block(technology_id: uuid.UUID, technology_code: str, role, step) -> CalculationBlock:
    template = slab_formwork_block(technology_id, role, step)
    mapping = {item.id: _id(technology_id, f"formwork/{index}") for index, item in enumerate(template.nodes)}
    nodes = tuple(replace(item, id=mapping[item.id], inputs=tuple(mapping[value] for value in item.inputs))
                  for item in template.nodes)
    title = "Опалубка опор" if technology_code == "FND_COLUMN_CONCRETE_RC" else "Опалубка стен"
    return replace(template, id=_id(technology_id, "formwork/block"), name=title, nodes=nodes,
                   outputs=tuple(mapping[value] for value in template.outputs),
                   material_output_id=mapping[template.material_output_id], work_output_id=mapping[template.work_output_id])


async def add_column_wall_concrete(db, *, actor: object, technology_code: str) -> dict:
    if technology_code not in ROLES or db.bind.dialect.name != "postgresql":
        raise ValueError("Supported concrete draft and PostgreSQL transaction locking are required")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                     {"key": f"atom.fnd3.concrete.{technology_code}"})
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == technology_code, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one supported concrete draft")
    technology = technologies[0]
    role = await db.scalar(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code == ROLES[technology_code]))
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == CONCRETE_WORK))).all()
    if role is None or role.canonical_material_id is None or len(steps) != 1:
        raise ValueError("Concrete role or work requires an explicit M1 selection")
    block = concrete_block(technology.id, technology_code, role, steps[0])
    existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
    if existing:
        edited = (existing.technology_id != technology.id or existing.definition != encode_definition(block) or
                  existing.name != block.name or str(existing.material_id or "") != block.material_id or
                  existing.work_code != block.work_code)
        return {"technology_id": str(technology.id), "created": 0, "reused": int(not edited),
                "edited": [block.name] if edited else []}
    await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
    return {"technology_id": str(technology.id), "created": 1, "reused": 0, "edited": []}


async def add_column_wall_reinforcement(db, *, actor: object, technology_code: str) -> dict:
    if technology_code not in REBAR_ROLES or db.bind.dialect.name != "postgresql":
        raise ValueError("Supported concrete draft and PostgreSQL transaction locking are required")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                     {"key": f"atom.fnd3.concrete.{technology_code}"})
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == technology_code, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one supported concrete draft")
    technology = technologies[0]
    codes = REBAR_ROLES[technology_code]
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(codes)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == REBAR_WORK))).all()
    if set(roles) != set(codes) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        raise ValueError("Reinforcement roles or work require explicit M1 selections")
    created, reused, edited = 0, 0, []
    for code in codes:
        block = reinforcement_block(technology.id, technology_code, code, roles[code], steps[0])
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


async def add_column_wall_formwork(db, *, actor: object, technology_code: str) -> dict:
    if technology_code not in ROLES or db.bind.dialect.name != "postgresql":
        raise ValueError("Supported concrete draft and PostgreSQL transaction locking are required")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                     {"key": f"atom.fnd3.concrete.{technology_code}"})
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == technology_code, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one supported concrete draft")
    technology = technologies[0]
    role = await db.scalar(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id, TechnologyMaterialRequirement.code == "FND2_FORM_01"))
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == FORMWORK_WORK))).all()
    if role is None or role.canonical_material_id is None or len(steps) != 1:
        raise ValueError("Formwork role or work requires an explicit M1 selection")
    block = formwork_block(technology.id, technology_code, role, steps[0])
    existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
    if existing:
        edited = (existing.technology_id != technology.id or existing.definition != encode_definition(block) or
                  existing.name != block.name or str(existing.material_id or "") != block.material_id or
                  existing.work_code != block.work_code)
        return {"technology_id": str(technology.id), "created": 0, "reused": int(not edited),
                "edited": [block.name] if edited else []}
    await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
    return {"technology_id": str(technology.id), "created": 1, "reused": 0, "edited": []}
