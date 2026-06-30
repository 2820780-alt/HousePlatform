from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.access_context_for_cabinet import AccessContextForCabinet
from app.services.partner_portal_block_catalog import get_cabinet_block_definition
from app.services.partner_portal_dashboard_presets import filter_dashboard_preset_for_access


SPECIALIST_CABINET_TYPE = "SPECIALIST"
SPECIALIST_MAIN_FOCUS = "Специализация / рабочий контекст"
SPECIALIST_DASHBOARD_PRESET = "SpecialistDashboardPreset"

SPECIALIST_SPECIALIZATIONS: tuple[dict[str, Any], ...] = (
    {
        "specializationCode": "FOREMAN",
        "title": "Прораб",
        "presetCode": "ForemanDashboardPreset",
        "blockCodes": ["SPECIALIST_OBJECTS_BLOCK", "WORKS_BLOCK", "OBJECT_STORAGE_BLOCK", "SPECIALIST_TASKS_BLOCK"],
    },
    {
        "specializationCode": "PROCUREMENT_ENGINEER",
        "title": "Инженер снабжения",
        "presetCode": "ProcurementEngineerDashboardPreset",
        "blockCodes": ["SPECIALIST_SPECIFICATIONS_BLOCK", "PROCUREMENT_BLOCK", "PROCUREMENT_SUPPLIERS_BLOCK"],
    },
    {
        "specializationCode": "ESTIMATOR",
        "title": "Сметчик",
        "presetCode": "EstimatorDashboardPreset",
        "blockCodes": ["ESTIMATES_BLOCK", "ESTIMATE_AUDIT_BLOCK", "MATERIALS_BLOCK", "WORKS_BLOCK", "ESTIMATE_EXPORT_BLOCK"],
    },
    {
        "specializationCode": "PTO_ENGINEER",
        "title": "Инженер ПТО",
        "presetCode": "PTOEngineerDashboardPreset",
        "blockCodes": ["CABINET_DOCUMENTS_BLOCK", "VOLUMES_BLOCK", "AS_BUILT_INFO_BLOCK"],
    },
    {
        "specializationCode": "DESIGNER",
        "title": "Проектировщик",
        "presetCode": "DesignerDashboardPreset",
        "blockCodes": ["PROJECT_DATA_BLOCK", "OBJECT_PLAN_BLOCK"],
    },
)

PLACEHOLDER_BLOCK_CODES = {
    "SPECIALIST_TASKS_BLOCK",
    "SPECIALIST_SPECIFICATIONS_BLOCK",
    "PROCUREMENT_BLOCK",
    "PROCUREMENT_SUPPLIERS_BLOCK",
    "ESTIMATES_BLOCK",
    "ESTIMATE_EXPORT_BLOCK",
    "VOLUMES_BLOCK",
    "AS_BUILT_INFO_BLOCK",
    "PROJECT_DATA_BLOCK",
    "OBJECT_PLAN_BLOCK",
}


