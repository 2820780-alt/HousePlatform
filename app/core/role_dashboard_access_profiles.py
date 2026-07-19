from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.role_access_matrix import ACTIVE_STARTER_MODULE_CODES, STARTER_ROLE_FEATURE_ACCESS, STARTER_ROLE_MODULE_ACCESS
from app.core.system_roles import SYSTEM_ROLE_CODES


SOURCE_MODULE_CODE = "MODULE_03_USERS_ROLES"
DEFAULT_DASHBOARD_FEATURES: tuple[str, ...] = (
    "DASHBOARD_VIEW",
    "DASHBOARD_PERSONALIZE",
    "ATOM_MAP_VIEW",
)


DEPRECATED_DEFAULT_QUICK_ACTION_CODES_NOTE = (
    "Deprecated compatibility field; roles grant permissions but never create quick action shortcuts."
)


MODULE_03_DASHBOARD_WIDGET_CODES: tuple[str, ...] = (
    "MODULE_03_USERS_SUMMARY_WIDGET",
    "MODULE_03_MODERATION_QUEUE_WIDGET",
    "MODULE_03_AUDIT_LOG_WIDGET",
    "MODULE_03_MODULES_STATUS_WIDGET",
    "MODULE_03_WIDGETS_STATUS_WIDGET",
)

MODULE_01_OPERATIONAL_WIDGET_CODES: tuple[str, ...] = (
    "MODULE_01_MATERIALS_REQUIRING_ATTENTION_WIDGET",
    "MODULE_01_MATERIAL_PRICE_RELEVANCE_WIDGET",
    "MODULE_01_DOCUMENTS_REQUIRING_REVIEW_WIDGET",
    "MODULE_01_ANALYZER_STATUS_WIDGET",
    "MODULE_01_WORK_COST_OFFERS_REQUIRING_ATTENTION_WIDGET",
)

@dataclass(frozen=True)
class RoleDashboardAccessProfileDefinition:
    roleCode: str
    allowedModuleCodes: tuple[str, ...]
    defaultWidgetCodes: tuple[str, ...] = ()
    allowedWidgetCodes: tuple[str, ...] = ()
    defaultQuickActionCodes: tuple[str, ...] = field(
        default_factory=tuple,
        metadata={"deprecated": DEPRECATED_DEFAULT_QUICK_ACTION_CODES_NOTE},
    )
    hiddenWidgetCodes: tuple[str, ...] = ()
    allowedFeatureCodes: tuple[str, ...] = DEFAULT_DASHBOARD_FEATURES
    defaultLayoutCode: str | None = None
    sourceModuleCode: str = SOURCE_MODULE_CODE
    isSystem: bool = True
    isActive: bool = True
    description: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _role_modules(role_code: str) -> tuple[str, ...]:
    if role_code == "SUPER_ADMIN":
        return ACTIVE_STARTER_MODULE_CODES
    modules = [
        rule.moduleCode
        for rule in STARTER_ROLE_MODULE_ACCESS
        if rule.roleCode == role_code and rule.accessLevel != "NO_ACCESS"
    ]
    return tuple(dict.fromkeys(modules))


def _role_features(role_code: str) -> tuple[str, ...]:
    features = list(DEFAULT_DASHBOARD_FEATURES)
    features.extend(
        rule.featureCode
        for rule in STARTER_ROLE_FEATURE_ACCESS
        if rule.roleCode == role_code
    )
    return tuple(dict.fromkeys(features))


