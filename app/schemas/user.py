from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from app.models.enums import UserRole, UserStatus


class UserRead(BaseModel):
    id: UUID
    email: str
    phone: str | None = None
    name: str | None = None
    role: UserRole
    status: UserStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None


class UserStatusUpdate(BaseModel):
    status: UserStatus
