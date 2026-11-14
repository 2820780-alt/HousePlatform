"""Persist independent calculation blocks on existing M2 DRAFT revisions."""

from __future__ import annotations

import uuid
from dataclasses import asdict, replace
from typing import Mapping

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_levels import AccessLevel
from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_calculation_block import CalculationBlockTemplate, TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.models.module2_material_gap import Module2MaterialGap
from app.schemas.module2_calculation_block import CalculationBlockDefinition
from app.services.audit_service import log_event
from app.services.module2_calculation_graph import (
    BlockParameter, CalculationBlock, CalculationNode, Threshold, copy_block, validate_block,
)
from app.services.module2_technology_foundation import require_module2_access


def encode_definition(block: CalculationBlock) -> dict:
    validate_block(block)
    payload = CalculationBlockDefinition.model_validate({
        "nodes": [asdict(node) for node in block.nodes],
        "outputs": block.outputs,
        "parameters": [asdict(parameter) for parameter in block.parameters],
        "material_output_id": block.material_output_id,
        "work_output_id": block.work_output_id,
        "rule_source": block.rule_source,
        "rule_status": block.rule_status,
        "material_requirement_id": block.material_requirement_id,
        "work_step_id": block.work_step_id,
    })
    return payload.model_dump(mode="json")


def decode_definition(
    definition: dict, *, block_id: str, name: str,
    material_id: str | None = None, work_code: str | None = None,
) -> CalculationBlock:
    payload = CalculationBlockDefinition.model_validate(definition)
    nodes = tuple(CalculationNode(
        id=node.id, operation=node.operation, unit=node.unit, inputs=node.inputs,
        input_key=node.input_key, constant=node.constant,
        thresholds=tuple(Threshold(**threshold.model_dump()) for threshold in node.thresholds),
        label=node.label,
    ) for node in payload.nodes)
    block = CalculationBlock(
        id=block_id, name=name, nodes=nodes, outputs=payload.outputs,
        parameters=tuple(BlockParameter(**parameter.model_dump()) for parameter in payload.parameters),
        material_id=material_id, work_code=work_code,
        material_output_id=payload.material_output_id, work_output_id=payload.work_output_id,
        rule_source=payload.rule_source, rule_status=payload.rule_status,
        material_requirement_id=payload.material_requirement_id, work_step_id=payload.work_step_id,
    )
    validate_block(block)
    return block


async def _draft(db: AsyncSession, technology_id: uuid.UUID, actor: object) -> Technology:
    require_module2_access(actor, AccessLevel.EDIT)
    technology = await db.scalar(select(Technology).where(Technology.id == technology_id).with_for_update())
    if technology is None:
        raise ValueError("technology revision not found")
    if technology.status != "DRAFT":
        raise ValueError("calculation blocks can be changed only in a DRAFT revision")
    return technology


async def _validate_links(db: AsyncSession, material_id: uuid.UUID | None, work_code: str | None) -> None:
    if material_id is not None:
        material = await db.get(Material, material_id)
        if material is None or material.status in {MaterialStatus.ARCHIVED, MaterialStatus.REJECTED}:
            raise ValueError("material is missing or archived")
    if work_code is not None:
        work = await db.get(WorkCatalogItem, work_code)
        if work is None or work.status == "ARCHIVED":
            raise ValueError("work code is missing or archived in the M1 work catalog")


async def _validate_technology_roles(db: AsyncSession, technology_id: uuid.UUID, block: CalculationBlock) -> None:
    try:
        requirement_id = uuid.UUID(block.material_requirement_id) if block.material_requirement_id else None
        step_id = uuid.UUID(block.work_step_id) if block.work_step_id else None
    except ValueError:
        raise ValueError("invalid technology role identifier") from None
    if requirement_id:
        requirement = await db.get(TechnologyMaterialRequirement, requirement_id)
        if requirement is None or requirement.technology_id != technology_id or not block.material_id:
            raise ValueError("material requirement must belong to this technology and select an M1 material")
        material_id = requirement.canonical_material_id
        if material_id is None:
            gap = await db.scalar(select(Module2MaterialGap).where(
                Module2MaterialGap.requirement_id == requirement_id,
                Module2MaterialGap.technology_id == technology_id,
                Module2MaterialGap.status.in_(["RESOLVED_EXISTING", "RESOLVED_NEW_MATERIAL"])))
            material_id = gap.resolved_material_id if gap else None
        if str(material_id) != block.material_id:
            raise ValueError("material differs from the technology requirement")
    if step_id:
        step = await db.get(TechnologyWorkStep, step_id)
        if step is None or step.technology_id != technology_id or step.work_code != block.work_code:
            raise ValueError("work step must belong to this technology and select the same M1 work")


