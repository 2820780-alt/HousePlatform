from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from app.services.audit_log_service import record_dashboard_layout_change
from app.services.dashboard_module_registry import get_canonical_module_code
from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_CONTEXT, LEGACY_ADMIN_CABINET_MODULE
from app.services.role_dashboard_access_profiles import get_role_dashboard_access_profile
from app.services.widget_permission import can_add_widget, can_view_widget
from app.services.widget_registry import get_widget_registry_item


LAYOUT_ZONES = {"TOP", "CENTER", "BOTTOM", "RIGHT_OPTIONAL"}
LAYOUT_SIZES = {"small", "medium", "large"}
LAYOUT_PLACEMENTS = {"DASHBOARD", "MODULE_OVERVIEW"}
DEFAULT_ZONE_BY_TYPE = {
    "KPI": "TOP",
    "ATOM_MAP": "CENTER",
}


@dataclass(frozen=True)
class UserDashboardWidgetLayoutItem:
    widgetCode: str
    sourceModuleCode: str
    position: int
    size: str
    isVisible: bool
    featureCode: str | None = None
    zone: str = "BOTTOM"
    instanceId: str | None = None
    placement: str | None = None
    userSettings: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class UserDashboardLayoutData:
    userId: str
    favoriteModules: list[str]
    widgets: list[dict[str, Any]]
    id: str | None = None
    workspaceId: str | None = None
    activeRegionCode: str | None = None
    activeCabinetId: str | None = None
    cabinetType: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        now = datetime.utcnow().isoformat()
        payload["createdAt"] = payload["createdAt"] or now
        payload["updatedAt"] = payload["updatedAt"] or now
        return payload


def normalize_user_dashboard_layout(layout: Any, *, user: Any, context: Any | None = None) -> dict[str, Any]:
    data = _layout_dict(layout)
    merged_context = _merge_context(user, context, data)
    widgets = [
        normalized
        for widget in data.get("widgets", [])
        if (normalized := normalize_dashboard_layout_widget(widget)) is not None
    ]
    favorite_modules = normalize_favorite_modules(data.get("favoriteModules") or data.get("favorite_modules") or [])
    return UserDashboardLayoutData(
        id=_string_or_none(data.get("id")),
        userId=_string_or_none(data.get("userId") or data.get("user_id") or _get_value(user, "userId") or _get_value(user, "id")) or "",
        workspaceId=_string_or_none(data.get("workspaceId") or data.get("workspace_id") or _get_value(user, "workspaceId")),
        activeRegionCode=_string_or_none(data.get("activeRegionCode") or data.get("active_region_code") or merged_context.get("activeRegionCode")),
        activeCabinetId=_string_or_none(data.get("activeCabinetId") or data.get("active_cabinet_id") or merged_context.get("activeCabinetId")),
        cabinetType=_string_or_none(data.get("cabinetType") or data.get("cabinet_type") or merged_context.get("activeCabinetType")),
        favoriteModules=favorite_modules,
        widgets=widgets,
        createdAt=data.get("createdAt") or data.get("created_at"),
        updatedAt=data.get("updatedAt") or data.get("updated_at"),
    ).to_dict()


def validate_user_dashboard_layout(layout: Any, *, user: Any, context: Any | None = None) -> dict[str, Any]:
    normalized = normalize_user_dashboard_layout(layout, user=user, context=context)
    effective_context = _merge_context(user, context, {
        "userDashboardLayout": normalized,
        "activeRegionCode": normalized.get("activeRegionCode"),
        "activeCabinetId": normalized.get("activeCabinetId"),
        "activeCabinetType": normalized.get("cabinetType"),
    })
    allowed_widgets: list[dict[str, Any]] = []
    for widget in normalized["widgets"]:
        if not can_view_widget(user, widget["widgetCode"], effective_context):
            continue
        allowed_widgets.append(widget)
    normalized["widgets"] = allowed_widgets
    normalized["favoriteModules"] = [
        module_code
        for module_code in normalized["favoriteModules"]
        if module_code != DASHBOARD_ADMIN_CONTEXT
    ]
    return normalized


