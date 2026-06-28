import uuid
from datetime import datetime

from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoleDashboardAccessProfile(Base):
    __tablename__ = "role_dashboard_access_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    role_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    source_module_code: Mapped[str] = mapped_column(String(120), default="MODULE_03_USERS_ROLES", nullable=False)
    allowed_module_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_feature_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    default_widget_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    default_quick_action_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    hidden_widget_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    default_layout_code: Mapped[str | None] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict | None] = mapped_column(JSON)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
