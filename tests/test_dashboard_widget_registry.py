from app.services.dashboard_widget_registry import (
    get_available_dashboard_widgets,
    get_dashboard_widget_registry_item,
    get_planned_dashboard_widgets,
)


def test_widget_registry_exposes_available_widgets_for_allowed_modules():
    profile = {
        "roleCode": "ADMIN",
        "authMode": "mock",
        "allowedModuleCodes": [
            "MODULE_01_MATERIAL_HUB",
            "MODULE_11_ANALYTICS",
            "MODULE_16_ADMIN_CABINET",
        ],
        "allowedWidgetCodes": ["materials-kpi", "price-dynamics", "atom-map"],
    }

    widget_codes = {widget["widgetCode"] for widget in get_available_dashboard_widgets(profile)}

    assert "materials-kpi" in widget_codes
    assert "price-dynamics" in widget_codes
    assert "atom-map" in widget_codes
    assert "quick-actions" not in widget_codes
    assert "digital-house-status" not in widget_codes


def test_planned_widgets_are_preview_only_for_admin():
    admin_profile = {
        "roleCode": "SUPER_ADMIN",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_07_DIGITAL_HOUSE"],
        "allowedWidgetCodes": ["digital-house-status"],
    }
    regular_profile = {
        "roleCode": "VIEWER",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_07_DIGITAL_HOUSE"],
        "allowedWidgetCodes": ["digital-house-status"],
    }

    planned_codes = {widget["widgetCode"] for widget in get_planned_dashboard_widgets(admin_profile)}

    assert "digital-house-status" in planned_codes
    assert get_planned_dashboard_widgets(regular_profile) == []
    assert get_available_dashboard_widgets(regular_profile) == []


def test_legacy_widget_source_module_is_canonicalized():
    widget = get_dashboard_widget_registry_item("price-dynamics")

    assert widget is not None
    assert widget.sourceModuleCode == "MODULE_11_ANALYTICS"
    assert widget.canonicalModuleCode == "MODULE_11_ANALYTICS"
    assert widget.legacyModuleCode is None
    assert widget.featureCode == "PRICE_DYNAMICS"
