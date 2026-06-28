from app.core.role_dashboard_access_profiles import missing_role_dashboard_profile_codes
from app.models import RoleDashboardAccessProfile
from app.services.dashboard_auth_adapters import get_dashboard_user_context
from app.services.role_dashboard_access_profiles import (
    ROLE_DASHBOARD_PROFILE_LAYER,
    can_preview_dashboard_access_profiles,
    get_role_dashboard_access_profile,
    get_role_dashboard_access_profiles,
    get_role_dashboard_preview_options,
)


def test_all_system_roles_have_dashboard_access_profiles():
    assert missing_role_dashboard_profile_codes() == set()

    profiles = get_role_dashboard_access_profiles()

    assert len(profiles) >= 11
    assert all(profile["sourceModuleCode"] == "MODULE_03_USERS_ROLES" for profile in profiles)
    assert all(profile["profileLayer"] == ROLE_DASHBOARD_PROFILE_LAYER for profile in profiles)


def test_profile_filters_widgets_through_registry_and_permissions_layer():
    supplier_profile = get_role_dashboard_access_profile("SUPPLIER")

    assert supplier_profile is not None
    assert "MODULE_01_MATERIAL_HUB" in supplier_profile["allowedModuleCodes"]
    assert "MODULE_11_ANALYTICS" not in supplier_profile["allowedModuleCodes"]
    assert supplier_profile["defaultWidgetCodes"] == ["materials-kpi"]
    assert "digital-house-status" not in supplier_profile["defaultWidgetCodes"]
    assert "SUPPLIER_PRICE_UPLOAD" in supplier_profile["defaultQuickActionCodes"]
    assert "SOURCE_TASK_CREATE" not in supplier_profile["defaultQuickActionCodes"]


def test_legacy_admin_uses_platform_admin_dashboard_profile():
    profile = get_role_dashboard_access_profile("ADMIN")

    assert profile is not None
    assert profile["roleCode"] == "PLATFORM_ADMIN"
    assert "MODULE_03_USERS_ROLES" in profile["allowedModuleCodes"]
    assert "DASHBOARD_REGISTRY_ADMIN" in profile["allowedFeatureCodes"]


def test_preview_role_options_are_profile_backed_not_separate_dashboards():
    options = get_role_dashboard_preview_options()
    option_codes = {option["roleCode"] for option in options}

    assert "SUPPLIER" in option_codes
    assert "CUSTOMER" in option_codes
    assert "SUPER_ADMIN" not in option_codes
    assert can_preview_dashboard_access_profiles("SUPER_ADMIN")
    assert can_preview_dashboard_access_profiles("ADMIN")
    assert not can_preview_dashboard_access_profiles("SUPPLIER")


def test_dashboard_context_consumes_role_dashboard_access_profile_for_preview():
    context = get_dashboard_user_context(
        personalization={
            "active_workspace": "Администрирование",
            "favorite_modules": [{"module_code": "MODULE_01_MATERIAL_HUB"}],
            "widgets": [],
        },
        active_region={"code": "KRASNODAR_KRAI", "name": "Краснодарский край"},
        cards=[
            {
                "module_code": "MODULE_01_MATERIAL_HUB",
                "canonical_module_code": "MODULE_01_MATERIAL_HUB",
                "atom_status": "active",
            },
            {
                "module_code": "MODULE_11_ANALYTICS",
                "canonical_module_code": "MODULE_11_ANALYTICS",
                "atom_status": "active",
            },
        ],
        preview_role_code="SUPPLIER",
    )

    assert context.roleCode == "ADMIN"
    assert context.effectiveRoleCode == "SUPPLIER"
    assert context.activeCabinetType == "SUPPLIER"
    assert context.workspaceType == "SUPPLIER"
    assert context.allowedModuleCodes == [
        "MODULE_01_MATERIAL_HUB",
        "MODULE_08_PROCUREMENT",
        "MODULE_09_TENDERS",
        "MODULE_10_MARKETPLACE",
    ]
    assert context.allowedWidgetCodes == ["materials-kpi"]
    assert context.allowedActionCodes == ["SUPPLIER_PRICE_UPLOAD", "DASHBOARD_CONFIGURE"]


def test_role_dashboard_access_profile_model_is_module03_preset_not_payload():
    profile = RoleDashboardAccessProfile(
        role_code="VIEWER",
        source_module_code="MODULE_03_USERS_ROLES",
        allowed_module_codes=["MODULE_01_MATERIAL_HUB"],
        default_widget_codes=["materials-kpi"],
        default_quick_action_codes=[],
    )

    assert profile.source_module_code == "MODULE_03_USERS_ROLES"
    assert not hasattr(profile, "business_payload")
