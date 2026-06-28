import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserDashboardLayout(Base):
    __tablename__ = "user_dashboard_layouts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    active_region_code: Mapped[str | None] = mapped_column(String(80), index=True)
    active_cabinet_id: Mapped[str | None] = mapped_column(String(120), index=True)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    favorite_modules: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    widgets: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    layout_settings: Mapped[dict | None] = mapped_column(JSON)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