async def add_block(
    db: AsyncSession, *, technology_id: uuid.UUID, block: CalculationBlock, actor: object,
    actor_id: uuid.UUID | None, template_id: uuid.UUID | None = None,
) -> TechnologyCalculationBlock:
    await _draft(db, technology_id, actor)
    try:
        block_id = uuid.UUID(block.id)
        material_id = uuid.UUID(block.material_id) if block.material_id else None
    except ValueError:
        raise ValueError("block and material IDs must be UUIDs") from None
    await _validate_links(db, material_id, block.work_code)
    await _validate_technology_roles(db, technology_id, block)
    if template_id is not None and await db.get(CalculationBlockTemplate, template_id) is None:
        raise ValueError("template version not found")
    definition = encode_definition(block)
    current = (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == technology_id))).all()
    new_node_ids = {node.id for node in block.nodes}
    for item in current:
        stored = decode_definition(item.definition, block_id=str(item.id), name=item.name)
        if new_node_ids.intersection(node.id for node in stored.nodes):
            raise ValueError("node IDs must be unique within a technology revision")
    position = max((item.position for item in current), default=0) + 1
    row = TechnologyCalculationBlock(
        id=block_id, technology_id=technology_id, template_id=template_id, name=block.name,
        position=position, version=1, definition=definition, material_id=material_id,
        work_code=block.work_code, created_by_user_id=actor_id,
    )
    db.add(row)
    await db.flush()
    await log_event(db, "M2_CALCULATION_BLOCK_CREATED", "TechnologyCalculationBlock", row.id, actor_id,
                    {"technology_id": str(technology_id), "template_id": str(template_id or "")})
    return row


async def update_block(
    db: AsyncSession, *, technology_id: uuid.UUID, block_id: uuid.UUID, block: CalculationBlock,
    expected_version: int, actor: object, actor_id: uuid.UUID | None, reviewed: bool = False,
) -> TechnologyCalculationBlock:
    await _draft(db, technology_id, actor)
    row = await db.scalar(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.id == block_id,
        TechnologyCalculationBlock.technology_id == technology_id,
    ).with_for_update())
    if row is None:
        raise ValueError("calculation block not found")
    if row.version != expected_version:
        raise ValueError("calculation block changed; refresh before saving")
    if block.id != str(block_id):
        raise ValueError("block ID cannot be changed")
    try:
        material_id = uuid.UUID(block.material_id) if block.material_id else None
    except ValueError:
        raise ValueError("material ID must be a UUID") from None
    await _validate_links(db, material_id, block.work_code)
    await _validate_technology_roles(db, technology_id, block)
    if not reviewed and block.rule_status == "VERIFIED":
        block = replace(block, rule_status="PRELIMINARY" if block.rule_source else "UNCONFIRMED")
    definition = encode_definition(block)
    siblings = (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == technology_id,
        TechnologyCalculationBlock.id != block_id))).all()
    node_ids = {node.id for node in block.nodes}
    for item in siblings:
        stored = decode_definition(item.definition, block_id=str(item.id), name=item.name)
        if node_ids.intersection(node.id for node in stored.nodes):
            raise ValueError("node IDs must be unique within a technology revision")
    row.name = block.name
    row.definition = definition
    row.material_id = material_id
    row.work_code = block.work_code
    row.version += 1
    await db.flush()
    await log_event(db, "M2_CALCULATION_BLOCK_UPDATED", "TechnologyCalculationBlock", row.id, actor_id,
                    {"technology_id": str(technology_id), "version": row.version})
    return row


async def remove_block(
    db: AsyncSession, *, technology_id: uuid.UUID, block_id: uuid.UUID,
    expected_version: int, actor: object, actor_id: uuid.UUID | None,
) -> None:
    await _draft(db, technology_id, actor)
    row = await db.scalar(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.id == block_id,
        TechnologyCalculationBlock.technology_id == technology_id,
    ).with_for_update())
    if row is None:
        raise ValueError("calculation block not found")
    if row.version != expected_version:
        raise ValueError("calculation block changed; refresh before deleting")
    await db.delete(row)
    await db.flush()
    await log_event(db, "M2_CALCULATION_BLOCK_REMOVED", "TechnologyCalculationBlock", block_id, actor_id,
                    {"technology_id": str(technology_id), "version": expected_version})


