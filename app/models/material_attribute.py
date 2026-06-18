import uuid
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MaterialAttribute(Base):
    __tablename__ = "material_attributes"
    __table_args__ = (
        UniqueConstraint("material_id", "attribute_name", name="uq_material_attribute"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    attribute_value: Mapped[str] = mapped_column(String(500), nullable=False)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    material = relationship("Material", back_populates="attributes")
    unit = relationship("Unit")
