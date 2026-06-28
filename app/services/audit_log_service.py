from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogType(StrEnum):
    ROLE_CHANGED = "role_changed"
    PERMISSION_CHANGED = "permission_changed"
    SCOPE_CHANGED = "scope_changed"
    PLATFORM_MODULE_REGISTRY_CHANGED = "platform_module_registry_changed"
    MODULE_STATUS_CHANGED = "module_status_changed"
    MODULE_ARCHIVED = "module_archived"
    MODULE_MERGED = "module_merged"
    LEGACY_ALIAS_REDIRECT_CHANGED = "legacy_alias_redirect_changed"
    WIDGET_REGISTRY_CHANGED = "widget_registry_changed"
    WIDGET_PERMISSION_CHANGED = "widget_permission_changed"
    USER_DASHBOARD_LAYOUT_CHANGED = "user_dashboard_layout_changed"
    VIEW_AS_ROLE_ENTERED = "view_as_role_entered"
    ACCESS_DENIED = "access_denied"
    LEGACY_MODULE_CODE_NORMALIZED = "legacy_module_code_normalized"
    PRICE_HISTORY_MIGRATED_TO_ANALYTICS = "price_history_migrated_to_analytics"
    INACCESSIBLE_WIDGET_ADD_ATTEMPT = "inaccessible_widget_add_attempt"
    INACTIVE_MODULE_OPEN_ATTEMPT = "inactive_module_open_attempt"


SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "passwordHash",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "secret",
    "api_key",
    "apiKey",
}

MOCK_AUDIT_EVENTS: list[dict[str, Any]] = []


