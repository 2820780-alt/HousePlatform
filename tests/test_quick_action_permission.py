import pytest

from app.core.exceptions import ForbiddenError
from app.services.quick_action_permission import (
    canUseQuickAction,
    can_use_quick_action,
    filterAllowedQuickActions,
    filter_allowed_quick_actions,
    requireQuickActionPermission,
    require_quick_action_permission,
)


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
