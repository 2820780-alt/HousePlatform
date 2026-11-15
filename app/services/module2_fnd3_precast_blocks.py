"""Precast layout quantities and explicit mortar for the existing FBS/FL draft."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.material import Material
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_STRIP_PRECAST_FBS_FL"
FBS_WORK = "foundations_concrete_montazh_blokov_fbs"
FL_WORK = "foundations_concrete_montazh_fundamentnyh_plit_fl"
MORTAR_WORK = "fnd2_ed1ae935010a5f1488bd48f73f277b95"
FBS_ROLES = {"FBS_MAIN": ("main", "layout.fbs_main"), "FBS_SHORT": ("short", "layout.fbs_short"),
             "FBS_SHORTER": ("shorter", "layout.fbs_shorter")}
FL_ROLE = "FND2_FL_12"
MORTAR_ROLE = "FND2_RM_01"


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/precast/{group}/{part}"))


def fbs_material(technology_id: uuid.UUID, code: str, role, name: str) -> CalculationBlock:
    key, input_key = FBS_ROLES[code]
    count = CalculationNode(_id(technology_id, key, "count"), "INPUT", "piece", input_key=input_key)
    return CalculationBlock(id=_id(technology_id, key, "block"), name=name, nodes=(count,), outputs=(count.id,),
        parameters=(BlockParameter(input_key, "Количество блоков по раскладке", "piece", minimum=Decimal(0)),),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id), material_output_id=count.id)


def fbs_work(technology_id: uuid.UUID, step) -> CalculationBlock:
    nodes = [CalculationNode(_id(technology_id, "fbs-work", key), "INPUT", "piece", input_key=input_key)
             for key, input_key in FBS_ROLES.values()]
    subtotal = CalculationNode(_id(technology_id, "fbs-work", "subtotal"), "ADD", "piece", inputs=(nodes[0].id, nodes[1].id))
    total = CalculationNode(_id(technology_id, "fbs-work", "total"), "ADD", "piece", inputs=(subtotal.id, nodes[2].id))
    return CalculationBlock(id=_id(technology_id, "fbs-work", "block"), name="Монтаж блоков ФБС",
        nodes=tuple(nodes) + (subtotal, total), outputs=(total.id,),
        parameters=tuple(BlockParameter(input_key, "Количество блоков по раскладке", "piece", minimum=Decimal(0))
                         for _, input_key in FBS_ROLES.values()),
        work_code=step.work_code, work_step_id=str(step.id), work_output_id=total.id)


def fl_block(technology_id: uuid.UUID, role, step, name: str) -> CalculationBlock:
    count = CalculationNode(_id(technology_id, "fl", "count"), "INPUT", "piece", input_key="layout.fl")
    return CalculationBlock(id=_id(technology_id, "fl", "block"), name=name, nodes=(count,), outputs=(count.id,),
        parameters=(BlockParameter("layout.fl", "Количество плит ФЛ по раскладке", "piece", minimum=Decimal(0)),),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=count.id, work_output_id=count.id)


def mortar_block(technology_id: uuid.UUID, role, step, name: str) -> CalculationBlock:
    volume = CalculationNode(_id(technology_id, "mortar", "volume"), "INPUT", "m3", input_key="mortar.volume")
    return CalculationBlock(id=_id(technology_id, "mortar", "block"), name=name, nodes=(volume,), outputs=(volume.id,),
        parameters=(BlockParameter("mortar.volume", "Объём раствора по раскладке и швам", "m3", minimum=Decimal(0)),),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        work_code=step.work_code, work_step_id=str(step.id), material_output_id=volume.id, work_output_id=volume.id)


async def expected_blocks(db, technology):
    codes = (*FBS_ROLES, FL_ROLE, MORTAR_ROLE)
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(codes)))).all()}
    rows = (await db.scalars(select(TechnologyWorkStep).where(TechnologyWorkStep.technology_id == technology.id,
        TechnologyWorkStep.work_code.in_((FBS_WORK, FL_WORK, MORTAR_WORK))))).all()
    steps = {row.work_code: row for row in rows}
    if (set(roles) != set(codes) or any(role.canonical_material_id is None for role in roles.values()) or
            len(rows) != 3 or set(steps) != {FBS_WORK, FL_WORK, MORTAR_WORK}):
        raise ValueError("Precast roles or works require explicit M1 selections")
    materials = {row.id: row for row in (await db.scalars(select(Material).where(
        Material.id.in_([role.canonical_material_id for role in roles.values()])))).all()}
    if len(materials) != len(roles):
        raise ValueError("Precast roles must refer to distinct existing materials")
    blocks = tuple(fbs_material(technology.id, code, roles[code], materials[roles[code].canonical_material_id].canonical_name)
                   for code in FBS_ROLES)
    return blocks + (fbs_work(technology.id, steps[FBS_WORK]),
        fl_block(technology.id, roles[FL_ROLE], steps[FL_WORK], materials[roles[FL_ROLE].canonical_material_id].canonical_name),
        mortar_block(technology.id, roles[MORTAR_ROLE], steps[MORTAR_WORK], materials[roles[MORTAR_ROLE].canonical_material_id].canonical_name))


async def add_precast_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Precast setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.precast.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one precast draft")
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
