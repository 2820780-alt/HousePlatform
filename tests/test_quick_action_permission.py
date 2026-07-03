import pytest

from app.core.exceptions import ForbiddenError
from app.services.quick_action_permission import (
    canUseQuickAction,
    can_use_quick_action,
    can_use_quick_action_item,
    filterAllowedQuickActions,
    filter_allowed_quick_action_items,
    filter_allowed_quick_actions,
    requireQuickActionPermission,
    require_quick_action_permission,
)


SAMPLE_MODULE_QUICK_ACTIONS = [
    {
        "quickActionCode": "SAMPLE_OPEN_LIST",
        "sourceModuleCode": "MODULE_TEST_SAMPLE",
        "featureCode": "SAMPLE",
        "sectionCode": "LIST",
        "actionCode": "OPEN_LIST",
        "titleRu": "Открыть список",
        "actionType": "navigate",
        "targetRoute": "/modules/sample/list",
        "requiredPermission": "sample.read",
        "isEnabledByDefault": False,
        "isAvailable": True,
        "maxSurface": "BOTH",
        "sortOrder": 10,
    },
    {
        "quickActionCode": "SAMPLE_ARCHIVED_ACTION",
        "sourceModuleCode": "MODULE_TEST_SAMPLE",
        "featureCode": "SAMPLE",
        "sectionCode": "LEGACY",
        "actionCode": "OPEN_ARCHIVED",
        "titleRu": "Архивное действие",
        "actionType": "navigate",
        "targetRoute": "/modules/sample/legacy",
        "requiredPermission": "sample.read",
        "isEnabledByDefault": False,
        "isAvailable": False,
        "status": "DISABLED",
        "maxSurface": "BOTH",
        "sortOrder": 20,
    },
]


def _user(**overrides):
    data = {
        "userId": "user-1",
        "roleCode": "PLATFORM_ADMIN",
        "authMode": "mock",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": [
            "MATERIAL_CREATE",
            "SUPPLIER_PRICE_UPLOAD",
            "SOURCE_TASK_CREATE",
            "MATERIAL_MODERATION_OPEN",
            "SOURCE_ERRORS_OPEN",
            "SOURCE_CREATE",
            "DOCUMENT_LIST_OPEN",
            "DASHBOARD_CONFIGURE",
        ],
        "allowedFeatureCodes": ["DASHBOARD_PERSONALIZE", "PRICE_DYNAMICS"],
    }
    data.update(overrides)
    return data


def _context(**overrides):
    data = {
        "activeRegionCode": "KRASNODAR_KRAI",
        "roleCode": "PLATFORM_ADMIN",
        "activeCabinetType": "ADMIN",
    }
    data.update(overrides)
    return data


def test_can_use_quick_action_requires_region_profile_and_permission_guard():
    assert can_use_quick_action(_user(), "MATERIAL_CREATE", _context())
    assert canUseQuickAction(_user(), "MATERIAL_CREATE", _context())

    assert not can_use_quick_action(
        _user(activeRegionCode=None),
        "MATERIAL_CREATE",
        _context(activeRegionCode=None),
    )
    assert not can_use_quick_action(
        _user(roleCode="SUPPLIER", allowedActionCodes=["MATERIAL_CREATE"]),
        "MATERIAL_CREATE",
        _context(roleCode="SUPPLIER", activeCabinetType="SUPPLIER"),
    )


def test_supplier_can_open_price_upload_but_cannot_use_admin_source_task():
    supplier = _user(
        roleCode="SUPPLIER",
        allowedActionCodes=["SUPPLIER_PRICE_UPLOAD", "SOURCE_TASK_CREATE", "DASHBOARD_CONFIGURE"],
    )
    context = _context(roleCode="SUPPLIER", activeCabinetType="SUPPLIER")

    assert can_use_quick_action(supplier, "SUPPLIER_PRICE_UPLOAD", context)
    assert not can_use_quick_action(supplier, "SOURCE_TASK_CREATE", context)


def test_module8_material_supplier_cabinet_alias_allows_supplier_action():
    supplier = _user(
        roleCode="SUPPLIER",
        allowedActionCodes=["SUPPLIER_PRICE_UPLOAD", "DASHBOARD_CONFIGURE"],
    )
    context = _context(roleCode="SUPPLIER", activeCabinetType="MATERIAL_SUPPLIER")

    assert can_use_quick_action(supplier, "SUPPLIER_PRICE_UPLOAD", context)


def test_moderator_actions_are_profile_and_permission_backed():
    moderator = _user(
        roleCode="MODERATOR",
        allowedActionCodes=[
            "MATERIAL_APPROVE",
            "MATERIAL_CLASSIFICATION_FIX",
            "MATERIAL_RECHECK_SEND",
            "SOURCE_TASK_CREATE",
        ],
    )
    context = _context(roleCode="MODERATOR", activeCabinetType="MODERATOR")

    assert can_use_quick_action(moderator, "MATERIAL_APPROVE", context)
    assert can_use_quick_action(moderator, "MATERIAL_CLASSIFICATION_FIX", context)
    assert can_use_quick_action(moderator, "MATERIAL_RECHECK_SEND", context)
    assert not can_use_quick_action(moderator, "SOURCE_TASK_CREATE", context)


