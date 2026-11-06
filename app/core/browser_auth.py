from __future__ import annotations

from secrets import token_urlsafe
from urllib.parse import urlencode, urlsplit

from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from app.config import settings


ACCESS_TOKEN_COOKIE = "atom_access_token"
CSRF_TOKEN_COOKIE = "atom_csrf_token"
CSRF_HEADER = "X-CSRF-Token"
DEFAULT_BROWSER_DESTINATION = "/api/v1/admin/cabinet/view"
LOGIN_VIEW_PATH = "/api/v1/auth/login/view"
PROTECTED_BROWSER_ROOTS = (
    "/api/v1/admin/material-hub/view",
    "/api/v1/admin/module2/workbench",
    "/api/v1/module2/encyclopedia",
    "/api/v1/admin/users-roles/view",
    "/api/v1/admin/module-registry/view",
    "/app/users-roles",
)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def set_browser_session_cookies(
    response: Response,
    request: Request,
    access_token: str,
) -> str:
    csrf_token = token_urlsafe(32)
    common = {
        "max_age": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "path": "/",
        "secure": _is_secure_request(request),
        "samesite": "lax",
    }
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        CSRF_TOKEN_COOKIE,
        csrf_token,
        httponly=False,
        **common,
    )
    return csrf_token


def clear_browser_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(CSRF_TOKEN_COOKIE, path="/")


def safe_next_path(candidate: str | None) -> str:
    value = (candidate or "").strip()
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return DEFAULT_BROWSER_DESTINATION
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return DEFAULT_BROWSER_DESTINATION
    return value


async def browser_auth_redirect_middleware(request: Request, call_next):
    response = await call_next(request)
    if not _requires_browser_login_redirect(request, response):
        return response

    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    query = urlencode({"next": safe_next_path(next_path)})
    return RedirectResponse(url=f"{LOGIN_VIEW_PATH}?{query}", status_code=303)


def _requires_browser_login_redirect(request: Request, response: Response) -> bool:
    path = request.url.path
    is_protected_browser_view = any(
        path == root or path.startswith(f"{root}/")
        for root in PROTECTED_BROWSER_ROOTS
    )
    return (
        response.status_code == 401
        and request.method == "GET"
        and is_protected_browser_view
        and "text/html" in request.headers.get("accept", "").lower()
    )


def _is_secure_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    proxy_scheme = forwarded_proto.split(",", 1)[0].strip().lower()
    return request.url.scheme == "https" or proxy_scheme == "https"
