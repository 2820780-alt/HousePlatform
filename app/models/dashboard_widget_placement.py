import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DashboardWidgetPlacement(Base):
    __tablename__ = "dashboard_widget_placements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dashboard_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dashboard_profiles.id"), nullable=False, index=True)
    widget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dashboard_widgets.id"), nullable=False, index=True)
    zone: Mapped[str] = mapped_column(String(80), default="main", nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    size: Mapped[str] = mapped_column(String(30), default="M", nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    dashboard_profile = relationship("DashboardProfile", back_populates="placements")
    widget = relationship("DashboardWidget", back_populates="placements")

