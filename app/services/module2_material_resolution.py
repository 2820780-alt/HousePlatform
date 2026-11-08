from __future__ import annotations

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import MaterialStatus, SourceActionType, TaskStatus
from app.models.material import Material
from app.models.module2_knowledge import CompatibilityRule
from app.models.module2_material_gap import Module2MaterialGap
from app.models.module2_technology import (
    Technology, TechnologyEvidenceReference, TechnologyMaterialRequirement,
)
from app.models.source_task import SourceTask
from app.schemas.module2_knowledge import CompatibilityRelation, KnowledgeSelectorInput, KnowledgeSelectorKind
from app.services.audit_service import log_event
from app.services.module2_knowledge_foundation import evaluate_compatibility_rules


class MaterialResolutionError(ValueError):
    pass


def material_card_url(material_id: uuid.UUID) -> str:
    return f"/api/v1/module1/materials/{material_id}"


async def compatible_materials(
    db: AsyncSession, requirement: TechnologyMaterialRequirement,
) -> tuple[Material, ...]:
    criteria = []
    if requirement.selector_kind == "CANONICAL_MATERIAL" and requirement.canonical_material_id:
        criteria.append(Material.id == requirement.canonical_material_id)
    elif requirement.material_category_id:
        category_id = requirement.material_category_id
        criteria.append(or_(Material.category_id == category_id, Material.subcategory_id == category_id))
        if requirement.material_type_id:
            criteria.append(Material.material_type_id == requirement.material_type_id)
    elif requirement.material_type_id:
        criteria.append(Material.material_type_id == requirement.material_type_id)
    else:
        return ()
    query = (
        select(Material)
        .options(selectinload(Material.attributes))
        .where(Material.status == MaterialStatus.VERIFIED, *criteria)
        .order_by(Material.canonical_name, Material.id)
    )
    materials = (await db.scalars(query)).all()
    constraints = requirement.technical_constraints or {}
    if not isinstance(constraints, dict):
        return ()
    rules = (await db.scalars(select(CompatibilityRule).where(
        CompatibilityRule.technology_id == requirement.technology_id,
        CompatibilityRule.status == "ACTIVE",
    ))).all()
    return tuple(material for material in materials
                 if (not constraints or _matches_attributes(material, constraints))
                 and _allowed_by_rules(material, requirement, rules))


def _allowed_by_rules(material: Material, requirement: TechnologyMaterialRequirement, rules) -> bool:
    if not rules:
        return True
    candidate = KnowledgeSelectorInput(
        selector_kind=KnowledgeSelectorKind.CANONICAL_MATERIAL,
        canonical_material_id=material.id,
    )
    targets = [KnowledgeSelectorInput(
        selector_kind=KnowledgeSelectorKind.MATERIAL_REQUIREMENT,
        material_requirement_id=requirement.id,
    )]
    if requirement.material_category_id or requirement.material_type_id:
        targets.append(KnowledgeSelectorInput(
            selector_kind=KnowledgeSelectorKind.MATERIAL_CLASS,
            material_category_id=requirement.material_category_id,
            material_type_id=requirement.material_type_id,
        ))
    for target in targets:
        result = evaluate_compatibility_rules(rules, candidate, target)
        if "no_matching_active_rule" not in result.blockers and result.relation != CompatibilityRelation.COMPATIBLE:
            return False
    return True


def _matches_attributes(material: Material, constraints: dict) -> bool:
    attributes = {item.attribute_name.casefold(): item.attribute_value.casefold() for item in material.attributes}
    for key, value in constraints.items():
        if not isinstance(value, (str, int, float, bool)):
            return False
        actual = attributes.get(str(key).casefold())
        if actual is None or actual != str(value).casefold():
            return False
    return True


async def gap_for_requirement(db: AsyncSession, requirement_id: uuid.UUID) -> Module2MaterialGap | None:
    return await db.scalar(select(Module2MaterialGap).where(Module2MaterialGap.requirement_id == requirement_id))


