import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class MaterialCategorySchema(Base):
    __tablename__ = "material_category_schemas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material_categories.id", ondelete="CASCADE"), nullable=False, unique=True)
    required_attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    optional_attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    comparison_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dedup_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    unit_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    normalization_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

    category = relationship("MaterialCategory", back_populates="schema")
