from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.audit_log import AuditLog
from app.models.dashboard_profile import DashboardProfile
from app.models.dashboard_widget import DashboardWidget
from app.models.dashboard_widget_placement import DashboardWidgetPlacement
from app.models.function_access import FunctionAccess
from app.models.module_access import ModuleAccess
from app.models.permission import Permission
from app.models.platform_module_registry import PlatformModuleRegistry
from app.services.admin_user_role_management import active_role_codes_for_user


MODULE_REGISTRY_STATUSES: tuple[str, ...] = (
    "ACTIVE",
    "DRAFT",
    "PLANNED",
    "DISABLED",
    "DEPRECATED",
    "ARCHIVED",
    "MERGED",
)

LEGACY_MODULE_CODES: set[str] = {
    "MODULE_07_DIGITAL_OBJECT",
    "MODULE_14_PRICE_HISTORY",
    "MODULE_14_CONSTRUCTOR_LITE",
    "MODULE_15_CONSTRUCTION_GROUPS",
    "MODULE_16_ADMIN_CABINET",
}

HIDDEN_MODULE_STATUSES: set[str] = {"MERGED", "ARCHIVED"}
TERMINAL_MODULE_STATUSES: set[str] = {"DEPRECATED", "ARCHIVED", "MERGED"}
PLATFORM_ADMIN_ALLOWED_STATUSES: set[str] = {"ACTIVE", "DRAFT", "PLANNED", "DISABLED"}
ARCHIVE_CONFIRMATION = "ARCHIVE_MODULE"


def can_open_module_registry_admin(actor: Any) -> bool:
    return bool(active_role_codes_for_user(actor) & {"SUPER_ADMIN", "PLATFORM_ADMIN"})


def is_super_admin(actor: Any) -> bool:
    return "SUPER_ADMIN" in active_role_codes_for_user(actor)


def is_legacy_or_alias_module(module: PlatformModuleRegistry | Any) -> bool:
    module_code = _get_value(module, "module_code")
    canonical_code = _get_value(module, "canonical_module_code")
    status = _status(module)
    return (
        module_code in LEGACY_MODULE_CODES
        or status in {"MERGED", "DEPRECATED"}
        or bool(canonical_code and canonical_code != module_code)
    )


def require_module_registry_admin(actor: Any) -> None:
    if not can_open_module_registry_admin(actor):
        raise ForbiddenError("Module registry administration requires PLATFORM_ADMIN or SUPER_ADMIN.")


def can_update_module_status(actor: Any, module: PlatformModuleRegistry, target_status: str) -> bool:
    normalized_status = normalize_module_status(target_status)
    if normalized_status is None:
        return False
    if is_legacy_or_alias_module(module) and normalized_status == "ACTIVE":
        return False
    if is_super_admin(actor):
        return True
    if normalized_status not in PLATFORM_ADMIN_ALLOWED_STATUSES:
        return False
    if module.is_system or is_legacy_or_alias_module(module):
        return False
    return can_open_module_registry_admin(actor)


def can_update_module_flags(actor: Any, module: PlatformModuleRegistry) -> bool:
    if is_super_admin(actor):
        return True
    return can_open_module_registry_admin(actor) and not module.is_system and not is_legacy_or_alias_module(module)


def normalize_module_status(status: str | None) -> str | None:
    if not status:
        return None
    normalized = status.upper()
    return normalized if normalized in MODULE_REGISTRY_STATUSES else None


async def get_module_registry_overview(db: AsyncSession, actor: Any) -> dict[str, Any]:
    require_module_registry_admin(actor)
    result = await db.execute(
        select(PlatformModuleRegistry).order_by(
            PlatformModuleRegistry.display_order,
            PlatformModuleRegistry.module_code,
        )
    )
    modules = list(result.scalars().all())
    dependency_map = await _load_dependency_map(db, modules)
    return {
        "actorRoleCodes": sorted(active_role_codes_for_user(actor)),
        "statuses": list(MODULE_REGISTRY_STATUSES),
        "modules": [module_summary(item, dependency_map.get(item.module_code, {})) for item in modules],
    }


async def get_module_registry_detail(db: AsyncSession, module_code: str, actor: Any) -> dict[str, Any]:
    require_module_registry_admin(actor)
    module = await _get_module(db, module_code)
    dependencies = await _load_module_dependencies(db, module)
    history = await _load_module_history(db, module)
    return {
        "module": module_detail(module, dependencies),
        "statuses": list(MODULE_REGISTRY_STATUSES),
        "history": [audit_summary(item) for item in history],
        "canUpdateStatus": {
            status: can_update_module_status(actor, module, status)
            for status in MODULE_REGISTRY_STATUSES
        },
        "canUpdateFlags": can_update_module_flags(actor, module),
        "archiveConfirmation": ARCHIVE_CONFIRMATION,
    }


