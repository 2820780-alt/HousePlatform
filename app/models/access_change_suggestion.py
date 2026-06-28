import uuid
from datetime import datetime

from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AccessChangeSuggestion(Base):
    __tablename__ = "access_change_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    suggestion_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    change_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_module_code: Mapped[str] = mapped_column(String(120), default="MODULE_12_AI_ASSISTANT", nullable=False, index=True)
    target_user_id: Mapped[str | None] = mapped_column(String(160), index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(160), index=True)
    module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    canonical_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    feature_code: Mapped[str | None] = mapped_column(String(120), index=True)
    widget_code: Mapped[str | None] = mapped_column(String(160), index=True)
    role_code: Mapped[str | None] = mapped_column(String(80), index=True)
    old_value: Mapped[dict | None] = mapped_column(JSON)
    new_value: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(80), default="AI_ASSISTANT", nullable=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(40), default="PENDING_ADMIN_APPROVAL", nullable=False, index=True)
    requires_admin_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(160), index=True)
    approved_at: Mapped[datetime | None] = mapped_column()
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
