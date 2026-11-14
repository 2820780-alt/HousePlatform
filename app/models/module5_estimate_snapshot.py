"""Immutable preliminary calculation snapshot."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EstimatePreviewSnapshot(Base):
    __tablename__ = "module5_estimate_preview_snapshots"
    __table_args__ = (CheckConstraint("mode = 'PREVIEW'", name="module5_estimate_preview_snapshots_mode_check"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    geometry_revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("module7_strip_geometry_revisions.id", ondelete="RESTRICT"), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="PREVIEW")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
