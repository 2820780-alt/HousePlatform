from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL


CUSTOMER = "CUSTOMER"
MATERIAL_SUPPLIER = "MATERIAL_SUPPLIER"
CONSTRUCTION_COMPANY = "CONSTRUCTION_COMPANY"
SPECIALIST = "SPECIALIST"


@dataclass(frozen=True)
class CabinetTypeDefinition:
    cabinetType: str
    userTitle: str
    description: str
    primaryGoal: str
    mainFocus: str
    recommendedModules: list[str] = field(default_factory=list)
    recommendedBlocks: list[str] = field(default_factory=list)
    quickActions: list[str] = field(default_factory=list)
    futureBlocks: list[str] = field(default_factory=list)
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    status: str = "ACTIVE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_cabinet_type_definitions() -> tuple[CabinetTypeDefinition, ...]:
    return CABINET_TYPE_DEFINITIONS


def get_cabinet_type_definition(cabinet_type: str | None) -> CabinetTypeDefinition | None:
    normalized = normalize_cabinet_type(cabinet_type)
    if not normalized:
        return None
    return next(
        (
            item
            for item in CABINET_TYPE_DEFINITIONS
            if item.cabinetType == normalized
        ),
        None,
    )


def get_cabinet_type_catalog() -> list[dict[str, Any]]:
    return [item.to_dict() for item in CABINET_TYPE_DEFINITIONS]


def normalize_cabinet_type(cabinet_type: str | None) -> str | None:
    if not cabinet_type:
        return None
    normalized = str(cabinet_type).upper()
    aliases = {
        "CUSTOMER": CUSTOMER,
        "PROJECT": CUSTOMER,
        "CLIENT": CUSTOMER,
        "SUPPLIER": MATERIAL_SUPPLIER,
        "MATERIAL_SUPPLIER": MATERIAL_SUPPLIER,
        "PARTNER_SUPPLIER": MATERIAL_SUPPLIER,
        "CONTRACTOR": CONSTRUCTION_COMPANY,
        "CONSTRUCTION_COMPANY": CONSTRUCTION_COMPANY,
        "BUILDER": CONSTRUCTION_COMPANY,
        "ORGANIZATION": CONSTRUCTION_COMPANY,
        "SPECIALIST": SPECIALIST,
        "ENGINEER": SPECIALIST,
        "ESTIMATOR": SPECIALIST,
        "DESIGNER": SPECIALIST,
    }
    return aliases.get(normalized, normalized)


