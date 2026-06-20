import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MaterialAnalog(Base):
    __tablename__ = "material_analogs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    analog_material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(30), default="ANALOG", nullable=False, index=True)
    match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="NEEDS_REVIEW", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    material = relationship("Material", foreign_keys=[material_id], back_populates="analog_links")
    analog_material = relationship("Material", foreign_keys=[analog_material_id])

