from app.services.dashboard_cabinet_context import get_current_cabinet_context
from app.services import dashboard_quick_actions as dashboard_service
from app.services.dashboard_quick_actions import (
    get_atom_card_quick_action_options,
    get_quick_actions_for_dashboard,
)
from app.services.user_module_quick_actions import MAX_ATOM_CARD_PINNED_ACTIONS


def test_dashboard_quick_actions_do_not_use_fixed_registry_presets():
    user_context = {
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": ["SAMPLE_OPEN_LIST"],
    }
    cabinet_context = get_current_cabinet_context(user_context).to_dict()

    assert cabinet_context["cabinetDashboardPreset"]["quickActionCodes"] == []
    assert get_quick_actions_for_dashboard(user_context, cabinet_context) == []


def test_atom_card_quick_actions_require_user_selected_actions():
    user_context = {
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": ["SAMPLE_OPEN_LIST"],
    }
    cabinet_context = get_current_cabinet_context(user_context).to_dict()

    assert get_atom_card_quick_action_options(
        user_context,
        cabinet_context,
        "MODULE_01_MATERIAL_HUB",
    ) == []
    assert get_atom_card_quick_action_options(
        user_context,
        cabinet_context,
        "MODULE_01_MATERIAL_HUB",
        selected_action_codes=["SAMPLE_OPEN_LIST"],
    ) == []


def test_dashboard_quick_action_legacy_contract_is_empty_and_limited_to_three():
    assert dashboard_service.QUICK_ACTION_REGISTRY == ()
    assert dashboard_service.DEFAULT_ATOM_CARD_ACTION_CODES == {}
    assert dashboard_service.ATOM_CARD_QUICK_ACTION_LIMIT == MAX_ATOM_CARD_PINNED_ACTIONS == 3


def test_dashboard_ignores_preset_quick_action_codes_without_user_saved_source():
    user_context = {
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": ["LEGACY_FIXED_ACTION"],
    }
    cabinet_context = {
        "cabinetDashboardPreset": {
            "quickActionCodes": ["LEGACY_FIXED_ACTION"],
        }
    }

    assert get_quick_actions_for_dashboard(user_context, cabinet_context) == []
    assert get_atom_card_quick_action_options(
        user_context,
        cabinet_context,
        "MODULE_01_MATERIAL_HUB",
        selected_action_codes=["LEGACY_FIXED_ACTION"],
    ) == []
