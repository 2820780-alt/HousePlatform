from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


WORKSPACE_TYPES: tuple[str, ...] = (
    "INTERNAL",
    "SUPPLIER",
    "CONTRACTOR",
    "CUSTOMER",
    "PROJECT",
    "ORGANIZATION",
)

WORKSPACE_STATUSES: tuple[str, ...] = ("ACTIVE", "INVITED", "DISABLED")

WORKSPACE_TYPE_ALIASES: dict[str, str] = {
    "ADMIN": "INTERNAL",
    "ADMINISTRATION": "INTERNAL",
    "ESTIMATES": "PROJECT",
    "ANALYTICS": "INTERNAL",
}


@dataclass(frozen=True)
class WorkspaceContext:
    workspaceId: str
    type: str
    title: str
    roleCode: str
    ownerUserId: str | None = None
    organizationId: str | None = None
    isActive: bool = True


def normalize_workspace_type(value: str | None) -> str:
    normalized = (value or "INTERNAL").upper()
    normalized = WORKSPACE_TYPE_ALIASES.get(normalized, normalized)
    return normalized if normalized in WORKSPACE_TYPES else "INTERNAL"


def normalize_workspace_member_status(value: str | None) -> str:
    normalized = (value or "ACTIVE").upper()
    return normalized if normalized in WORKSPACE_STATUSES else "DISABLED"


def workspace_to_dict(workspace: Any) -> dict[str, Any]:
    workspace_type = normalize_workspace_type(_get_value(workspace, "type") or _get_value(workspace, "workspace_type"))
    status = _enum_value(_get_value(workspace, "status") or "ACTIVE")
    is_active_value = _get_value(workspace, "is_active")
    return {
        "id": _string_or_none(_get_value(workspace, "id")),
        "type": workspace_type,
        "title": _get_value(workspace, "title") or _get_value(workspace, "name"),
        "ownerUserId": _string_or_none(_get_value(workspace, "ownerUserId") or _get_value(workspace, "owner_user_id")),
        "organizationId": _string_or_none(_get_value(workspace, "organizationId") or _get_value(workspace, "organization_id")),
        "isActive": bool(is_active_value if is_active_value is not None else status == "ACTIVE"),
    }


def workspace_member_to_dict(member: Any) -> dict[str, Any]:
    return {
        "id": _string_or_none(_get_value(member, "id")),
        "workspaceId": _string_or_none(_get_value(member, "workspaceId") or _get_value(member, "workspace_id")),
        "userId": _string_or_none(_get_value(member, "userId") or _get_value(member, "user_id")),
        "roleCode": _get_value(member, "roleCode") or _get_value(member, "role_code") or _get_value(member, "role_key"),
        "status": normalize_workspace_member_status(_get_value(member, "status")),
    }


def get_user_workspace_contexts(user: Any | None) -> list[WorkspaceContext]:
    contexts: list[WorkspaceContext] = []
    for member in _safe_iterable(_get_value(user, "workspace_members")):
        member_data = workspace_member_to_dict(member)
        if member_data["status"] != "ACTIVE":
            continue
        workspace = _get_value(member, "workspace")
        if not workspace:
            continue
        workspace_data = workspace_to_dict(workspace)
        if not workspace_data["id"] or not workspace_data["isActive"]:
            continue
        contexts.append(
            WorkspaceContext(
                workspaceId=workspace_data["id"],
                type=workspace_data["type"],
                title=workspace_data["title"] or workspace_data["id"],
                roleCode=member_data["roleCode"],
                ownerUserId=workspace_data["ownerUserId"],
                organizationId=workspace_data["organizationId"],
                isActive=workspace_data["isActive"],
            )
        )
    return contexts


def can_access_workspace(user: Any | None, workspace_id: str) -> bool:
    return workspace_id in {context.workspaceId for context in get_user_workspace_contexts(user)}


def role_code_for_workspace(user: Any | None, workspace_id: str) -> str | None:
    for context in get_user_workspace_contexts(user):
        if context.workspaceId == workspace_id:
            return context.roleCode
    return None


def restrict_to_user_workspaces(statement: Any, model: Any, user: Any | None) -> Any:
    workspace_ids = [context.workspaceId for context in get_user_workspace_contexts(user)]
    column = getattr(model, "workspace_id", None)
    if column is None or not workspace_ids:
        return statement.where(False)
    return statement.where(column.in_(workspace_ids))


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _safe_iterable(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
