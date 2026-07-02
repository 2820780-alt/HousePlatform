from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.role_access_matrix import get_starter_role_feature_access, get_starter_role_module_access
from app.core.system_roles import (
    SYSTEM_ROLE_DEFINITIONS,
    SYSTEM_ROLE_CODES,
    is_system_role_code,
)
from app.models.audit_log import AuditLog
from app.models.enums import UserRole, UserStatus
from app.models.function_access import FunctionAccess
from app.models.module_access import ModuleAccess
from app.models.role import Role
from app.models.user import User
from app.models.user_role_assignment import UserRoleAssignment
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.services.access_context_for_cabinet import build_access_context_for_cabinet
from app.services.access_distribution_registry import build_pending_access_distribution_items
from app.services.audit_log_service import AuditLogType, write_audit_event
from app.services.dashboard_module_registry import get_dashboard_module_registry, get_dashboard_module_registry_item
from app.services.module8_cabinet_admin_preview import get_module8_cabinet_admin_preview
from app.services.quick_action_preferences import build_quick_action_preference_preview
from app.services.quick_action_registry import get_quick_action_registry
from app.services.role_dashboard_access_profiles import get_role_dashboard_access_profile
from app.services.widget_settings_schema import build_widget_settings_schema_preview
from app.services.widget_registry import get_widget_registry, get_widget_registry_item


LEGACY_ROLE_ALIASES: dict[str, str] = {
    "ADMIN": "PLATFORM_ADMIN",
    "MANAGER": "PLATFORM_ADMIN",
    "ENGINEER": "ENGINEER_DESIGNER",
    "DEV_ADMIN": "SUPER_ADMIN",
}

ROLE_LABELS: dict[str, str] = {
    role.roleCode: role.name for role in SYSTEM_ROLE_DEFINITIONS
}

ADMIN_UI_ROLE_CODES = {"SUPER_ADMIN", "PLATFORM_ADMIN"}
PLATFORM_ADMIN_UI_ROLE_CODES = {"SUPER_ADMIN", "PLATFORM_ADMIN"}
PROTECTED_ROLE_CODES = {"SUPER_ADMIN"}
DISABLE_CONFIRMATION = "DISABLE_USER"
COMPANY_ADMIN_ROLE_CODE = "COMPANY_ADMIN"
COMPANY_ADMIN_ASSIGNER_ROLE_CODES = {"SUPER_ADMIN", "PLATFORM_ADMIN"}
COMPANY_ADMIN_FALLBACK_ROLE_CODE = "VIEWER"
COMPANY_ADMIN_COMPATIBLE_ROLE_CODES = {
    COMPANY_ADMIN_ROLE_CODE,
    "OWNER",
    "DIRECTOR",
    "COMPANY_OWNER",
}
COMPANY_ADMIN_VISIBLE_ROLE_CODES = {
    COMPANY_ADMIN_ROLE_CODE,
    "SUPPLIER",
    "CONTRACTOR",
    "CUSTOMER",
    "ESTIMATOR",
    "ENGINEER_DESIGNER",
    "VIEWER",
}

MODULE3_QUICK_ACTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "add-user",
        "label": "Добавить пользователя",
        "icon": "+",
        "permissionCode": "MODULE_03_USERS_MANAGE",
        "featureCode": "USERS",
        "visibleForCompanyAdmin": True,
        "enabled": True,
        "actionType": "navigate",
        "target": "#users",
        "description": "Переход к пользователям. Ручное создание заменяется стандартной регистрацией.",
    },
    {
        "id": "add-company",
        "label": "Добавить компанию",
        "icon": "+",
        "permissionCode": "MODULE_03_COMPANIES_MANAGE",
        "featureCode": "COMPANIES",
        "visibleForCompanyAdmin": False,
        "enabled": True,
        "actionType": "navigate",
        "target": "#companies",
        "description": "Переход к компаниям и карточкам организаций.",
    },
    {
        "id": "import-users",
        "label": "Импорт пользователей",
        "icon": "⇧",
        "permissionCode": "MODULE_03_USERS_IMPORT",
        "featureCode": "USERS_IMPORT",
        "visibleForCompanyAdmin": False,
        "enabled": True,
        "actionType": "navigate",
        "target": "#audit-log",
        "description": "Переход к журналу и существующим операциям импорта.",
    },
    {
        "id": "open-history",
        "label": "Открыть историю",
        "icon": "◷",
        "permissionCode": "MODULE_03_AUDIT_VIEW",
        "featureCode": "AUDIT_LOG",
        "visibleForCompanyAdmin": True,
        "enabled": True,
        "actionType": "navigate",
        "target": "#audit-log",
        "description": "Открыть историю изменений доступа.",
    },
    {
        "id": "configure-access",
        "label": "Настроить доступы",
        "icon": "◇",
        "permissionCode": "MODULE_03_ACCESS_MANAGE",
        "featureCode": "ACCESS_MATRIX",
        "visibleForCompanyAdmin": True,
        "enabled": True,
        "actionType": "navigate",
        "target": "#access-matrix",
        "detailTarget": "#access-matrix-detail",
        "description": "Переход к матрице доступа.",
    },
    {
        "id": "bulk-access-assignment",
        "label": "Массовое назначение доступа",
        "icon": "▦",
        "permissionCode": "MODULE_03_ACCESS_BULK_ASSIGN",
        "featureCode": "ACCESS_MATRIX",
        "visibleForCompanyAdmin": False,
        "enabled": True,
        "actionType": "navigate",
        "target": "#access-matrix",
        "detailTarget": "#access-matrix-detail",
        "description": "Групповой переход к настройке доступов.",
    },
    {
        "id": "export-users",
        "label": "Экспорт списка",
        "icon": "⇩",
        "permissionCode": "MODULE_03_USERS_EXPORT",
        "featureCode": "USERS",
        "visibleForCompanyAdmin": True,
        "enabled": True,
        "actionType": "navigate",
        "target": "#users",
        "description": "Переход к списку пользователей для выгрузки/проверки.",
    },
)

ACCESS_RESOLUTION_SOURCES: tuple[str, ...] = (
    "SYSTEM_DEFAULT",
    "ROLE_DEFAULT",
    "COMPANY_DEFAULT",
    "GROUP_DEFAULT",
    "USER_OVERRIDE",
    "TARIFF_LIMIT",
    "SYSTEM_LIMIT",
)

ACCESS_DENY_REASONS: dict[str, str] = {
    "PLATFORM_ADMIN_DENY": "Закрыто администратором платформы",
    "COMPANY_ADMIN_DENY": "Закрыто администратором компании",
    "TARIFF_LIMIT": "Недоступно по тарифу",
    "SYSTEM_LIMIT": "Недоступно: системное ограничение",
    "MODULE_DISABLED": "Недоступно: модуль отключен",
    "MODULE_PLANNED": "Недоступно: модуль еще не активен",
    "MODULE_DRAFT": "Недоступно: модуль в подготовке",
    "WIDGET_DISABLED": "Недоступно: виджет отключен",
    "WIDGET_REVOKED_BY_MODULE_DENY": "Недоступно: виджет закрыт вместе с модулем",
    "USER_BLOCKED": "Недоступно: пользователь заблокирован",
    "COMPANY_BLOCKED": "Недоступно: компания заблокирована",
}

VISIBLE_ACCESS_STATES: dict[str, str] = {
    "OPEN": "открыто",
    "CLOSED": "закрыто",
    "TARIFF_LIMIT": ACCESS_DENY_REASONS["TARIFF_LIMIT"],
    "SYSTEM_LIMIT": ACCESS_DENY_REASONS["SYSTEM_LIMIT"],
    "MODULE_DISABLED": ACCESS_DENY_REASONS["MODULE_DISABLED"],
    "MODULE_PLANNED": ACCESS_DENY_REASONS["MODULE_PLANNED"],
    "MODULE_DRAFT": ACCESS_DENY_REASONS["MODULE_DRAFT"],
    "WIDGET_DISABLED": ACCESS_DENY_REASONS["WIDGET_DISABLED"],
    "WIDGET_REVOKED_BY_MODULE_DENY": ACCESS_DENY_REASONS["WIDGET_REVOKED_BY_MODULE_DENY"],
    "USER_BLOCKED": ACCESS_DENY_REASONS["USER_BLOCKED"],
    "COMPANY_BLOCKED": ACCESS_DENY_REASONS["COMPANY_BLOCKED"],
}

ACCESS_REASON_CATEGORIES: dict[str, str] = {
    "PLATFORM_ADMIN_DENY": "manual_platform",
    "COMPANY_ADMIN_DENY": "manual_company",
    "TARIFF_LIMIT": "tariff",
    "SYSTEM_LIMIT": "system",
    "MODULE_DISABLED": "system",
    "MODULE_PLANNED": "system",
    "MODULE_DRAFT": "system",
    "WIDGET_DISABLED": "system",
    "WIDGET_REVOKED_BY_MODULE_DENY": "derived",
    "USER_BLOCKED": "system",
    "COMPANY_BLOCKED": "system",
}

MONETIZATION_READY_FIELDS: tuple[str, ...] = (
    "planCode",
    "subscriptionCode",
    "billingFeatureCode",
    "billingRestrictionReason",
    "tariffLevel",
    "tariffExpiresAt",
    "isBillingRestricted",
)

ROLE_LABELS[COMPANY_ADMIN_ROLE_CODE] = "Администратор компании"

ADMIN_UI_STATE_LEGEND: tuple[dict[str, str], ...] = (
    {
        "code": "EMPTY",
        "title": "empty state",
        "description": "Данных нет: список, registry или связанный контекст пока пуст.",
        "severity": "info",
    },
    {
        "code": "LOADING",
        "title": "loading state",
        "description": "Данные загружаются или adapter еще не вернул DTO.",
        "severity": "info",
    },
    {
        "code": "ERROR",
        "title": "error state",
        "description": "Ошибка не скрывается молча: администратор должен видеть причину и источник.",
        "severity": "error",
    },
    {
        "code": "NO_PERMISSION",
        "title": "no permission state",
        "description": "Виджет недоступен: нет прав на данные модуля, widgetCode, actionCode или scope.",
        "severity": "warning",
    },
    {
        "code": "NOT_CONFIGURED",
        "title": "not configured state",
        "description": "Не задан activeRegionCode, workspace, role profile или кабинетный context.",
        "severity": "warning",
    },
    {
        "code": "MODULE_NOT_READY",
        "title": "module not ready state",
        "description": "Модуль-источник не готов или недоступен для Dashboard/quick actions.",
        "severity": "warning",
    },
    {
        "code": "FUTURE_FEATURE",
        "title": "future feature state",
        "description": "Это действие запланировано, но еще не активно. Обычным пользователям оно не отображается как рабочее.",
        "severity": "info",
    },
    {
        "code": "PREMIUM_PLACEHOLDER",
        "title": "premium placeholder state",
        "description": "Будущая платная возможность: billing не реализуется в Module №3.",
        "severity": "info",
    },
    {
        "code": "LEGACY_MERGED",
        "title": "legacy/merged state",
        "description": "Модуль объединен с другим модулем. Используется актуальный canonical moduleCode.",
        "severity": "warning",
    },
    {
        "code": "ARCHIVED_DISABLED",
        "title": "archived/disabled state",
        "description": "Отключенные и архивные элементы не доступны как active.",
        "severity": "error",
    },
)


@dataclass(frozen=True)
class RoleOption:
    roleCode: str
    title: str
    description: str | None = None
    isSystem: bool = True
    isAssignableByPlatformAdmin: bool = True


def normalize_role_code(role_code: Any) -> str | None:
    value = _enum_value(role_code)
    if not value:
        return None
    return LEGACY_ROLE_ALIASES.get(value, value)


def active_role_codes_for_user(user: Any) -> set[str]:
    role_values: list[Any] = []
    for field_name in ("roleCode", "role_code", "role"):
        value = _get_value(user, field_name)
        if value:
            role_values.append(value)

    for assignment in _safe_iterable(_get_value(user, "role_assignments")):
        if _enum_value(_get_value(assignment, "status")) not in {"", "ACTIVE"}:
            continue
        role = _get_value(assignment, "role")
        role_key = _get_value(role, "role_key") if role else None
        if role_key:
            role_values.append(role_key)

    return {
        normalized
        for normalized in (normalize_role_code(value) for value in role_values)
        if normalized
    }


def can_open_user_role_admin(actor: Any) -> bool:
    return is_platform_admin_actor(actor) or is_company_admin_actor(actor)


def is_platform_admin_actor(actor: Any) -> bool:
    return bool(active_role_codes_for_user(actor) & PLATFORM_ADMIN_UI_ROLE_CODES)


def is_company_admin_actor(actor: Any) -> bool:
    return bool(company_admin_workspace_ids(actor))


def can_assign_role_code(actor: Any, role_code: str) -> bool:
    actor_roles = active_role_codes_for_user(actor)
    target_role = normalize_role_code(role_code)
    if not target_role or not can_open_user_role_admin(actor):
        return False
    if not is_platform_admin_actor(actor):
        return False
    if target_role in PROTECTED_ROLE_CODES and "SUPER_ADMIN" not in actor_roles:
        return False
    return True


def can_disable_user(actor: Any, target_user: Any) -> bool:
    actor_roles = active_role_codes_for_user(actor)
    target_roles = active_role_codes_for_user(target_user)
    if not is_platform_admin_actor(actor):
        return False
    if target_roles & PROTECTED_ROLE_CODES and "SUPER_ADMIN" not in actor_roles:
        return False
    if str(_get_value(actor, "id") or _get_value(actor, "userId") or "") == str(_get_value(target_user, "id") or ""):
        return False
    return True


