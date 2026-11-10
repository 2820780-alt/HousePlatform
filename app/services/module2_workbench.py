from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.access_levels import AccessLevel
from app.core.permission_guard import can
from app.models.knowledge_resource import KnowledgeResource
from app.models.material import Material
from app.models.material_category import MaterialCategory
from app.models.material_document import MaterialDocument
from app.models.material_type import MaterialType
from app.models.module2_knowledge import CompatibilityRule, ConsumptionNorm, KnowledgeRule
from app.models.module2_material_gap import Module2MaterialGap
from app.models.module2_technology import (
    MODULE2_OWNER_CODE,
    Technology,
    TechnologyEvidenceReference,
    TechnologyLayer,
    TechnologyMaterialRequirement,
    TechnologyNode,
    TechnologyWorkStep,
)
from app.schemas.module2_knowledge import (
    CompatibilityRuleDraftInput,
    ConsumptionNormDraftInput,
    KnowledgeRuleDraftInput,
)
from app.schemas.module2_technology import (
    TechnologyLayerInput,
    TechnologyLifecycle,
    TechnologyMaterialRequirementInput,
    TechnologyNodeInput,
    TechnologyWorkStepInput,
)
from app.services.module1_work_catalog import get_work_item, list_work_items
from app.services.module2_default_assumptions import active_defaults, requires_explicit_foundation_input
from app.services.module2_knowledge_foundation import (
    attach_evidence_reference,
    create_compatibility_rule_draft,
    create_consumption_norm_draft,
    create_knowledge_rule_draft,
    detect_compatibility_conflicts,
    detect_knowledge_rule_conflicts,
    validate_knowledge_activation,
    verify_evidence_references,
)
from app.services.module2_technology_foundation import (
    Module2TechnologyError,
    require_module2_access,
    validate_technology_activation,
)


class Module2WorkbenchError(ValueError):
    pass


STATUS_LABELS = {
    "DRAFT": "Черновик",
    "REVIEW": "На проверке",
    "ACTIVE": "Действует",
    "ARCHIVED": "Архив",
}
SELECTOR_LABELS = {
    "CANONICAL_MATERIAL": "Материал M1",
    "MATERIAL_CLASS": "Класс материалов M1",
    "MATERIAL_REQUIREMENT": "Требование технологии",
    "TECHNICAL_CONSTRAINTS": "Технические ограничения",
    "ROLE": "Функциональная роль",
}
RELATION_LABELS = {
    "COMPATIBLE": "Совместимо",
    "INCOMPATIBLE": "Несовместимо",
    "CONDITIONAL": "Условно совместимо",
    "UNKNOWN": "Недостаточно данных",
}
OUTCOME_LABELS = {
    "REQUIREMENT": "Требование",
    "WARNING": "Предупреждение",
    "PROHIBITION": "Запрет",
    "CONSTRAINT": "Ограничение",
    "INFORMATION": "Информация",
}
TARGET_LABELS = {
    "TECHNOLOGY": "Технология",
    "LAYER": "Слой",
    "MATERIAL_REQUIREMENT": "Требование к материалу",
    "NODE": "Узел",
    "WORK_STEP": "Работа",
    "CONSUMPTION_NORM": "Норма расхода",
    "COMPATIBILITY_RULE": "Правило совместимости",
    "KNOWLEDGE_RULE": "Инженерное правило",
}
BLOCKER_LABELS = {
    "missing_layer": "Не добавлен ни один слой.",
    "missing_evidence": "Отсутствует обязательное подтверждение M1.",
    "technology_not_active": "Технология еще не переведена в действующий статус.",
    "entity_belongs_to_another_technology": "Запись относится к другой редакции технологии.",
}
FIELD_LABELS = {
    "temperature_c": "Температура",
    "air_temperature_c": "Температура воздуха",
    "surface_temperature_c": "Температура поверхности",
    "humidity_percent": "Влажность",
    "thickness_mm": "Толщина",
    "frost_resistance": "Морозостойкость",
    "strength_class": "Класс прочности",
}
OPERATOR_LABELS = {
    "EQUAL": "равно",
    "NOT_EQUAL": "не равно",
    "IN": "одно из",
    "NOT_IN": "не входит в",
    "GT": "больше",
    "GTE": "не ниже",
    "LT": "меньше",
    "LTE": "не выше",
    "BETWEEN": "в диапазоне",
    "EXISTS": "задано",
}
REQUIREMENT_NAMES = {
    "CONCRETE": "Конструкционный бетон", "REBAR": "Арматура",
    "WATERPROOFING": "Гидроизоляция", "FORMWORK": "Опалубка",
    "INSULATION": "Теплоизоляция", "XPS": "Плиты XPS",
    "PILE": "Сваи", "FBS": "Блоки ФБС", "FL": "Плиты ФЛ",
    "MORTAR": "Кладочный раствор", "MASTIC": "Мастика",
    "MEMBRANE": "Мембрана", "CASING": "Обсадная труба",
}
LAYER_NAMES = {
    "ASSEMBLY_JOINTS": "Монтажные швы", "BORED_PILE_CONCRETE": "Бетон буронабивной сваи",
    "BORE_CASING": "Обсадная труба", "COATING_SYSTEM": "Мастичное покрытие",
    "COLUMN_CONCRETE": "Бетон столба", "COLUMN_REINFORCEMENT": "Армирование столба",
    "CONSTRUCTION_FORM": "Опалубка", "EDGE_FORM": "Краевая опалубка",
    "FACTORY_RC_PILE": "Заводская ЖБ свая", "GRILLAGE_CONCRETE": "Бетон ростверка",
    "GRILLAGE_REINFORCEMENT": "Армирование ростверка", "INSULATED_BASE": "Утепленное основание",
    "LOAD_BEARING_BLOCKS": "Несущие блоки", "LOAD_BEARING_SLAB": "Несущая плита",
    "LOAD_BEARING_STRIP": "Несущая лента", "MEMBRANE_SYSTEM": "Мембранная система",
    "PILE_REINFORCEMENT": "Армирование сваи", "PREFABRICATED_FOOTING": "Сборная подошва",
    "RIBBED_RC_FOUNDATION": "Ребристый ЖБ фундамент", "RIB_AND_SLAB_REINFORCEMENT": "Армирование ребер и плиты",
    "RIB_FORM": "Опалубка ребер", "SLAB_AND_RIBS": "Плита и ребра",
    "STEEL_SCREW_PILE": "Стальная винтовая свая", "STRIP_REINFORCEMENT": "Армирование ленты",
    "STRUCTURAL_REINFORCEMENT": "Конструкционное армирование", "SUBSTRUCTURE_PROTECTION": "Защита подземной части",
    "THERMAL_INTERFACE": "Тепловой контур", "THERMAL_PROTECTION": "Теплозащита",
    "WALL_CONCRETE": "Бетон стены", "WALL_REINFORCEMENT": "Армирование стены",
    "WALL_WATERPROOFING": "Гидроизоляция стены", "WATER_PROTECTION": "Защита от воды",
    "XPS_LAYER": "Слой XPS",
}

