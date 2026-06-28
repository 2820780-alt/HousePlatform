from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

from app.core.access_scopes import AccessScope
from app.core.exceptions import ForbiddenError
from app.core.permission_guard import can, canonical_module_code, require_permission
from app.core.system_roles import LEGACY_ADMIN_ROLE_CODES
from app.services.audit_log_service import record_access_denied_attempt
from app.services.dashboard_module_registry import get_canonical_module_code, get_dashboard_module_registry_item
from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_CONTEXT, DASHBOARD_ADMIN_SOURCE_MODULE
from app.services.quick_action_registry import QuickActionRegistryItemDefinition, get_quick_action_registry_item
from app.services.role_dashboard_access_profiles import get_role_dashboard_access_profile
from app.services.widget_permission import can_view_widget


ACTIVE_MODULE_STATUSES = {"active", "ACTIVE"}
ACTIVE_QUICK_ACTION_STATUSES = {"ACTIVE"}
DASHBOARD_CONTEXT_ACTION_CODES = {"DASHBOARD_CONFIGURE"}


@dataclass(frozen=True)
class QuickActionPermissionContext:
    activeRegionCode: str | None = None
    workspaceId: str | None = None
    widgetCode: str | None = None
    actionCode: str | None = None
    accessLevel: str | None = None
    accessScope: str | None = None
    roleCode: str | None = None
    cabinetType: str | None = None
    roleDashboardAccessProfile: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Any | None) -> "QuickActionPermissionContext":
        data = _context_dict(value)
        return cls(
            activeRegionCode=_first_value(data, "activeRegionCode", "region_id", "regionCode"),
            workspaceId=_first_value(data, "workspaceId", "workspace_id"),
            widgetCode=_first_value(data, "widgetCode", "widget_code"),
            actionCode=_first_value(data, "actionCode", "action_code"),
            accessLevel=_first_value(data, "accessLevel", "access_level"),
            accessScope=_first_value(data, "accessScope", "access_scope"),
            roleCode=_first_value(data, "effectiveRoleCode", "roleCode", "role_code", "role"),
            cabinetType=_first_value(data, "activeCabinetType", "cabinetType", "cabinet_type"),
            roleDashboardAccessProfile=data.get("roleDashboardAccessProfile") or data.get("dashboardAccessProfile") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "activeRegionCode": self.activeRegionCode,
            "workspaceId": self.workspaceId,
            "widgetCode": self.widgetCode,
            "actionCode": self.actionCode,
            "accessLevel": self.accessLevel,
            "accessScope": self.accessScope,
            "roleCode": self.roleCode,
            "cabinetType": self.cabinetType,
            "roleDashboardAccessProfile": self.roleDashboardAccessProfile,
        }


def can_use_quick_action(user: Any, quick_action_code: str, context: Any | None = None) -> bool:
    return _quick_action_permission_result(user, quick_action_code, context).allowed


def require_quick_action_permission(
    quick_action_code: str,
    context: Any | None = None,
    *,
    user: Any | None = None,
) -> QuickActionRegistryItemDefinition:
    effective_user = user or _context_dict(context).get("user") or context
    result = _quick_action_permission_result(effective_user, quick_action_code, context)
    if not result.allowed:
        raise ForbiddenError(result.reason)
    action = result.action
    if not _is_dashboard_context_action(action):
        require_permission(
            effective_user,
            _canonical_action_module_code(action),
            _required_action_code(action, result.context),
            _required_scope(action, result.context),
        )
    return action


def filter_allowed_quick_actions(user: Any, actions: Sequence[Any], context: Any | None = None) -> list[Any]:
    allowed: list[Any] = []
    for action in actions:
        action_code = _quick_action_code(action)
        if action_code and can_use_quick_action(user, action_code, context):
            allowed.append(action)
    return allowed


def canUseQuickAction(user: Any, quickActionCode: str, context: Any | None = None) -> bool:
    return can_use_quick_action(user, quickActionCode, context)


def requireQuickActionPermission(quickActionCode: str, context: Any | None = None) -> QuickActionRegistryItemDefinition:
    return require_quick_action_permission(quickActionCode, context)


