from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
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
from app.services.audit_log_service import AuditLogType, write_audit_event


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
PROTECTED_ROLE_CODES = {"SUPER_ADMIN"}
DISABLE_CONFIRMATION = "DISABLE_USER"


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
    return bool(active_role_codes_for_user(actor) & ADMIN_UI_ROLE_CODES)


def can_assign_role_code(actor: Any, role_code: str) -> bool:
    actor_roles = active_role_codes_for_user(actor)
    target_role = normalize_role_code(role_code)
    if not target_role or not can_open_user_role_admin(actor):
        return False
    if target_role in PROTECTED_ROLE_CODES and "SUPER_ADMIN" not in actor_roles:
        return False
    return True


def can_disable_user(actor: Any, target_user: Any) -> bool:
    actor_roles = active_role_codes_for_user(actor)
    target_roles = active_role_codes_for_user(target_user)
    if not can_open_user_role_admin(actor):
        return False
    if target_roles & PROTECTED_ROLE_CODES and "SUPER_ADMIN" not in actor_roles:
        return False
    if str(_get_value(actor, "id") or _get_value(actor, "userId") or "") == str(_get_value(target_user, "id") or ""):
        return False
    return True


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
        .options(selectinload(User.role_assignments).selectinload(UserRoleAssignment.role))
        .where(User.id == actor_id)
    )
    return result.scalar_one_or_none() or actor


async def get_user_role_admin_overview(db: AsyncSession, actor: Any) -> dict[str, Any]:
    require_user_role_admin(actor)
    users = await _load_users(db)
    roles = await _load_role_options(db, actor)
    workspaces = await _load_workspaces(db)
    return {
        "actorRoleCodes": sorted(active_role_codes_for_user(actor)),
        "users": [user_summary(user) for user in users],
        "roles": roles,
        "workspaces": [workspace_summary(workspace) for workspace in workspaces],
    }


async def get_user_role_admin_detail(db: AsyncSession, user_id: UUID, actor: Any) -> dict[str, Any]:
    require_user_role_admin(actor)
    user = await _get_user(db, user_id)
    roles = await _load_role_options(db, actor)
    workspaces = await _load_workspaces(db)
    history = await _load_user_history(db, user_id)
    return {
        "actorRoleCodes": sorted(active_role_codes_for_user(actor)),
        "user": user_summary(user, include_permissions=True),
        "roles": roles,
        "workspaces": [workspace_summary(workspace) for workspace in workspaces],
        "permissions": active_permissions_for_user(user),
        "history": [audit_log_summary(item) for item in history],
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
        "workspaces": workspaces,
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
    }
    if include_permissions:
        data["permissions"] = active_permissions_for_user(user)
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


def workspace_summary(workspace: Workspace) -> dict[str, Any]:
    return {
        "id": str(workspace.id),
        "title": workspace.title,
        "type": workspace.type,
        "isActive": workspace.isActive,
        "status": workspace.status,
    }


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


def audit_log_summary(item: AuditLog) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "createdAt": item.created_at,
        "actionType": item.action_type,
        "result": item.result,
        "actor": item.user.email if item.user else "system/dev",
        "details": item.details or {},
    }


def role_label(role_code: str | None) -> str:
    normalized = normalize_role_code(role_code)
    if not normalized:
        return "Нет роли"
    return ROLE_LABELS.get(normalized, normalized)


async def _load_users(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role_assignments).selectinload(UserRoleAssignment.role),
            selectinload(User.role_assignments).selectinload(UserRoleAssignment.workspace),
            selectinload(User.workspace_members).selectinload(WorkspaceMember.workspace),
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
    result = await db.execute(select(Workspace).order_by(Workspace.name.asc()))
    return list(result.scalars().all())


async def _load_user_history(db: AsyncSession, user_id: UUID) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .where(AuditLog.entity_type == "User", AuditLog.entity_id == user_id)
        .order_by(desc(AuditLog.created_at))
        .limit(30)
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
