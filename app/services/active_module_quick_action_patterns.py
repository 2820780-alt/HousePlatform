from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN: tuple[str, ...] = (
    "MODULE_01_MATERIAL_HUB",
    "MODULE_03_USERS_ROLES",
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
            "MODULE_01_MATERIAL_HUB",
            "MATERIAL_MODERATION",
            "OPEN_MATERIAL_MODERATION",
            "Открыть модерацию материалов",
            route="/api/v1/admin/material-hub/view/moderation",
            icon="shield",
            atomCardAccent="orange",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_01_MATERIAL_HUB",
            "SOURCE_PRODUCTS",
            "CHECK_SOURCE_CARDS",
            "Проверить карточки источников",
            route="/api/v1/admin/material-hub/view/products?status=NEEDS_REVIEW",
            icon="list-check",
            atomCardAccent="green",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_01_MATERIAL_HUB",
            "SUPPLIER_PRICE_UPLOAD",
            "UPLOAD_SUPPLIER_PRICE",
            "Загрузить прайс поставщика",
            route="/api/v1/admin/material-hub/view",
            configMode="CONFIG_SNAPSHOT",
            icon="upload",
            atomCardAccent="blue",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_01_MATERIAL_HUB",
            "SOURCE_ANALYSIS",
            "RUN_SOURCE_ANALYSIS",
            "Запустить анализ источника",
            route="/api/v1/admin/material-hub/view",
            configMode="CONFIG_SNAPSHOT",
            icon="scan-search",
            atomCardAccent="cyan",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_03_USERS_ROLES",
            "USERS_DIRECTORY",
            "VIEW",
            "Открыть пользователей",
            route="/api/v1/admin/users-roles/view#users",
            icon="users",
            atomCardAccent="cyan",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_03_USERS_ROLES",
            "ACCESS_MATRIX",
            "VIEW",
            "Открыть матрицу доступов",
            route="/api/v1/admin/users-roles/view#access-matrix",
            icon="shield-check",
            atomCardAccent="blue",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_03_USERS_ROLES",
            "AUDIT_LOG",
            "VIEW",
            "Открыть историю изменений",
            route="/api/v1/admin/users-roles/view/history",
            icon="history",
            atomCardAccent="purple",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_11_ANALYTICS",
            "PRICE_DYNAMICS",
            "OPEN_PRICE_DYNAMICS",
            "Открыть динамику цен",
            route="/api/v1/admin/price-dynamics/view",
            icon="chart-line",
            atomCardAccent="cyan",
            uiStatus=MODULE_UI_READY,
        ),
        _candidate(
            "MODULE_11_ANALYTICS",
            "PRICE_DYNAMICS",
            "OPEN_CURRENT_PRICE_DYNAMICS_SLICE",
            "Открыть текущий срез динамики цен",
            route="/api/v1/admin/price-dynamics/view",
            configMode="CONFIG_SNAPSHOT",
            icon="filter",
            atomCardAccent="blue",
            uiStatus=MODULE_UI_READY,
        ),
    )


def _planned_quick_action_candidate_patterns() -> tuple[QuickActionCandidatePattern, ...]:
    return (
        _planned_candidate(
            "MODULE_12_AI_ASSISTANT",
            "AI_ASSISTANT",
            "OPEN_AI_ASSISTANT",
            "Открыть AI ассистента",
            route="/api/v1/admin/cabinet/view",
            icon="sparkles",
            atomCardAccent="cyan",
        ),
        _planned_candidate(
            "MODULE_13_PROJECT_COLLABORATION",
            "PROJECT_COLLABORATION",
            "OPEN_PROJECT_COLLABORATION",
            "Открыть совместную работу",
            route="/api/v1/admin/cabinet/view",
            icon="users-round",
            atomCardAccent="blue",
        ),
        _planned_candidate(
            "MODULE_15_CONTRACTS",
            "CONTRACTS",
            "OPEN_CONTRACTS",
            "Открыть договоры",
            route="/api/v1/admin/cabinet/view",
            icon="file-signature",
            atomCardAccent="purple",
        ),
        _planned_candidate(
            "MODULE_16_LOGISTICS_DELIVERY",
            "LOGISTICS_DELIVERY",
            "OPEN_LOGISTICS",
            "Открыть логистику",
            route="/api/v1/admin/cabinet/view",
            icon="truck",
            atomCardAccent="orange",
        ),
        _planned_candidate(
            "MODULE_17_FINANCE_PAYMENTS",
            "FINANCE_PAYMENTS",
            "OPEN_FINANCE",
            "Открыть финансы",
            route="/api/v1/admin/cabinet/view",
            icon="wallet",
            atomCardAccent="green",
        ),
        _planned_candidate(
            "MODULE_18_QUALITY_CONTROL",
            "QUALITY_CONTROL",
            "OPEN_QUALITY_CONTROL",
            "Открыть контроль качества",
            route="/api/v1/admin/cabinet/view",
            icon="badge-check",
            atomCardAccent="cyan",
        ),
        _planned_candidate(
            "MODULE_19_CONSTRUCTOR_LITE",
            "CONSTRUCTOR_LITE",
            "OPEN_CONSTRUCTOR_LITE",
            "Открыть конструктор Lite",
            route="/api/v1/admin/cabinet/view",
            icon="drafting-compass",
            atomCardAccent="blue",
        ),
        _planned_candidate(
            "MODULE_20_SITE_SUPERVISION",
            "SITE_SUPERVISION",
            "OPEN_SITE_SUPERVISION",
            "Открыть стройконтроль",
            route="/api/v1/admin/cabinet/view",
            icon="hard-hat",
            atomCardAccent="orange",
        ),
        _planned_candidate(
            "MODULE_21_WARRANTY_SERVICE",
            "WARRANTY_SERVICE",
            "OPEN_WARRANTY_SERVICE",
            "Открыть гарантийное обслуживание",
            route="/api/v1/admin/cabinet/view",
            icon="shield",
            atomCardAccent="green",
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
    if any(
        item.sourceModuleCode == source_module_code and item.uiStatus == MODULE_UI_READY
        for item in _quick_action_candidate_patterns()
    ):
        return MODULE_UI_READY
    return PATTERN_READY_NO_UI
