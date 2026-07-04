from app.models import CustomerCabinet
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_customer_cabinet import (
    CUSTOMER_CABINET_BLOCK_CODES,
    CUSTOMER_MAIN_FOCUS,
    build_customer_cabinet_context,
    get_customer_cabinet_template,
)


FULL_CUSTOMER_ACCESS = {
    "userId": "customer-user",
    "workspaceId": "workspace-customer",
    "activeRegionCode": "KRASNODAR_KRAI",
    "allowedModuleCodes": [
        "MODULE_07_DIGITAL_HOUSE",
        "MODULE_05_ESTIMATE_ENGINE",
        "MODULE_06_ESTIMATE_AUDIT",
        "MODULE_09_PROCUREMENT",
        "MODULE_01_MATERIAL_HUB",
        "MODULE_02_KNOWLEDGE_BASE",
        "PARTICIPANT_CABINET_CONTEXT",
        "MODULE_11_ANALYTICS",
    ],
    "allowedFeatureCodes": [
        "CUSTOMER_OBJECTS",
        "ESTIMATE_ENGINE",
        "ESTIMATE_AUDIT",
        "HOUSE_STORAGE",
        "PROCUREMENT_REQUESTS",
        "DOCUMENTS",
        "TECHNOLOGY_KNOWLEDGE",
        "OFFER_SETTINGS",
        "VISIBILITY_SETTINGS",
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


def test_customer_cabinet_model_is_module8_entity():
    columns = set(CustomerCabinet.__table__.columns.keys())

    assert CustomerCabinet.__tablename__ == "module08_customer_cabinets"
    assert CustomerCabinet.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert "active_object_id" in columns
    assert "object_visibility_settings" in columns
    assert "offer_settings" in columns


def test_customer_cabinet_template_has_requested_focus_and_blocks():
    cabinet = get_customer_cabinet_template(
        access_context=FULL_CUSTOMER_ACCESS,
        include_placeholders=True,
    ).to_dict()
    titles = [block["title"] for block in cabinet["blocks"]]
    codes = [block["blockCode"] for block in cabinet["blocks"]]

    assert cabinet["cabinetType"] == "CUSTOMER"
    assert cabinet["mainFocus"] == CUSTOMER_MAIN_FOCUS
    assert codes == list(CUSTOMER_CABINET_BLOCK_CODES)
    assert titles == [
        "Мои объекты",
        "Сметы",
        "Проверка смет",
        "Склад объекта",
        "Закупки",
        "Документы материалов",
        "База технологий",
        "Настройки предложений",
        "Видимость объекта",
        "Аналитика стоимости",
    ]
    assert cabinet["dashboardPreset"]["presetCode"] == "CustomerDashboardPreset"


def test_customer_cabinet_marks_procurement_and_cost_analytics_as_placeholders():
    cabinet = get_customer_cabinet_template(
        access_context=FULL_CUSTOMER_ACCESS,
        include_placeholders=True,
    ).to_dict()
    placeholders = {
        block["blockCode"]
        for block in cabinet["blocks"]
        if block["isPlaceholder"]
    }

    assert "PROCUREMENT_BLOCK" in placeholders
    assert "PRICE_ANALYTICS_BLOCK" in placeholders


def test_customer_cabinet_filters_blocks_through_module3_access_context():
    limited = {
        **FULL_CUSTOMER_ACCESS,
        "allowedModuleCodes": ["MODULE_07_DIGITAL_HOUSE"],
        "allowedFeatureCodes": ["CUSTOMER_OBJECTS", "HOUSE_STORAGE"],
        "allowedWidgetCodes": ["digital-house-status"],
        "allowedQuickActionCodes": [],
    }
    cabinet = get_customer_cabinet_template(access_context=limited).to_dict()
    codes = [block["blockCode"] for block in cabinet["blocks"]]

    assert codes == ["MY_OBJECTS_BLOCK", "OBJECT_STORAGE_BLOCK"]
    assert "ESTIMATES_BLOCK" in cabinet["deniedByAccess"]["blockCodes"]
    assert "PRICE_ANALYTICS_BLOCK" in cabinet["deniedByAccess"]["blockCodes"]


def test_customer_cabinet_context_links_object_without_owning_object_data():
    cabinet = build_customer_cabinet_context(
        {
            "userId": "customer-user",
            "workspaceId": "workspace-customer",
            "activeRegionCode": "KRASNODAR_KRAI",
        },
        access_context=FULL_CUSTOMER_ACCESS,
        active_object_id="house-120",
        active_object_title="Дом 120 м2",
    ).to_dict()

    assert cabinet["activeObjectId"] == "house-120"
    assert cabinet["activeObjectTitle"] == "Дом 120 м2"
    assert cabinet["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert "DigitalHouse" not in cabinet
    assert "Material" not in cabinet
    assert "Estimate" not in cabinet
