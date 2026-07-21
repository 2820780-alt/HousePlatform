from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.v1.admin_material_hub import router as admin_material_hub_router
from app.api.v1.material_hub_view import router as material_hub_view_router
from app.config import settings
from app.models.enums import UserRole
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.schemas.auth import PUBLIC_REGISTRATION_ROLE, RegisterRequest
from app.schemas.user import UserRead, UserUpdate
from app.services import auth_service
from app.services.module1_operational_widgets import WORK_COST_WIDGET_CODE, get_module1_widget_catalog
from app.services.module1_provider_work_cost_offers import _apply_list_permissions
from tools.platform_security_image_scan import known_secret_values, parse_env_file


ROOT = Path(__file__).resolve().parents[1]


class _Result:
    def scalar_one_or_none(self):
        return None

    def scalars(self):
        return self

    def all(self) -> list:
        return []


class _FakeDb:
    def __init__(self) -> None:
        self.added = None

    async def execute(self, _statement):
        return _Result()

    def add(self, item) -> None:
        self.added = item

    async def flush(self) -> None:
        return None

    async def refresh(self, _item) -> None:
        return None


async def _fake_db_dependency():
    yield _FakeDb()


def _user(role: UserRole):
    return SimpleNamespace(id=uuid4(), role=role, roleCode=role.value)


def _client(router, role: UserRole | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    from app.database import get_db

    app.dependency_overrides[get_db] = _fake_db_dependency
    if role is not None:
        app.dependency_overrides[get_current_user] = lambda: _user(role)
    return TestClient(app)


def test_env_secret_files_are_untracked_ignored_and_excluded_from_docker() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env.docker"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert tracked.returncode != 0
    ignored = subprocess.run(
        ["git", "check-ignore", ".env.docker"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert ignored.returncode == 0

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".env.*" in gitignore
    assert "!.env.*.example" in gitignore
    assert ".env.*" in dockerignore
    assert "!.env.*.example" not in dockerignore
    assert "docs" in dockerignore
    assert "tests" in dockerignore
    assert "tools" in dockerignore


def test_safe_docker_example_contains_placeholders_not_local_secrets() -> None:
    example_path = ROOT / ".env.docker.example"
    example = parse_env_file(example_path)
    assert example["JWT_SECRET_KEY"].startswith("CHANGE_ME")
    assert example["ADMIN_PASSWORD"].startswith("CHANGE_ME")
    assert "CHANGE_ME" in example["DATABASE_URL"]
    assert "CHANGE_ME" in example["DATABASE_URL_SYNC"]

    local_env = ROOT / ".env.docker"
    if local_env.exists():
        example_bytes = example_path.read_bytes()
        assert all(value not in example_bytes for value in known_secret_values(local_env))


def test_auth_dependency_versions_are_reproducibly_pinned() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "passlib[bcrypt]==1.7.4" in requirements
    assert "bcrypt==4.0.1" in requirements


def test_packaged_config_uses_noncredential_development_placeholders() -> None:
    local_env = ROOT / ".env.docker"
    if not local_env.exists():
        pytest.skip("local env is unavailable for exact-value comparison")
    known_values = set(known_secret_values(local_env))
    packaged_defaults = {
        settings.DATABASE_URL.encode(),
        settings.DATABASE_URL_SYNC.encode(),
        settings.JWT_SECRET_KEY.encode(),
        settings.ADMIN_PASSWORD.encode(),
    }
    assert known_values.isdisjoint(packaged_defaults)
    assert settings.JWT_SECRET_KEY == "development-only-change-me"
    assert settings.ADMIN_PASSWORD == "development-only-change-me"

def test_public_registration_role_is_server_owned_and_privileged_roles_are_rejected() -> None:
    safe = RegisterRequest(email="safe@example.invalid", password="safe-password")
    assert safe.role == PUBLIC_REGISTRATION_ROLE == UserRole.SUPPLIER
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="admin@example.invalid", password="safe-password", role="ADMIN")
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="super@example.invalid", password="safe-password", role="SUPER_ADMIN")


@pytest.mark.asyncio
async def test_registration_service_assigns_safe_default_and_profile_cannot_escalate(monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "hash_password", lambda _password: "fixture-hash")
    database = _FakeDb()
    request = RegisterRequest(email="safe@example.invalid", password="safe-password")
    user = await auth_service.register_user(database, request)
    assert user.role == UserRole.SUPPLIER
    assert database.added is user
    assert "password_hash" not in UserRead.model_fields

    update = UserUpdate.model_validate({"name": "Updated", "role": "ADMIN"})
    assert "role" not in update.model_dump()


def test_anonymous_material_hub_is_denied_and_admin_is_allowed() -> None:
    anonymous = _client(material_hub_view_router)
    assert anonymous.get("/api/v1/admin/material-hub/view").status_code in {401, 403}

    admin = _client(material_hub_view_router, UserRole.ADMIN)
    assert admin.get("/api/v1/admin/material-hub/view").status_code == 200


@pytest.mark.parametrize("role", [UserRole.SUPPLIER, UserRole.CONTRACTOR, UserRole.CUSTOMER])
def test_admin_widget_catalog_rejects_non_admin_roles(role: UserRole) -> None:
    client = _client(admin_material_hub_router, role)
    assert client.get("/api/v1/admin/material-hub/widgets/catalog").status_code == 403


def test_admin_widget_catalog_allows_admin() -> None:
    client = _client(admin_material_hub_router, UserRole.ADMIN)
    assert client.get("/api/v1/admin/material-hub/widgets/catalog").status_code == 200


def test_supplier_work_cost_widget_and_owner_filter_remain_available() -> None:
    supplier = _user(UserRole.SUPPLIER)
    codes = {item["widgetCode"] for item in get_module1_widget_catalog(supplier)}
    assert codes == {WORK_COST_WIDGET_CODE}

    contractor = {"id": uuid4(), "roleCode": "CONTRACTOR"}
    query = _apply_list_permissions(select(ProviderWorkCostOffer), contractor, owner_user_id=None)
    assert "provider_work_cost_offers.owner_user_id" in str(query.whereclause)
