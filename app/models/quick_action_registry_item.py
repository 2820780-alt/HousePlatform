import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QuickActionRegistryItem(Base):
    __tablename__ = "quick_action_registry_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quick_action_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_module_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    canonical_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    feature_code: Mapped[str | None] = mapped_column(String(120), index=True)
    widget_code: Mapped[str | None] = mapped_column(String(160), index=True)
    required_action_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    required_access_level: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    required_scope: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    allowed_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_cabinet_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    route: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
