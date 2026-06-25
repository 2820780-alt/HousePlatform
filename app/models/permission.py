import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    permission_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    module_number: Mapped[int | None] = mapped_column(index=True)
    module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    action_code: Mapped[str | None] = mapped_column(String(80), index=True)
    access_level: Mapped[str] = mapped_column(String(30), default="VIEW", nullable=False, index=True)
    access_scope: Mapped[str] = mapped_column(String(30), default="GLOBAL", nullable=False, index=True)
    conditions: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    roles = relationship("RolePermission", back_populates="permission")
