from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.access_context_for_cabinet import AccessContextForCabinet
from app.services.partner_portal_block_catalog import get_cabinet_block_definition
from app.services.partner_portal_dashboard_presets import filter_dashboard_preset_for_access


CUSTOMER_CABINET_TYPE = "CUSTOMER"
CUSTOMER_MAIN_FOCUS = "Образ объекта"
CUSTOMER_DASHBOARD_PRESET = "CustomerDashboardPreset"

CUSTOMER_CABINET_BLOCK_CODES: tuple[str, ...] = (
    "MY_OBJECTS_BLOCK",
    "ESTIMATES_BLOCK",
    "ESTIMATE_AUDIT_BLOCK",
    "OBJECT_STORAGE_BLOCK",
    "PROCUREMENT_BLOCK",
    "DOCUMENTS_BLOCK",
    "TECHNOLOGY_KNOWLEDGE_BLOCK",
    "OFFER_SETTINGS_BLOCK",
    "VISIBILITY_SETTINGS_BLOCK",
    "PRICE_ANALYTICS_BLOCK",
)

PLACEHOLDER_BLOCK_CODES = {
    "PROCUREMENT_BLOCK",
    "PRICE_ANALYTICS_BLOCK",
}

CUSTOMER_BLOCK_TITLES = {
    "TECHNOLOGY_KNOWLEDGE_BLOCK": "База технологий",
    "VISIBILITY_SETTINGS_BLOCK": "Видимость объекта",
    "PRICE_ANALYTICS_BLOCK": "Аналитика стоимости",
}


@dataclass(frozen=True)
class CustomerCabinetBlockDTO:
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
class CustomerCabinetDTO:
    cabinetType: str = CUSTOMER_CABINET_TYPE
    title: str = "Кабинет заказчика"
    mainFocus: str = CUSTOMER_MAIN_FOCUS
    presetCode: str = CUSTOMER_DASHBOARD_PRESET
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    userId: str | None = None
    workspaceId: str | None = None
    activeRegionCode: str | None = None
    activeObjectId: str | None = None
    activeObjectTitle: str | None = None
    blocks: list[CustomerCabinetBlockDTO] = field(default_factory=list)
    dashboardPreset: dict[str, Any] = field(default_factory=dict)
    deniedByAccess: dict[str, list[str]] = field(default_factory=dict)
    isMock: bool = True
    compatibilityNote: str = (
        "CustomerCabinet belongs to Module 08 as cabinet context. Object data stays in Module 07; "
        "estimates, procurement, documents, knowledge and analytics stay in their owning modules."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["blocks"] = [item.to_dict() for item in self.blocks]
        return data


def get_customer_cabinet_template(
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> CustomerCabinetDTO:
    access_data = _access_context_dict(access_context)
    preset = filter_dashboard_preset_for_access(
        CUSTOMER_DASHBOARD_PRESET,
        access_context=access_context,
        include_future=include_placeholders,
    )
    allowed_block_codes = _allowed_customer_blocks(
        access_context=access_context,
        include_placeholders=include_placeholders,
    )
    return CustomerCabinetDTO(
        userId=_string_or_none(access_data.get("userId")),
        workspaceId=_string_or_none(access_data.get("workspaceId")),
        activeRegionCode=_string_or_none(access_data.get("activeRegionCode")),
        blocks=[
            _customer_block(block_code, sort_order=index * 10)
            for index, block_code in enumerate(allowed_block_codes, start=1)
        ],
        dashboardPreset=preset,
        deniedByAccess={
            "blockCodes": [
                block_code
                for block_code in CUSTOMER_CABINET_BLOCK_CODES
                if block_code not in set(allowed_block_codes)
            ],
            "sourceModuleCode": ["MODULE_03_USERS_ROLES"] if access_context is not None else [],
        },
    )


def build_customer_cabinet_context(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    active_object_id: str | None = None,
    active_object_title: str | None = None,
    include_placeholders: bool = True,
) -> CustomerCabinetDTO:
    user_data = _dict_value(user)
    access_data = _access_context_dict(access_context)
    template = get_customer_cabinet_template(
        access_context=access_context,
        include_placeholders=include_placeholders,
    )
    return CustomerCabinetDTO(
        userId=_string_or_none(user_data.get("userId") or user_data.get("id") or access_data.get("userId")),
        workspaceId=_string_or_none(user_data.get("workspaceId") or access_data.get("workspaceId")),
        activeRegionCode=_string_or_none(user_data.get("activeRegionCode") or access_data.get("activeRegionCode")),
        activeObjectId=active_object_id or _string_or_none(user_data.get("activeObjectId")),
        activeObjectTitle=active_object_title or _string_or_none(user_data.get("activeObjectTitle")),
        blocks=template.blocks,
        dashboardPreset=template.dashboardPreset,
        deniedByAccess=template.deniedByAccess,
    )


def getCustomerCabinetTemplate(
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    include_placeholders: bool = True,
) -> CustomerCabinetDTO:
    return get_customer_cabinet_template(
        access_context=access_context,
        include_placeholders=include_placeholders,
    )


def buildCustomerCabinetContext(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    active_object_id: str | None = None,
    active_object_title: str | None = None,
    include_placeholders: bool = True,
) -> CustomerCabinetDTO:
    return build_customer_cabinet_context(
        user,
        access_context=access_context,
        active_object_id=active_object_id,
        active_object_title=active_object_title,
        include_placeholders=include_placeholders,
    )


def _allowed_customer_blocks(
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None,
    include_placeholders: bool,
) -> list[str]:
    access_data = _access_context_dict(access_context)
    is_filtered = access_context is not None
    allowed_modules = set(_list_strings(access_data.get("allowedModuleCodes")))
    allowed_features = set(_list_strings(access_data.get("allowedFeatureCodes")))
    allowed: list[str] = []
    for block_code in CUSTOMER_CABINET_BLOCK_CODES:
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


def _customer_block(block_code: str, *, sort_order: int) -> CustomerCabinetBlockDTO:
    block = get_cabinet_block_definition(block_code)
    if not block:
        raise ValueError(f"Unknown customer cabinet block: {block_code}")
    return CustomerCabinetBlockDTO(
        blockCode=block.blockCode,
        title=CUSTOMER_BLOCK_TITLES.get(block.blockCode, block.userTitle),
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
    "CUSTOMER_CABINET_TYPE",
    "CUSTOMER_MAIN_FOCUS",
    "CUSTOMER_DASHBOARD_PRESET",
    "CUSTOMER_CABINET_BLOCK_CODES",
    "CustomerCabinetBlockDTO",
    "CustomerCabinetDTO",
    "get_customer_cabinet_template",
    "build_customer_cabinet_context",
    "getCustomerCabinetTemplate",
    "buildCustomerCabinetContext",
]