def filterAllowedQuickActions(user: Any, actions: Sequence[Any], context: Any | None = None) -> list[Any]:
    return filter_allowed_quick_actions(user, actions, context)


@dataclass(frozen=True)
class _QuickActionPermissionResult:
    allowed: bool
    reason: str
    action: QuickActionRegistryItemDefinition
    context: QuickActionPermissionContext


def _quick_action_permission_result(
    user: Any,
    quick_action_code: str,
    context: Any | None,
) -> _QuickActionPermissionResult:
    permission_context = QuickActionPermissionContext.from_value(_merge_context(user, context))
    action = get_quick_action_registry_item(quick_action_code)
    if action is None:
        return _denied(quick_action_code, "QuickActionRegistry item not found.", permission_context)

    module_code = _canonical_action_module_code(action)
    module_item = get_dashboard_module_registry_item(module_code)
    if action.status not in ACTIVE_QUICK_ACTION_STATUSES:
        return _denied(action.quickActionCode, f"Quick action status is {action.status}.", permission_context, action)
    if module_item and module_item.status not in ACTIVE_MODULE_STATUSES:
        return _denied(action.quickActionCode, f"Module status is {module_item.status}.", permission_context, action)
    if module_item and not module_item.isAvailableForDashboard:
        return _denied(action.quickActionCode, "Module is not available for Dashboard quick actions.", permission_context, action)
    if not permission_context.activeRegionCode:
        return _denied(action.quickActionCode, "Active region is required for quick action access.", permission_context, action)
    if not _context_allows_action_code(action, user):
        return _denied(action.quickActionCode, "allowedActionCodes does not allow this quick action.", permission_context, action)
    if not _role_and_cabinet_allow_action(action, user, permission_context):
        return _denied(action.quickActionCode, "Role or cabinet type does not allow this quick action.", permission_context, action)
    if not _role_profile_allows_action(action, permission_context):
        return _denied(action.quickActionCode, "RoleDashboardAccessProfile does not allow this quick action.", permission_context, action)
    if not _widget_allows_action(user, action, permission_context):
        return _denied(action.quickActionCode, "Widget permission does not allow this quick action.", permission_context, action)
    if _is_dashboard_context_action(action):
        if not _dashboard_context_action_allowed(action, user, permission_context):
            return _denied(action.quickActionCode, "Dashboard personalization feature is not allowed.", permission_context, action)
        return _QuickActionPermissionResult(True, "allowed", action, permission_context)

    if not can(user, module_code, _required_action_code(action, permission_context), _required_scope(action, permission_context)):
        return _denied(action.quickActionCode, "PermissionGuard denied quick action.", permission_context, action)
    return _QuickActionPermissionResult(True, "allowed", action, permission_context)


def _denied(
    action_code: str,
    reason: str,
    context: QuickActionPermissionContext,
    action: QuickActionRegistryItemDefinition | None = None,
) -> _QuickActionPermissionResult:
    record_access_denied_attempt(
        user=None,
        module_code=_canonical_action_module_code(action) if action else "UNKNOWN",
        action_code=action_code,
        scope=context.accessScope or (action.requiredScope if action else AccessScope.NONE),
        reason=reason,
    )
    fallback = action or QuickActionRegistryItemDefinition(
        id=action_code,
        quickActionCode=action_code,
        title=action_code,
        sourceModuleCode="UNKNOWN",
        requiredActionCode="VIEW",
        requiredAccessLevel="NO_ACCESS",
        requiredScope=AccessScope.NONE,
        status="DISABLED",
        isSystem=False,
        order=9999,
    )
    return _QuickActionPermissionResult(False, reason, fallback, context)


def _canonical_action_module_code(action: QuickActionRegistryItemDefinition) -> str:
    return canonical_module_code(
        get_canonical_module_code(action.canonicalModuleCode or action.sourceModuleCode)
        or action.sourceModuleCode
    )


def _required_action_code(action: QuickActionRegistryItemDefinition, context: QuickActionPermissionContext) -> str:
    return context.actionCode or action.requiredActionCode or action.requiredAccessLevel