async def update_module_registry_item(
    db: AsyncSession,
    *,
    actor: Any,
    module_code: str,
    status: str,
    visible_in_sidebar: bool,
    visible_on_dashboard: bool,
    visible_on_atom_map: bool,
    available_for_widgets: bool,
) -> PlatformModuleRegistry:
    require_module_registry_admin(actor)
    module = await _get_module(db, module_code)
    normalized_status = normalize_module_status(status)
    if not normalized_status:
        raise ValidationError("Unsupported module status.")
    if not can_update_module_status(actor, module, normalized_status):
        raise ForbiddenError("The current administrator cannot set this module status.")

    flags_allowed = can_update_module_flags(actor, module)
    old_state = _module_state(module)
    module.status = normalized_status
    module.is_active = normalized_status == "ACTIVE"
    if flags_allowed:
        module.is_visible_in_sidebar = bool(visible_in_sidebar)
        module.is_visible_on_dashboard = bool(visible_on_dashboard)
        module.is_visible_on_atom_map = bool(visible_on_atom_map)
        module.is_available_for_widgets = bool(available_for_widgets)
    if normalized_status in HIDDEN_MODULE_STATUSES or is_legacy_or_alias_module(module):
        module.is_visible_in_sidebar = False
        module.is_visible_on_dashboard = False
        module.is_visible_on_atom_map = False
        module.is_available_for_widgets = False
    if normalized_status in TERMINAL_MODULE_STATUSES:
        module.is_active = False
    module.updated_at = datetime.utcnow()
    _add_audit_log(
        db,
        actor,
        module,
        action_type="platform_module_registry_updated",
        details={"old": old_state, "new": _module_state(module)},
    )
    await db.flush()
    return module


async def archive_module_registry_item(
    db: AsyncSession,
    *,
    actor: Any,
    module_code: str,
    confirmation: str | None,
) -> PlatformModuleRegistry:
    if confirmation != ARCHIVE_CONFIRMATION:
        raise ValidationError(f"Confirm dangerous action with {ARCHIVE_CONFIRMATION}.")
    module = await _get_module(db, module_code)
    if not can_update_module_status(actor, module, "ARCHIVED"):
        raise ForbiddenError("The current administrator cannot archive this module.")
    old_state = _module_state(module)
    module.status = "ARCHIVED"
    module.is_active = False
    module.is_visible_in_sidebar = False
    module.is_visible_on_dashboard = False
    module.is_visible_on_atom_map = False
    module.is_available_for_widgets = False
    module.updated_at = datetime.utcnow()
    _add_audit_log(
        db,
        actor,
        module,
        action_type="platform_module_registry_archived",
        details={
            "old": old_state,
            "new": _module_state(module),
            "physicalDelete": "forbidden",
        },
    )
    await db.flush()
    return module


def module_summary(module: PlatformModuleRegistry, dependencies: dict[str, Any] | None = None) -> dict[str, Any]:
    deps = dependencies or {}
    legacy = is_legacy_or_alias_module(module)
    return {
        "moduleCode": module.module_code,
        "canonicalModuleCode": module.canonical_module_code or module.module_code,
        "title": module.title,
        "shortTitle": module.short_title,
        "status": module.status,
        "isActive": module.is_active,
        "isSystem": module.is_system,
        "isLegacyOrAlias": legacy,
        "displayOrder": module.display_order,
        "route": module.route,
        "redirectRoute": module.redirect_route,
        "mergedIntoModuleCode": module.merged_into_module_code,
        "legacyCodes": _list_value(module.legacy_codes),
        "featureCodes": _list_value(module.feature_codes),
        "visibleFlags": _visible_flags(module),
        "dependencyCounts": _dependency_counts(deps),
    }


def module_detail(module: PlatformModuleRegistry, dependencies: dict[str, Any]) -> dict[str, Any]:
    data = module_summary(module, dependencies)
    data.update(
        {
            "description": module.description,
            "version": module.version,
            "legacyNumber": module.legacy_number,
            "displayNumber": module.display_number,
            "visualNumber": module.visual_number,
            "parentModuleCode": module.parent_module_code,
            "ownerModuleCode": module.owner_module_code,
            "icon": module.icon,
            "color": module.color,
            "isPublic": module.is_public,
            "defaultPermissions": module.default_permissions or [],
            "availableActions": module.available_actions or [],
            "dashboardWidgets": module.dashboard_widgets or [],
            "ownerScopeRules": module.owner_scope_rules or {},
            "permissions": dependencies.get("permissions", []),
            "moduleAccess": dependencies.get("moduleAccess", []),
            "featureAccess": dependencies.get("featureAccess", []),
            "widgets": dependencies.get("widgets", []),
            "dashboardLayouts": dependencies.get("dashboardLayouts", []),
            "auditNotes": dependencies.get("auditNotes", []),
            "canPhysicallyDelete": False,
        }
    )
    return data


