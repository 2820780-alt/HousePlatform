import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum as SAEnum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AdminDecision, TaskResultType


class SourceTaskResult(Base):
    __tablename__ = "source_task_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    result_type: Mapped[TaskResultType] = mapped_column(
        SAEnum(TaskResultType, name="task_result_type", create_constraint=True),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str | None] = mapped_column(String(100), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    old_value: Mapped[dict | None] = mapped_column(JSON)
    new_value: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str | None] = mapped_column(String(50), index=True)
    admin_decision: Mapped[AdminDecision | None] = mapped_column(
        SAEnum(AdminDecision, name="task_admin_decision", create_constraint=True)
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    task = relationship("SourceTask", back_populates="results")
