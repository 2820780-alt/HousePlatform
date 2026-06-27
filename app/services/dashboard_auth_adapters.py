from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.dashboard_module_registry import (
    get_canonical_module_code,
    normalize_dashboard_layout,
)
from app.services.dashboard_widget_config import widget_config_from_dict
from app.services.dashboard_widget_registry import get_dashboard_widget_registry


ADMIN_ROLE_CODES = {"ADMIN", "SUPER_ADMIN", "DEV_ADMIN"}
DEV_AUTH_MODES = {"mock", "dev"}
ROLE_LABELS = {
    "ADMIN": "Администратор",
    "SUPER_ADMIN": "Супер администратор",
    "DEV_ADMIN": "Разработчик",
    "ANALYST": "Аналитик",
    "SUPPLIER": "Поставщик",
    "CUSTOMER": "Заказчик",
    "ESTIMATOR": "Сметчик",
}
PREVIEW_ROLE_OPTIONS = [
    {"roleCode": "ANALYST", "label": ROLE_LABELS["ANALYST"]},
    {"roleCode": "SUPPLIER", "label": ROLE_LABELS["SUPPLIER"]},
    {"roleCode": "CUSTOMER", "label": ROLE_LABELS["CUSTOMER"]},
    {"roleCode": "ESTIMATOR", "label": ROLE_LABELS["ESTIMATOR"]},
]
PREVIEW_ROLE_PROFILES = {
    "ANALYST": {
        "workspaceType": "ANALYTICS",
        "activeCabinetType": "ANALYST",
        "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS", "MODULE_13_AUDIT"],
        "favoriteModuleCodes": ["MODULE_11_ANALYTICS", "MODULE_01_MATERIAL_HUB", "MODULE_13_AUDIT"],
        "allowedActionCodes": ["DASHBOARD_CONFIGURE", "SOURCE_ERRORS_OPEN", "DOCUMENT_LIST_OPEN"],
        "allowedFeatureCodes": ["DASHBOARD_VIEW", "DASHBOARD_PERSONALIZE", "ATOM_MAP_VIEW", "PRICE_DYNAMICS"],
    },
    "SUPPLIER": {
        "workspaceType": "SUPPLIER",
        "activeCabinetType": "SUPPLIER",
        "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_08_PROCUREMENT", "MODULE_09_TENDERS", "MODULE_10_MARKETPLACE"],
        "favoriteModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_08_PROCUREMENT", "MODULE_09_TENDERS"],
        "allowedActionCodes": ["SUPPLIER_PRICE_UPLOAD", "DASHBOARD_CONFIGURE"],
        "allowedFeatureCodes": ["DASHBOARD_VIEW", "DASHBOARD_PERSONALIZE", "ATOM_MAP_VIEW"],
    },
    "CUSTOMER": {
        "workspaceType": "CUSTOMER",
        "activeCabinetType": "CUSTOMER",
        "allowedModuleCodes": ["MODULE_05_ESTIMATES", "MODULE_07_DIGITAL_HOUSE", "MODULE_08_PROCUREMENT", "MODULE_10_MARKETPLACE"],
        "favoriteModuleCodes": ["MODULE_07_DIGITAL_HOUSE", "MODULE_05_ESTIMATES", "MODULE_08_PROCUREMENT"],
        "allowedActionCodes": ["DASHBOARD_CONFIGURE"],
        "allowedFeatureCodes": ["DASHBOARD_VIEW", "DASHBOARD_PERSONALIZE", "ATOM_MAP_VIEW"],
    },
    "ESTIMATOR": {
        "workspaceType": "ESTIMATES",
        "activeCabinetType": "ESTIMATOR",
        "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_05_ESTIMATES", "MODULE_06_ESTIMATE_AUDIT", "MODULE_11_ANALYTICS"],
        "favoriteModuleCodes": ["MODULE_05_ESTIMATES", "MODULE_06_ESTIMATE_AUDIT", "MODULE_01_MATERIAL_HUB"],
        "allowedActionCodes": ["DASHBOARD_CONFIGURE"],
        "allowedFeatureCodes": ["DASHBOARD_VIEW", "DASHBOARD_PERSONALIZE", "ATOM_MAP_VIEW", "PRICE_DYNAMICS"],
    },
}


