from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.access_context_for_cabinet import AccessContextForCabinet
from app.services.partner_portal_block_catalog import get_cabinet_block_definition
from app.services.partner_portal_dashboard_presets import filter_dashboard_preset_for_access


CONSTRUCTION_COMPANY_CABINET_TYPE = "CONSTRUCTION_COMPANY"
CONSTRUCTION_COMPANY_MAIN_FOCUS = "Проекты / объекты компании"
CONSTRUCTION_COMPANY_DASHBOARD_PRESET = "ConstructionCompanyDashboardPreset"

CONSTRUCTION_COMPANY_ROLES: tuple[dict[str, str], ...] = (
    {"roleCode": "COMPANY_OWNER", "title": "Директор / владелец"},
    {"roleCode": "COMPANY_ADMIN", "title": "Администратор"},
    {"roleCode": "FOREMAN", "title": "Прораб"},
    {"roleCode": "PROCUREMENT_ENGINEER", "title": "Инженер снабжения"},
    {"roleCode": "ESTIMATOR", "title": "Сметчик"},
    {"roleCode": "PROJECT_SALES_MANAGER", "title": "Менеджер проекта / продаж"},
    {"roleCode": "PTO_ENGINEER", "title": "Инженер ПТО"},
    {"roleCode": "STOREKEEPER", "title": "Кладовщик"},
)

CONSTRUCTION_COMPANY_BLOCK_CODES: tuple[str, ...] = (
    "COMPANY_OBJECTS_BLOCK",
    "ESTIMATES_BLOCK",
    "WORKS_BLOCK",
    "COMPANY_EMPLOYEES_BLOCK",
    "PROCUREMENT_BLOCK",
    "COMPANY_REQUESTS_BLOCK",
    "CABINET_DOCUMENTS_BLOCK",
    "CONTRACTS_BLOCK",
    "FINANCE_BLOCK",
    "QUALITY_CONTROL_BLOCK",
)

PLACEHOLDER_BLOCK_CODES = {
    "ESTIMATES_BLOCK",
    "WORKS_BLOCK",
    "PROCUREMENT_BLOCK",
    "COMPANY_REQUESTS_BLOCK",
    "CONTRACTS_BLOCK",
    "FINANCE_BLOCK",
    "QUALITY_CONTROL_BLOCK",
}

CONSTRUCTION_COMPANY_BLOCK_TITLES = {
    "COMPANY_OBJECTS_BLOCK": "Объекты",
    "COMPANY_EMPLOYEES_BLOCK": "Сотрудники",
    "COMPANY_REQUESTS_BLOCK": "Заявки",
}


