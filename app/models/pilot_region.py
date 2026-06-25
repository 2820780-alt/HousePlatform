import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RegionStatus


class PilotRegion(Base):
    __tablename__ = "pilot_regions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_regions.id"), nullable=False, index=True)
    pilot_key: Mapped[str] = mapped_column(String(120), default="MVP", nullable=False, index=True)
    status: Mapped[RegionStatus] = mapped_column(
        SAEnum(RegionStatus, name="region_status", create_constraint=True),
        default=RegionStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    region = relationship("PlatformRegion", back_populates="pilot_entries")
