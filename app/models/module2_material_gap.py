from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Module2MaterialGap(Base):
    __tablename__ = "module2_material_gaps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'REVIEWING', 'RESOLVED_EXISTING', "
            "'SEARCH_REQUESTED', 'RESOLVED_NEW_MATERIAL', 'DISMISSED')",
            name="ck_module2_material_gap_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    technology_revision: Mapped[int] = mapped_column(nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technology_material_requirements.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    search_phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    expected_category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material_categories.id"))
    required_characteristics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN", index=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"))
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_tasks.id"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