async def copy_from_template(
    db: AsyncSession, *, technology_id: uuid.UUID, template_id: uuid.UUID,
    input_mapping: Mapping[str, str], material_id: uuid.UUID | None, work_code: str | None,
    actor: object, actor_id: uuid.UUID | None,
    material_requirement_id: str | None = None, work_step_id: str | None = None,
) -> TechnologyCalculationBlock:
    template = await db.get(CalculationBlockTemplate, template_id)
    if template is None:
        raise ValueError("template version not found")
    source = decode_definition(template.definition, block_id=str(template.id), name=template.name,
                               material_id=str(template.material_id) if template.material_id else None,
                               work_code=template.work_code)
    instance = copy_block(source, input_mapping=input_mapping,
                          material_id=str(material_id) if material_id else None, work_code=work_code)
    instance = replace(instance, material_requirement_id=material_requirement_id, work_step_id=work_step_id)
    if instance.rule_status == "VERIFIED":
        instance = replace(instance, rule_status="PRELIMINARY" if instance.rule_source else "UNCONFIRMED")
    return await add_block(db, technology_id=technology_id, block=instance, actor=actor,
                           actor_id=actor_id, template_id=template.id)


async def copy_from_technology(
    db: AsyncSession, *, source_block_id: uuid.UUID, technology_id: uuid.UUID,
    input_mapping: Mapping[str, str], material_id: uuid.UUID | None, work_code: str | None,
    actor: object, actor_id: uuid.UUID | None,
    material_requirement_id: str | None = None, work_step_id: str | None = None,
) -> TechnologyCalculationBlock:
    require_module2_access(actor, AccessLevel.VIEW)
    source_row = await db.get(TechnologyCalculationBlock, source_block_id)
    if source_row is None:
        raise ValueError("source block not found")
    source = decode_definition(source_row.definition, block_id=str(source_row.id), name=source_row.name)
    instance = copy_block(source, input_mapping=input_mapping,
                          material_id=str(material_id) if material_id else None, work_code=work_code)
    instance = replace(instance, material_requirement_id=material_requirement_id, work_step_id=work_step_id)
    if instance.rule_status == "VERIFIED":
        instance = replace(instance, rule_status="PRELIMINARY" if instance.rule_source else "UNCONFIRMED")
    return await add_block(db, technology_id=technology_id, block=instance, actor=actor, actor_id=actor_id)


async def save_template(
    db: AsyncSession, *, block_id: uuid.UUID, template_key: str, name: str, description: str | None,
    actor: object, actor_id: uuid.UUID | None,
) -> CalculationBlockTemplate:
    require_module2_access(actor, AccessLevel.ADMIN)
    key = template_key.strip()
    if not key or len(key) > 120 or not name.strip() or len(name) > 255:
        raise ValueError("template key and name are required")
    source = await db.get(TechnologyCalculationBlock, block_id)
    if source is None:
        raise ValueError("source block not found")
    block = decode_definition(source.definition, block_id=str(source.id), name=source.name)
    block = replace(block, material_requirement_id=None, work_step_id=None)
    existing = (await db.scalars(select(CalculationBlockTemplate).where(
        CalculationBlockTemplate.template_key == key).with_for_update())).all()
    version = max((item.version for item in existing), default=0) + 1
    template = CalculationBlockTemplate(
        id=uuid.uuid4(), template_key=key, version=version, name=name.strip(),
        description=description, definition=encode_definition(block), material_id=source.material_id,
        work_code=source.work_code, created_by_user_id=actor_id,
    )
    db.add(template)
    await db.flush()
    await log_event(db, "M2_CALCULATION_TEMPLATE_CREATED", "CalculationBlockTemplate", template.id, actor_id,
                    {"template_key": key, "version": version, "source_block_id": str(source.id)})
    return template


async def calculation_storage_available(db: AsyncSession) -> bool:
    connection = await db.connection()
    return await connection.run_sync(lambda sync: inspect(sync).has_table(TechnologyCalculationBlock.__tablename__))


