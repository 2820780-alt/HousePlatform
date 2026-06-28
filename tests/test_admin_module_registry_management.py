from fastapi.testclient import TestClient

from app.api.v1.admin_module_registry_view import router as admin_module_registry_router
from app.main import app
from app.models import PlatformModuleRegistry
from app.services.admin_module_registry_management import (
    can_open_module_registry_admin,
    can_update_module_flags,
    can_update_module_status,
    is_legacy_or_alias_module,
    module_summary,
    normalize_module_status,
)


def _module(
    module_code: str,
    *,
    canonical_module_code: str | None = None,
    status: str = "ACTIVE",
    is_system: bool = False,
) -> PlatformModuleRegistry:
    return PlatformModuleRegistry(
        module_code=module_code,
        canonical_module_code=canonical_module_code or module_code,
        title=module_code,
        status=status,
        is_active=status == "ACTIVE",
        is_system=is_system,
        is_visible_in_sidebar=status == "ACTIVE",
        is_visible_on_dashboard=status == "ACTIVE",
        is_visible_on_atom_map=status == "ACTIVE",
        is_available_for_widgets=status == "ACTIVE",
    )


def test_module_registry_admin_is_limited_to_admin_roles():
    assert can_open_module_registry_admin({"roleCode": "SUPER_ADMIN"})
    assert can_open_module_registry_admin({"roleCode": "PLATFORM_ADMIN"})
    assert not can_open_module_registry_admin({"roleCode": "SUPPLIER"})


def test_legacy_modules_cannot_be_made_active():
    legacy = _module(
        "MODULE_14_PRICE_HISTORY",
        canonical_module_code="MODULE_11_ANALYTICS",
        status="MERGED",
    )

    assert is_legacy_or_alias_module(legacy)
    assert not can_update_module_status({"roleCode": "SUPER_ADMIN"}, legacy, "ACTIVE")
    assert can_update_module_status({"roleCode": "SUPER_ADMIN"}, legacy, "MERGED")
    assert not can_update_module_flags({"roleCode": "PLATFORM_ADMIN"}, legacy)


def test_platform_admin_can_only_manage_non_system_regular_statuses():
    regular = _module("MODULE_22_TEST")
    system = _module("MODULE_03_USERS_ROLES", is_system=True)
    actor = {"roleCode": "PLATFORM_ADMIN"}

    assert can_update_module_status(actor, regular, "DISABLED")
    assert can_update_module_status(actor, regular, "DRAFT")
    assert can_update_module_flags(actor, regular)
    assert not can_update_module_status(actor, regular, "ARCHIVED")
    assert not can_update_module_status(actor, system, "DISABLED")
    assert not can_update_module_flags(actor, system)


def test_module_summary_exposes_canonical_flags_and_dependency_counts():
    module = _module("MODULE_07_DIGITAL_OBJECT", canonical_module_code="MODULE_07_DIGITAL_HOUSE", status="MERGED")
    summary = module_summary(
        module,
        {
            "permissions": [{"count": 2}],
            "moduleAccess": [{"count": 1}],
            "featureAccess": [{"count": 1}],
            "widgets": [{"count": 3}],
            "dashboardLayouts": [{"count": 4}],
            "auditNotes": [{"count": 5}],
        },
    )

    assert summary["moduleCode"] == "MODULE_07_DIGITAL_OBJECT"
    assert summary["canonicalModuleCode"] == "MODULE_07_DIGITAL_HOUSE"
    assert summary["isLegacyOrAlias"]
    assert summary["dependencyCounts"] == {
        "permissions": 4,
        "widgets": 3,
        "dashboardLayouts": 4,
        "auditNotes": 5,
    }


def test_module_registry_status_normalization_is_strict():
    assert normalize_module_status("planned") == "PLANNED"
    assert normalize_module_status("ACTIVE") == "ACTIVE"
    assert normalize_module_status("DELETE") is None


def test_admin_module_registry_routes_are_registered():
    paths = {route.path for route in admin_module_registry_router.routes}

    assert "/admin/module-registry/view" in paths
    assert "/admin/module-registry/view/{module_code}" in paths
    assert "/admin/module-registry/view/{module_code}/update" in paths
    assert "/admin/module-registry/view/{module_code}/archive" in paths


def test_api_entrypoint_is_not_blank():
    client = TestClient(app)

    response = client.get("/api")

    assert response.status_code == 200
    assert "АТОМ API" in response.text
    assert "/api/v1/health" in response.text
