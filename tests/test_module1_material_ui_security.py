from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models.enums import UserRole


BASE = "/api/v1/admin/material-hub/view/materials"


@pytest.mark.parametrize("module", ["MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE"])
@pytest.mark.parametrize("level,allowed", [
    ("VIEW", {"VIEW"}),
    ("EDIT", {"VIEW", "EDIT"}),
    ("APPROVE", {"VIEW", "EDIT", "APPROVE"}),
    ("ADMIN", {"VIEW", "EDIT", "APPROVE", "ADMIN"}),
])
def test_module_permission_levels_and_explicit_deny(module, level, allowed):
    from types import SimpleNamespace
    from app.core.permission_guard import can

    actor = SimpleNamespace(moduleAccessRules=[{
        "moduleCode": module, "accessLevel": level, "accessScope": "GLOBAL",
    }])
    for action in ("VIEW", "EDIT", "APPROVE", "ADMIN"):
        assert can(actor, module, action) == (action in allowed)
    actor.moduleAccessRules.append({"moduleCode": module, "accessLevel": "NO_ACCESS", "accessScope": "NONE"})
    assert all(not can(actor, module, action) for action in ("VIEW", "EDIT", "APPROVE", "ADMIN"))


def test_material_ui_rejects_unauthenticated_requests():
    client = TestClient(app, follow_redirects=False)
    response = client.get(BASE, headers={"Accept": "application/json"})
    assert response.status_code == 401


def test_material_ui_rejects_non_admin_for_read_and_write():
    class Customer:
        id = uuid4()
        role = UserRole.CUSTOMER

    app.dependency_overrides[get_current_user] = lambda: Customer()
    try:
        client = TestClient(app, follow_redirects=False)
        assert client.get(BASE, headers={"Accept": "application/json"}).status_code == 403
        assert client.post(f"{BASE}/save", json={}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_cookie_write_without_csrf_is_forbidden_before_database_access():
    client = TestClient(app, follow_redirects=False)
    response = client.post(f"{BASE}/save", cookies={"atom_access_token": "invalid"}, json={})
    assert response.status_code == 403
