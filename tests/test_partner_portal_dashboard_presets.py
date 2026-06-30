from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_dashboard_presets import (
    BOTTOM_WIDGET_GRID,
    get_dashboard_preset_for_context,
    get_dashboard_presets,
    filter_dashboard_preset_for_access,
)


EXPECTED_PRESETS = {
    "CustomerDashboardPreset",
    "SupplierDashboardPreset",
    "ConstructionCompanyDashboardPreset",
    "SpecialistDashboardPreset",
    "ForemanDashboardPreset",
    "ProcurementEngineerDashboardPreset",
    "EstimatorDashboardPreset",
    "PTOEngineerDashboardPreset",
    "DesignerDashboardPreset",
}


def test_dashboard_preset_catalog_contains_required_presets():
    presets = get_dashboard_presets()
    codes = {item["presetCode"] for item in presets}

    assert EXPECTED_PRESETS == codes
    for item in presets:
        assert item["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
        assert item["permissionFilterSourceModuleCode"] == "MODULE_03_USERS_ROLES"
        assert item["cabinetType"]
        assert item["businessRole"]
        assert item["primaryGoal"]
        assert item["mainFocus"]
        assert item["recommendedModuleCodes"]
        assert item["recommendedBlockCodes"]
        assert item["recommendedWidgetCodes"]
        assert item["recommendedQuickActionCodes"]
        assert item["zones"]
        assert "Dashboard only renders data" in item["compatibilityNote"]


def test_supplier_preset_filters_modules_widgets_actions_and_blocks_through_module3_context():
    preset = filter_dashboard_preset_for_access(
        "SupplierDashboardPreset",
        access_context={
            "userId": "supplier-user",
            "activeRegionCode": "KRASNODAR_KRAI",
            "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB"],
            "allowedFeatureCodes": ["SUPPLIER_PRICE_LIST"],
            "allowedWidgetCodes": ["materials-kpi"],
            "allowedQuickActionCodes": ["SUPPLIER_PRICE_UPLOAD"],
        },
    )

    assert preset["isPermissionFiltered"] is True
    assert preset["recommendedModuleCodes"] == ["MODULE_01_MATERIAL_HUB"]
    assert preset["recommendedWidgetCodes"] == ["materials-kpi"]
    assert preset["recommendedQuickActionCodes"] == ["SUPPLIER_PRICE_UPLOAD"]
    assert preset["recommendedBlockCodes"] == ["SUPPLIER_PRICE_LIST_BLOCK"]
    assert "SUPPLIER_REQUESTS_BLOCK" in preset["deniedByAccess"]["blockCodes"]
    assert "source-health" in preset["deniedByAccess"]["widgetCodes"]
    assert "SUPPLIER_PRICE_UPDATE" in preset["deniedByAccess"]["quickActionCodes"]


def test_future_blocks_are_hidden_until_explicitly_requested_and_allowed():
    access_context = {
        "userId": "customer-user",
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
        "allowedQuickActionCodes": [
            "CUSTOMER_OBJECT_CREATE",
            "CUSTOMER_ESTIMATE_REQUEST",
            "CUSTOMER_PROCUREMENT_REQUEST",
            "DASHBOARD_CONFIGURE",
        ],
    }

    default_preset = filter_dashboard_preset_for_access(
        "CustomerDashboardPreset",
        access_context=access_context,
    )
    future_preset = filter_dashboard_preset_for_access(
        "CustomerDashboardPreset",
        access_context=access_context,
        include_future=True,
    )

    assert "ESTIMATES_BLOCK" not in default_preset["recommendedBlockCodes"]
    assert "PROCUREMENT_BLOCK" not in default_preset["recommendedBlockCodes"]
    assert "ESTIMATES_BLOCK" in future_preset["recommendedBlockCodes"]
    assert "PROCUREMENT_BLOCK" in future_preset["recommendedBlockCodes"]
    assert "PRICE_ANALYTICS_BLOCK" in future_preset["futureBlockCodes"]


def test_context_selects_role_specific_preset_without_creating_another_dashboard():
    preset = get_dashboard_preset_for_context(
        {
            "activeCabinetType": "SPECIALIST",
            "activeBusinessRole": "ESTIMATOR",
        },
        access_context={
            "userId": "estimator-user",
            "activeRegionCode": "KRASNODAR_KRAI",
            "allowedModuleCodes": [
                "MODULE_05_ESTIMATE_ENGINE",
                "MODULE_06_ESTIMATE_AUDIT",
                "MODULE_04_WORKS_COSTS",
                "MODULE_01_MATERIAL_HUB",
                "MODULE_11_ANALYTICS",
            ],
            "allowedFeatureCodes": [],
            "allowedWidgetCodes": ["materials-kpi", "price-dynamics"],
            "allowedQuickActionCodes": ["DOCUMENT_LIST_OPEN", "DASHBOARD_CONFIGURE"],
        },
    )

    assert preset is not None
    assert preset["presetCode"] == "EstimatorDashboardPreset"
    assert preset["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert any(zone["zoneCode"] == BOTTOM_WIDGET_GRID for zone in preset["zones"])
    assert "materials-kpi" in preset["recommendedWidgetCodes"]
    assert "DASHBOARD_CONFIGURE" in preset["recommendedQuickActionCodes"]
    assert "route" not in preset
