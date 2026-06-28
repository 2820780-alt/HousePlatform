from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.role_dashboard_access_profiles import (
    SOURCE_MODULE_CODE,
    get_role_dashboard_access_profile_definition,
    get_role_dashboard_access_profile_definitions,
)
from app.core.system_roles import LEGACY_ADMIN_ROLE_CODES
from app.services.dashboard_module_registry import get_canonical_module_code, get_dashboard_module_registry_item
from app.services.dashboard_widget_registry import get_dashboard_widget_registry_item


ROLE_DASHBOARD_PROFILE_LAYER = "module03_role_dashboard_access_profile"
ROLE_DASHBOARD_PROFILE_NOTE = (
    "RoleDashboardAccessProfile is a Module 03 access/preset layer for the existing Dashboard. "
    "It recommends visible modules, widgets, quick actions and layout defaults, then the result is "
    "filtered by PermissionGuard, WidgetRegistry, PlatformModuleRegistry, UserDashboardLayout and later Module 08 presets."
)

LEGACY_ROLE_PROFILE_ALIASES = {
    "ADMIN": "PLATFORM_ADMIN",
    "DEV_ADMIN": "SUPER_ADMIN",
    "MANAGER": "PLATFORM_ADMIN",
    "ENGINEER": "ENGINEER_DESIGNER",
}

KNOWN_DASHBOARD_QUICK_ACTION_CODES = {
    "MATERIAL_CREATE",
    "SUPPLIER_PRICE_UPLOAD",
    "SOURCE_TASK_CREATE",
    "MATERIAL_MODERATION_OPEN",
    "SOURCE_ERRORS_OPEN",
    "SOURCE_CREATE",
    "DOCUMENT_LIST_OPEN",
    "DASHBOARD_CONFIGURE",
}


def get_role_dashboard_access_profile(role_code: str | None) -> dict[str, Any] | None:
    normalized_role = normalize_role_dashboard_profile_code(role_code)
    definition = get_role_dashboard_access_profile_definition(normalized_role)
    if not definition:
        return None

    profile = deepcopy(definition)
    allowed_modules = _normalize_module_codes(profile.get("allowedModuleCodes") or [])
    allowed_features = _unique_strings(profile.get("allowedFeatureCodes") or [])
    hidden_widgets = _unique_strings(profile.get("hiddenWidgetCodes") or [])

    profile["roleCode"] = normalized_role
    profile["sourceModuleCode"] = profile.get("sourceModuleCode") or SOURCE_MODULE_CODE
    profile["allowedModuleCodes"] = allowed_modules
    profile["allowedFeatureCodes"] = allowed_features
    profile["hiddenWidgetCodes"] = hidden_widgets
    profile["defaultWidgetCodes"] = _filter_default_widget_codes(
        profile.get("defaultWidgetCodes") or [],
        allowed_module_codes=allowed_modules,
        allowed_feature_codes=allowed_features,
        hidden_widget_codes=hidden_widgets,
    )
    profile["defaultQuickActionCodes"] = _filter_default_quick_action_codes(
        profile.get("defaultQuickActionCodes") or []
    )
    settings = dict(profile.get("settings") or {})
    settings["favoriteModuleCodes"] = _normalize_module_codes(settings.get("favoriteModuleCodes") or [])
    profile["settings"] = settings
    profile["profileLayer"] = ROLE_DASHBOARD_PROFILE_LAYER
    profile["compatibilityNote"] = ROLE_DASHBOARD_PROFILE_NOTE
    return profile


def get_role_dashboard_access_profiles() -> list[dict[str, Any]]:
    profiles = [
        get_role_dashboard_access_profile(profile["roleCode"])
        for profile in get_role_dashboard_access_profile_definitions()
    ]
    return [profile for profile in profiles if profile]


def get_role_dashboard_preview_options() -> list[dict[str, str]]:
    return [
        {
            "roleCode": profile["roleCode"],
            "label": profile.get("settings", {}).get("label") or _role_label(profile["roleCode"]),
        }
        for profile in get_role_dashboard_access_profiles()
        if profile["roleCode"] not in {"SUPER_ADMIN", "PLATFORM_ADMIN"}
    ]


def normalize_role_dashboard_profile_code(role_code: str | None) -> str | None:
    if not role_code:
        return None
    normalized = role_code.upper()
    return LEGACY_ROLE_PROFILE_ALIASES.get(normalized, normalized)


def can_preview_dashboard_access_profiles(role_code: str | None) -> bool:
    normalized = (role_code or "").upper()
    return normalized in {"SUPER_ADMIN", "PLATFORM_ADMIN", *LEGACY_ADMIN_ROLE_CODES}


def _filter_default_widget_codes(
    widget_codes: list[str] | tuple[str, ...],
    *,
    allowed_module_codes: list[str],
    allowed_feature_codes: list[str],
    hidden_widget_codes: list[str],
) -> list[str]:
    allowed_modules = set(allowed_module_codes)
    allowed_features = set(allowed_feature_codes)
    hidden_widgets = set(hidden_widget_codes)
    filtered: list[str] = []
    for widget_code in widget_codes:
        if widget_code in hidden_widgets or widget_code in filtered:
            continue
        widget = get_dashboard_widget_registry_item(widget_code)
        if not widget:
            continue
        if widget.status not in {"available", "mock_only"}:
            continue
        source_module_code = get_canonical_module_code(widget.requiredModuleCode or widget.sourceModuleCode)
        if source_module_code not in allowed_modules:
            continue
        if widget.featureCode and widget.featureCode not in allowed_features:
            continue
        filtered.append(widget_code)
    return filtered


def _filter_default_quick_action_codes(action_codes: list[str] | tuple[str, ...]) -> list[str]:
    return [
        action_code
        for action_code in _unique_strings(action_codes)
        if action_code in KNOWN_DASHBOARD_QUICK_ACTION_CODES
    ]


def _normalize_module_codes(module_codes: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    for module_code in module_codes:
        canonical = get_canonical_module_code(module_code) or module_code
        item = get_dashboard_module_registry_item(module_code) or get_dashboard_module_registry_item(canonical)
        if item and item.status in {"merged", "archived", "deprecated", "disabled"}:
            canonical = get_canonical_module_code(item.moduleCode) or canonical
        if canonical not in normalized:
            normalized.append(canonical)
    return normalized


def _unique_strings(values: list[Any] | tuple[Any, ...]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if not isinstance(value, str) or value in unique:
            continue
        unique.append(value)
    return unique


def _role_label(role_code: str) -> str:
    return {
        "SUPER_ADMIN": "Супер администратор",
        "PLATFORM_ADMIN": "Администратор платформы",
        "MODERATOR": "Модератор",
        "KNOWLEDGE_MANAGER": "Менеджер знаний",
        "ESTIMATOR": "Сметчик",
        "ENGINEER_DESIGNER": "Инженер-проектировщик",
        "SUPPLIER": "Поставщик",
        "CONTRACTOR": "Подрядчик",
        "CUSTOMER": "Заказчик",
        "ANALYST": "Аналитик",
        "VIEWER": "Наблюдатель",
    }.get(role_code, role_code)
