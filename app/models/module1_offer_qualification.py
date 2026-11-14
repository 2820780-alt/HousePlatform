"""Auditable confirmation of offer identity and comparable conditions."""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CalculationOfferQualification(Base):
    __tablename__ = "module1_calculation_offer_qualifications"
    __table_args__ = (
        CheckConstraint("(supplier_price_id IS NOT NULL AND work_offer_id IS NULL) OR "
                        "(supplier_price_id IS NULL AND work_offer_id IS NOT NULL)", name="ck_m1_qualification_offer_owner"),
        CheckConstraint("status IN ('CONFIRMED', 'WITHDRAWN')", name="ck_m1_qualification_status"),
        CheckConstraint("version > 0", name="ck_m1_qualification_version"),
        CheckConstraint("base_units_per_sale_unit IS NULL OR base_units_per_sale_unit > 0", name="ck_m1_qualification_conversion"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    supplier_price_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_prices.id", ondelete="RESTRICT"))
    work_offer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("provider_work_cost_offers.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    terms: Mapped[str] = mapped_column(String(500), nullable=False)
    offer_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    base_units_per_sale_unit: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    conversion_source: Mapped[str | None] = mapped_column(Text)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index("uq_m1_qualification_material_version", CalculationOfferQualification.supplier_price_id,
      CalculationOfferQualification.version, unique=True,
      postgresql_where=text("supplier_price_id IS NOT NULL"), sqlite_where=text("supplier_price_id IS NOT NULL"))
Index("uq_m1_qualification_work_version", CalculationOfferQualification.work_offer_id,
      CalculationOfferQualification.version, unique=True,
      postgresql_where=text("work_offer_id IS NOT NULL"), sqlite_where=text("work_offer_id IS NOT NULL"))
