from app.services.dashboard_cabinet_context import get_current_cabinet_context
from app.services.dashboard_quick_actions import (
    get_atom_card_quick_action_options,
    get_quick_actions_for_dashboard,
)


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
