import uuid
from datetime import datetime
from sqlalchemy import String, Text, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.enums import SupplierStatus


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    inn: Mapped[str | None] = mapped_column(String(20), unique=True)
    site: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(255), index=True)
    region: Mapped[str | None] = mapped_column(String(255), index=True)
    country: Mapped[str | None] = mapped_column(String(100), default="Россия")
    address: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SupplierStatus] = mapped_column(
        SAEnum(SupplierStatus, name="supplier_status", create_constraint=True),
        nullable=False,
        default=SupplierStatus.POTENTIAL,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.utcnow()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    # Relationships
    accounts = relationship("SupplierAccount", back_populates="supplier")
    branches = relationship("SupplierBranch", back_populates="supplier")
    supplier_prices = relationship("SupplierPrice")
    supplier_uploads = relationship("SupplierUpload")

    def __repr__(self):
        return f"<Supplier {self.name} [{self.status}]>"
