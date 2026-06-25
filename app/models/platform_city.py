import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RegionStatus


class PlatformCity(Base):
    __tablename__ = "platform_cities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_regions.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[RegionStatus] = mapped_column(
        SAEnum(RegionStatus, name="region_status", create_constraint=True),
        default=RegionStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    display_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    region = relationship("PlatformRegion", back_populates="cities")
    delivery_zones = relationship("DeliveryZone", back_populates="city")
