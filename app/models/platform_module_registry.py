import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlatformModuleRegistry(Base):
    __tablename__ = "platform_module_registry"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    module_code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    canonical_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_title: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(String(50))
    legacy_number: Mapped[int | None] = mapped_column(Integer, index=True)
    display_number: Mapped[int | None] = mapped_column(Integer, index=True)
    visual_number: Mapped[int | None] = mapped_column(Integer, index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    route: Mapped[str | None] = mapped_column(String(255))
    redirect_route: Mapped[str | None] = mapped_column(String(255))
    icon: Mapped[str | None] = mapped_column(String(80))
    color: Mapped[str | None] = mapped_column(String(50))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_visible_in_sidebar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_visible_on_dashboard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_visible_on_atom_map: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_available_for_widgets: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    owner_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    merged_into_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    legacy_codes: Mapped[list[str] | None] = mapped_column(JSONB)
    feature_codes: Mapped[list[str] | None] = mapped_column(JSONB)
    default_permissions: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)
    available_actions: Mapped[list[str] | None] = mapped_column(JSONB)
    dashboard_widgets: Mapped[list[str] | None] = mapped_column(JSONB)
    owner_scope_rules: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
