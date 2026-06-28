from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from app.core.access_levels import AccessLevel
from app.core.access_scopes import AccessScope
from app.core.module_registration import DEFAULT_MODULE_REGISTRATIONS
from app.core.permission_guard import can, canonical_module_code
from app.core.role_access_matrix import get_starter_role_feature_access, get_starter_role_module_access
from app.services.dashboard_module_registry import get_canonical_module_code
from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_SOURCE_MODULE
from app.services.quick_action_registry import get_quick_action_registry, get_quick_action_registry_item
from app.services.role_dashboard_access_profiles import normalize_role_dashboard_profile_code
from app.services.widget_permission import can_view_widget
from app.services.widget_registry import get_widget_registry


SOURCE_MODULE_CODE = "MODULE_03_USERS_ROLES"
ACTIVE_REGISTRY_STATUS = "ACTIVE"


@dataclass(frozen=True)
class AccessScopeGrant:
    moduleCode: str
    accessScope: str
    accessLevel: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AccessPermissionSummary:
    roleCode: str | None
    moduleCode: str
    accessLevel: str
    accessScope: str
    source: str

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class AccessContextForCabinet:
    userId: str
    roleCodes: list[str]
    allowedModuleCodes: list[str]
    scopes: list[AccessScopeGrant]
    sourceModuleCode: str = SOURCE_MODULE_CODE
    workspaceId: str | None = None
    activeRegionCode: str | None = None
    permissions: list[AccessPermissionSummary] = field(default_factory=list)
    allowedFeatureCodes: list[str] = field(default_factory=list)
    allowedActionCodes: list[str] = field(default_factory=list)
    allowedWidgetCodes: list[str] = field(default_factory=list)
    allowedQuickActionCodes: list[str] = field(default_factory=list)
    _userContext: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("_userContext", None)
        data["scopes"] = [scope.to_dict() for scope in self.scopes]
        data["permissions"] = [permission.to_dict() for permission in self.permissions]
        return data

    def canViewModule(self, moduleCode: str) -> bool:
        module_code = _canonical_module(moduleCode)
        if module_code not in set(self.allowedModuleCodes):
            return False
        return any(
            can(self._guard_user(), module_code, AccessLevel.VIEW, scope.accessScope)
            for scope in self.scopes
            if scope.moduleCode == module_code
        )

    def canViewWidget(self, widgetCode: str) -> bool:
        if widgetCode not in set(self.allowedWidgetCodes):
            return False
        return can_view_widget(
            self._guard_user(),
            widgetCode,
            {
                "activeRegionCode": self.activeRegionCode,
                "roleCode": self.roleCodes[0] if self.roleCodes else None,
                "userDashboardLayout": {"widgets": []},
            },
        )

    def canRunQuickAction(self, quickActionCode: str) -> bool:
        if quickActionCode not in set(self.allowedQuickActionCodes):
            return False
        action = get_quick_action_registry_item(quickActionCode)
        if not action or action.status != ACTIVE_REGISTRY_STATUS:
            return False
        return _quick_action_allowed_by_module03(
            action.to_dict(),
            self._guard_user(),
            self.allowedFeatureCodes,
            self.allowedWidgetCodes,
            self.roleCodes,
            self.activeRegionCode,
        )

    def _guard_user(self) -> dict[str, Any]:
        return {
            **self._userContext,
            "userId": self.userId,
            "workspaceId": self.workspaceId,
            "roleCode": self.roleCodes[0] if self.roleCodes else None,
            "roleCodes": self.roleCodes,
            "activeRegionCode": self.activeRegionCode,
            "allowedFeatureCodes": self.allowedFeatureCodes,
            "allowedWidgetCodes": self.allowedWidgetCodes,
            "allowedActionCodes": self.allowedQuickActionCodes,
        }