CABINET_TYPE_DEFINITIONS: tuple[CabinetTypeDefinition, ...] = (
    CabinetTypeDefinition(
        cabinetType=CUSTOMER,
        userTitle="Заказчик",
        description="Кабинет владельца объекта: дом, квартира, сметы, закупки и склад объекта.",
        primaryGoal="Управлять своим объектом и принимать решения по сметам, закупкам и комплектации.",
        mainFocus="Объект, сметы, закупки, склад и ближайшие действия.",
        recommendedModules=[
            "MODULE_07_DIGITAL_HOUSE",
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_06_ESTIMATE_AUDIT",
            "MODULE_09_PROCUREMENT",
            "MODULE_10_MARKETPLACE",
            "MODULE_11_ANALYTICS",
        ],
        recommendedBlocks=[
            "MY_OBJECTS_BLOCK",
            "OBJECT_IMAGE_BLOCK",
            "ESTIMATES_BLOCK",
            "ESTIMATE_AUDIT_BLOCK",
            "OBJECT_STORAGE_BLOCK",
            "PROCUREMENT_BLOCK",
        ],
        quickActions=[],
        futureBlocks=[
            "PRICE_ANALYTICS_BLOCK",
            "VISIBILITY_SETTINGS_BLOCK",
        ],
    ),
    CabinetTypeDefinition(
        cabinetType=MATERIAL_SUPPLIER,
        userTitle="Поставщик материалов",
        description="Кабинет поставщика: прайсы, предложения, заявки и доступность материалов.",
        primaryGoal="Управлять предложениями, ценами и ответами на заявки.",
        mainFocus="Прайсы, заявки, обновление цен и предложения поставщика.",
        recommendedModules=[
            "MODULE_01_MATERIAL_HUB",
            "MODULE_09_PROCUREMENT",
            "MODULE_10_MARKETPLACE",
            "MODULE_11_ANALYTICS",
        ],
        recommendedBlocks=[
            "SUPPLIER_PRICE_LIST_BLOCK",
            "SUPPLIER_REQUESTS_BLOCK",
            "CABINET_DOCUMENTS_BLOCK",
            "CONTACTS_BLOCK",
            "BRANCHES_BLOCK",
            "SUPPLY_REGIONS_BLOCK",
            "SUPPLIER_ACTIVE_OBJECTS_BLOCK",
        ],
        quickActions=[],
        futureBlocks=[
            "DEMAND_ANALYTICS_BLOCK",
            "MARKETPLACE_BLOCK",
            "OFFER_SETTINGS_BLOCK",
            "PRICE_ANALYTICS_BLOCK",
        ],
    ),
    CabinetTypeDefinition(
        cabinetType=CONSTRUCTION_COMPANY,
        userTitle="Строительная компания",
        description="Кабинет подрядчика: работы, расценки, проектные задачи и исполнение.",
        primaryGoal="Вести работы, расценки и участие в проектах без доступа к чужим данным.",
        mainFocus="Работы, проектная активность, сметы в работе и ближайшие задачи.",
        recommendedModules=[
            "MODULE_04_WORKS_COSTS",
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_07_DIGITAL_HOUSE",
            "MODULE_09_PROCUREMENT",
            "MODULE_11_ANALYTICS",
            "MODULE_13_PROJECT_COLLABORATION",
        ],
        recommendedBlocks=[
            "COMPANY_OBJECTS_BLOCK",
            "WORKS_BLOCK",
            "COMPANY_PROJECTS_BLOCK",
            "COMPANY_EMPLOYEES_BLOCK",
            "ESTIMATES_BLOCK",
            "PROCUREMENT_BLOCK",
            "COMPANY_REQUESTS_BLOCK",
            "CABINET_DOCUMENTS_BLOCK",
        ],
        quickActions=[],
        futureBlocks=[
            "CONTRACTS_BLOCK",
            "FINANCE_BLOCK",
            "QUALITY_CONTROL_BLOCK",
            "OFFER_SETTINGS_BLOCK",
            "VISIBILITY_SETTINGS_BLOCK",
        ],
    ),
    CabinetTypeDefinition(
        cabinetType=SPECIALIST,
        userTitle="Специалист",
        description="Кабинет специалиста: экспертиза, сметы, технологии и проектные консультации.",
        primaryGoal="Работать с профессиональными задачами в пределах назначенной роли и workspace.",
        mainFocus="Назначенные задачи, знания, сметы, проверки и аналитика.",
        recommendedModules=[
            "MODULE_01_MATERIAL_HUB",
            "MODULE_02_KNOWLEDGE_BASE",
            "MODULE_04_WORKS_COSTS",
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_06_ESTIMATE_AUDIT",
            "MODULE_07_DIGITAL_HOUSE",
            "MODULE_09_PROCUREMENT",
            "MODULE_11_ANALYTICS",
            "MODULE_13_PROJECT_COLLABORATION",
            "MODULE_19_CONSTRUCTOR_LITE",
        ],
        recommendedBlocks=[
            "SPECIALIST_OBJECTS_BLOCK",
            "TECHNOLOGY_KNOWLEDGE_BLOCK",
            "SPECIALIST_SPECIFICATIONS_BLOCK",
            "WORKS_BLOCK",
            "MATERIALS_BLOCK",
            "ESTIMATE_AUDIT_BLOCK",
            "SPECIALIST_TASKS_BLOCK",
        ],
        quickActions=[],
        futureBlocks=[
            "CABINET_DOCUMENTS_BLOCK",
            "DOCUMENTS_BLOCK",
            "OBJECT_STORAGE_BLOCK",
            "PROCUREMENT_BLOCK",
            "PROCUREMENT_SUPPLIERS_BLOCK",
            "ESTIMATES_BLOCK",
            "ESTIMATE_EXPORT_BLOCK",
            "VOLUMES_BLOCK",
            "AS_BUILT_INFO_BLOCK",
            "PROJECT_DATA_BLOCK",
            "OBJECT_PLAN_BLOCK",
            "PRICE_ANALYTICS_BLOCK",
            "VISIBILITY_SETTINGS_BLOCK",
        ],
    ),
)


__all__ = [
    "CUSTOMER",
    "MATERIAL_SUPPLIER",
    "CONSTRUCTION_COMPANY",
    "SPECIALIST",
    "CabinetTypeDefinition",
    "get_cabinet_type_definitions",
    "get_cabinet_type_definition",
    "get_cabinet_type_catalog",
    "normalize_cabinet_type",
]