SOURCE_INTERPRETATION_TRANSLATIONS = {
    "General sequence only; details, edition and PPR are project-dependent.": "Общая последовательность работ; детали, редакцию и ППР уточняют для объекта.",
    "Official current status and amendment list; check the applicable edition": "Проверить действующий статус, изменения и применимую редакцию документа.",
    "Official status and scope; project-specific foundation design, not construction dimensions": "Статус и область применения; размеры фундамента определяются расчётом для объекта.",
    "Official status and scope; reinforced-concrete design, not a fixed grade": "Статус и область применения; характеристики железобетона определяются расчётом.",
    "Primary published text for general work sequence in sections 5 and 6; later amendments not incorporated": "Основной текст о последовательности работ в разделах 5 и 6; последующие изменения не учтены.",
    "Project-specific design scope; no numerical recipe.": "Область проектирования для конкретного объекта без универсальных численных значений.",
    "Scope and project-dependent design, not a universal recipe.": "Область применения и проектирование для конкретного объекта, без универсального решения.",
    "Statement reviewed against the named source scope; no universal numerical design value.": "Положение сверено с областью применения источника; универсальное расчётное значение не задано.",
    "System or product-specific technical context; project selection remains required.": "Технический контекст системы или изделия; выбор выполняют для конкретного объекта.",
    "This is a project-dependent interface; the source does not prescribe a universal detail.": "Узел зависит от проекта; источник не устанавливает универсального решения.",
}


def actor_role_code(user: Any) -> str:
    value = getattr(user, "roleCode", None) or getattr(user, "role_code", None) or getattr(user, "role", "")
    return str(value.value if isinstance(value, Enum) else value).upper()


def workbench_permissions(user: Any) -> dict[str, bool]:
    return {
        "view": can(user, MODULE2_OWNER_CODE, "VIEW"),
        "edit": can(user, MODULE2_OWNER_CODE, "EDIT"),
        "approve": can(user, MODULE2_OWNER_CODE, "APPROVE"),
        "admin": can(user, MODULE2_OWNER_CODE, "ADMIN"),
    }


def upsert_draft_requirement(
    technology: Technology,
    data: TechnologyMaterialRequirementInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    item_id: uuid.UUID | None = None,
) -> TechnologyMaterialRequirement:
    _require_editable(technology, actor_role_code)
    command = _command(data, TechnologyMaterialRequirementInput)
    item = _find(technology.requirements, item_id) if item_id else None
    _ensure_unique(technology.requirements, "code", command.code, item)
    if item is None:
        item = TechnologyMaterialRequirement(id=uuid.uuid4())
        technology.requirements.append(item)
    item.code = command.code
    item.selector_kind = command.selector_kind.value
    item.material_role_code = command.material_role_code
    item.canonical_material_id = command.canonical_material_id
    item.material_category_id = command.material_category_id
    item.material_type_id = command.material_type_id
    item.technical_constraints = dict(command.technical_constraints)
    item.notes = command.notes
    return item


