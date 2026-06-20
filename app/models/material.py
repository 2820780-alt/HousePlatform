import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import MaterialStatus


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"), index=True)
    subcategory_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"))
    material_type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_types.id"), index=True)
    manufacturer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("manufacturers.id"), index=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id"), index=True)
    base_unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id"))
    article: Mapped[str | None] = mapped_column(String(255), index=True)
    brand: Mapped[str | None] = mapped_column(String(255), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[MaterialStatus] = mapped_column(
        SAEnum(MaterialStatus, name="material_status", create_constraint=True),
        default=MaterialStatus.DRAFT,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    category = relationship("MaterialCategory", back_populates="materials", foreign_keys=[category_id])
    subcategory = relationship("MaterialCategory", foreign_keys=[subcategory_id])
    material_type = relationship("MaterialType", back_populates="materials")
    manufacturer_ref = relationship("Manufacturer", back_populates="materials")
    brand_ref = relationship("Brand", back_populates="materials")
    base_unit = relationship("Unit")
    aliases = relationship("MaterialAlias", back_populates="material")
    attributes = relationship("MaterialAttribute", back_populates="material")
    specifications = relationship("MaterialSpecification", back_populates="material")
    documents = relationship("MaterialDocument", back_populates="material")
    catalog_products = relationship("CatalogProduct", back_populates="material")
    supplier_prices = relationship("SupplierPrice", back_populates="material")
    analog_links = relationship("MaterialAnalog", back_populates="material", foreign_keys="MaterialAnalog.material_id")
    quality_issues = relationship("MaterialQualityIssue", back_populates="material")
