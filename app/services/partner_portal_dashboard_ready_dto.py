from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_adapter import get_cabinet_dashboard_context
from app.services.partner_portal_dashboard_presets import (
    ATOM_MAP,
    BOTTOM_WIDGET_GRID,
    RIGHT_OPTIONAL,
    TOP_WIDGET_GRID,
)


CABINET_DASHBOARD_CONTEXT = "CABINET_DASHBOARD_CONTEXT"
MODULE_03_USERS_ROLES = "MODULE_03_USERS_ROLES"


@dataclass(frozen=True)
class DashboardReadyCabinetContextDTO:
    activeCabinetId: str | None
    activeCabinetType: str | None
    activeBusinessRole: str | None
    activeRegionCode: str | None
    activeObjectId: str | None
    mainFocus: str | None
    primaryBlocks: list[str] = field(default_factory=list)
    secondaryBlocks: list[str] = field(default_factory=list)
    quickActions: list[dict[str, Any]] = field(default_factory=list)
    availableModuleShortcuts: list[dict[str, Any]] = field(default_factory=list)
    widgetPreferences: list[dict[str, Any]] = field(default_factory=list)
    hiddenBlocks: list[str] = field(default_factory=list)
    lockedBlocks: list[str] = field(default_factory=list)
    futureBlocks: list[str] = field(default_factory=list)
    premiumBlocks: list[str] = field(default_factory=list)
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    featureCode: str = CABINET_DASHBOARD_CONTEXT
    permissionFilterSourceModuleCode: str = MODULE_03_USERS_ROLES
    isMock: bool = True
    compatibilityNote: str = (
        "Module 08 prepares cabinet Dashboard context only. Dashboard renders this DTO; "
        "Module 03 remains the permission filter and owning modules provide payload data."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_dashboard_ready_cabinet_context(
    context: Any,
    *,
    cabinet_id: str | None = None,
) -> DashboardReadyCabinetContextDTO:
    dashboard_context = get_cabinet_dashboard_context(cabinet_id, context)
    active_context = _dict_value(dashboard_context.get("activeCabinetContext"))
    preset = _dict_value(dashboard_context.get("dashboardPreset"))
    preferences = _dict_value(dashboard_context.get("widgetPreferences"))
    block_catalog = _list_dicts(dashboard_context.get("blockCatalog"))

    hidden_blocks = _hidden_blocks(preferences)
    locked_blocks = _locked_blocks(preset)
    future_blocks = _future_blocks(preset, block_catalog)
    premium_blocks = _premium_blocks(block_catalog)
    excluded_blocks = set(hidden_blocks + locked_blocks + future_blocks + premium_blocks)

    primary_blocks = _zone_blocks(
        preset,
        {TOP_WIDGET_GRID, ATOM_MAP},
        excluded_blocks=excluded_blocks,
    )
    if not primary_blocks:
        primary_blocks = _filtered_codes(
            preset.get("recommendedBlockCodes"),
            excluded_blocks=excluded_blocks,
        )[:3]

    secondary_blocks = _zone_blocks(
        preset,
        {BOTTOM_WIDGET_GRID, RIGHT_OPTIONAL},
        excluded_blocks=excluded_blocks,
    )
    if not secondary_blocks:
        secondary_blocks = [
            code
            for code in _filtered_codes(preset.get("recommendedBlockCodes"), excluded_blocks=excluded_blocks)
            if code not in set(primary_blocks)
        ]

    return DashboardReadyCabinetContextDTO(
        activeCabinetId=_string_or_none(active_context.get("activeCabinetId")),
        activeCabinetType=_string_or_none(active_context.get("activeCabinetType")),
        activeBusinessRole=_string_or_none(active_context.get("activeBusinessRole")),
        activeRegionCode=_string_or_none(active_context.get("activeRegionCode")),
        activeObjectId=_string_or_none(active_context.get("activeObjectId")),
        mainFocus=_string_or_none(preset.get("mainFocus") or active_context.get("mainFocus")),
        primaryBlocks=primary_blocks,
        secondaryBlocks=secondary_blocks,
        quickActions=_visible_quick_actions(dashboard_context, preferences),
        availableModuleShortcuts=_visible_dicts(preferences.get("moduleShortcuts")),
        widgetPreferences=_visible_dicts(preferences.get("widgetPreferences")),
        hiddenBlocks=hidden_blocks,
        lockedBlocks=locked_blocks,
        futureBlocks=future_blocks,
        premiumBlocks=premium_blocks,
    )


def buildDashboardReadyCabinetContext(
    context: Any,
    *,
    cabinetId: str | None = None,
) -> DashboardReadyCabinetContextDTO:
    return build_dashboard_ready_cabinet_context(context, cabinet_id=cabinetId)


def _visible_quick_actions(
    dashboard_context: dict[str, Any],
    preferences: dict[str, Any],
) -> list[dict[str, Any]]:
    hidden_codes = {
        str(item.get("quickActionCode"))
        for item in _list_dicts(preferences.get("quickActions"))
        if item.get("isVisible") is False and item.get("quickActionCode") is not None
    }
    return [
        item
        for item in _list_dicts(dashboard_context.get("quickActions"))
        if item.get("quickActionCode") not in hidden_codes
    ]


def _hidden_blocks(preferences: dict[str, Any]) -> list[str]:
    return _unique_strings(
        [
            str(item.get("blockCode"))
            for item in _list_dicts(preferences.get("blockPreferences"))
            if item.get("isVisible") is False and item.get("blockCode") is not None
        ]
    )


def _locked_blocks(preset: dict[str, Any]) -> list[str]:
    denied = _dict_value(preset.get("deniedByAccess"))
    return _unique_strings([str(item) for item in _list_value(denied.get("blockCodes"))])


def _future_blocks(preset: dict[str, Any], block_catalog: list[dict[str, Any]]) -> list[str]:
    return _unique_strings(
        [
            *[str(item) for item in _list_value(preset.get("futureBlockCodes"))],
            *[
                str(item.get("blockCode"))
                for item in block_catalog
                if item.get("isFuture") and item.get("blockCode") is not None
            ],
        ]
    )


def _premium_blocks(block_catalog: list[dict[str, Any]]) -> list[str]:
    return _unique_strings(
        [
            str(item.get("blockCode"))
            for item in block_catalog
            if item.get("isPremiumFeature") and item.get("blockCode") is not None
        ]
    )


def _zone_blocks(
    preset: dict[str, Any],
    zone_codes: set[str],
    *,
    excluded_blocks: set[str],
) -> list[str]:
    codes: list[str] = []
    for zone in _list_dicts(preset.get("zones")):
        if zone.get("zoneCode") not in zone_codes:
            continue
        for block_code in _list_value(zone.get("blockCodes")):
            value = str(block_code)
            if value and value not in excluded_blocks and value not in codes:
                codes.append(value)
    return codes


def _filtered_codes(value: Any, *, excluded_blocks: set[str]) -> list[str]:
    return [
        item
        for item in _unique_strings([str(code) for code in _list_value(value)])
        if item not in excluded_blocks
    ]


def _visible_dicts(value: Any) -> list[dict[str, Any]]:
    return [
        item
        for item in _list_dicts(value)
        if item.get("isVisible", True) is not False
    ]


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


def _list_dicts(value: Any) -> list[dict[str, Any]]:
    return [_dict_value(item) for item in _list_value(value)]


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "CABINET_DASHBOARD_CONTEXT",
    "DashboardReadyCabinetContextDTO",
    "build_dashboard_ready_cabinet_context",
    "buildDashboardReadyCabinetContext",
]