def audit_summary(item: AuditLog) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "createdAt": item.created_at,
        "actionType": item.action_type,
        "result": item.result,
        "actor": item.user.email if item.user else "system/dev",
        "details": item.details or {},
    }


async def _get_module(db: AsyncSession, module_code: str) -> PlatformModuleRegistry:
    result = await db.execute(
        select(PlatformModuleRegistry).where(PlatformModuleRegistry.module_code == module_code)
    )
    module = result.scalar_one_or_none()
    if module is None:
        raise NotFoundError("Module registry item not found.")
    return module


async def _load_dependency_map(
    db: AsyncSession,
    modules: list[PlatformModuleRegistry],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for module in modules:
        dependencies = await _load_module_dependencies(db, module, detail=False)
        result[module.module_code] = dependencies
    return result


async def _load_module_dependencies(
    db: AsyncSession,
    module: PlatformModuleRegistry,
    *,
    detail: bool = True,
) -> dict[str, Any]:
    codes = _related_codes(module)
    permissions = await _load_permissions(db, codes, detail)
    module_access = await _load_module_access(db, codes, detail)
    feature_access = await _load_feature_access(db, codes, detail)
    widgets = await _load_widgets(db, codes, detail)
    layouts = await _load_dashboard_layout_refs(db, module, widgets, detail)
    audit_notes = await _load_audit_notes(db, module, detail)
    return {
        "permissions": permissions,
        "moduleAccess": module_access,
        "featureAccess": feature_access,
        "widgets": widgets,
        "dashboardLayouts": layouts,
        "auditNotes": audit_notes,
    }


async def _load_permissions(db: AsyncSession, codes: set[str], detail: bool) -> list[dict[str, Any]]:
    if not codes:
        return []
    result = await db.execute(select(Permission).where(Permission.module_code.in_(codes)))
    items = list(result.scalars().all())
    if not detail:
        return [{"count": len(items)}]
    return [
        {
            "permissionKey": item.permission_key,
            "moduleCode": item.module_code,
            "actionCode": item.action_code,
            "accessLevel": item.access_level,
            "accessScope": item.access_scope,
            "status": item.status,
        }
        for item in items
    ]


async def _load_module_access(db: AsyncSession, codes: set[str], detail: bool) -> list[dict[str, Any]]:
    if not codes:
        return []
    result = await db.execute(
        select(ModuleAccess).where(
            or_(
                ModuleAccess.module_code.in_(codes),
                ModuleAccess.canonical_module_code.in_(codes),
            )
        )
    )
    items = list(result.scalars().all())
    if not detail:
        return [{"count": len(items)}]
    return [
        {
            "moduleCode": item.module_code,
            "canonicalModuleCode": item.canonical_module_code,
            "accessLevel": item.access_level,
            "accessScope": item.access_scope,
            "status": item.status,
            "roleId": str(item.role_id) if item.role_id else None,
            "userId": str(item.user_id) if item.user_id else None,
            "workspaceId": str(item.workspace_id) if item.workspace_id else None,
        }
        for item in items
    ]


async def _load_feature_access(db: AsyncSession, codes: set[str], detail: bool) -> list[dict[str, Any]]:
    if not codes:
        return []
    result = await db.execute(
        select(FunctionAccess).where(
            or_(
                FunctionAccess.module_code.in_(codes),
                FunctionAccess.canonical_module_code.in_(codes),
            )
        )
    )
    items = list(result.scalars().all())
    if not detail:
        return [{"count": len(items)}]
    return [
        {
            "moduleCode": item.module_code,
            "canonicalModuleCode": item.canonical_module_code,
            "featureCode": item.feature_code or item.function_key,
            "accessLevel": item.access_level,
            "accessScope": item.access_scope,
            "status": item.status,
        }
        for item in items
    ]


async def _load_widgets(db: AsyncSession, codes: set[str], detail: bool) -> list[dict[str, Any]]:
    if not codes:
        return []
    result = await db.execute(
        select(DashboardWidget).where(
            or_(
                DashboardWidget.source_module_code.in_(codes),
                DashboardWidget.canonical_module_code.in_(codes),
            )
        )
    )
    items = list(result.scalars().all())
    if not detail:
        return [{"count": len(items)}]
    return [
        {
            "widgetKey": item.widget_key,
            "title": item.title,
            "sourceModuleCode": item.source_module_code,
            "canonicalModuleCode": item.canonical_module_code,
            "featureCode": item.feature_code,
            "type": item.widget_type,
            "status": item.status,
        }
        for item in items
    ]


async def _load_dashboard_layout_refs(
    db: AsyncSession,
    module: PlatformModuleRegistry,
    widgets: list[dict[str, Any]],
    detail: bool,
) -> list[dict[str, Any]]:
    widget_keys = [item.get("widgetKey") for item in widgets if item.get("widgetKey")]
    widget_ids: list[Any] = []
    if widget_keys:
        result = await db.execute(select(DashboardWidget.id).where(DashboardWidget.widget_key.in_(widget_keys)))
        widget_ids = list(result.scalars().all())

    placement_count = 0
    if widget_ids:
        placement_count_result = await db.execute(
            select(func.count(DashboardWidgetPlacement.id)).where(DashboardWidgetPlacement.widget_id.in_(widget_ids))
        )
        placement_count = int(placement_count_result.scalar() or 0)

    profile_result = await db.execute(
        select(DashboardProfile).where(DashboardProfile.status == "ACTIVE")
    )
    profile_refs = [
        profile
        for profile in profile_result.scalars().all()
        if _profile_references_module(profile, module)
    ]
    if not detail:
        return [{"count": placement_count + len(profile_refs)}]
    refs: list[dict[str, Any]] = []
    if placement_count:
        refs.append({"type": "DashboardWidgetPlacement", "count": placement_count})
    refs.extend(
        {
            "type": "DashboardProfile",
            "profileId": str(profile.id),
            "name": profile.name,
            "status": profile.status,
        }
        for profile in profile_refs
    )
    return refs


async def _load_audit_notes(db: AsyncSession, module: PlatformModuleRegistry, detail: bool) -> list[dict[str, Any]]:
    result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .where(
            or_(
                AuditLog.entity_type == "PlatformModuleRegistry",
                AuditLog.entity_type == "ModuleRegistry",
            ),
            or_(
                AuditLog.entity_id == module.id,
                AuditLog.details["moduleCode"].astext == module.module_code,
            ),
        )
        .order_by(desc(AuditLog.created_at))
        .limit(20 if detail else 1)
    )
    items = list(result.scalars().all())
    if not detail:
        return [{"count": len(items)}]
    return [audit_summary(item) for item in items]


