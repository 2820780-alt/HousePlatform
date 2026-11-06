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


def test_module10_widget_registry_exposes_project_catalog_planned_context():
    widget = get_widget_registry_item("project-catalog")

    assert widget is not None
    assert widget.title == "Каталог проектов"
    assert widget.sourceModuleCode == "MODULE_10_MARKETPLACE"
    assert widget.canonicalModuleCode == "MODULE_10_MARKETPLACE"
    assert widget.featureCode == "PROJECT_CATALOG"
    assert widget.status == "PLANNED"


def test_module2_readiness_widget_is_active_in_formal_registry():
    widget = get_widget_registry_item("MODULE_02_TECHNOLOGY_READINESS_WIDGET")

    assert widget is not None
    assert widget.status == "ACTIVE"
    assert widget.sourceModuleCode == "MODULE_02_KNOWLEDGE_BASE"
    assert widget.isMock is False


def test_widget_registry_filters_available_widgets_by_module_widget_and_feature_access():
    profile = {
        "roleCode": "ANALYST",
        "authMode": "mock",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"],
        "allowedFeatureCodes": ["PRICE_DYNAMICS"],
        "allowedWidgetCodes": ["materials-kpi", "price-dynamics", "digital-house-status"],
    }

    widget_codes = {widget["widgetCode"] for widget in get_available_widget_registry_items(profile)}

    assert widget_codes == {"materials-kpi", "price-dynamics"}


def test_widget_registry_requires_active_region_for_available_widgets():
    profile = {
        "roleCode": "ANALYST",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"],
        "allowedFeatureCodes": ["PRICE_DYNAMICS"],
        "allowedWidgetCodes": ["materials-kpi", "price-dynamics"],
    }

    assert get_available_widget_registry_items(profile) == []


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


def test_module3_widget_registry_exposes_only_agreed_active_admin_widgets():
    expected_titles = {
        "MODULE_03_USERS_SUMMARY_WIDGET": "\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438",
        "MODULE_03_MODERATION_QUEUE_WIDGET": "\u041e\u0447\u0435\u0440\u0435\u0434\u044c \u043d\u0430 \u043c\u043e\u0434\u0435\u0440\u0430\u0446\u0438\u044e",
        "MODULE_03_AUDIT_LOG_WIDGET": "\u0418\u0441\u0442\u043e\u0440\u0438\u044f \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0439",
        "MODULE_03_MODULES_STATUS_WIDGET": "\u041c\u043e\u0434\u0443\u043b\u0438 \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0435",
        "MODULE_03_WIDGETS_STATUS_WIDGET": "\u0412\u0438\u0434\u0436\u0435\u0442\u044b \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0435",
    }
    expected_types = {
        "MODULE_03_USERS_SUMMARY_WIDGET": "SUMMARY",
        "MODULE_03_MODERATION_QUEUE_WIDGET": "TASK_QUEUE",
        "MODULE_03_AUDIT_LOG_WIDGET": "LIST",
        "MODULE_03_MODULES_STATUS_WIDGET": "STATUS",
        "MODULE_03_WIDGETS_STATUS_WIDGET": "STATUS",
    }

    module3_widgets = [
        item
        for item in get_widget_registry()
        if item["sourceModuleCode"] == "MODULE_03_USERS_ROLES"
        and item["widgetCode"].startswith("MODULE_03_")
        and item["widgetCode"].endswith("_WIDGET")
    ]

    assert {item["widgetCode"] for item in module3_widgets} == set(expected_titles)
    for item in module3_widgets:
        assert item["title"] == expected_titles[item["widgetCode"]]
        assert item["canonicalModuleCode"] == "MODULE_03_USERS_ROLES"
        assert item["widgetType"] == expected_types[item["widgetCode"]]
        assert item["status"] == "ACTIVE"
        assert item["isDashboardEligible"] is True
        assert item["isMock"] is False
        assert item["widgetType"] != "ACTIONS"
