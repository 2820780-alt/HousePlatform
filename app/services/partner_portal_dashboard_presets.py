from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.access_context_for_cabinet import AccessContextForCabinet
from app.services.partner_portal_block_catalog import get_cabinet_block_definition
from app.services.partner_portal_cabinet_types import (
    CONSTRUCTION_COMPANY,
    CUSTOMER,
    MATERIAL_SUPPLIER,
    SPECIALIST,
    get_cabinet_type_definition,
    normalize_cabinet_type,
)


MODULE_03_USERS_ROLES = "MODULE_03_USERS_ROLES"

TOP_WIDGET_GRID = "TOP_WIDGET_GRID"
ATOM_MAP = "ATOM_MAP"
BOTTOM_WIDGET_GRID = "BOTTOM_WIDGET_GRID"
RIGHT_OPTIONAL = "RIGHT_OPTIONAL"


@dataclass(frozen=True)
class DashboardPresetZone:
    zoneCode: str
    blockCodes: list[str] = field(default_factory=list)
    widgetCodes: list[str] = field(default_factory=list)
    maxItems: int = 6
    isOptional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetDashboardPresetDefinition:
    presetCode: str
    title: str
    cabinetType: str
    businessRole: str
    primaryGoal: str
    mainFocus: str
    recommendedModuleCodes: list[str]
    recommendedBlockCodes: list[str]
    futureBlockCodes: list[str]
    recommendedWidgetCodes: list[str]
    recommendedQuickActionCodes: list[str]
    zones: list[DashboardPresetZone]
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    permissionFilterSourceModuleCode: str = MODULE_03_USERS_ROLES
    status: str = "ACTIVE"
    isSystem: bool = True
    isMock: bool = True
    compatibilityNote: str = (
        "Module 08 recommends cabinet Dashboard presets. Module 03 filters permissions, "
        "WidgetRegistry remains Module 03 / Dashboard layer, and Dashboard only renders data."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["zones"] = [zone.to_dict() for zone in self.zones]
        return data


def get_dashboard_presets(*, include_future: bool = True) -> list[dict[str, Any]]:
    return [
        _preset_to_dict(item, include_future=include_future)
        for item in CABINET_DASHBOARD_PRESETS
    ]


def get_dashboard_preset(
    preset_code: str | None,
    *,
    include_future: bool = True,
) -> dict[str, Any] | None:
    definition = get_dashboard_preset_definition(preset_code)
    return _preset_to_dict(definition, include_future=include_future) if definition else None


def get_dashboard_preset_definition(
    preset_code: str | None,
) -> CabinetDashboardPresetDefinition | None:
    if not preset_code:
        return None
    normalized = str(preset_code)
    return next(
        (
            item
            for item in CABINET_DASHBOARD_PRESETS
            if item.presetCode == normalized
        ),
        None,
    )


def get_dashboard_presets_for_cabinet_type(
    cabinet_type: str | None,
    *,
    business_role: str | None = None,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
) -> list[dict[str, Any]]:
    normalized_type = normalize_cabinet_type(cabinet_type)
    normalized_role = _normalize_role(business_role)
    presets: list[dict[str, Any]] = []
    for preset in CABINET_DASHBOARD_PRESETS:
        if normalized_type and preset.cabinetType != normalized_type:
            continue
        if normalized_role and preset.businessRole != normalized_role:
            continue
        presets.append(
            filter_dashboard_preset_for_access(
                preset,
                access_context=access_context,
                include_future=include_future,
            )
        )
    return presets


def get_dashboard_preset_for_context(
    cabinet_context: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
) -> dict[str, Any] | None:
    data = _dict_value(cabinet_context)
    preset_code = _preset_code_for_context(
        data.get("activeCabinetType") or data.get("cabinetType"),
        data.get("activeBusinessRole") or data.get("businessRole") or data.get("roleCode"),
    )
    if not preset_code:
        return None
    return filter_dashboard_preset_for_access(
        preset_code,
        access_context=access_context,
        include_future=include_future,
    )


def filter_dashboard_preset_for_access(
    preset: CabinetDashboardPresetDefinition | str,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
) -> dict[str, Any]:
    definition = _preset_definition(preset)
    if definition is None:
        raise ValueError(f"Unknown CabinetDashboardPreset: {preset}")

    access_data = _access_context_dict(access_context)
    is_filtered = access_context is not None
    allowed_modules = set(_list_strings(access_data.get("allowedModuleCodes")))
    allowed_features = set(_list_strings(access_data.get("allowedFeatureCodes")))
    allowed_widgets = set(_list_strings(access_data.get("allowedWidgetCodes")))
    allowed_actions = set(_list_strings(access_data.get("allowedQuickActionCodes")))

    denied: dict[str, list[str]] = {
        "moduleCodes": [],
        "blockCodes": [],
        "widgetCodes": [],
        "quickActionCodes": [],
    }
    modules = _filter_codes(
        definition.recommendedModuleCodes,
        allowed_modules,
        is_filtered=is_filtered,
        denied=denied["moduleCodes"],
    )
    blocks = _filter_blocks(
        definition.recommendedBlockCodes,
        allowed_modules=allowed_modules,
        allowed_features=allowed_features,
        is_filtered=is_filtered,
        include_future=include_future,
        denied=denied["blockCodes"],
    )
    future_blocks = _filter_blocks(
        definition.futureBlockCodes,
        allowed_modules=allowed_modules,
        allowed_features=allowed_features,
        is_filtered=is_filtered,
        include_future=include_future,
        denied=denied["blockCodes"],
    )
    widgets = _filter_codes(
        definition.recommendedWidgetCodes,
        allowed_widgets,
        is_filtered=is_filtered,
        denied=denied["widgetCodes"],
    )
    actions = _filter_codes(
        definition.recommendedQuickActionCodes,
        allowed_actions,
        is_filtered=is_filtered,
        denied=denied["quickActionCodes"],
    )
    zones = _filter_zones(
        definition.zones,
        allowed_block_codes=set(blocks + future_blocks),
        allowed_widget_codes=set(widgets),
        include_empty=not is_filtered,
    )

    data = definition.to_dict()
    data.update(
        {
            "recommendedModuleCodes": modules,
            "recommendedBlockCodes": blocks,
            "futureBlockCodes": future_blocks,
            "recommendedWidgetCodes": widgets,
            "recommendedQuickActionCodes": actions,
            "zones": [zone.to_dict() for zone in zones],
            "isPermissionFiltered": is_filtered,
            "permissionFilterSourceModuleCode": MODULE_03_USERS_ROLES,
            "activeRegionCode": access_data.get("activeRegionCode"),
            "deniedByAccess": {
                key: _unique_strings(value)
                for key, value in denied.items()
            },
        }
    )
    return data


def getDashboardPresets(*, include_future: bool = True) -> list[dict[str, Any]]:
    return get_dashboard_presets(include_future=include_future)


def getDashboardPreset(
    presetCode: str | None,
    *,
    include_future: bool = True,
) -> dict[str, Any] | None:
    return get_dashboard_preset(presetCode, include_future=include_future)


def filterDashboardPresetForAccess(
    preset: CabinetDashboardPresetDefinition | str,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_future: bool = False,
) -> dict[str, Any]:
    return filter_dashboard_preset_for_access(
        preset,
        access_context=access_context,
        include_future=include_future,
    )


def _preset_to_dict(
    definition: CabinetDashboardPresetDefinition,
    *,
    include_future: bool,
) -> dict[str, Any]:
    data = definition.to_dict()
    if not include_future:
        future_block_codes = set(definition.futureBlockCodes)
        future_block_codes.update(
            block_code
            for block_code in definition.recommendedBlockCodes
            if _is_future_block(block_code)
        )
        data["recommendedBlockCodes"] = [
            block_code
            for block_code in definition.recommendedBlockCodes
            if block_code not in future_block_codes
        ]
        data["futureBlockCodes"] = []
        data["zones"] = [
            DashboardPresetZone(
                zoneCode=zone.zoneCode,
                blockCodes=[
                    block_code
                    for block_code in zone.blockCodes
                    if block_code not in future_block_codes
                ],
                widgetCodes=zone.widgetCodes,
                maxItems=zone.maxItems,
                isOptional=zone.isOptional,
            ).to_dict()
            for zone in definition.zones
        ]
    return data


def _preset_definition(
    preset: CabinetDashboardPresetDefinition | str,
) -> CabinetDashboardPresetDefinition | None:
    if isinstance(preset, CabinetDashboardPresetDefinition):
        return preset
    return get_dashboard_preset_definition(str(preset))


def _preset_code_for_context(
    cabinet_type: Any,
    business_role: Any,
) -> str | None:
    normalized_type = normalize_cabinet_type(_string_or_none(cabinet_type))
    normalized_role = _normalize_role(_string_or_none(business_role))
    role_presets = {
        "FOREMAN": "ForemanDashboardPreset",
        "PROCUREMENT_ENGINEER": "ProcurementEngineerDashboardPreset",
        "ESTIMATOR": "EstimatorDashboardPreset",
        "PTO_ENGINEER": "PTOEngineerDashboardPreset",
        "DESIGNER": "DesignerDashboardPreset",
        "ENGINEER_DESIGNER": "DesignerDashboardPreset",
    }
    if normalized_role in role_presets:
        return role_presets[normalized_role]
    type_presets = {
        CUSTOMER: "CustomerDashboardPreset",
        MATERIAL_SUPPLIER: "SupplierDashboardPreset",
        CONSTRUCTION_COMPANY: "ConstructionCompanyDashboardPreset",
        SPECIALIST: "SpecialistDashboardPreset",
    }
    return type_presets.get(normalized_type)


def _filter_codes(
    values: list[str],
    allowed_values: set[str],
    *,
    is_filtered: bool,
    denied: list[str],
) -> list[str]:
    if not is_filtered:
        return _unique_strings(values)
    result: list[str] = []
    for value in values:
        if value in allowed_values and value not in result:
            result.append(value)
        else:
            denied.append(value)
    return result


def _filter_blocks(
    block_codes: list[str],
    *,
    allowed_modules: set[str],
    allowed_features: set[str],
    is_filtered: bool,
    include_future: bool,
    denied: list[str],
) -> list[str]:
    result: list[str] = []
    for block_code in block_codes:
        definition = get_cabinet_block_definition(block_code)
        if not definition:
            denied.append(block_code)
            continue
        if definition.isFuture and not include_future:
            denied.append(block_code)
            continue
        if is_filtered and definition.requiresPermission:
            module_code = definition.requiresPermission.moduleCode
            feature_code = definition.requiresPermission.featureCode
            if module_code not in allowed_modules:
                denied.append(block_code)
                continue
            if not _feature_allowed(feature_code, allowed_features):
                denied.append(block_code)
                continue
        if block_code not in result:
            result.append(block_code)
    return result


def _filter_zones(
    zones: list[DashboardPresetZone],
    *,
    allowed_block_codes: set[str],
    allowed_widget_codes: set[str],
    include_empty: bool,
) -> list[DashboardPresetZone]:
    result: list[DashboardPresetZone] = []
    for zone in zones:
        block_codes = [
            block_code
            for block_code in zone.blockCodes
            if block_code in allowed_block_codes
        ]
        widget_codes = [
            widget_code
            for widget_code in zone.widgetCodes
            if widget_code in allowed_widget_codes
        ]
        if not include_empty and not block_codes and not widget_codes:
            continue
        result.append(
            DashboardPresetZone(
                zoneCode=zone.zoneCode,
                blockCodes=block_codes if not include_empty else list(zone.blockCodes),
                widgetCodes=widget_codes if not include_empty else list(zone.widgetCodes),
                maxItems=zone.maxItems,
                isOptional=zone.isOptional,
            )
        )
    return result


def _feature_allowed(feature_code: str | None, allowed_features: set[str]) -> bool:
    if not feature_code:
        return True
    source_feature_codes = {
        item
        for item in allowed_features
        if not item.startswith("DASHBOARD_") and item != "ATOM_MAP_VIEW"
    }
    if not source_feature_codes:
        return True
    return feature_code in source_feature_codes


def _is_future_block(block_code: str) -> bool:
    definition = get_cabinet_block_definition(block_code)
    return bool(definition and definition.isFuture)


def _access_context_dict(
    access_context: AccessContextForCabinet | dict[str, Any] | None,
) -> dict[str, Any]:
    if access_context is None:
        return {}
    if isinstance(access_context, dict):
        return access_context
    return access_context.to_dict()


def _dict_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value if item is not None]


