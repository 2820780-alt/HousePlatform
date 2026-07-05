from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
from app.services.quick_action_preferences import (
    MAX_MODULE_BAR_QUICK_ACTIONS,
    MAX_MODULE_CARD_QUICK_ACTIONS,
    build_user_quick_action_preference,
)
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

MODULE3_QUICK_ACTION_CODES: tuple[str, ...] = ()

USER_TYPE_WIDGET_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "userTypeCode": "COMPANY",
        "title": "Компании",
        "description": "Юридические лица и организации в платформе.",
        "source": "workspaces",
        "includeModeration": True,
    },
    {
        "userTypeCode": "SUPPLIER",
        "title": "Поставщики",
        "description": "Поставщики и карточки поставщиков, связанные с доступами.",
        "source": "suppliers",
        "includeModeration": True,
    },
    {
        "userTypeCode": "CUSTOMER",
        "title": "Заказчики",
        "description": "Пользователи и компании со сценариями заказчика.",
        "source": "users",
        "roleCodes": {"CUSTOMER"},
        "includeModeration": False,
    },
    {
        "userTypeCode": "SPECIALIST",
        "title": "Специалисты",
        "description": "Инженеры, сметчики, подрядчики и проектные роли.",
        "source": "users",
        "roleCodes": {"CONTRACTOR", "ESTIMATOR", "ENGINEER_DESIGNER"},
        "includeModeration": False,
    },
)

ACCESS_MATRIX_USER_TYPE_COLUMNS: tuple[dict[str, str], ...] = (
    {
        "userTypeCode": "CUSTOMER",
        "label": "Заказчики",
        "sourceRoleCode": "CUSTOMER",
    },
    {
        "userTypeCode": "SUPPLIER",
        "label": "Поставщики",
        "sourceRoleCode": "SUPPLIER",
    },
    {
        "userTypeCode": "CONSTRUCTION_COMPANY",
        "label": "Строительные компании",
        "sourceRoleCode": "CONTRACTOR",
    },
    {
        "userTypeCode": "INDEPENDENT_ENGINEER",
        "label": "Самостоятельные инженеры",
        "sourceRoleCode": "ENGINEER_DESIGNER",
    },
)

MODULE3_AUDIT_ACTION_LABELS: dict[str, str] = {
    "user_created": "Создание пользователя",
    "company_created": "Создание компании",
    "user_updated": "Изменение пользователя",
    "user_disabled": "Блокировка",
    "user_enabled": "Разблокировка",
    "permission_changed": "Изменение индивидуального доступа",
    "widget_permission_changed": "Включение/отключение виджета",
    "module_access_changed": "Изменение доступа по типу пользователя",
    "role_changed": "Изменение пользователя",
    "users_imported": "Импорт пользователей",
    "bulk_access_assigned": "Массовое назначение доступа",
    "platform_module_registry_changed": "Включение/отключение модуля",
    "widget_registry_changed": "Включение/отключение виджета",
}

MODULE3_AUDIT_ACTION_TYPES: tuple[str, ...] = tuple(MODULE3_AUDIT_ACTION_LABELS)

