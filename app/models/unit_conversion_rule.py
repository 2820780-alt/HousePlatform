import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UnitConversionRule(Base):
    __tablename__ = "unit_conversion_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"), index=True)
    subcategory_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"), index=True)
    from_unit: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    to_unit: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    formula_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    formula: Mapped[dict | None] = mapped_column(JSON)
    required_specifications: Mapped[list | None] = mapped_column(JSON)
    coefficient: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    source: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(String(30), default="NEEDS_REVIEW", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    material = relationship("Material")
    category = relationship("MaterialCategory", foreign_keys=[category_id])
    subcategory = relationship("MaterialCategory", foreign_keys=[subcategory_id])