ROLE_DASHBOARD_ACCESS_PROFILES: tuple[RoleDashboardAccessProfileDefinition, ...] = (
    RoleDashboardAccessProfileDefinition(
        roleCode="SUPER_ADMIN",
        allowedModuleCodes=_role_modules("SUPER_ADMIN"),
        allowedFeatureCodes=(*_role_features("SUPER_ADMIN"), "DASHBOARD_ROLE_PREVIEW", "DASHBOARD_REGISTRY_ADMIN"),
        defaultWidgetCodes=("materials-kpi", "classification-queue", "price-dynamics", "source-health", "system-alerts", "atom-map", *MODULE_03_DASHBOARD_WIDGET_CODES),
        allowedWidgetCodes=("materials-kpi", "classification-queue", "price-dynamics", "source-health", "system-alerts", "atom-map", *MODULE_03_DASHBOARD_WIDGET_CODES, *MODULE_01_OPERATIONAL_WIDGET_CODES),
        defaultQuickActionCodes=(),
        defaultLayoutCode="ADMIN_DASHBOARD_DEFAULT",
        description="Owner-level profile for viewing and configuring the existing Dashboard shell.",
        settings={
            "workspaceType": "ADMINISTRATION",
            "activeCabinetType": "ADMIN",
            "favoriteModuleCodes": ("MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS", "MODULE_03_USERS_ROLES"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="PLATFORM_ADMIN",
        allowedModuleCodes=_role_modules("PLATFORM_ADMIN"),
        allowedFeatureCodes=(*_role_features("PLATFORM_ADMIN"), "DASHBOARD_ROLE_PREVIEW", "DASHBOARD_REGISTRY_ADMIN"),
        defaultWidgetCodes=("materials-kpi", "classification-queue", "price-dynamics", "source-health", "system-alerts", "atom-map", *MODULE_03_DASHBOARD_WIDGET_CODES),
        allowedWidgetCodes=("materials-kpi", "classification-queue", "price-dynamics", "source-health", "system-alerts", "atom-map", *MODULE_03_DASHBOARD_WIDGET_CODES, *MODULE_01_OPERATIONAL_WIDGET_CODES),
        defaultQuickActionCodes=(),
        defaultLayoutCode="ADMIN_DASHBOARD_DEFAULT",
        description="Platform administration profile without Super Admin ownership-level operations.",
        settings={
            "workspaceType": "ADMINISTRATION",
            "activeCabinetType": "ADMIN",
            "favoriteModuleCodes": ("MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS", "MODULE_03_USERS_ROLES"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="MODERATOR",
        allowedModuleCodes=_role_modules("MODERATOR"),
        allowedFeatureCodes=_role_features("MODERATOR"),
        defaultWidgetCodes=("classification-queue", "materials-kpi", "source-health"),
        defaultQuickActionCodes=(),
        defaultLayoutCode="MODERATION_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "MODERATION",
            "activeCabinetType": "MODERATOR",
            "favoriteModuleCodes": ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="KNOWLEDGE_MANAGER",
        allowedModuleCodes=_role_modules("KNOWLEDGE_MANAGER"),
        allowedFeatureCodes=_role_features("KNOWLEDGE_MANAGER"),
        defaultWidgetCodes=("materials-kpi", "classification-queue", "price-dynamics"),
        defaultQuickActionCodes=(),
        defaultLayoutCode="KNOWLEDGE_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "KNOWLEDGE",
            "activeCabinetType": "KNOWLEDGE_MANAGER",
            "favoriteModuleCodes": ("MODULE_02_KNOWLEDGE_BASE", "MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="ESTIMATOR",
        allowedModuleCodes=_role_modules("ESTIMATOR"),
        allowedFeatureCodes=_role_features("ESTIMATOR"),
        defaultWidgetCodes=("price-dynamics", "materials-kpi", "atom-map"),
        defaultQuickActionCodes=(),
        defaultLayoutCode="ESTIMATOR_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "ESTIMATES",
            "activeCabinetType": "ESTIMATOR",
            "favoriteModuleCodes": ("MODULE_05_ESTIMATES", "MODULE_06_ESTIMATE_AUDIT", "MODULE_01_MATERIAL_HUB"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="ENGINEER_DESIGNER",
        allowedModuleCodes=_role_modules("ENGINEER_DESIGNER"),
        allowedFeatureCodes=_role_features("ENGINEER_DESIGNER"),
        defaultWidgetCodes=("materials-kpi", "price-dynamics"),
        defaultQuickActionCodes=(),
        defaultLayoutCode="ENGINEER_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "ENGINEERING",
            "activeCabinetType": "ENGINEER_DESIGNER",
            "favoriteModuleCodes": ("MODULE_02_KNOWLEDGE_BASE", "MODULE_04_WORKS_COSTS", "MODULE_11_ANALYTICS"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="SUPPLIER",
        allowedModuleCodes=("MODULE_01_MATERIAL_HUB", "MODULE_09_PROCUREMENT", "MODULE_10_MARKETPLACE"),
        allowedFeatureCodes=DEFAULT_DASHBOARD_FEATURES,
        defaultWidgetCodes=("materials-kpi", "atom-map"),
        allowedWidgetCodes=("materials-kpi", "atom-map", "MODULE_01_WORK_COST_OFFERS_REQUIRING_ATTENTION_WIDGET"),
        defaultQuickActionCodes=(),
        defaultLayoutCode="SUPPLIER_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "SUPPLIER",
            "activeCabinetType": "SUPPLIER",
            "favoriteModuleCodes": ("MODULE_01_MATERIAL_HUB", "MODULE_09_PROCUREMENT", "MODULE_10_MARKETPLACE"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="CONTRACTOR",
        allowedModuleCodes=_role_modules("CONTRACTOR"),
        allowedFeatureCodes=_role_features("CONTRACTOR"),
        defaultWidgetCodes=("price-dynamics", "atom-map"),
        allowedWidgetCodes=("price-dynamics", "atom-map", "MODULE_01_WORK_COST_OFFERS_REQUIRING_ATTENTION_WIDGET"),
        defaultQuickActionCodes=(),
        defaultLayoutCode="CONTRACTOR_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "CONTRACTOR",
            "activeCabinetType": "CONTRACTOR",
            "favoriteModuleCodes": ("MODULE_04_WORKS_COSTS", "MODULE_11_ANALYTICS"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="CUSTOMER",
        allowedModuleCodes=("MODULE_05_ESTIMATES", "MODULE_07_DIGITAL_HOUSE", "MODULE_09_PROCUREMENT", "MODULE_10_MARKETPLACE"),
        allowedFeatureCodes=DEFAULT_DASHBOARD_FEATURES,
        defaultWidgetCodes=("atom-map",),
        defaultQuickActionCodes=(),
        defaultLayoutCode="CUSTOMER_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "CUSTOMER",
            "activeCabinetType": "CUSTOMER",
            "favoriteModuleCodes": ("MODULE_07_DIGITAL_HOUSE", "MODULE_05_ESTIMATES", "MODULE_09_PROCUREMENT"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="ANALYST",
        allowedModuleCodes=("MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS", "MODULE_13_AUDIT"),
        allowedFeatureCodes=(*_role_features("ANALYST"),),
        defaultWidgetCodes=("price-dynamics", "materials-kpi", "source-health", "atom-map"),
        defaultQuickActionCodes=(),
        defaultLayoutCode="ANALYST_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "ANALYTICS",
            "activeCabinetType": "ANALYST",
            "favoriteModuleCodes": ("MODULE_11_ANALYTICS", "MODULE_01_MATERIAL_HUB", "MODULE_13_AUDIT"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="VIEWER",
        allowedModuleCodes=_role_modules("VIEWER"),
        allowedFeatureCodes=("DASHBOARD_VIEW", "ATOM_MAP_VIEW", "PRICE_DYNAMICS"),
        defaultWidgetCodes=("materials-kpi", "price-dynamics"),
        defaultQuickActionCodes=(),
        defaultLayoutCode="VIEWER_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "VIEW_ONLY",
            "activeCabinetType": "VIEWER",
            "favoriteModuleCodes": ("MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"),
        },
    ),
)


def get_role_dashboard_access_profile_definitions() -> list[dict[str, Any]]:
    return [profile.to_dict() for profile in ROLE_DASHBOARD_ACCESS_PROFILES]


def get_role_dashboard_access_profile_definition(role_code: str | None) -> dict[str, Any] | None:
    if not role_code:
        return None
    normalized = role_code.upper()
    for profile in ROLE_DASHBOARD_ACCESS_PROFILES:
        if profile.roleCode == normalized:
            return profile.to_dict()
    return None


def missing_role_dashboard_profile_codes() -> set[str]:
    configured = {profile.roleCode for profile in ROLE_DASHBOARD_ACCESS_PROFILES}
    return set(SYSTEM_ROLE_CODES) - configured
