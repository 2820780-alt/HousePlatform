from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.access_levels import AccessLevel
from app.core.access_scopes import AccessScope
from app.core.system_roles import LEGACY_ADMIN_ROLE_CODES
from app.services.dashboard_module_registry import get_canonical_module_code
QUICK_ACTION_STATUSES: tuple[str, ...] = ("ACTIVE", "DRAFT", "PLANNED", "DISABLED")
ACTIVE_QUICK_ACTION_STATUSES = {"ACTIVE"}
PREVIEW_QUICK_ACTION_STATUSES = {"DRAFT", "PLANNED", "DISABLED"}
QUICK_ACTION_PREVIEW_ROLE_CODES = {"SUPER_ADMIN", "PLATFORM_ADMIN", *LEGACY_ADMIN_ROLE_CODES}
QUICK_ACTION_SURFACES: tuple[str, ...] = ("MODULE_BAR", "MODULE_CARD", "BOTH")
QUICK_ACTION_ACTION_TYPES: tuple[str, ...] = ("navigate", "modal", "callback")

QUICK_ACTION_REGISTRY_LAYER = "module03_quick_action_registry"
QUICK_ACTION_REGISTRY_NOTE = (
    "QuickActionRegistry is kept as a compatibility layer for user-saved shortcuts. "
    "The platform does not ship fixed quick action presets: modules expose candidates on real controls, "
    "then a user explicitly saves the shortcut for their module or card."
)


@dataclass(frozen=True)
class QuickActionRegistryItemDefinition:
    id: str
    quickActionCode: str
    title: str
    sourceModuleCode: str
    actionCode: str
    requiredActionCode: str
    requiredAccessLevel: str
    requiredScope: str
    status: str
    isSystem: bool
    order: int
    description: str | None = None
    canonicalModuleCode: str | None = None
    featureCode: str | None = None
    sectionCode: str | None = None
    widgetCode: str | None = None
    allowedRoles: list[str] = field(default_factory=list)
    allowedCabinetTypes: list[str] = field(default_factory=list)
    route: str | None = None
    actionType: str = "navigate"
    targetRoute: str | None = None
    modalCode: str | None = None
    requiredPermission: str | None = None
    isEnabledByDefault: bool = True
    isAvailable: bool = True
    maxSurface: str = "BOTH"
    settings: dict[str, Any] = field(default_factory=dict)
    registryLayer: str = QUICK_ACTION_REGISTRY_LAYER
    compatibilityNote: str = QUICK_ACTION_REGISTRY_NOTE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["titleRu"] = self.title
        data["descriptionRu"] = self.description
        data["icon"] = self.settings.get("icon")
        data["sortOrder"] = self.order
        data["targetRoute"] = self.targetRoute or self.route
        data["route"] = self.route or self.targetRoute
        return data


def get_quick_action_registry() -> list[dict[str, Any]]:
    return [item.to_dict() for item in _quick_action_registry_definitions()]


def build_quick_action_registry_item(definition: dict[str, Any] | QuickActionRegistryItemDefinition) -> QuickActionRegistryItemDefinition:
    if isinstance(definition, QuickActionRegistryItemDefinition):
        return definition
    data = _normalize_external_quick_action_definition(definition)
    return _item(**data)


def quick_action_registry_item_to_dict(
    definition: dict[str, Any] | QuickActionRegistryItemDefinition,
) -> dict[str, Any]:
    return build_quick_action_registry_item(definition).to_dict()


