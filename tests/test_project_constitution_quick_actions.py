from pathlib import Path

from app.core.role_dashboard_access_profiles import get_role_dashboard_access_profile_definitions
from app.services.active_module_quick_action_patterns import (
    get_active_module_quick_action_patterns,
    get_planned_module_quick_action_patterns,
    get_quick_action_pattern_readiness,
)
from app.services.quick_action_registry import (
    get_preview_quick_action_registry_items,
    get_quick_action_registry,
    get_quick_action_registry_items_for_module,
)
from app.services.role_dashboard_access_profiles import get_role_dashboard_access_profiles


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_quick_actions_are_not_preseeded_by_registry_or_module():
    assert get_quick_action_registry() == []
    assert get_quick_action_registry_items_for_module("MODULE_01_MATERIAL_HUB") == []
    assert get_quick_action_registry_items_for_module("MODULE_03_USERS_ROLES") == []
    assert get_preview_quick_action_registry_items({"roleCode": "SUPER_ADMIN"}) == []


def test_role_dashboard_profiles_do_not_define_default_quick_actions():
    core_profiles = get_role_dashboard_access_profile_definitions()
    service_profiles = get_role_dashboard_access_profiles()

    assert all(not profile.get("defaultQuickActionCodes") for profile in core_profiles)
    assert all(not profile.get("defaultQuickActionCodes") for profile in service_profiles)


def test_quick_action_candidates_live_on_real_module_buttons_only():
    material_hub = _read("templates/material_hub_view.html")
    price_dynamics = _read("templates/price_dynamics_view.html")
    module3 = _read("templates/admin_users_roles.html")

    assert "data-quick-action-candidate" in material_hub
    assert "data-quick-action-candidate" in price_dynamics
    assert "data-quick-action-source-module-code=\"MODULE_03_USERS_ROLES\"" not in module3
    assert "data-module3-quick-actions" not in module3
    assert "data-module3-quick-action-modal" not in module3


def test_quick_action_pattern_service_does_not_predeclare_actions_for_modules():
    assert get_active_module_quick_action_patterns() == []
    assert get_planned_module_quick_action_patterns() == []
    assert get_quick_action_pattern_readiness() == []


def test_migrations_do_not_seed_fixed_quick_action_sets():
    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "database/migrations").glob("*.sql"))
    )

    assert "INSERT INTO quick_action_registry_items" not in migration_text
    assert "default_quick_action_codes" not in migration_text
    assert "MODULE_03_FIND_USER" not in migration_text
    assert "SUPPLIER_PRICE_UPLOAD" not in migration_text
    assert "DASHBOARD_CONFIGURE" not in migration_text
