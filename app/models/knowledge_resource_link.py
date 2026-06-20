import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeResourceLink(Base):
    __tablename__ = "knowledge_resource_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_resources.id"), nullable=False, index=True)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), index=True)
    construction_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("construction_groups.id"), index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"), index=True)
    subcategory_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"), index=True)
    material_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_types.id"), index=True)
    manufacturer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("manufacturers.id"), index=True)
    link_type: Mapped[str] = mapped_column(String(50), default="APPLIES_TO", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    resource = relationship("KnowledgeResource", back_populates="links")
    material = relationship("Material")
    construction_group = relationship("ConstructionGroup")
    category = relationship("MaterialCategory", foreign_keys=[category_id])
    subcategory = relationship("MaterialCategory", foreign_keys=[subcategory_id])
    material_type = relationship("MaterialType")
    manufacturer = relationship("Manufacturer")

