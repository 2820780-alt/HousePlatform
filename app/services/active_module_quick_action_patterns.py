from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN: tuple[str, ...] = (
    "MODULE_02_KNOWLEDGE_BASE",
    "MODULE_03_USERS_ROLES",
    "MODULE_04_WORKS_COSTS",
    "MODULE_05_ESTIMATE_ENGINE",
    "MODULE_06_ESTIMATE_AUDIT",
    "MODULE_07_DIGITAL_HOUSE",
    "MODULE_09_PROCUREMENT",
    "MODULE_10_MARKETPLACE",
    "MODULE_11_ANALYTICS",
)

PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY: tuple[str, ...] = (
    "MODULE_12_AI_ASSISTANT",
    "MODULE_13_PROJECT_COLLABORATION",
    "MODULE_15_CONTRACTS",
    "MODULE_16_LOGISTICS_DELIVERY",
    "MODULE_17_FINANCE_PAYMENTS",
    "MODULE_18_QUALITY_CONTROL",
    "MODULE_19_CONSTRUCTOR_LITE",
    "MODULE_20_SITE_SUPERVISION",
    "MODULE_21_WARRANTY_SERVICE",
)

MODULE_UI_READY = "UI_READY"
PATTERN_READY_NO_UI = "PATTERN_READY_NO_UI"
PLANNED_NO_ACTIVE_ACTIONS = "PLANNED_NO_ACTIVE_ACTIONS"
PLANNED_DOCUMENTATION_ONLY = "PLANNED_DOCUMENTATION_ONLY"

PATTERN_LAYER_NOTE = (
    "QuickActionCandidatePattern is documentation/adapter metadata for module-owned user shortcuts. "
    "It is not RBAC, not WidgetRegistry, not a business payload, and not a Dashboard engine."
)


@dataclass(frozen=True)
class QuickActionCandidatePattern:
    sourceModuleCode: str
    featureCode: str
    actionKey: str
    title: str
    route: str | None = None
    configMode: str = "NO_CONFIG"
    canPinToAtomCard: bool = True
    status: str = "PATTERN"
    note: str = PATTERN_LAYER_NOTE
    uiStatus: str = PATTERN_READY_NO_UI
    icon: str | None = None
    atomCardAccent: str = "cyan"
    ownerModuleOwnsExecution: bool = True
    isVisibleToOrdinaryUsers: bool = True
    isExecutable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_active_module_quick_action_patterns() -> list[dict[str, Any]]:
    return [item.to_dict() for item in _quick_action_candidate_patterns()]


def get_quick_action_patterns_for_module(source_module_code: str) -> list[dict[str, Any]]:
    return [
        item.to_dict()
        for item in _quick_action_candidate_patterns()
        if item.sourceModuleCode == source_module_code
    ]


def get_quick_action_pattern_readiness() -> list[dict[str, Any]]:
    definitions = _quick_action_candidate_patterns()
    return [
        {
            "sourceModuleCode": module_code,
            "uiStatus": _module_ui_status(module_code),
            "candidateCount": len([item for item in definitions if item.sourceModuleCode == module_code]),
            "patternLayer": "module_owned_user_quick_actions",
            "requiresModuleUi": _module_ui_status(module_code) == PATTERN_READY_NO_UI,
            "note": PATTERN_LAYER_NOTE,
        }
        for module_code in ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN
    ]


def get_planned_module_quick_action_patterns() -> list[dict[str, Any]]:
    return [item.to_dict() for item in _planned_quick_action_candidate_patterns()]


def get_planned_module_quick_action_compatibility_readiness() -> list[dict[str, Any]]:
    definitions = _planned_quick_action_candidate_patterns()
    return [
        {
            "sourceModuleCode": module_code,
            "uiStatus": PLANNED_NO_ACTIVE_ACTIONS,
            "candidateCount": len([item for item in definitions if item.sourceModuleCode == module_code]),
            "patternLayer": "planned_module_quick_action_documentation",
            "requiresModuleUi": True,
            "visibleToOrdinaryUsers": False,
            "executable": False,
            "note": (
                "Planned module quick actions are documentation-only compatibility placeholders. "
                "They must not be shown as active actions to ordinary users."
            ),
        }
        for module_code in PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY
    ]


