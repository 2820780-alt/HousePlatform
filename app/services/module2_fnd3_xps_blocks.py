"""Zone-specific XPS quantities and one installation work for the existing draft."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode

TECHNOLOGY_CODE = "FND_SUBSTRUCTURE_INSULATION_XPS"
INSTALL_WORK = "foundations_concrete_uteplenie_fundamenta"
ROLES = {"WALL_XPS": ("wall", "Утепление стен", "geometry.wall_area"),
         "UNDER_SLAB_XPS": ("slab", "Утепление под плитой", "geometry.slab_area")}
EXTRA_ROLES = {"EDGE_XPS": ("edge", "Утепление торцов", "geometry.edge_area"),
               "FOUNDATION_XPS": ("slab", "Утепление основания", "geometry.slab_area")}


def _id(technology_id: uuid.UUID, group: str, part: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd3/{technology_id}/xps/{group}/{part}"))


def material_block(technology_id: uuid.UUID, code: str, role) -> CalculationBlock:
    key, title, area_key = (ROLES | EXTRA_ROLES)[code]
    def node(part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id, key, part), operation, unit, **kwargs)
    area = node("area", "INPUT", "m2", input_key=area_key)
    length = node("length", "INPUT", "m", input_key=f"xps_{key}.sheet_length")
    width = node("width", "INPUT", "m", input_key=f"xps_{key}.sheet_width")
    zero_area = node("zero_area", "CONSTANT", "m2", constant=Decimal(0))
    zero_count = node("zero_count", "CONSTANT", "piece", constant=Decimal(0))
    active = node("active", "LESS_THAN", "1", inputs=(zero_area.id, area.id))
    sheet_area = node("sheet_area", "MULTIPLY", "m2", inputs=(length.id, width.id))
    raw_count = node("raw_count", "DIVIDE", "1", inputs=(area.id, sheet_area.id))
    rounded = node("rounded", "CEIL", "piece", inputs=(raw_count.id,))
    purchased = node("purchased", "MULTIPLY", "m2", inputs=(rounded.id, sheet_area.id))
    count = node("count", "IF", "piece", inputs=(active.id, rounded.id, zero_count.id))
    material = node("material", "IF", "m2", inputs=(active.id, purchased.id, zero_area.id))
    return CalculationBlock(id=_id(technology_id, key, "block"), name=title,
        nodes=(area, length, width, zero_area, zero_count, active, sheet_area, raw_count, rounded, purchased, count, material),
        outputs=(material.id, count.id),
        parameters=(BlockParameter(area_key, "Площадь зоны", "m2", minimum=Decimal(0)),
                    BlockParameter(f"xps_{key}.sheet_length", "Длина одной плиты", "m", minimum=Decimal("0.000001")),
                    BlockParameter(f"xps_{key}.sheet_width", "Ширина одной плиты", "m", minimum=Decimal("0.000001"))),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id), material_output_id=material.id)


def work_block(technology_id: uuid.UUID, step) -> CalculationBlock:
    def node(part, operation, unit, **kwargs):
        return CalculationNode(_id(technology_id, "work", part), operation, unit, **kwargs)
    wall = node("wall", "INPUT", "m2", input_key="geometry.wall_area")
    slab = node("slab", "INPUT", "m2", input_key="geometry.slab_area")
    edge = node("edge", "INPUT", "m2", input_key="geometry.edge_area")
    subtotal = node("subtotal", "ADD", "m2", inputs=(wall.id, slab.id))
    total = node("total", "ADD", "m2", inputs=(subtotal.id, edge.id))
    return CalculationBlock(id=_id(technology_id, "work", "block"), name="Монтаж теплоизоляции",
        nodes=(wall, slab, edge, subtotal, total), outputs=(total.id,),
        parameters=tuple(BlockParameter(key, label, "m2", minimum=Decimal(0)) for key, label in (
            ("geometry.wall_area", "Площадь стен"), ("geometry.slab_area", "Площадь под плитой"),
            ("geometry.edge_area", "Площадь торцов"))),
        work_code=step.work_code, work_step_id=str(step.id), work_output_id=total.id)


async def add_xps_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("XPS setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.xps.blocks'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one XPS draft")
    technology = technologies[0]
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(ROLES)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == INSTALL_WORK))).all()
    if set(roles) != set(ROLES) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        raise ValueError("XPS roles or work require explicit M1 selections")
    blocks = [material_block(technology.id, code, roles[code]) for code in ROLES] + [work_block(technology.id, steps[0])]
    created, reused, edited = 0, 0, []
    for block in blocks:
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
