from app.services.partner_portal_dashboard_preferences import (
    add_module_shortcut,
    apply_cabinet_dashboard_preferences,
    build_default_cabinet_dashboard_preferences,
    hide_block,
    pin_block,
    remove_widget,
    reorder_block,
    reset_to_role_template,
    set_quick_action_visibility,
    show_block,
)


CUSTOMER_ACCESS = {
    "userId": "customer-user",
    "workspaceId": "workspace-customer",
    "activeRegionCode": "KRASNODAR_KRAI",
    "allowedModuleCodes": [
        "MODULE_07_DIGITAL_HOUSE",
        "MODULE_05_ESTIMATE_ENGINE",
        "MODULE_06_ESTIMATE_AUDIT",
        "MODULE_09_PROCUREMENT",
        "MODULE_10_MARKETPLACE",
        "MODULE_11_ANALYTICS",
    ],
    "allowedFeatureCodes": [
        "HOUSE_PROFILE",
        "ESTIMATE_ENGINE",
        "ESTIMATE_AUDIT",
        "HOUSE_STORAGE",
        "PROCUREMENT_REQUESTS",
        "PRICE_DYNAMICS",
    ],
    "allowedWidgetCodes": [
        "atom-map",
        "digital-house-status",
        "estimate-summary",
        "estimate-audit-risk",
        "procurement-requests",
        "price-dynamics",
    ],
    "allowedQuickActionCodes": [],
}


def test_default_preferences_are_built_from_filtered_preset():
    preferences = build_default_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        access_context=CUSTOMER_ACCESS,
        include_future=True,
        cabinet_id="cabinet-customer",
    ).to_dict()

    assert preferences["sourceModuleCode"] == "MODULE_08_PARTNER_PORTAL"
    assert preferences["userId"] == "customer-user"
    assert preferences["workspaceId"] == "workspace-customer"
    assert preferences["cabinetId"] == "cabinet-customer"
    assert preferences["blockPreferences"]
    assert preferences["widgetPreferences"]
    assert preferences["quickActions"] == []
    assert preferences["moduleShortcuts"] == []


def test_hide_show_reorder_and_pin_block_changes_resulting_preset():
    preferences = build_default_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        access_context=CUSTOMER_ACCESS,
        include_future=True,
    )

    preferences = hide_block(preferences, "OBJECT_STORAGE_BLOCK")
    hidden = apply_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        preferences,
        access_context=CUSTOMER_ACCESS,
        include_future=True,
    )
    assert "OBJECT_STORAGE_BLOCK" not in hidden["recommendedBlockCodes"]

    preferences = show_block(preferences, "OBJECT_STORAGE_BLOCK")
    preferences = reorder_block(preferences, "PRICE_ANALYTICS_BLOCK", 1)
    ordered = apply_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        preferences,
        access_context=CUSTOMER_ACCESS,
        include_future=True,
    )
    assert ordered["recommendedBlockCodes"][0] == "PRICE_ANALYTICS_BLOCK"

    preferences = pin_block(preferences, "PROCUREMENT_BLOCK")
    pinned = apply_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        preferences,
        access_context=CUSTOMER_ACCESS,
        include_future=True,
    )
    assert pinned["recommendedBlockCodes"][0] == "PROCUREMENT_BLOCK"


def test_add_module_shortcut_respects_module3_allowed_modules():
    preferences = build_default_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        access_context=CUSTOMER_ACCESS,
    )

    allowed = add_module_shortcut(
        preferences,
        shortcut_code="customer-house",
        title="Открыть объект",
        target_module_code="MODULE_07_DIGITAL_HOUSE",
        route="/modules/digital-house",
        access_context=CUSTOMER_ACCESS,
    )
    denied = add_module_shortcut(
        allowed,
        shortcut_code="admin-registry",
        title="Реестр модулей",
        target_module_code="MODULE_03_USERS_ROLES",
        route="/api/v1/admin/modules",
        access_context=CUSTOMER_ACCESS,
    )
    result = apply_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        denied,
        access_context=CUSTOMER_ACCESS,
    )

    assert result["moduleShortcuts"] == [
        {
            "shortcutCode": "customer-house",
            "title": "Открыть объект",
            "targetModuleCode": "MODULE_07_DIGITAL_HOUSE",
            "route": "/modules/digital-house",
            "icon": None,
            "sortOrder": 10,
            "isVisible": True,
            "sourceModuleCode": "MODULE_08_PARTNER_PORTAL",
        }
    ]
    assert denied.deniedOperations[0]["operation"] == "add_module_shortcut"
    assert denied.deniedOperations[0]["sourceModuleCode"] == "MODULE_03_USERS_ROLES"


def test_remove_widget_and_quick_action_visibility_do_not_bypass_permissions():
    preferences = build_default_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        access_context=CUSTOMER_ACCESS,
    )
    preferences = remove_widget(preferences, "price-dynamics")
    preferences = set_quick_action_visibility(preferences, "SAMPLE_OPEN_LIST", False)

    result = apply_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        preferences,
        access_context=CUSTOMER_ACCESS,
    )

    assert "price-dynamics" not in result["recommendedWidgetCodes"]
    assert "recommendedQuickActionCodes" not in result
    assert result["deprecatedRecommendedQuickActionCodes"] == []
    assert result["preferenceState"]["quickActions"] == []


def test_reset_to_role_template_restores_filtered_defaults():
    preferences = build_default_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        access_context=CUSTOMER_ACCESS,
    )
    preferences = remove_widget(preferences, "price-dynamics")
    preferences = hide_block(preferences, "OBJECT_IMAGE_BLOCK")

    reset = reset_to_role_template(
        "CustomerDashboardPreset",
        access_context=CUSTOMER_ACCESS,
    )
    result = apply_cabinet_dashboard_preferences(
        "CustomerDashboardPreset",
        reset,
        access_context=CUSTOMER_ACCESS,
    )

    assert reset.isResetToRoleTemplate is True
    assert "price-dynamics" in result["recommendedWidgetCodes"]
    assert "OBJECT_IMAGE_BLOCK" in result["recommendedBlockCodes"]
