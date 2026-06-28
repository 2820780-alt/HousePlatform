from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.access_levels import AccessLevel
from app.core.access_scopes import AccessScope
from app.core.system_roles import LEGACY_ADMIN_ROLE_CODES
from app.services.dashboard_module_registry import ACTIVE_STATUS, get_canonical_module_code, get_dashboard_module_registry_item
from app.services.dashboard_widget_registry import DASHBOARD_WIDGET_REGISTRY, DashboardWidgetRegistryItem


WIDGET_TYPES: tuple[str, ...] = (
    "KPI",
    "CHART",
    "LIST",
    "STATUS",
    "TASK_QUEUE",
    "ALERTS",
    "ACTIONS",
    "ATOM_MAP",
    "SUMMARY",
)
WIDGET_SIZES: tuple[str, ...] = ("small", "medium", "large")
WIDGET_STATUSES: tuple[str, ...] = ("ACTIVE", "DRAFT", "PLANNED", "DISABLED", "DEPRECATED", "ARCHIVED")
VISIBLE_WIDGET_STATUSES = {"ACTIVE"}
PREVIEW_WIDGET_STATUSES = {"DRAFT", "PLANNED"}
HIDDEN_WIDGET_STATUSES = {"DISABLED", "DEPRECATED", "ARCHIVED"}

WIDGET_REGISTRY_LAYER = "module03_widget_registry"
WIDGET_REGISTRY_NOTE = (
    "WidgetRegistry is a Module 03 metadata and permission registry. "
    "Owning modules produce payload; Dashboard only renders payload; Module 08 may recommend widgets."
)
WIDGET_PREVIEW_ROLE_CODES = {"SUPER_ADMIN", "PLATFORM_ADMIN", *LEGACY_ADMIN_ROLE_CODES}


@dataclass(frozen=True)
class WidgetRegistryItemDefinition:
    id: str
    widgetCode: str
    title: str
    sourceModuleCode: str
    widgetType: str
    defaultSize: str
    status: str
    isSystem: bool
    order: int
    description: str | None = None
    canonicalModuleCode: str | None = None
    featureCode: str | None = None
    legacyModuleCode: str | None = None
    dataSource: str | None = None
    requiredAccessLevel: str | None = AccessLevel.VIEW
    requiredScope: str | None = AccessScope.LIMITED
    requiredActionCode: str | None = None
    allowedRoles: list[str] = field(default_factory=list)
    allowedCabinetTypes: list[str] = field(default_factory=list)
    allowedSizes: list[str] = field(default_factory=lambda: ["small", "medium", "large"])
    isMock: bool = False
    registryLayer: str = WIDGET_REGISTRY_LAYER
    compatibilityNote: str = WIDGET_REGISTRY_NOTE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_widget_registry() -> list[dict[str, Any]]:
    return [item.to_dict() for item in _widget_registry_definitions()]


def get_widget_registry_item(widget_code: str | None) -> WidgetRegistryItemDefinition | None:
    if not widget_code:
        return None
    return next((item for item in _widget_registry_definitions() if item.widgetCode == widget_code), None)


def get_available_widget_registry_items(user_profile: Any) -> list[dict[str, Any]]:
    data = _profile_dict(user_profile)
    allowed_modules = {
        get_canonical_module_code(code) or code
        for code in data.get("allowedModuleCodes") or []
    }
    allowed_widgets = set(data.get("allowedWidgetCodes") or [])
    allowed_features = set(data.get("allowedFeatureCodes") or [])
    role_code = data.get("effectiveRoleCode") or data.get("roleCode")
    cabinet_type = data.get("activeCabinetType")
    return [
        item.to_dict()
        for item in _widget_registry_definitions()
        if _is_widget_available_for_profile(
            item,
            allowed_module_codes=allowed_modules,
            allowed_widget_codes=allowed_widgets,
            allowed_feature_codes=allowed_features,
            role_code=role_code,
            cabinet_type=cabinet_type,
        )
    ]


