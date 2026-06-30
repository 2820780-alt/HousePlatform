from app.models import SpecialistCabinet
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_specialist_cabinet import (
    SPECIALIST_MAIN_FOCUS,
    SPECIALIST_SPECIALIZATIONS,
    build_specialist_cabinet_context,
    get_specialist_cabinet_template,
)


FULL_SPECIALIST_ACCESS = {
    "userId": "specialist-user",
    "workspaceId": "workspace-specialist",
    "activeRegionCode": "KRASNODAR_KRAI",
    "allowedModuleCodes": [
        "MODULE_01_MATERIAL_HUB",
        "MODULE_02_KNOWLEDGE_BASE",
        "MODULE_04_WORKS_COSTS",
        "MODULE_05_ESTIMATE_ENGINE",
        "MODULE_06_ESTIMATE_AUDIT",
        "MODULE_07_DIGITAL_HOUSE",
        "MODULE_08_PARTNER_PORTAL",
        "MODULE_09_PROCUREMENT",
        "MODULE_13_PROJECT_COLLABORATION",
        "MODULE_19_CONSTRUCTOR_LITE",
    ],
    "allowedFeatureCodes": [
        "MATERIALS",
        "DOCUMENTS",
        "CABINET_DOCUMENTS",
        "SPECIALIST_SPECIFICATIONS",
        "WORKS_COSTS",
        "ESTIMATE_ENGINE",
        "ESTIMATE_AUDIT",
        "ESTIMATE_EXPORT",
        "SPECIALIST_OBJECTS",
        "HOUSE_STORAGE",
        "PROCUREMENT_REQUESTS",
        "PROCUREMENT_SUPPLIERS",
        "SPECIALIST_TASKS",
        "WORK_VOLUMES",
        "AS_BUILT_INFO",
        "PROJECT_DATA",
        "OBJECT_PLAN",
    ],
    "allowedWidgetCodes": [
        "atom-map",
        "digital-house-status",
        "estimate-summary",
        "estimate-audit-risk",
        "materials-kpi",
        "project-collaboration-activity",
    ],
    "allowedQuickActionCodes": [
        "ESTIMATE_OPEN",
        "DOCUMENT_LIST_OPEN",
        "DASHBOARD_CONFIGURE",
    ],
}


def test_specialist_cabinet_model_is_module8_entity():
    columns = set(SpecialistCabinet.__table__.columns.keys())

    assert SpecialistCabinet.__tablename__ == "module08_specialist_cabinets"
    assert SpecialistCabinet.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert "specialization_code" in columns
    assert "specialization_presets" in columns
    assert "assigned_object_settings" in columns
    assert "task_context_settings" in columns


def test_specialist_cabinet_template_lists_requested_specializations():
    cabinet = get_specialist_cabinet_template(
        access_context=FULL_SPECIALIST_ACCESS,
        include_placeholders=True,
    ).to_dict()

    assert cabinet["cabinetType"] == "SPECIALIST"
    assert cabinet["mainFocus"] == SPECIALIST_MAIN_FOCUS
    assert [item["title"] for item in cabinet["specializations"]] == [
        item["title"]
        for item in SPECIALIST_SPECIALIZATIONS
    ]
    assert [item["title"] for item in cabinet["specializations"]] == [
        "Прораб",
        "Инженер снабжения",
        "Сметчик",
        "Инженер ПТО",
        "Проектировщик",
    ]


def test_foreman_specialization_uses_objects_works_storage_and_tasks():
    cabinet = get_specialist_cabinet_template(
        specialization_code="FOREMAN",
        access_context=FULL_SPECIALIST_ACCESS,
        include_placeholders=True,
    ).to_dict()

    assert cabinet["presetCode"] == "ForemanDashboardPreset"
    assert [block["title"] for block in cabinet["blocks"]] == [
        "Объекты",
        "Работы",
        "Склад объекта",
        "Задачи",
    ]
    assert "SPECIALIST_TASKS_BLOCK" in {
        block["blockCode"]
        for block in cabinet["blocks"]
        if block["isPlaceholder"]
    }


def test_procurement_engineer_specialization_uses_specifications_procurement_and_suppliers():
    cabinet = get_specialist_cabinet_template(
        specialization_code="PROCUREMENT_ENGINEER",
        access_context=FULL_SPECIALIST_ACCESS,
        include_placeholders=True,
    ).to_dict()

    assert cabinet["presetCode"] == "ProcurementEngineerDashboardPreset"
    assert [block["title"] for block in cabinet["blocks"]] == [
        "Спецификации",
        "Закупки",
        "Поставщики",
    ]


def test_estimator_specialization_uses_estimate_audit_materials_works_and_export():
    cabinet = get_specialist_cabinet_template(
        specialization_code="ESTIMATOR",
        access_context=FULL_SPECIALIST_ACCESS,
        include_placeholders=True,
    ).to_dict()

    assert cabinet["presetCode"] == "EstimatorDashboardPreset"
    assert [block["title"] for block in cabinet["blocks"]] == [
        "Сметы",
        "Проверка смет",
        "Материалы",
        "Работы",
        "Экспорт",
    ]


def test_pto_engineer_specialization_uses_documents_volumes_and_as_built_info():
    cabinet = get_specialist_cabinet_template(
        specialization_code="PTO_ENGINEER",
        access_context=FULL_SPECIALIST_ACCESS,
        include_placeholders=True,
    ).to_dict()

    assert cabinet["presetCode"] == "PTOEngineerDashboardPreset"
    assert [block["title"] for block in cabinet["blocks"]] == [
        "Документы",
        "Объемы",
        "Исполнительная информация",
    ]


def test_designer_specialization_uses_project_data_and_object_plan():
    cabinet = get_specialist_cabinet_template(
        specialization_code="DESIGNER",
        access_context=FULL_SPECIALIST_ACCESS,
        include_placeholders=True,
    ).to_dict()

    assert cabinet["presetCode"] == "DesignerDashboardPreset"
    assert [block["title"] for block in cabinet["blocks"]] == [
        "Проектные данные",
        "План объекта",
    ]


def test_specialist_cabinet_filters_blocks_through_module3_access_context():
    limited = {
        **FULL_SPECIALIST_ACCESS,
        "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_04_WORKS_COSTS"],
        "allowedFeatureCodes": ["MATERIALS", "WORKS_COSTS"],
        "allowedWidgetCodes": [],
        "allowedQuickActionCodes": ["DASHBOARD_CONFIGURE"],
    }
    cabinet = get_specialist_cabinet_template(
        specialization_code="ESTIMATOR",
        access_context=limited,
        include_placeholders=True,
    ).to_dict()

    assert [block["blockCode"] for block in cabinet["blocks"]] == ["MATERIALS_BLOCK", "WORKS_BLOCK"]
    assert "ESTIMATES_BLOCK" in cabinet["deniedByAccess"]["blockCodes"]
    assert "ESTIMATE_EXPORT_BLOCK" in cabinet["deniedByAccess"]["blockCodes"]


def test_specialist_cabinet_context_links_specialization_without_owning_business_data():
    cabinet = build_specialist_cabinet_context(
        {
            "userId": "specialist-user",
            "workspaceId": "workspace-specialist",
            "activeRegionCode": "KRASNODAR_KRAI",
            "specializationCode": "PTO_ENGINEER",
        },
        access_context=FULL_SPECIALIST_ACCESS,
    ).to_dict()

    assert cabinet["specializationCode"] == "PTO_ENGINEER"
    assert cabinet["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert "Estimate" not in cabinet
    assert "Procurement" not in cabinet
    assert "DigitalHouse" not in cabinet
