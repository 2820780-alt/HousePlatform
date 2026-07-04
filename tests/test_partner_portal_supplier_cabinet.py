from app.models import SupplierCabinet
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_supplier_cabinet import (
    SUPPLIER_CABINET_BLOCK_CODES,
    SUPPLIER_MAIN_FOCUS,
    SUPPLIER_MVP_ROLES,
    build_supplier_cabinet_context,
    get_supplier_cabinet_template,
)


FULL_SUPPLIER_ACCESS = {
    "userId": "supplier-user",
    "workspaceId": "workspace-supplier",
    "activeRegionCode": "KRASNODAR_KRAI",
    "allowedModuleCodes": [
        "MODULE_01_MATERIAL_HUB",
        "MODULE_09_PROCUREMENT",
        "PARTICIPANT_CABINET_CONTEXT",
        "MODULE_11_ANALYTICS",
        "MODULE_10_MARKETPLACE",
    ],
    "allowedFeatureCodes": [
        "SUPPLIER_PRICE_LIST",
        "SUPPLIER_REQUESTS",
        "PARTNER_BRANCHES",
        "PARTNER_CONTACTS",
        "SUPPLY_REGIONS",
        "CABINET_DOCUMENTS",
        "SUPPLIER_ACTIVE_OBJECTS",
        "DEMAND_ANALYTICS",
        "MARKETPLACE_OFFERS",
    ],
    "allowedWidgetCodes": [
        "materials-kpi",
        "source-health",
        "procurement-requests",
        "price-dynamics",
    ],
    "allowedQuickActionCodes": [],
}


def test_supplier_cabinet_model_is_module8_entity():
    columns = set(SupplierCabinet.__table__.columns.keys())

    assert SupplierCabinet.__tablename__ == "module08_supplier_cabinets"
    assert SupplierCabinet.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert "organization_id" in columns
    assert "mvp_roles" in columns
    assert "supply_region_settings" in columns
    assert "branch_settings" in columns
    assert "contact_settings" in columns


def test_supplier_cabinet_template_has_requested_focus_roles_and_blocks():
    cabinet = get_supplier_cabinet_template(
        access_context=FULL_SUPPLIER_ACCESS,
        include_placeholders=True,
    ).to_dict()
    titles = [block["title"] for block in cabinet["blocks"]]
    codes = [block["blockCode"] for block in cabinet["blocks"]]
    roles = [role["title"] for role in cabinet["roles"]]

    assert cabinet["cabinetType"] == "MATERIAL_SUPPLIER"
    assert cabinet["mainFocus"] == SUPPLIER_MAIN_FOCUS
    assert codes == list(SUPPLIER_CABINET_BLOCK_CODES)
    assert roles == [role["title"] for role in SUPPLIER_MVP_ROLES]
    assert roles == ["Директор / владелец", "Администратор", "Менеджер продаж"]
    assert titles == [
        "Прайсы",
        "Заявки",
        "Филиалы",
        "Контакты",
        "Регионы поставки",
        "Документы",
        "Объекты в работе",
        "Аналитика спроса",
        "Витрина",
    ]
    assert cabinet["dashboardPreset"]["presetCode"] == "SupplierDashboardPreset"


def test_supplier_cabinet_marks_requested_placeholders():
    cabinet = get_supplier_cabinet_template(
        access_context=FULL_SUPPLIER_ACCESS,
        include_placeholders=True,
    ).to_dict()
    placeholders = {
        block["blockCode"]
        for block in cabinet["blocks"]
        if block["isPlaceholder"]
    }

    assert "SUPPLIER_PRICE_LIST_BLOCK" in placeholders
    assert "SUPPLIER_REQUESTS_BLOCK" in placeholders
    assert "DEMAND_ANALYTICS_BLOCK" in placeholders
    assert "MARKETPLACE_BLOCK" in placeholders


def test_supplier_cabinet_filters_blocks_through_module3_access_context():
    limited = {
        **FULL_SUPPLIER_ACCESS,
        "allowedModuleCodes": ["PARTICIPANT_CABINET_CONTEXT"],
        "allowedFeatureCodes": ["PARTNER_BRANCHES", "PARTNER_CONTACTS", "SUPPLY_REGIONS"],
        "allowedWidgetCodes": [],
        "allowedQuickActionCodes": [],
    }
    cabinet = get_supplier_cabinet_template(access_context=limited).to_dict()
    codes = [block["blockCode"] for block in cabinet["blocks"]]

    assert codes == ["BRANCHES_BLOCK", "CONTACTS_BLOCK", "SUPPLY_REGIONS_BLOCK"]
    assert "SUPPLIER_PRICE_LIST_BLOCK" in cabinet["deniedByAccess"]["blockCodes"]
    assert "MARKETPLACE_BLOCK" in cabinet["deniedByAccess"]["blockCodes"]


def test_supplier_cabinet_context_links_organization_without_owning_business_data():
    cabinet = build_supplier_cabinet_context(
        {
            "userId": "supplier-user",
            "workspaceId": "workspace-supplier",
            "activeRegionCode": "KRASNODAR_KRAI",
        },
        access_context=FULL_SUPPLIER_ACCESS,
        organization_id="supplier-org-1",
    ).to_dict()

    assert cabinet["organizationId"] == "supplier-org-1"
    assert cabinet["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert "SupplierPrice" not in cabinet
    assert "Procurement" not in cabinet
    assert "MarketplaceOffer" not in cabinet
