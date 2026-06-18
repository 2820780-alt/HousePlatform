import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SpecificationTemplate(Base):
    __tablename__ = "specification_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material_categories.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    field_type: Mapped[str] = mapped_column(String(50), default="string")
    unit: Mapped[str | None] = mapped_column(String(50))
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    weight_for_matching: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    category = relationship("MaterialCategory", back_populates="specification_templates")
    specifications = relationship("MaterialSpecification", back_populates="template")
