import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkspaceRole(Base):
    __tablename__ = "workspace_roles"
    __table_args__ = (
        UniqueConstraint("workspace_id", "role_id", name="ux_workspace_roles_workspace_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    workspace = relationship("Workspace", back_populates="workspace_roles")
    role = relationship("Role", back_populates="workspace_roles")
