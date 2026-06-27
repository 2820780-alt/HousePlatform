import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    role_code: Mapped[str | None] = mapped_column(String(80), index=True)
    permissions: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="workspace_members")

    @property
    def workspaceId(self) -> uuid.UUID:
        return self.workspace_id

    @workspaceId.setter
    def workspaceId(self, value: uuid.UUID) -> None:
        self.workspace_id = value

    @property
    def userId(self) -> uuid.UUID:
        return self.user_id

    @userId.setter
    def userId(self, value: uuid.UUID) -> None:
        self.user_id = value

    @property
    def roleCode(self) -> str:
        return self.role_code or self.role_key

    @roleCode.setter
    def roleCode(self, value: str) -> None:
        self.role_code = value
        self.role_key = value
