from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_event import AuditEvent
from app.services.audit_log_service import sanitize_audit_details


async def log_event(
    db: AsyncSession,
    event_type: str,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    user_id: UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        details=sanitize_audit_details(details or {}),
        ip_address=ip_address,
    )
    db.add(event)
    await db.flush()
    return event
