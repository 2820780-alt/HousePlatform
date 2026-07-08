from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.access_context_for_cabinet import AccessContextForCabinet
from app.services.partner_portal_dashboard_presets import (
    filter_dashboard_preset_for_access,
)


MODULE_03_USERS_ROLES = "MODULE_03_USERS_ROLES"
DEPRECATED_CABINET_QUICK_ACTIONS_NOTE = (
    "Deprecated compatibility field. Cabinet presets/preferences must not seed "
    "quick actions; only user_module_quick_actions may store saved/pinned actions."
)


@dataclass(frozen=True)
class CabinetBlockPreferenceDTO:
    blockCode: str
    isVisible: bool = True
    sortOrder: int = 1000
    isPinned: bool = False
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetWidgetPreferenceDTO:
    widgetCode: str
    isVisible: bool = True
    zoneCode: str | None = None
    size: str | None = None
    sortOrder: int = 1000
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetModuleShortcutDTO:
    shortcutCode: str
    title: str
    targetModuleCode: str
    route: str | None = None
    icon: str | None = None
    sortOrder: int = 1000
    isVisible: bool = True
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetQuickActionDTO:
    quickActionCode: str
    isVisible: bool = True
    sortOrder: int = 1000
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetDashboardPreferenceState:
    presetCode: str
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    userId: str | None = None
    workspaceId: str | None = None
    cabinetId: str | None = None
    activeRegionCode: str | None = None
    blockPreferences: list[CabinetBlockPreferenceDTO] = field(default_factory=list)
    widgetPreferences: list[CabinetWidgetPreferenceDTO] = field(default_factory=list)
    moduleShortcuts: list[CabinetModuleShortcutDTO] = field(default_factory=list)
    quickActions: list[CabinetQuickActionDTO] = field(
        default_factory=list,
        metadata={"deprecated": DEPRECATED_CABINET_QUICK_ACTIONS_NOTE},
    )
    deniedOperations: list[dict[str, Any]] = field(default_factory=list)
    isMock: bool = True
    isResetToRoleTemplate: bool = False
    compatibilityNote: str = (
        "Module 08 stores cabinet display preferences. Module 03 still filters rights; "
        "Dashboard only renders the resulting preset/layout data."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["blockPreferences"] = [item.to_dict() for item in self.blockPreferences]
        data["widgetPreferences"] = [item.to_dict() for item in self.widgetPreferences]
        data["moduleShortcuts"] = [item.to_dict() for item in self.moduleShortcuts]
        data["quickActions"] = [item.to_dict() for item in self.quickActions]
        return data


def build_default_cabinet_dashboard_preferences(
    preset_code: str,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
    user_id: str | None = None,
    workspace_id: str | None = None,
    cabinet_id: str | None = None,
) -> CabinetDashboardPreferenceState:
    preset = filter_dashboard_preset_for_access(
        preset_code,
        access_context=access_context,
        include_future=include_future,
    )
    access_data = _access_context_dict(access_context)
    blocks = _unique_strings(
        [*preset.get("recommendedBlockCodes", []), *preset.get("futureBlockCodes", [])]
    )
    widgets = _unique_strings(preset.get("recommendedWidgetCodes", []))
    return CabinetDashboardPreferenceState(
        presetCode=preset["presetCode"],
        userId=user_id or _string_or_none(access_data.get("userId")),
        workspaceId=workspace_id or _string_or_none(access_data.get("workspaceId")),
        cabinetId=cabinet_id,
        activeRegionCode=_string_or_none(access_data.get("activeRegionCode")),
        blockPreferences=[
            CabinetBlockPreferenceDTO(blockCode=block_code, sortOrder=index * 10)
            for index, block_code in enumerate(blocks, start=1)
        ],
        widgetPreferences=[
            CabinetWidgetPreferenceDTO(
                widgetCode=widget_code,
                sortOrder=index * 10,
                zoneCode=_widget_zone(preset, widget_code),
            )
            for index, widget_code in enumerate(widgets, start=1)
        ],
    )


def apply_cabinet_dashboard_preferences(
    preset_code: str,
    preferences: CabinetDashboardPreferenceState | dict[str, Any] | None = None,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
) -> dict[str, Any]:
    state = _preference_state(preferences, preset_code, access_context=access_context, include_future=include_future)
    preset = filter_dashboard_preset_for_access(
        state.presetCode,
        access_context=access_context,
        include_future=include_future,
    )
    visible_blocks = _ordered_visible_blocks(state)
    visible_widgets = _ordered_visible_widgets(state)

    preset["recommendedBlockCodes"] = [
        block_code
        for block_code in visible_blocks
        if block_code in set(preset.get("recommendedBlockCodes", []) + preset.get("futureBlockCodes", []))
    ]
    preset["futureBlockCodes"] = [
        block_code
        for block_code in preset.get("futureBlockCodes", [])
        if block_code in set(preset["recommendedBlockCodes"])
    ]
    preset["recommendedWidgetCodes"] = [
        widget_code
        for widget_code in visible_widgets
        if widget_code in set(preset.get("recommendedWidgetCodes", []))
    ]
    preset.pop("recommendedQuickActionCodes", None)
    preset["deprecatedRecommendedQuickActionCodes"] = []
    preset["zones"] = [
        _apply_zone_preferences(zone, set(preset["recommendedBlockCodes"]), set(preset["recommendedWidgetCodes"]))
        for zone in preset.get("zones", [])
    ]
    preset["zones"] = [zone for zone in preset["zones"] if zone["blockCodes"] or zone["widgetCodes"]]
    preset["moduleShortcuts"] = [
        item.to_dict()
        for item in sorted(state.moduleShortcuts, key=lambda item: item.sortOrder)
        if item.isVisible
    ]
    preset["preferenceState"] = state.to_dict()
    return preset


def set_block_visibility(
    preferences: CabinetDashboardPreferenceState | dict[str, Any],
    block_code: str,
    is_visible: bool,
) -> CabinetDashboardPreferenceState:
    state = _preference_state(preferences)
    return _replace_block_preference(state, block_code, isVisible=is_visible)


def hide_block(
    preferences: CabinetDashboardPreferenceState | dict[str, Any],
    block_code: str,
) -> CabinetDashboardPreferenceState:
    return set_block_visibility(preferences, block_code, False)


def show_block(
    preferences: CabinetDashboardPreferenceState | dict[str, Any],
    block_code: str,
) -> CabinetDashboardPreferenceState:
    return set_block_visibility(preferences, block_code, True)


def reorder_block(
    preferences: CabinetDashboardPreferenceState | dict[str, Any],
    block_code: str,
    position: int,
) -> CabinetDashboardPreferenceState:
    state = _preference_state(preferences)
    block_codes = [item.blockCode for item in _ordered_blocks(state)]
    if block_code not in block_codes:
        block_codes.append(block_code)
    block_codes = [item for item in block_codes if item != block_code]
    insert_index = max(0, min(position - 1, len(block_codes)))
    block_codes.insert(insert_index, block_code)

    current = {item.blockCode: item for item in state.blockPreferences}
    block_preferences = [
        replace(current.get(code, CabinetBlockPreferenceDTO(blockCode=code)), sortOrder=index * 10)
        for index, code in enumerate(block_codes, start=1)
    ]
    return replace(state, blockPreferences=block_preferences, isResetToRoleTemplate=False)


def pin_block(
    preferences: CabinetDashboardPreferenceState | dict[str, Any],
    block_code: str,
    is_pinned: bool = True,
) -> CabinetDashboardPreferenceState:
    state = _preference_state(preferences)
    return _replace_block_preference(state, block_code, isPinned=is_pinned)


def add_module_shortcut(
    preferences: CabinetDashboardPreferenceState | dict[str, Any],
    *,
    shortcut_code: str,
    title: str,
    target_module_code: str,
    route: str | None = None,
    icon: str | None = None,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
) -> CabinetDashboardPreferenceState:
    state = _preference_state(preferences)
    access_data = _access_context_dict(access_context)
    allowed_modules = set(_list_strings(access_data.get("allowedModuleCodes")))
    if access_context is not None and target_module_code not in allowed_modules:
        return _deny(
            state,
            operation="add_module_shortcut",
            code=shortcut_code,
            reason="Module №3 did not allow targetModuleCode.",
            targetModuleCode=target_module_code,
        )

    existing = [item for item in state.moduleShortcuts if item.shortcutCode != shortcut_code]
    shortcut = CabinetModuleShortcutDTO(
        shortcutCode=shortcut_code,
        title=title,
        targetModuleCode=target_module_code,
        route=route,
        icon=icon,
        sortOrder=(len(existing) + 1) * 10,
    )
    return replace(state, moduleShortcuts=[*existing, shortcut], isResetToRoleTemplate=False)


def remove_widget(
    preferences: CabinetDashboardPreferenceState | dict[str, Any],
    widget_code: str,
) -> CabinetDashboardPreferenceState:
    state = _preference_state(preferences)
    current = {item.widgetCode: item for item in state.widgetPreferences}
    preference = replace(
        current.get(widget_code, CabinetWidgetPreferenceDTO(widgetCode=widget_code)),
        isVisible=False,
    )
    widget_preferences = [
        preference if item.widgetCode == widget_code else item
        for item in state.widgetPreferences
    ]
    if widget_code not in {item.widgetCode for item in state.widgetPreferences}:
        widget_preferences.append(preference)
    return replace(state, widgetPreferences=widget_preferences, isResetToRoleTemplate=False)


def set_quick_action_visibility(
    preferences: CabinetDashboardPreferenceState | dict[str, Any],
    quick_action_code: str,
    is_visible: bool,
) -> CabinetDashboardPreferenceState:
    """Compatibility no-op: cabinet preferences never seed quick actions."""
    return replace(_preference_state(preferences), quickActions=[], isResetToRoleTemplate=False)


def reset_to_role_template(
    preset_code: str,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
) -> CabinetDashboardPreferenceState:
    state = build_default_cabinet_dashboard_preferences(
        preset_code,
        access_context=access_context,
        include_future=include_future,
    )
    return replace(state, isResetToRoleTemplate=True)


def buildDefaultCabinetDashboardPreferences(
    presetCode: str,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
) -> CabinetDashboardPreferenceState:
    return build_default_cabinet_dashboard_preferences(
        presetCode,
        access_context=access_context,
        include_future=include_future,
    )


def applyCabinetDashboardPreferences(
    presetCode: str,
    preferences: CabinetDashboardPreferenceState | dict[str, Any] | None = None,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
) -> dict[str, Any]:
    return apply_cabinet_dashboard_preferences(
        presetCode,
        preferences,
        access_context=access_context,
        include_future=include_future,
    )


def _replace_block_preference(
    state: CabinetDashboardPreferenceState,
    block_code: str,
    **changes: Any,
) -> CabinetDashboardPreferenceState:
    current = {item.blockCode: item for item in state.blockPreferences}
    preference = replace(
        current.get(block_code, CabinetBlockPreferenceDTO(blockCode=block_code)),
        **changes,
    )
    block_preferences = [
        preference if item.blockCode == block_code else item
        for item in state.blockPreferences
    ]
    if block_code not in {item.blockCode for item in state.blockPreferences}:
        block_preferences.append(preference)
    return replace(state, blockPreferences=block_preferences, isResetToRoleTemplate=False)


def _preference_state(
    preferences: CabinetDashboardPreferenceState | dict[str, Any] | None,
    preset_code: str | None = None,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
) -> CabinetDashboardPreferenceState:
    if isinstance(preferences, CabinetDashboardPreferenceState):
        return preferences
    if preferences is None:
        if not preset_code:
            raise ValueError("preset_code is required when preferences are empty")
        return build_default_cabinet_dashboard_preferences(
            preset_code,
            access_context=access_context,
            include_future=include_future,
        )
    data = dict(preferences)
    return CabinetDashboardPreferenceState(
        presetCode=data.get("presetCode") or preset_code or "",
        userId=data.get("userId"),
        workspaceId=data.get("workspaceId"),
        cabinetId=data.get("cabinetId"),
        activeRegionCode=data.get("activeRegionCode"),
        blockPreferences=[
            _block_preference(item)
            for item in _list_value(data.get("blockPreferences"))
        ],
        widgetPreferences=[
            _widget_preference(item)
            for item in _list_value(data.get("widgetPreferences"))
        ],
        moduleShortcuts=[
            _module_shortcut(item)
            for item in _list_value(data.get("moduleShortcuts"))
        ],
        quickActions=[],
        deniedOperations=_list_value(data.get("deniedOperations")),
        isMock=bool(data.get("isMock", True)),
        isResetToRoleTemplate=bool(data.get("isResetToRoleTemplate", False)),
    )


def _block_preference(data: Any) -> CabinetBlockPreferenceDTO:
    value = _dict_value(data)
    return CabinetBlockPreferenceDTO(
        blockCode=str(value.get("blockCode")),
        isVisible=bool(value.get("isVisible", True)),
        sortOrder=int(value.get("sortOrder", 1000)),
        isPinned=bool(value.get("isPinned", False)),
    )


def _widget_preference(data: Any) -> CabinetWidgetPreferenceDTO:
    value = _dict_value(data)
    return CabinetWidgetPreferenceDTO(
        widgetCode=str(value.get("widgetCode")),
        isVisible=bool(value.get("isVisible", True)),
        zoneCode=_string_or_none(value.get("zoneCode")),
        size=_string_or_none(value.get("size")),
        sortOrder=int(value.get("sortOrder", 1000)),
    )


def _module_shortcut(data: Any) -> CabinetModuleShortcutDTO:
    value = _dict_value(data)
    return CabinetModuleShortcutDTO(
        shortcutCode=str(value.get("shortcutCode")),
        title=str(value.get("title")),
        targetModuleCode=str(value.get("targetModuleCode")),
        route=_string_or_none(value.get("route")),
        icon=_string_or_none(value.get("icon")),
        sortOrder=int(value.get("sortOrder", 1000)),
        isVisible=bool(value.get("isVisible", True)),
    )


def _quick_action(data: Any) -> CabinetQuickActionDTO:
    value = _dict_value(data)
    return CabinetQuickActionDTO(
        quickActionCode=str(value.get("quickActionCode")),
        isVisible=bool(value.get("isVisible", True)),
        sortOrder=int(value.get("sortOrder", 1000)),
    )


def _apply_zone_preferences(
    zone: dict[str, Any],
    visible_block_codes: set[str],
    visible_widget_codes: set[str],
) -> dict[str, Any]:
    return {
        **zone,
        "blockCodes": [
            block_code
            for block_code in zone.get("blockCodes", [])
            if block_code in visible_block_codes
        ],
        "widgetCodes": [
            widget_code
            for widget_code in zone.get("widgetCodes", [])
            if widget_code in visible_widget_codes
        ],
    }


def _ordered_blocks(state: CabinetDashboardPreferenceState) -> list[CabinetBlockPreferenceDTO]:
    return sorted(
        state.blockPreferences,
        key=lambda item: (not item.isPinned, item.sortOrder, item.blockCode),
    )


def _ordered_visible_blocks(state: CabinetDashboardPreferenceState) -> list[str]:
    return [item.blockCode for item in _ordered_blocks(state) if item.isVisible]


def _ordered_visible_widgets(state: CabinetDashboardPreferenceState) -> list[str]:
    return [
        item.widgetCode
        for item in sorted(state.widgetPreferences, key=lambda item: (item.sortOrder, item.widgetCode))
        if item.isVisible
    ]


def _ordered_visible_quick_actions(state: CabinetDashboardPreferenceState) -> list[str]:
    return []


def _widget_zone(preset: dict[str, Any], widget_code: str) -> str | None:
    for zone in preset.get("zones", []):
        if widget_code in zone.get("widgetCodes", []):
            return zone.get("zoneCode")
    return None


def _deny(
    state: CabinetDashboardPreferenceState,
    *,
    operation: str,
    code: str,
    reason: str,
    targetModuleCode: str | None = None,
) -> CabinetDashboardPreferenceState:
    denied = [
        *state.deniedOperations,
        {
            "operation": operation,
            "code": code,
            "reason": reason,
            "targetModuleCode": targetModuleCode,
            "sourceModuleCode": MODULE_03_USERS_ROLES,
        },
    ]
    return replace(state, deniedOperations=denied)


def _access_context_dict(
    access_context: AccessContextForCabinet | dict[str, Any] | None,
) -> dict[str, Any]:
    if access_context is None:
        return {}
    if isinstance(access_context, dict):
        return access_context
    return access_context.to_dict()


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


def _list_value(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _list_strings(value: Any) -> list[str]:
    return [str(item) for item in _list_value(value) if item is not None]


def _unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "CabinetBlockPreferenceDTO",
    "CabinetWidgetPreferenceDTO",
    "CabinetModuleShortcutDTO",
    "CabinetQuickActionDTO",
    "CabinetDashboardPreferenceState",
    "build_default_cabinet_dashboard_preferences",
    "apply_cabinet_dashboard_preferences",
    "set_block_visibility",
    "hide_block",
    "show_block",
    "reorder_block",
    "pin_block",
    "add_module_shortcut",
    "remove_widget",
    "set_quick_action_visibility",
    "reset_to_role_template",
    "buildDefaultCabinetDashboardPreferences",
    "applyCabinetDashboardPreferences",
]