@dataclass(frozen=True)
class ConstructionCompanyRoleDTO:
    roleCode: str
    title: str
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConstructionCompanyBlockDTO:
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
class ConstructionCompanyCabinetDTO:
    cabinetType: str = CONSTRUCTION_COMPANY_CABINET_TYPE
    title: str = "Кабинет строительной компании"
    mainFocus: str = CONSTRUCTION_COMPANY_MAIN_FOCUS
    presetCode: str = CONSTRUCTION_COMPANY_DASHBOARD_PRESET
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    userId: str | None = None
    workspaceId: str | None = None
    organizationId: str | None = None
    activeRegionCode: str | None = None
    roles: list[ConstructionCompanyRoleDTO] = field(default_factory=list)
    blocks: list[ConstructionCompanyBlockDTO] = field(default_factory=list)
    dashboardPreset: dict[str, Any] = field(default_factory=dict)
    deniedByAccess: dict[str, list[str]] = field(default_factory=dict)
    isMock: bool = True
    compatibilityNote: str = (
        "ConstructionCompanyCabinet belongs to Module 08 as cabinet context. Projects, objects, "
        "estimates, works, procurement, contracts, finance and quality data stay in owning modules."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["roles"] = [item.to_dict() for item in self.roles]
        data["blocks"] = [item.to_dict() for item in self.blocks]
        return data


def get_construction_company_cabinet_template(
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> ConstructionCompanyCabinetDTO:
    access_data = _access_context_dict(access_context)
    preset = filter_dashboard_preset_for_access(
        CONSTRUCTION_COMPANY_DASHBOARD_PRESET,
        access_context=access_context,
        include_future=include_placeholders,
    )
    allowed_block_codes = _allowed_construction_company_blocks(
        access_context=access_context,
        include_placeholders=include_placeholders,
    )
    return ConstructionCompanyCabinetDTO(
        userId=_string_or_none(access_data.get("userId")),
        workspaceId=_string_or_none(access_data.get("workspaceId")),
        activeRegionCode=_string_or_none(access_data.get("activeRegionCode")),
        roles=[
            ConstructionCompanyRoleDTO(**role)
            for role in CONSTRUCTION_COMPANY_ROLES
        ],
        blocks=[
            _construction_company_block(block_code, sort_order=index * 10)
            for index, block_code in enumerate(allowed_block_codes, start=1)
        ],
        dashboardPreset=preset,
        deniedByAccess={
            "blockCodes": [
                block_code
                for block_code in CONSTRUCTION_COMPANY_BLOCK_CODES
                if block_code not in set(allowed_block_codes)
            ],
            "sourceModuleCode": ["MODULE_03_USERS_ROLES"] if access_context is not None else [],
        },
    )


def build_construction_company_cabinet_context(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    organization_id: str | None = None,
    include_placeholders: bool = True,
) -> ConstructionCompanyCabinetDTO:
    user_data = _dict_value(user)
    access_data = _access_context_dict(access_context)
    template = get_construction_company_cabinet_template(
        access_context=access_context,
        include_placeholders=include_placeholders,
    )
    return ConstructionCompanyCabinetDTO(
        userId=_string_or_none(user_data.get("userId") or user_data.get("id") or access_data.get("userId")),
        workspaceId=_string_or_none(user_data.get("workspaceId") or access_data.get("workspaceId")),
        organizationId=organization_id or _string_or_none(user_data.get("organizationId")),
        activeRegionCode=_string_or_none(user_data.get("activeRegionCode") or access_data.get("activeRegionCode")),
        roles=template.roles,
        blocks=template.blocks,
        dashboardPreset=template.dashboardPreset,
        deniedByAccess=template.deniedByAccess,
    )


def getConstructionCompanyCabinetTemplate(
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> ConstructionCompanyCabinetDTO:
    return get_construction_company_cabinet_template(
        access_context=access_context,
        include_placeholders=include_placeholders,
    )


def buildConstructionCompanyCabinetContext(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    organization_id: str | None = None,
    include_placeholders: bool = True,
) -> ConstructionCompanyCabinetDTO:
    return build_construction_company_cabinet_context(
        user,
        access_context=access_context,
        organization_id=organization_id,
        include_placeholders=include_placeholders,
    )


def _allowed_construction_company_blocks(
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None,
    include_placeholders: bool,
) -> list[str]:
    access_data = _access_context_dict(access_context)
    is_filtered = access_context is not None
    allowed_modules = set(_list_strings(access_data.get("allowedModuleCodes")))
    allowed_features = set(_list_strings(access_data.get("allowedFeatureCodes")))
    allowed: list[str] = []
    for block_code in CONSTRUCTION_COMPANY_BLOCK_CODES:
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


def _construction_company_block(block_code: str, *, sort_order: int) -> ConstructionCompanyBlockDTO:
    block = get_cabinet_block_definition(block_code)
    if not block:
        raise ValueError(f"Unknown construction company cabinet block: {block_code}")
    return ConstructionCompanyBlockDTO(
        blockCode=block.blockCode,
        title=CONSTRUCTION_COMPANY_BLOCK_TITLES.get(block.blockCode, block.userTitle),
        sourceModuleCode=block.sourceModuleCode,
        featureCode=block.featureCode,
        isPlaceholder=block.blockCode in PLACEHOLDER_BLOCK_CODES or block.isFuture,
        sortOrder=sort_order,
    )


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
    "CONSTRUCTION_COMPANY_CABINET_TYPE",
    "CONSTRUCTION_COMPANY_MAIN_FOCUS",
    "CONSTRUCTION_COMPANY_DASHBOARD_PRESET",
    "CONSTRUCTION_COMPANY_ROLES",
    "CONSTRUCTION_COMPANY_BLOCK_CODES",
    "ConstructionCompanyRoleDTO",
    "ConstructionCompanyBlockDTO",
    "ConstructionCompanyCabinetDTO",
    "get_construction_company_cabinet_template",
    "build_construction_company_cabinet_context",
    "getConstructionCompanyCabinetTemplate",
    "buildConstructionCompanyCabinetContext",
]