def is_company_admin_role(role_code: Any) -> bool:
    normalized = normalize_role_code(role_code) or _enum_value(role_code)
    return normalized in COMPANY_ADMIN_COMPATIBLE_ROLE_CODES


def company_admin_workspace_ids(actor: Any) -> set[str]:
    ids: set[str] = set()
    members = _safe_iterable(_get_value(actor, "workspace_members"))
    members.extend(_safe_iterable(_get_value(actor, "workspaces")))
    for member in members:
        status = _enum_value(_get_value(member, "status")).upper()
        role_code = _get_value(member, "roleCode") or _get_value(member, "role_code") or _get_value(member, "role_key")
        workspace_id = _get_value(member, "workspace_id") or _get_value(member, "workspaceId") or _get_value(member, "id")
        if workspace_id and status in {"", "ACTIVE"} and is_company_admin_role(role_code):
            ids.add(str(workspace_id))
    return ids


def admin_scope_for_actor(actor: Any) -> dict[str, Any]:
    actor_roles = sorted(active_role_codes_for_user(actor))
    company_workspace_ids = sorted(company_admin_workspace_ids(actor))
    is_platform_admin = bool(set(actor_roles) & PLATFORM_ADMIN_UI_ROLE_CODES)
    is_company_admin = bool(company_workspace_ids) and not is_platform_admin
    return {
        "mode": "platform" if is_platform_admin else "company" if is_company_admin else "none",
        "isPlatformAdminMode": is_platform_admin,
        "isCompanyAdminMode": is_company_admin,
        "actorRoleCodes": actor_roles,
        "companyWorkspaceIds": company_workspace_ids,
        "companyWorkspaceCount": len(company_workspace_ids),
        "canSeeSystemSettings": is_platform_admin,
        "canSeeRegistryDiagnostics": is_platform_admin,
        "canSeeSystemCriticalModules": is_platform_admin,
        "canManageOtherCompanies": is_platform_admin,
        "canAssignPlatformRoles": is_platform_admin,
    }


def can_assign_company_admin(actor: Any, workspace: Workspace | dict[str, Any]) -> bool:
    if not _is_company_workspace(workspace) or not _workspace_is_active(workspace):
        return False
    return bool(active_role_codes_for_user(actor) & COMPANY_ADMIN_ASSIGNER_ROLE_CODES)


def can_manage_company_employee(actor: Any, workspace: Workspace | dict[str, Any], employee_member: Any) -> bool:
    if not _is_company_workspace(workspace) or not _workspace_is_active(workspace):
        return False
    workspace_id = _workspace_id(workspace)
    if not workspace_id:
        return False
    member_workspace_id = _get_value(employee_member, "workspace_id") or _get_value(employee_member, "workspaceId")
    if str(member_workspace_id) != str(workspace_id):
        return False
    actor_roles = active_role_codes_for_user(actor)
    if actor_roles & COMPANY_ADMIN_ASSIGNER_ROLE_CODES:
        return True
    if str(workspace_id) not in company_admin_workspace_ids(actor):
        return False
    target_user = _get_value(employee_member, "user")
    if active_role_codes_for_user(target_user) & COMPANY_ADMIN_ASSIGNER_ROLE_CODES:
        return False
    return True


def require_can_manage_company_employee(actor: Any, workspace: Workspace | dict[str, Any], employee_member: Any) -> None:
    if not can_manage_company_employee(actor, workspace, employee_member):
        raise ForbiddenError("Company admin can manage employees only inside the assigned company workspace.")


def company_module_is_open(workspace: Workspace | dict[str, Any], module_code: str | None) -> bool:
    if not _workspace_is_active(workspace) or not module_code:
        return False
    module_item = get_dashboard_module_registry_item(module_code)
    if module_item and not module_item.isAvailableForDashboard:
        return False
    if module_item and module_item.status != "active":
        return False
    canonical = _canonical_module_code_value(module_code)
    for rule in _safe_iterable(_get_value(workspace, "module_access") or _get_value(workspace, "moduleAccess")):
        if _enum_value(_get_value(rule, "status")).upper() not in {"", "ACTIVE"}:
            continue
        rule_code = _get_value(rule, "canonical_module_code") or _get_value(rule, "canonicalModuleCode") or _get_value(rule, "module_code") or _get_value(rule, "moduleCode")
        if _canonical_module_code_value(rule_code) != canonical:
            continue
        access_level = _enum_value(_get_value(rule, "access_level") or _get_value(rule, "accessLevel")).upper()
        if access_level in {"NO_ACCESS", "DENY", "CLOSED", "DISABLED"}:
            return False
        if access_level:
            return True
    return True


def company_widget_is_open(workspace: Workspace | dict[str, Any], widget_code: str | None) -> bool:
    if not _workspace_is_active(workspace) or not widget_code:
        return False
    widget = get_widget_registry_item(widget_code)
    if not widget or widget.status != "ACTIVE":
        return False
    if not company_module_is_open(workspace, widget.canonicalModuleCode or widget.sourceModuleCode):
        return False
    for rule in _safe_iterable(_get_value(workspace, "function_access") or _get_value(workspace, "widgetAccess")):
        if _enum_value(_get_value(rule, "status")).upper() not in {"", "ACTIVE"}:
            continue
        rule_key = _get_value(rule, "function_key") or _get_value(rule, "functionKey") or _get_value(rule, "widgetCode")
        if str(rule_key) != widget_code:
            continue
        access_level = _enum_value(_get_value(rule, "access_level") or _get_value(rule, "accessLevel")).upper()
        if access_level in {"NO_ACCESS", "DENY", "CLOSED", "DISABLED"}:
            return False
        if access_level:
            return True
    return True


def can_company_admin_open_employee_module(
    actor: Any,
    workspace: Workspace | dict[str, Any],
    employee_member: Any,
    module_code: str | None,
) -> bool:
    return can_manage_company_employee(actor, workspace, employee_member) and company_module_is_open(workspace, module_code)


def can_company_admin_open_employee_widget(
    actor: Any,
    workspace: Workspace | dict[str, Any],
    employee_member: Any,
    widget_code: str | None,
) -> bool:
    return can_manage_company_employee(actor, workspace, employee_member) and company_widget_is_open(workspace, widget_code)


def require_user_role_admin(actor: Any) -> None:
    if not can_open_user_role_admin(actor):
        raise ForbiddenError("User and role administration requires PLATFORM_ADMIN or SUPER_ADMIN.")


def require_can_assign_role(actor: Any, role_code: str) -> None:
    if not can_assign_role_code(actor, role_code):
        raise ForbiddenError("Only SUPER_ADMIN can assign protected platform owner roles.")


def require_can_disable_user(actor: Any, target_user: Any, confirmation: str | None) -> None:
    if confirmation != DISABLE_CONFIRMATION:
        raise ValidationError(f"Confirm dangerous action with {DISABLE_CONFIRMATION}.")
    if not can_disable_user(actor, target_user):
        raise ForbiddenError("This user cannot be disabled by the current administrator.")


async def load_actor_with_roles(db: AsyncSession, actor: User | dict[str, Any]) -> User | dict[str, Any]:
    actor_id = _get_value(actor, "id")
    if not actor_id:
        return actor
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role_assignments).selectinload(UserRoleAssignment.role),
            selectinload(User.workspace_members).selectinload(WorkspaceMember.workspace),
        )
        .where(User.id == actor_id)
    )
    return result.scalar_one_or_none() or actor


def module3_quick_actions(*, admin_scope: dict[str, Any], detail_mode: bool = False) -> list[dict[str, Any]]:
    is_company_admin = bool(admin_scope.get("isCompanyAdminMode"))
    actions: list[dict[str, Any]] = []
    for action in MODULE3_QUICK_ACTIONS:
        if is_company_admin and not action.get("visibleForCompanyAdmin"):
            continue
        target = action.get("detailTarget") if detail_mode and action.get("detailTarget") else action.get("target")
        actions.append(
            {
                "id": action["id"],
                "label": action["label"],
                "icon": action.get("icon"),
                "permissionCode": action.get("permissionCode"),
                "featureCode": action.get("featureCode"),
                "visible": True,
                "enabled": bool(action.get("enabled", True)),
                "actionType": action.get("actionType", "navigate"),
                "target": target,
                "description": action.get("description"),
            }
        )
    return actions


async def get_user_role_admin_overview(db: AsyncSession, actor: Any) -> dict[str, Any]:
    require_user_role_admin(actor)
    admin_scope = admin_scope_for_actor(actor)
    users = await _load_users(db)
    roles = await _load_role_options(db, actor)
    workspaces = await _load_workspaces(db)
    users = _filter_users_for_admin_scope(users, admin_scope)
    roles = _filter_roles_for_admin_scope(roles, admin_scope)
    workspaces = _filter_workspaces_for_admin_scope(workspaces, admin_scope)
    recent_history = await _load_recent_access_history(db, workspace_ids=_workspace_uuid_scope(admin_scope))
    recent_history = _filter_history_for_admin_scope(recent_history, admin_scope)
    pending_items = [] if admin_scope["isCompanyAdminMode"] else pending_access_distribution_items()
    access_distribution_panel = access_distribution_panel_summary(pending_items)
    summary = _overview_summary(users, workspaces, recent_history, pending_items=pending_items)
    return {
        "actorRoleCodes": sorted(active_role_codes_for_user(actor)),
        "adminScope": admin_scope,
        "users": [user_summary(user) for user in users],
        "roles": roles,
        "workspaces": [workspace_summary(workspace) for workspace in workspaces],
        "companies": [company_summary(workspace) for workspace in workspaces if _is_company_workspace(workspace)],
        "companyEmployees": company_employee_summaries(workspaces),
        "groups": access_group_summaries(roles),
        "workspacePanel": workspace_panel_summary(workspaces, recent_history=recent_history),
        "roleGroupPanel": role_group_panel_summary(
            roles,
            users=users,
            workspaces=workspaces,
            recent_history=recent_history,
            admin_scope=admin_scope,
        ),
        "summary": summary,
        "pendingAccessDistributionItems": pending_items,
        "accessDistributionPanel": access_distribution_panel,
        "moduleQuickActions": module3_quick_actions(admin_scope=admin_scope, detail_mode=False),
        "recentAccessHistory": [audit_log_summary(item) for item in recent_history],
        "auditPanel": audit_panel_summary(recent_history),
        "settingsPanel": settings_panel_summary(admin_scope),
        "stateLegend": list(ADMIN_UI_STATE_LEGEND),
    }


async def get_user_role_admin_detail(db: AsyncSession, user_id: UUID, actor: Any) -> dict[str, Any]:
    require_user_role_admin(actor)
    admin_scope = admin_scope_for_actor(actor)
    user = await _get_user(db, user_id)
    _require_user_visible_to_admin_scope(user, admin_scope)
    roles = await _load_role_options(db, actor)
    workspaces = await _load_workspaces(db)
    roles = _filter_roles_for_admin_scope(roles, admin_scope)
    workspaces = _filter_workspaces_for_admin_scope(workspaces, admin_scope)
    history = await _load_user_history(db, user_id)
    history = _filter_history_for_admin_scope(history, admin_scope)
    user_data = user_summary(user, include_permissions=True)
    apply_company_context_to_user_summary(user_data, workspaces)
    access_context = build_access_context_for_cabinet(user_data)
    module8_preview = get_module8_cabinet_admin_preview(
        user_data,
        access_context=access_context,
    )
    module8_preview_data = module8_preview.to_dict()
    permissions = active_permissions_for_user(user)
    await write_audit_event(
        db,
        AuditLogType.MODULE8_CONTEXT_ADAPTER_READ,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        workspace_id=module8_preview_data.get("workspaceId") or access_context.workspaceId,
        module_code="MODULE_08_PARTNER_PORTAL",
        canonical_module_code="MODULE_08_PARTNER_PORTAL",
        reason="Module 03 Admin UI read Module 08 cabinet context through adapter/DTO.",
        entity_type="Module8CabinetAdminPreviewDTO",
        entity_id=module8_preview_data.get("activeCabinetId"),
        metadata={
            "sourceModuleCode": "MODULE_08_PARTNER_PORTAL",
            "activeRegionCode": module8_preview_data.get("activeRegionCode") or access_context.activeRegionCode,
            "activeCabinetType": module8_preview_data.get("activeCabinetType"),
            "isMock": module8_preview_data.get("isMock", True),
            "cabinetCount": len(module8_preview_data.get("cabinets") or []),
            "businessPayloadLogged": False,
        },
    )
    return {
        "actorRoleCodes": sorted(active_role_codes_for_user(actor)),
        "adminScope": admin_scope,
        "user": user_data,
        "roles": roles,
        "workspaces": [workspace_summary(workspace) for workspace in workspaces],
        "companies": [company_summary(workspace) for workspace in workspaces if _is_company_workspace(workspace)],
        "companyEmployees": company_employee_summaries(workspaces),
        "groups": access_group_summaries(roles),
        "workspacePanel": workspace_panel_summary(workspaces, recent_history=history),
        "roleGroupPanel": role_group_panel_summary(
            roles,
            users=[user],
            workspaces=workspaces,
            recent_history=history,
            admin_scope=admin_scope,
        ),
        "permissions": permissions,
        "accessMatrix": access_matrix_for_subject(
            user_data,
            workspaces=workspaces,
            roles=roles,
            permissions=permissions,
            include_system_critical=admin_scope["canSeeSystemCriticalModules"],
        ),
        "accessContextForCabinet": access_context.to_dict(),
        "module8CabinetPreview": module8_preview_data,
        "moduleQuickActions": module3_quick_actions(admin_scope=admin_scope, detail_mode=True),
        "widgetAccessRows": widget_access_rows_for_user(
            user_data,
            access_context=access_context.to_dict(),
            module8_preview=module8_preview_data,
        ),
        "quickActionRows": quick_action_rows_for_user(
            user_data,
            access_context=access_context.to_dict(),
            module8_preview=module8_preview_data,
        ),
        "stateLegend": list(ADMIN_UI_STATE_LEGEND),
        "history": [audit_log_summary(item) for item in history],
        "changeHistory": change_history_for_admin_panel(history, user_data),
        "auditPanel": audit_panel_summary(history),
        "settingsPanel": settings_panel_summary(admin_scope),
        "canDisable": can_disable_user(actor, user),
        "disableConfirmation": DISABLE_CONFIRMATION,
    }


