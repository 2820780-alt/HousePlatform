from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence

from app.core.access_levels import AccessLevel
from app.core.access_scopes import AccessScope
from app.core.exceptions import ForbiddenError
from app.core.permission_guard import can, canonical_module_code, require_permission
from app.services.audit_log_service import record_inaccessible_widget_add_attempt
from app.services.dashboard_module_registry import get_canonical_module_code, get_dashboard_module_registry_item
from app.services.role_dashboard_access_profiles import get_role_dashboard_access_profile
from app.services.widget_registry import WidgetRegistryItemDefinition, get_widget_registry_item


ACTIVE_MODULE_STATUSES = {"active", "ACTIVE"}
ACTIVE_WIDGET_STATUSES = {"ACTIVE"}
ADD_WIDGET_ACTION_CODE = "DASHBOARD_CONFIGURE"


@dataclass(frozen=True)
class WidgetPermissionContext:
    activeRegionCode: str | None = None
    workspaceId: str | None = None
    ownerId: str | None = None
    actionCode: str | None = None
    accessLevel: str | None = None
    accessScope: str | None = None
    roleCode: str | None = None
    userDashboardLayout: dict[str, Any] = field(default_factory=dict)
    roleDashboardAccessProfile: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Any | None) -> "WidgetPermissionContext":
        data = _context_dict(value)
        return cls(
            activeRegionCode=_first_value(data, "activeRegionCode", "region_id", "regionCode"),
            workspaceId=_first_value(data, "workspaceId", "workspace_id"),
            ownerId=_first_value(data, "ownerId", "owner_id", "userId", "user_id"),
            actionCode=_first_value(data, "actionCode", "action_code"),
            accessLevel=_first_value(data, "accessLevel", "access_level"),
            accessScope=_first_value(data, "accessScope", "access_scope"),
            roleCode=_first_value(data, "effectiveRoleCode", "roleCode", "role_code", "role"),
            userDashboardLayout=data.get("userDashboardLayout") or data.get("dashboardLayout") or data.get("layout") or {},
            roleDashboardAccessProfile=data.get("roleDashboardAccessProfile") or data.get("dashboardAccessProfile") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "activeRegionCode": self.activeRegionCode,
            "workspaceId": self.workspaceId,
            "ownerId": self.ownerId,
            "actionCode": self.actionCode,
            "accessLevel": self.accessLevel,
            "accessScope": self.accessScope,
            "roleCode": self.roleCode,
            "userDashboardLayout": self.userDashboardLayout,
            "roleDashboardAccessProfile": self.roleDashboardAccessProfile,
        }


def can_view_widget(user: Any, widget_code: str, context: Any | None = None) -> bool:
    return _widget_permission_result(user, widget_code, context, mode="view").allowed


def can_add_widget(user: Any, widget_code: str, context: Any | None = None) -> bool:
    return _widget_permission_result(user, widget_code, context, mode="add").allowed


def require_widget_permission(widget_code: str, context: Any | None = None, *, user: Any | None = None) -> WidgetRegistryItemDefinition:
    effective_user = user or _context_dict(context).get("user") or context
    result = _widget_permission_result(effective_user, widget_code, context, mode="view")
    if not result.allowed:
        raise ForbiddenError(result.reason)
    return result.widget


def filter_allowed_widgets(user: Any, widgets: Sequence[Any], context: Any | None = None) -> list[Any]:
    allowed: list[Any] = []
    for widget in widgets:
        widget_code = _widget_code(widget)
        if widget_code and can_view_widget(user, widget_code, context):
            allowed.append(widget)
    return allowed


def canViewWidget(user: Any, widgetCode: str, context: Any | None = None) -> bool:
    return can_view_widget(user, widgetCode, context)


def canAddWidget(user: Any, widgetCode: str, context: Any | None = None) -> bool:
    return can_add_widget(user, widgetCode, context)


def requireWidgetPermission(widgetCode: str, context: Any | None = None) -> WidgetRegistryItemDefinition:
    return require_widget_permission(widgetCode, context)


