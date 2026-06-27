import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    workspace_type: Mapped[str] = mapped_column(String(50), default="ADMIN", nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(120), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
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
    owner = relationship("User", foreign_keys=[owner_user_id])

    @property
    def title(self) -> str:
        return self.name

    @title.setter
    def title(self, value: str) -> None:
        self.name = value

    @property
    def type(self) -> str:
        return "INTERNAL" if self.workspace_type == "ADMIN" else self.workspace_type

    @type.setter
    def type(self, value: str) -> None:
        self.workspace_type = value

    @property
    def ownerUserId(self) -> uuid.UUID | None:
        return self.owner_user_id

    @ownerUserId.setter
    def ownerUserId(self, value: uuid.UUID | None) -> None:
        self.owner_user_id = value

    @property
    def organizationId(self) -> str | None:
        return self.organization_id

    @organizationId.setter
    def organizationId(self, value: str | None) -> None:
        self.organization_id = value

    @property
    def isActive(self) -> bool:
        return self.is_active and self.status == "ACTIVE"
