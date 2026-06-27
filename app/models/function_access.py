import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FunctionAccess(Base):
    __tablename__ = "function_access"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    role_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("roles.id"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    module_number: Mapped[int | None] = mapped_column(index=True)
    module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    canonical_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    feature_code: Mapped[str | None] = mapped_column(String(120), index=True)
    function_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    access_level: Mapped[str] = mapped_column(String(30), default="NO_ACCESS", nullable=False, index=True)
    access_scope: Mapped[str] = mapped_column(String(30), default="GLOBAL", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    role = relationship("Role", back_populates="function_access")
    user = relationship("User", back_populates="function_access")
    workspace = relationship("Workspace")