def add_widget_to_layout(
    layout: Any,
    widget_code: str,
    *,
    user: Any,
    context: Any | None = None,
    instance_id: str | None = None,
    placement: str | None = None,
    user_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_user_dashboard_layout(layout, user=user, context=context)
    effective_context = _merge_context(user, context, {
        "userDashboardLayout": normalized,
        "activeRegionCode": normalized.get("activeRegionCode"),
    })
    if not can_add_widget(user, widget_code, effective_context):
        record_dashboard_layout_change(
            user=user,
            old_layout=normalized,
            new_layout=normalized,
            reason=f"Denied attempt to add unavailable widget {widget_code}.",
        )
        return normalized
    widget = get_widget_registry_item(widget_code)
    if not widget:
        return normalized
    if not widget.allowsMultipleInstances and any(
        item["widgetCode"] == widget_code for item in normalized["widgets"]
    ):
        return normalized
    item = _layout_item_from_widget(
        widget,
        position=len(normalized["widgets"]) + 1,
        instance_id=instance_id or (str(uuid4()) if widget.allowsMultipleInstances else None),
        placement=_normalize_placement(placement) if placement else None,
        user_settings=dict(user_settings or {}) if user_settings is not None else None,
    )
    normalized["widgets"].append(item.to_dict())
    record_dashboard_layout_change(
        user=user,
        old_layout=layout,
        new_layout=normalized,
        reason=f"Widget {widget_code} added to UserDashboardLayout.",
    )
    return normalized


def hide_widget_in_layout(layout: Any, widget_code: str, *, user: Any | None = None) -> dict[str, Any]:
    normalized = normalize_user_dashboard_layout(layout, user=user or {}, context=layout)
    for widget in normalized["widgets"]:
        if widget["widgetCode"] == widget_code:
            widget["isVisible"] = False
    return normalized


def update_widget_instance_in_layout(
    layout: Any,
    instance_id: str,
    *,
    user: Any,
    placement: str | None = None,
    user_settings: dict[str, Any] | None = None,
    position: int | None = None,
    is_visible: bool | None = None,
) -> dict[str, Any]:
    normalized = normalize_user_dashboard_layout(layout, user=user, context=layout)
    old_layout = deepcopy(normalized)
    updated_widgets: list[dict[str, Any]] = []
    for item in normalized["widgets"]:
        updated = dict(item)
        if item.get("instanceId") == instance_id:
            if placement is not None:
                updated["placement"] = _normalize_placement(placement)
            if user_settings is not None:
                updated["userSettings"] = dict(user_settings)
            if position is not None:
                updated["position"] = max(1, int(position))
            if is_visible is not None:
                updated["isVisible"] = bool(is_visible)
        updated_widgets.append(updated)
    normalized["widgets"] = sorted(updated_widgets, key=lambda item: item["position"])
    record_dashboard_layout_change(
        user=user,
        old_layout=old_layout,
        new_layout=normalized,
        reason=f"Widget instance {instance_id} updated in UserDashboardLayout.",
    )
    return normalized


def remove_widget_instance_from_layout(layout: Any, instance_id: str, *, user: Any) -> dict[str, Any]:
    normalized = normalize_user_dashboard_layout(layout, user=user, context=layout)
    old_layout = deepcopy(normalized)
    normalized["widgets"] = [
        item for item in normalized["widgets"] if item.get("instanceId") != instance_id
    ]
    for index, item in enumerate(normalized["widgets"], start=1):
        item["position"] = index
    record_dashboard_layout_change(
        user=user,
        old_layout=old_layout,
        new_layout=normalized,
        reason=f"Widget instance {instance_id} removed from UserDashboardLayout.",
    )
    return normalized


def reorder_widget_instances_in_layout(
    layout: Any,
    ordered_instance_ids: list[str],
    *,
    user: Any,
) -> dict[str, Any]:
    normalized = normalize_user_dashboard_layout(layout, user=user, context=layout)
    old_layout = deepcopy(normalized)
    requested = list(dict.fromkeys(ordered_instance_ids))
    by_id = {
        item.get("instanceId"): item
        for item in normalized["widgets"]
        if item.get("instanceId") in requested
    }
    ordered = [by_id[instance_id] for instance_id in requested if instance_id in by_id]
    target_indexes = [
        index
        for index, item in enumerate(normalized["widgets"])
        if item.get("instanceId") in by_id
    ]
    widgets = [dict(item) for item in normalized["widgets"]]
    for index, item in zip(target_indexes, ordered):
        widgets[index] = dict(item)
    for position, item in enumerate(widgets, start=1):
        item["position"] = position
    normalized["widgets"] = widgets
    record_dashboard_layout_change(
        user=user,
        old_layout=old_layout,
        new_layout=normalized,
        reason="Widget instances reordered in UserDashboardLayout.",
    )
    return normalized

def reset_layout_to_role_profile(*, user: Any, role_code: str | None = None, context: Any | None = None) -> dict[str, Any]:
    data = _merge_context(user, context)
    effective_role = role_code or data.get("effectiveRoleCode") or data.get("roleCode") or data.get("role")
    profile = get_role_dashboard_access_profile(effective_role) or {}
    settings = profile.get("settings") or {}
    active_region_code = data.get("activeRegionCode")
    widget_items: list[dict[str, Any]] = []
    for index, widget_code in enumerate(profile.get("defaultWidgetCodes") or []):
        item = _layout_item_from_widget_code(widget_code, position=index + 1)
        if item:
            widget_items.append(item.to_dict())
    layout = UserDashboardLayoutData(
        userId=_string_or_none(data.get("userId") or data.get("id")) or "",
        workspaceId=_string_or_none(data.get("workspaceId")),
        activeRegionCode=_string_or_none(active_region_code),
        activeCabinetId=_string_or_none(data.get("activeCabinetId")),
        cabinetType=_string_or_none(settings.get("activeCabinetType") or data.get("activeCabinetType")),
        favoriteModules=normalize_favorite_modules(settings.get("favoriteModuleCodes") or []),
        widgets=widget_items,
    ).to_dict()
    return validate_user_dashboard_layout(layout, user=user, context={**data, "roleDashboardAccessProfile": profile})


def normalize_favorite_modules(module_codes: list[Any]) -> list[str]:
    normalized: list[str] = []
    for module_code in module_codes:
        if module_code == LEGACY_ADMIN_CABINET_MODULE:
            canonical = DASHBOARD_ADMIN_CONTEXT
        else:
            canonical = get_canonical_module_code(str(module_code)) if module_code is not None else None
        if not canonical or canonical in normalized:
            continue
        normalized.append(canonical)
    return normalized


def normalize_dashboard_layout_widget(widget: Any) -> dict[str, Any] | None:
    data = _layout_dict(widget)
    widget_code = data.get("widgetCode") or data.get("widget_code")
    registry_item = get_widget_registry_item(widget_code)
    if not widget_code or not registry_item:
        return None
    item = UserDashboardWidgetLayoutItem(
        widgetCode=registry_item.widgetCode,
        sourceModuleCode=registry_item.sourceModuleCode,
        featureCode=registry_item.featureCode,
        position=_int_value(data.get("position") or data.get("order"), 100),
        zone=_normalize_zone(data.get("zone")),
        size=_normalize_size(data.get("size") or registry_item.defaultSize),
        isVisible=bool(data.get("isVisible", data.get("is_visible", True))),
        instanceId=_string_or_none(data.get("instanceId") or data.get("instance_id")),
        placement=_normalize_placement(data.get("placement")) if data.get("placement") else None,
        userSettings=(
            dict(data.get("userSettings") or data.get("user_settings") or {})
            if isinstance(data.get("userSettings") or data.get("user_settings") or {}, dict)
            else {}
        )
        if "userSettings" in data or "user_settings" in data
        else None,
    )
    return item.to_dict()


def _layout_item_from_widget_code(widget_code: str, *, position: int) -> UserDashboardWidgetLayoutItem | None:
    widget = get_widget_registry_item(widget_code)
    if not widget:
        return None
    return _layout_item_from_widget(widget, position=position)


def _layout_item_from_widget(
    widget: Any,
    *,
    position: int,
    instance_id: str | None = None,
    placement: str | None = None,
    user_settings: dict[str, Any] | None = None,
) -> UserDashboardWidgetLayoutItem:
    widget_type = _get_value(widget, "widgetType") or "STATUS"
    return UserDashboardWidgetLayoutItem(
        widgetCode=_get_value(widget, "widgetCode"),
        sourceModuleCode=_get_value(widget, "sourceModuleCode"),
        featureCode=_get_value(widget, "featureCode"),
        position=position,
        zone=DEFAULT_ZONE_BY_TYPE.get(widget_type, "BOTTOM"),
        size=_normalize_size(_get_value(widget, "defaultSize")),
        isVisible=True,
        instanceId=instance_id,
        placement=placement,
        userSettings=user_settings,
    )


def _normalize_placement(value: Any) -> str:
    placement = str(value or "DASHBOARD").upper()
    return placement if placement in LAYOUT_PLACEMENTS else "DASHBOARD"


def _normalize_zone(value: Any) -> str:
    zone = str(value or "BOTTOM").upper()
    return zone if zone in LAYOUT_ZONES else "BOTTOM"


def _normalize_size(value: Any) -> str:
    size = str(value or "medium").lower()
    return size if size in LAYOUT_SIZES else "medium"


def _merge_context(*values: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        merged.update(_layout_dict(value))
    return merged


def _layout_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_template_dict"):
        return value.to_template_dict()
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _get_value(source: Any, field_name: str) -> Any:
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
