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


@dataclass(frozen=True)
class RoleDashboardAccessProfileDefinition:
    roleCode: str
    allowedModuleCodes: tuple[str, ...]
    defaultWidgetCodes: tuple[str, ...] = ()
    defaultQuickActionCodes: tuple[str, ...] = ()
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
        defaultWidgetCodes=("materials-kpi", "classification-queue", "price-dynamics", "source-health", "system-alerts", "atom-map"),
        defaultQuickActionCodes=(
            "MATERIAL_CREATE",
            "SUPPLIER_PRICE_UPLOAD",
            "SOURCE_TASK_CREATE",
            "MATERIAL_MODERATION_OPEN",
            "SOURCE_ERRORS_OPEN",
            "SOURCE_CREATE",
            "DOCUMENT_LIST_OPEN",
            "DASHBOARD_CONFIGURE",
        ),
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
        defaultWidgetCodes=("materials-kpi", "classification-queue", "price-dynamics", "source-health", "system-alerts", "atom-map"),
        defaultQuickActionCodes=(
            "MATERIAL_CREATE",
            "SUPPLIER_PRICE_UPLOAD",
            "SOURCE_TASK_CREATE",
            "MATERIAL_MODERATION_OPEN",
            "SOURCE_ERRORS_OPEN",
            "SOURCE_CREATE",
            "DOCUMENT_LIST_OPEN",
            "DASHBOARD_CONFIGURE",
        ),
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
        defaultQuickActionCodes=("MATERIAL_MODERATION_OPEN", "SOURCE_ERRORS_OPEN", "DASHBOARD_CONFIGURE"),
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
        defaultQuickActionCodes=("MATERIAL_CREATE", "DOCUMENT_LIST_OPEN", "DASHBOARD_CONFIGURE"),
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
        defaultQuickActionCodes=("DASHBOARD_CONFIGURE",),
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
        defaultQuickActionCodes=("DOCUMENT_LIST_OPEN", "DASHBOARD_CONFIGURE"),
        defaultLayoutCode="ENGINEER_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "ENGINEERING",
            "activeCabinetType": "ENGINEER_DESIGNER",
            "favoriteModuleCodes": ("MODULE_02_KNOWLEDGE_BASE", "MODULE_04_WORKS_COSTS", "MODULE_11_ANALYTICS"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="SUPPLIER",
        allowedModuleCodes=("MODULE_01_MATERIAL_HUB", "MODULE_08_PROCUREMENT", "MODULE_09_TENDERS", "MODULE_10_MARKETPLACE"),
        allowedFeatureCodes=DEFAULT_DASHBOARD_FEATURES,
        defaultWidgetCodes=("materials-kpi", "atom-map"),
        defaultQuickActionCodes=("SUPPLIER_PRICE_UPLOAD", "DASHBOARD_CONFIGURE"),
        defaultLayoutCode="SUPPLIER_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "SUPPLIER",
            "activeCabinetType": "SUPPLIER",
            "favoriteModuleCodes": ("MODULE_01_MATERIAL_HUB", "MODULE_08_PROCUREMENT", "MODULE_09_TENDERS"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="CONTRACTOR",
        allowedModuleCodes=_role_modules("CONTRACTOR"),
        allowedFeatureCodes=_role_features("CONTRACTOR"),
        defaultWidgetCodes=("price-dynamics", "atom-map"),
        defaultQuickActionCodes=("DASHBOARD_CONFIGURE",),
        defaultLayoutCode="CONTRACTOR_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "CONTRACTOR",
            "activeCabinetType": "CONTRACTOR",
            "favoriteModuleCodes": ("MODULE_04_WORKS_COSTS", "MODULE_11_ANALYTICS"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="CUSTOMER",
        allowedModuleCodes=("MODULE_05_ESTIMATES", "MODULE_07_DIGITAL_HOUSE", "MODULE_08_PROCUREMENT", "MODULE_10_MARKETPLACE"),
        allowedFeatureCodes=DEFAULT_DASHBOARD_FEATURES,
        defaultWidgetCodes=("atom-map",),
        defaultQuickActionCodes=("DASHBOARD_CONFIGURE",),
        defaultLayoutCode="CUSTOMER_DASHBOARD_DEFAULT",
        settings={
            "workspaceType": "CUSTOMER",
            "activeCabinetType": "CUSTOMER",
            "favoriteModuleCodes": ("MODULE_07_DIGITAL_HOUSE", "MODULE_05_ESTIMATES", "MODULE_08_PROCUREMENT"),
        },
    ),
    RoleDashboardAccessProfileDefinition(
        roleCode="ANALYST",
        allowedModuleCodes=("MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS", "MODULE_13_AUDIT"),
        allowedFeatureCodes=(*_role_features("ANALYST"),),
        defaultWidgetCodes=("price-dynamics", "materials-kpi", "source-health", "atom-map"),
        defaultQuickActionCodes=("SOURCE_ERRORS_OPEN", "DOCUMENT_LIST_OPEN", "DASHBOARD_CONFIGURE"),
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
