"""Explicit grillage geometry, pile selection and bundled-work scope."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.material import Material
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_PILE_GRILLAGE"
BUNDLE_WORK = "foundations_concrete_ustroystvo_svayno_rostverkovogo_fundamenta"
PILE_ROLES = {"FND2_PILE_RC_01":"factory_6", "FND2_PILE_RC_02":"factory_8",
              "FND2_PILE_S_01":"screw_89", "FND2_PILE_S_02":"screw_108", "FND2_PILE_S_03":"screw_108_long"}
REBAR_ROLES = {"REBAR_TOP": "Верхняя продольная арматура ростверка",
               "REBAR_BOTTOM": "Нижняя продольная арматура ростверка", "STIRRUPS": "Хомуты ростверка"}
CONCRETE_ROLE = "FND2_BT_02"


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/grillage/{group}/{part}"))


def material_block(technology_id: uuid.UUID, code: str, role, name: str) -> CalculationBlock:
    key = PILE_ROLES[code]
    count = CalculationNode(_id(technology_id,key,"count"), "INPUT", "piece", input_key=f"{key}.count")
    return CalculationBlock(id=_id(technology_id,key,"block"), name=name, nodes=(count,), outputs=(count.id,),
        parameters=(BlockParameter(f"{key}.count", "Количество свай этого исполнения", "piece", minimum=Decimal(0)),),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id), material_output_id=count.id)


def rebar_block(technology_id: uuid.UUID, code: str, role) -> CalculationBlock:
    key = code.lower()
    def node(part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id,key,part), operation, unit, **kwargs)
    length = node("length","INPUT","m",input_key=f"{key}.length")
    count = node("count","INPUT","piece",input_key=f"{key}.count")
    lap = node("lap","INPUT","m",input_key=f"{key}.lap_length")
    joints = node("joints","INPUT","piece",input_key=f"{key}.lap_count")
    bars = node("bars","MULTIPLY","m",inputs=(length.id,count.id))
    laps = node("laps","MULTIPLY","m",inputs=(lap.id,joints.id))
    total = node("total","ADD","m",inputs=(bars.id,laps.id))
    return CalculationBlock(id=_id(technology_id,key,"block"), name=REBAR_ROLES[code],
        nodes=(length,count,lap,joints,bars,laps,total), outputs=(total.id,),
        parameters=(BlockParameter(f"{key}.length","Длина одного элемента","m",minimum=Decimal(0)),
                    BlockParameter(f"{key}.count","Общее количество элементов","piece",minimum=Decimal(0)),
                    BlockParameter(f"{key}.lap_length","Длина одного нахлёста","m",minimum=Decimal(0)),
                    BlockParameter(f"{key}.lap_count","Общее число нахлёстов","piece",minimum=Decimal(0))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id), material_output_id=total.id)


def concrete_block(technology_id: uuid.UUID, role) -> CalculationBlock:
    def node(part,operation,unit,**kwargs):
        return CalculationNode(_id(technology_id,"concrete",part),operation,unit,**kwargs)
    length=node("length","INPUT","m",input_key="geometry.length")
    width=node("width","INPUT","m",input_key="geometry.width")
    height=node("height","INPUT","m",input_key="geometry.height")
    overlap=node("overlap","INPUT","m3",input_key="strip.overlap_volume")
    gross=node("gross","PRISM_VOLUME","m3",inputs=(length.id,width.id,height.id))
    total=node("total","SUBTRACT","m3",inputs=(gross.id,overlap.id))
    return CalculationBlock(id=_id(technology_id,"concrete","block"),name="Бетон ростверка",
        nodes=(length,width,height,overlap,gross,total),outputs=(total.id,),
        parameters=tuple(BlockParameter(key,label,unit,minimum=Decimal(0)) for key,label,unit in (
            ("geometry.length","Суммарная длина ростверка","m"), ("geometry.width","Ширина ростверка","m"),
            ("geometry.height","Высота ростверка","m"), ("strip.overlap_volume","Объём пересечений ростверка","m3"))),
        material_id=str(role.canonical_material_id),material_requirement_id=str(role.id),material_output_id=total.id)


def work_block(technology_id: uuid.UUID, step) -> CalculationBlock:
    length=CalculationNode(_id(technology_id,"bundle","length"),"INPUT","m",input_key="geometry.length")
    return CalculationBlock(id=_id(technology_id,"bundle","block"),name="Комплексная работа по свайно-ростверковому фундаменту",
        nodes=(length,),outputs=(length.id,),
        parameters=(BlockParameter("geometry.length","Суммарная длина ростверка","m",minimum=Decimal(0)),),
        work_code=step.work_code,work_step_id=str(step.id),work_output_id=length.id)


async def expected_blocks(db, technology):
    codes=(*PILE_ROLES,*REBAR_ROLES,CONCRETE_ROLE)
    roles={row.code:row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id==technology.id,TechnologyMaterialRequirement.code.in_(codes)))).all()}
    steps=(await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id==technology.id,TechnologyWorkStep.work_code==BUNDLE_WORK))).all()
    if set(roles)!=set(codes) or any(role.canonical_material_id is None for role in roles.values()) or len(steps)!=1:
        raise ValueError("Grillage roles or bundled work require explicit M1 selections")
    materials={row.id:row for row in (await db.scalars(select(Material).where(
        Material.id.in_([roles[code].canonical_material_id for code in PILE_ROLES])))).all()}
    if len(materials)!=len(PILE_ROLES):
        raise ValueError("Grillage pile variants must refer to distinct existing materials")
    return (tuple(material_block(technology.id,code,roles[code],materials[roles[code].canonical_material_id].canonical_name)
                  for code in PILE_ROLES) +
            tuple(rebar_block(technology.id,code,roles[code]) for code in REBAR_ROLES) +
            (concrete_block(technology.id,roles[CONCRETE_ROLE]),work_block(technology.id,steps[0])))


async def add_grillage_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name!="postgresql":
        raise ValueError("Grillage setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.grillage.blocks'))"))
    technologies=(await db.scalars(select(Technology).where(
        Technology.technology_code==TECHNOLOGY_CODE,Technology.status=="DRAFT").with_for_update())).all()
    if len(technologies)!=1:
        raise ValueError("Expected one grillage draft")
    technology=technologies[0]
    created,reused,edited=0,0,[]
    for block in await expected_blocks(db,technology):
        existing=await db.get(TechnologyCalculationBlock,uuid.UUID(block.id))
        if existing:
            changed=(existing.technology_id!=technology.id or existing.definition!=encode_definition(block) or
                     existing.name!=block.name or str(existing.material_id or "")!=(block.material_id or "") or
                     (existing.work_code or None)!=block.work_code)
            if changed:
                edited.append(block.name)
            else:
                reused+=1
            continue
        await add_block(db,technology_id=technology.id,block=block,actor=actor,actor_id=getattr(actor,"id",None))
        created+=1
    return {"technology_id":str(technology.id),"created":created,"reused":reused,"edited":edited}