@dataclass
class DashboardUserContext:
    userId: str | None = None
    displayName: str | None = None
    roleCode: str | None = None
    workspaceId: str | None = None
    workspaceTitle: str | None = None
    workspaceType: str | None = None
    activeRegionCode: str | None = None
    activeRegionName: str | None = None
    activeCabinetId: str | None = None
    activeCabinetType: str | None = None
    availableRegionCodes: list[str] = field(default_factory=list)
    allowedModuleCodes: list[str] = field(default_factory=list)
    allowedWidgetCodes: list[str] = field(default_factory=list)
    allowedFeatureCodes: list[str] = field(default_factory=list)
    allowedActionCodes: list[str] = field(default_factory=list)
    favoriteModuleCodes: list[str] = field(default_factory=list)
    previewRoleCode: str | None = None
    effectiveRoleCode: str | None = None
    effectiveRoleLabel: str | None = None
    dashboardLayout: dict[str, Any] = field(default_factory=dict)
    cabinetDashboardPreset: dict[str, Any] = field(default_factory=dict)
    userDashboardLayout: dict[str, Any] = field(default_factory=dict)
    authMode: str = "mock"

    def to_template_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["display_name"] = self.displayName
        data["role"] = self.roleCode
        data["roleLabel"] = ROLE_LABELS.get(self.roleCode or "", self.roleCode)
        data["previewRoleCode"] = self.previewRoleCode
        data["effectiveRoleCode"] = self.effectiveRoleCode or self.roleCode
        data["effectiveRoleLabel"] = self.effectiveRoleLabel or ROLE_LABELS.get(self.roleCode or "", self.roleCode)
        data["workspace"] = self.workspaceTitle
        data["allowedModules"] = self.allowedModuleCodes
        data["allowedWidgets"] = self.allowedWidgetCodes
        data["allowedActions"] = self.allowedActionCodes
        data["favoriteModules"] = self.favoriteModuleCodes
        data["canPreviewDashboardRoles"] = self.roleCode in ADMIN_ROLE_CODES
        data["previewRoleOptions"] = PREVIEW_ROLE_OPTIONS
        data["cabinetDashboardPreset"] = self.cabinetDashboardPreset
        data["userDashboardLayout"] = self.userDashboardLayout
        data["is_mock"] = self.authMode == "mock"
        return data


