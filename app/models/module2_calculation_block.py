from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CalculationBlockTemplate(Base):
    __tablename__ = "module2_calculation_block_templates"
    __table_args__ = (
        UniqueConstraint("template_key", "version", name="uq_m2_block_template_key_version"),
        CheckConstraint("version >= 1", name="ck_m2_block_template_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    template_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    work_code: Mapped[str | None] = mapped_column(String(120))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)


class TechnologyCalculationBlock(Base):
    __tablename__ = "module2_calculation_blocks"
    __table_args__ = (
        UniqueConstraint("technology_id", "position", name="uq_m2_calculation_block_position"),
        CheckConstraint("position >= 1", name="ck_m2_calculation_block_position"),
        CheckConstraint("version >= 1", name="ck_m2_calculation_block_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_calculation_block_templates.id", ondelete="RESTRICT"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    work_code: Mapped[str | None] = mapped_column(String(120))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
