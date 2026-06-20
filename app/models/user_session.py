import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    session_token_hash: Mapped[str | None] = mapped_column(String(255), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow(), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(index=True)
    ended_at: Mapped[datetime | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    user = relationship("User", back_populates="sessions")