def get_preview_widget_registry_items(user_profile: Any) -> list[dict[str, Any]]:
    data = _profile_dict(user_profile)
    if data.get("authMode") not in {"mock", "dev"}:
        return []
    if data.get("roleCode") not in WIDGET_PREVIEW_ROLE_CODES:
        return []
    return [
        item.to_dict()
        for item in _widget_registry_definitions()
        if item.status in PREVIEW_WIDGET_STATUSES | HIDDEN_WIDGET_STATUSES
    ]


def widget_registry_item_from_dashboard(item: DashboardWidgetRegistryItem, *, order: int) -> WidgetRegistryItemDefinition:
    canonical = get_canonical_module_code(item.sourceModuleCode) or item.sourceModuleCode
    status = _dashboard_status_to_widget_status(item.status)
    legacy_module_code = item.legacyModuleCode
    feature_code = item.featureCode
    if item.widgetCode == "price-dynamics":
        legacy_module_code = legacy_module_code or "MODULE_14_PRICE_HISTORY"
        feature_code = feature_code or "PRICE_DYNAMICS"
    return WidgetRegistryItemDefinition(
        id=item.widgetCode,
        widgetCode=item.widgetCode,
        title=item.title,
        description=item.description,
        sourceModuleCode=canonical,
        canonicalModuleCode=canonical,
        featureCode=feature_code,
        legacyModuleCode=legacy_module_code,
        widgetType=item.type if item.type in WIDGET_TYPES else "STATUS",
        dataSource=item.mockDataProvider,
        requiredAccessLevel=AccessLevel.VIEW,
        requiredScope=AccessScope.LIMITED,
        requiredActionCode=None,
        allowedRoles=[],
        allowedCabinetTypes=[],
        defaultSize=item.defaultSize if item.defaultSize in WIDGET_SIZES else "medium",
        allowedSizes=[size for size in item.allowedSizes if size in WIDGET_SIZES] or ["small", "medium", "large"],
        status=status,
        isSystem=True,
        isMock=bool(item.mockDataProvider or item.status == "mock_only"),
        order=order,
    )


def _widget_registry_definitions() -> tuple[WidgetRegistryItemDefinition, ...]:
    return tuple(
        widget_registry_item_from_dashboard(item, order=index * 10)
        for index, item in enumerate(DASHBOARD_WIDGET_REGISTRY, start=1)
    )


def _is_widget_available_for_profile(
    item: WidgetRegistryItemDefinition,
    *,
    allowed_module_codes: set[str],
    allowed_widget_codes: set[str],
    allowed_feature_codes: set[str],
    role_code: str | None,
    cabinet_type: str | None,
) -> bool:
    if item.status not in VISIBLE_WIDGET_STATUSES:
        return False
    if allowed_widget_codes and item.widgetCode not in allowed_widget_codes:
        return False
    if item.sourceModuleCode not in allowed_module_codes:
        return False
    if item.featureCode and allowed_feature_codes and item.featureCode not in allowed_feature_codes:
        return False
    if item.allowedRoles and role_code not in item.allowedRoles:
        return False
    if item.allowedCabinetTypes and cabinet_type not in item.allowedCabinetTypes:
        return False
    module_item = get_dashboard_module_registry_item(item.sourceModuleCode)
    return module_item is None or module_item.status == ACTIVE_STATUS


def _dashboard_status_to_widget_status(status: str) -> str:
    return {
        "available": "ACTIVE",
        "mock_only": "ACTIVE",
        "planned": "PLANNED",
        "requires_module": "PLANNED",
        "requires_permission": "DISABLED",
        "disabled": "DISABLED",
    }.get(status, "DISABLED")


def _profile_dict(user_profile: Any) -> dict[str, Any]:
    if user_profile is None:
        return {}
    if hasattr(user_profile, "to_template_dict"):
        return user_profile.to_template_dict()
    if hasattr(user_profile, "__dict__") and not isinstance(user_profile, dict):
        return dict(user_profile.__dict__)
    if isinstance(user_profile, dict):
        return user_profile
    return {}
