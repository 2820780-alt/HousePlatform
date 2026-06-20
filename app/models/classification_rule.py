import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ClassificationRule(Base):
    __tablename__ = "classification_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_code: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    construction_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("construction_groups.id"), index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"), index=True)
    subcategory_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"), index=True)
    material_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_types.id"), index=True)
    priority: Mapped[int] = mapped_column(default=100, nullable=False, index=True)
    match_keywords: Mapped[list | None] = mapped_column(JSON)
    required_keywords: Mapped[list | None] = mapped_column(JSON)
    excluded_keywords: Mapped[list | None] = mapped_column(JSON)
    source_category_patterns: Mapped[list | None] = mapped_column(JSON)
    brand_patterns: Mapped[list | None] = mapped_column(JSON)
    manufacturer_patterns: Mapped[list | None] = mapped_column(JSON)
    characteristic_conditions: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_from_material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    construction_group = relationship("ConstructionGroup")
    category = relationship("MaterialCategory", foreign_keys=[category_id])
    subcategory = relationship("MaterialCategory", foreign_keys=[subcategory_id])
    material_type = relationship("MaterialType")
    created_from_material = relationship("Material")