def build_access_context_for_cabinet(user: Any, *, active_region_code: str | None = None) -> AccessContextForCabinet:
    data = _value_dict(user)
    role_codes = _role_codes(data)
    user_id = _string_or_none(_get_value(data, "userId") or _get_value(data, "id")) or ""
    workspace_id = _string_or_none(_get_value(data, "workspaceId") or _get_value(data, "workspace_id"))
    region_code = active_region_code or _string_or_none(_get_value(data, "activeRegionCode") or _get_value(data, "region_id"))

    permissions = _permission_summaries(data, role_codes)
    scopes = _scopes_from_permissions(permissions)
    allowed_module_codes = _unique_strings(
        permission.moduleCode
        for permission in permissions
        if permission.accessLevel != AccessLevel.NO_ACCESS and permission.accessScope != AccessScope.NONE
    )
    allowed_feature_codes = _allowed_feature_codes(data, role_codes)
    user_context = {
        **data,
        "userId": user_id,
        "workspaceId": workspace_id,
        "roleCode": role_codes[0] if role_codes else None,
        "roleCodes": role_codes,
        "activeRegionCode": region_code,
    }
    allowed_widget_codes = _allowed_widget_codes(user_context, allowed_feature_codes)
    allowed_quick_action_codes = _allowed_quick_action_codes(
        user_context,
        role_codes,
        allowed_feature_codes,
        allowed_widget_codes,
        region_code,
    )
    allowed_action_codes = _allowed_action_codes(allowed_quick_action_codes)

    return AccessContextForCabinet(
        userId=user_id,
        workspaceId=workspace_id,
        roleCodes=role_codes,
        activeRegionCode=region_code,
        permissions=permissions,
        allowedModuleCodes=allowed_module_codes,
        allowedFeatureCodes=allowed_feature_codes,
        allowedActionCodes=allowed_action_codes,
        allowedWidgetCodes=allowed_widget_codes,
        allowedQuickActionCodes=allowed_quick_action_codes,
        scopes=scopes,
        _userContext=user_context,
    )


def get_access_context_for_cabinet(user: Any, *, active_region_code: str | None = None) -> AccessContextForCabinet:
    return build_access_context_for_cabinet(user, active_region_code=active_region_code)


def _permission_summaries(data: dict[str, Any], role_codes: list[str]) -> list[AccessPermissionSummary]:
    permissions: list[AccessPermissionSummary] = []
    for rule in get_starter_role_module_access():
        role_code = normalize_role_dashboard_profile_code(rule.get("roleCode"))
        if role_code not in set(role_codes):
            continue
        permissions.append(
            AccessPermissionSummary(
                roleCode=role_code,
                moduleCode=_canonical_module(rule["moduleCode"]),
                accessLevel=rule["accessLevel"],
                accessScope=rule["accessScope"],
                source="role_access_matrix",
            )
        )

    for registration in DEFAULT_MODULE_REGISTRATIONS:
        for permission in registration.defaultPermissions:
            role_code = normalize_role_dashboard_profile_code(permission.role)
            if role_code not in set(role_codes):
                continue
            permissions.append(
                AccessPermissionSummary(
                    roleCode=role_code,
                    moduleCode=_canonical_module(registration.canonicalModuleCode or registration.moduleCode),
                    accessLevel=permission.accessLevel,
                    accessScope=permission.scope,
                    source="module_registration_default",
                )
            )

    for rule in _list_value(data.get("moduleAccessRules") or data.get("module_access_rules")):
        module_code = _get_value(rule, "moduleCode") or _get_value(rule, "module_code")
        access_level = _get_value(rule, "accessLevel") or _get_value(rule, "access_level")
        access_scope = _get_value(rule, "accessScope") or _get_value(rule, "access_scope")
        if not module_code or not access_level or not access_scope:
            continue
        permissions.append(
            AccessPermissionSummary(
                roleCode=None,
                moduleCode=_canonical_module(str(module_code)),
                accessLevel=_enum_value(access_level),
                accessScope=_enum_value(access_scope),
                source="explicit_user_rule",
            )
        )

    return _dedupe_permissions(permissions)


def _scopes_from_permissions(permissions: list[AccessPermissionSummary]) -> list[AccessScopeGrant]:
    scopes: list[AccessScopeGrant] = []
    for permission in permissions:
        if permission.accessLevel == AccessLevel.NO_ACCESS or permission.accessScope == AccessScope.NONE:
            continue
        grant = AccessScopeGrant(
            moduleCode=permission.moduleCode,
            accessLevel=permission.accessLevel,
            accessScope=permission.accessScope,
        )
        if grant not in scopes:
            scopes.append(grant)
    return scopes


