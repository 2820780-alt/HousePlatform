import uuid
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.enums import AccessStatus


class SupplierAccount(Base):
    __tablename__ = "supplier_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "supplier_id", name="uq_user_supplier"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_in_company: Mapped[str | None] = mapped_column(String(100))
    access_status: Mapped[AccessStatus] = mapped_column(
        SAEnum(AccessStatus, name="access_status", create_constraint=True),
        nullable=False,
        default=AccessStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_login_at: Mapped[datetime | None] = mapped_column()

    # Relationships
    user = relationship("User", back_populates="supplier_accounts")
    supplier = relationship("Supplier", back_populates="accounts")

    def __repr__(self):
        return f"<SupplierAccount user={self.user_id} supplier={self.supplier_id}>"
