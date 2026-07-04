from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN: tuple[str, ...] = ()

PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY: tuple[str, ...] = ()

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
    return ()

def _planned_quick_action_candidate_patterns() -> tuple[QuickActionCandidatePattern, ...]:
    return ()

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