async def assign_role_to_user(
    db: AsyncSession,
    *,
    actor: Any,
    user_id: UUID,
    role_code: str,
    workspace_id: UUID | None = None,
) -> UserRoleAssignment:
    require_can_assign_role(actor, role_code)
    user = await _get_user(db, user_id)
    normalized_role_code = normalize_role_code(role_code)
    if not normalized_role_code:
        raise ValidationError("Role code is required.")

    role = await _get_or_create_role(db, normalized_role_code)
    workspace = await _get_workspace(db, workspace_id) if workspace_id else None

    filters = [
        UserRoleAssignment.user_id == user.id,
        UserRoleAssignment.role_id == role.id,
        UserRoleAssignment.status == "ACTIVE",
    ]
    if workspace_id:
        filters.append(UserRoleAssignment.workspace_id == workspace_id)
    else:
        filters.append(UserRoleAssignment.workspace_id.is_(None))

    result = await db.execute(select(UserRoleAssignment).where(*filters))
    assignment = result.scalar_one_or_none()
    if assignment is None:
        assignment = UserRoleAssignment(
            user_id=user.id,
            role_id=role.id,
            workspace_id=workspace.id if workspace else None,
            status="ACTIVE",
        )
        db.add(assignment)
    else:
        assignment.updated_at = datetime.utcnow()

    if workspace:
        await _upsert_workspace_member(db, user, workspace, normalized_role_code)

    await write_audit_event(
        db,
        AuditLogType.ROLE_CHANGED,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        workspace_id=workspace.id if workspace else None,
        role_code=normalized_role_code,
        old_value=None,
        new_value={"roleCode": normalized_role_code, "workspaceId": str(workspace.id) if workspace else None},
        reason="Role assignment through Module 03 admin UI.",
        entity_type="User",
        entity_id=user.id,
        metadata={"rule": "PLATFORM_ADMIN cannot assign SUPER_ADMIN"},
    )
    _add_audit_log(
        db,
        actor,
        action_type="user_role_assigned",
        target_user=user,
        workspace_id=workspace.id if workspace else None,
        details={
            "roleCode": normalized_role_code,
            "workspaceId": str(workspace.id) if workspace else None,
            "rule": "PLATFORM_ADMIN cannot assign SUPER_ADMIN",
        },
    )
    await db.flush()
    return assignment


async def assign_workspace_to_user(
    db: AsyncSession,
    *,
    actor: Any,
    user_id: UUID,
    workspace_id: UUID,
    role_code: str,
) -> WorkspaceMember:
    require_can_assign_role(actor, role_code)
    user = await _get_user(db, user_id)
    workspace = await _get_workspace(db, workspace_id)
    normalized_role_code = normalize_role_code(role_code)
    if not normalized_role_code:
        raise ValidationError("Role code is required.")
    await _get_or_create_role(db, normalized_role_code)
    member = await _upsert_workspace_member(db, user, workspace, normalized_role_code)
    await write_audit_event(
        db,
        AuditLogType.ROLE_CHANGED,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        workspace_id=workspace.id,
        role_code=normalized_role_code,
        old_value=None,
        new_value={"workspaceId": str(workspace.id), "roleCode": normalized_role_code},
        reason="Workspace role assignment through Module 03 admin UI.",
        entity_type="User",
        entity_id=user.id,
    )
    _add_audit_log(
        db,
        actor,
        action_type="user_workspace_assigned",
        target_user=user,
        workspace_id=workspace.id,
        details={"workspaceId": str(workspace.id), "roleCode": normalized_role_code},
    )
    await db.flush()
    return member


async def assign_company_admin(
    db: AsyncSession,
    *,
    actor: Any,
    user_id: UUID,
    workspace_id: UUID,
) -> WorkspaceMember:
    user = await _get_user(db, user_id)
    workspace = await _get_workspace(db, workspace_id)
    if not can_assign_company_admin(actor, workspace):
        raise ForbiddenError("Only platform administrators can assign a company administrator.")
    old_member = await _get_workspace_member(db, user.id, workspace.id)
    old_role = old_member.roleCode if old_member else None
    member = await _upsert_workspace_member(db, user, workspace, COMPANY_ADMIN_ROLE_CODE)
    await write_audit_event(
        db,
        AuditLogType.ROLE_CHANGED,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        workspace_id=workspace.id,
        role_code=COMPANY_ADMIN_ROLE_CODE,
        old_value={"roleCode": old_role, "workspaceId": str(workspace.id)},
        new_value={"roleCode": COMPANY_ADMIN_ROLE_CODE, "workspaceId": str(workspace.id)},
        reason="Company administrator assigned through Module 03 admin UI.",
        entity_type="WorkspaceMember",
        entity_id=member.id,
        metadata={"scope": "company_only", "canExceedCompanyAccess": False},
    )
    _add_audit_log(
        db,
        actor,
        action_type="company_admin_assigned",
        target_user=user,
        workspace_id=workspace.id,
        details={
            "oldRoleCode": old_role,
            "newRoleCode": COMPANY_ADMIN_ROLE_CODE,
            "workspaceId": str(workspace.id),
            "scope": "company_only",
        },
    )
    await db.flush()
    return member


async def revoke_company_admin(
    db: AsyncSession,
    *,
    actor: Any,
    user_id: UUID,
    workspace_id: UUID,
    fallback_role_code: str = COMPANY_ADMIN_FALLBACK_ROLE_CODE,
) -> WorkspaceMember:
    user = await _get_user(db, user_id)
    workspace = await _get_workspace(db, workspace_id)
    if not can_assign_company_admin(actor, workspace):
        raise ForbiddenError("Only platform administrators can revoke a company administrator.")
    normalized_fallback = normalize_role_code(fallback_role_code) or fallback_role_code
    if normalized_fallback in PROTECTED_ROLE_CODES or normalized_fallback in COMPANY_ADMIN_ASSIGNER_ROLE_CODES:
        raise ValidationError("Company admin fallback role cannot be a platform administrator role.")
    old_member = await _get_workspace_member(db, user.id, workspace.id)
    old_role = old_member.roleCode if old_member else None
    member = await _upsert_workspace_member(db, user, workspace, normalized_fallback)
    await write_audit_event(
        db,
        AuditLogType.ROLE_CHANGED,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        workspace_id=workspace.id,
        role_code=normalized_fallback,
        old_value={"roleCode": old_role, "workspaceId": str(workspace.id)},
        new_value={"roleCode": normalized_fallback, "workspaceId": str(workspace.id)},
        reason="Company administrator revoked through Module 03 admin UI.",
        entity_type="WorkspaceMember",
        entity_id=member.id,
        metadata={"scope": "company_only", "companyAdminRevoked": True},
    )
    _add_audit_log(
        db,
        actor,
        action_type="company_admin_revoked",
        target_user=user,
        workspace_id=workspace.id,
        details={
            "oldRoleCode": old_role,
            "newRoleCode": normalized_fallback,
            "workspaceId": str(workspace.id),
        },
    )
    await db.flush()
    return member


async def assign_company_employee_role(
    db: AsyncSession,
    *,
    actor: Any,
    user_id: UUID,
    workspace_id: UUID,
    role_code: str,
) -> WorkspaceMember:
    user = await _get_user(db, user_id)
    workspace = await _get_workspace(db, workspace_id)
    member = await _get_workspace_member(db, user.id, workspace.id)
    if member is None:
        raise NotFoundError("Company employee link not found.")
    require_can_manage_company_employee(actor, workspace, member)
    normalized_role_code = normalize_role_code(role_code) or role_code
    if normalized_role_code in COMPANY_ADMIN_ASSIGNER_ROLE_CODES or normalized_role_code in PROTECTED_ROLE_CODES:
        raise ForbiddenError("Company admin cannot assign platform administrator roles.")
    old_role = member.roleCode
    member.roleCode = normalized_role_code
    member.status = "ACTIVE"
    member.updated_at = datetime.utcnow()
    await write_audit_event(
        db,
        AuditLogType.ROLE_CHANGED,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        workspace_id=workspace.id,
        role_code=normalized_role_code,
        old_value={"roleCode": old_role},
        new_value={"roleCode": normalized_role_code},
        reason="Company employee role changed inside company workspace.",
        entity_type="WorkspaceMember",
        entity_id=member.id,
        metadata={"scope": "company_only"},
    )
    _add_audit_log(
        db,
        actor,
        action_type="company_employee_role_changed",
        target_user=user,
        workspace_id=workspace.id,
        details={"oldRoleCode": old_role, "newRoleCode": normalized_role_code},
    )
    await db.flush()
    return member


async def set_company_employee_module_access(
    db: AsyncSession,
    *,
    actor: Any,
    user_id: UUID,
    workspace_id: UUID,
    module_code: str,
    access_level: str,
    access_scope: str = "OWN",
) -> ModuleAccess:
    user = await _get_user(db, user_id)
    workspace = await _get_workspace(db, workspace_id)
    member = await _get_workspace_member(db, user.id, workspace.id)
    if member is None:
        raise NotFoundError("Company employee link not found.")
    require_can_manage_company_employee(actor, workspace, member)
    normalized_level = _enum_value(access_level).upper()
    if normalized_level not in {"NO_ACCESS", "DENY", "CLOSED"} and not company_module_is_open(workspace, module_code):
        raise ForbiddenError("Cannot open an employee module that is closed for the company.")
    canonical = _canonical_module_code_value(module_code)
    access = await _get_or_create_user_module_access(db, user.id, workspace.id, module_code, canonical)
    old_value = {"accessLevel": access.access_level, "accessScope": access.access_scope}
    access.access_level = normalized_level
    access.access_scope = _enum_value(access_scope).upper() or "OWN"
    access.status = "ACTIVE"
    access.updated_at = datetime.utcnow()
    revoked_widget_count = 0
    if normalized_level in {"NO_ACCESS", "DENY", "CLOSED"}:
        revoked_widget_count = await _auto_revoke_employee_widgets_for_module(
            db,
            user_id=user.id,
            workspace_id=workspace.id,
            module_code=canonical,
        )
    await write_audit_event(
        db,
        AuditLogType.PERMISSION_CHANGED,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        workspace_id=workspace.id,
        module_code=module_code,
        canonical_module_code=canonical,
        old_value=old_value,
        new_value={"accessLevel": access.access_level, "accessScope": access.access_scope},
        reason="Company employee module access changed inside company workspace.",
        entity_type="ModuleAccess",
        entity_id=access.id,
        metadata={
            "scope": "company_only",
            "companyAccessChecked": True,
            "revokedWidgetCount": revoked_widget_count,
            "revokedWidgetReason": "WIDGET_REVOKED_BY_MODULE_DENY" if revoked_widget_count else None,
        },
    )
    await db.flush()
    return access


async def set_company_employee_widget_access(
    db: AsyncSession,
    *,
    actor: Any,
    user_id: UUID,
    workspace_id: UUID,
    widget_code: str,
    access_level: str,
    access_scope: str = "OWN",
) -> FunctionAccess:
    user = await _get_user(db, user_id)
    workspace = await _get_workspace(db, workspace_id)
    member = await _get_workspace_member(db, user.id, workspace.id)
    if member is None:
        raise NotFoundError("Company employee link not found.")
    require_can_manage_company_employee(actor, workspace, member)
    normalized_level = _enum_value(access_level).upper()
    if normalized_level not in {"NO_ACCESS", "DENY", "CLOSED"} and not company_widget_is_open(workspace, widget_code):
        raise ForbiddenError("Cannot open an employee widget that is closed for the company.")
    widget = get_widget_registry_item(widget_code)
    module_code = (widget.canonicalModuleCode or widget.sourceModuleCode) if widget else None
    access = await _get_or_create_user_widget_access(db, user.id, workspace.id, widget_code, module_code, widget.featureCode if widget else None)
    old_value = {"accessLevel": access.access_level, "accessScope": access.access_scope}
    access.access_level = normalized_level
    access.access_scope = _enum_value(access_scope).upper() or "OWN"
    access.status = "ACTIVE"
    access.updated_at = datetime.utcnow()
    await write_audit_event(
        db,
        AuditLogType.WIDGET_PERMISSION_CHANGED,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        workspace_id=workspace.id,
        module_code=module_code,
        canonical_module_code=module_code,
        widget_code=widget_code,
        old_value=old_value,
        new_value={"accessLevel": access.access_level, "accessScope": access.access_scope},
        reason="Company employee widget access changed inside company workspace.",
        entity_type="FunctionAccess",
        entity_id=access.id,
        metadata={"scope": "company_only", "companyAccessChecked": True},
    )
    await db.flush()
    return access


async def disable_user_account(
    db: AsyncSession,
    *,
    actor: Any,
    user_id: UUID,
    confirmation: str | None,
) -> User:
    user = await _get_user(db, user_id)
    require_can_disable_user(actor, user, confirmation)
    old_status = _enum_value(user.status)
    user.status = UserStatus.BLOCKED
    user.updated_at = datetime.utcnow()
    await write_audit_event(
        db,
        AuditLogType.PERMISSION_CHANGED,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        old_value={"status": old_status},
        new_value={"status": UserStatus.BLOCKED.value},
        reason="User disabled through Module 03 admin UI.",
        entity_type="User",
        entity_id=user.id,
        metadata={"confirmation": confirmation},
    )
    _add_audit_log(
        db,
        actor,
        action_type="user_disabled",
        target_user=user,
        details={"status": UserStatus.BLOCKED.value, "confirmation": confirmation},
    )
    await db.flush()
    return user