@dataclass(frozen=True)
class SpecialistSpecializationDTO:
    specializationCode: str
    title: str
    presetCode: str
    blockCodes: list[str]
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpecialistCabinetBlockDTO:
    blockCode: str
    title: str
    sourceModuleCode: str
    featureCode: str
    isPlaceholder: bool = False
    isVisible: bool = True
    sortOrder: int = 1000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpecialistCabinetDTO:
    cabinetType: str = SPECIALIST_CABINET_TYPE
    title: str = "Кабинет специалиста"
    mainFocus: str = SPECIALIST_MAIN_FOCUS
    presetCode: str = SPECIALIST_DASHBOARD_PRESET
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    userId: str | None = None
    workspaceId: str | None = None
    specializationCode: str | None = None
    activeRegionCode: str | None = None
    specializations: list[SpecialistSpecializationDTO] = field(default_factory=list)
    blocks: list[SpecialistCabinetBlockDTO] = field(default_factory=list)
    dashboardPreset: dict[str, Any] = field(default_factory=dict)
    deniedByAccess: dict[str, list[str]] = field(default_factory=dict)
    isMock: bool = True
    compatibilityNote: str = (
        "SpecialistCabinet belongs to Module 08 as cabinet context. Objects, works, estimates, "
        "procurement, documents and project data stay in owning modules."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["specializations"] = [item.to_dict() for item in self.specializations]
        data["blocks"] = [item.to_dict() for item in self.blocks]
        return data


def get_specialist_cabinet_template(
    *,
    specialization_code: str | None = None,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> SpecialistCabinetDTO:
    access_data = _access_context_dict(access_context)
    specialization = _specialization_definition(specialization_code)
    preset_code = _specialization_preset_code(specialization)
    block_codes = _specialization_block_codes(specialization)
    allowed_block_codes = _allowed_specialist_blocks(
        block_codes,
        access_context=access_context,
        include_placeholders=include_placeholders,
    )
    preset = filter_dashboard_preset_for_access(
        preset_code,
        access_context=access_context,
        include_future=include_placeholders,
    )
    return SpecialistCabinetDTO(
        userId=_string_or_none(access_data.get("userId")),
        workspaceId=_string_or_none(access_data.get("workspaceId")),
        activeRegionCode=_string_or_none(access_data.get("activeRegionCode")),
        specializationCode=_specialization_code(specialization),
        presetCode=preset_code,
        specializations=[
            SpecialistSpecializationDTO(
                specializationCode=str(item["specializationCode"]),
                title=str(item["title"]),
                presetCode=str(item["presetCode"]),
                blockCodes=list(item["blockCodes"]),
            )
            for item in SPECIALIST_SPECIALIZATIONS
        ],
        blocks=[
            _specialist_block(block_code, sort_order=index * 10)
            for index, block_code in enumerate(allowed_block_codes, start=1)
        ],
        dashboardPreset=preset,
        deniedByAccess={
            "blockCodes": [
                block_code
                for block_code in block_codes
                if block_code not in set(allowed_block_codes)
            ],
            "sourceModuleCode": ["MODULE_03_USERS_ROLES"] if access_context is not None else [],
        },
    )


def build_specialist_cabinet_context(
    user: Any,
    *,
    specialization_code: str | None = None,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> SpecialistCabinetDTO:
    user_data = _dict_value(user)
    access_data = _access_context_dict(access_context)
    specialization = specialization_code or _string_or_none(user_data.get("specializationCode"))
    template = get_specialist_cabinet_template(
        specialization_code=specialization,
        access_context=access_context,
        include_placeholders=include_placeholders,
    )
    return SpecialistCabinetDTO(
        userId=_string_or_none(user_data.get("userId") or user_data.get("id") or access_data.get("userId")),
        workspaceId=_string_or_none(user_data.get("workspaceId") or access_data.get("workspaceId")),
        activeRegionCode=_string_or_none(user_data.get("activeRegionCode") or access_data.get("activeRegionCode")),
        specializationCode=template.specializationCode,
        presetCode=template.presetCode,
        specializations=template.specializations,
        blocks=template.blocks,
        dashboardPreset=template.dashboardPreset,
        deniedByAccess=template.deniedByAccess,
    )


def getSpecialistCabinetTemplate(
    *,
    specialization_code: str | None = None,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> SpecialistCabinetDTO:
    return get_specialist_cabinet_template(
        specialization_code=specialization_code,
        access_context=access_context,
        include_placeholders=include_placeholders,
    )


def buildSpecialistCabinetContext(
    user: Any,
    *,
    specialization_code: str | None = None,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> SpecialistCabinetDTO:
    return build_specialist_cabinet_context(
        user,
        specialization_code=specialization_code,
        access_context=access_context,
        include_placeholders=include_placeholders,
    )


def _allowed_specialist_blocks(
    block_codes: list[str],
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None,
    include_placeholders: bool,
) -> list[str]:
    access_data = _access_context_dict(access_context)
    is_filtered = access_context is not None
    allowed_modules = set(_list_strings(access_data.get("allowedModuleCodes")))
    allowed_features = set(_list_strings(access_data.get("allowedFeatureCodes")))
    allowed: list[str] = []
    for block_code in block_codes:
        if block_code in PLACEHOLDER_BLOCK_CODES and not include_placeholders:
            continue
        block = get_cabinet_block_definition(block_code)
        if not block:
            continue
        if is_filtered and block.requiresPermission:
            if block.requiresPermission.moduleCode not in allowed_modules:
                continue
            if not _feature_allowed(block.requiresPermission.featureCode, allowed_features):
                continue
        allowed.append(block_code)
    return allowed


def _specialist_block(block_code: str, *, sort_order: int) -> SpecialistCabinetBlockDTO:
    block = get_cabinet_block_definition(block_code)
    if not block:
        raise ValueError(f"Unknown specialist cabinet block: {block_code}")
    return SpecialistCabinetBlockDTO(
        blockCode=block.blockCode,
        title=block.userTitle,
        sourceModuleCode=block.sourceModuleCode,
        featureCode=block.featureCode,
        isPlaceholder=block.blockCode in PLACEHOLDER_BLOCK_CODES or block.isFuture,
        sortOrder=sort_order,
    )


def _specialization_definition(specialization_code: str | None) -> dict[str, Any] | None:
    if not specialization_code:
        return None
    normalized = str(specialization_code).upper()
    aliases = {
        "ПРОРАБ": "FOREMAN",
        "SNAB": "PROCUREMENT_ENGINEER",
        "PROCUREMENT": "PROCUREMENT_ENGINEER",
        "СНАБЖЕНИЕ": "PROCUREMENT_ENGINEER",
        "СМЕТЧИК": "ESTIMATOR",
        "PTO": "PTO_ENGINEER",
        "ПТО": "PTO_ENGINEER",
        "ПРОЕКТИРОВЩИК": "DESIGNER",
        "ENGINEER_DESIGNER": "DESIGNER",
    }
    normalized = aliases.get(normalized, normalized)
    return next(
        (
            item
            for item in SPECIALIST_SPECIALIZATIONS
            if item["specializationCode"] == normalized
        ),
        None,
    )


def _specialization_preset_code(specialization: dict[str, Any] | None) -> str:
    if not specialization:
        return SPECIALIST_DASHBOARD_PRESET
    return str(specialization["presetCode"])


def _specialization_code(specialization: dict[str, Any] | None) -> str | None:
    if not specialization:
        return None
    return str(specialization["specializationCode"])


def _specialization_block_codes(specialization: dict[str, Any] | None) -> list[str]:
    if specialization:
        return list(specialization["blockCodes"])
    codes: list[str] = []
    for item in SPECIALIST_SPECIALIZATIONS:
        for block_code in item["blockCodes"]:
            if block_code not in codes:
                codes.append(block_code)
    return codes


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


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "SPECIALIST_CABINET_TYPE",
    "SPECIALIST_MAIN_FOCUS",
    "SPECIALIST_DASHBOARD_PRESET",
    "SPECIALIST_SPECIALIZATIONS",
    "SpecialistSpecializationDTO",
    "SpecialistCabinetBlockDTO",
    "SpecialistCabinetDTO",
    "get_specialist_cabinet_template",
    "build_specialist_cabinet_context",
    "getSpecialistCabinetTemplate",
    "buildSpecialistCabinetContext",
]