def _quick_action_candidate_patterns() -> tuple[QuickActionCandidatePattern, ...]:
    return (
        _candidate(
            "MODULE_02_KNOWLEDGE_BASE",
            "TECHNOLOGY_TREE",
            "OPEN_TECHNOLOGY_TREE",
            "Открыть дерево технологий",
            route="/modules/knowledge-base",
            icon="◇",
            atomCardAccent="green",
        ),
        _candidate(
            "MODULE_02_KNOWLEDGE_BASE",
            "TECHNOLOGY_MODERATION",
            "OPEN_TECHNOLOGY_MODERATION",
            "Открыть модерацию технологий",
            route="/modules/knowledge-base",
            icon="!",
            atomCardAccent="orange",
        ),
        _candidate(
            "MODULE_03_USERS_ROLES",
            "USER_ADMIN",
            "OPEN_USERS_ADMIN",
            "Открыть пользователей",
            route="/api/v1/admin/users-roles/view#users",
            icon="U",
            atomCardAccent="cyan",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_03_USERS_ROLES",
            "MODULE_REGISTRY",
            "OPEN_MODULE_REGISTRY",
            "Открыть реестр модулей",
            route="/api/v1/admin/module-registry/view",
            icon="R",
            atomCardAccent="blue",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_03_USERS_ROLES",
            "AUDIT_LOG",
            "OPEN_AUDIT_LOG",
            "Открыть журнал изменений",
            route="/api/v1/admin/users-roles/view#audit-log",
            icon="A",
            atomCardAccent="purple",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_04_WORKS_COSTS",
            "WORK_RATE_REGISTRY",
            "OPEN_WORK_RATES",
            "Открыть расценки работ",
            route="/modules/works-costs",
            icon="W",
            atomCardAccent="blue",
        ),
        _candidate(
            "MODULE_05_ESTIMATE_ENGINE",
            "ESTIMATE_CREATE",
            "CREATE_ESTIMATE",
            "Создать смету",
            route="/modules/estimates",
            icon="+",
            atomCardAccent="green",
        ),
        _candidate(
            "MODULE_06_ESTIMATE_AUDIT",
            "ESTIMATE_AUDIT_RUN",
            "RUN_ESTIMATE_AUDIT",
            "Проверить смету",
            route="/modules/estimate-audit",
            icon="!",
            atomCardAccent="orange",
        ),
        _candidate(
            "MODULE_07_DIGITAL_HOUSE",
            "HOUSE_PROFILE",
            "OPEN_OBJECT_CARD",
            "Открыть карточку объекта",
            route="/modules/digital-house",
            icon="H",
            atomCardAccent="cyan",
        ),
        _candidate(
            "MODULE_09_PROCUREMENT",
            "PROCUREMENT_REQUEST",
            "CREATE_PROCUREMENT_REQUEST",
            "Сформировать заявку поставщику",
            route="/modules/procurement",
            icon="→",
            atomCardAccent="orange",
        ),
        _candidate(
            "MODULE_10_MARKETPLACE",
            "MARKETPLACE_SEARCH",
            "OPEN_MARKETPLACE",
            "Открыть витрину",
            route="/modules/marketplace",
            icon="M",
            atomCardAccent="purple",
        ),
        _candidate(
            "MODULE_11_ANALYTICS",
            "PRICE_DYNAMICS",
            "OPEN_PRICE_DYNAMICS",
            "Открыть динамику цен",
            route="/api/v1/admin/price-dynamics/view",
            icon="↗",
            atomCardAccent="purple",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_11_ANALYTICS",
            "PRICE_DYNAMICS",
            "OPEN_CURRENT_PRICE_DYNAMICS_SLICE",
            "Открыть текущий срез динамики цен",
            route="/api/v1/admin/price-dynamics/view",
            configMode="CONFIG_SNAPSHOT",
            icon="≋",
            atomCardAccent="blue",
            uiStatus=MODULE_UI_READY,
        ),
    )