def _allowed_feature_codes(data: dict[str, Any], role_codes: list[str]) -> list[str]:
    values: list[str] = []
    values.extend(_list_value(data.get("allowedFeatureCodes") or data.get("allowed_feature_codes")))
    for rule in get_starter_role_feature_access():
        if normalize_role_dashboard_profile_code(rule.get("roleCode")) in set(role_codes):
            values.append(str(rule["featureCode"]))
    if role_codes:
        values.extend(["DASHBOARD_VIEW", "ATOM_MAP_VIEW"])
    values.extend(["DASHBOARD_PERSONALIZE"] if set(role_codes) - {"VIEWER"} else [])
    return _unique_strings(values)


def _allowed_widget_codes(user_context: dict[str, Any], allowed_feature_codes: list[str]) -> list[str]:
    user = {**user_context, "allowedFeatureCodes": allowed_feature_codes}
    codes: list[str] = []
    for widget in get_widget_registry():
        widget_code = widget["widgetCode"]
        if can_view_widget(user, widget_code, {"activeRegionCode": user_context.get("activeRegionCode"), "userDashboardLayout": {"widgets": []}}):
            codes.append(widget_code)
    return _unique_strings(codes)


def _allowed_quick_action_codes(
    user_context: dict[str, Any],
    role_codes: list[str],
    allowed_feature_codes: list[str],
    allowed_widget_codes: list[str],
    active_region_code: str | None,
) -> list[str]:
    codes: list[str] = []
    for action in get_quick_action_registry():
        if _quick_action_allowed_by_module03(
            action,
            user_context,
            allowed_feature_codes,
            allowed_widget_codes,
            role_codes,
            active_region_code,
        ):
            codes.append(action["quickActionCode"])
    return _unique_strings(codes)


def _allowed_action_codes(allowed_quick_action_codes: list[str]) -> list[str]:
    action_codes: list[str] = []
    for quick_action_code in allowed_quick_action_codes:
        action = get_quick_action_registry_item(quick_action_code)
        if action:
            action_codes.append(action.requiredActionCode)
    return _unique_strings(action_codes)


def _quick_action_allowed_by_module03(
    action: dict[str, Any],
    user_context: dict[str, Any],
    allowed_feature_codes: list[str],
    allowed_widget_codes: list[str],
    role_codes: list[str],
    active_region_code: str | None,
) -> bool:
    if not active_region_code:
        return False
    if action.get("status") != ACTIVE_REGISTRY_STATUS:
        return False
    allowed_roles = set(action.get("allowedRoles") or [])
    if allowed_roles and not allowed_roles.intersection(set(role_codes)):
        return False
    widget_code = action.get("widgetCode")
    if widget_code and widget_code not in set(allowed_widget_codes):
        return False

    source_module_code = _canonical_module(action.get("canonicalModuleCode") or action.get("sourceModuleCode"))
    if source_module_code == DASHBOARD_ADMIN_SOURCE_MODULE:
        feature_code = action.get("featureCode")
        return not feature_code or feature_code in set(allowed_feature_codes)

    return can(
        user_context,
        source_module_code,
        action.get("requiredActionCode") or action.get("requiredAccessLevel") or AccessLevel.VIEW,
        action.get("requiredScope") or AccessScope.LIMITED,
    )


def _role_codes(data: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in ("effectiveRoleCode", "roleCode", "role_code", "role"):
        value = data.get(key)
        if value:
            values.append(value)
    values.extend(_list_value(data.get("roleCodes") or data.get("role_codes")))

    normalized: list[str] = []
    for value in values:
        role_code = normalize_role_dashboard_profile_code(str(value))
        if role_code and role_code not in normalized:
            normalized.append(role_code)
    return normalized


def _canonical_module(module_code: Any) -> str:
    return canonical_module_code(get_canonical_module_code(str(module_code)) or str(module_code))


def _dedupe_permissions(permissions: list[AccessPermissionSummary]) -> list[AccessPermissionSummary]:
    result: list[AccessPermissionSummary] = []
    seen: set[tuple[str | None, str, str, str, str]] = set()
    for permission in permissions:
        key = (
            permission.roleCode,
            permission.moduleCode,
            permission.accessLevel,
            permission.accessScope,
            permission.source,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(permission)
    return result


def _value_dict(value: Any) -> dict[str, Any]:
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
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _unique_strings(values: Any) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value is None:
            continue
        item = str(value)
        if item not in unique:
            unique.append(item)
    return unique


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