def filterAllowedWidgets(user: Any, widgets: Sequence[Any], context: Any | None = None) -> list[Any]:
    return filter_allowed_widgets(user, widgets, context)


@dataclass(frozen=True)
class _WidgetPermissionResult:
    allowed: bool
    reason: str
    widget: WidgetRegistryItemDefinition


def _widget_permission_result(
    user: Any,
    widget_code: str,
    context: Any | None,
    *,
    mode: str,
) -> _WidgetPermissionResult:
    permission_context = WidgetPermissionContext.from_value(_merge_context(user, context))
    widget = get_widget_registry_item(widget_code)
    if widget is None:
        return _denied(widget_code, "WidgetRegistry item not found.", permission_context)

    module_code = _canonical_widget_module_code(widget)
    module_item = get_dashboard_module_registry_item(module_code)
    if widget.status not in ACTIVE_WIDGET_STATUSES:
        return _denied(widget.widgetCode, f"Widget status is {widget.status}.", permission_context, widget)
    if module_item and module_item.status not in ACTIVE_MODULE_STATUSES:
        return _denied(widget.widgetCode, f"Module status is {module_item.status}.", permission_context, widget)
    if module_item and not module_item.isAvailableForDashboard:
        return _denied(widget.widgetCode, "Module is not available for Dashboard.", permission_context, widget)
    if not permission_context.activeRegionCode:
        return _denied(widget.widgetCode, "Active region is required for widget access.", permission_context, widget)
    if not _context_allows_widget_code(widget, user, permission_context):
        return _denied(widget.widgetCode, "widgetCode is not allowed for current user context.", permission_context, widget)
    if not _role_profile_allows_widget(widget, permission_context):
        return _denied(widget.widgetCode, "RoleDashboardAccessProfile does not allow this widget.", permission_context, widget)
    if not _layout_allows_widget(widget, permission_context, mode=mode):
        return _denied(widget.widgetCode, "UserDashboardLayout hides or does not allow this widget.", permission_context, widget)
    if widget.featureCode and not _feature_allowed(widget.featureCode, user, permission_context):
        return _denied(widget.widgetCode, "Feature is not allowed for current context.", permission_context, widget)

    action_code = _required_action_code(widget, permission_context, mode=mode)
    required_scope = _required_scope(widget, permission_context)
    if not can(user, module_code, action_code, required_scope):
        return _denied(widget.widgetCode, "PermissionGuard denied widget data access.", permission_context, widget)

    # Keep the server-side guarantee explicit: callers that require widget data must pass through require_permission().
    require_permission(user, module_code, action_code, required_scope)
    return _WidgetPermissionResult(True, "allowed", widget)


def _denied(
    widget_code: str,
    reason: str,
    context: WidgetPermissionContext,
    widget: WidgetRegistryItemDefinition | None = None,
) -> _WidgetPermissionResult:
    record_inaccessible_widget_add_attempt(
        widget_code=widget_code,
        module_code=widget.sourceModuleCode if widget else None,
        canonical_module_code=widget.canonicalModuleCode if widget else None,
        feature_code=widget.featureCode if widget else None,
        reason=reason,
    )
    fallback = widget or WidgetRegistryItemDefinition(
        id=widget_code,
        widgetCode=widget_code,
        title=widget_code,
        sourceModuleCode="UNKNOWN",
        widgetType="STATUS",
        defaultSize="medium",
        status="DISABLED",
        isSystem=False,
        order=9999,
    )
    return _WidgetPermissionResult(False, reason, fallback)


def _canonical_widget_module_code(widget: WidgetRegistryItemDefinition) -> str:
    return canonical_module_code(
        get_canonical_module_code(widget.canonicalModuleCode or widget.sourceModuleCode) or widget.sourceModuleCode
    )


