from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class AuditEventRead(BaseModel):
    id: UUID
    event_type: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    user_id: UUID | None = None
    details: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
