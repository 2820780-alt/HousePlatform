from dataclasses import fields
from pathlib import Path
from app.core.role_dashboard_access_profiles import RoleDashboardAccessProfileDefinition, missing_role_dashboard_profile_codes
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
    assert supplier_profile["defaultQuickActionCodes"] == []



def test_default_quick_action_codes_are_deprecated_not_active_contract():
    field = next(item for item in fields(RoleDashboardAccessProfileDefinition) if item.name == "defaultQuickActionCodes")
    service_text = Path("app/services/role_dashboard_access_profiles.py").read_text(encoding="utf-8")
    dashboard_text = Path("app/services/dashboard_auth_adapters.py").read_text(encoding="utf-8")
    preview_text = Path("app/services/preview_role.py").read_text(encoding="utf-8")
    profile = get_role_dashboard_access_profile("ADMIN")

    assert "roles grant permissions" in field.metadata["deprecated"]
    assert profile["defaultQuickActionCodes"] == []
    assert profile["deprecatedDefaultQuickActionCodes"] == []
    assert 'profile["defaultQuickActionCodes"] = _filter_default_quick_action_codes' not in service_text
    assert 'allowedActionCodes=profile.get("defaultQuickActionCodes")' not in dashboard_text
    assert '"allowedActionCodes": profile.get("defaultQuickActionCodes")' not in preview_text

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
        "MODULE_09_PROCUREMENT",
        "MODULE_10_MARKETPLACE",
    ]
    assert context.allowedWidgetCodes == ["materials-kpi"]
    assert context.allowedActionCodes == []


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

def test_admin_dashboard_profiles_include_module3_widgets_without_quick_actions():
    profile = get_role_dashboard_access_profile("ADMIN")
    module3_codes = {
        "MODULE_03_USERS_SUMMARY_WIDGET",
        "MODULE_03_MODERATION_QUEUE_WIDGET",
        "MODULE_03_AUDIT_LOG_WIDGET",
        "MODULE_03_MODULES_STATUS_WIDGET",
        "MODULE_03_WIDGETS_STATUS_WIDGET",
    }

    assert module3_codes.issubset(set(profile["defaultWidgetCodes"]))
    assert profile["defaultQuickActionCodes"] == []
