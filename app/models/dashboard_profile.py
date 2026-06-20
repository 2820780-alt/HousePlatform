import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DashboardProfile(Base):
    __tablename__ = "dashboard_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    layout: Mapped[dict | None] = mapped_column(JSON)
    theme_key: Mapped[str] = mapped_column(String(80), default="atom-dark", nullable=False)
    density: Mapped[str] = mapped_column(String(30), default="normal", nullable=False)
    favorite_modules: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    user = relationship("User", back_populates="dashboard_profiles")
    workspace = relationship("Workspace", back_populates="dashboard_profiles")
    placements = relationship("DashboardWidgetPlacement", back_populates="dashboard_profile")

