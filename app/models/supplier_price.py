import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SupplierPrice(Base):
    __tablename__ = "supplier_prices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    catalog_product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("catalog_products.id"), index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    unit: Mapped[str | None] = mapped_column(String(50))
    region: Mapped[str | None] = mapped_column(String(255), index=True)
    availability: Mapped[str | None] = mapped_column(String(100))
    min_order_quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    delivery_terms: Mapped[str | None] = mapped_column(String(500))
    valid_until: Mapped[date | None] = mapped_column(Date, index=True)
    source_upload_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_uploads.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    material = relationship("Material", back_populates="supplier_prices")
    supplier = relationship("Supplier", back_populates="supplier_prices")
    catalog_product = relationship("CatalogProduct", back_populates="supplier_prices")
    source_upload = relationship("SupplierUpload", back_populates="supplier_prices")
