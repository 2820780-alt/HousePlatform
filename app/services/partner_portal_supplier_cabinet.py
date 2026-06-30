from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.access_context_for_cabinet import AccessContextForCabinet
from app.services.partner_portal_block_catalog import get_cabinet_block_definition
from app.services.partner_portal_dashboard_presets import filter_dashboard_preset_for_access


SUPPLIER_CABINET_TYPE = "MATERIAL_SUPPLIER"
SUPPLIER_MAIN_FOCUS = "Продажи / прайсы / заявки"
SUPPLIER_DASHBOARD_PRESET = "SupplierDashboardPreset"

SUPPLIER_MVP_ROLES: tuple[dict[str, str], ...] = (
    {"roleCode": "SUPPLIER_OWNER", "title": "Директор / владелец"},
    {"roleCode": "SUPPLIER_ADMIN", "title": "Администратор"},
    {"roleCode": "SALES_MANAGER", "title": "Менеджер продаж"},
)

SUPPLIER_CABINET_BLOCK_CODES: tuple[str, ...] = (
    "SUPPLIER_PRICE_LIST_BLOCK",
    "SUPPLIER_REQUESTS_BLOCK",
    "BRANCHES_BLOCK",
    "CONTACTS_BLOCK",
    "SUPPLY_REGIONS_BLOCK",
    "CABINET_DOCUMENTS_BLOCK",
    "SUPPLIER_ACTIVE_OBJECTS_BLOCK",
    "DEMAND_ANALYTICS_BLOCK",
    "MARKETPLACE_BLOCK",
)

PLACEHOLDER_BLOCK_CODES = {
    "SUPPLIER_PRICE_LIST_BLOCK",
    "SUPPLIER_REQUESTS_BLOCK",
    "DEMAND_ANALYTICS_BLOCK",
    "MARKETPLACE_BLOCK",
}

SUPPLIER_BLOCK_TITLES = {
    "SUPPLIER_PRICE_LIST_BLOCK": "Прайсы",
    "SUPPLIER_REQUESTS_BLOCK": "Заявки",
    "DEMAND_ANALYTICS_BLOCK": "Аналитика спроса",
}


@dataclass(frozen=True)
class SupplierCabinetRoleDTO:
    roleCode: str
    title: str
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SupplierCabinetBlockDTO:
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
class SupplierCabinetDTO:
    cabinetType: str = SUPPLIER_CABINET_TYPE
    title: str = "Кабинет поставщика"
    mainFocus: str = SUPPLIER_MAIN_FOCUS
    presetCode: str = SUPPLIER_DASHBOARD_PRESET
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    userId: str | None = None
    workspaceId: str | None = None
    organizationId: str | None = None
    activeRegionCode: str | None = None
    roles: list[SupplierCabinetRoleDTO] = field(default_factory=list)
    blocks: list[SupplierCabinetBlockDTO] = field(default_factory=list)
    dashboardPreset: dict[str, Any] = field(default_factory=dict)
    deniedByAccess: dict[str, list[str]] = field(default_factory=dict)
    isMock: bool = True
    compatibilityNote: str = (
        "SupplierCabinet belongs to Module 08 as cabinet context. Prices stay in Module 1, "
        "requests/procurement in Module 9, marketplace in Module 10, demand analytics in Module 11."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["roles"] = [item.to_dict() for item in self.roles]
        data["blocks"] = [item.to_dict() for item in self.blocks]
        return data


def get_supplier_cabinet_template(
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> SupplierCabinetDTO:
    access_data = _access_context_dict(access_context)
    preset = filter_dashboard_preset_for_access(
        SUPPLIER_DASHBOARD_PRESET,
        access_context=access_context,
        include_future=include_placeholders,
    )
    allowed_block_codes = _allowed_supplier_blocks(
        access_context=access_context,
        include_placeholders=include_placeholders,
    )
    return SupplierCabinetDTO(
        userId=_string_or_none(access_data.get("userId")),
        workspaceId=_string_or_none(access_data.get("workspaceId")),
        activeRegionCode=_string_or_none(access_data.get("activeRegionCode")),
        roles=[
            SupplierCabinetRoleDTO(**role)
            for role in SUPPLIER_MVP_ROLES
        ],
        blocks=[
            _supplier_block(block_code, sort_order=index * 10)
            for index, block_code in enumerate(allowed_block_codes, start=1)
        ],
        dashboardPreset=preset,
        deniedByAccess={
            "blockCodes": [
                block_code
                for block_code in SUPPLIER_CABINET_BLOCK_CODES
                if block_code not in set(allowed_block_codes)
            ],
            "sourceModuleCode": ["MODULE_03_USERS_ROLES"] if access_context is not None else [],
        },
    )


def build_supplier_cabinet_context(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    organization_id: str | None = None,
    include_placeholders: bool = True,
) -> SupplierCabinetDTO:
    user_data = _dict_value(user)
    access_data = _access_context_dict(access_context)
    template = get_supplier_cabinet_template(
        access_context=access_context,
        include_placeholders=include_placeholders,
    )
    return SupplierCabinetDTO(
        userId=_string_or_none(user_data.get("userId") or user_data.get("id") or access_data.get("userId")),
        workspaceId=_string_or_none(user_data.get("workspaceId") or access_data.get("workspaceId")),
        organizationId=organization_id or _string_or_none(user_data.get("organizationId")),
        activeRegionCode=_string_or_none(user_data.get("activeRegionCode") or access_data.get("activeRegionCode")),
        roles=template.roles,
        blocks=template.blocks,
        dashboardPreset=template.dashboardPreset,
        deniedByAccess=template.deniedByAccess,
    )


def getSupplierCabinetTemplate(
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> SupplierCabinetDTO:
    return get_supplier_cabinet_template(
        access_context=access_context,
        include_placeholders=include_placeholders,
    )


def buildSupplierCabinetContext(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    organization_id: str | None = None,
    include_placeholders: bool = True,
) -> SupplierCabinetDTO:
    return build_supplier_cabinet_context(
        user,
        access_context=access_context,
        organization_id=organization_id,
        include_placeholders=include_placeholders,
    )


def _allowed_supplier_blocks(
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None,
    include_placeholders: bool,
) -> list[str]:
    access_data = _access_context_dict(access_context)
    is_filtered = access_context is not None
    allowed_modules = set(_list_strings(access_data.get("allowedModuleCodes")))
    allowed_features = set(_list_strings(access_data.get("allowedFeatureCodes")))
    allowed: list[str] = []
    for block_code in SUPPLIER_CABINET_BLOCK_CODES:
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


def _supplier_block(block_code: str, *, sort_order: int) -> SupplierCabinetBlockDTO:
    block = get_cabinet_block_definition(block_code)
    if not block:
        raise ValueError(f"Unknown supplier cabinet block: {block_code}")
    return SupplierCabinetBlockDTO(
        blockCode=block.blockCode,
        title=SUPPLIER_BLOCK_TITLES.get(block.blockCode, block.userTitle),
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
    "SUPPLIER_CABINET_TYPE",
    "SUPPLIER_MAIN_FOCUS",
    "SUPPLIER_DASHBOARD_PRESET",
    "SUPPLIER_MVP_ROLES",
    "SUPPLIER_CABINET_BLOCK_CODES",
    "SupplierCabinetRoleDTO",
    "SupplierCabinetBlockDTO",
    "SupplierCabinetDTO",
    "get_supplier_cabinet_template",
    "build_supplier_cabinet_context",
    "getSupplierCabinetTemplate",
    "buildSupplierCabinetContext",
]
