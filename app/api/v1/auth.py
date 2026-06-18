from fastapi import APIRouter
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest
from app.schemas.user import UserRead, UserUpdate
from app.services.auth_service import register_user, authenticate_user
from app.services.audit_service import log_event
from app.api.deps import CurrentUser, DBSession
from app.core.security import decode_token, create_access_token, create_refresh_token
from app.core.exceptions import UnauthorizedError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead)
async def api_register(data: RegisterRequest, db: DBSession):
    user = await register_user(db, data)
    await log_event(db, "user_registered", "User", user.id, user.id)
    return user


@router.post("/login", response_model=TokenResponse)
async def api_login(data: LoginRequest, db: DBSession):
    return await authenticate_user(db, data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def api_refresh(data: RefreshRequest, db: DBSession):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid refresh token")
    user_id = payload.get("sub")
    return TokenResponse(
        access_token=create_access_token(subject=user_id),
        refresh_token=create_refresh_token(subject=user_id),
    )


@router.get("/me", response_model=UserRead)
async def api_me(user: CurrentUser):
    return user


@router.put("/me", response_model=UserRead)
async def api_update_me(data: UserUpdate, user: CurrentUser, db: DBSession):
    if data.name is not None:
        user.name = data.name
    if data.phone is not None:
        user.phone = data.phone
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
