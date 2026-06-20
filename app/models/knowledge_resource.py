import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeResource(Base):
    __tablename__ = "knowledge_resources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"), index=True)
    legacy_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_documents.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    resource_url: Mapped[str | None] = mapped_column(String(1000))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    extracted_data: Mapped[dict | None] = mapped_column(JSON)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default="NEEDS_REVIEW", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    source = relationship("Source")
    legacy_document = relationship("MaterialDocument")
    links = relationship("KnowledgeResourceLink", back_populates="resource")
    candidates = relationship("KnowledgeCandidate", back_populates="knowledge_resource")

