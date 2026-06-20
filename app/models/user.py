import uuid
from datetime import datetime
from sqlalchemy import String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.enums import UserRole, UserStatus


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    phone: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
        default=UserRole.SUPPLIER,
        index=True,
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="user_status", create_constraint=True),
        nullable=False,
        default=UserStatus.ACTIVE,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.utcnow()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    # Relationships
    supplier_accounts = relationship("SupplierAccount", back_populates="user")
    workspace_members = relationship("WorkspaceMember", back_populates="user")
    dashboard_profiles = relationship("DashboardProfile", back_populates="user")
    favorite_modules = relationship("FavoriteModule", back_populates="user")
    role_assignments = relationship("UserRoleAssignment", back_populates="user")
    module_access = relationship("ModuleAccess", back_populates="user")
    function_access = relationship("FunctionAccess", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    preferences = relationship("UserPreference", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

    def __repr__(self):
        return f"<User {self.email} role={self.role}>"