def upsert_draft_layer(
    technology: Technology,
    data: TechnologyLayerInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    item_id: uuid.UUID | None = None,
) -> TechnologyLayer:
    _require_editable(technology, actor_role_code)
    command = _command(data, TechnologyLayerInput)
    item = _find(technology.layers, item_id) if item_id else None
    _ensure_unique(technology.layers, "position", command.position, item)
    requirement = _find_by(technology.requirements, "code", command.requirement_code) if command.requirement_code else None
    if command.requirement_code and requirement is None:
        raise Module2WorkbenchError("Выбранное требование к материалу не найдено.")
    if item is None:
        item = TechnologyLayer(id=uuid.uuid4())
        technology.layers.append(item)
    item.position = command.position
    item.functional_role = command.functional_role
    item.material_requirement = requirement
    item.thickness_expression = command.thickness_expression
    item.is_mandatory = command.is_mandatory
    item.notes = command.notes
    item.restrictions = dict(command.restrictions)
    return item


def upsert_draft_node(
    technology: Technology,
    data: TechnologyNodeInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    item_id: uuid.UUID | None = None,
) -> TechnologyNode:
    _require_editable(technology, actor_role_code)
    command = _command(data, TechnologyNodeInput)
    item = _find(technology.nodes, item_id) if item_id else None
    _ensure_unique(technology.nodes, "code", command.code, item)
    if item is None:
        item = TechnologyNode(id=uuid.uuid4())
        technology.nodes.append(item)
    item.code = command.code
    item.node_type = command.node_type
    item.name = command.name
    item.description = command.description
    item.conditions = dict(command.conditions)
    return item


def upsert_draft_work_step(
    technology: Technology,
    data: TechnologyWorkStepInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    item_id: uuid.UUID | None = None,
) -> TechnologyWorkStep:
    _require_editable(technology, actor_role_code)
    command = _command(data, TechnologyWorkStepInput)
    if get_work_item(command.work_code) is None:
        raise Module2WorkbenchError("Выбранная работа отсутствует в каталоге работ M1.")
    item = _find(technology.work_steps, item_id) if item_id else None
    _ensure_unique(technology.work_steps, "position", command.position, item)
    if item is None:
        item = TechnologyWorkStep(id=uuid.uuid4())
        technology.work_steps.append(item)
    item.position = command.position
    item.work_code = command.work_code
    item.applicability_expression = command.applicability_expression
    item.dependency_step_codes = list(command.dependency_step_codes)
    item.instructions = command.instructions
    return item


def upsert_consumption_norm(
    technology: Technology,
    data: ConsumptionNormDraftInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
) -> ConsumptionNorm:
    _require_editable(technology, actor_role_code)
    candidate = create_consumption_norm_draft(
        technology,
        data,
        actor_role_code=actor_role_code,
        created_by_user_id=created_by_user_id,
    )
    if item_id is None:
        _ensure_unique(technology.consumption_norms, "norm_code", candidate.norm_code, candidate)
        return candidate
    technology.consumption_norms.remove(candidate)
    item = _find(technology.consumption_norms, item_id)
    _require_item_draft(item)
    _ensure_unique(technology.consumption_norms, "norm_code", candidate.norm_code, item)
    _copy_fields(item, candidate, (
        "norm_code", "scope_layer_id", "scope_requirement_id", "scope_work_step_id",
        "resource_kind", "resource_selector", "basis_quantity", "basis_unit",
        "consumption_quantity", "consumption_unit", "conditions", "source_kind", "blockers",
    ))
    return item


def upsert_compatibility_rule(
    technology: Technology,
    data: CompatibilityRuleDraftInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
) -> CompatibilityRule:
    _require_editable(technology, actor_role_code)
    candidate = create_compatibility_rule_draft(
        technology,
        data,
        actor_role_code=actor_role_code,
        created_by_user_id=created_by_user_id,
    )
    if item_id is None:
        _ensure_unique(technology.compatibility_rules, "rule_code", candidate.rule_code, candidate)
        return candidate
    technology.compatibility_rules.remove(candidate)
    item = _find(technology.compatibility_rules, item_id)
    _require_item_draft(item)
    _ensure_unique(technology.compatibility_rules, "rule_code", candidate.rule_code, item)
    _copy_fields(item, candidate, (
        "rule_code", "subject_kind", "subject_selector", "object_kind", "object_selector",
        "relation", "conditions", "reason", "is_symmetric", "source_kind", "blockers",
    ))
    return item


