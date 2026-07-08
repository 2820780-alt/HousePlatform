from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_adapter import (
    MODULE_03_USERS_ROLES,
    getActiveCabinetContext,
    getAvailableCabinets,
    getCabinetBlockCatalog,
    getCabinetDashboardContext,
    getCabinetDashboardPreset,
    getCabinetObjectLinks,
    getCabinetQuickActions,
    getCabinetSummary,
    getCabinetWidgetPreferences,
    getObjectVisibilityForCabinet,
    switchActiveCabinet,
    updateCabinetWidgetPreferences,
    updateObjectOfferSettings,
)


MODULE8_CONTEXT = {
    "userId": "customer-user-1",
    "roleCode": "CUSTOMER",
    "workspaceId": "workspace-customer-1",
    "activeRegionCode": "KRASNODAR_KRAI",
    "activeCabinetId": "cabinet-customer-1",
    "permissions": {
        "allowedModuleCodes": [
            "MODULE_07_DIGITAL_HOUSE",
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_06_ESTIMATE_AUDIT",
            "MODULE_09_PROCUREMENT",
            "MODULE_10_MARKETPLACE",
            "MODULE_11_ANALYTICS",
            "PARTICIPANT_CABINET_CONTEXT",
        ],
        "allowedFeatureCodes": [
            "CUSTOMER_OBJECTS",
            "ESTIMATE_ENGINE",
            "ESTIMATE_AUDIT",
            "HOUSE_STORAGE",
            "PROCUREMENT_REQUESTS",
            "VISIBILITY_SETTINGS",
            "OFFER_SETTINGS",
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
    },
    "availableCabinets": [
        {
            "cabinetId": "cabinet-customer-1",
            "cabinetType": "CUSTOMER",
            "title": "Кабинет заказчика",
            "businessRole": "CUSTOMER",
            "workspaceId": "workspace-customer-1",
            "isActive": True,
        },
        {
            "cabinetId": "cabinet-specialist-1",
            "cabinetType": "SPECIALIST",
            "title": "Кабинет специалиста",
            "businessRole": "ESTIMATOR",
            "workspaceId": "workspace-customer-1",
        },
    ],
    "linkedObjects": [
        {
            "cabinetId": "cabinet-customer-1",
            "objectId": "object-1",
            "relationType": "OWNER",
            "visibilityScope": "PRIVATE",
            "sourceModuleCode": "MODULE_07_DIGITAL_HOUSE",
        }
    ],
    "objectVisibilitySettings": [
        {
            "cabinetId": "cabinet-customer-1",
            "objectId": "object-1",
            "visibilityScope": "REGION",
            "showRegion": True,
            "showExactAddress": False,
        }
    ],
}


def test_partner_portal_adapter_active_context_and_switch():
    context = getActiveCabinetContext(MODULE8_CONTEXT)
    switched = switchActiveCabinet("cabinet-specialist-1", MODULE8_CONTEXT)
    available = getAvailableCabinets(MODULE8_CONTEXT)

    assert context["userId"] == "customer-user-1"
    assert context["activeCabinetId"] == "cabinet-customer-1"
    assert context["activeCabinetType"] == "CUSTOMER"
    assert switched["previousActiveCabinetId"] == "cabinet-customer-1"
    assert switched["activeCabinetId"] == "cabinet-specialist-1"
    assert len(available) == 2
    assert all(item["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL for item in [context, switched])


def test_partner_portal_adapter_dashboard_context_preset_blocks_and_actions():
    dashboard_context = getCabinetDashboardContext("cabinet-customer-1", MODULE8_CONTEXT)
    preset = getCabinetDashboardPreset("cabinet-customer-1", MODULE8_CONTEXT)
    blocks = getCabinetBlockCatalog("cabinet-customer-1", MODULE8_CONTEXT)
    actions = getCabinetQuickActions("cabinet-customer-1", MODULE8_CONTEXT)

    assert dashboard_context["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert preset["presetCode"] == "CustomerDashboardPreset"
    assert "MODULE_07_DIGITAL_HOUSE" in preset["recommendedModuleCodes"]
    assert any(block["blockCode"] == "OBJECT_IMAGE_BLOCK" for block in blocks)
    assert actions == []
    assert dashboard_context["quickActions"] == []


def test_partner_portal_adapter_widget_preferences_can_be_read_and_updated():
    preferences = getCabinetWidgetPreferences("cabinet-customer-1", MODULE8_CONTEXT)
    updated = updateCabinetWidgetPreferences(
        "cabinet-customer-1",
        {
            "widgetPreferences": [
                {"widgetCode": "digital-house-status", "isVisible": True, "sortOrder": 10},
                {"widgetCode": "estimate-summary", "isVisible": False, "sortOrder": 20},
            ]
        },
        MODULE8_CONTEXT,
    )

    assert preferences["cabinetId"] == "cabinet-customer-1"
    assert preferences["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert any(item["widgetCode"] == "estimate-summary" for item in preferences["widgetPreferences"])
    assert updated["updatedByModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert updated["permissionSourceModuleCode"] == MODULE_03_USERS_ROLES
    assert "estimate-summary" not in updated["recommendedWidgetCodes"]


def test_partner_portal_adapter_object_links_visibility_offer_settings_and_summary():
    links = getCabinetObjectLinks("cabinet-customer-1", MODULE8_CONTEXT)
    visibility = getObjectVisibilityForCabinet("object-1", "cabinet-customer-1", MODULE8_CONTEXT)
    offer = updateObjectOfferSettings(
        "object-1",
        {
            "cabinetId": "cabinet-customer-1",
            "receiveSupplierOffers": True,
            "offerContactPolicy": "after_approval",
        },
        MODULE8_CONTEXT,
    )
    summary = getCabinetSummary(MODULE8_CONTEXT)

    assert links[0]["objectId"] == "object-1"
    assert links[0]["targetModuleCode"] == "MODULE_07_DIGITAL_HOUSE"
    assert visibility["visibilityScope"] == "REGION"
    assert visibility["showExactAddress"] is False
    assert offer["canReceiveOffers"] is True
    assert offer["offerContactPolicy"] == "AFTER_APPROVAL"
    assert summary["linkedObjectCount"] == 1
    assert summary["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert summary["quickActionCount"] == 0