def _unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _normalize_role(role: str | None) -> str | None:
    if not role:
        return None
    normalized = role.upper()
    aliases = {
        "CONTRACTOR": "CONTRACTOR",
        "SUPPLIER": "SUPPLIER",
        "CUSTOMER": "CUSTOMER",
        "ENGINEER": "ENGINEER_DESIGNER",
        "ENGINEER_DESIGNER": "ENGINEER_DESIGNER",
        "DESIGNER": "DESIGNER",
        "ESTIMATOR": "ESTIMATOR",
        "FOREMAN": "FOREMAN",
        "PTO": "PTO_ENGINEER",
        "PTO_ENGINEER": "PTO_ENGINEER",
        "PROCUREMENT": "PROCUREMENT_ENGINEER",
        "PROCUREMENT_ENGINEER": "PROCUREMENT_ENGINEER",
        "SPECIALIST": "SPECIALIST",
    }
    return aliases.get(normalized, normalized)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _cabinet_definition(cabinet_type: str) -> tuple[str, str]:
    definition = get_cabinet_type_definition(cabinet_type)
    if not definition:
        return "", ""
    return definition.primaryGoal, definition.mainFocus


def _preset(
    *,
    presetCode: str,
    title: str,
    cabinetType: str,
    businessRole: str,
    recommendedModuleCodes: list[str],
    recommendedBlockCodes: list[str],
    futureBlockCodes: list[str],
    recommendedWidgetCodes: list[str],
    recommendedQuickActionCodes: list[str],
    zones: list[DashboardPresetZone],
    primaryGoal: str | None = None,
    mainFocus: str | None = None,
) -> CabinetDashboardPresetDefinition:
    default_goal, default_focus = _cabinet_definition(cabinetType)
    return CabinetDashboardPresetDefinition(
        presetCode=presetCode,
        title=title,
        cabinetType=cabinetType,
        businessRole=businessRole,
        primaryGoal=primaryGoal or default_goal,
        mainFocus=mainFocus or default_focus,
        recommendedModuleCodes=_unique_strings(recommendedModuleCodes),
        recommendedBlockCodes=_unique_strings(recommendedBlockCodes),
        futureBlockCodes=_unique_strings(futureBlockCodes),
        recommendedWidgetCodes=_unique_strings(recommendedWidgetCodes),
        recommendedQuickActionCodes=_unique_strings(recommendedQuickActionCodes),
        zones=zones,
    )