def _planned_quick_action_candidate_patterns() -> tuple[QuickActionCandidatePattern, ...]:
    return (
        _planned_candidate(
            "MODULE_12_AI_ASSISTANT",
            "AI_ASSISTANT_HOME",
            "OPEN_AI_ASSISTANT",
            "Открыть AI-помощник",
            route="/modules/ai-assistant",
            icon="AI",
            atomCardAccent="purple",
        ),
        _planned_candidate(
            "MODULE_13_PROJECT_COLLABORATION",
            "PROJECT_ROOM",
            "OPEN_PROJECT_ROOM",
            "Открыть комнату проекта",
            route="/modules/project-collaboration",
            icon="P",
            atomCardAccent="blue",
        ),
        _planned_candidate(
            "MODULE_15_CONTRACTS",
            "CONTRACTS_HOME",
            "OPEN_CONTRACTS",
            "Открыть договоры",
            route="/modules/contracts",
            icon="C",
            atomCardAccent="cyan",
        ),
        _planned_candidate(
            "MODULE_16_LOGISTICS_DELIVERY",
            "LOGISTICS_HOME",
            "OPEN_LOGISTICS",
            "Открыть логистику",
            route="/modules/logistics-delivery",
            icon="L",
            atomCardAccent="orange",
        ),
        _planned_candidate(
            "MODULE_17_FINANCE_PAYMENTS",
            "FINANCE_BUDGET",
            "OPEN_BUDGET",
            "Открыть бюджет",
            route="/modules/finance-payments",
            icon="F",
            atomCardAccent="green",
        ),
        _planned_candidate(
            "MODULE_18_QUALITY_CONTROL",
            "QUALITY_CHECKS",
            "OPEN_QUALITY_CHECKS",
            "Открыть контроль качества",
            route="/modules/quality-control",
            icon="Q",
            atomCardAccent="red",
        ),
        _planned_candidate(
            "MODULE_19_CONSTRUCTOR_LITE",
            "CONSTRUCTOR_PLAN",
            "OPEN_PLAN",
            "Открыть план",
            route="/modules/constructor-lite",
            icon="P",
            atomCardAccent="purple",
        ),
        _planned_candidate(
            "MODULE_20_SITE_SUPERVISION",
            "SITE_SUPERVISION_JOURNAL",
            "OPEN_SITE_JOURNAL",
            "Открыть журнал технадзора",
            route="/modules/site-supervision",
            icon="S",
            atomCardAccent="blue",
        ),
        _planned_candidate(
            "MODULE_21_WARRANTY_SERVICE",
            "WARRANTY_REQUESTS",
            "OPEN_WARRANTY_REQUESTS",
            "Открыть гарантийные обращения",
            route="/modules/warranty-service",
            icon="W",
            atomCardAccent="cyan",
        ),
    )


def _candidate(
    source_module_code: str,
    feature_code: str,
    action_key: str,
    title: str,
    *,
    route: str,
    configMode: str = "NO_CONFIG",
    icon: str | None = None,
    atomCardAccent: str = "cyan",
    uiStatus: str = PATTERN_READY_NO_UI,
) -> QuickActionCandidatePattern:
    return QuickActionCandidatePattern(
        sourceModuleCode=source_module_code,
        featureCode=feature_code,
        actionKey=action_key,
        title=title,
        route=route,
        configMode=configMode,
        icon=icon,
        atomCardAccent=atomCardAccent,
        uiStatus=uiStatus,
    )


def _planned_candidate(
    source_module_code: str,
    feature_code: str,
    action_key: str,
    title: str,
    *,
    route: str,
    icon: str | None = None,
    atomCardAccent: str = "cyan",
) -> QuickActionCandidatePattern:
    return QuickActionCandidatePattern(
        sourceModuleCode=source_module_code,
        featureCode=feature_code,
        actionKey=action_key,
        title=title,
        route=route,
        canPinToAtomCard=False,
        status=PLANNED_DOCUMENTATION_ONLY,
        uiStatus=PLANNED_NO_ACTIVE_ACTIONS,
        icon=icon,
        atomCardAccent=atomCardAccent,
        isVisibleToOrdinaryUsers=False,
        isExecutable=False,
        metadata={
            "compatibilityOnly": True,
            "mustNotRenderAsActive": True,
            "requiresFutureModuleUi": True,
        },
    )


def _module_ui_status(source_module_code: str) -> str:
    if any(item.sourceModuleCode == source_module_code and item.uiStatus == MODULE_UI_READY for item in _quick_action_candidate_patterns()):
        return MODULE_UI_READY
    return PATTERN_READY_NO_UI
