import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TaskLogLevel


class SourceTaskLog(Base):
    __tablename__ = "source_task_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    level: Mapped[TaskLogLevel] = mapped_column(
        SAEnum(TaskLogLevel, name="task_log_level", create_constraint=True),
        default=TaskLogLevel.INFO,
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())

    task = relationship("SourceTask", back_populates="logs")
