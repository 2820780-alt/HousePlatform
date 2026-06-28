from app.models import UserDashboardLayout
from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_CONTEXT
from app.services.user_dashboard_layout import (
    add_widget_to_layout,
    hide_widget_in_layout,
    normalize_favorite_modules,
    normalize_user_dashboard_layout,
    reset_layout_to_role_profile,
    validate_user_dashboard_layout,
)


def _admin_user(**overrides):
    data = {
        "userId": "admin-1",
        "roleCode": "PLATFORM_ADMIN",
        "authMode": "mock",
        "workspaceId": "workspace-1",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedFeatureCodes": ["PRICE_DYNAMICS"],
        "allowedWidgetCodes": ["materials-kpi", "price-dynamics", "source-health"],
    }
    data.update(overrides)
    return data


def test_favorite_modules_normalize_legacy_codes_without_deleting_layout():
    assert normalize_favorite_modules(
        [
            "MODULE_14_PRICE_HISTORY",
            "MODULE_07_DIGITAL_OBJECT",
            "MODULE_16_ADMIN_CABINET",
            "MODULE_01_MATERIAL_HUB",
        ]
    ) == [
        "MODULE_11_ANALYTICS",
        "MODULE_07_DIGITAL_HOUSE",
        DASHBOARD_ADMIN_CONTEXT,
        "MODULE_01_MATERIAL_HUB",
    ]


def test_normalize_user_dashboard_layout_keeps_code_first_widget_items():
    layout = normalize_user_dashboard_layout(
        {
            "id": "layout-1",
            "userId": "admin-1",
            "activeRegionCode": "KRASNODAR_KRAI",
            "activeCabinetId": "cabinet-admin",
            "cabinetType": "ADMIN",
            "favoriteModules": ["MODULE_14_PRICE_HISTORY", "MODULE_16_ADMIN_CABINET"],
            "widgets": [
                {"widgetCode": "price-dynamics", "position": "2", "zone": "right_optional", "size": "LARGE"},
                {"widgetCode": "unknown-widget", "position": 3},
            ],
        },
        user=_admin_user(),
    )

    assert layout["favoriteModules"] == ["MODULE_11_ANALYTICS", DASHBOARD_ADMIN_CONTEXT]
    assert layout["widgets"] == [
        {
            "widgetCode": "price-dynamics",
            "sourceModuleCode": "MODULE_11_ANALYTICS",
            "position": 2,
            "size": "large",
            "isVisible": True,
            "featureCode": "PRICE_DYNAMICS",
            "zone": "RIGHT_OPTIONAL",
        }
    ]
    assert "moduleNumber" not in layout["widgets"][0]


def test_validate_layout_filters_widgets_through_widget_permission():
    layout = {
        "userId": "customer-1",
        "activeRegionCode": "KRASNODAR_KRAI",
        "favoriteModules": ["MODULE_14_PRICE_HISTORY"],
        "widgets": [
            {"widgetCode": "price-dynamics", "position": 1},
            {"widgetCode": "digital-house-status", "position": 2},
        ],
    }

    validated = validate_user_dashboard_layout(
        layout,
        user={
            "userId": "customer-1",
            "roleCode": "CUSTOMER",
            "activeRegionCode": "KRASNODAR_KRAI",
            "allowedWidgetCodes": ["price-dynamics", "digital-house-status"],
            "allowedFeatureCodes": ["PRICE_DYNAMICS"],
        },
    )

    assert validated["widgets"] == []


def test_add_widget_to_layout_allows_only_permitted_widgets():
    layout = {
        "userId": "admin-1",
        "activeRegionCode": "KRASNODAR_KRAI",
        "widgets": [],
    }

    updated = add_widget_to_layout(layout, "materials-kpi", user=_admin_user())
    denied = add_widget_to_layout(layout, "digital-house-status", user=_admin_user())

    assert [widget["widgetCode"] for widget in updated["widgets"]] == ["materials-kpi"]
    assert denied["widgets"] == []


def test_hide_widget_updates_visibility_without_removing_layout_item():
    layout = {
        "userId": "admin-1",
        "activeRegionCode": "KRASNODAR_KRAI",
        "widgets": [{"widgetCode": "materials-kpi", "position": 1, "isVisible": True}],
    }

    updated = hide_widget_in_layout(layout, "materials-kpi", user=_admin_user())

    assert updated["widgets"][0]["widgetCode"] == "materials-kpi"
    assert updated["widgets"][0]["isVisible"] is False


def test_reset_layout_to_role_profile_uses_profile_and_widget_permission():
    layout = reset_layout_to_role_profile(
        user=_admin_user(roleCode="ANALYST", allowedWidgetCodes=["materials-kpi", "price-dynamics", "source-health"]),
        context={"activeRegionCode": "KRASNODAR_KRAI"},
    )

    assert layout["favoriteModules"] == ["MODULE_11_ANALYTICS", "MODULE_01_MATERIAL_HUB", "MODULE_13_AUDIT"]
    assert [widget["widgetCode"] for widget in layout["widgets"]] == [
        "price-dynamics",
        "materials-kpi",
        "source-health",
    ]


def test_user_dashboard_layout_model_is_code_first_and_payload_free():
    layout = UserDashboardLayout(
        user_id="00000000-0000-0000-0000-000000000001",
        active_region_code="KRASNODAR_KRAI",
        favorite_modules=["MODULE_01_MATERIAL_HUB"],
        widgets=[{"widgetCode": "materials-kpi"}],
    )

    assert layout.active_region_code == "KRASNODAR_KRAI"
    assert not hasattr(layout, "module_number")
    assert not hasattr(layout, "business_payload")
