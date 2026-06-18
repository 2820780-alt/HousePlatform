import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import UploadFileType, UploadStatus


class SupplierUpload(Base):
    __tablename__ = "supplier_uploads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[UploadFileType] = mapped_column(
        SAEnum(UploadFileType, name="upload_file_type", create_constraint=True),
        nullable=False,
        index=True,
    )
    file_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[UploadStatus] = mapped_column(
        SAEnum(UploadStatus, name="upload_status", create_constraint=True),
        default=UploadStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_processed: Mapped[int] = mapped_column(Integer, default=0)
    rows_matched: Mapped[int] = mapped_column(Integer, default=0)
    rows_needs_review: Mapped[int] = mapped_column(Integer, default=0)
    rows_errors: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    rows = relationship("SupplierUploadRow", back_populates="upload")
    supplier = relationship("Supplier", back_populates="supplier_uploads")
    supplier_prices = relationship("SupplierPrice", back_populates="source_upload")