def _required_scope(action: QuickActionRegistryItemDefinition, context: QuickActionPermissionContext) -> str:
    return context.accessScope or action.requiredScope or AccessScope.LIMITED


def _is_dashboard_context_action(action: QuickActionRegistryItemDefinition) -> bool:
    return (
        action.quickActionCode in DASHBOARD_CONTEXT_ACTION_CODES
        or action.settings.get("contextCode") == DASHBOARD_ADMIN_CONTEXT
        or action.sourceModuleCode == DASHBOARD_ADMIN_SOURCE_MODULE
        and action.featureCode == "DASHBOARD_PERSONALIZE"
    )


def _dashboard_context_action_allowed(
    action: QuickActionRegistryItemDefinition,
    user: Any,
    context: QuickActionPermissionContext,
) -> bool:
    values: list[str] = []
    values.extend(_list_value(_get_value(user, "allowedFeatureCodes") or _get_value(user, "allowed_feature_codes")))
    values.extend(_list_value(_context_dict(user).get("allowedFeatureCodes")))
    profile = context.roleDashboardAccessProfile or get_role_dashboard_access_profile(context.roleCode)
    values.extend(_list_value(profile.get("allowedFeatureCodes") if profile else []))
    if not values:
        return False
    return action.featureCode in set(values)


def _context_allows_action_code(action: QuickActionRegistryItemDefinition, user: Any) -> bool:
    allowed_codes: list[str] = []
    allowed_codes.extend(_list_value(_get_value(user, "allowedActionCodes") or _get_value(user, "allowed_action_codes")))
    allowed_codes.extend(_list_value(_context_dict(user).get("allowedActionCodes")))
    if not allowed_codes:
        return True
    return action.quickActionCode in set(allowed_codes)


def _role_and_cabinet_allow_action(
    action: QuickActionRegistryItemDefinition,
    user: Any,
    context: QuickActionPermissionContext,
) -> bool:
    role_codes = _role_codes(user, context)
    if action.allowedRoles and not role_codes.intersection(set(action.allowedRoles)):
        return False
    if action.allowedCabinetTypes and context.cabinetType not in set(action.allowedCabinetTypes):
        return False
    return True


def _role_profile_allows_action(
    action: QuickActionRegistryItemDefinition,
    context: QuickActionPermissionContext,
) -> bool:
    profile = context.roleDashboardAccessProfile or get_role_dashboard_access_profile(context.roleCode)
    if not profile:
        return False
    default_actions = set(profile.get("defaultQuickActionCodes") or [])
    return action.quickActionCode in default_actions


def _widget_allows_action(
    user: Any,
    action: QuickActionRegistryItemDefinition,
    context: QuickActionPermissionContext,
) -> bool:
    widget_code = context.widgetCode or action.widgetCode
    if not widget_code:
        return True
    return can_view_widget(user, widget_code, {**context.to_dict(), "user": user})


def _merge_context(user: Any, context: Any | None) -> dict[str, Any]:
    merged = _context_dict(user)
    merged.update(_context_dict(context))
    return merged


def _quick_action_code(action: Any) -> str | None:
    if isinstance(action, str):
        return action
    return _get_value(action, "quickActionCode") or _get_value(action, "quick_action_code") or _get_value(action, "actionCode")


def _role_codes(user: Any, context: QuickActionPermissionContext) -> set[str]:
    values: list[str] = []
    for field_name in ("effectiveRoleCode", "roleCode", "role_code", "role"):
        value = _get_value(user, field_name) or _context_dict(user).get(field_name)
        if value:
            values.append(str(value))
    if context.roleCode:
        values.append(context.roleCode)

    normalized: set[str] = set()
    for value in values:
        normalized.add(value)
        upper = value.upper()
        if upper == "ADMIN":
            normalized.add("PLATFORM_ADMIN")
        if upper == "DEV_ADMIN":
            normalized.add("SUPER_ADMIN")
        if upper in LEGACY_ADMIN_ROLE_CODES:
            normalized.add("PLATFORM_ADMIN")
    return normalized


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
