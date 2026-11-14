from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkCatalogItem(Base):
    __tablename__ = "module1_work_items"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')", name="ck_m1_work_item_status"),
        CheckConstraint("version >= 1", name="ck_m1_work_item_version"),
    )

    work_code: Mapped[str] = mapped_column(String(120), primary_key=True)
    work_group: Mapped[str] = mapped_column(String(120), nullable=False)
    work_category: Mapped[str] = mapped_column(String(255), nullable=False)
    work_name: Mapped[str] = mapped_column(String(500), nullable=False)
    default_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    allowed_units: Mapped[list] = mapped_column(JSON, nullable=False)
    is_range_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    applies_to: Mapped[str] = mapped_column(String(30), nullable=False)
    module2_usage_hint: Mapped[str | None] = mapped_column(String(255))
    module5_usage_hint: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    catalog_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkCatalogItemRevision(Base):
    __tablename__ = "module1_work_item_revisions"
    __table_args__ = (UniqueConstraint("work_code", "version", name="uq_m1_work_item_revision"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    work_code: Mapped[str] = mapped_column(ForeignKey("module1_work_items.work_code", ondelete="RESTRICT"),
                                            nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)


class ManualCalculationPriceRevision(Base):
    __tablename__ = "module1_manual_price_revisions"
    __table_args__ = (
        CheckConstraint("(material_id IS NOT NULL AND work_code IS NULL) OR "
                        "(material_id IS NULL AND work_code IS NOT NULL)", name="ck_m1_manual_price_owner"),
        CheckConstraint("amount IS NULL OR amount > 0", name="ck_m1_manual_price_positive"),
        CheckConstraint("version >= 1", name="ck_m1_manual_price_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    work_code: Mapped[str | None] = mapped_column(ForeignKey("module1_work_items.work_code", ondelete="RESTRICT"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    region: Mapped[str] = mapped_column(String(255), nullable=False)
    terms: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)


Index("uq_m1_manual_price_material_revision", ManualCalculationPriceRevision.material_id,
      ManualCalculationPriceRevision.currency, ManualCalculationPriceRevision.unit,
      ManualCalculationPriceRevision.region, ManualCalculationPriceRevision.terms,
      ManualCalculationPriceRevision.version, unique=True,
      postgresql_where=text("material_id IS NOT NULL"), sqlite_where=text("material_id IS NOT NULL"))
Index("uq_m1_manual_price_work_revision", ManualCalculationPriceRevision.work_code,
      ManualCalculationPriceRevision.currency, ManualCalculationPriceRevision.unit,
      ManualCalculationPriceRevision.region, ManualCalculationPriceRevision.terms,
      ManualCalculationPriceRevision.version, unique=True,
      postgresql_where=text("work_code IS NOT NULL"), sqlite_where=text("work_code IS NOT NULL"))
