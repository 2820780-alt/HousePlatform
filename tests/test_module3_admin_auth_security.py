from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import app.api.deps as deps_module
import app.api.v1.admin_module_registry_view as registry_routes
import app.api.v1.admin_users_roles_view as module3_routes
from app.api.v1.admin_module_registry_view import router as registry_router
from app.api.v1.admin_users_roles_view import router as module3_router, ui_router as module3_ui_router
from app.core.browser_auth import ACCESS_TOKEN_COOKIE, CSRF_HEADER, CSRF_TOKEN_COOKIE
from app.database import get_db
from app.models.enums import UserRole, UserStatus
import app.services.admin_user_role_management as module3_service


class _Result:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class _DB:
    def __init__(self, user):
        self.user = user
        self.commits = 0

    async def execute(self, _statement):
        return _Result(self.user)

    async def commit(self):
        self.commits += 1


def _user(role: UserRole, *, workspace_members: list | None = None):
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        roleCode=role.value,
        status=UserStatus.ACTIVE,
        role_assignments=[],
        workspace_members=workspace_members or [],
        module_access=[],
    )


def _client(monkeypatch, user, *routers) -> tuple[TestClient, _DB]:
    database = _DB(user)
    app = FastAPI()
    for router in routers:
        app.include_router(router, prefix="/api/v1")

    async def fake_db():
        yield database

    app.dependency_overrides[get_db] = fake_db
    monkeypatch.setattr(
        deps_module,
        "decode_token",
        lambda _token: {"type": "access", "sub": str(user.id)} if user else None,
    )
    return TestClient(app), database


def _authenticate(client: TestClient, *, csrf: str = "csrf-value") -> dict[str, str]:
    client.cookies.set(ACCESS_TOKEN_COOKIE, "signed-access-token")
    client.cookies.set(CSRF_TOKEN_COOKIE, csrf)
    return {CSRF_HEADER: csrf}


def test_module3_admin_get_requires_authentication_and_permission(monkeypatch):
    anonymous, _ = _client(monkeypatch, None, module3_router)
    assert anonymous.get("/api/v1/admin/users-roles/view/users", follow_redirects=False).status_code == 401

    customer, _ = _client(monkeypatch, _user(UserRole.CUSTOMER), module3_router)
    _authenticate(customer)
    assert customer.get("/api/v1/admin/users-roles/view/users", follow_redirects=False).status_code == 403

    admin, _ = _client(monkeypatch, _user(UserRole.ADMIN), module3_router)
    _authenticate(admin)
    response = admin.get("/api/v1/admin/users-roles/view/users", follow_redirects=False)
    assert response.status_code == 307


def test_module3_mutation_requires_authentication_and_matching_csrf(monkeypatch):
    target_user_id = uuid4()
    path = f"/api/v1/admin/users-roles/view/users/{target_user_id}/roles"
    data = {"role_code": "VIEWER"}

    anonymous, _ = _client(monkeypatch, None, module3_router)
    assert anonymous.post(path, data=data, follow_redirects=False).status_code == 401

    actor = _user(UserRole.ADMIN)
    client, database = _client(monkeypatch, actor, module3_router)
    client.cookies.set(ACCESS_TOKEN_COOKIE, "signed-access-token")
    client.cookies.set(CSRF_TOKEN_COOKIE, "csrf-value")
    assert client.post(path, data=data, follow_redirects=False).status_code == 403
    assert client.post(path, data=data, headers={CSRF_HEADER: "wrong"}, follow_redirects=False).status_code == 403
    assert database.commits == 0


def test_module3_mutation_passes_authenticated_actor(monkeypatch):
    actor = _user(UserRole.ADMIN)
    target_user_id = uuid4()
    captured = {}

    async def assign_role(_db, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(module3_routes, "assign_role_to_user", assign_role)
    client, database = _client(monkeypatch, actor, module3_router)
    headers = _authenticate(client)
    response = client.post(
        f"/api/v1/admin/users-roles/view/users/{target_user_id}/roles",
        data={"role_code": "VIEWER"},
        headers=headers,
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert captured["actor"] is actor
    assert captured["user_id"] == target_user_id
    assert database.commits == 1


def test_moderation_passes_authenticated_actor(monkeypatch):
    actor = _user(UserRole.ADMIN)
    captured = {}

    async def moderate(_db, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(module3_routes, "moderate_company_workspace", moderate)
    client, database = _client(monkeypatch, actor, module3_router)
    workspace_id = uuid4()
    response = client.post(
        f"/api/v1/admin/users-roles/view/workspaces/{workspace_id}/moderation",
        data={"decision": "accept"},
        headers=_authenticate(client),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert captured["actor"] is actor
    assert captured["workspace_id"] == workspace_id
    assert database.commits == 1


@pytest.mark.parametrize("decision", ["accept", "reject"])
def test_moderation_decisions_reject_user_without_admin_permission(monkeypatch, decision: str):
    client, database = _client(monkeypatch, _user(UserRole.CUSTOMER), module3_router)
    headers = _authenticate(client)
    response = client.post(
        f"/api/v1/admin/users-roles/view/workspaces/{uuid4()}/moderation",
        data={"decision": decision},
        headers=headers,
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert database.commits == 0


def test_access_matrix_rejects_user_without_admin_permission(monkeypatch):
    client, database = _client(monkeypatch, _user(UserRole.CUSTOMER), module3_router)
    response = client.post(
        "/api/v1/admin/users-roles/view/access-matrix",
        data={"matrix_payload": "{}"},
        headers=_authenticate(client),
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert database.commits == 0


def test_module_registry_mutation_uses_current_user_and_csrf(monkeypatch):
    actor = _user(UserRole.ADMIN)
    captured = {}

    async def update_registry(_db, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(registry_routes, "update_module_registry_item", update_registry)
    client, database = _client(monkeypatch, actor, registry_router)
    path = "/api/v1/admin/module-registry/view/MODULE_03_USERS_ROLES/update"
    data = {"status": "ACTIVE"}
    client.cookies.set(ACCESS_TOKEN_COOKIE, "signed-access-token")
    client.cookies.set(CSRF_TOKEN_COOKIE, "csrf-value")

    assert client.post(path, data=data, follow_redirects=False).status_code == 403
    response = client.post(path, data=data, headers={CSRF_HEADER: "csrf-value"}, follow_redirects=False)

    assert response.status_code == 303
    assert captured["actor"] is actor
    assert database.commits == 1


def test_production_admin_routes_have_no_static_actor_fallback():
    route_paths = [
        Path("app/api/v1/admin_users_roles_view.py"),
        Path("app/api/v1/admin_module_registry_view.py"),
    ]
    production_sources = "\n".join(path.read_text(encoding="utf-8") for path in route_paths)

    assert "_dev_actor" not in production_sources
    assert "DEV_USER" not in production_sources


def test_every_production_admin_route_depends_on_current_user():
    routes = [
        route
        for router in (module3_router, module3_ui_router, registry_router)
        for route in router.routes
        if isinstance(route, APIRoute)
    ]

    assert routes
    assert all(
        any(dependency.call is deps_module.get_current_user for dependency in route.dependant.dependencies)
        for route in routes
    )


@pytest.mark.asyncio
async def test_access_matrix_audit_actor_is_authenticated_user(monkeypatch):
    actor = _user(UserRole.ADMIN)
    captured = {}

    async def write_event(_db, _event_type, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(module3_service, "write_audit_event", write_event)
    await module3_service.save_user_type_access_matrix_changes(
        None,
        actor=actor,
        matrix_payload={"changes": []},
    )

    assert captured["actor_user_id"] == actor.id
