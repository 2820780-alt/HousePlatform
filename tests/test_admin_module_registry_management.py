from fastapi.testclient import TestClient
import pytest

from app.api.v1.admin_module_registry_view import router as admin_module_registry_router
from app.core.exceptions import ValidationError
from app.main import app
from app.models import PlatformModuleRegistry
from app.services.admin_module_registry_management import (
    SYSTEM_CRITICAL_MODULE_CONFIRMATION,
    can_open_module_registry_admin,
    can_update_module_flags,
    can_update_module_status,
    is_legacy_or_alias_module,
    is_system_critical_module,
    module_status_change_requires_confirmation,
    module_summary,
    normalize_module_status,
    require_system_critical_module_confirmation,
)


def _module(
    module_code: str,
    *,
    canonical_module_code: str | None = None,
    merged_into_module_code: str | None = None,
    redirect_route: str | None = None,
    status: str = "ACTIVE",
    is_system: bool = False,
    is_system_critical: bool = False,
) -> PlatformModuleRegistry:
    return PlatformModuleRegistry(
        module_code=module_code,
        canonical_module_code=canonical_module_code or module_code,
        merged_into_module_code=merged_into_module_code,
        redirect_route=redirect_route,
        title=module_code,
        status=status,
        is_active=status == "ACTIVE",
        is_system=is_system,
        is_system_critical=is_system_critical,
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
        merged_into_module_code="MODULE_11_ANALYTICS",
        redirect_route="/modules/analytics?section=price-dynamics",
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


def test_system_critical_modules_require_super_admin_and_confirmation_for_hidden_status():
    critical = _module("MODULE_03_USERS_ROLES", is_system_critical=True)

    assert is_system_critical_module(critical)
    assert not can_update_module_status({"roleCode": "PLATFORM_ADMIN"}, critical, "DISABLED")
    assert not can_update_module_status({"roleCode": "MODERATOR"}, critical, "DISABLED")
    assert not can_update_module_flags({"roleCode": "PLATFORM_ADMIN"}, critical)
    assert can_update_module_status({"roleCode": "SUPER_ADMIN"}, critical, "DISABLED")
    assert module_status_change_requires_confirmation({"roleCode": "SUPER_ADMIN"}, critical, "DISABLED")
    assert not module_status_change_requires_confirmation({"roleCode": "SUPER_ADMIN"}, critical, "ACTIVE")

    with pytest.raises(ValidationError):
        require_system_critical_module_confirmation({"roleCode": "SUPER_ADMIN"}, critical, "DISABLED", None)

    require_system_critical_module_confirmation(
        {"roleCode": "SUPER_ADMIN"},
        critical,
        "DISABLED",
        SYSTEM_CRITICAL_MODULE_CONFIRMATION,
    )


def test_module_summary_exposes_canonical_flags_and_dependency_counts():
    module = _module(
        "MODULE_07_DIGITAL_OBJECT",
        canonical_module_code="MODULE_07_DIGITAL_HOUSE",
        merged_into_module_code="MODULE_07_DIGITAL_HOUSE",
        redirect_route="/modules/digital-house",
        status="MERGED",
    )
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
    assert summary["isSystemCritical"] is False
    assert summary["lifecycle"]["rule"]["status"] == "MERGED"
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


def test_lifecycle_hides_non_active_status_even_when_form_flags_are_true():
    module = _module("MODULE_22_TEST")

    from app.services.module_lifecycle import apply_module_lifecycle_state

    apply_module_lifecycle_state(
        module,
        "DISABLED",
        visible_flags={
            "sidebar": True,
            "dashboard": True,
            "atomMap": True,
            "widgets": True,
        },
    )

    assert module.status == "DISABLED"
    assert module.is_active is False
    assert module.is_visible_in_sidebar is False
    assert module.is_visible_on_dashboard is False
    assert module.is_visible_on_atom_map is False
    assert module.is_available_for_widgets is False


def test_admin_module_registry_routes_are_registered():
    paths = {route.path for route in admin_module_registry_router.routes}

    assert "/admin/module-registry/view" in paths
    assert "/admin/module-registry/view/{module_code}" in paths
    assert "/admin/module-registry/view/{module_code}/update" in paths
    assert "/admin/module-registry/view/{module_code}/archive" in paths


def test_admin_module_registry_template_exposes_system_critical_confirmation():
    template = open("templates/admin_module_registry.html", encoding="utf-8").read()

    assert "system-critical" in template
    assert "Системно-критичный модуль нельзя отключить обычному администратору или модератору" in template
    assert "critical_confirmation" in template
    assert "CONFIRM_SYSTEM_CRITICAL_MODULE_CHANGE" not in template


def test_api_entrypoint_is_not_blank():
    client = TestClient(app)

    response = client.get("/api")

    assert response.status_code == 200
    assert "АТОМ API" in response.text
    assert "/api/v1/health" in response.text