def upsert_knowledge_rule(
    technology: Technology,
    data: KnowledgeRuleDraftInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
) -> KnowledgeRule:
    _require_editable(technology, actor_role_code)
    candidate = create_knowledge_rule_draft(
        technology,
        data,
        actor_role_code=actor_role_code,
        created_by_user_id=created_by_user_id,
    )
    if item_id is None:
        _ensure_unique(technology.knowledge_rules, "rule_code", candidate.rule_code, candidate)
        return candidate
    technology.knowledge_rules.remove(candidate)
    item = _find(technology.knowledge_rules, item_id)
    _require_item_draft(item)
    _ensure_unique(technology.knowledge_rules, "rule_code", candidate.rule_code, item)
    _copy_fields(item, candidate, (
        "rule_code", "scope_kind", "scope_reference", "conditions", "outcome_type",
        "outcome_payload", "source_kind", "blockers",
    ))
    return item


def add_evidence(
    technology: Technology,
    data: Mapping[str, Any],
    *,
    actor_role_code: str,
) -> TechnologyEvidenceReference:
    _require_editable(technology, actor_role_code)
    target = _evidence_target(technology, str(data.get("target_kind") or "TECHNOLOGY"), data.get("target_reference"))
    return attach_evidence_reference(
        technology,
        target,
        {
            "document_id": data.get("document_id"),
            "knowledge_resource_id": data.get("knowledge_resource_id"),
            "interpretation": data.get("interpretation"),
        },
        actor_role_code=actor_role_code,
    )


def delete_draft_component(
    technology: Technology,
    component: str,
    item_id: uuid.UUID,
    *,
    actor_role_code: str,
) -> None:
    _require_editable(technology, actor_role_code)
    collections = {
        "requirement": technology.requirements,
        "layer": technology.layers,
        "node": technology.nodes,
        "work-step": technology.work_steps,
        "norm": technology.consumption_norms,
        "compatibility": technology.compatibility_rules,
        "rule": technology.knowledge_rules,
        "evidence": technology.evidence_references,
    }
    collection = collections.get(component)
    if collection is None:
        raise Module2WorkbenchError("Неизвестный раздел Workbench.")
    item = _find(collection, item_id)
    if hasattr(item, "status"):
        _require_item_draft(item)
    _ensure_not_referenced(technology, component, item)
    collection.remove(item)


async def move_draft_ordered_item(
    db: AsyncSession,
    technology: Technology,
    component: str,
    item_id: uuid.UUID,
    direction: str,
    *,
    actor_role_code: str,
) -> None:
    _require_editable(technology, actor_role_code)
    collection: Sequence[Any]
    if component == "layer":
        collection = technology.layers
    elif component == "work-step":
        collection = technology.work_steps
    else:
        raise Module2WorkbenchError("Порядок поддерживается только для слоев и работ.")
    ordered = sorted(collection, key=lambda value: value.position)
    item = _find(ordered, item_id)
    index = ordered.index(item)
    target_index = index - 1 if direction == "up" else index + 1 if direction == "down" else -1
    if target_index < 0 or target_index >= len(ordered):
        return
    peer = ordered[target_index]
    item_position = item.position
    peer_position = peer.position
    item.position = max(value.position for value in ordered) + 1000
    await db.flush()
    peer.position = item_position
    await db.flush()
    item.position = peer_position
    await db.flush()


def _needs_material_selection(requirement: Any, gaps: Mapping) -> bool:
    if requirement.canonical_material_id is not None:
        return False
    status, resolved_material_id = gaps.get(requirement.id, (None, None))
    if status == "DISMISSED":
        return False
    return not (status in {"RESOLVED_EXISTING", "RESOLVED_NEW_MATERIAL"} and resolved_material_id is not None)


async def build_technology_list_view(db: AsyncSession) -> tuple[dict[str, Any], ...]:
    result = await db.execute(
        select(Technology)
        .options(selectinload(Technology.layers), selectinload(Technology.requirements))
        .order_by(Technology.updated_at.desc(), Technology.technology_code, Technology.revision.desc())
    )
    gap_rows = await db.execute(select(
        Module2MaterialGap.requirement_id,
        Module2MaterialGap.status,
        Module2MaterialGap.resolved_material_id,
    ))
    gaps = {requirement_id: (status, material_id) for requirement_id, status, material_id in gap_rows.all()}
    return tuple(
        {
            "id": item.id,
            "name": item.name,
            "code": item.technology_code,
            "revision": item.revision,
            "status": item.status,
            "status_label": status_label(item.status),
            "system_code": item.system_code or "Не задана",
            "category_id": item.category_id,
            "blocker_count": len(validate_technology_activation(item)),
            "unresolved_material_count": sum(
                1 for requirement in item.requirements if _needs_material_selection(requirement, gaps)
            ),
            "open_gap_count": sum(
                1 for requirement in item.requirements
                if gaps.get(requirement.id, (None, None))[0] in {"OPEN", "REVIEWING", "SEARCH_REQUESTED"}
            ),
            "updated_at": item.updated_at,
        }
        for item in result.scalars().all()
    )