async def copy_revision_blocks(db: AsyncSession, *, source_technology_id: uuid.UUID,
                               technology_id: uuid.UUID, actor: object, actor_id: uuid.UUID | None) -> int:
    """Independently copy existing calculation blocks to a new DRAFT revision."""
    if not await calculation_storage_available(db):
        return 0
    source = (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == source_technology_id).order_by(
        TechnologyCalculationBlock.position))).all()
    for row in source:
        graph = decode_definition(row.definition, block_id=str(row.id), name=row.name,
                                  material_id=str(row.material_id) if row.material_id else None,
                                  work_code=row.work_code)
        mapping = {node.input_key: node.input_key for node in graph.nodes if node.operation == "INPUT"}
        cloned = copy_block(graph, input_mapping=mapping, material_id=graph.material_id, work_code=graph.work_code)
        requirement_id, step_id = None, None
        if graph.material_requirement_id:
            original = await db.get(TechnologyMaterialRequirement, uuid.UUID(graph.material_requirement_id))
            if original is None or original.technology_id != source_technology_id:
                raise ValueError("source material role is missing")
            target = await db.scalar(select(TechnologyMaterialRequirement).where(
                TechnologyMaterialRequirement.technology_id == technology_id,
                TechnologyMaterialRequirement.code == original.code))
            if target is None:
                raise ValueError("material role was not copied into the new revision")
            requirement_id = str(target.id)
        if graph.work_step_id:
            original = await db.get(TechnologyWorkStep, uuid.UUID(graph.work_step_id))
            if original is None or original.technology_id != source_technology_id:
                raise ValueError("source work step is missing")
            target = await db.scalar(select(TechnologyWorkStep).where(
                TechnologyWorkStep.technology_id == technology_id, TechnologyWorkStep.position == original.position,
                TechnologyWorkStep.work_code == original.work_code))
            if target is None:
                raise ValueError("work step was not copied into the new revision")
            step_id = str(target.id)
        cloned = replace(cloned, material_requirement_id=requirement_id, work_step_id=step_id)
        await add_block(db, technology_id=technology_id, block=cloned, actor=actor,
                        actor_id=actor_id, template_id=row.template_id)
    return len(source)


async def verify_block(db: AsyncSession, *, technology_id: uuid.UUID, block_id: uuid.UUID,
                       expected_version: int, source: str, actor: object, actor_id: uuid.UUID | None):
    require_module2_access(actor, AccessLevel.APPROVE)
    row = await db.get(TechnologyCalculationBlock, block_id)
    if row is None or row.technology_id != technology_id:
        raise ValueError("calculation block not found")
    graph = decode_definition(row.definition, block_id=str(row.id), name=row.name,
                              material_id=str(row.material_id) if row.material_id else None, work_code=row.work_code)
    if not source.strip() or len(source.strip()) > 1000:
        raise ValueError("rule source is required")
    if any(parameter.default is not None and not (parameter.source or "").strip() for parameter in graph.parameters):
        raise ValueError("default parameters require sources")
    parameters = tuple(replace(parameter, status="VERIFIED") if parameter.default is not None else parameter
                       for parameter in graph.parameters)
    graph = replace(graph, parameters=parameters, rule_source=source.strip(), rule_status="VERIFIED")
    updated = await update_block(db, technology_id=technology_id, block_id=block_id, block=graph,
                                 expected_version=expected_version, actor=actor, actor_id=actor_id, reviewed=True)
    await log_event(db, "M2_CALCULATION_BLOCK_VERIFIED", "TechnologyCalculationBlock", block_id, actor_id,
                    {"technology_id": str(technology_id), "version": updated.version})
    return updated


async def require_verified_calculation_blocks(db: AsyncSession, technology_id: uuid.UUID) -> None:
    """Fail closed before activation, even when the preview interface is disabled."""
    if not await calculation_storage_available(db):
        return
    rows = (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == technology_id))).all()
    for row in rows:
        graph = decode_definition(row.definition, block_id=str(row.id), name=row.name,
                                  material_id=str(row.material_id) if row.material_id else None, work_code=row.work_code)
        if not graph.material_output_id and not graph.work_output_id:
            raise ValueError("Укажите выход расчётного блока для материала или работы перед активацией.")
        if graph.rule_status != "VERIFIED" or not (graph.rule_source or "").strip():
            raise ValueError("Подтвердите источники и расчётные правила всех блоков перед активацией.")
        if any(parameter.default is not None and parameter.status != "VERIFIED" for parameter in graph.parameters):
            raise ValueError("Подтвердите все используемые значения блоков перед активацией.")
        if graph.material_output_id:
            material = await db.get(Material, row.material_id) if row.material_id else None
            if material is None or material.status != MaterialStatus.VERIFIED:
                raise ValueError("Для активации выберите проверенный материал M1.")
            if not graph.material_requirement_id:
                raise ValueError("Выберите материальную роль этой технологии для расчёта.")
        if graph.work_output_id:
            work = await db.get(WorkCatalogItem, row.work_code) if row.work_code else None
            if work is None or work.status != "ACTIVE":
                raise ValueError("Для активации выберите действующую работу M1.")
            if not graph.work_step_id:
                raise ValueError("Выберите этап работы этой технологии для расчёта.")
        await _validate_technology_roles(db, technology_id, graph)