CABINET_DASHBOARD_PRESETS: tuple[CabinetDashboardPresetDefinition, ...] = (
    _preset(
        presetCode="CustomerDashboardPreset",
        title="Dashboard заказчика",
        cabinetType=CUSTOMER,
        businessRole="CUSTOMER",
        recommendedModuleCodes=[
            "MODULE_07_DIGITAL_HOUSE",
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_06_ESTIMATE_AUDIT",
            "MODULE_09_PROCUREMENT",
            "MODULE_10_MARKETPLACE",
            "MODULE_11_ANALYTICS",
        ],
        recommendedBlockCodes=[
            "MY_OBJECTS_BLOCK",
            "OBJECT_IMAGE_BLOCK",
            "ESTIMATES_BLOCK",
            "ESTIMATE_AUDIT_BLOCK",
            "OBJECT_STORAGE_BLOCK",
            "PROCUREMENT_BLOCK",
        ],
        futureBlockCodes=["PRICE_ANALYTICS_BLOCK", "VISIBILITY_SETTINGS_BLOCK"],
        recommendedWidgetCodes=[
            "atom-map",
            "digital-house-status",
            "estimate-summary",
            "estimate-audit-risk",
            "procurement-requests",
            "price-dynamics",
        ],
        recommendedQuickActionCodes=[
            "CUSTOMER_OBJECT_CREATE",
            "CUSTOMER_ESTIMATE_REQUEST",
            "CUSTOMER_PROCUREMENT_REQUEST",
            "DASHBOARD_CONFIGURE",
        ],
        zones=[
            DashboardPresetZone(TOP_WIDGET_GRID, widgetCodes=["digital-house-status", "estimate-summary"]),
            DashboardPresetZone(ATOM_MAP, blockCodes=["OBJECT_IMAGE_BLOCK"], widgetCodes=["atom-map"], maxItems=1),
            DashboardPresetZone(BOTTOM_WIDGET_GRID, blockCodes=["MY_OBJECTS_BLOCK", "ESTIMATE_AUDIT_BLOCK", "OBJECT_STORAGE_BLOCK", "PROCUREMENT_BLOCK"]),
            DashboardPresetZone(RIGHT_OPTIONAL, blockCodes=["PRICE_ANALYTICS_BLOCK"], widgetCodes=["price-dynamics"], maxItems=2, isOptional=True),
        ],
    ),
    _preset(
        presetCode="SupplierDashboardPreset",
        title="Dashboard поставщика материалов",
        cabinetType=MATERIAL_SUPPLIER,
        businessRole="SUPPLIER",
        recommendedModuleCodes=[
            "MODULE_01_MATERIAL_HUB",
            "MODULE_08_PARTNER_PORTAL",
            "MODULE_09_PROCUREMENT",
            "MODULE_10_MARKETPLACE",
            "MODULE_11_ANALYTICS",
        ],
        recommendedBlockCodes=[
            "SUPPLIER_PRICE_LIST_BLOCK",
            "SUPPLIER_REQUESTS_BLOCK",
            "CABINET_DOCUMENTS_BLOCK",
            "CONTACTS_BLOCK",
            "BRANCHES_BLOCK",
            "SUPPLY_REGIONS_BLOCK",
            "SUPPLIER_ACTIVE_OBJECTS_BLOCK",
        ],
        futureBlockCodes=["DEMAND_ANALYTICS_BLOCK", "MARKETPLACE_BLOCK", "OFFER_SETTINGS_BLOCK", "PRICE_ANALYTICS_BLOCK"],
        recommendedWidgetCodes=[
            "materials-kpi",
            "source-health",
            "procurement-requests",
            "partner-tender-invites",
            "price-dynamics",
        ],
        recommendedQuickActionCodes=[
            "SUPPLIER_PRICE_UPLOAD",
            "SUPPLIER_PRICE_UPDATE",
            "SUPPLIER_OFFER_CREATE",
            "DASHBOARD_CONFIGURE",
        ],
        zones=[
            DashboardPresetZone(TOP_WIDGET_GRID, blockCodes=["SUPPLIER_PRICE_LIST_BLOCK"], widgetCodes=["materials-kpi", "source-health"]),
            DashboardPresetZone(ATOM_MAP, widgetCodes=["atom-map"], maxItems=1),
            DashboardPresetZone(BOTTOM_WIDGET_GRID, blockCodes=["CABINET_DOCUMENTS_BLOCK", "CONTACTS_BLOCK", "BRANCHES_BLOCK", "SUPPLY_REGIONS_BLOCK", "SUPPLIER_ACTIVE_OBJECTS_BLOCK"]),
            DashboardPresetZone(RIGHT_OPTIONAL, blockCodes=["SUPPLIER_REQUESTS_BLOCK", "DEMAND_ANALYTICS_BLOCK", "MARKETPLACE_BLOCK", "PRICE_ANALYTICS_BLOCK"], widgetCodes=["price-dynamics"], maxItems=2, isOptional=True),
        ],
    ),
    _preset(
        presetCode="ConstructionCompanyDashboardPreset",
        title="Dashboard строительной компании",
        cabinetType=CONSTRUCTION_COMPANY,
        businessRole="CONTRACTOR",
        recommendedModuleCodes=[
            "MODULE_07_DIGITAL_HOUSE",
            "MODULE_04_WORKS_COSTS",
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_09_PROCUREMENT",
            "MODULE_01_MATERIAL_HUB",
            "MODULE_08_PARTNER_PORTAL",
            "MODULE_11_ANALYTICS",
            "MODULE_13_PROJECT_COLLABORATION",
            "MODULE_15_CONTRACTS",
            "MODULE_17_FINANCE_PAYMENTS",
            "MODULE_18_QUALITY_CONTROL",
        ],
        recommendedBlockCodes=[
            "COMPANY_OBJECTS_BLOCK",
            "ESTIMATES_BLOCK",
            "WORKS_BLOCK",
            "COMPANY_EMPLOYEES_BLOCK",
            "PROCUREMENT_BLOCK",
            "COMPANY_REQUESTS_BLOCK",
            "CABINET_DOCUMENTS_BLOCK",
        ],
        futureBlockCodes=[
            "CONTRACTS_BLOCK",
            "FINANCE_BLOCK",
            "QUALITY_CONTROL_BLOCK",
            "OFFER_SETTINGS_BLOCK",
            "VISIBILITY_SETTINGS_BLOCK",
        ],
        recommendedWidgetCodes=[
            "atom-map",
            "estimate-summary",
            "procurement-requests",
            "project-collaboration-activity",
            "price-dynamics",
        ],
        recommendedQuickActionCodes=[
            "CUSTOMER_PROCUREMENT_REQUEST",
            "DASHBOARD_CONFIGURE",
        ],
        zones=[
            DashboardPresetZone(TOP_WIDGET_GRID, blockCodes=["COMPANY_OBJECTS_BLOCK", "WORKS_BLOCK"], widgetCodes=["estimate-summary"]),
            DashboardPresetZone(ATOM_MAP, widgetCodes=["atom-map"], maxItems=1),
            DashboardPresetZone(BOTTOM_WIDGET_GRID, blockCodes=["ESTIMATES_BLOCK", "COMPANY_EMPLOYEES_BLOCK", "PROCUREMENT_BLOCK", "COMPANY_REQUESTS_BLOCK", "CABINET_DOCUMENTS_BLOCK"]),
            DashboardPresetZone(RIGHT_OPTIONAL, blockCodes=["CONTRACTS_BLOCK", "FINANCE_BLOCK", "QUALITY_CONTROL_BLOCK", "PRICE_ANALYTICS_BLOCK"], widgetCodes=["price-dynamics"], maxItems=2, isOptional=True),
        ],
    ),
    _preset(
        presetCode="SpecialistDashboardPreset",
        title="Dashboard специалиста",
        cabinetType=SPECIALIST,
        businessRole="SPECIALIST",
        recommendedModuleCodes=[
            "MODULE_02_KNOWLEDGE_BASE",
            "MODULE_04_WORKS_COSTS",
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_06_ESTIMATE_AUDIT",
            "MODULE_07_DIGITAL_HOUSE",
            "MODULE_08_PARTNER_PORTAL",
            "MODULE_11_ANALYTICS",
            "MODULE_13_PROJECT_COLLABORATION",
        ],
        recommendedBlockCodes=[
            "SPECIALIST_OBJECTS_BLOCK",
            "TECHNOLOGY_KNOWLEDGE_BLOCK",
            "SPECIALIST_SPECIFICATIONS_BLOCK",
            "WORKS_BLOCK",
            "SPECIALIST_TASKS_BLOCK",
            "ESTIMATE_AUDIT_BLOCK",
            "PRICE_ANALYTICS_BLOCK",
        ],
        futureBlockCodes=[
            "DOCUMENTS_BLOCK",
            "MATERIALS_BLOCK",
            "PROCUREMENT_BLOCK",
            "PROCUREMENT_SUPPLIERS_BLOCK",
            "ESTIMATE_EXPORT_BLOCK",
            "VOLUMES_BLOCK",
            "AS_BUILT_INFO_BLOCK",
            "PROJECT_DATA_BLOCK",
            "OBJECT_PLAN_BLOCK",
            "VISIBILITY_SETTINGS_BLOCK",
        ],
        recommendedWidgetCodes=[
            "classification-queue",
            "estimate-audit-risk",
            "price-dynamics",
            "system-alerts",
        ],
        recommendedQuickActionCodes=[
            "ESTIMATE_OPEN",
            "MATERIAL_CLASSIFICATION_FIX",
            "DOCUMENT_LIST_OPEN",
            "DASHBOARD_CONFIGURE",
        ],
        zones=[
            DashboardPresetZone(TOP_WIDGET_GRID, blockCodes=["SPECIALIST_OBJECTS_BLOCK", "WORKS_BLOCK"], widgetCodes=["classification-queue"]),
            DashboardPresetZone(ATOM_MAP, widgetCodes=["atom-map"], maxItems=1),
            DashboardPresetZone(BOTTOM_WIDGET_GRID, blockCodes=["SPECIALIST_SPECIFICATIONS_BLOCK", "SPECIALIST_TASKS_BLOCK", "ESTIMATE_AUDIT_BLOCK"]),
            DashboardPresetZone(RIGHT_OPTIONAL, blockCodes=["PRICE_ANALYTICS_BLOCK"], widgetCodes=["price-dynamics"], maxItems=2, isOptional=True),
        ],
    ),
    _preset(
        presetCode="ForemanDashboardPreset",
        title="Dashboard прораба",
        cabinetType=SPECIALIST,
        businessRole="FOREMAN",
        primaryGoal="Контролировать работы на объекте, склад и ближайшие задачи бригады.",
        mainFocus="Объект, работы, склад, замечания и ближайшие действия.",
        recommendedModuleCodes=[
            "MODULE_07_DIGITAL_HOUSE",
            "MODULE_04_WORKS_COSTS",
            "MODULE_13_PROJECT_COLLABORATION",
        ],
        recommendedBlockCodes=[
            "SPECIALIST_OBJECTS_BLOCK",
            "WORKS_BLOCK",
            "OBJECT_STORAGE_BLOCK",
            "SPECIALIST_TASKS_BLOCK",
        ],
        futureBlockCodes=["VISIBILITY_SETTINGS_BLOCK"],
        recommendedWidgetCodes=[
            "atom-map",
            "digital-house-status",
            "project-collaboration-activity",
            "quality-control-issues",
        ],
        recommendedQuickActionCodes=["DASHBOARD_CONFIGURE"],
        zones=[
            DashboardPresetZone(TOP_WIDGET_GRID, blockCodes=["SPECIALIST_OBJECTS_BLOCK", "WORKS_BLOCK"], widgetCodes=["digital-house-status"]),
            DashboardPresetZone(ATOM_MAP, widgetCodes=["atom-map"], maxItems=1),
            DashboardPresetZone(BOTTOM_WIDGET_GRID, blockCodes=["OBJECT_STORAGE_BLOCK", "SPECIALIST_TASKS_BLOCK"]),
        ],
    ),
    _preset(
        presetCode="ProcurementEngineerDashboardPreset",
        title="Dashboard инженера по закупкам",
        cabinetType=SPECIALIST,
        businessRole="PROCUREMENT_ENGINEER",
        primaryGoal="Вести закупочную потребность, заявки и ценовые сигналы без владения бизнес-данными.",
        mainFocus="Спецификации, закупки и поставщики.",
        recommendedModuleCodes=[
            "MODULE_09_PROCUREMENT",
            "MODULE_01_MATERIAL_HUB",
            "MODULE_10_MARKETPLACE",
            "MODULE_11_ANALYTICS",
            "MODULE_02_KNOWLEDGE_BASE",
            "MODULE_08_PARTNER_PORTAL",
        ],
        recommendedBlockCodes=[
            "SPECIALIST_SPECIFICATIONS_BLOCK",
            "PROCUREMENT_BLOCK",
            "PROCUREMENT_SUPPLIERS_BLOCK",
            "PRICE_ANALYTICS_BLOCK",
        ],
        futureBlockCodes=["CABINET_DOCUMENTS_BLOCK", "OFFER_SETTINGS_BLOCK"],
        recommendedWidgetCodes=[
            "materials-kpi",
            "procurement-requests",
            "marketplace-cart",
            "price-dynamics",
        ],
        recommendedQuickActionCodes=[
            "CUSTOMER_PROCUREMENT_REQUEST",
            "SUPPLIER_PRICE_UPLOAD",
            "DASHBOARD_CONFIGURE",
        ],
        zones=[
            DashboardPresetZone(TOP_WIDGET_GRID, blockCodes=["SPECIALIST_SPECIFICATIONS_BLOCK", "PROCUREMENT_BLOCK"], widgetCodes=["procurement-requests"]),
            DashboardPresetZone(ATOM_MAP, widgetCodes=["atom-map"], maxItems=1),
            DashboardPresetZone(BOTTOM_WIDGET_GRID, blockCodes=["PROCUREMENT_SUPPLIERS_BLOCK", "CABINET_DOCUMENTS_BLOCK"]),
            DashboardPresetZone(RIGHT_OPTIONAL, blockCodes=["PRICE_ANALYTICS_BLOCK"], widgetCodes=["price-dynamics"], maxItems=2, isOptional=True),
        ],
    ),
    _preset(
        presetCode="EstimatorDashboardPreset",
        title="Dashboard сметчика",
        cabinetType=SPECIALIST,
        businessRole="ESTIMATOR",
        primaryGoal="Готовить и проверять сметы, используя данные модулей-владельцев.",
        mainFocus="Сметы, проверки, работы, материалы и ценовая динамика.",
        recommendedModuleCodes=[
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_06_ESTIMATE_AUDIT",
            "MODULE_04_WORKS_COSTS",
            "MODULE_01_MATERIAL_HUB",
            "MODULE_11_ANALYTICS",
        ],
        recommendedBlockCodes=[
            "ESTIMATES_BLOCK",
            "ESTIMATE_AUDIT_BLOCK",
            "MATERIALS_BLOCK",
            "WORKS_BLOCK",
            "ESTIMATE_EXPORT_BLOCK",
            "PRICE_ANALYTICS_BLOCK",
        ],
        futureBlockCodes=["TECHNOLOGY_KNOWLEDGE_BLOCK"],
        recommendedWidgetCodes=[
            "estimate-summary",
            "estimate-audit-risk",
            "materials-kpi",
            "price-dynamics",
        ],
        recommendedQuickActionCodes=[
            "ESTIMATE_OPEN",
            "DOCUMENT_LIST_OPEN",
            "DASHBOARD_CONFIGURE",
        ],
        zones=[
            DashboardPresetZone(TOP_WIDGET_GRID, blockCodes=["ESTIMATES_BLOCK", "ESTIMATE_AUDIT_BLOCK"], widgetCodes=["estimate-summary", "estimate-audit-risk"]),
            DashboardPresetZone(ATOM_MAP, widgetCodes=["atom-map"], maxItems=1),
            DashboardPresetZone(BOTTOM_WIDGET_GRID, blockCodes=["MATERIALS_BLOCK", "WORKS_BLOCK", "ESTIMATE_EXPORT_BLOCK"]),
            DashboardPresetZone(RIGHT_OPTIONAL, blockCodes=["PRICE_ANALYTICS_BLOCK"], widgetCodes=["price-dynamics"], maxItems=2, isOptional=True),
        ],
    ),
    _preset(
        presetCode="PTOEngineerDashboardPreset",
        title="Dashboard инженера ПТО",
        cabinetType=SPECIALIST,
        businessRole="PTO_ENGINEER",
        primaryGoal="Собирать документы, спецификации и проектный контекст без подмены модулей-владельцев.",
        mainFocus="Документы, объемы и исполнительная информация.",
        recommendedModuleCodes=[
            "MODULE_01_MATERIAL_HUB",
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_08_PARTNER_PORTAL",
            "MODULE_13_PROJECT_COLLABORATION",
        ],
        recommendedBlockCodes=[
            "CABINET_DOCUMENTS_BLOCK",
            "VOLUMES_BLOCK",
            "AS_BUILT_INFO_BLOCK",
        ],
        futureBlockCodes=["SPECIALIST_SPECIFICATIONS_BLOCK"],
        recommendedWidgetCodes=[
            "materials-kpi",
            "classification-queue",
            "project-collaboration-activity",
        ],
        recommendedQuickActionCodes=[
            "DOCUMENT_LIST_OPEN",
            "DASHBOARD_CONFIGURE",
        ],
        zones=[
            DashboardPresetZone(TOP_WIDGET_GRID, blockCodes=["CABINET_DOCUMENTS_BLOCK", "VOLUMES_BLOCK"], widgetCodes=["materials-kpi"]),
            DashboardPresetZone(ATOM_MAP, widgetCodes=["atom-map"], maxItems=1),
            DashboardPresetZone(BOTTOM_WIDGET_GRID, blockCodes=["AS_BUILT_INFO_BLOCK", "SPECIALIST_SPECIFICATIONS_BLOCK"]),
        ],
    ),
    _preset(
        presetCode="DesignerDashboardPreset",
        title="Dashboard проектировщика",
        cabinetType=SPECIALIST,
        businessRole="DESIGNER",
        primaryGoal="Работать с образом объекта, технологиями и спецификациями без хранения данных объекта в Module 8.",
        mainFocus="Проектные данные и план объекта.",
        recommendedModuleCodes=[
            "MODULE_19_CONSTRUCTOR_LITE",
            "MODULE_07_DIGITAL_HOUSE",
            "MODULE_02_KNOWLEDGE_BASE",
            "MODULE_08_PARTNER_PORTAL",
        ],
        recommendedBlockCodes=[
            "PROJECT_DATA_BLOCK",
            "OBJECT_PLAN_BLOCK",
        ],
        futureBlockCodes=["OBJECT_IMAGE_BLOCK", "TECHNOLOGY_KNOWLEDGE_BLOCK", "SPECIALIST_SPECIFICATIONS_BLOCK", "CABINET_DOCUMENTS_BLOCK", "VISIBILITY_SETTINGS_BLOCK"],
        recommendedWidgetCodes=[
            "digital-house-status",
            "classification-queue",
            "constructor-changes",
            "materials-kpi",
        ],
        recommendedQuickActionCodes=[
            "DOCUMENT_LIST_OPEN",
            "DASHBOARD_CONFIGURE",
        ],
        zones=[
            DashboardPresetZone(TOP_WIDGET_GRID, blockCodes=["PROJECT_DATA_BLOCK", "OBJECT_PLAN_BLOCK"], widgetCodes=["digital-house-status"]),
            DashboardPresetZone(ATOM_MAP, widgetCodes=["atom-map"], maxItems=1),
            DashboardPresetZone(BOTTOM_WIDGET_GRID, blockCodes=["OBJECT_IMAGE_BLOCK", "TECHNOLOGY_KNOWLEDGE_BLOCK", "SPECIALIST_SPECIFICATIONS_BLOCK", "CABINET_DOCUMENTS_BLOCK"]),
        ],
    ),
)


__all__ = [
    "TOP_WIDGET_GRID",
    "ATOM_MAP",
    "BOTTOM_WIDGET_GRID",
    "RIGHT_OPTIONAL",
    "DashboardPresetZone",
    "CabinetDashboardPresetDefinition",
    "CABINET_DASHBOARD_PRESETS",
    "get_dashboard_presets",
    "get_dashboard_preset",
    "get_dashboard_preset_definition",
    "get_dashboard_presets_for_cabinet_type",
    "get_dashboard_preset_for_context",
    "filter_dashboard_preset_for_access",
    "getDashboardPresets",
    "getDashboardPreset",
    "filterDashboardPresetForAccess",
]