class DashboardUserContextAdapter:
    @staticmethod
    def get_dashboard_user_context(
        *,
        personalization: dict[str, Any],
        active_region: dict[str, Any],
        cards: list[dict[str, Any]],
        preview_role_code: str | None = None,
    ) -> DashboardUserContext:
        real_role_code = "ADMIN"
        normalized_preview_role = _normalize_preview_role(preview_role_code, real_role_code)
        effective_role_code = normalized_preview_role or real_role_code
        allowed_module_codes = sorted({
            get_canonical_module_code(card["canonical_module_code"])
            for card in cards
            if card.get("atom_status") not in {"disabled", "archived", "merged"}
        })
        favorite_module_codes = [
            get_canonical_module_code(module["module_code"])
            for module in personalization["favorite_modules"]
            if module.get("module_code")
        ] or ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"]
        allowed_widget_codes = [
            widget_config_from_dict(widget, position=index + 1).widgetCode
            for index, widget in enumerate(personalization["widgets"])
        ]
        allowed_widget_codes.extend(
            widget["widgetCode"]
            for widget in get_dashboard_widget_registry()
            if widget["isEnabledByDefault"]
        )
        allowed_widget_codes = sorted(set(allowed_widget_codes))
        active_region_code = active_region.get("code")
        profile = PREVIEW_ROLE_PROFILES.get(effective_role_code, {})
        if profile:
            allowed_module_codes = profile["allowedModuleCodes"]
            favorite_module_codes = profile["favoriteModuleCodes"]

        dashboard_layout = normalize_dashboard_layout({
            "version": "mock-v1",
            "previewRoleCode": normalized_preview_role,
            "atomMap": {
                "maxVisibleModules": 6,
                "favoriteModulesOnly": True,
            },
            "zones": {
                "TOP_WIDGET_GRID": {
                    "isEnabled": True,
                    "maxVisibleWidgets": 6,
                },
                "RIGHT_RAIL": {
                    "isEnabled": False,
                    "maxVisibleWidgets": 3,
                },
                "BOTTOM_WIDGET_GRID": {
                    "isEnabled": True,
                    "maxVisibleWidgets": 6,
                },
            },
            "widgets": [
                _widget_layout(widget, position=index + 1)
                for index, widget in enumerate(personalization["widgets"])
            ],
        })

        return DashboardUserContext(
            userId="dev-admin-mock",
            displayName="Администратор",
            roleCode=real_role_code,
            workspaceTitle=personalization["active_workspace"],
            workspaceType=profile.get("workspaceType", "ADMINISTRATION"),
            activeRegionCode=active_region_code,
            activeRegionName=active_region.get("name"),
            activeCabinetId="cabinet-admin-mock",
            activeCabinetType=profile.get("activeCabinetType", "ADMIN"),
            availableRegionCodes=[active_region_code] if active_region_code else [],
            allowedModuleCodes=allowed_module_codes,
            allowedWidgetCodes=allowed_widget_codes,
            allowedFeatureCodes=profile.get("allowedFeatureCodes", [
                "DASHBOARD_VIEW",
                "DASHBOARD_PERSONALIZE",
                "ATOM_MAP_VIEW",
                "PRICE_DYNAMICS",
            ]),
            allowedActionCodes=profile.get("allowedActionCodes", [
                "MATERIAL_CREATE",
                "SUPPLIER_PRICE_UPLOAD",
                "MATERIAL_MODERATION_OPEN",
                "SOURCE_ERRORS_OPEN",
                "SOURCE_CREATE",
                "DOCUMENT_LIST_OPEN",
                "SOURCE_TASK_CREATE",
                "DASHBOARD_CONFIGURE",
            ]),
            favoriteModuleCodes=favorite_module_codes[:8],
            previewRoleCode=normalized_preview_role,
            effectiveRoleCode=effective_role_code,
            effectiveRoleLabel=ROLE_LABELS.get(effective_role_code, effective_role_code),
            dashboardLayout=dashboard_layout,
            userDashboardLayout=dashboard_layout,
            authMode="mock",
        )


class DashboardPermissionAdapter:
    @staticmethod
    def can_access_module(context: DashboardUserContext | dict[str, Any], module_code: str) -> bool:
        data = _context_dict(context)
        canonical_module_code = get_canonical_module_code(module_code)
        allowed_module_codes = {
            get_canonical_module_code(code) or code
            for code in data.get("allowedModuleCodes", [])
        }
        return canonical_module_code in allowed_module_codes

    @staticmethod
    def can_access_widget(context: DashboardUserContext | dict[str, Any], widget_code: str) -> bool:
        data = _context_dict(context)
        if widget_code in data.get("allowedWidgetCodes", []):
            return True
        widgets = (data.get("dashboardLayout") or {}).get("widgets") or []
        return any(f"{widget.get('type')}:{widget.get('title')}" == widget_code for widget in widgets)

    @staticmethod
    def can_use_feature(context: DashboardUserContext | dict[str, Any], feature_code: str) -> bool:
        data = _context_dict(context)
        return feature_code in data.get("allowedFeatureCodes", [])

    @staticmethod
    def can_see_planned_modules(context: DashboardUserContext | dict[str, Any]) -> bool:
        data = _context_dict(context)
        role_code = data.get("effectiveRoleCode") or data.get("roleCode")
        return data.get("authMode") in DEV_AUTH_MODES and role_code in ADMIN_ROLE_CODES

    @staticmethod
    def can_see_admin_widgets(context: DashboardUserContext | dict[str, Any]) -> bool:
        data = _context_dict(context)
        return (data.get("effectiveRoleCode") or data.get("roleCode")) in ADMIN_ROLE_CODES

    @staticmethod
    def can_edit_dashboard_layout(context: DashboardUserContext | dict[str, Any]) -> bool:
        return DashboardPermissionAdapter.can_use_feature(context, "DASHBOARD_PERSONALIZE")

    @staticmethod
    def can_use_action(context: DashboardUserContext | dict[str, Any], action_code: str) -> bool:
        data = _context_dict(context)
        return action_code in data.get("allowedActionCodes", [])

    @staticmethod
    def can_preview_dashboard_roles(context: DashboardUserContext | dict[str, Any]) -> bool:
        data = _context_dict(context)
        return data.get("roleCode") in ADMIN_ROLE_CODES


