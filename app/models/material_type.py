import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MaterialType(Base):
    __tablename__ = "material_types"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    construction_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("construction_groups.id"), index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material_categories.id"), nullable=False, index=True)
    subcategory_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    key_characteristics: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    construction_group = relationship("ConstructionGroup", back_populates="material_types")
    category = relationship("MaterialCategory", foreign_keys=[category_id])
    subcategory = relationship("MaterialCategory", foreign_keys=[subcategory_id])
    materials = relationship("Material", back_populates="material_type")

