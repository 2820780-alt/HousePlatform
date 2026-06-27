from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SYSTEM_ROLE_CODES: tuple[str, ...] = (
    "SUPER_ADMIN",
    "PLATFORM_ADMIN",
    "MODERATOR",
    "KNOWLEDGE_MANAGER",
    "ESTIMATOR",
    "ENGINEER_DESIGNER",
    "SUPPLIER",
    "CONTRACTOR",
    "CUSTOMER",
    "ANALYST",
    "VIEWER",
)

LEGACY_ADMIN_ROLE_CODES: tuple[str, ...] = (
    "ADMIN",
    "MANAGER",
    "ENGINEER",
    "DEV_ADMIN",
)


@dataclass(frozen=True)
class SystemRoleDefinition:
    roleCode: str
    name: str
    description: str
    isSystem: bool = True
    canDelete: bool = False
    canRenameCode: bool = False
    canDisable: bool = False
    canExtendPermissions: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SYSTEM_ROLE_DEFINITIONS: tuple[SystemRoleDefinition, ...] = (
    SystemRoleDefinition("SUPER_ADMIN", "Super Admin", "Full platform owner role with all administrative capabilities."),
    SystemRoleDefinition("PLATFORM_ADMIN", "Platform Admin", "Platform administration without ownership-level safeguards."),
    SystemRoleDefinition("MODERATOR", "Moderator", "Data moderation, classification review and quality control workflows."),
    SystemRoleDefinition("KNOWLEDGE_MANAGER", "Knowledge Manager", "Technology, knowledge base and reference-data curation."),
    SystemRoleDefinition("ESTIMATOR", "Estimator", "Estimate preparation, review and estimate-related workflows."),
    SystemRoleDefinition("ENGINEER_DESIGNER", "Engineer Designer", "Engineering, design and technical validation workflows."),
    SystemRoleDefinition("SUPPLIER", "Supplier", "Supplier cabinet, offers, prices and source data workflows."),
    SystemRoleDefinition("CONTRACTOR", "Contractor", "Contractor cabinet, works and project execution workflows."),
    SystemRoleDefinition("CUSTOMER", "Customer", "Customer cabinet, project object and procurement visibility."),
    SystemRoleDefinition("ANALYST", "Analyst", "Analytics and reporting workflows."),
    SystemRoleDefinition("VIEWER", "Viewer", "Read-only access to explicitly allowed platform areas."),
)


def get_system_role_definitions() -> list[dict[str, Any]]:
    return [role.to_dict() for role in SYSTEM_ROLE_DEFINITIONS]


def get_system_role_codes() -> tuple[str, ...]:
    return SYSTEM_ROLE_CODES


def is_system_role_code(role_code: str | None) -> bool:
    return bool(role_code) and role_code in SYSTEM_ROLE_CODES


def can_delete_role_code(role_code: str | None) -> bool:
    return not is_system_role_code(role_code)


def can_rename_role_code(role_code: str | None) -> bool:
    return not is_system_role_code(role_code)