async def ensure_gap(
    db: AsyncSession, technology: Technology, requirement: TechnologyMaterialRequirement,
    *, search_phrase: str, actor_id: uuid.UUID | None = None,
) -> Module2MaterialGap | None:
    if await compatible_materials(db, requirement):
        return await gap_for_requirement(db, requirement.id)
    gap = await gap_for_requirement(db, requirement.id)
    if gap is not None:
        return gap
    phrase = search_phrase.strip()[:500] or requirement.code
    evidence_ids = [str(item) for item in (await db.scalars(
        select(TechnologyEvidenceReference.id).where(
            TechnologyEvidenceReference.technology_id == technology.id,
            or_(
                TechnologyEvidenceReference.target_kind == "TECHNOLOGY",
                and_(TechnologyEvidenceReference.target_kind == "MATERIAL_REQUIREMENT",
                     TechnologyEvidenceReference.target_reference == str(requirement.id)),
            ),
        ).order_by(TechnologyEvidenceReference.id)
    )).all()]
    evidence_context = {"technology_code": technology.technology_code,
                        "requirement_code": requirement.code,
                        "evidence_reference_ids": evidence_ids}
    gap = Module2MaterialGap(
        technology_id=technology.id,
        technology_revision=technology.revision,
        requirement_id=requirement.id,
        search_phrase=phrase,
        expected_category_id=requirement.material_category_id,
        required_characteristics=requirement.technical_constraints or {},
        evidence_context=evidence_context,
        status="OPEN",
    )
    db.add(gap)
    await db.flush()
    task = SourceTask(
        action_type=SourceActionType.FIND_NEW_PRODUCTS,
        status=TaskStatus.NEEDS_REVIEW,
        created_by=actor_id,
        parameters={"origin": "M2_MATERIAL_GAP", "gap_id": str(gap.id),
                    "technology_code": technology.technology_code,
                    "requirement_code": requirement.code, "search_phrase": phrase,
                    "evidence_reference_ids": evidence_ids,
                    "category_id": str(requirement.material_category_id) if requirement.material_category_id else None},
    )
    db.add(task)
    await db.flush()
    gap.source_task_id = task.id
    await log_event(db, "M2_MATERIAL_GAP_OPEN", "module2_material_gap", gap.id, actor_id,
                    {"requirement_id": str(requirement.id), "source_task_id": str(task.id)})
    return gap


async def change_gap_query(
    db: AsyncSession, gap: Module2MaterialGap, phrase: str, actor_id: uuid.UUID | None,
) -> None:
    phrase = phrase.strip()
    if not phrase or len(phrase) > 500 or gap.status in {"RESOLVED_EXISTING", "RESOLVED_NEW_MATERIAL", "DISMISSED"}:
        raise MaterialResolutionError("Запрос должен содержать от 1 до 500 символов для открытого пробела.")
    previous = gap.search_phrase
    gap.search_phrase = phrase
    gap.status = "REVIEWING"
    if gap.source_task_id:
        task = await db.get(SourceTask, gap.source_task_id)
        if task:
            task.parameters = {**(task.parameters or {}), "search_phrase": phrase,
                               "search_requested": False}
    await log_event(db, "M2_MATERIAL_GAP_QUERY", "module2_material_gap", gap.id, actor_id,
                    {"from": previous, "to": phrase})


async def resolve_existing(
    db: AsyncSession, gap: Module2MaterialGap, requirement: TechnologyMaterialRequirement,
    material_id: uuid.UUID, actor_id: uuid.UUID | None,
) -> None:
    if gap.status == "DISMISSED":
        raise MaterialResolutionError("Отклоненный пробел нельзя разрешить без повторного рассмотрения.")
    candidates = await compatible_materials(db, requirement)
    if material_id not in {item.id for item in candidates}:
        raise MaterialResolutionError("Материал M1 не подтвержден или не соответствует требованию.")
    gap.resolved_material_id = material_id
    selected = next(item for item in candidates if item.id == material_id)
    gap.status = (
        "RESOLVED_NEW_MATERIAL"
        if gap.status == "SEARCH_REQUESTED" and selected.created_at and selected.created_at > gap.created_at
        else "RESOLVED_EXISTING"
    )
    gap.resolution_note = "Выбрана каноническая карточка M1."
    await log_event(db, "M2_MATERIAL_GAP_RESOLVED", "module2_material_gap", gap.id, actor_id,
                    {"material_id": str(material_id)})


async def request_m1_search(
    db: AsyncSession, gap: Module2MaterialGap, actor_id: uuid.UUID | None,
) -> None:
    if gap.status not in {"OPEN", "REVIEWING", "SEARCH_REQUESTED"}:
        raise MaterialResolutionError("Поиск можно запросить только для неразрешенного материала.")
    if not gap.source_task_id:
        raise MaterialResolutionError("Для пробела нет задачи M1.")
    task = await db.get(SourceTask, gap.source_task_id)
    if not task:
        raise MaterialResolutionError("Задача M1 недоступна.")
    task.parameters = {**(task.parameters or {}), "search_requested": True,
                       "search_phrase": gap.search_phrase,
                       "required_characteristics": gap.required_characteristics,
                       "evidence_context": gap.evidence_context}
    task.status = TaskStatus.NEEDS_REVIEW
    gap.status = "SEARCH_REQUESTED"
    await log_event(db, "M2_MATERIAL_GAP_SEARCH_REQUESTED", "module2_material_gap", gap.id,
                    actor_id, {"source_task_id": str(task.id)})


async def dismiss_gap(
    db: AsyncSession, gap: Module2MaterialGap, rationale: str, actor_id: uuid.UUID | None,
) -> None:
    rationale = rationale.strip()
    if len(rationale) < 10 or len(rationale) > 1000:
        raise MaterialResolutionError("Для отклонения нужно обоснование от 10 до 1000 символов.")
    if gap.status in {"RESOLVED_EXISTING", "RESOLVED_NEW_MATERIAL"}:
        raise MaterialResolutionError("Разрешенный пробел нельзя отклонить.")
    gap.status = "DISMISSED"
    gap.resolution_note = rationale
    await log_event(db, "M2_MATERIAL_GAP_DISMISSED", "module2_material_gap", gap.id,
                    actor_id, {"rationale": rationale})
