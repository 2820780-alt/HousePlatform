import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import SourceStatus, SourceType


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="source_type", create_constraint=True),
        nullable=False,
        index=True,
    )
    url: Mapped[str | None] = mapped_column(String(1000))
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    status: Mapped[SourceStatus] = mapped_column(
        SAEnum(SourceStatus, name="source_status", create_constraint=True),
        default=SourceStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    last_full_scan_at: Mapped[datetime | None] = mapped_column()
    last_price_update_at: Mapped[datetime | None] = mapped_column()
    last_document_update_at: Mapped[datetime | None] = mapped_column()
    last_knowledge_scan_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    catalog_products = relationship("CatalogProduct", back_populates="source")
    tasks = relationship("SourceTask", back_populates="source")
    documents = relationship("MaterialDocument", back_populates="source")
