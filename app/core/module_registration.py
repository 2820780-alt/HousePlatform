from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.access_levels import is_valid_access_level
from app.core.access_scopes import is_valid_access_scope
from app.core.system_roles import is_system_role_code


LEGACY_OR_CONFLICTING_MODULE_CODES: dict[str, str] = {
    "MODULE_07_DIGITAL_OBJECT": "MODULE_07_DIGITAL_HOUSE",
    "MODULE_14_PRICE_HISTORY": "MODULE_11_ANALYTICS",
    "MODULE_14_CONSTRUCTOR_LITE": "MODULE_19_CONSTRUCTOR_LITE",
    "MODULE_15_CONSTRUCTION_GROUPS": "MODULE_01_MATERIAL_HUB",
    "MODULE_16_QUALITY_CONTROL": "MODULE_18_QUALITY_CONTROL",
}


@dataclass(frozen=True)
class DefaultModulePermission:
    role: str
    accessLevel: str
    scope: str

    def __post_init__(self) -> None:
        if not is_system_role_code(self.role):
            raise ValueError(f"Unknown system role: {self.role}")
        if not is_valid_access_level(self.accessLevel):
            raise ValueError(f"Invalid access level: {self.accessLevel}")
        if not is_valid_access_scope(self.scope):
            raise ValueError(f"Invalid access scope: {self.scope}")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class NewModuleRegistration:
    moduleCode: str
    title: str
    defaultPermissions: tuple[DefaultModulePermission, ...]
    availableActions: tuple[str, ...]
    dashboardWidgets: tuple[str, ...] = ()
    ownerScopeRules: dict[str, Any] = field(default_factory=dict)
    canonicalModuleCode: str | None = None
    featureCodes: tuple[str, ...] = ()
    status: str = "PLANNED"

    def __post_init__(self) -> None:
        validate_module_registration(self)

    def to_registry_metadata(self) -> dict[str, Any]:
        return {
            "moduleCode": self.moduleCode,
            "canonicalModuleCode": self.canonicalModuleCode or self.moduleCode,
            "defaultPermissions": [permission.to_dict() for permission in self.defaultPermissions],
            "availableActions": list(self.availableActions),
            "dashboardWidgets": list(self.dashboardWidgets),
            "ownerScopeRules": dict(self.ownerScopeRules),
            "featureCodes": list(self.featureCodes),
            "status": self.status,
        }


def validate_module_registration(registration: NewModuleRegistration) -> None:
    if not registration.moduleCode.startswith("MODULE_"):
        raise ValueError("moduleCode must be a stable MODULE_* code.")
    if registration.moduleCode in LEGACY_OR_CONFLICTING_MODULE_CODES:
        canonical = LEGACY_OR_CONFLICTING_MODULE_CODES[registration.moduleCode]
        raise ValueError(f"{registration.moduleCode} is legacy or conflicting. Use {canonical}.")
    if not registration.title.strip():
        raise ValueError("title is required.")
    if not registration.defaultPermissions:
        raise ValueError("defaultPermissions must declare at least one rule.")
    if len(set(registration.availableActions)) != len(registration.availableActions):
        raise ValueError("availableActions must not contain duplicates.")
    if len(set(registration.dashboardWidgets)) != len(registration.dashboardWidgets):
        raise ValueError("dashboardWidgets must not contain duplicates.")


def registration_to_module_access_defaults(registration: NewModuleRegistration) -> list[dict[str, str]]:
    return [
        {
            "roleCode": permission.role,
            "moduleCode": registration.canonicalModuleCode or registration.moduleCode,
            "accessLevel": permission.accessLevel,
            "accessScope": permission.scope,
        }
        for permission in registration.defaultPermissions
    ]


def registration_to_action_defaults(registration: NewModuleRegistration) -> list[dict[str, str]]:
    return [
        {
            "moduleCode": registration.canonicalModuleCode or registration.moduleCode,
            "actionCode": action_code,
        }
        for action_code in registration.availableActions
    ]


def registration_to_widget_defaults(registration: NewModuleRegistration) -> list[dict[str, str]]:
    return [
        {
            "widgetCode": widget_code,
            "sourceModuleCode": registration.canonicalModuleCode or registration.moduleCode,
        }
        for widget_code in registration.dashboardWidgets
    ]


QUALITY_CONTROL_MODULE_REGISTRATION = NewModuleRegistration(
    moduleCode="MODULE_18_QUALITY_CONTROL",
    canonicalModuleCode="MODULE_18_QUALITY_CONTROL",
    title="Quality Control",
    status="PLANNED",
    defaultPermissions=(
        DefaultModulePermission("SUPER_ADMIN", "ADMIN", "GLOBAL"),
        DefaultModulePermission("PLATFORM_ADMIN", "VIEW", "GLOBAL"),
        DefaultModulePermission("MODERATOR", "APPROVE", "GLOBAL"),
        DefaultModulePermission("CONTRACTOR", "VIEW", "OWN"),
        DefaultModulePermission("CUSTOMER", "VIEW", "OWN"),
    ),
    availableActions=("VIEW", "CREATE_ISSUE", "APPROVE_CHECK", "EXPORT_REPORT"),
    dashboardWidgets=("QUALITY_CONTROL_ISSUES",),
    ownerScopeRules={
        "ownerField": "workspaceId",
        "regionField": "service_region_id",
        "notes": "Module-owned payloads will define concrete object/project visibility.",
    },
    featureCodes=("QUALITY_ISSUES", "CHECKLISTS", "ACCEPTANCE_REPORTS"),
)


DEFAULT_MODULE_REGISTRATIONS: tuple[NewModuleRegistration, ...] = (
    QUALITY_CONTROL_MODULE_REGISTRATION,
)