SYSTEM_USER_CARD_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "login": "platform-admin",
        "roleCodes": {"PLATFORM_ADMIN"},
        "roleTitle": "Администратор платформы",
        "purpose": "Рабочее управление пользователями, компаниями и доступами.",
    },
    {
        "login": "super-admin",
        "roleCodes": {"SUPER_ADMIN"},
        "roleTitle": "Супер администратор",
        "purpose": "Полный контроль платформы, системные настройки и опасные действия.",
    },
    {
        "login": "moderator",
        "roleCodes": {"MODERATOR"},
        "roleTitle": "Модератор",
        "purpose": "Модерация пользователей, компаний и изменений доступа.",
    },
    {
        "login": "support-admin",
        "roleCodes": {"SUPPORT_ADMIN", "PLATFORM_ADMIN"},
        "roleTitle": "Поддержка",
        "purpose": "Помощь администраторам, проверка обращений и сопровождение доступа.",
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

ACCESS_SOURCE_LABELS: dict[str, str] = {
    "SYSTEM_DEFAULT": "Системный",
    "ROLE_DEFAULT": "По типу пользователя",
    "COMPANY_DEFAULT": "По компании",
    "GROUP_DEFAULT": "По группе",
    "USER_OVERRIDE": "Индивидуально переопределен",
    "TARIFF_LIMIT": "Ограничено тарифом",
    "SYSTEM_LIMIT": "Системный",
}

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
ROLE_LABELS["ENGINEER_DESIGNER"] = "Инженер-проектировщик"
ROLE_LABELS["PROCUREMENT_MANAGER"] = "Менеджер закупок"
ROLE_LABELS["PROJECT_MANAGER"] = "Менеджер проекта"

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
    return []


def module3_quick_action_settings(*, admin_scope: dict[str, Any], detail_mode: bool = False) -> dict[str, Any]:
    actions = module3_quick_actions(admin_scope=admin_scope, detail_mode=detail_mode)
    preferences = [
        build_user_quick_action_preference(
            user_id=str(admin_scope.get("userId") or "current-user"),
            quick_action_code=action["quickActionCode"],
            source_module_code=action["sourceModuleCode"],
            is_enabled=bool(action["enabled"]),
            is_pinned_in_module=bool(action["enabled"]),
            is_pinned_on_module_card=False,
            sort_order=index,
            disabled_reason=action.get("disabledReason"),
        )
        for index, action in enumerate(actions, start=1)
    ]
    return {
        "title": "Настроить быстрые действия",
        "sourceModuleCode": "MODULE_03_USERS_ROLES",
        "maxModuleActions": MAX_MODULE_BAR_QUICK_ACTIONS,
        "maxDashboardCardActions": MAX_MODULE_CARD_QUICK_ACTIONS,
        "storageLayer": "UserDashboardLayout.layout_settings.moduleQuickActions",
        "localStorageKey": "atom:module3:quickActionSettings:v1",
        "localAdapterNote": (
            "Временный UI adapter до подключения API сохранения. "
            "Контракт совместим с UserDashboardLayout.layout_settings.moduleQuickActions."
        ),
        "actions": [
            {
                **action,
                "sortOrder": index,
                "sourceLabel": _module3_quick_action_source_label(action.get("sectionCode")),
                "isModulePinnedByDefault": bool(action["enabled"]),
                "isDashboardPinnedByDefault": False,
                "canPin": bool(action["enabled"]),
                "unavailableReason": action.get("disabledReason") or ("" if action["enabled"] else "Действие сейчас недоступно."),
            }
            for index, action in enumerate(actions, start=1)
        ],
        "preferences": preferences,
    }


def _module3_quick_action_source_label(section_code: str | None) -> str:
    labels = {
        "USERS_TABLE": "Пользователи",
        "ACCESS_MATRIX": "Доступы",
        "AUDIT_LOG": "Журнал изменений",
        "SYSTEM_USERS": "Системные пользователи",
    }
    return labels.get(str(section_code or ""), "Module №3")


def user_type_summary_widgets(users: list[User], workspaces: list[Workspace]) -> list[dict[str, Any]]:
    company_workspaces = [workspace for workspace in workspaces if _is_company_workspace(workspace)]
    supplier_workspaces = [
        workspace
        for workspace in company_workspaces
        if _workspace_type_value(workspace) in {"SUPPLIER", "MATERIAL_SUPPLIER"}
    ]
    supplier_users = [user for user in users if _user_has_any_role(user, {"SUPPLIER"})]
    widgets: list[dict[str, Any]] = []

    for definition in USER_TYPE_WIDGET_DEFINITIONS:
        code = definition["userTypeCode"]
        if code == "COMPANY":
            total = len(company_workspaces)
            active = len([workspace for workspace in company_workspaces if _workspace_is_active(workspace)])
            blocked = len([workspace for workspace in company_workspaces if _workspace_is_blocked(workspace)])
            on_moderation = len([workspace for workspace in company_workspaces if _workspace_is_on_moderation(workspace)])
        elif code == "SUPPLIER" and supplier_workspaces:
            total = len(supplier_workspaces)
            active = len([workspace for workspace in supplier_workspaces if _workspace_is_active(workspace)])
            blocked = len([workspace for workspace in supplier_workspaces if _workspace_is_blocked(workspace)])
            on_moderation = len([workspace for workspace in supplier_workspaces if _workspace_is_on_moderation(workspace)])
        else:
            role_codes = set(definition.get("roleCodes") or {"SUPPLIER"})
            matching_users = supplier_users if code == "SUPPLIER" else [user for user in users if _user_has_any_role(user, role_codes)]
            total = len(matching_users)
            active = len([user for user in matching_users if _user_is_active(user)])
            blocked = len([user for user in matching_users if _user_is_blocked(user)])
            on_moderation = 0

        widget = {
            "userTypeCode": code,
            "title": definition["title"],
            "description": definition["description"],
            "total": total,
            "active": active,
            "blocked": blocked,
        }
        if definition.get("includeModeration"):
            widget["onModeration"] = on_moderation
        widgets.append(widget)

    return widgets


def module_registry_overview_summary() -> dict[str, Any]:
    modules = get_dashboard_module_registry()
    return _registry_status_summary(
        modules,
        status_key="status",
        active_values={"active"},
        in_development_values={"planned", "draft"},
        archived_values={"archived", "deprecated", "merged"},
    )


def widget_registry_overview_summary() -> dict[str, Any]:
    widgets = get_widget_registry()
    return _registry_status_summary(
        widgets,
        status_key="status",
        active_values={"active"},
        in_development_values={"planned", "draft"},
        archived_values={"archived", "deprecated", "disabled"},
    )


def system_user_cards(users: list[User], recent_history: list[AuditLog]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for definition in SYSTEM_USER_CARD_DEFINITIONS:
        user = _find_system_user(users, definition["roleCodes"], definition["login"])
        last_activity = _latest_user_activity(user, recent_history) if user else "нет данных"
        cards.append(
            {
                "login": definition["login"],
                "displayName": _get_value(user, "name") or _get_value(user, "email") or definition["login"],
                "email": _get_value(user, "email") or "",
                "roleTitle": definition["roleTitle"],
                "purpose": definition["purpose"],
                "status": _status_value(_get_value(user, "status")) or "not_configured",
                "statusLabel": _system_user_status_label(_get_value(user, "status")),
                "lastActivity": last_activity,
                "lastActivityCompact": _reference_datetime_label(last_activity),
                "isPlaceholder": user is None,
            }
        )
    return cards


def demo_recent_access_history_summaries(users: list[User], workspaces: list[Workspace]) -> list[dict[str, Any]]:
    if not _has_module3_demo_records(users, workspaces):
        return []
    base_time = _latest_demo_activity_time(users, workspaces) or datetime(2026, 7, 3, 14, 35)
    rows = [
        ("platform-admin", "Создана компания", "ООО «СтройПроект Юг»", "Компания активирована для проверки карточки и сотрудников."),
        ("platform-admin", "Изменён доступ", "MODULE_03_USERS_ROLES", "Строительным компаниям предоставлен доступ к управлению сотрудниками."),
        ("moderator", "Заблокирован пользователь", "demo.customer.blocked@atom.local", "Демо-сценарий блокировки пользователя."),
        ("super-admin", "Назначен доступ к модулю", "MODULE_01_MATERIAL_HUB", "Поставщику разрешен ограниченный доступ к материалам."),
        ("platform-admin", "Отключён виджет", "price-dynamics", "Индивидуальное ограничение виджета при включенном модуле."),
    ]
    return [
        {
            "id": f"module3-demo-history-{index}",
            "timestamp": _stringify_search_value((base_time - timedelta(minutes=index * 7)).replace(microsecond=0)),
            "timestampCompact": _reference_datetime_label((base_time - timedelta(minutes=index * 7)).replace(microsecond=0)),
            "actorId": actor,
            "actorName": actor,
            "action": action,
            "objectTypeCode": "ACCESS",
            "objectId": object_name,
            "objectName": object_name,
            "detailsText": details,
            "result": "SUCCESS",
        }
        for index, (actor, action, object_name, details) in enumerate(rows)
    ]


def _has_module3_demo_records(users: list[User], workspaces: list[Workspace]) -> bool:
    return any(_is_module3_demo_user(user) for user in users) or any(_is_module3_demo_workspace(workspace) for workspace in workspaces)


def _is_module3_demo_user(user: User) -> bool:
    email = str(_get_value(user, "email") or "").lower()
    name = str(_get_value(user, "name") or "").lower()
    return email.startswith("demo.") or email in {
        "platform-admin@atom.local",
        "super-admin@atom.local",
        "moderator@atom.local",
        "support-admin@atom.local",
    } or name in {"platform-admin", "super-admin", "moderator", "support-admin"}


def _is_module3_demo_workspace(workspace: Workspace) -> bool:
    slug = str(_get_value(workspace, "slug") or "").lower()
    name = str(_get_value(workspace, "name") or _get_value(workspace, "title") or "").lower()
    return slug.startswith("demo-") or "стройпроект юг" in name or "бетонпоставка кубань" in name


def _latest_demo_activity_time(users: list[User], workspaces: list[Workspace]) -> datetime | None:
    values: list[datetime] = []
    for item in [*users, *workspaces]:
        for field_name in ("updated_at", "created_at", "updatedAt", "createdAt"):
            value = _get_value(item, field_name)
            if isinstance(value, datetime):
                values.append(value)
    return max(values) if values else None


def user_directory_rows(users: list[User], workspaces: list[Workspace]) -> list[dict[str, Any]]:
    company_by_id = {
        str(workspace.id): company_summary(workspace)
        for workspace in workspaces
        if _is_company_workspace(workspace)
    }
    rows: list[dict[str, Any]] = []

    for user in users:
        user_data = user_summary(user)
        row_type = _directory_user_type(user_data)
        primary_workspace = _primary_user_workspace(user_data)
        company = company_by_id.get(str(primary_workspace.get("workspaceId") or "")) if primary_workspace else None
        last_activity = _get_value(user, "updated_at") or _get_value(user, "created_at")
        registered_at = _get_value(user, "created_at")
        search_blob = " ".join(
            _stringify_search_value(value)
            for value in (
                user_data["name"],
                user_data["email"],
                user_data.get("phone"),
                user_data["id"],
                primary_workspace.get("workspaceTitle") if primary_workspace else "",
                company.get("title") if company else "",
            )
        )
        blocking_state = "blocked" if _user_is_blocked(user) else "not_blocked"
        rows.append(
            {
                "id": f"user-{user_data['id']}",
                "subjectKind": "user",
                "typeCode": row_type["typeCode"],
                "typeLabel": row_type["typeLabel"],
                "displayName": user_data["name"],
                "companyName": primary_workspace.get("workspaceTitle") if primary_workspace else "—",
                "organizationLabel": primary_workspace.get("roleTitle") if primary_workspace else "не связан с компанией",
                "contacts": _contact_lines(user_data.get("email"), user_data.get("phone")),
                "status": user_data["status"],
                "statusLabel": _directory_status_label(user_data["status"], blocking_state),
                "moduleCount": user_data["allowedModuleCount"],
                "widgetCount": user_data["allowedWidgetCount"],
                "moduleLabel": f"{user_data['allowedModuleCount']} модулей",
                "widgetLabel": f"{user_data['allowedWidgetCount']} виджетов",
                "blocking": blocking_state,
                "blockingLabel": "Да" if blocking_state == "blocked" else "—",
                "activity": "has_activity" if last_activity else "no_activity",
                "lastActivity": last_activity or "нет данных",
                "lastActivityCompact": _compact_datetime_label(last_activity) or "—",
                "registeredAt": registered_at or "",
                "registeredAtCompact": _compact_datetime_label(registered_at) or "—",
                "region": _company_region_label(company),
                "moduleAccess": "has_modules" if user_data["allowedModuleCount"] else "no_modules",
                "isWithoutCompany": primary_workspace is None,
                "isWithoutType": row_type["typeCode"] == "USER",
                "isSystemUser": _is_system_user_for_directory(user),
                "sortName": user_data["name"].lower(),
                "sortType": row_type["typeLabel"].lower(),
                "cardUrl": f"/api/v1/admin/users-roles/view/users/{user_data['id']}",
                "searchBlob": search_blob.lower(),
            }
        )

    for workspace in workspaces:
        if not _is_company_workspace(workspace):
            continue
        company = company_summary(workspace)
        primary_user = _company_primary_user(workspace)
        row_type_code = "SUPPLIER" if _workspace_type_value(workspace) in {"SUPPLIER", "MATERIAL_SUPPLIER"} else "COMPANY"
        row_type_label = "Поставщик" if row_type_code == "SUPPLIER" else "Компания"
        last_activity = _get_value(workspace, "updated_at") or _get_value(workspace, "created_at")
        registered_at = _get_value(workspace, "created_at")
        search_blob = " ".join(
            _stringify_search_value(value)
            for value in (
                company["title"],
                company["id"],
                company["type"],
                company["adminTitle"],
                _company_region_label(company),
                _get_value(workspace, "organization_id"),
            )
        )
        blocking_state = "not_blocked" if company["isActive"] else "blocked"
        rows.append(
            {
                "id": f"company-{company['id']}",
                "subjectKind": "company",
                "typeCode": row_type_code,
                "typeLabel": row_type_label,
                "displayName": company["title"],
                "companyName": company["title"],
                "organizationLabel": company["type"],
                "contacts": _contact_lines(company["adminTitle"], _get_value(workspace, "organization_id")),
                "status": str(company["status"] or "").lower(),
                "statusLabel": _directory_status_label(company["status"], blocking_state),
                "moduleCount": None,
                "widgetCount": None,
                "moduleLabel": company["moduleAccessState"],
                "widgetLabel": company["widgetAccessState"],
                "blocking": blocking_state,
                "blockingLabel": "—" if blocking_state == "not_blocked" else "Да",
                "activity": "has_activity" if last_activity else "no_activity",
                "lastActivity": last_activity or "нет данных",
                "lastActivityCompact": _compact_datetime_label(last_activity) or "—",
                "registeredAt": registered_at or "",
                "registeredAtCompact": _compact_datetime_label(registered_at) or "—",
                "region": _company_region_label(company),
                "moduleAccess": "has_modules" if company["isActive"] else "no_modules",
                "isWithoutCompany": False,
                "isWithoutType": False,
                "isSystemUser": False,
                "sortName": company["title"].lower(),
                "sortType": row_type_label.lower(),
                "cardUrl": _company_primary_user_card_url(primary_user) or "#companies",
                "searchBlob": search_blob.lower(),
            }
        )

    return sorted(rows, key=lambda item: (item["sortType"], item["sortName"]))


def user_directory_summary_chips(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chip_defs = (
        ("ALL", "Все"),
        ("COMPANY", "Компании"),
        ("SUPPLIER", "Поставщики"),
        ("CUSTOMER", "Заказчики"),
        ("SPECIALIST", "Специалисты"),
    )
    return [
        {
            "typeCode": code,
            "label": label,
            "count": len(rows) if code == "ALL" else len([row for row in rows if row["typeCode"] == code]),
        }
        for code, label in chip_defs
    ]


def user_directory_filter_options(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    return {
        "types": _directory_filter_options(rows, "typeCode", "typeLabel"),
        "statuses": _directory_filter_options(rows, "status", "statusLabel"),
        "regions": _directory_filter_options(rows, "region", "region"),
        "moduleAccess": [
            {"value": "has_modules", "label": "Есть доступ к модулям"},
            {"value": "no_modules", "label": "Нет доступа к модулям"},
        ],
    }


def verification_queue_summary(users: list[User], workspaces: list[Workspace]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for workspace in workspaces:
        if not _is_company_workspace(workspace):
            continue
        company = company_summary(workspace)
        target = _company_primary_user_card_url(_company_primary_user(workspace)) or "#companies"
        if _workspace_is_on_moderation(workspace):
            items.append(
                _verification_queue_item(
                    kind="COMPANY_REVIEW",
                    priority="high",
                    title="Компания на проверке",
                    subject=company["title"],
                    description="Проверьте данные компании, регион и назначенного администратора.",
                    target=target,
                    meta=[company["type"], company["status"]],
                )
            )
        if company["adminCount"] == 0:
            items.append(
                _verification_queue_item(
                    kind="COMPANY_ADMIN_MISSING",
                    priority="normal",
                    title="Нет администратора компании",
                    subject=company["title"],
                    description="Назначьте ответственного пользователя внутри компании.",
                    target=target,
                    meta=[company["type"], "admin не назначен"],
                )
            )

        for member in _safe_iterable(workspace.members):
            status = _status_value(_get_value(member, "status"))
            if status not in {"pending", "moderation", "review", "on_moderation", "pending_review", "invited", "invite_sent"}:
                continue
            user = _get_value(member, "user")
            user_id = _get_value(user, "id") or _get_value(member, "user_id")
            items.append(
                _verification_queue_item(
                    kind="COMPANY_MEMBER_REVIEW",
                    priority="normal",
                    title="Сотрудник ожидает проверки",
                    subject=_get_value(user, "name") or _get_value(user, "email") or str(user_id),
                    description="Проверьте роль сотрудника в компании и активируйте связь.",
                    target=f"/api/v1/admin/users-roles/view/users/{user_id}" if user_id else "#company-employees",
                    meta=[workspace.title, role_label(_get_value(member, "roleCode"))],
                )
            )

    for user in users:
        if _is_system_user_for_directory(user):
            continue
        status = _status_value(_get_value(user, "status"))
        target = f"/api/v1/admin/users-roles/view/users/{_get_value(user, 'id')}"
        subject = _get_value(user, "name") or _get_value(user, "email") or str(_get_value(user, "id"))
        if status in {"pending", "moderation", "review", "on_moderation", "pending_review", "invited", "invite_sent"}:
            items.append(
                _verification_queue_item(
                    kind="USER_REVIEW",
                    priority="normal",
                    title="Пользователь ожидает проверки",
                    subject=subject,
                    description="Проверьте выбранную роль и контактные данные пользователя.",
                    target=target,
                    meta=[_directory_status_label(status, "not_blocked")],
                )
            )
            continue
        if _user_is_active(user) and not active_role_codes_for_user(user):
            items.append(
                _verification_queue_item(
                    kind="ROLE_MISSING",
                    priority="normal",
                    title="Не выбрана роль",
                    subject=subject,
                    description="Роль должна прийти из регистрации; администратор может назначить роль вручную.",
                    target=target,
                    meta=["роль не задана"],
                )
            )

    priority_order = {"high": 0, "normal": 1, "low": 2}
    items.sort(key=lambda item: (priority_order.get(item["priority"], 9), item["subject"].lower()))
    visible_items = items[:6]
    return {
        "summary": {
            "total": len(items),
            "visible": len(visible_items),
            "high": len([item for item in items if item["priority"] == "high"]),
            "normal": len([item for item in items if item["priority"] == "normal"]),
        },
        "items": visible_items,
        "allItems": items,
        "byKind": _verification_queue_kind_counts(items),
        "emptyState": "Очередь проверки пуста: новых компаний, пользователей и ролей на подтверждение нет.",
        "roleModelNote": "Основная роль приходит из регистрации, дополнительные роли и роли в компании учитываются как контекст пользователя; доступы задаются на вкладке «Доступы».",
    }


def _verification_queue_item(
    *,
    kind: str,
    priority: str,
    title: str,
    subject: str,
    description: str,
    target: str,
    meta: list[Any] | None = None,
) -> dict[str, Any]:
    priority_label = "Важно" if priority == "high" else "Проверить"
    return {
        "kind": kind,
        "priority": priority,
        "priorityLabel": priority_label,
        "tone": "danger" if priority == "high" else "warn",
        "title": title,
        "subject": subject,
        "description": description,
        "target": target,
        "meta": [str(item) for item in (meta or []) if item not in {None, ""}],
    }


def _verification_queue_kind_counts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {
        "COMPANY_REVIEW": "компании на проверке",
        "COMPANY_ADMIN_MISSING": "нет администратора",
        "COMPANY_MEMBER_REVIEW": "сотрудники на проверке",
        "USER_REVIEW": "пользователи на проверке",
        "ROLE_MISSING": "роль не выбрана",
    }
    counts: dict[str, int] = {}
    for item in items:
        kind = item.get("kind") or ""
        counts[kind] = counts.get(kind, 0) + 1
    return [
        {"kind": kind, "label": labels.get(kind, kind), "count": count}
        for kind, count in sorted(counts.items(), key=lambda value: labels.get(value[0], value[0]))
    ]


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
    directory_rows = user_directory_rows(users, workspaces)
    history_users_by_id = _module3_user_name_lookup(users)
    history_workspaces_by_id = _module3_workspace_name_lookup(workspaces)
    recent_history_rows = [
        audit_log_summary(item, users_by_id=history_users_by_id, workspaces_by_id=history_workspaces_by_id)
        for item in recent_history
    ]
    if not recent_history_rows:
        recent_history_rows = demo_recent_access_history_summaries(users, workspaces)
    return {
        "actorRoleCodes": sorted(active_role_codes_for_user(actor)),
        "adminScope": admin_scope,
        "users": [user_summary(user) for user in users],
        "roles": roles,
        "workspaces": [workspace_summary(workspace) for workspace in workspaces],
        "companies": [company_summary(workspace) for workspace in workspaces if _is_company_workspace(workspace)],
        "companyEmployees": company_employee_summaries(workspaces),
        "groups": access_group_summaries(roles),
        "userTypeSummaryWidgets": user_type_summary_widgets(users, workspaces),
        "moduleRegistrySummary": module_registry_overview_summary(),
        "widgetRegistrySummary": widget_registry_overview_summary(),
        "systemUsers": system_user_cards(users, recent_history),
        "userDirectoryRows": directory_rows,
        "userDirectoryChips": user_directory_summary_chips(directory_rows),
        "userDirectoryFilters": user_directory_filter_options(directory_rows),
        "verificationQueue": verification_queue_summary(users, workspaces),
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
        "userTypeAccessMatrix": user_type_access_matrix_view_model(),
        "moduleQuickActions": module3_quick_actions(admin_scope=admin_scope, detail_mode=False),
        "moduleQuickActionSettings": module3_quick_action_settings(admin_scope=admin_scope, detail_mode=False),
        "recentAccessHistory": recent_history_rows,
        "historyTotal": len(recent_history_rows),
        "auditPanel": audit_panel_summary(recent_history, users=users, workspaces=workspaces),
        "settingsPanel": settings_panel_summary(admin_scope),
        "stateLegend": list(ADMIN_UI_STATE_LEGEND),
    }


async def get_user_role_admin_history(
    db: AsyncSession,
    actor: Any,
    *,
    limit: int = 200,
) -> dict[str, Any]:
    require_user_role_admin(actor)
    admin_scope = admin_scope_for_actor(actor)
    users = _filter_users_for_admin_scope(await _load_users(db), admin_scope)
    workspaces = _filter_workspaces_for_admin_scope(await _load_workspaces(db), admin_scope)
    history = await _load_recent_access_history(
        db,
        workspace_ids=_workspace_uuid_scope(admin_scope),
        limit=limit,
    )
    history = _filter_history_for_admin_scope(history, admin_scope)
    return {
        "actorRoleCodes": sorted(active_role_codes_for_user(actor)),
        "adminScope": admin_scope,
        "auditPanel": audit_panel_summary(history, users=users, workspaces=workspaces),
        "fieldDescriptions": [
            {"label": "Дата и время", "description": "Момент записи события в AuditLog."},
            {"label": "Администратор", "description": "Кто выполнил изменение или системный источник события."},
            {"label": "Действие", "description": "Тип операции: изменение роли, доступа, модуля, виджета или статуса."},
            {"label": "Объект", "description": "Пользователь, компания, модуль, виджет или роль, к которым относится событие."},
            {"label": "Старое / новое значение", "description": "Фиксация изменения без записи бизнес-payload."},
            {"label": "Причина", "description": "Комментарий администратора или системное объяснение изменения."},
            {"label": "Статус", "description": "Результат выполнения события."},
        ],
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
    access_matrix = access_matrix_for_subject(
        user_data,
        workspaces=workspaces,
        roles=roles,
        permissions=permissions,
        include_system_critical=admin_scope["canSeeSystemCriticalModules"],
    )
    profile_card = user_profile_card_summary(
        user,
        user_data=user_data,
        workspaces=workspaces,
        access_matrix=access_matrix,
        history=history,
    )
    await write_audit_event(
        db,
        AuditLogType.MODULE8_CONTEXT_ADAPTER_READ,
        actor_user_id=_get_value(actor, "id"),
        target_user_id=user.id,
        workspace_id=module8_preview_data.get("workspaceId") or access_context.workspaceId,
        module_code="MODULE_08_PARTNER_PORTAL",
        canonical_module_code="MODULE_08_PARTNER_PORTAL",
        reason="Module 03 Admin UI read legacy draft cabinet context through adapter/DTO.",
        entity_type="Module8CabinetAdminPreviewDTO",
        entity_id=module8_preview_data.get("activeCabinetId"),
        metadata={
            "sourceModuleCode": "MODULE_08_PARTNER_PORTAL",
            "moduleBoundaryStatus": "LEGACY_DRAFT_BOUNDARY",
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
        "accessMatrix": access_matrix,
        "profileCard": profile_card,
        "accessContextForCabinet": access_context.to_dict(),
        "module8CabinetPreview": module8_preview_data,
        "moduleQuickActions": module3_quick_actions(admin_scope=admin_scope, detail_mode=True),
        "moduleQuickActionSettings": module3_quick_action_settings(admin_scope=admin_scope, detail_mode=True),
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
        "auditPanel": audit_panel_summary(history, users=users, workspaces=workspaces),
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
    allowed_widget_codes = {
        _get_value(access, "function_key") or _get_value(access, "functionKey")
        for access in _safe_iterable(user.function_access)
        if _enum_value(_get_value(access, "access_level") or _get_value(access, "accessLevel")).upper() not in {"NO_ACCESS", "DENY", "CLOSED", "DISABLED"}
        and _enum_value(_get_value(access, "status")).upper() in {"", "ACTIVE"}
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
        "allowedWidgetCount": len([widget_code for widget_code in allowed_widget_codes if widget_code]),
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
    settings = _dict_value(_get_value(workspace, "settings"))
    return {
        "id": str(workspace.id),
        "title": workspace.title,
        "type": workspace.type,
        "status": workspace.status,
        "region": settings.get("region") or settings.get("regionCode") or settings.get("activeRegionCode"),
        "city": settings.get("city") or settings.get("cityName"),
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


def user_profile_card_summary(
    user: User,
    *,
    user_data: dict[str, Any],
    workspaces: list[Workspace],
    access_matrix: dict[str, Any],
    history: list[AuditLog],
) -> dict[str, Any]:
    primary_workspace = _primary_user_workspace(user_data)
    workspace = _find_workspace_by_id(workspaces, primary_workspace.get("workspaceId"))
    company = company_summary(workspace) if workspace and _is_company_workspace(workspace) else None
    company_details = _profile_company_details(workspace, company)
    employee_block = _profile_employee_role_block(workspace)
    subject_type = _profile_subject_type(user_data, company_details)
    status = str(user_data.get("status") or "").lower()
    is_blocked = status in {"blocked", "disabled", "deleted"}
    registered_at = _get_value(user, "created_at") or user_data.get("createdAt")
    region = company_details.get("region") or primary_workspace.get("region") or "не задан"

    return {
        "subjectType": "COMPANY" if company else "USER",
        "header": {
            "title": company_details.get("title") or user_data["name"],
            "subtitle": user_data["name"] if company else user_data.get("email"),
            "typeLabel": subject_type["typeLabel"],
            "typeCode": subject_type["typeCode"],
            "status": status,
            "statusLabel": _profile_status_label(status),
            "blockLabel": "Заблокирован" if is_blocked else "Без блокировки",
            "primaryContact": user_data.get("email") or company_details.get("adminTitle") or "не задан",
            "phone": user_data.get("phone") or "не задан",
            "region": region,
            "registeredAt": registered_at or "не задана",
            "assignedManager": company_details.get("assignedManager") or "не назначен",
            "actions": _profile_header_actions(is_blocked),
        },
        "generalInfo": _profile_general_info(user_data, subject_type, region, registered_at, is_blocked),
        "companyInfo": company_details.get("fields") or [],
        "employeeRoles": employee_block,
        "moduleAccessRows": _profile_module_access_rows(user_data, access_matrix),
        "widgetAccessGroups": _profile_widget_access_groups(access_matrix),
        "activityRows": [audit_log_summary(item) for item in history[:6]],
        "effectiveAccess": {
            "subjectType": "USER",
            "subjectId": user_data["id"],
            "sources": [
                {"source": "TYPE_TEMPLATE", "label": "По типу пользователя"},
                {"source": "USER_OVERRIDE", "label": "Индивидуально переопределен"},
                {"source": "SYSTEM", "label": "Системный"},
            ],
        },
        "selectedWorkspaceId": primary_workspace.get("workspaceId"),
    }


def _profile_header_actions(is_blocked: bool) -> list[dict[str, Any]]:
    return [
        {
            "id": "edit-access",
            "label": "Редактировать доступы",
            "actionType": "navigate",
            "target": "#access-matrix-detail",
            "enabled": True,
            "tone": "default",
        },
        {
            "id": "toggle-block",
            "label": "Разблокировать" if is_blocked else "Заблокировать",
            "actionType": "modal",
            "target": "#danger-zone",
            "enabled": True,
            "tone": "default" if is_blocked else "danger",
        },
        {
            "id": "assign-access",
            "label": "Назначить доступ",
            "actionType": "navigate",
            "target": "#access-matrix-detail",
            "enabled": True,
            "tone": "default",
        },
    ]


def _profile_subject_type(user_data: dict[str, Any], company_details: dict[str, Any]) -> dict[str, str]:
    if company_details:
        return {
            "typeCode": company_details.get("typeCode") or "COMPANY",
            "typeLabel": company_details.get("companyTypeLabel") or "Компания",
        }
    return _directory_user_type(user_data)


def _profile_general_info(
    user_data: dict[str, Any],
    subject_type: dict[str, str],
    region: str,
    registered_at: Any,
    is_blocked: bool,
) -> list[dict[str, Any]]:
    return [
        _profile_field("Тип", subject_type["typeLabel"]),
        _profile_field("Email", user_data.get("email") or "не задан"),
        _profile_field("Телефон", user_data.get("phone") or "не задан"),
        _profile_field("Регион", region or "не задан"),
        _profile_field("Дата регистрации", registered_at or "не задана"),
        _profile_field("Статус", _profile_status_label(user_data.get("status"))),
        _profile_field("Блокировка", "Заблокирован" if is_blocked else "Без блокировки"),
    ]


def _profile_company_details(workspace: Workspace | None, company: dict[str, Any] | None) -> dict[str, Any]:
    if not workspace or not company:
        return {}
    settings = _dict_value(_get_value(workspace, "settings"))
    company_type_label = _company_type_label(_workspace_type_value(workspace))
    inn = _settings_first(settings, "inn", "INN", "taxId", "tax_id") or _get_value(workspace, "organization_id")
    fields = [
        _profile_field("Название компании", company["title"]),
        _profile_field("Тип компании", company_type_label),
        _profile_field("Статус", company.get("status") or "не задан"),
        _profile_field("Регион / город", _company_region_label(company) or "не задан"),
        _profile_field("Администратор компании", company.get("adminTitle") or "администратор не назначен"),
        _profile_field("ИНН", inn or "не задан"),
        _profile_field("КПП", _settings_first(settings, "kpp", "KPP") or "не задан"),
        _profile_field("ОГРН", _settings_first(settings, "ogrn", "OGRN") or "не задан"),
        _profile_field(
            "Юридический адрес",
            _settings_first(settings, "legalAddress", "legal_address", "juridicalAddress", "address") or "не задан",
        ),
    ]
    return {
        "id": company["id"],
        "title": company["title"],
        "typeCode": "SUPPLIER" if _workspace_type_value(workspace) in {"SUPPLIER", "MATERIAL_SUPPLIER"} else "COMPANY",
        "companyTypeLabel": company_type_label,
        "status": company.get("status"),
        "region": _company_region_label(company),
        "adminTitle": company.get("adminTitle"),
        "assignedManager": _settings_first(settings, "assignedManager", "assignedManagerName", "managerName", "manager"),
        "fields": fields,
    }


def _profile_employee_role_block(workspace: Workspace | None) -> dict[str, Any]:
    if not workspace or not _is_company_workspace(workspace):
        return {"summary": [], "recent": [], "total": 0}
    active_members = [
        member
        for member in _safe_iterable(workspace.members)
        if _enum_value(_get_value(member, "status")).upper() in {"", "ACTIVE"}
    ]
    leader_count = len([member for member in active_members if _member_role_in(member, COMPANY_ADMIN_COMPATIBLE_ROLE_CODES | {COMPANY_ADMIN_ROLE_CODE})])
    engineer_count = len([member for member in active_members if _member_role_in(member, {"ENGINEER", "ENGINEER_DESIGNER", "ESTIMATOR", "CONTRACTOR"})])
    buyer_count = len([member for member in active_members if _member_role_in(member, {"BUYER", "PURCHASER", "PROCUREMENT", "SUPPLIER"})])
    manager_count = len([member for member in active_members if _member_role_contains(member, "MANAGER")])
    return {
        "total": len(active_members),
        "summary": [
            {"label": "Сотрудники", "value": len(active_members)},
            {"label": "Руководители", "value": leader_count},
            {"label": "Инженеры", "value": engineer_count},
            {"label": "Закупщики", "value": buyer_count},
            {"label": "Менеджеры", "value": manager_count},
        ],
        "recent": [
            {
                "userId": str(_get_value(member, "user_id") or _get_value(member, "userId") or ""),
                "name": _get_value(_get_value(member, "user"), "name")
                or _get_value(_get_value(member, "user"), "email")
                or str(_get_value(member, "user_id") or ""),
                "roleTitle": role_label(_get_value(member, "roleCode") or _get_value(member, "role_code")),
                "status": _enum_value(_get_value(member, "status")) or "ACTIVE",
            }
            for member in active_members[:5]
        ],
    }


def _profile_module_access_rows(user_data: dict[str, Any], access_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    subject_id = str(user_data.get("id") or "")
    selected_company_id = access_matrix.get("selectedCompanyId")
    for row in access_matrix.get("rows") or []:
        cell = row.get("employee") if selected_company_id else row.get("user")
        editable_cell = next((item for item in row.get("cells") or [] if item.get("key") == "employee"), cell or {})
        source = _effective_access_source(cell or {})
        rows.append(
            {
                "subjectType": "USER",
                "subjectId": subject_id,
                "moduleCode": row["moduleCode"],
                "moduleTitle": row["title"],
                "widgetCount": row.get("widgetCount", 0),
                "allowed": (cell or {}).get("stateCode") == "OPEN",
                "accessLabel": (cell or {}).get("label"),
                "accessStatus": (cell or {}).get("stateCode"),
                "reason": (cell or {}).get("reason"),
                "source": source,
                "sourceLabel": _effective_access_source_label(source),
                "resolutionSource": (cell or {}).get("resolutionSource"),
                "workspaceId": row.get("workspaceId"),
                "canOpen": bool(editable_cell.get("canOpen")),
                "canClose": bool(editable_cell.get("canClose")),
                "disabledReason": editable_cell.get("disabledReason") or (cell or {}).get("reason"),
            }
        )
    return rows


def _profile_widget_access_groups(access_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    selected_company_id = access_matrix.get("selectedCompanyId")
    for row in access_matrix.get("rows") or []:
        widgets = row.get("widgets") or []
        if not widgets:
            continue
        module_cell = row.get("employee") if selected_company_id else row.get("user")
        module_allowed = (module_cell or {}).get("stateCode") == "OPEN"
        groups.append(
            {
                "moduleCode": row["moduleCode"],
                "moduleTitle": row["title"],
                "moduleAllowed": module_allowed,
                "workspaceId": row.get("workspaceId"),
                "disabledReason": "" if module_allowed else ACCESS_DENY_REASONS["WIDGET_REVOKED_BY_MODULE_DENY"],
                "widgets": [
                    {
                        "widgetCode": widget["widgetCode"],
                        "title": widget["title"],
                        "allowed": widget.get("stateCode") == "OPEN",
                        "accessLabel": widget.get("label"),
                        "reason": widget.get("reason"),
                        "source": _effective_access_source(widget),
                        "sourceLabel": _effective_access_source_label(_effective_access_source(widget)),
                        "canOpen": bool(widget.get("canOpen")),
                        "canClose": bool(widget.get("canClose")),
                        "disabledReason": widget.get("disabledReason") or ("" if module_allowed else ACCESS_DENY_REASONS["WIDGET_REVOKED_BY_MODULE_DENY"]),
                    }
                    for widget in widgets
                ],
            }
        )
    return groups


def _profile_field(label: str, value: Any) -> dict[str, Any]:
    return {"label": label, "value": value if value not in {None, ""} else "не задан"}


def _profile_status_label(status: Any) -> str:
    normalized = str(status or "").lower()
    if normalized == "active":
        return "Активен"
    if normalized in {"blocked", "disabled"}:
        return "Заблокирован"
    if normalized == "deleted":
        return "Удален"
    return normalized or "не задан"


def _company_type_label(workspace_type: str) -> str:
    return {
        "SUPPLIER": "Поставщик",
        "MATERIAL_SUPPLIER": "Поставщик",
        "CONTRACTOR": "Строительная компания",
        "CONSTRUCTION_COMPANY": "Строительная компания",
        "ORGANIZATION": "Компания",
    }.get(workspace_type, workspace_type or "Компания")


def _settings_first(settings: dict[str, Any], *keys: str) -> Any:
    lowered = {str(key).lower(): value for key, value in settings.items()}
    for key in keys:
        if key in settings and settings[key] not in {None, ""}:
            return settings[key]
        lowered_value = lowered.get(key.lower())
        if lowered_value not in {None, ""}:
            return lowered_value
    return None


def _find_workspace_by_id(workspaces: list[Workspace], workspace_id: Any) -> Workspace | None:
    if not workspace_id:
        return None
    workspace_id_str = str(workspace_id)
    return next((workspace for workspace in workspaces if str(workspace.id) == workspace_id_str), None)


def _member_role_in(member: WorkspaceMember, role_codes: set[str]) -> bool:
    role_code = normalize_role_code(_get_value(member, "roleCode") or _get_value(member, "role_code"))
    return role_code in role_codes


def _member_role_contains(member: WorkspaceMember, pattern: str) -> bool:
    role_code = normalize_role_code(_get_value(member, "roleCode") or _get_value(member, "role_code"))
    return pattern in role_code


def _effective_access_source(cell: dict[str, Any]) -> str:
    resolution_source = str(cell.get("resolutionSource") or "")
    if resolution_source == "USER_OVERRIDE":
        return "USER_OVERRIDE"
    if resolution_source in {"ROLE_DEFAULT", "GROUP_DEFAULT", "COMPANY_DEFAULT"}:
        return "TYPE_TEMPLATE"
    return "SYSTEM"


def _effective_access_source_label(source: str) -> str:
    return {
        "TYPE_TEMPLATE": "По типу пользователя",
        "USER_OVERRIDE": "Индивидуально переопределен",
        "SYSTEM": "Системный",
    }.get(source, ACCESS_SOURCE_LABELS.get(source, source))


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
            "functionKey": access.function_key,
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
    widget_permission_map = _permission_map_by_widget(permissions)
    pending_module_codes, pending_widget_codes = _pending_access_distribution_codes()
    rows = [
        _access_matrix_module_row(
            module,
            permission_map=permission_map,
            widget_permission_map=widget_permission_map,
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
    widget_permission_map: dict[str, dict[str, Any]],
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
        widget_permission_map=widget_permission_map,
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
    widget_permission_map: dict[str, dict[str, Any]],
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
            elif widget_permission := _widget_permission_for_widget(widget_permission_map, widget):
                if _access_level_is_open(widget_permission.get("accessLevel")):
                    cell = _matrix_cell("OPEN", "Открыто индивидуальным правилом пользователя.", "USER_OVERRIDE")
                else:
                    cell = _matrix_cell(
                        "CLOSED",
                        "Закрыто индивидуальным правилом пользователя.",
                        "USER_OVERRIDE",
                        reason_code="PLATFORM_ADMIN_DENY",
                    )
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
    if explicit_permission:
        source = "USER_OVERRIDE" if explicit_permission.get("source") == "user_override" else "ROLE_DEFAULT"
        return _matrix_cell("OPEN", open_reason, source)
    return _matrix_cell("OPEN", open_reason, "SYSTEM_DEFAULT")


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


def _permission_map_by_widget(permissions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for permission in permissions:
        if permission.get("kind") != "feature":
            continue
        for key in (permission.get("functionKey"), permission.get("featureCode")):
            if key:
                result[str(key)] = permission
    return result


def _widget_permission_for_widget(
    permissions: dict[str, dict[str, Any]],
    widget: dict[str, Any],
) -> dict[str, Any] | None:
    widget_code = widget.get("widgetCode")
    feature_code = widget.get("featureCode")
    if widget_code and str(widget_code) in permissions:
        return permissions[str(widget_code)]
    if feature_code and str(feature_code) in permissions:
        return permissions[str(feature_code)]
    return None


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


def audit_log_summary(
    item: AuditLog,
    *,
    users_by_id: dict[str, str] | None = None,
    workspaces_by_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    details = item.details or {}
    entity_type = _details_value(details, "entityType") or item.entity_type
    entity_id = _details_value(details, "entityId") or str(item.entity_id or "")
    module_code = _details_value(details, "moduleCode")
    widget_code = _details_value(details, "widgetCode")
    role_code = _details_value(details, "roleCode")
    workspace_id = _details_value(details, "workspaceId") or str(item.workspace_id or "")
    target_user_id = _details_value(details, "targetUserId")
    object_type = _audit_object_type(entity_type, module_code=module_code, widget_code=widget_code, role_code=role_code)
    subject_label = _audit_subject_label(entity_type, target_user_id=target_user_id, workspace_id=workspace_id, module_code=module_code, widget_code=widget_code)
    actor_id = _details_value(details, "actorUserId") or str(item.user_id or "")
    actor_name = item.user.email if item.user else "system/dev"
    reason = _details_value(details, "reason") or _details_value(details, "comment") or ""
    summary = {
        "id": str(item.id),
        "createdAt": item.created_at,
        "actionType": item.action_type,
        "result": item.result,
        "actor": actor_name,
        "actorUserId": actor_id,
        "targetUserId": target_user_id,
        "workspaceId": workspace_id,
        "moduleCode": module_code,
        "canonicalModuleCode": _details_value(details, "canonicalModuleCode"),
        "featureCode": _details_value(details, "featureCode"),
        "widgetCode": widget_code,
        "roleCode": role_code,
        "oldValue": _details_value(details, "oldValue"),
        "newValue": _details_value(details, "newValue"),
        "reason": reason,
        "comment": _details_value(details, "comment") or "",
        "entityType": entity_type,
        "entityId": entity_id,
        "objectType": object_type,
        "subjectLabel": subject_label,
        "details": details,
    }
    module3_entry = module3_audit_log_entry(
        summary,
        users_by_id=users_by_id,
        workspaces_by_id=workspaces_by_id,
    )
    summary.update(
        {
            "timestamp": module3_entry["timestamp"],
            "timestampCompact": _compact_datetime_label(module3_entry["timestamp"]),
            "timestampReference": _reference_datetime_label(module3_entry["timestamp"]),
            "actorId": module3_entry["actorId"],
            "actorName": module3_entry["actorName"],
            "action": module3_entry["action"],
            "objectTypeCode": module3_entry["objectType"],
            "objectId": module3_entry["objectId"],
            "objectName": module3_entry["objectName"],
            "detailsText": module3_entry["details"],
            "module3Entry": module3_entry,
        }
    )
    summary.update(_module3_audit_display_fields(summary, module3_entry))
    return summary


def module3_audit_log_entry(
    row: dict[str, Any],
    *,
    users_by_id: dict[str, str] | None = None,
    workspaces_by_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    object_type_code = _module3_object_type_code(row)
    object_id = row.get("widgetCode") or row.get("moduleCode") or row.get("targetUserId") or row.get("workspaceId") or row.get("entityId") or ""
    object_name = _module3_history_subject_name(
        row,
        object_type_code=object_type_code,
        object_id=object_id,
        users_by_id=users_by_id,
        workspaces_by_id=workspaces_by_id,
    )
    details_text = _module3_audit_details_text(row)
    return {
        "id": str(row.get("id") or ""),
        "timestamp": _stringify_search_value(row.get("createdAt")),
        "actorId": str(row.get("actorUserId") or row.get("actorId") or ""),
        "actorName": str(row.get("actor") or row.get("actorName") or "system/dev"),
        "action": _module3_specific_action_label(row),
        "objectType": object_type_code,
        "objectId": str(object_id or ""),
        "objectName": str(object_name or ""),
        "details": details_text,
    }


def _module3_specific_action_label(row: dict[str, Any]) -> str:
    action_type = str(row.get("actionType") or "").strip().lower()
    old_open = _module3_value_open_state(row.get("oldValue"))
    new_open = _module3_value_open_state(row.get("newValue"))

    if action_type in {"permission_changed", "module_access_changed"}:
        if new_open is True and old_open is not True:
            return "Доступ добавлен"
        if new_open is False and old_open is not False:
            return "Доступ ограничен"
        if action_type == "module_access_changed":
            return "Доступ изменен"
        return "Доступ изменен"

    if action_type in {"widget_permission_changed", "widget_registry_changed"}:
        if new_open is True and old_open is not True:
            return "Виджет добавлен"
        if new_open is False and old_open is not False:
            return "Виджет ограничен"
        return "Виджет изменен"

    if action_type == "platform_module_registry_changed":
        if new_open is True and old_open is not True:
            return "Модуль добавлен"
        if new_open is False and old_open is not False:
            return "Модуль ограничен"
        return "Модуль изменен"

    if action_type in {"user_disabled"}:
        return "Блокировка"
    if action_type in {"user_enabled"}:
        return "Разблокировка"
    if action_type in {"user_created"}:
        return "Пользователь добавлен"
    if action_type in {"company_created"}:
        return "Компания добавлена"
    if action_type in {"role_changed", "user_role_assigned", "company_employee_role_changed"}:
        return "Роль изменена"
    if action_type == "bulk_access_assigned":
        return "Доступ назначен"
    if action_type == "user_dashboard_layout_changed":
        return "Панель изменена"

    return MODULE3_AUDIT_ACTION_LABELS.get(action_type, str(row.get("actionType") or "Изменение"))


def _module3_value_open_state(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        for key in ("accessLevel", "access_level"):
            if key in value:
                return _access_level_is_open(value.get(key))
        for key in ("enabled", "isEnabled", "is_active", "isActive"):
            if key in value:
                return bool(value.get(key))
        for key in ("status", "state"):
            if key in value:
                return _module3_status_open_state(value.get(key))
        return None
    return _module3_status_open_state(value)


def _module3_status_open_state(value: Any) -> bool | None:
    raw = str(value or "").strip().upper()
    if raw in {"NO_ACCESS", "DENY", "DENIED", "CLOSED", "DISABLED", "BLOCKED", "DELETED", "ARCHIVED", "FALSE", "0"}:
        return False
    if raw in {"ACTIVE", "ENABLED", "OPEN", "ALLOWED", "READ", "WRITE", "ADMIN", "OWNER", "TRUE", "1"}:
        return True
    return None


def _module3_history_subject_name(
    row: dict[str, Any],
    *,
    object_type_code: str,
    object_id: Any,
    users_by_id: dict[str, str] | None = None,
    workspaces_by_id: dict[str, str] | None = None,
) -> str:
    details = _dict_value(row.get("details"))
    users_by_id = users_by_id or {}
    workspaces_by_id = workspaces_by_id or {}
    target_user_id = str(row.get("targetUserId") or details.get("targetUserId") or details.get("target_user_id") or "")
    workspace_id = str(row.get("workspaceId") or details.get("workspaceId") or details.get("workspace_id") or "")

    if target_user_id and users_by_id.get(target_user_id):
        return users_by_id[target_user_id]
    if workspace_id and workspaces_by_id.get(workspace_id):
        return workspaces_by_id[workspace_id]

    for key in (
        "subjectName",
        "targetUserName",
        "target_user_name",
        "userName",
        "companyName",
        "supplierName",
        "workspaceTitle",
        "workspaceName",
        "objectName",
        "title",
        "name",
        "targetUserEmail",
        "email",
    ):
        value = details.get(key) or row.get(key)
        if value and not _module3_is_opaque_identifier(value):
            return str(value)

    if object_type_code == "WIDGET" and row.get("widgetCode"):
        widget = get_widget_registry_item(str(row.get("widgetCode")))
        return str(_get_value(widget, "title") or row.get("widgetCode"))
    if object_type_code in {"MODULE", "ACCESS"} and row.get("moduleCode"):
        module = get_dashboard_module_registry_item(str(row.get("moduleCode")))
        return str(_get_value(module, "title") or row.get("moduleCode"))

    candidate = row.get("subjectLabel") or row.get("objectName") or object_id
    if candidate and not _module3_is_opaque_identifier(candidate):
        return str(candidate)
    return _module3_object_type_display_label(object_type_code)


def _module3_is_opaque_identifier(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        UUID(raw)
        return True
    except ValueError:
        return False


def _module3_user_name_lookup(users: list[User] | None) -> dict[str, str]:
    return {
        str(_get_value(user, "id")): str(_get_value(user, "name") or _get_value(user, "email") or _get_value(user, "id"))
        for user in (users or [])
        if _get_value(user, "id")
    }


def _module3_workspace_name_lookup(workspaces: list[Workspace] | None) -> dict[str, str]:
    return {
        str(_get_value(workspace, "id")): str(_get_value(workspace, "title") or _get_value(workspace, "name") or _get_value(workspace, "id"))
        for workspace in (workspaces or [])
        if _get_value(workspace, "id")
    }


def _module3_audit_display_fields(row: dict[str, Any], entry: dict[str, Any]) -> dict[str, str]:
    module_label, widget_label = _module3_module_widget_display_label(row)
    subject_name = str(entry.get("objectName") or row.get("subjectLabel") or "").strip()
    return {
        "displayTimestamp": _reference_datetime_label(row.get("createdAt") or entry.get("timestamp")),
        "displayTimestampShort": _compact_datetime_label(row.get("createdAt") or entry.get("timestamp")),
        "displayActor": _module3_actor_display_label(entry.get("actorName") or row.get("actor")),
        "displayAction": str(entry.get("action") or row.get("actionType") or "Изменение"),
        "displayObject": _module3_object_display_label(row, entry),
        "displayObjectType": _module3_object_type_display_label(entry.get("objectType") or row.get("objectType")),
        "displaySubjectName": subject_name,
        "displayDetails": _module3_overview_details_label(row, entry),
        "displayOldValue": _module3_value_display_label(row.get("oldValue")),
        "displayNewValue": _module3_value_display_label(row.get("newValue")),
        "displayModule": module_label,
        "displayWidget": widget_label,
        "displayModuleWidget": " / ".join(part for part in (module_label, widget_label) if part) or "—",
        "displayResult": _module3_result_display_label(row.get("result")),
    }


def _module3_actor_display_label(value: Any) -> str:
    label = str(value or "").strip()
    if not label or label.lower() in {"system/dev", "system", "dev"}:
        return "Admin"
    if "@" in label:
        return label.split("@", 1)[0]
    return label


def _module3_object_display_label(row: dict[str, Any], entry: dict[str, Any]) -> str:
    widget_code = row.get("widgetCode")
    if widget_code:
        widget = get_widget_registry_item(str(widget_code))
        return str(_get_value(widget, "title") or widget_code)
    module_code = row.get("moduleCode")
    if module_code:
        module = get_dashboard_module_registry_item(str(module_code))
        return str(_get_value(module, "title") or module_code)
    object_name = str(entry.get("objectName") or row.get("subjectLabel") or "").strip()
    if object_name and object_name.upper() not in {"USER", "COMPANY", "MODULE", "WIDGET", "ACCESS", "SYSTEM_USER"}:
        return object_name
    return _module3_object_type_display_label(entry.get("objectType") or row.get("objectType"))


def _module3_object_type_display_label(value: Any) -> str:
    labels = {
        "USER": "Пользователь",
        "COMPANY": "Компания",
        "MODULE": "Модуль",
        "WIDGET": "Виджет",
        "ACCESS": "Доступ",
        "SYSTEM_USER": "Системный пользователь",
    }
    raw = str(value or "").strip()
    return labels.get(raw.upper(), raw or "Объект")


def _module3_module_widget_display_label(row: dict[str, Any]) -> tuple[str, str]:
    module_label = ""
    widget_label = ""
    module_code = row.get("moduleCode")
    widget_code = row.get("widgetCode")
    if module_code:
        module = get_dashboard_module_registry_item(str(module_code))
        module_label = str(_get_value(module, "title") or module_code)
    if widget_code:
        widget = get_widget_registry_item(str(widget_code))
        widget_label = str(_get_value(widget, "title") or widget_code)
    return module_label, widget_label


def _module3_overview_details_label(row: dict[str, Any], entry: dict[str, Any]) -> str:
    subject_name = _module3_compact_text(str(entry.get("objectName") or row.get("subjectLabel") or "").strip(), limit=72)
    reason = str(row.get("reason") or row.get("comment") or "").strip()
    if reason:
        detail = _module3_compact_text(reason, limit=110)
    else:
        new_value = row.get("newValue")
        if new_value is not None and new_value != "":
            detail = f"Новое значение: {_module3_value_display_label(new_value)}"
        else:
            details = str(entry.get("details") or "").strip()
            if details and details.upper() not in {"SUCCESS", "OK"}:
                detail = _module3_compact_text(details, limit=110)
            else:
                detail = _module3_result_display_label(row.get("result"))

    if subject_name and subject_name.lower() not in detail.lower():
        if detail in {"Успешно", "SUCCESS", "OK"}:
            return subject_name
        return _module3_compact_text(f"{subject_name} · {detail}", limit=132)
    return detail


def _module3_value_display_label(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Разрешено" if value else "Запрещено"
    if isinstance(value, list):
        return f"{len(value)} изменений"
    if isinstance(value, dict):
        if "accessLevel" in value:
            return _access_level_label(str(value.get("accessLevel") or ""))
        if "enabled" in value:
            return "Разрешено" if value.get("enabled") else "Запрещено"
        return f"{len(value)} поля"
    return _module3_compact_text(str(value), limit=120)


def _access_level_label(value: str) -> str:
    labels = {
        "NONE": "Нет доступа",
        "READ": "Просмотр",
        "WRITE": "Редактирование",
        "ADMIN": "Администрирование",
        "OWNER": "Владелец",
        "ALLOWED": "Разрешено",
        "DENIED": "Запрещено",
    }
    return labels.get(value.upper(), value or "—")


def _module3_result_display_label(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if raw in {"", "SUCCESS", "OK"}:
        return "Успешно"
    if raw in {"FAILED", "ERROR"}:
        return "Ошибка"
    return str(value)


def _module3_compact_text(value: str, *, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _module3_object_type_code(row: dict[str, Any]) -> str:
    if row.get("widgetCode"):
        return "WIDGET"
    if row.get("moduleCode"):
        action_type = str(row.get("actionType") or "")
        return "ACCESS" if "access" in action_type or "permission" in action_type else "MODULE"
    object_type = str(row.get("objectType") or "").lower()
    entity_type = str(row.get("entityType") or "").lower()
    if "company" in entity_type or object_type == "компания":
        return "COMPANY"
    if "workspace" in entity_type or object_type == "сотрудник компании":
        return "COMPANY"
    if "system" in entity_type:
        return "SYSTEM_USER"
    if "widget" in entity_type or object_type == "виджет":
        return "WIDGET"
    if "module" in entity_type or object_type == "модуль":
        return "MODULE"
    if "access" in entity_type or "permission" in entity_type:
        return "ACCESS"
    return "USER"


def _module3_audit_details_text(row: dict[str, Any]) -> str:
    reason = str(row.get("reason") or row.get("comment") or "")
    old_value = row.get("oldValue")
    new_value = row.get("newValue")
    parts = []
    if reason:
        parts.append(reason)
    if old_value is not None and old_value != "":
        parts.append(f"Старое значение: {old_value}")
    if new_value is not None and new_value != "":
        parts.append(f"Новое значение: {new_value}")
    if not parts:
        parts.append(str(row.get("result") or "SUCCESS"))
    return "; ".join(parts)


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


def audit_panel_summary(
    history: list[AuditLog],
    *,
    users: list[User] | None = None,
    workspaces: list[Workspace] | None = None,
) -> dict[str, Any]:
    users_by_id = _module3_user_name_lookup(users)
    workspaces_by_id = _module3_workspace_name_lookup(workspaces)
    rows = [audit_log_summary(item, users_by_id=users_by_id, workspaces_by_id=workspaces_by_id) for item in history]
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


def _registry_status_summary(
    items: list[dict[str, Any]],
    *,
    status_key: str,
    active_values: set[str],
    in_development_values: set[str],
    archived_values: set[str],
) -> dict[str, Any]:
    normalized_items = [
        {**item, "_normalizedStatus": str(item.get(status_key) or "").lower()}
        for item in items
    ]
    return {
        "total": len(normalized_items),
        "active": len([item for item in normalized_items if item["_normalizedStatus"] in active_values]),
        "inDevelopment": len([item for item in normalized_items if item["_normalizedStatus"] in in_development_values]),
        "archived": len([item for item in normalized_items if item["_normalizedStatus"] in archived_values]),
    }


def _is_company_workspace(workspace: Workspace) -> bool:
    return _workspace_type_value(workspace) in {
        "SUPPLIER",
        "CONTRACTOR",
        "ORGANIZATION",
        "CONSTRUCTION_COMPANY",
        "MATERIAL_SUPPLIER",
    }


def _workspace_type_value(workspace: Workspace | dict[str, Any]) -> str:
    return str(_get_value(workspace, "type") or _get_value(workspace, "workspace_type") or "").upper()


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


def _workspace_is_blocked(workspace: Workspace | dict[str, Any]) -> bool:
    status = _enum_value(_get_value(workspace, "status")).upper()
    if _workspace_is_on_moderation(workspace):
        return False
    is_active = _get_value(workspace, "is_active")
    if is_active is None:
        is_active = _get_value(workspace, "isActive")
    return status in {"BLOCKED", "DISABLED", "ARCHIVED", "DELETED"} or is_active is False


def _workspace_is_on_moderation(workspace: Workspace | dict[str, Any]) -> bool:
    status = _enum_value(_get_value(workspace, "status")).upper()
    return status in {"ON_MODERATION", "MODERATION", "PENDING", "PENDING_REVIEW", "NEEDS_REVIEW"}


def _user_has_any_role(user: User, role_codes: set[str]) -> bool:
    return bool(active_role_codes_for_user(user) & role_codes)


def _user_is_active(user: User) -> bool:
    return _status_value(_get_value(user, "status")) == "active"


def _user_is_blocked(user: User) -> bool:
    return _status_value(_get_value(user, "status")) in {"blocked", "disabled", "deleted"}


def _find_system_user(users: list[User], role_codes: set[str], login: str) -> User | None:
    normalized_login = login.lower()
    for user in users:
        email = str(_get_value(user, "email") or "").lower()
        name = str(_get_value(user, "name") or "").lower()
        if normalized_login in email or normalized_login in name:
            return user
    return next((user for user in users if _user_has_any_role(user, role_codes)), None)


def _is_system_user_for_directory(user: User) -> bool:
    email = str(_get_value(user, "email") or "").lower()
    name = str(_get_value(user, "name") or "").lower()
    if any(definition["login"] in email or definition["login"] in name for definition in SYSTEM_USER_CARD_DEFINITIONS):
        return True
    return any(_user_has_any_role(user, set(definition["roleCodes"])) for definition in SYSTEM_USER_CARD_DEFINITIONS)


def _system_user_status_label(status: Any) -> str:
    normalized = _status_value(status)
    if normalized == "active":
        return "Активен"
    if normalized == "blocked":
        return "Заблокирован"
    if normalized:
        return normalized
    return "Не настроен"


def _directory_status_label(status: Any, blocking_state: str) -> str:
    if blocking_state == "blocked":
        return "Заблокирован"
    normalized = _status_value(status)
    if normalized == "active":
        return "Активен"
    if normalized in {"pending", "moderation", "review", "on_moderation"}:
        return "На модерации"
    if normalized in {"invited", "invite_sent"}:
        return "Приглашен"
    if normalized in {"disabled", "archived", "deleted"}:
        return "Отключен"
    return normalized or "Не задан"


def _latest_user_activity(user: User | None, recent_history: list[AuditLog]) -> Any:
    if not user:
        return "нет данных"
    user_id = str(_get_value(user, "id") or "")
    for item in recent_history:
        if str(_get_value(item, "user_id") or "") == user_id:
            return item.created_at
    return _get_value(user, "updated_at") or _get_value(user, "created_at") or "нет данных"


def _directory_user_type(user_data: dict[str, Any]) -> dict[str, str]:
    role_codes = set(user_data.get("roleCodes") or [])
    workspace_types = {str(item.get("workspaceType") or "").upper() for item in user_data.get("workspaces") or []}
    if "SUPPLIER" in role_codes or "SUPPLIER" in workspace_types or "MATERIAL_SUPPLIER" in workspace_types:
        return {"typeCode": "SUPPLIER", "typeLabel": "Поставщик"}
    if "CUSTOMER" in role_codes:
        return {"typeCode": "CUSTOMER", "typeLabel": "Заказчик"}
    if role_codes & {"CONTRACTOR", "ESTIMATOR", "ENGINEER_DESIGNER"}:
        return {"typeCode": "SPECIALIST", "typeLabel": "Специалист"}
    return {"typeCode": "USER", "typeLabel": "Пользователь"}


def _primary_user_workspace(user_data: dict[str, Any]) -> dict[str, Any]:
    workspaces = user_data.get("workspaces") or []
    return workspaces[0] if workspaces else {}


def _company_region_label(company: dict[str, Any] | None) -> str:
    if not company:
        return ""
    return str(company.get("city") or company.get("region") or "")


def _contact_lines(*values: Any) -> list[str]:
    return [str(value) for value in values if value not in {None, ""}]


def _stringify_search_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _compact_datetime_label(value: Any) -> str:
    if value in {None, ""}:
        return ""
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        for candidate in (raw, raw.replace("Z", "+00:00"), raw.replace(" ", "T", 1)):
            try:
                parsed = datetime.fromisoformat(candidate)
                break
            except ValueError:
                continue
    if parsed:
        return parsed.strftime("%d.%m %H:%M")
    return str(value)[:16]


def _reference_datetime_label(value: Any) -> str:
    if value in {None, ""}:
        return ""
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        for candidate in (raw, raw.replace("Z", "+00:00"), raw.replace(" ", "T", 1)):
            try:
                parsed = datetime.fromisoformat(candidate)
                break
            except ValueError:
                continue
    if parsed:
        return parsed.strftime("%d.%m.%Y %H:%M")
    return str(value)[:16]


def _company_primary_user(workspace: Workspace) -> User | None:
    members = list(_safe_iterable(workspace.members))
    admins = [member for member in members if is_company_admin_role(member.roleCode) and _get_value(member, "user")]
    if admins:
        return admins[0].user
    member_with_user = next((member for member in members if _get_value(member, "user")), None)
    return member_with_user.user if member_with_user else None


def _company_primary_user_card_url(user: User | None) -> str | None:
    user_id = _get_value(user, "id")
    return f"/api/v1/admin/users-roles/view/users/{user_id}" if user_id else None


def _directory_filter_options(rows: list[dict[str, Any]], value_key: str, label_key: str) -> list[dict[str, str]]:
    options: dict[str, str] = {}
    for row in rows:
        value = str(row.get(value_key) or "")
        label = str(row.get(label_key) or value)
        if value:
            options.setdefault(value, label)
    return [{"value": value, "label": label} for value, label in sorted(options.items(), key=lambda item: item[1])]


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


def user_type_access_matrix_view_model() -> dict[str, Any]:
    columns = [
        {
            "userTypeCode": column["userTypeCode"],
            "label": column["label"],
            "sourceRoleCode": column["sourceRoleCode"],
        }
        for column in ACCESS_MATRIX_USER_TYPE_COLUMNS
    ]
    profiles = {
        column["userTypeCode"]: get_role_dashboard_access_profile(column["sourceRoleCode"]) or {}
        for column in columns
    }
    widgets_by_module = _matrix_widgets_by_module()
    rows: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    order = 0

    for module in get_dashboard_module_registry():
        module_code = module["canonicalModuleCode"] or module["moduleCode"]
        if module.get("status") in {"merged", "archived", "deprecated"}:
            continue
        order += 10
        module_row_id = f"module:{module_code}"
        module_row = {
            "id": module_row_id,
            "type": "MODULE",
            "moduleCode": module_code,
            "widgetCode": None,
            "parentId": None,
            "title": module.get("title") or module_code,
            "status": module.get("status") or "unknown",
            "statusLabel": _module_status_label(str(module.get("status") or "")),
            "order": order,
            "level": 0,
            "expanded": True,
            "cells": [],
        }
        for column in columns:
            cell = _user_type_module_access_cell(module_row_id, column, module, profiles[column["userTypeCode"]])
            module_row["cells"].append(cell)
            cells.append(cell)
        rows.append(module_row)

        for widget in widgets_by_module.get(module_code, []):
            order += 1
            widget_row_id = f"widget:{widget['widgetCode']}"
            widget_row = {
                "id": widget_row_id,
                "type": "WIDGET",
                "moduleCode": module_code,
                "widgetCode": widget["widgetCode"],
                "parentId": module_row_id,
                "title": widget["title"],
                "status": widget.get("status") or "UNKNOWN",
                "statusLabel": _widget_status_label(widget.get("status")),
                "order": order,
                "level": 1,
                "expanded": True,
                "cells": [],
            }
            for column in columns:
                parent_cell = next(cell for cell in module_row["cells"] if cell["userTypeCode"] == column["userTypeCode"])
                cell = _user_type_widget_access_cell(widget_row_id, column, widget, profiles[column["userTypeCode"]], parent_cell=parent_cell)
                widget_row["cells"].append(cell)
                cells.append(cell)
            rows.append(widget_row)

    return {
        "columns": columns,
        "rows": rows,
        "cells": cells,
        "filters": {
            "statusOptions": _matrix_status_options(rows),
            "userTypeOptions": [{"value": column["userTypeCode"], "label": column["label"]} for column in columns],
            "searchPlaceholder": "Поиск по модулю / виджету",
        },
        "saveAction": "/api/v1/admin/users-roles/view/access-matrix",
        "saveState": {
            "noChanges": "Изменений нет",
            "dirty": "Есть несохраненные изменения",
            "saving": "Сохранение",
            "error": "Ошибка сохранения",
            "success": "Успешно сохранено",
        },
        "viewModelNote": "AccessMatrixRow / AccessMatrixCell is a Module 03 UI adapter over existing permission profiles.",
    }


async def save_user_type_access_matrix_changes(
    db: AsyncSession | None,
    *,
    actor: Any,
    matrix_payload: dict[str, Any] | None,
) -> Any:
    payload = matrix_payload or {}
    rows = payload.get("rows") if isinstance(payload, dict) else None
    changes = payload.get("changes") if isinstance(payload, dict) else None
    bulk_action = payload.get("bulkAction") if isinstance(payload, dict) else None
    return await write_audit_event(
        db,
        AuditLogType.MODULE_ACCESS_CHANGED,
        actor_user_id=_get_value(actor, "id"),
        module_code="MODULE_03_USERS_ROLES",
        canonical_module_code="MODULE_03_USERS_ROLES",
        reason="User type access matrix saved from Module 03 UI adapter.",
        entity_type="Module3UserTypeAccessMatrix",
        entity_id=None,
        new_value={
            "rows": rows if isinstance(rows, list) else [],
            "changes": changes if isinstance(changes, list) else [],
            "bulkAction": bulk_action if isinstance(bulk_action, dict) else None,
        },
        metadata={
            "viewModelOnly": True,
            "permissionModelReplaced": False,
            "historyWritten": True,
            "rowCount": len(rows) if isinstance(rows, list) else 0,
            "changeCount": len(changes) if isinstance(changes, list) else 0,
            "bulkActionUsed": bool(bulk_action),
        },
    )


def _matrix_widgets_by_module() -> dict[str, list[dict[str, Any]]]:
    widgets_by_module: dict[str, list[dict[str, Any]]] = {}
    for widget in get_widget_registry():
        module_code = _canonical_module_code_value(widget.get("canonicalModuleCode") or widget.get("sourceModuleCode"))
        if not module_code:
            continue
        widgets_by_module.setdefault(module_code, []).append(widget)
    for widgets in widgets_by_module.values():
        widgets.sort(key=lambda item: (int(item.get("order") or 0), item.get("title") or item.get("widgetCode") or ""))
    return widgets_by_module


def _user_type_module_access_cell(
    row_id: str,
    column: dict[str, str],
    module: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    module_code = module["canonicalModuleCode"] or module["moduleCode"]
    module_status = str(module.get("status") or "").lower()
    allowed_modules = set(_list_strings(profile.get("allowedModuleCodes")))
    disabled = module_status != "active" or not module.get("isAvailableForDashboard")
    allowed = module_code in allowed_modules and not disabled
    return {
        "rowId": row_id,
        "userTypeCode": column["userTypeCode"],
        "allowed": allowed,
        "disabled": disabled,
        "inheritedFromModule": False,
        "reason": _module_status_disabled_reason(module_status) if disabled else ("Доступ разрешен профилем типа пользователя." if allowed else "Доступ запрещен профилем типа пользователя."),
        "sourceRoleCode": column["sourceRoleCode"],
    }


def _user_type_widget_access_cell(
    row_id: str,
    column: dict[str, str],
    widget: dict[str, Any],
    profile: dict[str, Any],
    *,
    parent_cell: dict[str, Any],
) -> dict[str, Any]:
    widget_status = str(widget.get("status") or "").upper()
    default_widgets = set(_list_strings(profile.get("defaultWidgetCodes")))
    hidden_widgets = set(_list_strings(profile.get("hiddenWidgetCodes")))
    module_allowed = bool(parent_cell.get("allowed"))
    system_disabled = widget_status != "ACTIVE"
    inherited_disabled = not module_allowed
    disabled = inherited_disabled or system_disabled
    allowed = widget["widgetCode"] in default_widgets and widget["widgetCode"] not in hidden_widgets and not disabled
    if inherited_disabled:
        reason = "Виджет недоступен, потому что модуль выключен для этого типа пользователя."
    elif system_disabled:
        reason = _widget_status_disabled_reason(widget_status)
    elif allowed:
        reason = "Виджет выбран в профиле типа пользователя."
    else:
        reason = "Виджет не выбран в профиле типа пользователя."
    return {
        "rowId": row_id,
        "userTypeCode": column["userTypeCode"],
        "allowed": allowed,
        "disabled": disabled,
        "inheritedFromModule": inherited_disabled,
        "reason": reason,
        "sourceRoleCode": column["sourceRoleCode"],
    }


def _matrix_status_options(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    statuses: dict[str, str] = {}
    for row in rows:
        if row["type"] != "MODULE":
            continue
        statuses[str(row["status"])] = str(row["statusLabel"])
    return [{"value": value, "label": label} for value, label in sorted(statuses.items(), key=lambda item: item[1])]


def _module_status_disabled_reason(status: str) -> str:
    if status == "planned":
        return ACCESS_DENY_REASONS["MODULE_PLANNED"]
    if status == "draft":
        return ACCESS_DENY_REASONS["MODULE_DRAFT"]
    if status != "active":
        return ACCESS_DENY_REASONS["MODULE_DISABLED"]
    return ACCESS_DENY_REASONS["SYSTEM_LIMIT"]


def _widget_status_label(status: Any) -> str:
    normalized = str(status or "").upper()
    return {
        "ACTIVE": "активен",
        "PLANNED": "запланирован",
        "DRAFT": "в подготовке",
        "DISABLED": "отключен",
        "DEPRECATED": "устаревает",
        "ARCHIVED": "архив",
    }.get(normalized, normalized.lower() or "не задан")


def _widget_status_disabled_reason(status: str) -> str:
    if status == "PLANNED":
        return ACCESS_DENY_REASONS["MODULE_PLANNED"]
    if status == "DRAFT":
        return ACCESS_DENY_REASONS["MODULE_DRAFT"]
    return ACCESS_DENY_REASONS["WIDGET_DISABLED"]


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


async def _load_recent_access_history(
    db: AsyncSession,
    *,
    workspace_ids: list[UUID] | None = None,
    limit: int = 6,
) -> list[AuditLog]:
    filters = [
        AuditLog.action_type.in_(
            [
                *MODULE3_AUDIT_ACTION_TYPES,
                AuditLogType.ROLE_CHANGED.value,
                AuditLogType.PERMISSION_CHANGED.value,
                AuditLogType.WIDGET_PERMISSION_CHANGED.value,
                AuditLogType.MODULE_ACCESS_CHANGED.value,
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
        .limit(limit)
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
    audit_details = dict(details or {})
    audit_details.setdefault("targetUserId", str(target_user.id))
    audit_details.setdefault("targetUserName", target_user.name or target_user.email or str(target_user.id))
    audit_details.setdefault("targetUserEmail", target_user.email)
    db.add(
        AuditLog(
            user_id=actor_id if isinstance(actor_id, UUID) else None,
            workspace_id=workspace_id,
            action_type=action_type,
            entity_type="User",
            entity_id=target_user.id,
            result="SUCCESS",
            details=audit_details,
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