@dataclass(frozen=True)
class AuditEventPayload:
    eventType: str
    actorUserId: str | None = None
    targetUserId: str | None = None
    workspaceId: str | None = None
    moduleCode: str | None = None
    canonicalModuleCode: str | None = None
    featureCode: str | None = None
    widgetCode: str | None = None
    roleCode: str | None = None
    oldValue: Any | None = None
    newValue: Any | None = None
    reason: str | None = None
    comment: str | None = None
    result: str = "SUCCESS"
    entityType: str | None = None
    entityId: str | None = None
    metadata: dict[str, Any] | None = None
    createdAt: str | None = None

    def to_details(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["createdAt"] = payload["createdAt"] or datetime.utcnow().isoformat()
        return sanitize_audit_details(payload)


async def write_audit_event(
    db: AsyncSession | None,
    event_type: str | AuditLogType,
    *,
    actor_user_id: Any | None = None,
    target_user_id: Any | None = None,
    workspace_id: Any | None = None,
    module_code: str | None = None,
    canonical_module_code: str | None = None,
    feature_code: str | None = None,
    widget_code: str | None = None,
    role_code: str | None = None,
    old_value: Any | None = None,
    new_value: Any | None = None,
    reason: str | None = None,
    comment: str | None = None,
    result: str = "SUCCESS",
    entity_type: str | None = None,
    entity_id: Any | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog | dict[str, Any]:
    payload = AuditEventPayload(
        eventType=str(event_type),
        actorUserId=_string_or_none(actor_user_id),
        targetUserId=_string_or_none(target_user_id),
        workspaceId=_string_or_none(workspace_id),
        moduleCode=module_code,
        canonicalModuleCode=canonical_module_code,
        featureCode=feature_code,
        widgetCode=widget_code,
        roleCode=role_code,
        oldValue=old_value,
        newValue=new_value,
        reason=reason,
        comment=comment,
        result=result,
        entityType=entity_type,
        entityId=_string_or_none(entity_id),
        metadata=metadata or {},
    )
    details = payload.to_details()
    if db is None:
        return write_audit_event_mock(details)

    audit_log = AuditLog(
        user_id=_uuid_or_none(actor_user_id),
        workspace_id=_uuid_or_none(workspace_id),
        action_type=str(event_type),
        entity_type=entity_type,
        entity_id=_uuid_or_none(entity_id),
        result=result,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db.add(audit_log)
    await db.flush()
    return audit_log


def write_audit_event_mock(details: dict[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_audit_details(details)
    MOCK_AUDIT_EVENTS.append(sanitized)
    return sanitized


def writeAuditEvent(*args: Any, **kwargs: Any):
    return write_audit_event(*args, **kwargs)


def record_access_denied_attempt(
    *,
    user: Any | None,
    module_code: str,
    action_code: str,
    scope: str,
    reason: str,
) -> dict[str, Any]:
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=AuditLogType.ACCESS_DENIED,
            actorUserId=_get_value(user, "id") or _get_value(user, "userId"),
            moduleCode=module_code,
            canonicalModuleCode=module_code,
            reason=reason,
            result="DENIED",
            metadata={"actionCode": action_code, "scope": scope},
        ).to_details()
    )


def record_legacy_module_normalization(
    *,
    legacy_module_code: str,
    canonical_module_code: str,
    feature_code: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    event_type = (
        AuditLogType.PRICE_HISTORY_MIGRATED_TO_ANALYTICS
        if legacy_module_code == "MODULE_14_PRICE_HISTORY"
        and canonical_module_code == "MODULE_11_ANALYTICS"
        else AuditLogType.LEGACY_MODULE_CODE_NORMALIZED
    )
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=event_type,
            moduleCode=legacy_module_code,
            canonicalModuleCode=canonical_module_code,
            featureCode=feature_code,
            oldValue={"moduleCode": legacy_module_code},
            newValue={"moduleCode": canonical_module_code, "featureCode": feature_code},
            reason=reason or "legacy/canonical normalization",
        ).to_details()
    )


def record_inactive_module_open_attempt(
    *,
    module_code: str,
    canonical_module_code: str | None = None,
    status: str | None = None,
    user: Any | None = None,
) -> dict[str, Any]:
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=AuditLogType.INACTIVE_MODULE_OPEN_ATTEMPT,
            actorUserId=_get_value(user, "id") or _get_value(user, "userId"),
            moduleCode=module_code,
            canonicalModuleCode=canonical_module_code,
            result="DENIED",
            reason="Attempted to open disabled/archived/merged module as active.",
            metadata={"status": status},
        ).to_details()
    )


def record_inaccessible_widget_add_attempt(
    *,
    widget_code: str,
    module_code: str | None = None,
    canonical_module_code: str | None = None,
    feature_code: str | None = None,
    user: Any | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=AuditLogType.INACCESSIBLE_WIDGET_ADD_ATTEMPT,
            actorUserId=_get_value(user, "id") or _get_value(user, "userId"),
            moduleCode=module_code,
            canonicalModuleCode=canonical_module_code,
            featureCode=feature_code,
            widgetCode=widget_code,
            result="DENIED",
            reason=reason or "Widget is not allowed by Module 03 / Module 08 / WidgetRegistry.",
        ).to_details()
    )


def record_permission_change(
    *,
    actor: Any | None,
    target_user_id: Any | None = None,
    workspace_id: Any | None = None,
    module_code: str | None = None,
    canonical_module_code: str | None = None,
    feature_code: str | None = None,
    role_code: str | None = None,
    old_value: Any | None = None,
    new_value: Any | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    old_scope = _scope_from_value(old_value)
    new_scope = _scope_from_value(new_value)
    event_type = AuditLogType.SCOPE_CHANGED if old_scope != new_scope else AuditLogType.PERMISSION_CHANGED
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=event_type,
            actorUserId=_get_value(actor, "id") or _get_value(actor, "userId"),
            targetUserId=_string_or_none(target_user_id),
            workspaceId=_string_or_none(workspace_id),
            moduleCode=module_code,
            canonicalModuleCode=canonical_module_code,
            featureCode=feature_code,
            roleCode=role_code,
            oldValue=old_value,
            newValue=new_value,
            reason=reason or "Permission/scope changed.",
        ).to_details()
    )


