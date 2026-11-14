"""Versioned minimal geometry for a strip foundation."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DigitalHouseObject(Base):
    __tablename__ = "module7_digital_house_objects"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StripGeometryRevision(Base):
    __tablename__ = "module7_strip_geometry_revisions"
    __table_args__ = (
        UniqueConstraint("object_id", "version", name="uq_m7_strip_geometry_version"),
        CheckConstraint("version > 0 AND length_m > 0 AND width_m > 0 AND height_m > 0", name="ck_m7_strip_geometry_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("module7_digital_house_objects.id", ondelete="RESTRICT"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    technology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("module2_technologies.id", ondelete="RESTRICT"), nullable=False)
    length_m: Mapped[Decimal] = mapped_column(Numeric(16, 6), nullable=False)
    width_m: Mapped[Decimal] = mapped_column(Numeric(16, 6), nullable=False)
    height_m: Mapped[Decimal] = mapped_column(Numeric(16, 6), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
