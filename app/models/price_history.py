import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        Index("ix_ph_material_source_collected", "material_id", "source_id", "collected_at"),
        Index("ix_ph_material_region_collected", "material_id", "region", "collected_at"),
        Index("ix_ph_material_supplier_collected", "material_id", "supplier_id", "collected_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    catalog_product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("catalog_products.id"), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"), index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    supplier_upload_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_uploads.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    unit: Mapped[str | None] = mapped_column(String(50))
    region: Mapped[str | None] = mapped_column(String(255))
    availability: Mapped[str | None] = mapped_column(String(100))
    collected_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    price_date: Mapped[date | None] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))
    # INSERT ONLY - no update, no delete
