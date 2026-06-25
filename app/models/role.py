import uuid
from datetime import datetime

from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    role_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    permissions = relationship("RolePermission", back_populates="role")
    user_roles = relationship("UserRoleAssignment", back_populates="role")
    workspace_roles = relationship("WorkspaceRole", back_populates="role")
    module_access = relationship("ModuleAccess", back_populates="role")
    function_access = relationship("FunctionAccess", back_populates="role")