def _role_profile_allows_widget(widget: WidgetRegistryItemDefinition, context: WidgetPermissionContext) -> bool:
    profile = context.roleDashboardAccessProfile or get_role_dashboard_access_profile(context.roleCode)
    if not profile:
        return False
    allowed_modules = {
        canonical_module_code(get_canonical_module_code(code) or code)
        for code in profile.get("allowedModuleCodes", [])
    }
    allowed_features = set(profile.get("allowedFeatureCodes") or [])
    default_widgets = set(profile.get("defaultWidgetCodes") or [])
    hidden_widgets = set(profile.get("hiddenWidgetCodes") or [])
    if widget.widgetCode in hidden_widgets:
        return False
    if widget.widgetCode not in default_widgets:
        return False
    if _canonical_widget_module_code(widget) not in allowed_modules:
        return False
    if widget.featureCode and allowed_features and widget.featureCode not in allowed_features:
        return False
    return True


def _context_allows_widget_code(widget: WidgetRegistryItemDefinition, user: Any, context: WidgetPermissionContext) -> bool:
    allowed_codes: list[str] = []
    allowed_codes.extend(_list_value(_get_value(user, "allowedWidgetCodes") or _get_value(user, "allowed_widget_codes")))
    allowed_codes.extend(_list_value(_context_dict(user).get("allowedWidgetCodes")))
    allowed_codes.extend(_list_value(context.userDashboardLayout.get("allowedWidgetCodes")))
    if not allowed_codes:
        return True
    return widget.widgetCode in set(allowed_codes)


def _layout_allows_widget(widget: WidgetRegistryItemDefinition, context: WidgetPermissionContext, *, mode: str) -> bool:
    layout = context.userDashboardLayout or {}
    hidden_codes = set(_list_value(layout.get("hiddenWidgetCodes") or layout.get("hiddenWidgets")))
    if widget.widgetCode in hidden_codes:
        return False

    layout_widgets = _layout_widgets(layout)
    if not layout_widgets:
        return True

    matching = [item for item in layout_widgets if _widget_code(item) == widget.widgetCode]
    if matching:
        return any(_is_visible_layout_item(item) for item in matching)
    return mode == "add"


def _feature_allowed(feature_code: str, user: Any, context: WidgetPermissionContext) -> bool:
    values: list[Any] = []
    values.extend(_list_value(_get_value(user, "allowedFeatureCodes") or _get_value(user, "allowed_feature_codes")))
    values.extend(_list_value(_context_dict(user).get("allowedFeatureCodes")))
    values.extend(_list_value(context.roleDashboardAccessProfile.get("allowedFeatureCodes") if context.roleDashboardAccessProfile else []))
    if not values:
        return True
    return feature_code in {str(value) for value in values}


def _required_action_code(widget: WidgetRegistryItemDefinition, context: WidgetPermissionContext, *, mode: str) -> str:
    if mode == "add":
        return context.actionCode or widget.requiredActionCode or ADD_WIDGET_ACTION_CODE
    return context.actionCode or widget.requiredActionCode or widget.requiredAccessLevel or AccessLevel.VIEW


def _required_scope(widget: WidgetRegistryItemDefinition, context: WidgetPermissionContext) -> str:
    return context.accessScope or widget.requiredScope or AccessScope.LIMITED


def _merge_context(user: Any, context: Any | None) -> dict[str, Any]:
    merged = _context_dict(user)
    merged.update(_context_dict(context))
    return merged


def _layout_widgets(layout: dict[str, Any]) -> list[Any]:
    widgets = layout.get("widgets")
    if isinstance(widgets, list):
        return widgets
    zones = layout.get("zones")
    if isinstance(zones, dict):
        result: list[Any] = []
        for zone in zones.values():
            if isinstance(zone, dict) and isinstance(zone.get("widgets"), list):
                result.extend(zone["widgets"])
        return result
    return []


def _widget_code(widget: Any) -> str | None:
    if isinstance(widget, str):
        return widget
    return _get_value(widget, "widgetCode") or _get_value(widget, "widget_code")


def _is_visible_layout_item(item: Any) -> bool:
    if isinstance(item, str):
        return True
    if _get_value(item, "isVisible") is False:
        return False
    if _get_value(item, "enabled") is False:
        return False
    return True


def _context_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_template_dict"):
        return value.to_template_dict()
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _first_value(data: dict[str, Any], *field_names: str) -> Any:
    for field_name in field_names:
        value = data.get(field_name)
        if value is not None:
            return _enum_value(value)
    return None


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return []


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)