def test_planned_quick_actions_are_not_usable_by_ordinary_users():
    customer = _user(
        roleCode="CUSTOMER",
        allowedActionCodes=["CUSTOMER_OBJECT_CREATE", "DASHBOARD_CONFIGURE"],
    )
    context = _context(roleCode="CUSTOMER", activeCabinetType="CUSTOMER")

    assert not can_use_quick_action(customer, "CUSTOMER_OBJECT_CREATE", context)


def test_unavailable_module3_export_action_is_disabled_even_with_permission():
    admin = _user(
        roleCode="PLATFORM_ADMIN",
        allowedActionCodes=["MODULE_03_EXPORT_USERS"],
    )
    context = _context(roleCode="PLATFORM_ADMIN", activeCabinetType="ADMIN")

    assert not can_use_quick_action(admin, "MODULE_03_EXPORT_USERS", context)


def test_dashboard_configure_uses_dashboard_feature_without_business_payload():
    supplier = _user(
        roleCode="SUPPLIER",
        allowedActionCodes=["DASHBOARD_CONFIGURE"],
        allowedFeatureCodes=["DASHBOARD_PERSONALIZE"],
    )
    context = _context(roleCode="SUPPLIER", activeCabinetType="SUPPLIER")

    assert can_use_quick_action(supplier, "DASHBOARD_CONFIGURE", context)


def test_require_quick_action_permission_returns_action_or_raises_403():
    action = require_quick_action_permission("MATERIAL_CREATE", _context(), user=_user())

    assert action.quickActionCode == "MATERIAL_CREATE"
    assert requireQuickActionPermission("MATERIAL_CREATE", {**_context(), "user": _user()}).quickActionCode == "MATERIAL_CREATE"
    with pytest.raises(ForbiddenError):
        require_quick_action_permission(
            "SOURCE_TASK_CREATE",
            _context(roleCode="SUPPLIER", activeCabinetType="SUPPLIER"),
            user=_user(roleCode="SUPPLIER", allowedActionCodes=["SOURCE_TASK_CREATE"]),
        )


def test_filter_allowed_quick_actions_keeps_only_server_allowed_items():
    actions = [
        {"quickActionCode": "SUPPLIER_PRICE_UPLOAD"},
        {"quickActionCode": "SOURCE_TASK_CREATE"},
        {"quickActionCode": "CUSTOMER_OBJECT_CREATE"},
        {"quickActionCode": "unknown"},
    ]
    supplier = _user(roleCode="SUPPLIER", allowedActionCodes=["SUPPLIER_PRICE_UPLOAD", "SOURCE_TASK_CREATE"])
    context = _context(roleCode="SUPPLIER", activeCabinetType="SUPPLIER")

    assert filter_allowed_quick_actions(supplier, actions, context) == [
        {"quickActionCode": "SUPPLIER_PRICE_UPLOAD"},
    ]
    assert filterAllowedQuickActions(supplier, actions, context) == [
        {"quickActionCode": "SUPPLIER_PRICE_UPLOAD"},
    ]


def test_future_module_quick_action_items_filter_by_permissions_without_registry_rewrite():
    user = _user(
        allowedActionCodes=["SAMPLE_OPEN_LIST", "SAMPLE_ARCHIVED_ACTION"],
        moduleAccessRules=[
            {
                "moduleCode": "MODULE_TEST_SAMPLE",
                "accessLevel": "VIEW",
                "accessScope": "GLOBAL",
            }
        ],
    )
    context = _context(
        roleDashboardAccessProfile={"defaultQuickActionCodes": ["SAMPLE_OPEN_LIST", "SAMPLE_ARCHIVED_ACTION"]},
    )

    assert can_use_quick_action_item(user, SAMPLE_MODULE_QUICK_ACTIONS[0], context)
    assert not can_use_quick_action_item(user, SAMPLE_MODULE_QUICK_ACTIONS[1], context)
    assert filter_allowed_quick_action_items(user, SAMPLE_MODULE_QUICK_ACTIONS, context) == [
        SAMPLE_MODULE_QUICK_ACTIONS[0],
    ]

    denied_user = _user(
        allowedActionCodes=["SAMPLE_OPEN_LIST"],
        moduleAccessRules=[
            {
                "moduleCode": "MODULE_TEST_SAMPLE",
                "accessLevel": "NO_ACCESS",
                "accessScope": "GLOBAL",
            }
        ],
    )
    assert not can_use_quick_action_item(denied_user, SAMPLE_MODULE_QUICK_ACTIONS[0], context)

    disabled_context = _context(
        disabledModuleCodes=["MODULE_TEST_SAMPLE"],
        roleDashboardAccessProfile={"defaultQuickActionCodes": ["SAMPLE_OPEN_LIST"]},
    )
    assert not can_use_quick_action_item(user, SAMPLE_MODULE_QUICK_ACTIONS[0], disabled_context)
