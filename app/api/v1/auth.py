from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest
from app.schemas.user import UserRead, UserUpdate
from app.services.auth_service import register_user, authenticate_user
from app.services.audit_service import log_event
from app.api.deps import CurrentUser, DBSession
from app.core.security import decode_token, create_access_token, create_refresh_token
from app.core.exceptions import UnauthorizedError
from app.core.browser_auth import (
    clear_browser_session_cookies,
    safe_next_path,
    set_browser_session_cookies,
)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")


@router.post("/register", response_model=UserRead)
async def api_register(data: RegisterRequest, db: DBSession):
    user = await register_user(db, data)
    await log_event(db, "user_registered", "User", user.id, user.id)
    return user


@router.post("/login", response_model=TokenResponse)
async def api_login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: DBSession,
):
    tokens = await authenticate_user(db, data.email, data.password)
    set_browser_session_cookies(response, request, tokens.access_token)
    return tokens


@router.get("/login/view", response_class=HTMLResponse, include_in_schema=False)
async def api_login_view(
    request: Request,
    next_path: str | None = Query(default=None, alias="next"),
):
    return templates.TemplateResponse(
        request,
        "auth_login.html",
        {"next_path": safe_next_path(next_path)},
        headers={"Cache-Control": "no-store"},
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def api_logout(response: Response):
    clear_browser_session_cookies(response)


@router.post("/refresh", response_model=TokenResponse)
async def api_refresh(
    data: RefreshRequest,
    request: Request,
    response: Response,
    db: DBSession,
):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid refresh token")
    user_id = payload.get("sub")
    tokens = TokenResponse(
        access_token=create_access_token(subject=user_id),
        refresh_token=create_refresh_token(subject=user_id),
    )
    set_browser_session_cookies(response, request, tokens.access_token)
    return tokens


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
