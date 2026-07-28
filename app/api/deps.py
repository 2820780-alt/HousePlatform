from hmac import compare_digest
from typing import Annotated
from uuid import UUID
from fastapi import Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.permission_guard import require_permission as guard_require_permission
from app.core.browser_auth import (
    ACCESS_TOKEN_COOKIE,
    CSRF_HEADER,
    CSRF_TOKEN_COOKIE,
    SAFE_METHODS,
)
from app.models.user import User
from app.models.enums import UserRole, UserStatus

security = HTTPBearer(auto_error=False)

DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    db: DBSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
) -> User:
    bearer_token = credentials.credentials if credentials else None
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    token = bearer_token or cookie_token
    if not token:
        raise UnauthorizedError()

    if not bearer_token and request.method.upper() not in SAFE_METHODS:
        csrf_cookie = request.cookies.get(CSRF_TOKEN_COOKIE)
        if (
            not csrf_cookie
            or not x_csrf_token
            or not compare_digest(csrf_cookie, x_csrf_token)
        ):
            raise ForbiddenError("Invalid or missing CSRF token")

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    try:
        uid = UUID(user_id)
    except ValueError:
        raise UnauthorizedError("Invalid token payload")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("User not found")
    if user.status != UserStatus.ACTIVE:
        raise ForbiddenError("User account is not active")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole):
    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError(f"Required role: {', '.join(r.value for r in roles)}")
        return user
    return Depends(checker)


def require_admin():
    return require_role(UserRole.ADMIN)


def require_supplier():
    return require_role(UserRole.SUPPLIER)


def require_permission(module_code: str, action_code: str, scope: str = "GLOBAL"):
    def checker(user: CurrentUser) -> User:
        guard_require_permission(user, module_code, action_code, scope)
        return user
    return Depends(checker)


def requirePermission(moduleCode: str, actionCode: str, scope: str = "GLOBAL"):
    return require_permission(moduleCode, actionCode, scope)