async def build_technology_detail_view(db: AsyncSession, technology: Technology) -> dict[str, Any]:
    material_options = await _options(db, Material, Material.canonical_name)
    category_options = await _options(db, MaterialCategory, MaterialCategory.name)
    type_options = await _options(db, MaterialType, MaterialType.name)
    document_options = await _options(db, MaterialDocument, MaterialDocument.title, limit=300)
    resource_options = await _options(db, KnowledgeResource, KnowledgeResource.title, limit=300)
    verified_evidence = await verify_evidence_references(db, technology.evidence_references)
    revisions_result = await db.execute(
        select(Technology)
        .where(Technology.technology_code == technology.technology_code)
        .order_by(Technology.revision.desc())
    )
    revisions = tuple(revisions_result.scalars().all())

    names = {
        "materials": dict(material_options),
        "categories": dict(category_options),
        "types": dict(type_options),
    }
    requirements = [
        {
            "model": item,
            "display_name": REQUIREMENT_NAMES.get(item.code, item.code),
            "selector_label": SELECTOR_LABELS.get(item.selector_kind, _words(item.selector_kind)),
            "reference": _requirement_reference(item, names),
            "constraints": _human_mapping(item.technical_constraints),
            "constraint_pair": _first_pair(item.technical_constraints),
        }
        for item in technology.requirements
    ]
    requirement_codes = {item.id: REQUIREMENT_NAMES.get(item.code, "Требование к материалу") for item in technology.requirements}
    work_items = tuple(list_work_items())
    work_by_code = {item.work_code: item for item in work_items}
    layers = [
        {
            "model": item,
            "display_name": LAYER_NAMES.get(item.functional_role, item.functional_role),
            "requirement": requirement_codes.get(item.material_requirement_id, "Без привязки"),
            "restrictions": _human_mapping(item.restrictions),
            "restriction_pair": _first_pair(item.restrictions),
        }
        for item in sorted(technology.layers, key=lambda value: value.position)
    ]
    work_steps = [
        {
            "model": item,
            "work_name": work_by_code[item.work_code].work_name if item.work_code in work_by_code else "Работа отсутствует в каталоге M1",
            "unit": work_by_code[item.work_code].default_unit if item.work_code in work_by_code else None,
            "active_norm_count": sum(
                1 for norm in technology.consumption_norms
                if norm.scope_work_step_id == item.id and norm.status == "ACTIVE"
            ),
            "dependencies": ", ".join(
                work_by_code[code].work_name if code in work_by_code else "Работа не найдена в M1"
                for code in item.dependency_step_codes or ()
            ) or "Нет",
            "catalog_missing": item.work_code not in work_by_code,
        }
        for item in sorted(technology.work_steps, key=lambda value: value.position)
    ]
    norms = [
        {
            "model": item,
            "summary": format_consumption_norm(item),
            "resource": format_selector(item.resource_kind, item.resource_selector, names, requirement_codes),
            "conditions": format_conditions(item.conditions),
            "status_label": status_label(item.status),
            "selector_form": _selector_form(item.resource_kind, item.resource_selector),
            "condition_form": _condition_form(item.conditions),
            "blockers": _knowledge_blockers(item, technology, verified_evidence),
        }
        for item in technology.consumption_norms
    ]
    compatibility = [
        {
            "model": item,
            "relation_label": RELATION_LABELS.get(item.relation, _words(item.relation)),
            "subject": format_selector(item.subject_kind, item.subject_selector, names, requirement_codes),
            "object": format_selector(item.object_kind, item.object_selector, names, requirement_codes),
            "conditions": format_conditions(item.conditions),
            "status_label": status_label(item.status),
            "conflicts": detect_compatibility_conflicts(item, technology.compatibility_rules),
            "subject_form": _selector_form(item.subject_kind, item.subject_selector),
            "object_form": _selector_form(item.object_kind, item.object_selector),
            "condition_form": _condition_form(item.conditions),
            "blockers": _knowledge_blockers(item, technology, verified_evidence),
        }
        for item in technology.compatibility_rules
    ]
    rules = [
        {
            "model": item,
            "outcome_label": OUTCOME_LABELS.get(item.outcome_type, _words(item.outcome_type)),
            "conditions": format_conditions(item.conditions),
            "outcome": _human_mapping(item.outcome_payload),
            "status_label": status_label(item.status),
            "conflicts": detect_knowledge_rule_conflicts(item, technology.knowledge_rules),
            "condition_form": _condition_form(item.conditions),
            "outcome_pair": _first_pair(item.outcome_payload),
            "blockers": _knowledge_blockers(item, technology, verified_evidence),
        }
        for item in technology.knowledge_rules
    ]
    evidence_sources = {
        **{item_id: (label, "Документ M1") for item_id, label in document_options},
        **{item_id: (label, "Ресурс знаний M1") for item_id, label in resource_options},
    }
    evidence = []
    evidence_targets = {}
    for collection, label_key in ((requirements, "display_name"), (layers, "display_name"),
                                  (work_steps, "work_name"), (rules, "display_text")):
        for row in collection:
            model = row["model"]
            label = row.get(label_key) or row.get("outcome_label")
            evidence_targets[str(model.id)] = label
            for key in ("code", "rule_code"):
                if getattr(model, key, None):
                    evidence_targets[getattr(model, key)] = label
    for node in technology.nodes:
        evidence_targets[str(node.id)] = node.name
        evidence_targets[node.code] = node.name
    for item in technology.evidence_references:
        source_id = item.document_id or item.knowledge_resource_id
        source = evidence_sources.get(source_id)
        evidence.append(
            {
                "model": item,
                "title": source[0] if source else "Источник M1 недоступен",
                "source_type": source[1] if source else "Нарушенная ссылка",
                "target_label": TARGET_LABELS.get(item.target_kind, "Связь с технологией"),
                "target_name": evidence_targets.get(item.target_reference),
                "interpretation": SOURCE_INTERPRETATION_TRANSLATIONS.get(item.interpretation, item.interpretation)
                if item.interpretation and (item.interpretation in SOURCE_INTERPRETATION_TRANSLATIONS or
                                            any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in item.interpretation))
                else ("Описание источника пока не переведено." if item.interpretation else None),
                "verified": item.id in verified_evidence,
            }
        )

    source_groups: dict[tuple, dict[str, Any]] = {}
    for item in evidence:
        model = item["model"]
        key = (model.document_id, model.knowledge_resource_id)
        group = source_groups.setdefault(key, {
            "title": item["title"], "source_type": item["source_type"], "links": [],
        })
        group["links"].append(item)
    for group in source_groups.values():
        group["verified"] = all(item["verified"] for item in group["links"])
        counts: dict[str, int] = {}
        for item in group["links"]:
            counts[item["target_label"]] = counts.get(item["target_label"], 0) + 1
        group["counts"] = tuple(counts.items())

    rule_section_labels = {
        "applicability": "Применимость", "exclusions": "Ограничения и совместимость",
        "quality_before": "Контроль качества", "quality_during": "Контроль качества",
        "quality_after": "Контроль качества", "common_error": "Типичные ошибки",
        "project_dependent": "Ограничения и совместимость",
    }
    rule_groups: dict[str, list[dict[str, Any]]] = {}
    for item in rules:
        payload = item["model"].outcome_payload or {}
        section = str(payload.get("section") or "").lower()
        label = rule_section_labels.get(section, "Другие правила")
        item["phase_label"] = {"quality_before": "До начала работ", "quality_during": "Во время работ",
                               "quality_after": "После выполнения"}.get(section)
        item["display_text"] = next((payload[key] for key in ("message", "description", "text", "note")
                                     if isinstance(payload.get(key), str) and payload[key].strip()),
                                    item["outcome_label"])
        rule_groups.setdefault(label, []).append(item)

    activation_codes = validate_technology_activation(technology)
    activation_blockers = [blocker_label(item) for item in activation_codes]
    warnings = []
    broken_count = sum(1 for item in evidence if not item["verified"])
    conflict_count = sum(len(item["conflicts"]) for item in compatibility + rules)
    if broken_count:
        warnings.append(f"Недоступных или неподтвержденных ссылок M1: {broken_count}.")
    if conflict_count:
        warnings.append(f"Обнаружено конфликтующих правил: {conflict_count}.")
    if not technology.evidence_references:
        warnings.append("Для технологии пока не добавлены подтверждения M1.")

    return {
        "technology": technology,
        "status_label": status_label(technology.status),
        "requirements": requirements,
        "layers": layers,
        "defaults": [
            {
                "model": item,
                "requires_explicit_input": requires_explicit_foundation_input(technology, item),
                "requirement_name": REQUIREMENT_NAMES.get(item.material_requirement.code, item.material_requirement.code)
                if item.material_requirement else None,
                "display_value": names["categories"].get(uuid.UUID(str(item.default_value["value"])), str(item.default_value["value"]))
                if item.value_type == "MATERIAL_CLASS" else str(item.default_value["value"]),
                "alternatives": tuple(item.allowed_values.get("values", ()))
                if item.value_type == "ENUM" else (),
            }
            for item in active_defaults(technology)
        ],
        "nodes": [
            {
                "model": item,
                "conditions": _human_mapping(item.conditions),
                "condition_pair": _first_pair(item.conditions),
            }
            for item in sorted(technology.nodes, key=lambda value: value.code)
        ],
        "work_steps": work_steps,
        "norms": norms,
        "compatibility": compatibility,
        "rules": rules,
        "rule_groups": rule_groups,
        "evidence": evidence,
        "source_groups": tuple(source_groups.values()),
        "revisions": revisions,
        "activation_blockers": activation_blockers,
        "warnings": warnings,
        "material_options": material_options,
        "category_options": category_options,
        "type_options": type_options,
        "document_options": document_options,
        "resource_options": resource_options,
        "work_catalog": work_items,
    }


