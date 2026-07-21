from pydantic import BaseModel, EmailStr, field_validator
from app.models.enums import UserRole


PUBLIC_REGISTRATION_ROLE = UserRole.SUPPLIER


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None
    phone: str | None = None
    role: UserRole = PUBLIC_REGISTRATION_ROLE

    @field_validator("role")
    @classmethod
    def public_role_must_be_safe_default(cls, value: UserRole) -> UserRole:
        if value != PUBLIC_REGISTRATION_ROLE:
            raise ValueError("Public registration cannot assign this role")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
