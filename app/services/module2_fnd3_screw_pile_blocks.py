"""Explicit screw-pile and compatible head allocations for the existing draft."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.material import Material
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode
from app.services.module2_fnd3_work_details import candidates, _resolve

TECHNOLOGY_CODE = "FND_PILE_SCREW"
PILE_WORK = "foundations_concrete_montazh_vintovyh_svay"
HEAD_WORK = "fnd2_958fdc85802355c7adeeb361726ca304"
ROLES = {"FND2_PILE_S_01": "screw_89", "FND2_PILE_S_03": "screw_108_long",
         "SCREW_PILE": "screw_108", "FND2_PILE_S_04": "head_89", "PILE_HEAD": "head_108"}


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/screw-pile/{group}/{part}"))


def material_block(technology_id: uuid.UUID, code: str, role, name: str) -> CalculationBlock:
    key = ROLES[code]
    count = CalculationNode(_id(technology_id, key, "count"), "INPUT", "piece", input_key=f"{key}.count")
    return CalculationBlock(id=_id(technology_id, key, "block"), name=name, nodes=(count,), outputs=(count.id,),
        parameters=(BlockParameter(f"{key}.count", "Количество изделий данного исполнения", "piece", minimum=Decimal(0)),),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id), material_output_id=count.id)


def work_block(technology_id: uuid.UUID, key: str, label: str, input_key: str, step) -> CalculationBlock:
    count = CalculationNode(_id(technology_id, key, "count"), "INPUT", "piece", input_key=input_key)
    return CalculationBlock(id=_id(technology_id, key, "block"), name=label, nodes=(count,), outputs=(count.id,),
        parameters=(BlockParameter(input_key, label, "piece", minimum=Decimal(0)),),
        work_code=step.work_code, work_step_id=str(step.id), work_output_id=count.id)


async def expected_blocks(db, technology):
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(ROLES)))).all()}
    rows = (await db.scalars(select(TechnologyWorkStep).where(TechnologyWorkStep.technology_id == technology.id,
        TechnologyWorkStep.work_code.in_((PILE_WORK, HEAD_WORK))))).all()
    steps = {row.work_code: row for row in rows}
    if (set(roles) != set(ROLES) or any(role.canonical_material_id is None for role in roles.values()) or
            len(rows) != 2 or set(steps) != {PILE_WORK, HEAD_WORK}):
        raise ValueError("Screw-pile roles or work require explicit M1 selections")
    materials = {row.id: row for row in (await db.scalars(select(Material).where(
        Material.id.in_([role.canonical_material_id for role in roles.values()])))).all()}
    if len(materials) != len(roles):
        raise ValueError("Screw-pile variants must refer to distinct existing materials")
    return (tuple(material_block(technology.id, code, roles[code], materials[roles[code].canonical_material_id].canonical_name)
                  for code in ROLES) +
            (work_block(technology.id, "pile_work", "Монтаж винтовых свай", "pile.count", steps[PILE_WORK]),
             work_block(technology.id, "head_work", "Монтаж оголовков свай", "pile.head_count", steps[HEAD_WORK])))


async def add_screw_pile_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Screw-pile setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.screw-pile.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one screw-pile draft")
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


OPTIONAL_WORKS = {
    33: ("weld", "Сварка и монтаж соединений свайной системы", "screw.weld_count", "piece"),
    34: ("corrosion", "Антикоррозионная обработка соединений", "screw.corrosion_area", "m2"),
}


def optional_work_block(technology_id: uuid.UUID, number: int, step) -> CalculationBlock:
    key, title, input_key, unit = OPTIONAL_WORKS[number]
    value = CalculationNode(_id(technology_id, key, "quantity"), "INPUT", unit, input_key=input_key)
    label = "Количество предусмотренных соединений" if number == 33 else "Площадь обрабатываемых соединений"
    return CalculationBlock(id=_id(technology_id, key, "block"), name=title, nodes=(value,), outputs=(value.id,),
        parameters=(BlockParameter(input_key, label, unit, minimum=Decimal(0)),),
        work_code=step.work_code, work_step_id=str(step.id), work_output_id=value.id)


async def expected_optional_work_blocks(db, technology):
    codes = await _resolve(db, candidates(), numbers=set(OPTIONAL_WORKS))
    work_codes = {number: codes[f"FND-WK-{number:03d}"] for number in OPTIONAL_WORKS}
    rows = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code.in_(work_codes.values())))).all()
    steps = {row.work_code: row for row in rows}
    if len(rows) != len(work_codes) or set(steps) != set(work_codes.values()):
        raise ValueError("Optional screw-pile works require existing M1 steps")
    return tuple(optional_work_block(technology.id, number, steps[code]) for number, code in work_codes.items())


async def add_screw_optional_work_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Screw-pile setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.screw-pile.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one screw-pile draft")
    technology = technologies[0]
    created, reused, edited = 0, 0, []
    for block in await expected_optional_work_blocks(db, technology):
        existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
        if existing:
            changed = (existing.technology_id != technology.id or existing.definition != encode_definition(block) or
                       existing.name != block.name or existing.material_id is not None or existing.work_code != block.work_code)
            if changed:
                edited.append(block.name)
            else:
                reused += 1
            continue
        await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
        created += 1
    return {"technology_id": str(technology.id), "created": created, "reused": reused, "edited": edited}
