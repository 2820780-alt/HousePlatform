from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.models.material import Material
from app.schemas.material_hub_contracts import (
    ConstructionUsageModerationAction,
    ConstructionUsageStatus,
    MaterialConstructionUsage,
    MaterialConstructionUsageCandidate,
    MaterialConstructionUsageModerationDecision,
    Module2TechnologyKnowledgeRef,
)


MODULE_01_MATERIAL_HUB = "MODULE_01_MATERIAL_HUB"
MODULE_02_KNOWLEDGE_BASE = "MODULE_02_KNOWLEDGE_BASE"
CONSTRUCTION_APPLICABILITY_FEATURE = "CONSTRUCTION_APPLICABILITY"


STARTER_CONSTRUCTION_GROUPS: tuple[str, ...] = (
    "Фундамент",
    "Коробка дома",
    "Перекрытия",
    "Кровля",
    "Фасад",
    "Окна и двери",
    "Внутренняя отделка",
    "Наружная отделка",
    "Инженерные системы",
    "Электрика",
    "Водоснабжение",
    "Канализация",
    "Отопление",
    "Гидроизоляция",
    "Теплоизоляция",
    "Пароизоляция",
    "Звукоизоляция",
    "Крепеж и расходники",
)


STARTER_CONSTRUCTION_SUBGROUPS: dict[str, tuple[str, ...]] = {
    "Фундамент": ("опалубка", "армирование", "бетон", "гидроизоляция", "утепление"),
    "Коробка дома": ("кладка", "каркас", "перемычки", "армопояс", "наружные стены", "внутренние перегородки"),
    "Кровля": (
        "стропила",
        "обрешетка",
        "контробрешетка",
        "кровельное покрытие",
        "мембраны",
        "утепление",
        "водосточная система",
    ),
}


def get_material_construction_usage(material: Material) -> list[MaterialConstructionUsage]:
    """Return safe Module 01 construction usage entries for a material card.

    Module 02 is intentionally not imported here. Until a persisted usage table is
    introduced, the only generated entry comes from existing Module 01 taxonomy
    and remains NEEDS_REVIEW so it cannot become an absolute construction truth.
    """

    usages: list[MaterialConstructionUsage] = []
    material_type = getattr(material, "material_type", None)
    construction_group = getattr(material_type, "construction_group", None) if material_type else None
    if construction_group and getattr(construction_group, "name", None):
        usages.append(
            MaterialConstructionUsage(
                material_id=getattr(material, "id", None),
                construction_group=construction_group.name,
                construction_subgroup=getattr(getattr(material, "subcategory", None), "name", None),
                construction_element=getattr(material_type, "name", None),
                usage_role="Предварительная применимость по типу материала",
                condition=(
                    "Требует проверки модератором. Строительная применимость не равна категории "
                    "материала и может зависеть от характеристик."
                ),
                source_module=MODULE_01_MATERIAL_HUB,
                source_reference_id=getattr(material_type, "id", None),
                confidence=Decimal("0.35"),
                verified_by_moderator=False,
                moderator_note="Подготовлено из существующей таксономии Module 01; не источник Module 02.",
                status=ConstructionUsageStatus.NEEDS_REVIEW,
                created_at=getattr(material_type, "created_at", None),
                updated_at=getattr(material_type, "updated_at", None),
            )
        )
    return usages


def build_module2_construction_usage_candidate(
    knowledge: Module2TechnologyKnowledgeRef | dict[str, Any],
    *,
    material_id=None,
    material_name: str | None = None,
) -> MaterialConstructionUsageCandidate:
    """Build a candidate from future Module 02 structured knowledge.

    This is an adapter contract only: it does not call Module 02, write Module 02
    data, or persist anything by itself.
    """

    ref = (
        knowledge
        if isinstance(knowledge, Module2TechnologyKnowledgeRef)
        else Module2TechnologyKnowledgeRef(**knowledge)
    )
    usage = MaterialConstructionUsage(
        material_id=material_id,
        construction_group=ref.construction_group or "Требует указания группы",
        construction_subgroup=ref.construction_subgroup,
        construction_element=ref.construction or ref.node,
        technology_context=ref.technology,
        usage_role=ref.material_role,
        condition=ref.usage_condition,
        required_characteristics=ref.required_characteristics,
        source_module=MODULE_02_KNOWLEDGE_BASE,
        source_reference_id=ref.source_reference_id,
        confidence=ref.confidence,
        verified_by_moderator=False,
        moderator_note="Кандидат из будущего адаптера Module 02; требуется модерация или правило.",
        status=ConstructionUsageStatus.NEEDS_REVIEW,
    )
    return MaterialConstructionUsageCandidate(
        material_id=material_id,
        material_name=material_name or ref.material_name,
        proposed_usage=usage,
        module2_knowledge_ref=ref,
        status=ConstructionUsageStatus.NEEDS_REVIEW,
    )


def apply_construction_usage_moderation_decision(
    candidate: MaterialConstructionUsageCandidate,
    decision: MaterialConstructionUsageModerationDecision,
) -> MaterialConstructionUsageCandidate:
    updated = candidate.model_copy(deep=True)
    usage = deepcopy(decision.updated_usage or updated.proposed_usage)
    usage.material_id = decision.material_id or usage.material_id or updated.material_id
    usage.moderator_note = decision.moderator_note or usage.moderator_note
    usage.updated_at = decision.decided_at or datetime.now(UTC)

    if decision.action == ConstructionUsageModerationAction.APPROVE:
        usage.status = ConstructionUsageStatus.ACTIVE
        usage.verified_by_moderator = True
        updated.status = ConstructionUsageStatus.ACTIVE
    elif decision.action == ConstructionUsageModerationAction.UPDATE:
        usage.status = ConstructionUsageStatus.NEEDS_REVIEW
        usage.verified_by_moderator = False
        updated.status = ConstructionUsageStatus.NEEDS_REVIEW
    elif decision.action == ConstructionUsageModerationAction.REJECT:
        usage.status = ConstructionUsageStatus.REJECTED
        usage.verified_by_moderator = False
        updated.status = ConstructionUsageStatus.REJECTED
    elif decision.action == ConstructionUsageModerationAction.ARCHIVE:
        usage.status = ConstructionUsageStatus.ARCHIVED
        usage.verified_by_moderator = False
        updated.status = ConstructionUsageStatus.ARCHIVED

    updated.proposed_usage = usage
    updated.moderator_note = decision.moderator_note
    updated.updated_at = usage.updated_at
    return updated


def get_starter_construction_applicability_catalog() -> dict[str, tuple[str, ...]]:
    catalog = {group: STARTER_CONSTRUCTION_SUBGROUPS.get(group, tuple()) for group in STARTER_CONSTRUCTION_GROUPS}
    return catalog
