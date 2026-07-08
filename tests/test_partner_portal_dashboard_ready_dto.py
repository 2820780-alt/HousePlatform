from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_dashboard_ready_dto import (
    CABINET_DASHBOARD_CONTEXT,
    buildDashboardReadyCabinetContext,
    build_dashboard_ready_cabinet_context,
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
    },
    "availableCabinets": [
        {
            "cabinetId": "cabinet-customer-1",
            "cabinetType": "CUSTOMER",
            "title": "Кабинет заказчика",
            "businessRole": "CUSTOMER",
            "workspaceId": "workspace-customer-1",
            "isActive": True,
        }
    ],
    "availableObjects": [
        {
            "objectId": "object-1",
            "title": "Дом 120 м2",
            "visibilityScope": "WORKSPACE",
            "workspaceId": "workspace-customer-1",
            "sourceModuleCode": "MODULE_07_DIGITAL_HOUSE",
            "isActive": True,
        }
    ],
}


def test_dashboard_ready_dto_uses_module8_context_without_dashboard_edits():
    dto = build_dashboard_ready_cabinet_context(
        MODULE8_CONTEXT,
        cabinet_id="cabinet-customer-1",
    ).to_dict()

    assert dto["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert dto["featureCode"] == CABINET_DASHBOARD_CONTEXT
    assert dto["activeCabinetId"] == "cabinet-customer-1"
    assert dto["activeCabinetType"] == "CUSTOMER"
    assert dto["activeBusinessRole"] == "CUSTOMER"
    assert dto["activeRegionCode"] == "KRASNODAR_KRAI"
    assert dto["activeObjectId"] == "object-1"
    assert dto["mainFocus"]
    assert "OBJECT_IMAGE_BLOCK" in dto["primaryBlocks"]
    assert "ESTIMATE_AUDIT_BLOCK" in dto["secondaryBlocks"]
    assert dto["quickActions"] == []
    assert any(item["widgetCode"] == "estimate-summary" for item in dto["widgetPreferences"])
    assert "businessPayload" not in dto


def test_dashboard_ready_dto_splits_hidden_locked_future_and_premium_blocks(monkeypatch):
    def fake_dashboard_context(cabinet_id, context):
        return {
            "activeCabinetContext": {
                "activeCabinetId": cabinet_id,
                "activeCabinetType": "CUSTOMER",
                "activeBusinessRole": "CUSTOMER",
                "activeRegionCode": "KRASNODAR_KRAI",
                "activeObjectId": "object-1",
            },
            "dashboardPreset": {
                "mainFocus": "Образ объекта",
                "recommendedBlockCodes": [
                    "OBJECT_IMAGE_BLOCK",
                    "ESTIMATES_BLOCK",
                    "PRICE_ANALYTICS_BLOCK",
                    "PREMIUM_BLOCK",
                    "LOCKED_BLOCK",
                    "HIDDEN_BLOCK",
                ],
                "futureBlockCodes": ["PRICE_ANALYTICS_BLOCK"],
                "deniedByAccess": {"blockCodes": ["LOCKED_BLOCK"]},
                "zones": [
                    {
                        "zoneCode": "TOP_WIDGET_GRID",
                        "blockCodes": ["OBJECT_IMAGE_BLOCK", "HIDDEN_BLOCK", "LOCKED_BLOCK"],
                    },
                    {
                        "zoneCode": "BOTTOM_WIDGET_GRID",
                        "blockCodes": ["ESTIMATES_BLOCK", "PRICE_ANALYTICS_BLOCK", "PREMIUM_BLOCK"],
                    },
                ],
            },
            "widgetPreferences": {
                "blockPreferences": [
                    {"blockCode": "HIDDEN_BLOCK", "isVisible": False},
                ],
                "widgetPreferences": [
                    {"widgetCode": "estimate-summary", "isVisible": True},
                    {"widgetCode": "hidden-widget", "isVisible": False},
                ],
                "moduleShortcuts": [
                    {"shortcutCode": "house", "targetModuleCode": "MODULE_07_DIGITAL_HOUSE", "isVisible": True},
                    {"shortcutCode": "hidden", "targetModuleCode": "MODULE_05_ESTIMATE_ENGINE", "isVisible": False},
                ],
                "quickActions": [
                    {"quickActionCode": "HIDDEN_ACTION", "isVisible": False},
                ],
            },
            "blockCatalog": [
                {"blockCode": "PRICE_ANALYTICS_BLOCK", "isFuture": True},
                {"blockCode": "PREMIUM_BLOCK", "isPremiumFeature": True},
            ],
            "quickActions": [
                {"quickActionCode": "CUSTOMER_OBJECT_CREATE"},
                {"quickActionCode": "HIDDEN_ACTION"},
            ],
        }

    monkeypatch.setattr(
        "app.services.partner_portal_dashboard_ready_dto.get_cabinet_dashboard_context",
        fake_dashboard_context,
    )

    dto = buildDashboardReadyCabinetContext({}, cabinetId="cabinet-customer-1").to_dict()

    assert dto["hiddenBlocks"] == ["HIDDEN_BLOCK"]
    assert dto["lockedBlocks"] == ["LOCKED_BLOCK"]
    assert dto["futureBlocks"] == ["PRICE_ANALYTICS_BLOCK"]
    assert dto["premiumBlocks"] == ["PREMIUM_BLOCK"]
    assert dto["primaryBlocks"] == ["OBJECT_IMAGE_BLOCK"]
    assert dto["secondaryBlocks"] == ["ESTIMATES_BLOCK"]
    assert dto["quickActions"] == []
    assert [item["widgetCode"] for item in dto["widgetPreferences"]] == ["estimate-summary"]
    assert [item["shortcutCode"] for item in dto["availableModuleShortcuts"]] == ["house"]
