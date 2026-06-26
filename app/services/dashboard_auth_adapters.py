from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.dashboard_module_registry import (
    get_canonical_module_code,
    get_dashboard_module_registry_item_by_number,
    normalize_dashboard_layout,
)


ADMIN_ROLE_CODES = {"ADMIN", "SUPER_ADMIN", "DEV_ADMIN"}
DEV_AUTH_MODES = {"mock", "dev"}


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
    availableRegionCodes: list[str] = field(default_factory=list)
    allowedModuleCodes: list[str] = field(default_factory=list)
    allowedWidgetCodes: list[str] = field(default_factory=list)
    allowedFeatureCodes: list[str] = field(default_factory=list)
    favoriteModuleCodes: list[str] = field(default_factory=list)
    dashboardLayout: dict[str, Any] = field(default_factory=dict)
    authMode: str = "mock"

    def to_template_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["display_name"] = self.displayName
        data["role"] = self.roleCode
        data["roleLabel"] = self.roleCode
        data["workspace"] = self.workspaceTitle
        data["allowedModules"] = self.allowedModuleCodes
        data["allowedWidgets"] = self.allowedWidgetCodes
        data["favoriteModules"] = self.favoriteModuleCodes
        data["is_mock"] = self.authMode == "mock"
        return data


class DashboardUserContextAdapter:
    @staticmethod
    def get_dashboard_user_context(
        *,
        personalization: dict[str, Any],
        active_region: dict[str, Any],
        cards: list[dict[str, Any]],
    ) -> DashboardUserContext:
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
            f"{widget['type']}:{widget['title']}"
            for widget in personalization["widgets"]
        ]
        active_region_code = active_region.get("code")

        dashboard_layout = normalize_dashboard_layout({
            "version": "mock-v1",
            "atomMap": {
                "maxVisibleModules": 6,
                "favoriteModulesOnly": True,
            },
            "widgets": [
                _widget_layout(widget)
                for widget in personalization["widgets"]
            ],
        })

        return DashboardUserContext(
            userId="dev-admin-mock",
            displayName="Администратор",
            roleCode="ADMIN",
            workspaceTitle=personalization["active_workspace"],
            workspaceType="ADMINISTRATION",
            activeRegionCode=active_region_code,
            activeRegionName=active_region.get("name"),
            availableRegionCodes=[active_region_code] if active_region_code else [],
            allowedModuleCodes=allowed_module_codes,
            allowedWidgetCodes=allowed_widget_codes,
            allowedFeatureCodes=[
                "DASHBOARD_VIEW",
                "DASHBOARD_PERSONALIZE",
                "ATOM_MAP_VIEW",
                "PRICE_DYNAMICS",
            ],
            favoriteModuleCodes=favorite_module_codes[:8],
            dashboardLayout=dashboard_layout,
            authMode="mock",
        )


class DashboardPermissionAdapter:
    @staticmethod
    def can_access_module(context: DashboardUserContext | dict[str, Any], module_code: str) -> bool:
        data = _context_dict(context)
        canonical_module_code = get_canonical_module_code(module_code)
        return canonical_module_code in data.get("allowedModuleCodes", [])

    @staticmethod
    def can_access_widget(context: DashboardUserContext | dict[str, Any], widget_code: str) -> bool:
        data = _context_dict(context)
        return widget_code in data.get("allowedWidgetCodes", [])

    @staticmethod
    def can_use_feature(context: DashboardUserContext | dict[str, Any], feature_code: str) -> bool:
        data = _context_dict(context)
        return feature_code in data.get("allowedFeatureCodes", [])

    @staticmethod
    def can_see_planned_modules(context: DashboardUserContext | dict[str, Any]) -> bool:
        data = _context_dict(context)
        return data.get("authMode") in DEV_AUTH_MODES and data.get("roleCode") in ADMIN_ROLE_CODES

    @staticmethod
    def can_see_admin_widgets(context: DashboardUserContext | dict[str, Any]) -> bool:
        data = _context_dict(context)
        return data.get("roleCode") in ADMIN_ROLE_CODES

    @staticmethod
    def can_edit_dashboard_layout(context: DashboardUserContext | dict[str, Any]) -> bool:
        return DashboardPermissionAdapter.can_use_feature(context, "DASHBOARD_PERSONALIZE")


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
) -> DashboardUserContext:
    return DashboardUserContextAdapter.get_dashboard_user_context(
        personalization=personalization,
        active_region=active_region,
        cards=cards,
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


def can_change_region(context: DashboardUserContext | dict[str, Any]) -> bool:
    return DashboardRegionContextAdapter.can_change_region(context)


def _context_dict(context: DashboardUserContext | dict[str, Any]) -> dict[str, Any]:
    if isinstance(context, DashboardUserContext):
        return asdict(context)
    return context


def _widget_layout(widget: dict[str, Any]) -> dict[str, Any]:
    module_number = widget.get("module_number")
    registry_item = get_dashboard_module_registry_item_by_number(module_number)
    module_code = registry_item.moduleCode if registry_item else None
    canonical_module_code = get_canonical_module_code(module_code)
    return {
        "type": widget["type"],
        "title": widget["title"],
        "size": widget["size"],
        "moduleNumberLegacy": module_number,
        "moduleCode": module_code,
        "canonicalModuleCode": canonical_module_code,
    }
