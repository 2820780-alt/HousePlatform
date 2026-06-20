import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    result: Mapped[str] = mapped_column(String(30), default="SUCCESS", nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(50))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow(), index=True)

    user = relationship("User", back_populates="audit_logs")
    workspace = relationship("Workspace")
