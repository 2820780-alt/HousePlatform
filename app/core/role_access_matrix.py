from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.core.access_levels import AccessLevel
from app.core.access_scopes import AccessScope


ACTIVE_STARTER_MODULE_CODES: tuple[str, ...] = (
    "MODULE_01_MATERIAL_HUB",
    "MODULE_02_KNOWLEDGE_BASE",
    "MODULE_03_USERS_ROLES",
    "MODULE_04_WORKS_COSTS",
    "MODULE_05_ESTIMATES",
    "MODULE_06_ESTIMATE_AUDIT",
    "MODULE_08_PROCUREMENT",
    "MODULE_09_TENDERS",
    "MODULE_10_MARKETPLACE",
    "MODULE_11_ANALYTICS",
    "MODULE_12_AI_ASSISTANT",
    "MODULE_13_AUDIT",
)


@dataclass(frozen=True)
class RoleModuleAccessRule:
    roleCode: str
    moduleCode: str
    accessLevel: str
    accessScope: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoleFeatureAccessRule:
    roleCode: str
    moduleCode: str
    featureCode: str
    accessLevel: str
    accessScope: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SUPER_ADMIN_MODULE_ACCESS: tuple[RoleModuleAccessRule, ...] = tuple(
    RoleModuleAccessRule("SUPER_ADMIN", module_code, AccessLevel.ADMIN, AccessScope.GLOBAL)
    for module_code in ACTIVE_STARTER_MODULE_CODES
)

STARTER_ROLE_MODULE_ACCESS: tuple[RoleModuleAccessRule, ...] = (
    *SUPER_ADMIN_MODULE_ACCESS,
    RoleModuleAccessRule("PLATFORM_ADMIN", "MODULE_01_MATERIAL_HUB", AccessLevel.ADMIN, AccessScope.GLOBAL),
    RoleModuleAccessRule("PLATFORM_ADMIN", "MODULE_02_KNOWLEDGE_BASE", AccessLevel.ADMIN, AccessScope.GLOBAL),
    RoleModuleAccessRule("PLATFORM_ADMIN", "MODULE_03_USERS_ROLES", AccessLevel.EDIT, AccessScope.GLOBAL),
    RoleModuleAccessRule("PLATFORM_ADMIN", "MODULE_11_ANALYTICS", AccessLevel.ADMIN, AccessScope.GLOBAL),
    RoleModuleAccessRule("MODERATOR", "MODULE_01_MATERIAL_HUB", AccessLevel.APPROVE, AccessScope.GLOBAL),
    RoleModuleAccessRule("MODERATOR", "MODULE_02_KNOWLEDGE_BASE", AccessLevel.APPROVE, AccessScope.GLOBAL),
    RoleModuleAccessRule("MODERATOR", "MODULE_03_USERS_ROLES", AccessLevel.NO_ACCESS, AccessScope.NONE),
    RoleModuleAccessRule("KNOWLEDGE_MANAGER", "MODULE_02_KNOWLEDGE_BASE", AccessLevel.ADMIN, AccessScope.GLOBAL),
    RoleModuleAccessRule("KNOWLEDGE_MANAGER", "MODULE_01_MATERIAL_HUB", AccessLevel.VIEW, AccessScope.GLOBAL),
    RoleModuleAccessRule("KNOWLEDGE_MANAGER", "MODULE_11_ANALYTICS", AccessLevel.VIEW, AccessScope.GLOBAL),
    RoleModuleAccessRule("ESTIMATOR", "MODULE_05_ESTIMATES", AccessLevel.ADMIN, AccessScope.OWN),
    RoleModuleAccessRule("ESTIMATOR", "MODULE_06_ESTIMATE_AUDIT", AccessLevel.APPROVE, AccessScope.OWN),
    RoleModuleAccessRule("ESTIMATOR", "MODULE_01_MATERIAL_HUB", AccessLevel.VIEW, AccessScope.LIMITED),
    RoleModuleAccessRule("ESTIMATOR", "MODULE_02_KNOWLEDGE_BASE", AccessLevel.VIEW, AccessScope.LIMITED),
    RoleModuleAccessRule("ESTIMATOR", "MODULE_11_ANALYTICS", AccessLevel.VIEW, AccessScope.OWN),
    RoleModuleAccessRule("ENGINEER_DESIGNER", "MODULE_02_KNOWLEDGE_BASE", AccessLevel.EDIT, AccessScope.GLOBAL),
    RoleModuleAccessRule("ENGINEER_DESIGNER", "MODULE_04_WORKS_COSTS", AccessLevel.VIEW, AccessScope.GLOBAL),
    RoleModuleAccessRule("ENGINEER_DESIGNER", "MODULE_11_ANALYTICS", AccessLevel.VIEW, AccessScope.OWN),
    RoleModuleAccessRule("SUPPLIER", "MODULE_01_MATERIAL_HUB", AccessLevel.VIEW, AccessScope.LIMITED),
    RoleModuleAccessRule("SUPPLIER", "MODULE_11_ANALYTICS", AccessLevel.VIEW, AccessScope.OWN),
    RoleModuleAccessRule("CONTRACTOR", "MODULE_04_WORKS_COSTS", AccessLevel.ADMIN, AccessScope.OWN),
    RoleModuleAccessRule("CONTRACTOR", "MODULE_11_ANALYTICS", AccessLevel.VIEW, AccessScope.OWN),
    RoleModuleAccessRule("CUSTOMER", "MODULE_05_ESTIMATES", AccessLevel.VIEW, AccessScope.OWN),
    RoleModuleAccessRule("CUSTOMER", "MODULE_08_PROCUREMENT", AccessLevel.VIEW, AccessScope.OWN),
    RoleModuleAccessRule("CUSTOMER", "MODULE_02_KNOWLEDGE_BASE", AccessLevel.VIEW, AccessScope.LIMITED),
    RoleModuleAccessRule("ANALYST", "MODULE_11_ANALYTICS", AccessLevel.ADMIN, AccessScope.GLOBAL),
    RoleModuleAccessRule("ANALYST", "MODULE_01_MATERIAL_HUB", AccessLevel.VIEW, AccessScope.GLOBAL),
    RoleModuleAccessRule("ANALYST", "MODULE_02_KNOWLEDGE_BASE", AccessLevel.VIEW, AccessScope.GLOBAL),
    RoleModuleAccessRule("VIEWER", "MODULE_01_MATERIAL_HUB", AccessLevel.VIEW, AccessScope.LIMITED),
    RoleModuleAccessRule("VIEWER", "MODULE_02_KNOWLEDGE_BASE", AccessLevel.VIEW, AccessScope.LIMITED),
    RoleModuleAccessRule("VIEWER", "MODULE_11_ANALYTICS", AccessLevel.VIEW, AccessScope.LIMITED),
)

