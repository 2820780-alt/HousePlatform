"""Explicitly quantified auxiliary materials for the existing strip draft."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, text

from app.models.material import Material
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement
from app.models.unit import Unit
from app.services.module2_calculation_blocks import add_block, encode_definition
from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode
from app.services.module2_fnd3_strip_blocks import TECHNOLOGY_CODE


AUXILIARY = {
    "FND2_ARM_AUX_01": ("wire", "Вязальная проволока", "kg"),
    "FND2_ARM_AUX_05": ("spacers", "Фиксаторы защитного слоя", "piece"),
}


def auxiliary_block(technology_id: uuid.UUID, role_code: str, role) -> CalculationBlock:
    key, label, unit = AUXILIARY[role_code]
    base = f"atom/fnd3/{technology_id}/strip-auxiliary/{key}"
    block_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{base}/block"))
    node_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{base}/quantity"))
    input_key = f"strip_auxiliary.{key}.quantity"
    quantity = CalculationNode(node_id, "INPUT", unit, input_key=input_key)
    return CalculationBlock(
        id=block_id, name=label, nodes=(quantity,), outputs=(node_id,),
        parameters=(BlockParameter(input_key, f"Количество: {label.lower()}", unit, minimum=Decimal(0)),),
        material_id=str(role.canonical_material_id), material_requirement_id=str(role.id),
        material_output_id=node_id,
    )


async def add_strip_auxiliary_blocks(db, *, actor: object) -> dict:
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Strip auxiliary setup requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.strip.auxiliary'))"))
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code == TECHNOLOGY_CODE, Technology.status == "DRAFT").with_for_update())).all()
    if len(technologies) != 1:
        raise ValueError("Expected one strip foundation draft")
    technology = technologies[0]
    rows = (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(AUXILIARY)))).all()
    roles = {row.code: row for row in rows}
    if len(rows) != len(AUXILIARY) or set(roles) != set(AUXILIARY) or any(
        role.canonical_material_id is None for role in roles.values()
    ):
        raise ValueError("Strip auxiliary materials require explicit M1 selections")
    units = dict((await db.execute(select(Material.id, Unit.abbreviation).join(
        Unit, Unit.id == Material.base_unit_id).where(
            Material.id.in_([role.canonical_material_id for role in roles.values()])))).all())
    if any(units.get(roles[code].canonical_material_id) != definition[2]
           for code, definition in AUXILIARY.items()):
        raise ValueError("Strip auxiliary material unit does not match its calculation")
    created, reused, edited = 0, 0, []
    for code in AUXILIARY:
        block = auxiliary_block(technology.id, code, roles[code])
        existing = await db.get(TechnologyCalculationBlock, uuid.UUID(block.id))
        if existing:
            changed = (existing.technology_id != technology.id or existing.definition != encode_definition(block)
                       or existing.name != block.name or str(existing.material_id or "") != block.material_id
                       or existing.work_code is not None)
            if changed:
                edited.append(block.name)
            else:
                reused += 1
            continue
        await add_block(db, technology_id=technology.id, block=block, actor=actor, actor_id=getattr(actor, "id", None))
        created += 1
    return {"technology_id": str(technology.id), "created": created, "reused": reused, "edited": edited}