def user_summary(user: User, *, include_permissions: bool = False) -> dict[str, Any]:
    role_codes = sorted(active_role_codes_for_user(user))
    permissions = active_permissions_for_user(user)
    allowed_module_codes = {
        permission["moduleCode"]
        for permission in permissions
        if permission.get("moduleCode") and permission.get("accessLevel") != "NO_ACCESS"
    }
    allowed_feature_codes = {
        permission["featureCode"]
        for permission in permissions
        if permission.get("featureCode") and permission.get("accessLevel") != "NO_ACCESS"
    }
    workspaces = [
        workspace_member_summary(member)
        for member in sorted(
            _safe_iterable(user.workspace_members),
            key=lambda item: (_get_value(_get_value(item, "workspace"), "name") or ""),
        )
        if _enum_value(member.status) == "ACTIVE"
    ]
    data = {
        "id": str(user.id),
        "email": user.email,
        "name": user.name or user.email,
        "phone": user.phone,
        "status": _enum_value(user.status),
        "roleCodes": role_codes,
        "roleTitle": ", ".join(role_label(code) for code in role_codes) or "Нет роли",
        "groupTitles": [role_label(code) for code in role_codes],
        "allowedModuleCount": len(allowed_module_codes),
        "allowedFeatureCount": len(allowed_feature_codes),
        "workspaces": workspaces,
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
    }
    if include_permissions:
        data["permissions"] = permissions
    return data


def workspace_member_summary(member: WorkspaceMember) -> dict[str, Any]:
    workspace = member.workspace
    return {
        "workspaceId": str(member.workspace_id),
        "workspaceTitle": workspace.name if workspace else str(member.workspace_id),
        "workspaceType": workspace.type if workspace else None,
        "roleCode": member.roleCode,
        "roleTitle": role_label(member.roleCode),
        "status": member.status,
    }


def apply_company_context_to_user_summary(user_data: dict[str, Any], workspaces: list[Workspace]) -> None:
    companies_by_id = {
        str(workspace.id): company_summary(workspace)
        for workspace in workspaces
        if _is_company_workspace(workspace)
    }
    for member in user_data.get("workspaces", []):
        company = companies_by_id.get(str(member.get("workspaceId")))
        if not company:
            continue
        member.update({
            "companyStatus": company["status"],
            "isCompanyActive": company["isActive"],
            "employeeCount": company["employeeCount"],
            "adminTitle": company["adminTitle"],
            "moduleAccessState": company["moduleAccessState"],
            "widgetAccessState": company["widgetAccessState"],
        })


def workspace_summary(workspace: Workspace) -> dict[str, Any]:
    return {
        "id": str(workspace.id),
        "title": workspace.title,
        "type": workspace.type,
        "isActive": workspace.isActive,
        "status": workspace.status,
    }


def company_summary(workspace: Workspace) -> dict[str, Any]:
    members = list(_safe_iterable(workspace.members))
    admins = [
        member
        for member in members
        if is_company_admin_role(member.roleCode)
    ]
    return {
        "id": str(workspace.id),
        "title": workspace.title,
        "type": workspace.type,
        "status": workspace.status,
        "isActive": workspace.isActive,
        "employeeCount": len(members),
        "adminCount": len(admins),
        "adminTitle": _company_admin_title(admins),
        "moduleAccessState": "открыто в пределах платформы" if workspace.isActive else "закрыто: компания заблокирована",
        "widgetAccessState": "следует доступу компании к модулям" if workspace.isActive else "закрыто вместе с компанией",
    }


def company_employee_summaries(workspaces: list[Workspace]) -> list[dict[str, Any]]:
    employees: list[dict[str, Any]] = []
    for workspace in workspaces:
        if not _is_company_workspace(workspace):
            continue
        for member in _safe_iterable(workspace.members):
            user = member.user
            employees.append(
                {
                    "id": str(member.id),
                    "userId": str(member.user_id),
                    "userName": _get_value(user, "name") or _get_value(user, "email") or str(member.user_id),
                    "userEmail": _get_value(user, "email"),
                    "companyId": str(workspace.id),
                    "companyTitle": workspace.title,
                    "companyType": workspace.type,
                    "roleCode": member.roleCode,
                    "roleTitle": role_label(member.roleCode),
                    "status": member.status,
                    "accessBoundary": "только в пределах доступа компании",
                }
            )
    return sorted(employees, key=lambda item: (item["companyTitle"], item["userName"]))


def workspace_panel_summary(workspaces: list[Workspace], *, recent_history: list[AuditLog]) -> dict[str, Any]:
    cards = [_workspace_card_summary(workspace, recent_history=recent_history) for workspace in workspaces]
    selected = next((card for card in cards if card["isCompany"]), cards[0] if cards else None)
    active_count = len([card for card in cards if card["isActive"]])
    company_count = len([card for card in cards if card["isCompany"]])
    user_count = sum(card["memberCount"] for card in cards)
    return {
        "workspaces": cards,
        "selectedWorkspace": selected,
        "summary": {
            "total": len(cards),
            "active": active_count,
            "blocked": len(cards) - active_count,
            "companies": company_count,
            "linkedUsers": user_count,
        },
        "notes": {
            "dashboardLayoutEditor": False,
            "technicalDashboardPresetsHidden": True,
            "description": "Рабочие области показывают связь пользователей и компаний. Dashboard layout здесь не редактируется.",
        },
    }


def _workspace_card_summary(workspace: Workspace, *, recent_history: list[AuditLog]) -> dict[str, Any]:
    members = list(_safe_iterable(workspace.members))
    companies = [workspace] if _is_company_workspace(workspace) else []
    admins = [member for member in members if is_company_admin_role(member.roleCode)]
    history = [
        audit_log_summary(item)
        for item in recent_history
        if str(_get_value(item, "workspace_id") or "") == str(workspace.id)
        or str((item.details or {}).get("workspaceId") or "") == str(workspace.id)
    ][:4]
    return {
        "id": str(workspace.id),
        "title": workspace.title,
        "type": workspace.type,
        "status": workspace.status,
        "isActive": workspace.isActive,
        "isCompany": _is_company_workspace(workspace),
        "memberCount": len(members),
        "companyCount": len(companies),
        "adminTitle": _company_admin_title(admins) if companies else "не требуется",
        "linkedUsers": [_workspace_member_preview(member) for member in members[:6]],
        "linkedCompanies": [
            {
                "id": str(company.id),
                "title": company.title,
                "type": company.type,
                "status": company.status,
            }
            for company in companies
        ],
        "history": history,
        "moduleAccessState": "открыто в пределах платформы" if workspace.isActive else "закрыто: workspace заблокирован",
        "widgetAccessState": "следует доступу workspace к модулям" if workspace.isActive else "закрыто вместе с workspace",
    }


def _workspace_member_preview(member: WorkspaceMember) -> dict[str, Any]:
    user = member.user
    return {
        "id": str(member.id),
        "userId": str(member.user_id),
        "name": _get_value(user, "name") or _get_value(user, "email") or str(member.user_id),
        "email": _get_value(user, "email"),
        "roleTitle": role_label(member.roleCode),
        "status": member.status,
    }


def access_group_summaries(roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "groupCode": "SYSTEM_ROLES",
            "title": "Системные роли",
            "description": "Базовые группы доступа платформы. Code системных ролей не переименовывается.",
            "itemCount": len([role for role in roles if role.get("isSystem")]),
        },
        {
            "groupCode": "COMPANY_ACCESS_GROUPS",
            "title": "Группы компаний",
            "description": "Будущий слой группировки сотрудников внутри компании без обхода прав компании.",
            "itemCount": 0,
        },
    ]


def role_group_panel_summary(
    roles: list[dict[str, Any]],
    *,
    users: list[User],
    workspaces: list[Workspace],
    recent_history: list[AuditLog],
    admin_scope: dict[str, Any],
) -> dict[str, Any]:
    role_cards = [
        _role_card_summary(
            role,
            users=users,
            workspaces=workspaces,
            recent_history=recent_history,
            admin_scope=admin_scope,
        )
        for role in roles
    ]
    group_cards = _role_group_cards(role_cards, recent_history=recent_history)
    return {
        "roles": role_cards,
        "groups": group_cards,
        "selectedRole": role_cards[0] if role_cards else None,
        "selectedGroup": group_cards[0] if group_cards else None,
        "technicalDetailsVisible": bool(admin_scope.get("canSeeSystemSettings")),
    }


def _role_card_summary(
    role: dict[str, Any],
    *,
    users: list[User],
    workspaces: list[Workspace],
    recent_history: list[AuditLog],
    admin_scope: dict[str, Any],
) -> dict[str, Any]:
    role_code = str(role.get("roleCode") or "")
    participants = _role_participants(role_code, users, workspaces)
    modules = _role_module_summaries(role_code, admin_scope=admin_scope)
    features = _role_feature_summaries(role_code)
    widgets = _role_widget_summaries(role_code)
    history = _history_for_role(recent_history, role_code)
    return {
        "roleCode": role_code,
        "title": role.get("title") or role_label(role_code),
        "description": role.get("description"),
        "isSystem": bool(role.get("isSystem")),
        "isAssignable": bool(role.get("isAssignable")),
        "memberCount": len(participants),
        "participants": participants[:5],
        "modules": modules,
        "features": features,
        "widgets": widgets,
        "history": history[:4],
        "technicalDetails": {
            "roleCode": role_code,
            "moduleCodes": [item["moduleCode"] for item in modules],
            "widgetCodes": [item["widgetCode"] for item in widgets],
            "featureCodes": [item["featureCode"] for item in features],
        },
    }


def _role_participants(role_code: str, users: list[User], workspaces: list[Workspace]) -> list[dict[str, Any]]:
    company_titles_by_id = {str(workspace.id): workspace.title for workspace in workspaces}
    participants: dict[str, dict[str, Any]] = {}
    for user in users:
        if _user_has_role_code(user, role_code):
            participants[str(user.id)] = {
                "userId": str(user.id),
                "name": _user_display_name(user),
                "email": user.email,
                "companyTitle": _first_user_company_title(user, company_titles_by_id),
            }
    return sorted(participants.values(), key=lambda item: (item["companyTitle"] or "", item["name"]))


def _role_module_summaries(role_code: str, *, admin_scope: dict[str, Any]) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    for rule in get_starter_role_module_access():
        if rule.get("roleCode") != role_code:
            continue
        module_code = _canonical_module_code_value(rule.get("moduleCode"))
        module_item = get_dashboard_module_registry_item(module_code)
        if module_item and module_item.isSystemCritical and not admin_scope.get("canSeeSystemCriticalModules"):
            continue
        modules.append(
            {
                "moduleCode": module_code or rule.get("moduleCode"),
                "title": _get_value(module_item, "title") or module_code or rule.get("moduleCode"),
                "accessLevel": rule.get("accessLevel"),
                "accessScope": rule.get("accessScope"),
            }
        )
    return modules


def _role_feature_summaries(role_code: str) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for rule in get_starter_role_feature_access():
        if rule.get("roleCode") != role_code:
            continue
        module_code = _canonical_module_code_value(rule.get("moduleCode")) or rule.get("moduleCode")
        module_item = get_dashboard_module_registry_item(module_code)
        features.append(
            {
                "moduleCode": module_code,
                "moduleTitle": _get_value(module_item, "title") or module_code,
                "featureCode": rule.get("featureCode"),
                "accessLevel": rule.get("accessLevel"),
                "accessScope": rule.get("accessScope"),
            }
        )
    return features


def _role_widget_summaries(role_code: str) -> list[dict[str, Any]]:
    profile = get_role_dashboard_access_profile(role_code) or {}
    widget_codes = _list_strings(profile.get("defaultWidgetCodes"))
    hidden_widgets = set(_list_strings(profile.get("hiddenWidgetCodes")))
    widgets: list[dict[str, Any]] = []
    for widget_code in widget_codes:
        widget = get_widget_registry_item(widget_code)
        if not widget:
            continue
        widgets.append(
            {
                "widgetCode": widget.widgetCode,
                "title": widget.title,
                "sourceModuleCode": widget.sourceModuleCode,
                "featureCode": widget.featureCode,
                "status": widget.status,
                "isHidden": widget.widgetCode in hidden_widgets,
            }
        )
    return widgets


def _role_group_cards(role_cards: list[dict[str, Any]], *, recent_history: list[AuditLog]) -> list[dict[str, Any]]:
    system_roles = [role for role in role_cards if role["isSystem"]]
    company_roles = [
        role
        for role in role_cards
        if role["roleCode"] in COMPANY_ADMIN_VISIBLE_ROLE_CODES or role["roleCode"] == COMPANY_ADMIN_ROLE_CODE
    ]
    groups = [
        {
            "groupCode": "SYSTEM_ROLES",
            "title": "Системные роли",
            "description": "Базовый набор ролей платформы. Code системной роли не переименовывается.",
            "roles": system_roles,
            "roleCount": len(system_roles),
            "memberCount": sum(role["memberCount"] for role in system_roles),
            "modules": _unique_role_group_modules(system_roles),
            "widgets": _unique_role_group_widgets(system_roles),
            "history": _history_for_group(recent_history, "SYSTEM_ROLES"),
        },
        {
            "groupCode": "COMPANY_ACCESS_GROUPS",
            "title": "Группы компаний",
            "description": "Внутренние роли сотрудников компании без выхода за пределы доступа компании.",
            "roles": company_roles,
            "roleCount": len(company_roles),
            "memberCount": sum(role["memberCount"] for role in company_roles),
            "modules": _unique_role_group_modules(company_roles),
            "widgets": _unique_role_group_widgets(company_roles),
            "history": _history_for_group(recent_history, "COMPANY_ACCESS_GROUPS"),
        },
    ]
    return groups


