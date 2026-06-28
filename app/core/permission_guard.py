from __future__ import annotations

from enum import Enum
from typing import Any

from app.core.access_levels import AccessLevel, is_valid_access_level
from app.core.access_scopes import AccessScope, is_valid_access_scope
from app.core.exceptions import ForbiddenError
from app.core.module_registration import DEFAULT_MODULE_REGISTRATIONS
from app.core.role_access_matrix import get_starter_role_module_access
from app.services.audit_log_service import record_access_denied_attempt


ACCESS_LEVEL_RANK: dict[str, int] = {
    AccessLevel.NO_ACCESS: 0,
    AccessLevel.VIEW: 1,
    AccessLevel.CREATE: 2,
    AccessLevel.EDIT: 3,
    AccessLevel.APPROVE: 4,
    AccessLevel.ADMIN: 5,
}

LEGACY_ROLE_ALIASES: dict[str, str] = {
    "ADMIN": "PLATFORM_ADMIN",
    "DEV_ADMIN": "SUPER_ADMIN",
    "MANAGER": "PLATFORM_ADMIN",
    "ENGINEER": "ENGINEER_DESIGNER",
}

MODULE_CODE_ALIASES: dict[str, str] = {
    "MODULE_05_ESTIMATES": "MODULE_05_ESTIMATE_ENGINE",
    "MODULE_07_DIGITAL_OBJECT": "MODULE_07_DIGITAL_HOUSE",
    "MODULE_08_PROCUREMENT": "MODULE_09_PROCUREMENT",
    "MODULE_09_TENDERS": "MODULE_09_PROCUREMENT",
    "MODULE_14_PRICE_HISTORY": "MODULE_11_ANALYTICS",
    "MODULE_14_CONSTRUCTOR_LITE": "MODULE_19_CONSTRUCTOR_LITE",
    "MODULE_15_CONSTRUCTION_GROUPS": "MODULE_01_MATERIAL_HUB",
    "MODULE_16_ADMIN_CABINET": "MODULE_03_USERS_ROLES",
    "MODULE_16_QUALITY_CONTROL": "MODULE_18_QUALITY_CONTROL",
    "MODULE_17_SITE_SUPERVISION": "MODULE_20_SITE_SUPERVISION",
    "MODULE_18_WARRANTY_SERVICE": "MODULE_21_WARRANTY_SERVICE",
}

ACTION_REQUIRED_ACCESS_LEVELS: dict[str, str] = {
    "VIEW": AccessLevel.VIEW,
    "READ": AccessLevel.VIEW,
    "OPEN": AccessLevel.VIEW,
    "LIST": AccessLevel.VIEW,
    "EXPORT": AccessLevel.VIEW,
    "CREATE": AccessLevel.CREATE,
    "ADD": AccessLevel.CREATE,
    "UPLOAD": AccessLevel.CREATE,
    "RUN": AccessLevel.CREATE,
    "START": AccessLevel.CREATE,
    "IMPORT": AccessLevel.EDIT,
    "EDIT": AccessLevel.EDIT,
    "UPDATE": AccessLevel.EDIT,
    "CONFIGURE": AccessLevel.EDIT,
    "MANAGE": AccessLevel.ADMIN,
    "APPROVE": AccessLevel.APPROVE,
    "MODERATE": AccessLevel.APPROVE,
    "VERIFY": AccessLevel.APPROVE,
    "ADMIN": AccessLevel.ADMIN,
}

OWNERSHIP_FIELDS: tuple[str, ...] = (
    "owner_id",
    "ownerId",
    "user_id",
    "userId",
    "created_by",
    "createdBy",
    "created_by_user_id",
    "uploaded_by_user_id",
)


DEV_USER: dict[str, Any] = {
    "userId": "dev-admin-mock",
    "roleCode": "SUPER_ADMIN",
    "authMode": "dev",
}


def can(
    user: Any | None,
    moduleCode: str,
    actionCode: str,
    scope: str = AccessScope.GLOBAL,
) -> bool:
    if not user or not moduleCode or not actionCode:
        return False

    module_code = canonical_module_code(moduleCode)
    required_access_level = required_access_level_for_action(actionCode)
    required_scope = _enum_value(scope)
    if not is_valid_access_scope(required_scope):
        return False

    rules = _access_rules_for_user(user)
    explicit_rules = _explicit_access_rules_for_user(user)
    if _has_explicit_no_access(explicit_rules, module_code):
        return False

    return any(
        canonical_module_code(rule.get("moduleCode") or "") == module_code
        and _access_level_satisfies(rule.get("accessLevel"), required_access_level)
        and _scope_satisfies(rule.get("accessScope"), required_scope)
        for rule in rules
    )


def require_permission(
    user: Any | None,
    moduleCode: str,
    actionCode: str,
    scope: str = AccessScope.GLOBAL,
) -> Any:
    if not can(user, moduleCode, actionCode, scope):
        record_access_denied_attempt(
            user=user,
            module_code=canonical_module_code(moduleCode),
            action_code=actionCode,
            scope=_enum_value(scope),
            reason="Permission Guard denied access.",
        )
        raise ForbiddenError(
            f"Required permission: {moduleCode}:{actionCode}:{_enum_value(scope)}"
        )
    return user


def requirePermission(
    user: Any | None,
    moduleCode: str,
    actionCode: str,
    scope: str = AccessScope.GLOBAL,
) -> Any:
    return require_permission(user, moduleCode, actionCode, scope)


