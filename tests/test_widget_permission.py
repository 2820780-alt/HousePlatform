import pytest

from app.core.exceptions import ForbiddenError
from app.services.widget_permission import (
    canAddWidget,
    canViewWidget,
    can_add_widget,
    can_view_widget,
    filterAllowedWidgets,
    filter_allowed_widgets,
    requireWidgetPermission,
    require_widget_permission,
)


def _user(**overrides):
    data = {
        "userId": "user-1",
        "roleCode": "PLATFORM_ADMIN",
        "authMode": "mock",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedFeatureCodes": ["PRICE_DYNAMICS"],
    }
    data.update(overrides)
    return data


def _context(**overrides):
    data = {
        "activeRegionCode": "KRASNODAR_KRAI",
        "roleCode": "PLATFORM_ADMIN",
        "userDashboardLayout": {
            "widgets": [
                {"widgetCode": "materials-kpi", "isVisible": True},
                {"widgetCode": "price-dynamics", "isVisible": True},
            ]
        },
    }
    data.update(overrides)
    return data


def test_can_view_widget_requires_registry_profile_permission_layout_and_region():
    assert can_view_widget(_user(), "materials-kpi", _context())
    assert canViewWidget(_user(), "materials-kpi", _context())

    assert not can_view_widget(
        _user(activeRegionCode=None),
        "materials-kpi",
        _context(activeRegionCode=None),
    )
    assert not can_view_widget(
        _user(roleCode="SUPPLIER"),
        "price-dynamics",
        _context(roleCode="SUPPLIER"),
    )


def test_layout_cannot_grant_widget_without_role_profile_and_permission():
    customer = _user(
        roleCode="CUSTOMER",
        allowedFeatureCodes=["PRICE_DYNAMICS"],
    )
    layout = _context(
        roleCode="CUSTOMER",
        userDashboardLayout={
            "widgets": [
                {"widgetCode": "price-dynamics", "isVisible": True},
            ]
        },
    )

    assert not can_view_widget(customer, "price-dynamics", layout)


def test_hidden_layout_blocks_widget_even_when_profile_allows_it():
    user = _user()
    context = _context(
        userDashboardLayout={
            "widgets": [
                {"widgetCode": "materials-kpi", "isVisible": False},
            ]
        }
    )

    assert not can_view_widget(user, "materials-kpi", context)


def test_can_add_widget_requires_dashboard_configure_permission_and_profile():
    user = _user()

    assert can_add_widget(user, "materials-kpi", _context(userDashboardLayout={"widgets": []}))
    assert canAddWidget(user, "materials-kpi", _context(userDashboardLayout={"widgets": []}))
    assert not can_add_widget(_user(roleCode="VIEWER"), "materials-kpi", _context(roleCode="VIEWER"))


def test_planned_or_disabled_widgets_are_not_available_for_view_or_add():
    user = _user(roleCode="SUPER_ADMIN")
    context = _context(roleCode="SUPER_ADMIN")

    assert not can_view_widget(user, "digital-house-status", context)
    assert not can_add_widget(user, "quick-actions", context)


def test_require_widget_permission_returns_widget_or_raises_403():
    widget = require_widget_permission("materials-kpi", _context(), user=_user())

    assert widget.widgetCode == "materials-kpi"
    assert requireWidgetPermission("materials-kpi", {**_context(), "user": _user()}).widgetCode == "materials-kpi"
    with pytest.raises(ForbiddenError):
        require_widget_permission("price-dynamics", _context(roleCode="SUPPLIER"), user=_user(roleCode="SUPPLIER"))


def test_filter_allowed_widgets_keeps_only_server_allowed_items():
    widgets = [
        {"widgetCode": "materials-kpi"},
        {"widgetCode": "price-dynamics"},
        {"widgetCode": "digital-house-status"},
        {"widgetCode": "unknown"},
    ]

    assert filter_allowed_widgets(_user(), widgets, _context()) == [
        {"widgetCode": "materials-kpi"},
        {"widgetCode": "price-dynamics"},
    ]
    assert filterAllowedWidgets(_user(), widgets, _context()) == [
        {"widgetCode": "materials-kpi"},
        {"widgetCode": "price-dynamics"},
    ]


def test_legacy_price_widget_uses_analytics_permission_and_feature():
    user = _user(roleCode="ANALYST", allowedFeatureCodes=["PRICE_DYNAMICS"])
    context = _context(
        roleCode="ANALYST",
        userDashboardLayout={"widgets": [{"widgetCode": "price-dynamics", "isVisible": True}]},
    )

    assert can_view_widget(user, "price-dynamics", context)