def format_consumption_norm(norm: ConsumptionNorm) -> str:
    return (
        f"{_decimal(norm.consumption_quantity)} {norm.consumption_unit} / "
        f"{_decimal(norm.basis_quantity)} {norm.basis_unit}"
    )


def format_conditions(conditions: Iterable[Mapping[str, Any]] | None) -> tuple[str, ...]:
    return tuple(format_condition(item) for item in conditions or ())


def format_condition(condition: Mapping[str, Any]) -> str:
    field = str(condition.get("field") or "условие")
    field_label = FIELD_LABELS.get(field, _words(field))
    operator = str(condition.get("operator") or "EQUAL")
    operator_label = OPERATOR_LABELS.get(operator, _words(operator))
    value = condition.get("value")
    if operator == "EXISTS":
        return f"{field_label}: {'задано' if value is not False else 'не задано'}"
    if isinstance(value, (list, tuple)):
        value_label = "–".join(str(item) for item in value) if operator == "BETWEEN" else ", ".join(str(item) for item in value)
    else:
        value_label = str(value)
    unit = " °C" if field.endswith("temperature_c") or field == "temperature_c" else " %" if field.endswith("percent") else " мм" if field.endswith("_mm") else ""
    return f"{field_label} {operator_label} {value_label}{unit}"


