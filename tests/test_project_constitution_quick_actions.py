from pathlib import Path

from app.core.role_dashboard_access_profiles import get_role_dashboard_access_profile_definitions
from app.services.dashboard_quick_actions import DEFAULT_ATOM_CARD_ACTION_CODES, QUICK_ACTION_REGISTRY
from app.services.dashboard_widget_registry import get_dashboard_widget_registry
from app.services.partner_portal_dashboard_presets import get_dashboard_presets
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


def test_dashboard_and_module8_presets_do_not_declare_quick_action_defaults():
    assert QUICK_ACTION_REGISTRY == ()
    assert DEFAULT_ATOM_CARD_ACTION_CODES == {}

    for preset in get_dashboard_presets():
        assert preset["recommendedQuickActionCodes"] == []
        assert preset.get("quickActionCodes") in (None, [])


def test_quick_actions_are_not_dashboard_widgets_or_widget_registry_items():
    available_widgets = [
        widget
        for widget in get_dashboard_widget_registry()
        if widget["status"] in {"available", "mock_only"}
    ]
    available_widget_codes = {widget["widgetCode"] for widget in available_widgets}

    assert "quick-actions" not in available_widget_codes
    assert all(widget["type"] != "ACTIONS" for widget in available_widgets)
    assert get_quick_action_registry() == []


def test_quick_action_candidates_do_not_use_legacy_quick_action_codes():
    candidate_templates = [
        _read("templates/material_hub_view.html"),
        _read("templates/price_dynamics_view.html"),
    ]

    for html in candidate_templates:
        assert "data-quick-action-candidate" in html
        assert "data-quick-action-key" in html
        assert "data-quick-action-code" not in html
        assert "quickActionCode" not in html


def test_local_storage_is_not_backend_source_of_truth_for_quick_actions():
    ui_partial = _read("templates/_atom_quick_action_menu.html")
    backend_text = "\n".join(
        _read(path)
        for path in [
            "app/models/user_module_quick_action.py",
            "app/services/user_module_quick_actions.py",
            "app/services/dashboard_quick_actions.py",
            "app/services/quick_action_registry.py",
            "app/services/quick_action_permission.py",
        ]
    )

    assert 'STORAGE_KEY = "atom:userModuleQuickActions:v1"' in ui_partial
    assert "user_module_quick_actions" in backend_text
    assert "localStorage" not in backend_text
    assert "atom:quick-action:add" in ui_partial
    assert "atom:quick-action:pin" in ui_partial


def test_dashboard_quick_action_contract_keeps_legacy_registry_empty_until_user_source_is_wired():
    dashboard_service = _read("app/services/dashboard_quick_actions.py")

    assert "DEFAULT_ATOM_CARD_ACTION_CODES: dict[str, tuple[str, ...]] = {}" in dashboard_service
    assert "QUICK_ACTION_REGISTRY = _dashboard_quick_action_registry()" in dashboard_service
    assert get_preview_quick_action_registry_items({"roleCode": "SUPER_ADMIN"}) == []


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
