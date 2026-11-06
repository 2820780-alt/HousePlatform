from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.deps import get_current_user
from app.core.browser_auth import (
    ACCESS_TOKEN_COOKIE,
    CSRF_HEADER,
    CSRF_TOKEN_COOKIE,
    browser_auth_redirect_middleware,
    safe_next_path,
)
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import create_access_token
from app.models.enums import UserRole, UserStatus


class _Result:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class _DB:
    def __init__(self, user):
        self._user = user

    async def execute(self, _statement):
        return _Result(self._user)


def _request(
    method: str = "GET",
    *,
    cookie: str | None = None,
    csrf_header: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))
    if csrf_header:
        headers.append((CSRF_HEADER.lower().encode("ascii"), csrf_header.encode("ascii")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": "/api/v1/admin/material-hub/view",
            "raw_path": b"/api/v1/admin/material-hub/view",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }
    )


@pytest.mark.asyncio
async def test_cookie_session_authenticates_safe_browser_request():
    user = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    token = create_access_token(subject=str(user.id))
    request = _request(cookie=f"{ACCESS_TOKEN_COOKIE}={token}")

    current = await get_current_user(
        request=request,
        db=_DB(user),
        credentials=None,
        x_csrf_token=None,
    )

    assert current is user


@pytest.mark.asyncio
async def test_cookie_session_requires_matching_csrf_for_unsafe_request():
    user = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    token = create_access_token(subject=str(user.id))
    cookie = f"{ACCESS_TOKEN_COOKIE}={token}; {CSRF_TOKEN_COOKIE}=csrf-value"

    with pytest.raises(ForbiddenError, match="CSRF"):
        await get_current_user(
            request=_request("POST", cookie=cookie),
            db=_DB(user),
            credentials=None,
            x_csrf_token=None,
        )

    current = await get_current_user(
        request=_request("POST", cookie=cookie, csrf_header="csrf-value"),
        db=_DB(user),
        credentials=None,
        x_csrf_token="csrf-value",
    )
    assert current is user


@pytest.mark.asyncio
async def test_bearer_api_request_does_not_require_csrf():
    user = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN, status=UserStatus.ACTIVE)
    token = create_access_token(subject=str(user.id))

    current = await get_current_user(
        request=_request("POST"),
        db=_DB(user),
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        x_csrf_token=None,
    )

    assert current is user


@pytest.mark.asyncio
async def test_missing_browser_and_bearer_token_remains_unauthorized():
    with pytest.raises(UnauthorizedError):
        await get_current_user(
            request=_request(),
            db=_DB(None),
            credentials=None,
            x_csrf_token=None,
        )


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/material-hub/view?feature=prices",
        "/api/v1/admin/module2/workbench",
        "/api/v1/admin/users-roles/view?tab=access",
        "/app/users-roles/users/user-1",
        "/api/v1/admin/module-registry/view/MODULE_03_USERS_ROLES",
    ],
)
def test_protected_html_navigation_redirects_to_safe_login(path: str):
    app = FastAPI()
    app.middleware("http")(browser_auth_redirect_middleware)

    @app.get("/{path:path}")
    async def protected_view(path: str):
        raise UnauthorizedError()

    client = TestClient(app)
    browser = client.get(
        path,
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    api = client.get(path)

    assert browser.status_code == 303
    assert browser.headers["location"].startswith("/api/v1/auth/login/view?next=")
    assert api.status_code == 401


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("/api/v1/admin/material-hub/view", "/api/v1/admin/material-hub/view"),
        ("https://example.com", "/api/v1/admin/cabinet/view"),
        ("//example.com", "/api/v1/admin/cabinet/view"),
        ("\\example.com", "/api/v1/admin/cabinet/view"),
    ],
)
def test_safe_next_path_blocks_external_redirects(candidate: str, expected: str):
    assert safe_next_path(candidate) == expected


def test_module1_fetch_hook_includes_csrf_header():
    template = (
        __import__("pathlib").Path("templates/_module1_visual_system.html")
        .read_text(encoding="utf-8")
    )
    assert "X-CSRF-Token" in template
    assert "atom_csrf_token" in template


def test_admin_form_adapter_reuses_cookie_csrf_header():
    template = (
        __import__("pathlib").Path("templates/_atom_csrf_forms.html")
        .read_text(encoding="utf-8")
    )
    users_roles = __import__("pathlib").Path("templates/admin_users_roles.html").read_text(encoding="utf-8")
    registry = __import__("pathlib").Path("templates/admin_module_registry.html").read_text(encoding="utf-8")

    assert 'readCookie("atom_csrf_token")' in template
    assert 'headers.set("X-CSRF-Token", token)' in template
    assert 'credentials: init.credentials || "same-origin"' in template
    assert '{% include "_atom_csrf_forms.html" %}' in users_roles
    assert '{% include "_atom_csrf_forms.html" %}' in registry
    assert "window.atomCsrfFetch(actionUrl" in users_roles
