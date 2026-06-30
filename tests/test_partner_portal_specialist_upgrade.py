from app.models import CabinetUpgradeHistory, CabinetUpgradeRequest, SpecialistToCompanyLink
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_specialist_upgrade import (
    FOUNDER_OWNER_RELATION,
    SPECIALIST_TO_COMPANY_UPGRADE,
    UPGRADE_EVENT_REQUESTED,
    UPGRADE_STATUS_REQUESTED,
    prepare_specialist_to_company_upgrade,
)


FULL_UPGRADE_ACCESS = {
    "userId": "specialist-user",
    "workspaceId": "workspace-specialist",
    "activeRegionCode": "KRASNODAR_KRAI",
    "allowedModuleCodes": [
        "MODULE_01_MATERIAL_HUB",
        "MODULE_04_WORKS_COSTS",
        "MODULE_05_ESTIMATE_ENGINE",
        "MODULE_07_DIGITAL_HOUSE",
        "MODULE_08_PARTNER_PORTAL",
        "MODULE_09_PROCUREMENT",
    ],
    "allowedFeatureCodes": [
        "MATERIALS",
        "WORKS_COSTS",
        "ESTIMATE_ENGINE",
        "COMPANY_OBJECTS",
        "COMPANY_EMPLOYEES",
        "DOCUMENTS",
        "SPECIALIST_OBJECTS",
        "HOUSE_STORAGE",
    ],
    "allowedWidgetCodes": ["atom-map", "estimate-summary", "materials-kpi"],
    "allowedQuickActionCodes": ["DASHBOARD_CONFIGURE"],
}


def test_specialist_upgrade_models_are_module8_entities():
    assert CabinetUpgradeRequest.__tablename__ == "module08_cabinet_upgrade_requests"
    assert CabinetUpgradeHistory.__tablename__ == "module08_cabinet_upgrade_history"
    assert SpecialistToCompanyLink.__tablename__ == "module08_specialist_to_company_links"
    assert CabinetUpgradeRequest.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert CabinetUpgradeHistory.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert SpecialistToCompanyLink.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert "preserve_source_cabinet" in set(CabinetUpgradeRequest.__table__.columns.keys())
    assert "relation_type" in set(SpecialistToCompanyLink.__table__.columns.keys())


def test_prepare_specialist_to_company_upgrade_preserves_specialist_and_creates_company_context():
    plan = prepare_specialist_to_company_upgrade(
        {
            "userId": "specialist-user",
            "workspaceId": "workspace-specialist",
            "activeRegionCode": "KRASNODAR_KRAI",
            "specializationCode": "FOREMAN",
        },
        specialist_cabinet_id="specialist-cabinet-1",
        requested_by_user_id="specialist-user",
        target_company_title="ООО СтройДом",
        organization_id="company-org-1",
        access_context=FULL_UPGRADE_ACCESS,
        reason="Компания выросла из практики специалиста",
    ).to_dict()

    assert plan["request"]["upgradeType"] == SPECIALIST_TO_COMPANY_UPGRADE
    assert plan["request"]["requestStatus"] == UPGRADE_STATUS_REQUESTED
    assert plan["request"]["preserveSourceCabinet"] is True
    assert plan["specialistCabinet"]["cabinetType"] == "SPECIALIST"
    assert plan["specialistCabinet"]["specializationCode"] == "FOREMAN"
    assert plan["constructionCompanyCabinet"]["cabinetType"] == "CONSTRUCTION_COMPANY"
    assert plan["constructionCompanyCabinet"]["organizationId"] == "company-org-1"
    assert plan["link"]["specialistCabinetId"] == "specialist-cabinet-1"
    assert plan["link"]["relationType"] == FOUNDER_OWNER_RELATION
    assert plan["link"]["isActive"] is True


def test_specialist_upgrade_history_records_request_without_replacing_permissions_or_business_data():
    plan = prepare_specialist_to_company_upgrade(
        {"userId": "specialist-user", "workspaceId": "workspace-specialist"},
        specialist_cabinet_id="specialist-cabinet-1",
        access_context=FULL_UPGRADE_ACCESS,
    ).to_dict()
    history = plan["history"][0]

    assert history["eventType"] == UPGRADE_EVENT_REQUESTED
    assert history["newStatus"] == UPGRADE_STATUS_REQUESTED
    assert history["sourceCabinetId"] == "specialist-cabinet-1"
    assert history["targetCabinetId"] == plan["link"]["constructionCompanyCabinetId"]
    assert plan["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert "Permission" not in plan
    assert "Estimate" not in plan
    assert "Procurement" not in plan