def format_selector(
    kind: str,
    payload: Mapping[str, Any] | None,
    names: Mapping[str, Mapping[uuid.UUID, str]],
    requirement_codes: Mapping[uuid.UUID, str],
) -> str:
    values = payload or {}
    if kind == "CANONICAL_MATERIAL":
        return names["materials"].get(_uuid(values.get("canonical_material_id")), "Материал M1 недоступен")
    if kind == "MATERIAL_CLASS":
        category = names["categories"].get(_uuid(values.get("material_category_id")))
        material_type = names["types"].get(_uuid(values.get("material_type_id")))
        return category or material_type or "Класс M1 не найден"
    if kind == "MATERIAL_REQUIREMENT":
        return requirement_codes.get(_uuid(values.get("material_requirement_id")), "Требование не найдено")
    if kind == "ROLE":
        return _words(str(values.get("material_role_code") or "Роль не задана"))
    if kind == "TECHNICAL_CONSTRAINTS":
        return _human_mapping(values.get("technical_constraints") or {}) or "Ограничения не заданы"
    return SELECTOR_LABELS.get(kind, _words(kind))


def blocker_label(code: str) -> str:
    if code in BLOCKER_LABELS:
        return BLOCKER_LABELS[code]
    if code.startswith("missing_m1_field:"):
        return f"В M1 отсутствует обязательное поле: {_words(code.split(':', 1)[1])}."
    if code.startswith("m1_blocker:"):
        return f"Блокирующая проверка M1: {_words(code.split(':', 1)[1])}."
    if code.startswith("broken_or_unverified_evidence:"):
        return "Связанное подтверждение M1 отсутствует или не прошло проверку."
    if code.startswith("missing_m1_property:"):
        return f"Не найдено техническое свойство M1: {_words(code.split(':', 1)[1])}."
    return _words(code).capitalize() + "."


def _knowledge_blockers(
    entity: Any,
    technology: Technology,
    verified_evidence: Iterable[uuid.UUID],
) -> list[str]:
    try:
        codes = validate_knowledge_activation(
            entity,
            technology,
            technology.evidence_references,
            verified_evidence_reference_ids=verified_evidence,
            allow_draft_technology=True,
        )
    except ValueError:
        return ["Условия записи повреждены и требуют проверки специалистом."]
    return [blocker_label(code) for code in codes]


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, _words(status))


def _require_editable(technology: Technology, role_code: str) -> None:
    require_module2_access(role_code, AccessLevel.EDIT)
    if technology.status != TechnologyLifecycle.DRAFT.value:
        raise Module2TechnologyError("Изменять можно только черновую редакцию технологии.")


def _require_item_draft(item: Any) -> None:
    if getattr(item, "status", None) != TechnologyLifecycle.DRAFT.value:
        raise Module2WorkbenchError("Изменять или удалять можно только черновую запись.")


def _find(values: Sequence[Any], item_id: uuid.UUID | None) -> Any:
    item = next((value for value in values if value.id == item_id), None)
    if item is None:
        raise Module2WorkbenchError("Запись Workbench не найдена.")
    return item


def _find_by(values: Sequence[Any], field: str, expected: Any) -> Any | None:
    return next((value for value in values if getattr(value, field) == expected), None)


def _ensure_unique(values: Sequence[Any], field: str, expected: Any, current: Any | None) -> None:
    if any(value is not current and getattr(value, field) == expected for value in values):
        label = "позиция" if field == "position" else "код"
        raise Module2WorkbenchError(f"Такой {label} уже используется в этой редакции.")


