import uuid
from datetime import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    workspace_type: Mapped[str] = mapped_column(String(50), default="ADMIN", nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    members = relationship("WorkspaceMember", back_populates="workspace")
    workspace_roles = relationship("WorkspaceRole", back_populates="workspace")
    dashboard_profiles = relationship("DashboardProfile", back_populates="workspace")
