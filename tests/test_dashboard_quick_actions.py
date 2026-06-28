from app.services.dashboard_cabinet_context import get_current_cabinet_context
from app.services.dashboard_quick_actions import (
    ATOM_CARD_QUICK_ACTION_LIMIT,
    get_atom_card_quick_action_options,
    get_quick_actions_for_dashboard,
)


def test_quick_actions_are_filtered_by_permissions_and_cabinet_preset():
    user_context = {
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": ["SUPPLIER_PRICE_UPLOAD", "DASHBOARD_CONFIGURE"],
    }
    cabinet_context = get_current_cabinet_context(user_context).to_dict()

    action_codes = {action["actionCode"] for action in get_quick_actions_for_dashboard(user_context, cabinet_context)}

    assert action_codes == {"SUPPLIER_PRICE_UPLOAD", "DASHBOARD_CONFIGURE"}
    dashboard_action = next(action for action in get_quick_actions_for_dashboard(user_context, cabinet_context) if action["actionCode"] == "DASHBOARD_CONFIGURE")
    assert dashboard_action["moduleCode"] == "MODULE_03_USERS_ROLES"
    assert dashboard_action["contextCode"] == "DASHBOARD_ADMIN_CONTEXT"


def test_admin_quick_actions_have_module_and_feature_codes():
    user_context = {
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": [
            "SUPPLIER_PRICE_UPLOAD",
            "SOURCE_TASK_CREATE",
            "MATERIAL_MODERATION_OPEN",
            "SOURCE_ERRORS_OPEN",
            "SOURCE_CREATE",
        ],
    }
    cabinet_context = get_current_cabinet_context(user_context).to_dict()

    actions = get_quick_actions_for_dashboard(user_context, cabinet_context)

    assert [action["actionCode"] for action in actions] == [
        "SUPPLIER_PRICE_UPLOAD",
        "SOURCE_TASK_CREATE",
        "MATERIAL_MODERATION_OPEN",
        "SOURCE_ERRORS_OPEN",
        "SOURCE_CREATE",
    ]
    assert all(action["moduleCode"] for action in actions)
    assert all(action["featureCode"] for action in actions)


def test_atom_card_quick_actions_are_module_scoped_and_limited():
    user_context = {
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": [
            "SUPPLIER_PRICE_UPLOAD",
            "SOURCE_TASK_CREATE",
            "MATERIAL_MODERATION_OPEN",
            "SOURCE_ERRORS_OPEN",
            "SOURCE_CREATE",
            "MATERIAL_CREATE",
            "DOCUMENT_LIST_OPEN",
        ],
    }
    cabinet_context = get_current_cabinet_context(user_context).to_dict()

    actions = get_atom_card_quick_action_options(
        user_context,
        cabinet_context,
        "MODULE_01_MATERIAL_HUB",
    )
    selected = [action for action in actions if action["isSelected"]]

    assert len(selected) == ATOM_CARD_QUICK_ACTION_LIMIT
    assert [action["actionCode"] for action in selected] == [
        "MATERIAL_CREATE",
        "SUPPLIER_PRICE_UPLOAD",
        "MATERIAL_MODERATION_OPEN",
    ]
    assert all(action["moduleCode"] == "MODULE_01_MATERIAL_HUB" for action in actions)
