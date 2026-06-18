import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Enum as SAEnum, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import UploadRowStatus


class SupplierUploadRow(Base):
    __tablename__ = "supplier_upload_rows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_uploads.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number: Mapped[int | None] = mapped_column(index=True)
    raw_name: Mapped[str | None] = mapped_column(Text)
    normalized_name: Mapped[str | None] = mapped_column(Text)
    raw_category: Mapped[str | None] = mapped_column(String(500))
    raw_brand: Mapped[str | None] = mapped_column(String(255))
    raw_manufacturer: Mapped[str | None] = mapped_column(String(255))
    raw_unit: Mapped[str | None] = mapped_column(String(50))
    raw_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    raw_quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    raw_article: Mapped[str | None] = mapped_column(String(255), index=True)
    parsed_data: Mapped[dict | None] = mapped_column(JSON)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), index=True)
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[UploadRowStatus] = mapped_column(
        SAEnum(UploadRowStatus, name="upload_row_status", create_constraint=True),
        default=UploadRowStatus.EXTRACTED,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    upload = relationship("SupplierUpload", back_populates="rows")
    material = relationship("Material")