def filter_quick_action_registry_items_for_module(
    registry_items: list[dict[str, Any] | QuickActionRegistryItemDefinition],
    source_module_code: str,
    *,
    surface: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    surface_code = surface.upper() if surface else None
    items: list[dict[str, Any]] = []
    for definition in registry_items:
        item = build_quick_action_registry_item(definition)
        if item.sourceModuleCode != source_module_code:
            continue
        if not include_inactive and item.status not in ACTIVE_QUICK_ACTION_STATUSES:
            continue
        if surface_code and item.maxSurface not in {surface_code, "BOTH"}:
            continue
        items.append(item.to_dict())
    return sorted(items, key=lambda action: (action["sortOrder"], action["quickActionCode"]))


def get_quick_action_registry_item(quick_action_code: str | None) -> QuickActionRegistryItemDefinition | None:
    if not quick_action_code:
        return None
    return next(
        (
            item
            for item in _quick_action_registry_definitions()
            if item.quickActionCode == quick_action_code
        ),
        None,
    )


def get_quick_action_registry_items_for_module(
    source_module_code: str,
    *,
    surface: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    surface_code = surface.upper() if surface else None
    items: list[dict[str, Any]] = []
    for item in _quick_action_registry_definitions():
        if item.sourceModuleCode != source_module_code:
            continue
        if not include_inactive and item.status not in ACTIVE_QUICK_ACTION_STATUSES:
            continue
        if surface_code and item.maxSurface not in {surface_code, "BOTH"}:
            continue
        items.append(item.to_dict())
    return sorted(items, key=lambda action: (action["sortOrder"], action["quickActionCode"]))


def get_available_quick_action_registry_items(user_profile: Any, context: Any | None = None) -> list[dict[str, Any]]:
    from app.services.quick_action_permission import can_use_quick_action

    effective_context = context or user_profile
    return [
        item.to_dict()
        for item in _quick_action_registry_definitions()
        if can_use_quick_action(user_profile, item.quickActionCode, effective_context)
    ]


def get_preview_quick_action_registry_items(user_profile: Any) -> list[dict[str, Any]]:
    data = _profile_dict(user_profile)
    if data.get("authMode") not in {"mock", "dev"}:
        return []
    role_code = (data.get("effectiveRoleCode") or data.get("roleCode") or "").upper()
    if role_code not in QUICK_ACTION_PREVIEW_ROLE_CODES:
        return []
    return [
        item.to_dict()
        for item in _quick_action_registry_definitions()
        if item.status in PREVIEW_QUICK_ACTION_STATUSES
    ]


def _quick_action_registry_definitions() -> tuple[QuickActionRegistryItemDefinition, ...]:
    return ()

def _item(**data: Any) -> QuickActionRegistryItemDefinition:
    source_module_code = data["sourceModuleCode"]
    canonical_module_code = get_canonical_module_code(source_module_code) or source_module_code
    action_type = data.get("actionType", "navigate")
    max_surface = data.get("maxSurface", "BOTH")
    if action_type not in QUICK_ACTION_ACTION_TYPES:
        raise ValueError(f"Unsupported quick action actionType: {action_type}")
    if max_surface not in QUICK_ACTION_SURFACES:
        raise ValueError(f"Unsupported quick action maxSurface: {max_surface}")
    return QuickActionRegistryItemDefinition(
        id=data.get("id") or data["quickActionCode"],
        quickActionCode=data["quickActionCode"],
        title=data["title"],
        description=data.get("description"),
        sourceModuleCode=source_module_code,
        canonicalModuleCode=data.get("canonicalModuleCode") or canonical_module_code,
        featureCode=data.get("featureCode"),
        sectionCode=data.get("sectionCode"),
        widgetCode=data.get("widgetCode"),
        actionCode=data.get("actionCode") or data["quickActionCode"],
        requiredActionCode=str(data["requiredActionCode"]),
        requiredAccessLevel=str(data["requiredAccessLevel"]),
        requiredScope=str(data["requiredScope"]),
        allowedRoles=list(data.get("allowedRoles") or []),
        allowedCabinetTypes=list(data.get("allowedCabinetTypes") or []),
        route=data.get("route"),
        actionType=action_type,
        targetRoute=data.get("targetRoute") or data.get("route"),
        modalCode=data.get("modalCode"),
        requiredPermission=data.get("requiredPermission") or (data.get("settings") or {}).get("permissionCode"),
        isEnabledByDefault=bool(data.get("isEnabledByDefault", True)),
        isAvailable=bool(data.get("isAvailable", data.get("status", "ACTIVE") == "ACTIVE")),
        maxSurface=max_surface,
        status=data.get("status", "ACTIVE"),
        isSystem=data.get("isSystem", True),
        order=data.get("order", 1000),
        settings=dict(data.get("settings") or {}),
    )


def _normalize_external_quick_action_definition(definition: dict[str, Any]) -> dict[str, Any]:
    data = dict(definition)
    if "title" not in data and "titleRu" in data:
        data["title"] = data["titleRu"]
    if "description" not in data and "descriptionRu" in data:
        data["description"] = data["descriptionRu"]
    if "order" not in data and "sortOrder" in data:
        data["order"] = data["sortOrder"]
    if "route" not in data and "targetRoute" in data:
        data["route"] = data["targetRoute"]
    required_action_code, required_access_level = _permission_defaults(data)
    data.setdefault("requiredActionCode", required_action_code)
    data.setdefault("requiredAccessLevel", required_access_level)
    data.setdefault("requiredScope", AccessScope.GLOBAL)
    return data


def _permission_defaults(data: dict[str, Any]) -> tuple[str, str]:
    permission = str(data.get("requiredPermission") or "").lower()
    action_code = str(data.get("actionCode") or data.get("quickActionCode") or "VIEW").upper()
    if permission.endswith(".read") or permission.endswith(".view"):
        return "VIEW", AccessLevel.VIEW
    if permission.endswith(".create") or permission.endswith(".upload"):
        return "CREATE", AccessLevel.CREATE
    if permission.endswith(".edit") or permission.endswith(".update"):
        return "EDIT", AccessLevel.EDIT
    if permission.endswith(".approve") or permission.endswith(".moderate"):
        return "APPROVE", AccessLevel.APPROVE
    if action_code.startswith("OPEN_") or action_code.startswith("VIEW_") or action_code.endswith("_LIST"):
        return "VIEW", AccessLevel.VIEW
    if action_code.startswith("CREATE_") or action_code.startswith("ADD_"):
        return "CREATE", AccessLevel.CREATE
    return action_code, data.get("requiredAccessLevel") or AccessLevel.ADMIN


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