STARTER_ROLE_FEATURE_ACCESS: tuple[RoleFeatureAccessRule, ...] = (
    RoleFeatureAccessRule("SUPER_ADMIN", "MODULE_11_ANALYTICS", "PRICE_DYNAMICS", AccessLevel.ADMIN, AccessScope.GLOBAL),
    RoleFeatureAccessRule("PLATFORM_ADMIN", "MODULE_11_ANALYTICS", "PRICE_DYNAMICS", AccessLevel.ADMIN, AccessScope.GLOBAL),
    RoleFeatureAccessRule("MODERATOR", "MODULE_11_ANALYTICS", "PRICE_DYNAMICS", AccessLevel.VIEW, AccessScope.GLOBAL),
    RoleFeatureAccessRule("ESTIMATOR", "MODULE_11_ANALYTICS", "PRICE_DYNAMICS", AccessLevel.VIEW, AccessScope.OWN),
    RoleFeatureAccessRule("SUPPLIER", "MODULE_11_ANALYTICS", "PRICE_DYNAMICS", AccessLevel.VIEW, AccessScope.OWN),
    RoleFeatureAccessRule("CONTRACTOR", "MODULE_11_ANALYTICS", "PRICE_DYNAMICS", AccessLevel.VIEW, AccessScope.OWN),
    RoleFeatureAccessRule("ANALYST", "MODULE_11_ANALYTICS", "PRICE_DYNAMICS", AccessLevel.ADMIN, AccessScope.GLOBAL),
    RoleFeatureAccessRule("VIEWER", "MODULE_11_ANALYTICS", "PRICE_DYNAMICS", AccessLevel.VIEW, AccessScope.LIMITED),
)


def get_starter_role_module_access() -> list[dict[str, Any]]:
    return [rule.to_dict() for rule in STARTER_ROLE_MODULE_ACCESS]


def get_starter_role_feature_access() -> list[dict[str, Any]]:
    return [rule.to_dict() for rule in STARTER_ROLE_FEATURE_ACCESS]
