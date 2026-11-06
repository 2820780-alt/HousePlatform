from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TechnologyCategory(Base):
    __tablename__ = "module2_technology_categories"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')", name="ck_module2_category_status"),
        CheckConstraint(
            "content_status IN ('EMPTY', 'IN_PROGRESS', 'CONTENT_COMPLETE')",
            name="ck_module2_category_content_status",
        ),
        CheckConstraint("sort_order >= 0", name="ck_module2_category_sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_technology_categories.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    scope_code: Mapped[str] = mapped_column(
        String(80), nullable=False, default="RESIDENTIAL", server_default=text("'RESIDENTIAL'")
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DRAFT", server_default=text("'DRAFT'"), index=True
    )
    content_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="EMPTY", server_default=text("'EMPTY'")
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
        server_default=text("now()"),
    )

    parent = relationship("TechnologyCategory", remote_side=[id])
