from app.models import WidgetRegistryItem
from app.services.widget_registry import (
    WIDGET_REGISTRY_LAYER,
    get_available_widget_registry_items,
    get_preview_widget_registry_items,
    get_widget_registry,
    get_widget_registry_item,
)


def test_widget_registry_is_code_first_and_not_dashboard_payload_layer():
    registry = get_widget_registry()

    assert registry
    assert all(item["registryLayer"] == WIDGET_REGISTRY_LAYER for item in registry)
    assert all("sourceModuleCode" in item for item in registry)
    assert all("moduleNumber" not in item for item in registry)
    assert all("sourceModuleNumber" not in item for item in registry)
    assert all("businessPayload" not in item for item in registry)
    assert all(item["widgetType"] in {"KPI", "CHART", "LIST", "STATUS", "TASK_QUEUE", "ALERTS", "ACTIONS", "ATOM_MAP", "SUMMARY"} for item in registry)


def test_price_dynamics_widget_is_analytics_feature_with_legacy_module_alias():
    widget = get_widget_registry_item("price-dynamics")

    assert widget is not None
    assert widget.sourceModuleCode == "MODULE_11_ANALYTICS"
    assert widget.canonicalModuleCode == "MODULE_11_ANALYTICS"
    assert widget.featureCode == "PRICE_DYNAMICS"
    assert widget.legacyModuleCode == "MODULE_14_PRICE_HISTORY"
    assert widget.widgetType == "CHART"
    assert widget.status == "ACTIVE"
    assert widget.isMock is True


def test_widget_registry_filters_available_widgets_by_module_widget_and_feature_access():
    profile = {
        "roleCode": "ANALYST",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"],
        "allowedFeatureCodes": ["PRICE_DYNAMICS"],
        "allowedWidgetCodes": ["materials-kpi", "price-dynamics", "digital-house-status"],
    }

    widget_codes = {widget["widgetCode"] for widget in get_available_widget_registry_items(profile)}

    assert widget_codes == {"materials-kpi", "price-dynamics"}


def test_planned_widgets_are_hidden_from_regular_available_registry():
    regular_profile = {
        "roleCode": "CUSTOMER",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_07_DIGITAL_HOUSE"],
        "allowedWidgetCodes": ["digital-house-status"],
    }
    admin_profile = {
        "roleCode": "SUPER_ADMIN",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_07_DIGITAL_HOUSE"],
        "allowedWidgetCodes": ["digital-house-status"],
    }

    assert get_available_widget_registry_items(regular_profile) == []
    planned_codes = {widget["widgetCode"] for widget in get_preview_widget_registry_items(admin_profile)}

    assert "digital-house-status" in planned_codes


def test_widget_registry_model_has_no_module_number_logic():
    item = WidgetRegistryItem(
        widget_code="PRICE_TREND_WIDGET",
        title="Price Trend",
        source_module_code="MODULE_11_ANALYTICS",
        canonical_module_code="MODULE_11_ANALYTICS",
        feature_code="PRICE_DYNAMICS",
        legacy_module_code="MODULE_14_PRICE_HISTORY",
        widget_type="CHART",
    )

    assert item.widget_code == "PRICE_TREND_WIDGET"
    assert item.source_module_code == "MODULE_11_ANALYTICS"
    assert not hasattr(item, "module_number")
    assert not hasattr(item, "source_module_number")
