import uuid
from datetime import date, datetime

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import DocumentStatus, DocumentType


class MaterialDocument(Base):
    __tablename__ = "material_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), index=True)
    manufacturer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("manufacturers.id"), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"), index=True)
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type", create_constraint=True),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[str | None] = mapped_column(String(1000))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status", create_constraint=True),
        default=DocumentStatus.NEEDS_REVIEW,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    material = relationship("Material", back_populates="documents")
    manufacturer = relationship("Manufacturer", back_populates="documents")
    source = relationship("Source", back_populates="documents")