async def _load_module_history(db: AsyncSession, module: PlatformModuleRegistry) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .where(AuditLog.entity_type == "PlatformModuleRegistry", AuditLog.entity_id == module.id)
        .order_by(desc(AuditLog.created_at))
        .limit(30)
    )
    return list(result.scalars().all())


def _related_codes(module: PlatformModuleRegistry) -> set[str]:
    return {
        code
        for code in (
            module.module_code,
            module.canonical_module_code,
            module.merged_into_module_code,
            *(_list_value(module.legacy_codes)),
        )
        if code
    }


def _profile_references_module(profile: DashboardProfile, module: PlatformModuleRegistry) -> bool:
    codes = _related_codes(module)
    payload = {
        "layout": profile.layout or {},
        "favorite_modules": profile.favorite_modules or [],
    }
    text = repr(payload)
    return any(code in text for code in codes)


def _dependency_counts(dependencies: dict[str, Any]) -> dict[str, int]:
    def count(key: str) -> int:
        items = dependencies.get(key) or []
        if len(items) == 1 and "count" in items[0]:
            return int(items[0]["count"])
        return len(items)

    return {
        "permissions": count("permissions") + count("moduleAccess") + count("featureAccess"),
        "widgets": count("widgets"),
        "dashboardLayouts": count("dashboardLayouts"),
        "auditNotes": count("auditNotes"),
    }


def _visible_flags(module: PlatformModuleRegistry) -> dict[str, bool]:
    return {
        "sidebar": module.is_visible_in_sidebar,
        "dashboard": module.is_visible_on_dashboard,
        "atomMap": module.is_visible_on_atom_map,
        "widgets": module.is_available_for_widgets,
    }


def _module_state(module: PlatformModuleRegistry) -> dict[str, Any]:
    return {
        "moduleCode": module.module_code,
        "status": module.status,
        "isActive": module.is_active,
        "visibleFlags": _visible_flags(module),
    }


def _add_audit_log(
    db: AsyncSession,
    actor: Any,
    module: PlatformModuleRegistry,
    *,
    action_type: str,
    details: dict[str, Any],
) -> None:
    actor_id = _get_value(actor, "id")
    db.add(
        AuditLog(
            user_id=actor_id if isinstance(actor_id, UUID) else None,
            action_type=action_type,
            entity_type="PlatformModuleRegistry",
            entity_id=module.id,
            result="SUCCESS",
            details={"moduleCode": module.module_code, **details},
        )
    )


def _status(module: Any) -> str:
    return str(_get_value(module, "status") or "").upper()


def _list_value(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if item]
    return []


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)