class DashboardRegionContextAdapter:
    @staticmethod
    def can_change_region(context: DashboardUserContext | dict[str, Any]) -> bool:
        data = _context_dict(context)
        return len(data.get("availableRegionCodes", [])) > 1 and data.get("roleCode") in ADMIN_ROLE_CODES


class DashboardWorkspaceAdapter:
    @staticmethod
    def can_change_workspace(context: DashboardUserContext | dict[str, Any]) -> bool:
        data = _context_dict(context)
        return data.get("roleCode") in ADMIN_ROLE_CODES


def get_dashboard_user_context(
    *,
    personalization: dict[str, Any],
    active_region: dict[str, Any],
    cards: list[dict[str, Any]],
    preview_role_code: str | None = None,
) -> DashboardUserContext:
    return DashboardUserContextAdapter.get_dashboard_user_context(
        personalization=personalization,
        active_region=active_region,
        cards=cards,
        preview_role_code=preview_role_code,
    )


def can_access_module(context: DashboardUserContext | dict[str, Any], module_code: str) -> bool:
    return DashboardPermissionAdapter.can_access_module(context, module_code)


def can_access_widget(context: DashboardUserContext | dict[str, Any], widget_code: str) -> bool:
    return DashboardPermissionAdapter.can_access_widget(context, widget_code)


def can_use_feature(context: DashboardUserContext | dict[str, Any], feature_code: str) -> bool:
    return DashboardPermissionAdapter.can_use_feature(context, feature_code)


def can_see_planned_modules(context: DashboardUserContext | dict[str, Any]) -> bool:
    return DashboardPermissionAdapter.can_see_planned_modules(context)


def can_see_admin_widgets(context: DashboardUserContext | dict[str, Any]) -> bool:
    return DashboardPermissionAdapter.can_see_admin_widgets(context)


def can_edit_dashboard_layout(context: DashboardUserContext | dict[str, Any]) -> bool:
    return DashboardPermissionAdapter.can_edit_dashboard_layout(context)


def can_use_action(context: DashboardUserContext | dict[str, Any], action_code: str) -> bool:
    return DashboardPermissionAdapter.can_use_action(context, action_code)


def can_preview_dashboard_roles(context: DashboardUserContext | dict[str, Any]) -> bool:
    return DashboardPermissionAdapter.can_preview_dashboard_roles(context)


def can_change_region(context: DashboardUserContext | dict[str, Any]) -> bool:
    return DashboardRegionContextAdapter.can_change_region(context)


def _context_dict(context: DashboardUserContext | dict[str, Any]) -> dict[str, Any]:
    if isinstance(context, DashboardUserContext):
        return asdict(context)
    return context


def _widget_layout(widget: dict[str, Any], position: int = 100) -> dict[str, Any]:
    config = widget_config_from_dict(widget, position=position).to_dict()
    config["moduleCode"] = config["canonicalModuleCode"]
    return config


def _normalize_preview_role(preview_role_code: str | None, real_role_code: str) -> str | None:
    if real_role_code not in ADMIN_ROLE_CODES:
        return None
    normalized = (preview_role_code or "").upper()
    return normalized if normalized in PREVIEW_ROLE_PROFILES else None
