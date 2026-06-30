from app.models import ConstructionCompanyCabinet
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_construction_company_cabinet import (
    CONSTRUCTION_COMPANY_BLOCK_CODES,
    CONSTRUCTION_COMPANY_MAIN_FOCUS,
    CONSTRUCTION_COMPANY_ROLES,
    build_construction_company_cabinet_context,
    get_construction_company_cabinet_template,
)


FULL_COMPANY_ACCESS = {
    "userId": "company-user",
    "workspaceId": "workspace-company",
    "activeRegionCode": "KRASNODAR_KRAI",
    "allowedModuleCodes": [
        "MODULE_07_DIGITAL_HOUSE",
        "MODULE_05_ESTIMATE_ENGINE",
        "MODULE_04_WORKS_COSTS",
        "MODULE_08_PARTNER_PORTAL",
        "MODULE_09_PROCUREMENT",
        "MODULE_01_MATERIAL_HUB",
        "MODULE_15_CONTRACTS",
        "MODULE_17_FINANCE_PAYMENTS",
        "MODULE_18_QUALITY_CONTROL",
    ],
    "allowedFeatureCodes": [
        "COMPANY_OBJECTS",
        "ESTIMATE_ENGINE",
        "WORKS_COSTS",
        "COMPANY_EMPLOYEES",
        "PROCUREMENT_REQUESTS",
        "COMPANY_REQUESTS",
        "CABINET_DOCUMENTS",
        "CONTRACTS_PENDING",
        "FINANCE_BUDGET",
        "QUALITY_CONTROL_ISSUES",
    ],
    "allowedWidgetCodes": [
        "atom-map",
        "estimate-summary",
        "procurement-requests",
        "price-dynamics",
    ],
    "allowedQuickActionCodes": [
        "CUSTOMER_PROCUREMENT_REQUEST",
        "DASHBOARD_CONFIGURE",
    ],
}


def test_construction_company_cabinet_model_is_module8_entity():
    columns = set(ConstructionCompanyCabinet.__table__.columns.keys())

    assert ConstructionCompanyCabinet.__tablename__ == "module08_construction_company_cabinets"
    assert ConstructionCompanyCabinet.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert "organization_id" in columns
    assert "mvp_roles" in columns
    assert "project_visibility_settings" in columns
    assert "employee_settings" in columns
    assert "object_access_settings" in columns


def test_construction_company_cabinet_template_has_requested_focus_roles_and_blocks():
    cabinet = get_construction_company_cabinet_template(
        access_context=FULL_COMPANY_ACCESS,
        include_placeholders=True,
    ).to_dict()
    titles = [block["title"] for block in cabinet["blocks"]]
    codes = [block["blockCode"] for block in cabinet["blocks"]]
    roles = [role["title"] for role in cabinet["roles"]]

    assert cabinet["cabinetType"] == "CONSTRUCTION_COMPANY"
    assert cabinet["mainFocus"] == CONSTRUCTION_COMPANY_MAIN_FOCUS
    assert codes == list(CONSTRUCTION_COMPANY_BLOCK_CODES)
    assert roles == [role["title"] for role in CONSTRUCTION_COMPANY_ROLES]
    assert roles == [
        "Директор / владелец",
        "Администратор",
        "Прораб",
        "Инженер снабжения",
        "Сметчик",
        "Менеджер проекта / продаж",
        "Инженер ПТО",
        "Кладовщик",
    ]
    assert titles == [
        "Объекты",
        "Сметы",
        "Работы",
        "Сотрудники",
        "Закупки",
        "Заявки",
        "Документы",
        "Договоры",
        "Финансы",
        "Контроль качества",
    ]
    assert cabinet["dashboardPreset"]["presetCode"] == "ConstructionCompanyDashboardPreset"


def test_construction_company_cabinet_marks_requested_placeholders():
    cabinet = get_construction_company_cabinet_template(
        access_context=FULL_COMPANY_ACCESS,
        include_placeholders=True,
    ).to_dict()
    placeholders = {
        block["blockCode"]
        for block in cabinet["blocks"]
        if block["isPlaceholder"]
    }

    assert "ESTIMATES_BLOCK" in placeholders
    assert "WORKS_BLOCK" in placeholders
    assert "PROCUREMENT_BLOCK" in placeholders
    assert "COMPANY_REQUESTS_BLOCK" in placeholders
    assert "CONTRACTS_BLOCK" in placeholders
    assert "FINANCE_BLOCK" in placeholders
    assert "QUALITY_CONTROL_BLOCK" in placeholders


def test_construction_company_cabinet_filters_blocks_through_module3_access_context():
    limited = {
        **FULL_COMPANY_ACCESS,
        "allowedModuleCodes": ["MODULE_07_DIGITAL_HOUSE", "MODULE_08_PARTNER_PORTAL", "MODULE_01_MATERIAL_HUB"],
        "allowedFeatureCodes": ["COMPANY_OBJECTS", "COMPANY_EMPLOYEES", "CABINET_DOCUMENTS"],
        "allowedWidgetCodes": [],
        "allowedQuickActionCodes": ["DASHBOARD_CONFIGURE"],
    }
    cabinet = get_construction_company_cabinet_template(access_context=limited).to_dict()
    codes = [block["blockCode"] for block in cabinet["blocks"]]

    assert codes == ["COMPANY_OBJECTS_BLOCK", "COMPANY_EMPLOYEES_BLOCK", "CABINET_DOCUMENTS_BLOCK"]
    assert "ESTIMATES_BLOCK" in cabinet["deniedByAccess"]["blockCodes"]
    assert "FINANCE_BLOCK" in cabinet["deniedByAccess"]["blockCodes"]


def test_construction_company_cabinet_context_links_organization_without_owning_business_data():
    cabinet = build_construction_company_cabinet_context(
        {
            "userId": "company-user",
            "workspaceId": "workspace-company",
            "activeRegionCode": "KRASNODAR_KRAI",
        },
        access_context=FULL_COMPANY_ACCESS,
        organization_id="company-org-1",
    ).to_dict()

    assert cabinet["organizationId"] == "company-org-1"
    assert cabinet["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert "Estimate" not in cabinet
    assert "Procurement" not in cabinet
    assert "Contract" not in cabinet
    assert "Finance" not in cabinet