def record_widget_registry_change(
    *,
    widget_code: str,
    module_code: str | None = None,
    canonical_module_code: str | None = None,
    feature_code: str | None = None,
    actor: Any | None = None,
    old_value: Any | None = None,
    new_value: Any | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=AuditLogType.WIDGET_REGISTRY_CHANGED,
            actorUserId=_get_value(actor, "id") or _get_value(actor, "userId"),
            moduleCode=module_code,
            canonicalModuleCode=canonical_module_code,
            featureCode=feature_code,
            widgetCode=widget_code,
            oldValue=old_value,
            newValue=new_value,
            reason=reason or "WidgetRegistry changed.",
        ).to_details()
    )


def record_widget_permission_change(
    *,
    widget_code: str,
    role_code: str | None = None,
    module_code: str | None = None,
    canonical_module_code: str | None = None,
    feature_code: str | None = None,
    actor: Any | None = None,
    old_value: Any | None = None,
    new_value: Any | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=AuditLogType.WIDGET_PERMISSION_CHANGED,
            actorUserId=_get_value(actor, "id") or _get_value(actor, "userId"),
            moduleCode=module_code,
            canonicalModuleCode=canonical_module_code,
            featureCode=feature_code,
            widgetCode=widget_code,
            roleCode=role_code,
            oldValue=old_value,
            newValue=new_value,
            reason=reason or "Widget permission changed.",
        ).to_details()
    )


def record_view_as_role_entered(
    *,
    actor: Any,
    role_code: str,
    workspace_id: Any | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=AuditLogType.VIEW_AS_ROLE_ENTERED,
            actorUserId=_get_value(actor, "id") or _get_value(actor, "userId"),
            workspaceId=_string_or_none(workspace_id),
            roleCode=role_code,
            reason=reason or "Dashboard preview role entered.",
        ).to_details()
    )


def record_module_merge_or_alias_change(
    *,
    module_code: str,
    canonical_module_code: str,
    merged_into_module_code: str | None = None,
    redirect_route: str | None = None,
    legacy_codes: list[str] | None = None,
    actor: Any | None = None,
    old_value: Any | None = None,
    new_value: Any | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    event_type = AuditLogType.MODULE_MERGED if merged_into_module_code else AuditLogType.LEGACY_ALIAS_REDIRECT_CHANGED
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=event_type,
            actorUserId=_get_value(actor, "id") or _get_value(actor, "userId"),
            moduleCode=module_code,
            canonicalModuleCode=canonical_module_code,
            oldValue=old_value,
            newValue=new_value
            or {
                "canonicalModuleCode": canonical_module_code,
                "mergedIntoModuleCode": merged_into_module_code,
                "redirectRoute": redirect_route,
                "legacyCodes": legacy_codes or [],
            },
            reason=reason or "Module merge/legacy alias changed.",
        ).to_details()
    )


def record_dashboard_layout_change(
    *,
    user: Any | None,
    workspace_id: Any | None = None,
    old_layout: Any | None = None,
    new_layout: Any | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return write_audit_event_mock(
        AuditEventPayload(
            eventType=AuditLogType.USER_DASHBOARD_LAYOUT_CHANGED,
            actorUserId=_get_value(user, "id") or _get_value(user, "userId"),
            workspaceId=_string_or_none(workspace_id),
            oldValue=old_layout,
            newValue=new_layout,
            reason=reason,
        ).to_details()
    )


def sanitize_audit_details(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_audit_details(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_audit_details(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_audit_details(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def clear_mock_audit_events() -> None:
    MOCK_AUDIT_EVENTS.clear()


def _scope_from_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("accessScope") or value.get("scope")
    return None


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    return any(sensitive.lower() in lower for sensitive in SENSITIVE_KEYS)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _uuid_or_none(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)