def _unique_role_group_modules(role_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    modules: dict[str, dict[str, Any]] = {}
    for role in role_cards:
        for module in role["modules"]:
            modules.setdefault(module["moduleCode"], module)
    return list(modules.values())[:8]


def _unique_role_group_widgets(role_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    widgets: dict[str, dict[str, Any]] = {}
    for role in role_cards:
        for widget in role["widgets"]:
            widgets.setdefault(widget["widgetCode"], widget)
    return list(widgets.values())[:8]


def _history_for_role(recent_history: list[AuditLog], role_code: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in recent_history:
        details = item.details or {}
        if details.get("roleCode") == role_code or details.get("newRoleCode") == role_code:
            result.append(audit_log_summary(item))
    return result


def _history_for_group(recent_history: list[AuditLog], group_code: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in recent_history:
        details = item.details or {}
        if details.get("groupCode") == group_code:
            result.append(audit_log_summary(item))
    return result[:4]


def _user_has_role_code(user: User, role_code: str) -> bool:
    if role_code in active_role_codes_for_user(user):
        return True
    for member in _safe_iterable(user.workspace_members):
        if _enum_value(_get_value(member, "status")).upper() not in {"", "ACTIVE"}:
            continue
        if normalize_role_code(_get_value(member, "role_code") or _get_value(member, "roleCode")) == role_code:
            return True
    return False


def _user_display_name(user: User) -> str:
    return str(_get_value(user, "name") or _get_value(user, "email") or user.id)


def _first_user_company_title(user: User, company_titles_by_id: dict[str, str]) -> str | None:
    for member in _safe_iterable(user.workspace_members):
        workspace_id = str(_get_value(member, "workspace_id") or _get_value(member, "workspaceId") or "")
        if workspace_id in company_titles_by_id:
            return company_titles_by_id[workspace_id]
    return None


def _company_admin_title(admins: list[WorkspaceMember]) -> str:
    if not admins:
        return "администратор не назначен"
    admin = admins[0]
    user = admin.user
    title = _get_value(user, "name") or _get_value(user, "email") or str(admin.user_id)
    if len(admins) > 1:
        return f"{title} +{len(admins) - 1}"
    return str(title)


def active_permissions_for_user(user: User) -> list[dict[str, Any]]:
    role_codes = active_role_codes_for_user(user)
    permissions: list[dict[str, Any]] = []
    for rule in get_starter_role_module_access():
        if rule["roleCode"] in role_codes:
            permissions.append({**rule, "kind": "module", "source": "role_matrix"})
    for rule in get_starter_role_feature_access():
        if rule["roleCode"] in role_codes:
            permissions.append({**rule, "kind": "feature", "source": "role_matrix"})
    for access in _safe_iterable(user.module_access):
        if _enum_value(_get_value(access, "status")) not in {"", "ACTIVE"}:
            continue
        permissions.append({
            "kind": "module",
            "source": "user_override",
            "roleCode": "USER_OVERRIDE",
            "moduleCode": access.module_code,
            "featureCode": None,
            "accessLevel": _enum_value(access.access_level),
            "accessScope": _enum_value(access.access_scope),
        })
    for access in _safe_iterable(user.function_access):
        if _enum_value(_get_value(access, "status")) not in {"", "ACTIVE"}:
            continue
        permissions.append({
            "kind": "feature",
            "source": "user_override",
            "roleCode": "USER_OVERRIDE",
            "moduleCode": access.module_code,
            "featureCode": access.feature_code or access.function_key,
            "accessLevel": _enum_value(access.access_level),
            "accessScope": _enum_value(access.access_scope),
        })
    return permissions


def access_matrix_for_subject(
    user_data: dict[str, Any],
    *,
    workspaces: list[Workspace],
    roles: list[dict[str, Any]],
    permissions: list[dict[str, Any]],
    include_system_critical: bool = True,
) -> dict[str, Any]:
    user_workspace_ids = {item.get("workspaceId") for item in user_data.get("workspaces", [])}
    selected_company = next(
        (
            workspace
            for workspace in workspaces
            if str(workspace.id) in user_workspace_ids and _is_company_workspace(workspace)
        ),
        None,
    )
    permission_map = _permission_map_by_module(permissions)
    pending_module_codes, pending_widget_codes = _pending_access_distribution_codes()
    rows = [
        _access_matrix_module_row(
            module,
            permission_map=permission_map,
            selected_company=selected_company,
            pending_module_codes=pending_module_codes,
            pending_widget_codes=pending_widget_codes,
        )
        for module in get_dashboard_module_registry()
        if module.get("status") not in {"merged", "archived", "deprecated"}
        and (include_system_critical or not module.get("isSystemCritical"))
    ]
    selected_module = next((row for row in rows if row["widgets"]), rows[0] if rows else None)
    return {
        "resolutionSources": list(ACCESS_RESOLUTION_SOURCES),
        "visibleStates": dict(VISIBLE_ACCESS_STATES),
        "denyReasons": dict(ACCESS_DENY_REASONS),
        "reasonCategories": dict(ACCESS_REASON_CATEGORIES),
        "monetizationReadyFields": list(MONETIZATION_READY_FIELDS),
        "columns": ["Пользователь", "Компания", "Сотрудник компании", "Группа", "Роль"],
        "rows": rows,
        "selectedModule": selected_module,
        "selectedModuleWidgets": selected_module["widgets"] if selected_module else [],
        "selectedCompanyTitle": selected_company.title if selected_company else None,
        "selectedCompanyId": str(selected_company.id) if selected_company else None,
        "noInheritanceUi": True,
    }


def _access_matrix_module_row(
    module: dict[str, Any],
    *,
    permission_map: dict[str, dict[str, Any]],
    selected_company: Workspace | None,
    pending_module_codes: set[str],
    pending_widget_codes: set[str],
) -> dict[str, Any]:
    module_code = module["canonicalModuleCode"] or module["moduleCode"]
    module_status = str(module.get("status") or "").lower()
    module_limit_code = _module_limit_reason_code(module)
    role_permission = permission_map.get(module_code)
    user_state = _module_access_cell(
        module_limit_code=module_limit_code,
        explicit_permission=role_permission,
        closed_reason="PLATFORM_ADMIN_DENY",
        open_reason="Открыто ролью или системным правилом.",
    )
    company_state = _company_module_access_cell(selected_company, module_code, module_limit_code=module_limit_code)
    employee_state = _employee_module_access_cell(company_state, user_state)
    group_state = _matrix_cell(
        "OPEN",
        "Открыто группой, если не закрыто пользователю, компании, тарифом или системой.",
        "GROUP_DEFAULT",
    )
    role_state = _module_access_cell(
        module_limit_code=module_limit_code,
        explicit_permission=role_permission,
        closed_reason="SYSTEM_LIMIT",
        open_reason="Открыто ролью пользователя.",
    )
    widgets = _access_matrix_widgets_for_module(
        module_code,
        company_state=company_state,
        user_state=user_state,
        pending_widget_codes=pending_widget_codes,
    )
    cells = [
        {**user_state, "key": "user", "title": "Пользователь", "isEditable": False, "disabledReason": "Настраивается в карточке пользователя или роли."},
        {**company_state, "key": "company", "title": "Компания", "isEditable": False, "disabledReason": "Доступ компании меняется в карточке компании."},
        _editable_employee_cell(
            employee_state,
            company_state=company_state,
            module_limit_code=module_limit_code,
            selected_company=selected_company,
        ),
        {**group_state, "key": "group", "title": "Группа", "isEditable": False, "disabledReason": "Группы меняются во вкладке Роли и группы."},
        {**role_state, "key": "role", "title": "Роль", "isEditable": False, "disabledReason": "Роли меняются во вкладке Роли и группы."},
    ]
    open_widget_count = len([widget for widget in widgets if widget["stateCode"] == "OPEN"])
    revoked_widget_count = len([widget for widget in widgets if widget["stateCode"] == "WIDGET_REVOKED_BY_MODULE_DENY"])
    blocked_widget_count = len(widgets) - open_widget_count
    return {
        "moduleCode": module_code,
        "title": module.get("title") or module_code,
        "status": module.get("status"),
        "statusLabel": _module_status_label(module_status),
        "statusTone": _status_tone(module_status),
        "route": module.get("route") or module.get("redirectRoute"),
        "isNew": module_code in pending_module_codes,
        "workspaceId": str(selected_company.id) if selected_company else None,
        "user": user_state,
        "company": company_state,
        "employee": employee_state,
        "group": group_state,
        "role": role_state,
        "cells": cells,
        "widgets": widgets,
        "widgetCount": len(widgets),
        "openWidgetCount": open_widget_count,
        "blockedWidgetCount": blocked_widget_count,
        "revokedWidgetCount": revoked_widget_count,
    }


def _access_matrix_widgets_for_module(
    module_code: str,
    *,
    company_state: dict[str, str],
    user_state: dict[str, str],
    pending_widget_codes: set[str],
) -> list[dict[str, Any]]:
    widgets: list[dict[str, Any]] = []
    for widget in get_widget_registry():
        source_code = _canonical_module_code_value(widget.get("canonicalModuleCode") or widget.get("sourceModuleCode"))
        if source_code != module_code:
            continue
        if company_state["stateCode"] == "CLOSED" or user_state["stateCode"] == "CLOSED":
            cell = _matrix_cell(
                "WIDGET_REVOKED_BY_MODULE_DENY",
                ACCESS_DENY_REASONS["WIDGET_REVOKED_BY_MODULE_DENY"],
                "COMPANY_DEFAULT" if company_state["stateCode"] == "CLOSED" else "USER_OVERRIDE",
            )
        else:
            widget_limit_code = _widget_limit_reason_code(widget)
            if widget_limit_code:
                cell = _matrix_cell(widget_limit_code, ACCESS_DENY_REASONS[widget_limit_code], "SYSTEM_LIMIT")
            else:
                cell = _matrix_cell("OPEN", "Открыто: модуль доступен, виджет активен.", "SYSTEM_DEFAULT")
        widgets.append(
            {
                "widgetCode": widget["widgetCode"],
                "title": widget["title"],
                "sourceModuleCode": source_code,
                "featureCode": widget.get("featureCode"),
                "isNew": widget["widgetCode"] in pending_widget_codes,
                "canOpen": cell["stateCode"] != "OPEN" and company_state["stateCode"] == "OPEN" and user_state["stateCode"] == "OPEN",
                "canClose": cell["stateCode"] == "OPEN",
                "disabledReason": _widget_action_disabled_reason(cell, company_state=company_state, user_state=user_state),
                **cell,
            }
        )
    return widgets


def _editable_employee_cell(
    cell: dict[str, str],
    *,
    company_state: dict[str, str],
    module_limit_code: str | None,
    selected_company: Workspace | None,
) -> dict[str, Any]:
    if not selected_company:
        return {
            **cell,
            "key": "employee",
            "title": "Сотрудник компании",
            "isEditable": False,
            "canOpen": False,
            "canClose": False,
            "disabledReason": "Сначала привяжите пользователя к компании.",
        }
    if module_limit_code:
        return {
            **cell,
            "key": "employee",
            "title": "Сотрудник компании",
            "isEditable": False,
            "canOpen": False,
            "canClose": False,
            "disabledReason": ACCESS_DENY_REASONS[module_limit_code],
        }
    can_open = company_state["stateCode"] == "OPEN" and cell["stateCode"] != "OPEN"
    can_close = cell["stateCode"] == "OPEN"
    disabled_reason = ""
    if company_state["stateCode"] != "OPEN":
        disabled_reason = "Сначала откройте доступ компании."
    elif not can_open and not can_close:
        disabled_reason = cell["reason"]
    return {
        **cell,
        "key": "employee",
        "title": "Сотрудник компании",
        "isEditable": True,
        "canOpen": can_open,
        "canClose": can_close,
        "disabledReason": disabled_reason,
    }


def _widget_action_disabled_reason(
    cell: dict[str, str],
    *,
    company_state: dict[str, str],
    user_state: dict[str, str],
) -> str:
    if cell["stateCode"] == "OPEN":
        return ""
    if company_state["stateCode"] != "OPEN" or user_state["stateCode"] != "OPEN":
        return ACCESS_DENY_REASONS["WIDGET_REVOKED_BY_MODULE_DENY"]
    return cell["reason"]


def _module_access_cell(
    *,
    module_limit_code: str | None,
    explicit_permission: dict[str, Any] | None,
    closed_reason: str,
    open_reason: str,
) -> dict[str, str]:
    if module_limit_code:
        return _matrix_cell(module_limit_code, ACCESS_DENY_REASONS[module_limit_code], "SYSTEM_LIMIT")
    if explicit_permission and not _access_level_is_open(explicit_permission.get("accessLevel")):
        return _matrix_cell("CLOSED", ACCESS_DENY_REASONS[closed_reason], "USER_OVERRIDE", reason_code=closed_reason)
    return _matrix_cell("OPEN", open_reason, "ROLE_DEFAULT" if explicit_permission else "SYSTEM_DEFAULT")


def _company_module_access_cell(
    selected_company: Workspace | None,
    module_code: str,
    *,
    module_limit_code: str | None,
) -> dict[str, str]:
    if module_limit_code:
        return _matrix_cell(module_limit_code, ACCESS_DENY_REASONS[module_limit_code], "SYSTEM_LIMIT")
    if not selected_company:
        return _matrix_cell("OPEN", "Компания не выбрана: ограничение компании не применяется.", "SYSTEM_DEFAULT")
    if not _workspace_is_active(selected_company):
        return _matrix_cell("COMPANY_BLOCKED", ACCESS_DENY_REASONS["COMPANY_BLOCKED"], "SYSTEM_LIMIT")
    if company_module_is_open(selected_company, module_code):
        return _matrix_cell("OPEN", "Открыто компании платформой.", "COMPANY_DEFAULT")
    return _matrix_cell(
        "CLOSED",
        ACCESS_DENY_REASONS["PLATFORM_ADMIN_DENY"],
        "COMPANY_DEFAULT",
        reason_code="PLATFORM_ADMIN_DENY",
    )


def _employee_module_access_cell(company_state: dict[str, str], user_state: dict[str, str]) -> dict[str, str]:
    if company_state["stateCode"] != "OPEN":
        reason_code = company_state.get("reasonCode") or "COMPANY_ADMIN_DENY"
        return _matrix_cell(
            reason_code if reason_code in {"COMPANY_BLOCKED", "MODULE_PLANNED", "MODULE_DRAFT", "MODULE_DISABLED"} else "CLOSED",
            ACCESS_DENY_REASONS.get(reason_code, "Закрыто: сотрудник не может получить больше доступа, чем компания."),
            "COMPANY_DEFAULT",
            reason_code=reason_code,
        )
    if user_state["stateCode"] != "OPEN":
        return _matrix_cell(user_state["stateCode"], user_state["reason"], "USER_OVERRIDE")
    return _matrix_cell("OPEN", "Открыто сотруднику в пределах доступа компании.", "COMPANY_DEFAULT")


def _matrix_cell(state_code: str, reason: str, resolution_source: str, *, reason_code: str | None = None) -> dict[str, str]:
    normalized_reason_code = reason_code or (state_code if state_code in ACCESS_DENY_REASONS else "")
    return {
        "stateCode": state_code,
        "label": VISIBLE_ACCESS_STATES.get(state_code, state_code.lower()),
        "reason": reason,
        "reasonCode": normalized_reason_code,
        "reasonCategory": ACCESS_REASON_CATEGORIES.get(normalized_reason_code, "open"),
        "resolutionSource": resolution_source,
        "monetization": _monetization_placeholder(normalized_reason_code or state_code),
    }


def _pending_access_distribution_codes() -> tuple[set[str], set[str]]:
    pending_items = pending_access_distribution_items()
    module_codes = {
        str(item.get("canonicalModuleCode") or item.get("moduleCode") or item.get("code"))
        for item in pending_items
        if item.get("itemKind") == "module"
    }
    widget_codes = {
        str(item.get("widgetCode") or item.get("code"))
        for item in pending_items
        if item.get("itemKind") == "widget"
    }
    return module_codes, widget_codes


def _module_status_label(status: str) -> str:
    return {
        "active": "активен",
        "planned": "запланирован",
        "draft": "в подготовке",
        "disabled": "отключен",
        "deprecated": "устаревает",
        "archived": "архив",
        "merged": "объединен",
    }.get(status, status or "не задан")


def _status_tone(status: str) -> str:
    if status == "active":
        return "ok"
    if status in {"disabled", "archived", "merged"}:
        return "danger"
    return "warn"


def _module_limit_reason_code(module: dict[str, Any]) -> str | None:
    status = str(module.get("status") or "").lower()
    if status == "planned":
        return "MODULE_PLANNED"
    if status == "draft":
        return "MODULE_DRAFT"
    if status != "active" or not module.get("isAvailableForDashboard"):
        return "MODULE_DISABLED"
    return None


def _widget_limit_reason_code(widget: dict[str, Any]) -> str | None:
    status = str(widget.get("status") or "").upper()
    if status in {"PLANNED"}:
        return "MODULE_PLANNED"
    if status in {"DRAFT"}:
        return "MODULE_DRAFT"
    if status != "ACTIVE":
        return "WIDGET_DISABLED"
    return None


def _monetization_placeholder(state_code: str) -> dict[str, Any]:
    return {
        "planCode": None,
        "subscriptionCode": None,
        "billingFeatureCode": None,
        "billingRestrictionReason": ACCESS_DENY_REASONS["TARIFF_LIMIT"] if state_code == "TARIFF_LIMIT" else None,
        "tariffLevel": None,
        "tariffExpiresAt": None,
        "isBillingRestricted": state_code == "TARIFF_LIMIT",
    }


def _permission_map_by_module(permissions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for permission in permissions:
        if permission.get("kind") != "module":
            continue
        module_code = _canonical_module_code_value(permission.get("moduleCode"))
        if module_code:
            result[module_code] = permission
    return result


def _access_level_is_open(access_level: Any) -> bool:
    return _enum_value(access_level).upper() not in {"NO_ACCESS", "DENY", "CLOSED", "DISABLED"}


def widget_access_rows_for_user(
    user: Any,
    *,
    access_context: dict[str, Any] | None = None,
    module8_preview: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    user_data = _dict_value(user)
    access_data = access_context or {}
    module8_data = module8_preview or {}
    role_codes = _list_strings(access_data.get("roleCodes") or user_data.get("roleCodes"))
    primary_role_code = role_codes[0] if role_codes else normalize_role_code(user_data.get("roleCode"))
    profile = get_role_dashboard_access_profile(primary_role_code) or {}
    allowed_widget_codes = set(_list_strings(access_data.get("allowedWidgetCodes")))
    allowed_feature_codes = set(_list_strings(access_data.get("allowedFeatureCodes")))
    profile_widgets = set(_list_strings(profile.get("defaultWidgetCodes")))
    profile_hidden_widgets = set(_list_strings(profile.get("hiddenWidgetCodes")))
    recommended_widgets = set(
        _list_strings(
            (module8_data.get("dashboardContextPreview") or {}).get("recommendedWidgetCodes")
        )
    )
    active_region_code = access_data.get("activeRegionCode")

    rows: list[dict[str, Any]] = []
    for widget in get_widget_registry():
        module_item = get_dashboard_module_registry_item(widget.get("canonicalModuleCode") or widget.get("sourceModuleCode"))
        allowed, reason = _widget_access_preview_reason(
            widget,
            module_item=module_item,
            active_region_code=active_region_code,
            has_role_profile=bool(profile),
            allowed_widget_codes=allowed_widget_codes,
            allowed_feature_codes=allowed_feature_codes,
            profile_widgets=profile_widgets,
            profile_hidden_widgets=profile_hidden_widgets,
        )
        settings_preview = build_widget_settings_schema_preview(
            widget,
            access_context=access_data,
            module8_preview=module8_data,
            is_widget_allowed=allowed,
        )
        state = _state_for_access_preview(
            item_status=widget["status"],
            reason=reason,
            module_status=_get_value(module_item, "status"),
            has_legacy=bool(widget.get("legacyModuleCode")),
            is_allowed=allowed,
        )
        rows.append({
            "widgetCode": widget["widgetCode"],
            "title": widget["title"],
            "sourceModuleCode": widget["sourceModuleCode"],
            "canonicalModuleCode": widget.get("canonicalModuleCode") or widget["sourceModuleCode"],
            "featureCode": widget.get("featureCode"),
            "legacyModuleCode": widget.get("legacyModuleCode"),
            "status": widget["status"],
            "widgetType": widget["widgetType"],
            "requiredAccessLevel": widget.get("requiredAccessLevel"),
            "requiredScope": widget.get("requiredScope"),
            "requiredActionCode": widget.get("requiredActionCode"),
            "allowedRoles": widget.get("allowedRoles") or ["через RoleDashboardAccessProfile"],
            "allowedCabinetTypes": widget.get("allowedCabinetTypes") or ["Module №8 adapter / preset"],
            "isAllowed": allowed,
            "unavailableReason": reason,
            "stateCode": state["code"],
            "stateTitle": state["title"],
            "stateDescription": state["description"],
            "stateSeverity": state["severity"],
            "module8Recommendation": "рекомендован" if widget["widgetCode"] in recommended_widgets else "не выбран кабинетом",
            "layoutRelation": "можно добавить в UserDashboardLayout" if allowed else "layout не может включить без доступа",
            "isMock": widget.get("isMock", False),
            "settingsPreview": settings_preview,
        })
    return sorted(rows, key=lambda item: (not item["isAllowed"], item["status"], item["sourceModuleCode"], item["widgetCode"]))


def quick_action_rows_for_user(
    user: Any,
    *,
    access_context: dict[str, Any] | None = None,
    module8_preview: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    user_data = _dict_value(user)
    access_data = access_context or {}
    module8_data = module8_preview or {}
    raw_role_codes = _list_strings(access_data.get("roleCodes") or user_data.get("roleCodes"))
    if not raw_role_codes and user_data.get("roleCode"):
        raw_role_codes = [str(user_data["roleCode"])]
    role_codes = _role_aliases(raw_role_codes)
    primary_role_code = normalize_role_code(raw_role_codes[0]) if raw_role_codes else normalize_role_code(user_data.get("roleCode"))
    profile = get_role_dashboard_access_profile(primary_role_code) or {}
    profile_actions = set(_list_strings(profile.get("defaultQuickActionCodes")))
    allowed_quick_action_codes = set(_list_strings(access_data.get("allowedQuickActionCodes")))
    active_region_code = access_data.get("activeRegionCode")
    active_cabinet_type = module8_data.get("activeCabinetType")
    cabinet_types = _cabinet_type_aliases(active_cabinet_type)

    rows: list[dict[str, Any]] = []
    for action in get_quick_action_registry():
        module_item = get_dashboard_module_registry_item(action.get("canonicalModuleCode") or action.get("sourceModuleCode"))
        allowed, reason = _quick_action_access_preview_reason(
            action,
            module_item=module_item,
            active_region_code=active_region_code,
            has_role_profile=bool(profile),
            profile_actions=profile_actions,
            allowed_quick_action_codes=allowed_quick_action_codes,
            role_codes=role_codes,
            cabinet_types=cabinet_types,
        )
        preference_preview = build_quick_action_preference_preview(
            action,
            access_context=access_data,
            module8_preview=module8_data,
            is_action_allowed=allowed,
            unavailable_reason=reason,
        )
        state = _state_for_access_preview(
            item_status=action["status"],
            reason=reason,
            module_status=_get_value(module_item, "status"),
            has_legacy=False,
            is_allowed=allowed,
        )
        rows.append({
            "quickActionCode": action["quickActionCode"],
            "title": action["title"],
            "sourceModuleCode": action["sourceModuleCode"],
            "canonicalModuleCode": action.get("canonicalModuleCode") or action["sourceModuleCode"],
            "featureCode": action.get("featureCode"),
            "widgetCode": action.get("widgetCode"),
            "actionCode": action.get("requiredActionCode"),
            "requiredAccessLevel": action.get("requiredAccessLevel"),
            "requiredScope": action.get("requiredScope"),
            "status": action["status"],
            "route": action.get("route"),
            "allowedRoles": action.get("allowedRoles") or ["через RoleDashboardAccessProfile"],
            "allowedCabinetTypes": action.get("allowedCabinetTypes") or ["Module №8 adapter / preset"],
            "isAllowed": allowed,
            "unavailableReason": reason,
            "stateCode": state["code"],
            "stateTitle": state["title"],
            "stateDescription": state["description"],
            "stateSeverity": state["severity"],
            "module8Recommendation": "уместно" if cabinet_types.intersection(set(action.get("allowedCabinetTypes") or [])) else "ожидает кабинетный preset",
            "preferencePreview": preference_preview,
        })
    return sorted(rows, key=lambda item: (not item["isAllowed"], item["status"], item["sourceModuleCode"], item["quickActionCode"]))


def _widget_access_preview_reason(
    widget: dict[str, Any],
    *,
    module_item: Any,
    active_region_code: str | None,
    has_role_profile: bool,
    allowed_widget_codes: set[str],
    allowed_feature_codes: set[str],
    profile_widgets: set[str],
    profile_hidden_widgets: set[str],
) -> tuple[bool, str]:
    if widget["status"] != "ACTIVE":
        return False, f"Статус виджета: {widget['status']}."
    if module_item and (not module_item.isAvailableForDashboard or module_item.status != "active"):
        return False, f"Модуль-источник недоступен для Dashboard: {module_item.status}."
    if not active_region_code:
        return False, "Не задан activeRegionCode."
    if not has_role_profile:
        return False, "Нет RoleDashboardAccessProfile для роли пользователя."
    if widget["widgetCode"] in profile_hidden_widgets:
        return False, "Скрыт RoleDashboardAccessProfile."
    if profile_widgets and widget["widgetCode"] not in profile_widgets:
        return False, "Не входит в RoleDashboardAccessProfile."
    if widget.get("featureCode") and allowed_feature_codes and widget["featureCode"] not in allowed_feature_codes:
        return False, f"Нет доступа к featureCode {widget['featureCode']}."
    if allowed_widget_codes and widget["widgetCode"] not in allowed_widget_codes:
        return False, "WidgetPermission / PermissionGuard не разрешил widgetCode."
    return True, "Доступен через WidgetRegistry, role profile, permissions и activeRegionCode."


def _quick_action_access_preview_reason(
    action: dict[str, Any],
    *,
    module_item: Any,
    active_region_code: str | None,
    has_role_profile: bool,
    profile_actions: set[str],
    allowed_quick_action_codes: set[str],
    role_codes: set[str],
    cabinet_types: set[str],
) -> tuple[bool, str]:
    if action["status"] != "ACTIVE":
        return False, f"Статус quick action: {action['status']}."
    if module_item and (not module_item.isAvailableForDashboard or module_item.status != "active"):
        return False, f"Модуль-источник недоступен для quick actions: {module_item.status}."
    if not active_region_code:
        return False, "Не задан activeRegionCode."
    if not has_role_profile:
        return False, "Нет RoleDashboardAccessProfile для роли пользователя."
    if profile_actions and action["quickActionCode"] not in profile_actions:
        return False, "Не входит в RoleDashboardAccessProfile."
    if allowed_quick_action_codes and action["quickActionCode"] not in allowed_quick_action_codes:
        return False, "PermissionGuard / QuickActionPermission не разрешил quickActionCode."
    allowed_roles = set(action.get("allowedRoles") or [])
    if allowed_roles and not role_codes.intersection(allowed_roles):
        return False, "Роль пользователя не разрешена для quick action."
    allowed_cabinets = set(action.get("allowedCabinetTypes") or [])
    if allowed_cabinets and not cabinet_types.intersection(allowed_cabinets):
        return False, "Module №8 adapter не считает действие уместным для активного кабинета."
    return True, "Доступно через QuickActionRegistry, PermissionGuard, role profile и Module №8 context."


def _state_for_access_preview(
    *,
    item_status: str,
    reason: str,
    module_status: Any,
    has_legacy: bool,
    is_allowed: bool,
) -> dict[str, str]:
    normalized_status = str(item_status or "").upper()
    normalized_module_status = str(module_status or "").lower()
    lower_reason = reason.lower()
    if is_allowed:
        if has_legacy:
            return _state_definition("LEGACY_MERGED")
        return {
            "code": "AVAILABLE",
            "title": "available state",
            "description": "Доступно, но backend/service guard все равно обязателен перед действием или получением данных.",
            "severity": "ok",
        }
    if normalized_status in {"PLANNED", "DRAFT"}:
        return _state_definition("FUTURE_FEATURE")
    if normalized_status in {"DISABLED", "DEPRECATED", "ARCHIVED"}:
        return _state_definition("ARCHIVED_DISABLED")
    if normalized_module_status in {"merged", "deprecated"}:
        return _state_definition("LEGACY_MERGED")
    if normalized_module_status in {"planned", "draft"} or "модуль-источник" in lower_reason:
        return _state_definition("MODULE_NOT_READY")
    if "activeregioncode" in lower_reason or "roleprofile" in lower_reason or "role dashboard" in lower_reason:
        return _state_definition("NOT_CONFIGURED")
    if "permission" in lower_reason or "нет доступа" in lower_reason or "роль" in lower_reason:
        return _state_definition("NO_PERMISSION")
    return _state_definition("ERROR")


def _state_definition(code: str) -> dict[str, str]:
    for item in ADMIN_UI_STATE_LEGEND:
        if item["code"] == code:
            return dict(item)
    return {
        "code": "ERROR",
        "title": "error state",
        "description": "Неизвестное состояние. Требуется проверка администратором.",
        "severity": "error",
    }


def audit_log_summary(item: AuditLog) -> dict[str, Any]:
    details = item.details or {}
    entity_type = _details_value(details, "entityType") or item.entity_type
    entity_id = _details_value(details, "entityId") or str(item.entity_id or "")
    module_code = _details_value(details, "moduleCode")
    widget_code = _details_value(details, "widgetCode")
    role_code = _details_value(details, "roleCode")
    workspace_id = _details_value(details, "workspaceId") or str(item.workspace_id or "")
    target_user_id = _details_value(details, "targetUserId")
    return {
        "id": str(item.id),
        "createdAt": item.created_at,
        "actionType": item.action_type,
        "result": item.result,
        "actor": item.user.email if item.user else "system/dev",
        "actorUserId": _details_value(details, "actorUserId") or str(item.user_id or ""),
        "targetUserId": target_user_id,
        "workspaceId": workspace_id,
        "moduleCode": module_code,
        "canonicalModuleCode": _details_value(details, "canonicalModuleCode"),
        "featureCode": _details_value(details, "featureCode"),
        "widgetCode": widget_code,
        "roleCode": role_code,
        "oldValue": _details_value(details, "oldValue"),
        "newValue": _details_value(details, "newValue"),
        "reason": _details_value(details, "reason") or _details_value(details, "comment") or "",
        "comment": _details_value(details, "comment") or "",
        "entityType": entity_type,
        "entityId": entity_id,
        "objectType": _audit_object_type(entity_type, module_code=module_code, widget_code=widget_code, role_code=role_code),
        "subjectLabel": _audit_subject_label(entity_type, target_user_id=target_user_id, workspace_id=workspace_id, module_code=module_code, widget_code=widget_code),
        "details": details,
    }


def change_history_for_admin_panel(history: list[AuditLog], user_data: dict[str, Any]) -> dict[str, Any]:
    rows = [audit_log_summary(item) for item in history]
    return {
        "rows": rows,
        "filters": {
            "authors": _unique_sorted(row["actor"] for row in rows),
            "dates": _unique_sorted(_date_filter_value(row["createdAt"]) for row in rows),
            "actions": _unique_sorted(row["actionType"] for row in rows),
            "objectTypes": _unique_sorted(row["objectType"] for row in rows),
            "modules": _unique_sorted(row["moduleCode"] for row in rows if row.get("moduleCode")),
            "widgets": _unique_sorted(row["widgetCode"] for row in rows if row.get("widgetCode")),
        },
        "bySubject": _history_bucket_counts(rows, "objectType"),
        "byModule": _history_bucket_counts(rows, "moduleCode"),
        "byWidget": _history_bucket_counts(rows, "widgetCode"),
        "subject": {
            "userId": user_data.get("id"),
            "title": user_data.get("name") or user_data.get("email"),
            "type": "пользователь",
        },
        "notes": {
            "oldNewValuesVisible": True,
            "reasonOptional": True,
            "businessPayloadLogged": False,
        },
    }


def audit_panel_summary(history: list[AuditLog]) -> dict[str, Any]:
    rows = [audit_log_summary(item) for item in history]
    selected = rows[0] if rows else None
    return {
        "rows": rows,
        "selectedRecord": selected,
        "filters": {
            "authors": _unique_sorted(row["actor"] for row in rows),
            "dates": _unique_sorted(_date_filter_value(row["createdAt"]) for row in rows),
            "actions": _unique_sorted(row["actionType"] for row in rows),
            "objectTypes": _unique_sorted(row["objectType"] for row in rows),
            "modules": _unique_sorted(row["moduleCode"] for row in rows if row.get("moduleCode")),
            "widgets": _unique_sorted(row["widgetCode"] for row in rows if row.get("widgetCode")),
            "subjects": _unique_sorted(row["subjectLabel"] for row in rows if row.get("subjectLabel")),
        },
        "summary": {
            "total": len(rows),
            "success": len([row for row in rows if str(row.get("result")).upper() == "SUCCESS"]),
            "failed": len([row for row in rows if str(row.get("result")).upper() not in {"", "SUCCESS"}]),
            "withReason": len([row for row in rows if row.get("reason")]),
        },
        "byAction": _history_bucket_counts(rows, "actionType"),
        "bySubject": _history_bucket_counts(rows, "objectType"),
        "notes": {
            "oldNewValuesVisible": True,
            "actorVisible": True,
            "targetVisible": True,
            "businessPayloadLogged": False,
        },
    }


def settings_panel_summary(admin_scope: dict[str, Any]) -> dict[str, Any]:
    actor_roles = set(admin_scope.get("actorRoleCodes") or [])
    is_super_admin = "SUPER_ADMIN" in actor_roles
    return {
        "normalSettings": [
            {
                "title": "Правила рабочего меню",
                "description": "Обычный администратор видит только рабочие разделы Module №3: пользователей, роли, рабочие области и журнал изменений.",
                "target": "#users",
            },
            {
                "title": "Регистрация пользователей",
                "description": "Ручное создание пользователя отключено. Пользователь появляется только через стандартную регистрацию.",
                "target": "#users",
            },
            {
                "title": "Причины ограничений",
                "description": "Ручные запреты, тарифные ограничения и системные блокировки показываются раздельно в карточках пользователя, компании и сотрудника.",
                "target": "#access-matrix",
            },
            {
                "title": "Журнал изменений",
                "description": "История доступа остается главным способом проверить, кто и почему открыл или закрыл доступ.",
                "target": "#audit-log",
            },
        ],
        "superAdminMode": {
            "enabled": is_super_admin,
            "title": "Super Admin mode",
            "description": (
                "Системные и developer-only инструменты доступны только Super Admin."
                if is_super_admin
                else "Системные и developer-only инструменты скрыты от обычного администратора."
            ),
        },
        "developerDiagnostics": [
            {
                "title": "Registry diagnostics",
                "description": "Диагностика PlatformModuleRegistry, canonical mapping и legacy aliases.",
                "target": "/api/v1/admin/module-registry/view",
            },
            {
                "title": "Widget diagnostics",
                "description": "Диагностика WidgetRegistry, Widget Permission и связи с UserDashboardLayout.",
                "target": "#widget-access",
            },
            {
                "title": "Legacy aliases",
                "description": "Проверка legacy/merged moduleCode и redirect/canonical mapping.",
                "target": "#settings",
            },
            {
                "title": "UI states",
                "description": "Справочник empty/loading/error/no permission/future/archived states.",
                "target": "#settings",
            },
            {
                "title": "Module lifecycle diagnostics",
                "description": "Проверка PLANNED / DRAFT / ACTIVE / DISABLED / DEPRECATED / ARCHIVED / MERGED.",
                "target": "#settings",
            },
            {
                "title": "Widget lifecycle diagnostics",
                "description": "Проверка статусов виджетов и причин недоступности.",
                "target": "#widget-access",
            },
            {
                "title": "Dashboard layout presets",
                "description": "Технические presets и UserDashboardLayout без редактирования главного Dashboard.",
                "target": "#dashboard-layouts",
            },
        ],
        "dangerZone": {
            "title": "Danger zone",
            "requiresConfirmation": True,
            "confirmationText": DISABLE_CONFIRMATION,
            "warning": "Опасные действия требуют явного подтверждения и записи в AuditLog.",
            "actions": [
                "Отключить пользователя",
                "Архивировать компанию",
                "Изменить системно-критичный модуль",
                "Массово открыть или закрыть доступ",
                "Назначить Super Admin",
            ],
        },
        "notes": {
            "registryDiagnosticsHiddenForRegularAdmin": True,
            "widgetDiagnosticsHiddenForRegularAdmin": True,
            "legacyAliasesHiddenForRegularAdmin": True,
            "uiStatesHiddenForRegularAdmin": True,
            "moduleLifecycleDiagnosticsHiddenForRegularAdmin": True,
            "widgetLifecycleDiagnosticsHiddenForRegularAdmin": True,
            "ordinaryAdminKeepsWorkingSettings": True,
        },
    }


def _details_value(details: dict[str, Any], key: str) -> Any:
    value = details.get(key)
    if value is not None:
        return value
    metadata = details.get("metadata")
    if isinstance(metadata, dict):
        return metadata.get(key)
    return None


def _audit_object_type(
    entity_type: Any,
    *,
    module_code: Any = None,
    widget_code: Any = None,
    role_code: Any = None,
) -> str:
    normalized = str(entity_type or "").lower()
    if widget_code or "widget" in normalized or normalized == "functionaccess":
        return "виджет"
    if module_code or "module" in normalized:
        return "модуль"
    if "workspacemember" in normalized:
        return "сотрудник компании"
    if "workspace" in normalized:
        return "компания"
    if role_code or "role" in normalized:
        return "роль"
    return "пользователь"


def _audit_subject_label(
    entity_type: Any,
    *,
    target_user_id: Any = None,
    workspace_id: Any = None,
    module_code: Any = None,
    widget_code: Any = None,
) -> str:
    object_type = _audit_object_type(entity_type, module_code=module_code, widget_code=widget_code)
    if object_type == "виджет":
        return str(widget_code or "виджет")
    if object_type == "модуль":
        return str(module_code or "модуль")
    if object_type in {"компания", "сотрудник компании"}:
        return str(workspace_id or object_type)
    return str(target_user_id or object_type)


def _filter_users_for_admin_scope(users: list[User], admin_scope: dict[str, Any]) -> list[User]:
    if admin_scope.get("isPlatformAdminMode"):
        return users
    company_ids = set(admin_scope.get("companyWorkspaceIds") or [])
    if not company_ids:
        return []
    return [user for user in users if _user_in_company_scope(user, company_ids)]


def _filter_workspaces_for_admin_scope(workspaces: list[Workspace], admin_scope: dict[str, Any]) -> list[Workspace]:
    if admin_scope.get("isPlatformAdminMode"):
        return workspaces
    company_ids = set(admin_scope.get("companyWorkspaceIds") or [])
    return [
        workspace
        for workspace in workspaces
        if str(_workspace_id(workspace)) in company_ids and _is_company_workspace(workspace)
    ]


def _filter_roles_for_admin_scope(roles: list[dict[str, Any]], admin_scope: dict[str, Any]) -> list[dict[str, Any]]:
    if admin_scope.get("isPlatformAdminMode"):
        return roles
    return [
        {**role, "isAssignable": False}
        for role in roles
        if role.get("roleCode") in COMPANY_ADMIN_VISIBLE_ROLE_CODES
    ]


def _filter_history_for_admin_scope(rows: list[AuditLog], admin_scope: dict[str, Any]) -> list[AuditLog]:
    if admin_scope.get("isPlatformAdminMode"):
        return rows
    company_ids = set(admin_scope.get("companyWorkspaceIds") or [])
    if not company_ids:
        return []
    filtered: list[AuditLog] = []
    for row in rows:
        details = row.details or {}
        workspace_id = row.workspace_id or details.get("workspaceId") or details.get("workspace_id")
        if str(workspace_id) in company_ids:
            filtered.append(row)
    return filtered


def _require_user_visible_to_admin_scope(user: User, admin_scope: dict[str, Any]) -> None:
    if admin_scope.get("isPlatformAdminMode"):
        return
    company_ids = set(admin_scope.get("companyWorkspaceIds") or [])
    if not company_ids or not _user_in_company_scope(user, company_ids):
        raise ForbiddenError("Company administrator can open only employees inside the assigned company.")


def _user_in_company_scope(user: User, company_ids: set[str]) -> bool:
    for member in _safe_iterable(_get_value(user, "workspace_members")):
        status = _enum_value(_get_value(member, "status")).upper()
        workspace_id = _get_value(member, "workspace_id") or _get_value(member, "workspaceId")
        if str(workspace_id) in company_ids and status in {"", "ACTIVE"}:
            return True
    return False


def _workspace_uuid_scope(admin_scope: dict[str, Any]) -> list[UUID] | None:
    if admin_scope.get("isPlatformAdminMode"):
        return None
    ids: list[UUID] = []
    for workspace_id in admin_scope.get("companyWorkspaceIds") or []:
        try:
            ids.append(UUID(str(workspace_id)))
        except ValueError:
            continue
    return ids


def _history_bucket_counts(rows: list[dict[str, Any]], field_name: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(field_name)
        if not value:
            continue
        counts[str(value)] = counts.get(str(value), 0) + 1
    return [{"label": label, "count": count} for label, count in sorted(counts.items())]


def _unique_sorted(values: Any) -> list[str]:
    return sorted({str(value) for value in values if value not in {None, ""}})


def _date_filter_value(value: Any) -> str:
    if hasattr(value, "date"):
        return str(value.date())
    text = str(value or "")
    return text[:10] if text else ""


def _overview_summary(
    users: list[User],
    workspaces: list[Workspace],
    recent_history: list[AuditLog],
    *,
    pending_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    company_workspaces = [workspace for workspace in workspaces if _is_company_workspace(workspace)]
    blocked_users = [
        user
        for user in users
        if _status_value(_get_value(user, "status")) in {"blocked", "disabled", "deleted"}
    ]
    blocked_companies = [
        workspace
        for workspace in company_workspaces
        if not workspace.isActive or str(workspace.status or "").upper() in {"BLOCKED", "DISABLED", "ARCHIVED"}
    ]
    pending_items = pending_items if pending_items is not None else pending_access_distribution_items()
    return {
        "usersTotal": len(users),
        "companiesTotal": len(company_workspaces),
        "blockedUsersTotal": len(blocked_users),
        "blockedCompaniesTotal": len(blocked_companies),
        "pendingAccessDistributionTotal": len(pending_items),
        "historyTotal": len(recent_history),
    }


def _is_company_workspace(workspace: Workspace) -> bool:
    return str(_get_value(workspace, "type") or _get_value(workspace, "workspace_type") or "").upper() in {
        "SUPPLIER",
        "CONTRACTOR",
        "ORGANIZATION",
        "CONSTRUCTION_COMPANY",
        "MATERIAL_SUPPLIER",
    }


def _workspace_id(workspace: Workspace | dict[str, Any]) -> Any:
    return _get_value(workspace, "id") or _get_value(workspace, "workspaceId") or _get_value(workspace, "workspace_id")


def _workspace_is_active(workspace: Workspace | dict[str, Any]) -> bool:
    if workspace is None:
        return False
    is_active = _get_value(workspace, "isActive")
    if is_active is None:
        is_active = _get_value(workspace, "is_active")
    status = _enum_value(_get_value(workspace, "status")).upper()
    return bool(is_active if is_active is not None else True) and status in {"", "ACTIVE"}


def _canonical_module_code_value(module_code: str | None) -> str | None:
    if not module_code:
        return None
    item = get_dashboard_module_registry_item(module_code)
    if not item:
        return module_code
    return item.canonicalModuleCode or item.mergedIntoModuleCode or item.moduleCode


def _status_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").lower()


def pending_access_distribution_items(
    *,
    modules: list[Any] | None = None,
    widgets: list[Any] | None = None,
    distributed_module_codes: set[str] | None = None,
    distributed_widget_codes: set[str] | None = None,
) -> list[dict[str, Any]]:
    return build_pending_access_distribution_items(
        modules if modules is not None else get_dashboard_module_registry(),
        widgets if widgets is not None else get_widget_registry(),
        distributedModuleCodes=distributed_module_codes,
        distributedWidgetCodes=distributed_widget_codes,
    )


def access_distribution_panel_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    module_items = [item for item in items if item.get("itemKind") == "module"]
    widget_items = [item for item in items if item.get("itemKind") == "widget"]
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "modules": len(module_items),
            "widgets": len(widget_items),
        },
        "hasPendingItems": bool(items),
        "actionTarget": "#access-matrix",
        "actionLabel": "Распределить доступ",
        "emptyState": "Новых модулей и виджетов для распределения нет.",
        "description": "Новые ACTIVE модули и dashboard-eligible ACTIVE виджеты появляются здесь автоматически.",
        "dashboardRewriteRequired": False,
        "dashboardNote": "Dashboard не переписывается при добавлении нового модуля или виджета.",
    }


def role_label(role_code: str | None) -> str:
    normalized = normalize_role_code(role_code)
    if not normalized:
        return "Нет роли"
    return ROLE_LABELS.get(normalized, normalized)


def _dict_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _list_strings(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return []


def _role_aliases(role_codes: list[str]) -> set[str]:
    aliases: set[str] = set()
    for role_code in role_codes:
        normalized = normalize_role_code(role_code) or str(role_code).upper()
        aliases.add(normalized)
        if normalized == "ADMIN":
            aliases.add("PLATFORM_ADMIN")
        if normalized == "DEV_ADMIN":
            aliases.add("SUPER_ADMIN")
    return aliases


def _cabinet_type_aliases(cabinet_type: Any) -> set[str]:
    if not cabinet_type:
        return set()
    normalized = str(cabinet_type).upper()
    aliases = {normalized}
    if normalized == "MATERIAL_SUPPLIER":
        aliases.add("SUPPLIER")
    if normalized == "CONSTRUCTION_COMPANY":
        aliases.add("CONTRACTOR")
    if normalized in {"PLATFORM_ADMIN", "SYSTEM_ADMIN"}:
        aliases.add("ADMIN")
    return aliases


async def _load_users(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role_assignments).selectinload(UserRoleAssignment.role),
            selectinload(User.role_assignments).selectinload(UserRoleAssignment.workspace),
            selectinload(User.workspace_members).selectinload(WorkspaceMember.workspace),
            selectinload(User.module_access),
            selectinload(User.function_access),
        )
        .order_by(User.email.asc())
    )
    return list(result.scalars().unique().all())


async def _get_user(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role_assignments).selectinload(UserRoleAssignment.role),
            selectinload(User.role_assignments).selectinload(UserRoleAssignment.workspace),
            selectinload(User.workspace_members).selectinload(WorkspaceMember.workspace),
            selectinload(User.module_access),
            selectinload(User.function_access),
        )
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found.")
    return user


async def _load_role_options(db: AsyncSession, actor: Any) -> list[dict[str, Any]]:
    result = await db.execute(select(Role).order_by(Role.is_system.desc(), Role.role_key.asc()))
    db_roles = {role.role_key: role for role in result.scalars().all()}
    role_codes = sorted({*SYSTEM_ROLE_CODES, *db_roles.keys()})
    return [
        {
            "roleCode": code,
            "title": role_label(code),
            "description": _role_description(code, db_roles.get(code)),
            "isSystem": is_system_role_code(code) or bool(db_roles.get(code) and db_roles[code].is_system),
            "isAssignable": can_assign_role_code(actor, code),
            "isAssignableByPlatformAdmin": code not in PROTECTED_ROLE_CODES,
        }
        for code in role_codes
    ]


async def _load_workspaces(db: AsyncSession) -> list[Workspace]:
    result = await db.execute(
        select(Workspace)
        .options(selectinload(Workspace.members).selectinload(WorkspaceMember.user))
        .order_by(Workspace.name.asc())
    )
    return list(result.scalars().unique().all())


async def _load_user_history(db: AsyncSession, user_id: UUID) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .where(
            or_(
                (AuditLog.entity_type == "User") & (AuditLog.entity_id == user_id),
                AuditLog.details["targetUserId"].as_string() == str(user_id),
            )
        )
        .order_by(desc(AuditLog.created_at))
        .limit(30)
    )
    return list(result.scalars().all())


async def _load_recent_access_history(db: AsyncSession, *, workspace_ids: list[UUID] | None = None) -> list[AuditLog]:
    filters = [
        AuditLog.action_type.in_(
            [
                AuditLogType.ROLE_CHANGED.value,
                AuditLogType.PERMISSION_CHANGED.value,
                AuditLogType.PLATFORM_MODULE_REGISTRY_CHANGED.value,
                AuditLogType.WIDGET_REGISTRY_CHANGED.value,
                AuditLogType.USER_DASHBOARD_LAYOUT_CHANGED.value,
            ]
        )
    ]
    if workspace_ids is not None:
        if not workspace_ids:
            return []
        filters.append(AuditLog.workspace_id.in_(workspace_ids))
    result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .where(*filters)
        .order_by(desc(AuditLog.created_at))
        .limit(6)
    )
    return list(result.scalars().all())


async def _get_or_create_role(db: AsyncSession, role_code: str) -> Role:
    result = await db.execute(select(Role).where(Role.role_key == role_code))
    role = result.scalar_one_or_none()
    if role:
        return role
    if not is_system_role_code(role_code):
        raise NotFoundError("Role not found.")
    role = Role(
        role_key=role_code,
        name=role_label(role_code),
        description=_role_description(role_code, None),
        is_system=True,
        status="ACTIVE",
    )
    db.add(role)
    await db.flush()
    return role


async def _get_workspace(db: AsyncSession, workspace_id: UUID | None) -> Workspace:
    if not workspace_id:
        raise ValidationError("Workspace id is required.")
    workspace = await db.get(Workspace, workspace_id)
    if workspace is None:
        raise NotFoundError("Workspace not found.")
    return workspace


async def _get_workspace_member(db: AsyncSession, user_id: UUID, workspace_id: UUID) -> WorkspaceMember | None:
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_or_create_user_module_access(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    module_code: str,
    canonical_module_code: str | None,
) -> ModuleAccess:
    result = await db.execute(
        select(ModuleAccess).where(
            ModuleAccess.user_id == user_id,
            ModuleAccess.workspace_id == workspace_id,
            ModuleAccess.canonical_module_code == canonical_module_code,
        )
    )
    access = result.scalar_one_or_none()
    if access is None:
        access = ModuleAccess(
            user_id=user_id,
            workspace_id=workspace_id,
            module_code=module_code,
            canonical_module_code=canonical_module_code,
            access_level="NO_ACCESS",
            access_scope="OWN",
            status="ACTIVE",
        )
        db.add(access)
    return access


async def _get_or_create_user_widget_access(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    widget_code: str,
    module_code: str | None,
    feature_code: str | None,
) -> FunctionAccess:
    result = await db.execute(
        select(FunctionAccess).where(
            FunctionAccess.user_id == user_id,
            FunctionAccess.workspace_id == workspace_id,
            FunctionAccess.function_key == widget_code,
        )
    )
    access = result.scalar_one_or_none()
    if access is None:
        access = FunctionAccess(
            user_id=user_id,
            workspace_id=workspace_id,
            module_code=module_code,
            canonical_module_code=module_code,
            feature_code=feature_code,
            function_key=widget_code,
            access_level="NO_ACCESS",
            access_scope="OWN",
            status="ACTIVE",
        )
        db.add(access)
    return access


async def _auto_revoke_employee_widgets_for_module(
    db: AsyncSession,
    *,
    user_id: UUID,
    workspace_id: UUID,
    module_code: str | None,
) -> int:
    if not module_code:
        return 0
    result = await db.execute(
        select(FunctionAccess).where(
            FunctionAccess.user_id == user_id,
            FunctionAccess.workspace_id == workspace_id,
            FunctionAccess.status == "ACTIVE",
        )
    )
    revoked = 0
    for access in result.scalars().all():
        access_module_code = _canonical_module_code_value(access.canonical_module_code or access.module_code)
        if access_module_code != module_code:
            continue
        if access.access_level == "NO_ACCESS":
            continue
        access.access_level = "NO_ACCESS"
        access.updated_at = datetime.utcnow()
        revoked += 1
    return revoked


async def _upsert_workspace_member(
    db: AsyncSession,
    user: User,
    workspace: Workspace,
    role_code: str,
) -> WorkspaceMember:
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.workspace_id == workspace.id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        member = WorkspaceMember(
            user_id=user.id,
            workspace_id=workspace.id,
            role_key=role_code,
            role_code=role_code,
            status="ACTIVE",
        )
        db.add(member)
    else:
        member.role_key = role_code
        member.role_code = role_code
        member.status = "ACTIVE"
        member.updated_at = datetime.utcnow()
    return member


def _add_audit_log(
    db: AsyncSession,
    actor: Any,
    *,
    action_type: str,
    target_user: User,
    workspace_id: UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    actor_id = _get_value(actor, "id")
    db.add(
        AuditLog(
            user_id=actor_id if isinstance(actor_id, UUID) else None,
            workspace_id=workspace_id,
            action_type=action_type,
            entity_type="User",
            entity_id=target_user.id,
            result="SUCCESS",
            details=details or {},
        )
    )


def _role_description(role_code: str, db_role: Role | None) -> str | None:
    if db_role and db_role.description:
        return db_role.description
    for definition in SYSTEM_ROLE_DEFINITIONS:
        if definition.roleCode == role_code:
            return definition.description
    return None


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, UserRole | UserStatus):
        return str(value.value)
    return str(value)


def _safe_iterable(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list | tuple | set):
        return list(value)
    return []
