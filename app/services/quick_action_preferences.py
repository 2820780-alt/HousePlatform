from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.services.audit_log_service import AuditLogType


MAX_MODULE_BAR_QUICK_ACTIONS = 9
MAX_MODULE_CARD_QUICK_ACTIONS = 3
QUICK_ACTION_PREFERENCE_LAYER = "module03_quick_action_preference_preview"
QUICK_ACTION_PREFERENCE_STORAGE = "UserDashboardLayout.quickActions[] / Module08 CabinetQuickAction later"
QUICK_ACTION_PREFERENCE_NOTE = (
    "Quick action preference stores only a reference to an owning-module saved configuration. "
    "The owning module executes the action and must call requirePermission() before every run."
)


@dataclass(frozen=True)
class UserQuickActionPreference:
    userId: str
    quickActionCode: str
    sourceModuleCode: str
    isEnabled: bool
    isPinnedInModule: bool
    isPinnedOnModuleCard: bool
    sortOrder: int
    disabledReason: str | None = None
    preferenceLayer: str = "module03_user_quick_action_preference"
    storageLayer: str = "user_module_quick_actions / UserDashboardLayout.quickActions[] compatibility"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuickActionPreferencePreview:
    quickActionCode: str
    actionCode: str
    sourceModuleCode: str
    canonicalModuleCode: str
    savedConfigRef: str
    route: str | None
    workspaceId: str | None
    activeRegionCode: str | None
    activeCabinetId: str | None
    canRunQuickAction: bool
    unavailableReason: str
    requiresPermissionOnRun: bool = True
    preferenceLayer: str = QUICK_ACTION_PREFERENCE_LAYER
    storageLayer: str = QUICK_ACTION_PREFERENCE_STORAGE
    auditEventType: str = AuditLogType.QUICK_ACTION_PREFERENCE_CHANGED.value
    sourceModuleOwnsExecution: bool = True
    warning: str = QUICK_ACTION_PREFERENCE_NOTE
    featureCode: str | None = None
    widgetCode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_user_quick_action_preference(
    *,
    user_id: str,
    quick_action_code: str,
    source_module_code: str,
    is_enabled: bool = True,
    is_pinned_in_module: bool = True,
    is_pinned_on_module_card: bool = False,
    sort_order: int = 1000,
    disabled_reason: str | None = None,
) -> dict[str, Any]:
    if not source_module_code:
        raise ValueError("source_module_code is required for UserQuickActionPreference.")
    return UserQuickActionPreference(
        userId=user_id,
        quickActionCode=quick_action_code,
        sourceModuleCode=source_module_code,
        isEnabled=bool(is_enabled),
        isPinnedInModule=bool(is_pinned_in_module),
        isPinnedOnModuleCard=bool(is_pinned_on_module_card),
        sortOrder=int(sort_order),
        disabledReason=disabled_reason,
    ).to_dict()


def select_module_bar_preferences(preferences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            item
            for item in preferences
            if item.get("isEnabled") is not False and item.get("isPinnedInModule") is not False
        ],
        key=lambda item: (int(item.get("sortOrder") or 1000), str(item.get("quickActionCode") or "")),
    )[:MAX_MODULE_BAR_QUICK_ACTIONS]


def select_module_card_preferences(preferences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            item
            for item in preferences
            if item.get("isEnabled") is not False and item.get("isPinnedOnModuleCard") is True
        ],
        key=lambda item: (int(item.get("sortOrder") or 1000), str(item.get("quickActionCode") or "")),
    )[:MAX_MODULE_CARD_QUICK_ACTIONS]


def build_quick_action_preference_preview(
    action: Any,
    *,
    access_context: dict[str, Any] | None = None,
    module8_preview: dict[str, Any] | None = None,
    is_action_allowed: bool = False,
    unavailable_reason: str = "",
) -> dict[str, Any]:
    action_data = _dict_value(action)
    access_data = access_context or {}
    module8_data = module8_preview or {}
    quick_action_code = str(action_data.get("quickActionCode") or action_data.get("quick_action_code") or "")
    action_code = str(action_data.get("requiredActionCode") or action_data.get("actionCode") or "")
    source_module_code = str(action_data.get("sourceModuleCode") or "UNKNOWN")
    canonical_module_code = str(action_data.get("canonicalModuleCode") or source_module_code)
    return QuickActionPreferencePreview(
        quickActionCode=quick_action_code,
        actionCode=action_code,
        sourceModuleCode=source_module_code,
        canonicalModuleCode=canonical_module_code,
        featureCode=_string_or_none(action_data.get("featureCode")),
        widgetCode=_string_or_none(action_data.get("widgetCode")),
        savedConfigRef=_saved_config_ref(access_data, source_module_code, quick_action_code),
        route=_string_or_none(action_data.get("route")),
        workspaceId=_string_or_none(access_data.get("workspaceId")),
        activeRegionCode=_string_or_none(access_data.get("activeRegionCode")),
        activeCabinetId=_string_or_none(module8_data.get("activeCabinetId") or access_data.get("activeCabinetId")),
        canRunQuickAction=is_action_allowed,
        unavailableReason=unavailable_reason or ("allowed" if is_action_allowed else "Quick action is not allowed."),
    ).to_dict()


def _saved_config_ref(access_data: dict[str, Any], source_module_code: str, quick_action_code: str) -> str:
    user_id = access_data.get("userId") or "preview-user"
    workspace_id = access_data.get("workspaceId") or "workspace"
    return f"{source_module_code}:{quick_action_code}:{user_id}:{workspace_id}:saved-config-ref"


def _dict_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
