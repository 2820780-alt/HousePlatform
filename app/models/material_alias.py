import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MaterialAlias(Base):
    __tablename__ = "material_aliases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.5"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())

    material = relationship("Material", back_populates="aliases")
