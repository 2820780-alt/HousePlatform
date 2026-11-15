"""Disjoint slab and rib concrete volumes for the existing ribbed-slab draft."""
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

TECHNOLOGY_CODE = "FND_SLAB_RIBBED_RC"
USHP_CODE = "FND_SLAB_USHP"
CONCRETE_WORK = "foundations_concrete_betonirovanie_konstrukciy"
REBAR_WORK = "reinforcement_armirovanie_plity"
FORMWORK_WORK = "foundations_concrete_montazh_opalubki_fundamenta"
ROLES = {"SLAB_CONCRETE": "slab", "RIB_CONCRETE": "ribs"}
REBAR_ROLES = {"SLAB_LOWER": ("LOWER_X", "Нижняя арматура плиты"),
               "SLAB_UPPER": ("LOWER_Y", "Верхняя арматура плиты"),
               "RIB_LONGITUDINAL": ("UPPER_X", "Продольная арматура рёбер"),
               "STIRRUPS": ("UPPER_Y", "Хомуты рёбер")}


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/ribbed-slab/{group}/{part}"))


def concrete_block(technology_id: uuid.UUID, code: str, role, step) -> CalculationBlock:
    key = ROLES[code]
    def node(part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id, key, part), operation, unit, **kwargs)
    if code == "SLAB_CONCRETE":
        area = node("area", "INPUT", "m2", input_key="geometry.net_area")
        thickness = node("thickness", "INPUT", "m", input_key="geometry.slab_thickness")
        result = node("volume", "MULTIPLY", "m3", inputs=(area.id, thickness.id))
        nodes = (area, thickness, result)
        params = (BlockParameter("geometry.net_area", "Площадь плиты с учётом вырезов", "m2", minimum=Decimal(0)),
                  BlockParameter("geometry.slab_thickness", "Толщина плиты", "m", minimum=Decimal(0)))
        name = "Бетон плитной части"
    else:
        length = node("length", "INPUT", "m", input_key="geometry.rib_length")
        width = node("width", "INPUT", "m", input_key="geometry.rib_width")
        height = node("height", "INPUT", "m", input_key="geometry.rib_height")
        overlaps = node("overlaps", "INPUT", "m3", input_key="geometry.rib_overlap_volume")
        gross = node("gross", "PRISM_VOLUME", "m3", inputs=(length.id, width.id, height.id))
        result = node("volume", "SUBTRACT", "m3", inputs=(gross.id, overlaps.id))
        nodes = (length, width, height, overlaps, gross, result)
        params = (BlockParameter("geometry.rib_length", "Суммарная длина рёбер", "m", minimum=Decimal(0)),
                  BlockParameter("geometry.rib_width", "Ширина ребра", "m", minimum=Decimal(0)),
                  BlockParameter("geometry.rib_height", "Высота ребра вне плиты", "m", minimum=Decimal(0)),
                  BlockParameter("geometry.rib_overlap_volume", "Объём пересечений рёбер", "m3", minimum=Decimal(0)))
        name = "Бетон рёбер вне плиты"
    return CalculationBlock(id=_id(technology_id, key, "block"), name=name, nodes=nodes, outputs=(result.id,),
        parameters=params, material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=result.id, work_output_id=result.id)


def reinforcement_block(technology_id: uuid.UUID, role_code: str, role, step) -> CalculationBlock:
    template_code, title = REBAR_ROLES[role_code]
    template = slab_reinforcement_block(technology_id, template_code, role, step)
    key, old_key = role_code.lower(), template_code.lower()
    mapping = {item.id: _id(technology_id, key, str(index)) for index, item in enumerate(template.nodes)}
    nodes = tuple(replace(item, id=mapping[item.id], inputs=tuple(mapping[value] for value in item.inputs),
                          input_key=item.input_key.replace(old_key + ".", key + ".", 1) if item.input_key else None)
                  for item in template.nodes)
    parameters = tuple(replace(item, input_key=item.input_key.replace(old_key + ".", key + ".", 1))
                       for item in template.parameters)
    return replace(template, id=_id(technology_id, key, "block"), name=title, nodes=nodes,
                   outputs=tuple(mapping[value] for value in template.outputs), parameters=parameters,
                   material_output_id=mapping[template.material_output_id], work_output_id=mapping[template.work_output_id])


async def expected_blocks(db, technology):
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(ROLES)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == CONCRETE_WORK))).all()
    if set(roles) != set(ROLES) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        raise ValueError("Ribbed-slab concrete roles or work require explicit M1 selections")
    return tuple(concrete_block(technology.id, code, roles[code], steps[0]) for code in ROLES)


async def add_ribbed_slab_blocks(db, *, actor: object, technology_code: str = TECHNOLOGY_CODE) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Ribbed-slab setup requires PostgreSQL transaction locking")
    if technology_code not in {TECHNOLOGY_CODE, USHP_CODE}:
        raise ValueError("Unsupported slab draft")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                     {"key": f"atom.fnd3.ribbed-slab.{technology_code}"})
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == technology_code, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one ribbed-slab draft")
    technology = technologies[0]
    created, reused, edited = 0, 0, []
    for block in await expected_blocks(db, technology):
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


async def add_ribbed_slab_detail_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Ribbed-slab setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                     {"key": f"atom.fnd3.ribbed-slab.{TECHNOLOGY_CODE}"})
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one ribbed-slab draft")
    technology = technologies[0]
    codes = (*REBAR_ROLES, "FND2_FORM_01")
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(codes)))).all()}
    rows = (await db.scalars(select(TechnologyWorkStep).where(TechnologyWorkStep.technology_id == technology.id,
        TechnologyWorkStep.work_code.in_((REBAR_WORK, FORMWORK_WORK))))).all()
    steps = {row.work_code: row for row in rows}
    if (set(roles) != set(codes) or any(role.canonical_material_id is None for role in roles.values()) or
            len(rows) != 2 or set(steps) != {REBAR_WORK, FORMWORK_WORK}):
        raise ValueError("Ribbed-slab reinforcement or formwork requires explicit M1 selections")
    formwork = replace(slab_formwork_block(technology.id, roles["FND2_FORM_01"], steps[FORMWORK_WORK]),
                       name="Опалубка плиты и рёбер")
    blocks = tuple(reinforcement_block(technology.id, code, roles[code], steps[REBAR_WORK]) for code in REBAR_ROLES) + (formwork,)
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
