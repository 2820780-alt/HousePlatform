import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum as SAEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RegionStatus


class PlatformRegion(Base):
    __tablename__ = "platform_regions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(10), default="RU", nullable=False, index=True)
    status: Mapped[RegionStatus] = mapped_column(
        SAEnum(RegionStatus, name="region_status", create_constraint=True),
        default=RegionStatus.DRAFT,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_pilot_region: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_open_for_users: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_open_for_suppliers: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_open_for_marketplace: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_open_for_analytics: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    cities = relationship("PlatformCity", back_populates="region")
    delivery_zones = relationship("DeliveryZone", back_populates="region")
    active_entries = relationship("ActiveRegion", back_populates="region")
    pilot_entries = relationship("PilotRegion", back_populates="region")
