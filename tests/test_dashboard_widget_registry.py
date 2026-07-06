from app.services.dashboard_widget_registry import (
    DASHBOARD_WIDGET_REGISTRY_LAYER,
    PAYLOAD_SOURCE_MODULE_OWNED_MOCK,
    PAYLOAD_SOURCE_PLANNED_MODULE,
    PAYLOAD_SOURCE_SYSTEM_CONTEXT,
    get_available_dashboard_widgets,
    get_dashboard_widget_registry,
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
            "MODULE_03_USERS_ROLES",
        ],
        "allowedWidgetCodes": ["materials-kpi", "price-dynamics", "atom-map"],
    }

    widget_codes = {widget["widgetCode"] for widget in get_available_dashboard_widgets(profile)}

    assert "materials-kpi" in widget_codes
    assert "price-dynamics" in widget_codes
    assert "atom-map" in widget_codes
    assert "quick-actions" not in widget_codes
    assert "digital-house-status" not in widget_codes


def test_dashboard_admin_context_widgets_use_module_03_source():
    widget = get_dashboard_widget_registry_item("atom-map")

    assert widget is not None
    assert widget.sourceModuleCode == "MODULE_03_USERS_ROLES"
    assert widget.canonicalModuleCode == "MODULE_03_USERS_ROLES"
    assert widget.contextCode == "DASHBOARD_ADMIN_CONTEXT"
    assert widget.payloadSource == PAYLOAD_SOURCE_SYSTEM_CONTEXT
    assert widget.isBusinessLogicOwner is False


def test_widget_registry_is_marked_as_aggregator_not_business_owner():
    registry = get_dashboard_widget_registry()

    assert registry
    assert all(widget["registryLayer"] == DASHBOARD_WIDGET_REGISTRY_LAYER for widget in registry)
    assert all(widget["isBusinessLogicOwner"] is False for widget in registry)
    assert all(widget["payloadOwnerModuleCode"] for widget in registry)
    assert all("temporary aggregator" in widget["compatibilityNote"] for widget in registry)


def test_legacy_admin_cabinet_allowed_module_is_canonicalized_for_widgets():
    profile = {
        "roleCode": "ADMIN",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_16_ADMIN_CABINET"],
        "allowedWidgetCodes": ["atom-map"],
    }

    widget_codes = {widget["widgetCode"] for widget in get_available_dashboard_widgets(profile)}

    assert "atom-map" in widget_codes


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

    planned_widget = get_dashboard_widget_registry_item("digital-house-status")
    assert planned_widget is not None
    assert planned_widget.payloadSource == PAYLOAD_SOURCE_PLANNED_MODULE
    assert planned_widget.mockDataProvider is None
    assert planned_widget.isEnabledByDefault is False


def test_legacy_widget_source_module_is_canonicalized():
    widget = get_dashboard_widget_registry_item("price-dynamics")

    assert widget is not None
    assert widget.sourceModuleCode == "MODULE_11_ANALYTICS"
    assert widget.canonicalModuleCode == "MODULE_11_ANALYTICS"
    assert widget.legacyModuleCode is None
    assert widget.featureCode == "PRICE_DYNAMICS"
    assert widget.status == "mock_only"
    assert widget.mockDataProvider == "priceDynamicsSummary"
    assert widget.payloadSource == PAYLOAD_SOURCE_MODULE_OWNED_MOCK
    assert widget.isBusinessLogicOwner is False


def test_constructor_lite_widget_uses_module_19_canonical_source():
    widget = get_dashboard_widget_registry_item("constructor-changes")

    assert widget is not None
    assert widget.sourceModuleCode == "MODULE_19_CONSTRUCTOR_LITE"
    assert widget.canonicalModuleCode == "MODULE_19_CONSTRUCTOR_LITE"
    assert widget.legacyModuleCode is None


def test_module3_dashboard_widget_registry_contract_has_no_settings_or_quick_actions():
    expected = {
        "MODULE_03_USERS_SUMMARY_WIDGET": "Module03UsersSummaryWidget",
        "MODULE_03_MODERATION_QUEUE_WIDGET": "Module03ModerationQueueWidget",
        "MODULE_03_AUDIT_LOG_WIDGET": "Module03AuditLogWidget",
        "MODULE_03_MODULES_STATUS_WIDGET": "Module03ModulesStatusWidget",
        "MODULE_03_WIDGETS_STATUS_WIDGET": "Module03WidgetsStatusWidget",
    }

    for widget_code, component_key in expected.items():
        widget = get_dashboard_widget_registry_item(widget_code)

        assert widget is not None
        assert widget.sourceModuleCode == "MODULE_03_USERS_ROLES"
        assert widget.canonicalModuleCode == "MODULE_03_USERS_ROLES"
        assert widget.status == "available"
        assert widget.type != "ACTIONS"
        assert widget.componentKey == component_key
        assert widget.defaultSettings == {}
        assert widget.availableSettings == {}
        assert widget.requiredPermissions == []
        assert widget.mockDataProvider is None
        assert widget.payloadOwnerModuleCode == "MODULE_03_USERS_ROLES"
        assert widget.isBusinessLogicOwner is False

def test_module3_dashboard_widgets_are_available_only_with_module_and_widget_access():
    all_module3_codes = {
        "MODULE_03_USERS_SUMMARY_WIDGET",
        "MODULE_03_MODERATION_QUEUE_WIDGET",
        "MODULE_03_AUDIT_LOG_WIDGET",
        "MODULE_03_MODULES_STATUS_WIDGET",
        "MODULE_03_WIDGETS_STATUS_WIDGET",
    }
    profile = {
        "roleCode": "PLATFORM_ADMIN",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_03_USERS_ROLES"],
        "allowedWidgetCodes": sorted(all_module3_codes),
    }

    widget_codes = {widget["widgetCode"] for widget in get_available_dashboard_widgets(profile)}
    assert all_module3_codes.issubset(widget_codes)

    no_module_profile = {**profile, "allowedModuleCodes": []}
    assert all_module3_codes.isdisjoint({widget["widgetCode"] for widget in get_available_dashboard_widgets(no_module_profile)})

    one_widget_profile = {**profile, "allowedWidgetCodes": ["MODULE_03_USERS_SUMMARY_WIDGET"]}
    one_widget_codes = {widget["widgetCode"] for widget in get_available_dashboard_widgets(one_widget_profile)}
    assert "MODULE_03_USERS_SUMMARY_WIDGET" in one_widget_codes
    assert "MODULE_03_AUDIT_LOG_WIDGET" not in one_widget_codes
