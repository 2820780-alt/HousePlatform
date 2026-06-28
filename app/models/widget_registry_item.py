import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WidgetRegistryItem(Base):
    __tablename__ = "widget_registry_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    widget_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_module_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    canonical_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    feature_code: Mapped[str | None] = mapped_column(String(120), index=True)
    legacy_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    widget_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    data_source: Mapped[str | None] = mapped_column(String(160), index=True)
    required_access_level: Mapped[str | None] = mapped_column(String(40), index=True)
    required_scope: Mapped[str | None] = mapped_column(String(40), index=True)
    required_action_code: Mapped[str | None] = mapped_column(String(120), index=True)
    allowed_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_cabinet_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    default_size: Mapped[str] = mapped_column(String(30), default="medium", nullable=False)
    allowed_sizes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