def _ensure_not_referenced(technology: Technology, component: str, item: Any) -> None:
    if component == "requirement":
        if any(layer.material_requirement_id == item.id or layer.material_requirement is item for layer in technology.layers):
            raise Module2WorkbenchError("Требование используется слоем и не может быть удалено.")
        if any(norm.scope_requirement_id == item.id for norm in technology.consumption_norms):
            raise Module2WorkbenchError("Требование используется нормой расхода.")
    if component == "layer" and any(norm.scope_layer_id == item.id for norm in technology.consumption_norms):
        raise Module2WorkbenchError("Слой используется нормой расхода.")
    if component == "work-step":
        if any(norm.scope_work_step_id == item.id for norm in technology.consumption_norms):
            raise Module2WorkbenchError("Работа используется нормой расхода.")
        if any(item.work_code in (peer.dependency_step_codes or ()) for peer in technology.work_steps if peer is not item):
            raise Module2WorkbenchError("Работа указана как зависимость следующего шага.")
    references = {
        "requirement": "MATERIAL_REQUIREMENT",
        "layer": "LAYER",
        "node": "NODE",
        "work-step": "WORK_STEP",
        "norm": "CONSUMPTION_NORM",
        "compatibility": "COMPATIBILITY_RULE",
        "rule": "KNOWLEDGE_RULE",
    }
    target_kind = references.get(component)
    if target_kind and any(
        evidence.target_kind == target_kind
        and evidence.target_reference in {str(item.id), getattr(item, "code", None), getattr(item, "norm_code", None), getattr(item, "rule_code", None)}
        for evidence in technology.evidence_references
    ):
        raise Module2WorkbenchError("Сначала удалите подтверждение, связанное с этой записью.")


def _evidence_target(technology: Technology, target_kind: str, target_reference: Any) -> Any:
    if target_kind == "TECHNOLOGY":
        return technology
    collection = {
        "LAYER": technology.layers,
        "MATERIAL_REQUIREMENT": technology.requirements,
        "NODE": technology.nodes,
        "WORK_STEP": technology.work_steps,
        "CONSUMPTION_NORM": technology.consumption_norms,
        "COMPATIBILITY_RULE": technology.compatibility_rules,
        "KNOWLEDGE_RULE": technology.knowledge_rules,
    }.get(target_kind)
    if collection is None:
        raise Module2WorkbenchError("Неизвестная цель подтверждения.")
    return _find(collection, _uuid(target_reference))


async def _options(db: AsyncSession, model: type[Any], label_column: Any, *, limit: int = 200) -> tuple[tuple[uuid.UUID, str], ...]:
    result = await db.execute(select(model.id, label_column).order_by(label_column).limit(limit))
    return tuple((item_id, str(label)) for item_id, label in result.all())


def _requirement_reference(item: TechnologyMaterialRequirement, names: Mapping[str, Mapping[uuid.UUID, str]]) -> str:
    if item.canonical_material_id:
        return names["materials"].get(item.canonical_material_id, "Материал M1 недоступен")
    if item.material_category_id:
        return names["categories"].get(item.material_category_id, "Категория M1 недоступна")
    if item.material_type_id:
        return names["types"].get(item.material_type_id, "Тип материала M1 недоступен")
    if item.material_role_code:
        return _words(item.material_role_code)
    return _human_mapping(item.technical_constraints) or "Не разрешено"


def _human_mapping(value: Mapping[str, Any] | None) -> str:
    if not value:
        return ""
    return "; ".join(f"{_words(str(key))}: {_human_value(item)}" for key, item in value.items())


def _first_pair(value: Mapping[str, Any] | None) -> tuple[str, str]:
    if not value:
        return "", ""
    key, item = next(iter(value.items()))
    return str(key), _human_value(item)


def _selector_form(kind: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
    values = payload or {}
    constraint_field, constraint_value = _first_pair(values.get("technical_constraints") or {})
    return {
        "kind": kind,
        "canonical_material_id": values.get("canonical_material_id") or "",
        "material_category_id": values.get("material_category_id") or "",
        "material_type_id": values.get("material_type_id") or "",
        "material_requirement_id": values.get("material_requirement_id") or "",
        "material_role_code": values.get("material_role_code") or "",
        "constraint_field": constraint_field,
        "constraint_value": constraint_value,
    }


def _condition_form(conditions: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    if not conditions:
        return {
            "source": "CONTEXT",
            "field": "",
            "operator": "EQUAL",
            "value": "",
            "required": False,
        }
    item = conditions[0]
    value = item.get("value")
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(part) for part in value)
    return {
        "source": item.get("source") or "CONTEXT",
        "field": item.get("field") or "",
        "operator": item.get("operator") or "EQUAL",
        "value": "" if value is None else value,
        "required": bool(item.get("required_for_activation")),
    }


def _human_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return ", ".join(f"{_words(str(key))} {item}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _words(value: str) -> str:
    return value.replace("_", " ").strip().lower()


def _decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _command(value: Any, model_type: type[Any]) -> Any:
    return value if isinstance(value, model_type) else model_type.model_validate(value)


def _copy_fields(target: Any, source: Any, fields: Iterable[str]) -> None:
    for field in fields:
        value = getattr(source, field)
        setattr(target, field, value.copy() if isinstance(value, (dict, list)) else value)
