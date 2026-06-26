from app.services.dashboard_cabinet_context import get_current_cabinet_context
from app.services.dashboard_quick_actions import get_quick_actions_for_dashboard


def test_quick_actions_are_filtered_by_permissions_and_cabinet_preset():
    user_context = {
        "roleCode": "ADMIN",
        "allowedActionCodes": ["SUPPLIER_PRICE_UPLOAD", "DASHBOARD_CONFIGURE"],
    }
    cabinet_context = get_current_cabinet_context(user_context).to_dict()

    action_codes = {action["actionCode"] for action in get_quick_actions_for_dashboard(user_context, cabinet_context)}

    assert action_codes == {"SUPPLIER_PRICE_UPLOAD", "DASHBOARD_CONFIGURE"}


def test_admin_quick_actions_have_module_and_feature_codes():
    user_context = {
        "roleCode": "ADMIN",
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
