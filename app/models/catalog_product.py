import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import CatalogProductStatus


class CatalogProduct(Base):
    __tablename__ = "catalog_products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    external_url: Mapped[str | None] = mapped_column(String(1000))
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(Text)
    raw_category: Mapped[str | None] = mapped_column(String(500))
    raw_brand: Mapped[str | None] = mapped_column(String(255))
    raw_manufacturer: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    unit: Mapped[str | None] = mapped_column(String(50))
    availability: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(255), index=True)
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[CatalogProductStatus] = mapped_column(
        SAEnum(CatalogProductStatus, name="catalog_product_status", create_constraint=True),
        default=CatalogProductStatus.NEEDS_REVIEW,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    source = relationship("Source", back_populates="catalog_products")
    material = relationship("Material", back_populates="catalog_products")
    match_candidates = relationship("MaterialMatchCandidate", back_populates="catalog_product")
    supplier_prices = relationship("SupplierPrice", back_populates="catalog_product")
