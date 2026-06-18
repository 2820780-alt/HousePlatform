from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_event import AuditEvent


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
        details=details,
        ip_address=ip_address,
    )
    db.add(event)
    await db.flush()
    return event
