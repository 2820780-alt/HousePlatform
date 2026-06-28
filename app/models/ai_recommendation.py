import uuid
from datetime import datetime

from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recommendation_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    source_module_code: Mapped[str] = mapped_column(String(120), default="MODULE_12_AI_ASSISTANT", nullable=False, index=True)
    target_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    canonical_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    feature_code: Mapped[str | None] = mapped_column(String(120), index=True)
    widget_code: Mapped[str | None] = mapped_column(String(160), index=True)
    role_code: Mapped[str | None] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(40), default="INFO", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", nullable=False, index=True)
    requires_admin_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
