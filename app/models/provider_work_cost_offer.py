import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProviderWorkCostOffer(Base):
    __tablename__ = "provider_work_cost_offers"
    __table_args__ = (
        CheckConstraint("pricing_mode in ('fixed', 'range')", name="ck_provider_work_cost_pricing_mode"),
        CheckConstraint("status in ('draft', 'active', 'inactive')", name="ck_provider_work_cost_status"),
        CheckConstraint("fixed_amount is null or fixed_amount > 0", name="ck_provider_work_cost_fixed_positive"),
        CheckConstraint("minimum_amount is null or minimum_amount > 0", name="ck_provider_work_cost_min_positive"),
        CheckConstraint("maximum_amount is null or maximum_amount > 0", name="ck_provider_work_cost_max_positive"),
        CheckConstraint(
            "valid_until is null or valid_from is null or valid_until >= valid_from",
            name="ck_provider_work_cost_validity",
        ),
        CheckConstraint(
            "(pricing_mode = 'fixed' and fixed_amount is not null and minimum_amount is null and maximum_amount is null) "
            "or (pricing_mode = 'range' and fixed_amount is null and minimum_amount is not null "
            "and maximum_amount is not null and minimum_amount <= maximum_amount)",
            name="ck_provider_work_cost_amount_contract",
        ),
        Index("ix_provider_work_cost_owner_work_code", "owner_user_id", "work_code"),
        Index("ix_provider_work_cost_region_status", "region", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    work_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pricing_mode: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    fixed_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    minimum_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    maximum_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="RUB", index=True)
    pricing_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    comment: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    owner = relationship("User", foreign_keys=[owner_user_id])
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
