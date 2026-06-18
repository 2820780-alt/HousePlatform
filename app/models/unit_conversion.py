import uuid
from decimal import Decimal
from sqlalchemy import String, Text, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UnitConversion(Base):
    __tablename__ = "unit_conversions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    from_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id"), nullable=False, index=True)
    to_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id"), nullable=False, index=True)
    factor: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    condition: Mapped[str | None] = mapped_column(Text)
    material_category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"), index=True)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"))

    from_unit = relationship("Unit", foreign_keys=[from_unit_id])
    to_unit = relationship("Unit", foreign_keys=[to_unit_id])