def require_own_resource(
    user: Any | None,
    resource: Any | None,
    *,
    allow_global_admin: bool = False,
) -> Any:
    if not user or not resource:
        raise ForbiddenError("Resource ownership is required.")
    if allow_global_admin and _has_global_admin_access(user):
        return resource

    user_id = _string_or_none(_get_value(user, "userId") or _get_value(user, "id"))
    if not user_id:
        raise ForbiddenError("Current user id is required.")

    for field_name in OWNERSHIP_FIELDS:
        owner_value = _get_value(resource, field_name)
        if owner_value is not None and str(owner_value) == user_id:
            return resource

    raise ForbiddenError("Resource ownership is required.")


def requireOwnResource(user: Any | None, resource: Any | None) -> Any:
    return require_own_resource(user, resource)


def canonical_module_code(module_code: str) -> str:
    return MODULE_CODE_ALIASES.get(module_code, module_code)


def required_access_level_for_action(action_code: str) -> str:
    normalized = action_code.upper()
    if is_valid_access_level(normalized):
        return normalized
    for prefix, access_level in ACTION_REQUIRED_ACCESS_LEVELS.items():
        if normalized == prefix or normalized.startswith(f"{prefix}_"):
            return access_level
    return AccessLevel.ADMIN


def _access_rules_for_user(user: Any) -> list[dict[str, str]]:
    return [
        *_explicit_access_rules_for_user(user),
        *_role_matrix_rules_for_user(user),
        *_registration_rules_for_user(user),
    ]


def _explicit_access_rules_for_user(user: Any) -> list[dict[str, str]]:
    data_rules = _get_value(user, "moduleAccessRules") or _get_value(user, "module_access_rules")
    if data_rules:
        return [_normalize_rule(rule) for rule in data_rules if _normalize_rule(rule)]

    model_rules = _safe_iterable(_get_value(user, "module_access"))
    return [_normalize_model_access_rule(rule) for rule in model_rules if _normalize_model_access_rule(rule)]


def _role_matrix_rules_for_user(user: Any) -> list[dict[str, str]]:
    role_codes = _role_codes_for_user(user)
    if not role_codes:
        return []
    matrix = get_starter_role_module_access()
    return [
        rule
        for rule in matrix
        if rule.get("roleCode") in role_codes
    ]


def _registration_rules_for_user(user: Any) -> list[dict[str, str]]:
    role_codes = _role_codes_for_user(user)
    if not role_codes:
        return []

    rules: list[dict[str, str]] = []
    for registration in DEFAULT_MODULE_REGISTRATIONS:
        for permission in registration.defaultPermissions:
            if _normalize_role_code(permission.role) in role_codes:
                rules.append(
                    {
                        "roleCode": permission.role,
                        "moduleCode": registration.canonicalModuleCode or registration.moduleCode,
                        "accessLevel": permission.accessLevel,
                        "accessScope": permission.scope,
                    }
                )
    return rules


def _role_codes_for_user(user: Any) -> set[str]:
    role_values: list[Any] = []
    for field_name in ("roleCode", "role_code", "role"):
        value = _get_value(user, field_name)
        if value:
            role_values.append(value)

    role_values.extend(_safe_iterable(_get_value(user, "roleCodes") or _get_value(user, "role_codes")))
    for assignment in _safe_iterable(_get_value(user, "role_assignments")):
        role = _get_value(assignment, "role")
        role_key = _get_value(role, "role_key") if role else None
        if role_key:
            role_values.append(role_key)

    return {
        normalized
        for normalized in (_normalize_role_code(value) for value in role_values)
        if normalized
    }


def _normalize_role_code(value: Any) -> str | None:
    role_code = _enum_value(value)
    if not role_code:
        return None
    return LEGACY_ROLE_ALIASES.get(role_code, role_code)


def _normalize_rule(rule: Any) -> dict[str, str]:
    module_code = _get_value(rule, "moduleCode") or _get_value(rule, "module_code")
    access_level = _get_value(rule, "accessLevel") or _get_value(rule, "access_level")
    access_scope = _get_value(rule, "accessScope") or _get_value(rule, "access_scope")
    if not module_code or not access_level or not access_scope:
        return {}
    return {
        "moduleCode": str(module_code),
        "accessLevel": _enum_value(access_level),
        "accessScope": _enum_value(access_scope),
    }


def _normalize_model_access_rule(rule: Any) -> dict[str, str]:
    if _enum_value(_get_value(rule, "status")) not in {"", "ACTIVE"}:
        return {}
    return _normalize_rule(rule)


def _has_explicit_no_access(explicit_rules: list[dict[str, str]], module_code: str) -> bool:
    return any(
        canonical_module_code(rule.get("moduleCode") or "") == module_code
        and _enum_value(rule.get("accessLevel")) == AccessLevel.NO_ACCESS
        for rule in explicit_rules
    )


def _access_level_satisfies(granted: Any, required: str) -> bool:
    granted_value = _enum_value(granted)
    required_value = _enum_value(required)
    return ACCESS_LEVEL_RANK.get(granted_value, 0) >= ACCESS_LEVEL_RANK.get(required_value, 0)


def _scope_satisfies(granted: Any, required: str) -> bool:
    granted_value = _enum_value(granted)
    required_value = _enum_value(required)
    if granted_value == AccessScope.NONE:
        return False
    if granted_value == AccessScope.GLOBAL:
        return True
    return granted_value == required_value


def _has_global_admin_access(user: Any) -> bool:
    role_codes = _role_codes_for_user(user)
    return bool({"SUPER_ADMIN", "PLATFORM_ADMIN"} & role_codes)


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    try:
        return getattr(source, field_name)
    except Exception:
        return None


def _safe_iterable(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


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
