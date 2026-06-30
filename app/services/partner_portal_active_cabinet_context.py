from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.access_context_for_cabinet import AccessContextForCabinet
from app.services.partner_portal_cabinet_types import (
    get_cabinet_type_definition,
    normalize_cabinet_type,
)


DIGITAL_HOUSE_MODULE_CODE = "MODULE_07_DIGITAL_HOUSE"
COMPACT_SELECTOR = "compact"
FULL_SELECTOR = "selector"
NO_SELECTOR = "none"


@dataclass(frozen=True)
class CabinetOption:
    cabinetId: str
    activeCabinetType: str
    activeCabinetTitle: str
    activeBusinessRole: str | None = None
    workspaceId: str | None = None
    status: str = "ACTIVE"
    isActive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RegionOption:
    activeRegionCode: str
    title: str | None = None
    status: str = "ACTIVE"
    isActive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ObjectOption:
    activeObjectId: str
    activeObjectTitle: str
    objectType: str | None = None
    relationType: str | None = None
    visibilityScope: str | None = None
    sourceModuleCode: str = DIGITAL_HOUSE_MODULE_CODE
    targetModuleCode: str | None = None
    isActive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActiveCabinetContextDTO:
    userId: str
    workspaceId: str | None
    activeCabinetId: str | None
    activeCabinetType: str | None
    activeCabinetTitle: str | None
    activeBusinessRole: str | None
    activeRegionCode: str | None
    activeObjectId: str | None = None
    activeObjectTitle: str | None = None
    availableCabinets: list[CabinetOption] = field(default_factory=list)
    availableRegions: list[RegionOption] = field(default_factory=list)
    availableObjects: list[ObjectOption] = field(default_factory=list)
    allowedModuleCodes: list[str] = field(default_factory=list)
    allowedFeatureCodes: list[str] = field(default_factory=list)
    primaryGoal: str | None = None
    mainFocus: str | None = None
    recommendedModules: list[str] = field(default_factory=list)
    recommendedBlocks: list[str] = field(default_factory=list)
    quickActions: list[str] = field(default_factory=list)
    futureBlocks: list[str] = field(default_factory=list)
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    isMock: bool = True
    cabinetSelectorMode: str = NO_SELECTOR
    objectSelectorMode: str = NO_SELECTOR

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["availableCabinets"] = [item.to_dict() for item in self.availableCabinets]
        data["availableRegions"] = [item.to_dict() for item in self.availableRegions]
        data["availableObjects"] = [item.to_dict() for item in self.availableObjects]
        return data


def build_active_cabinet_context(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    active_cabinet_id: str | None = None,
    active_object_id: str | None = None,
    active_region_code: str | None = None,
) -> ActiveCabinetContextDTO:
    user_data = _dict_value(user)
    access_data = _access_context_dict(access_context)
    user_id = _string_or_none(
        user_data.get("userId")
        or user_data.get("id")
        or access_data.get("userId")
    ) or ""
    allowed_module_codes = _unique_strings(
        access_data.get("allowedModuleCodes")
        or user_data.get("allowedModuleCodes")
        or user_data.get("allowedModules")
        or []
    )
    allowed_feature_codes = _unique_strings(
        access_data.get("allowedFeatureCodes")
        or user_data.get("allowedFeatureCodes")
        or []
    )
    region_code = _string_or_none(
        active_region_code
        or user_data.get("activeRegionCode")
        or access_data.get("activeRegionCode")
        or user_data.get("region_id")
    )

    cabinets = _cabinet_options(user_data)
    selected_cabinet = _select_cabinet(
        cabinets,
        active_cabinet_id
        or _string_or_none(user_data.get("activeCabinetId") or user_data.get("active_cabinet_id")),
    )
    active_cabinet_type = selected_cabinet.activeCabinetType if selected_cabinet else None
    workspace_id = (
        (selected_cabinet.workspaceId if selected_cabinet else None)
        or _string_or_none(user_data.get("workspaceId") or access_data.get("workspaceId"))
    )

    regions = _region_options(user_data, region_code)
    objects = _visible_object_options(
        user_data,
        user_id=user_id,
        workspace_id=workspace_id,
        active_cabinet_id=selected_cabinet.cabinetId if selected_cabinet else None,
        active_cabinet_type=active_cabinet_type,
        active_region_code=region_code,
        allowed_module_codes=allowed_module_codes,
        allowed_feature_codes=allowed_feature_codes,
    )
    selected_object = _select_object(
        objects,
        active_object_id
        or _string_or_none(user_data.get("activeObjectId") or user_data.get("active_object_id")),
    )
    cabinet_type_definition = get_cabinet_type_definition(active_cabinet_type)

    return ActiveCabinetContextDTO(
        userId=user_id,
        workspaceId=workspace_id,
        activeCabinetId=selected_cabinet.cabinetId if selected_cabinet else None,
        activeCabinetType=active_cabinet_type,
        activeCabinetTitle=selected_cabinet.activeCabinetTitle if selected_cabinet else None,
        activeBusinessRole=selected_cabinet.activeBusinessRole if selected_cabinet else None,
        activeRegionCode=region_code,
        activeObjectId=selected_object.activeObjectId if selected_object else None,
        activeObjectTitle=selected_object.activeObjectTitle if selected_object else None,
        availableCabinets=_mark_active_cabinet(cabinets, selected_cabinet),
        availableRegions=_mark_active_region(regions, region_code),
        availableObjects=_mark_active_object(objects, selected_object),
        allowedModuleCodes=allowed_module_codes,
        allowedFeatureCodes=allowed_feature_codes,
        primaryGoal=cabinet_type_definition.primaryGoal if cabinet_type_definition else None,
        mainFocus=cabinet_type_definition.mainFocus if cabinet_type_definition else None,
        recommendedModules=cabinet_type_definition.recommendedModules if cabinet_type_definition else [],
        recommendedBlocks=cabinet_type_definition.recommendedBlocks if cabinet_type_definition else [],
        quickActions=cabinet_type_definition.quickActions if cabinet_type_definition else [],
        futureBlocks=cabinet_type_definition.futureBlocks if cabinet_type_definition else [],
        cabinetSelectorMode=_selector_mode(len(cabinets)),
        objectSelectorMode=_selector_mode(len(objects)),
    )


def get_active_cabinet_context(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    active_cabinet_id: str | None = None,
    active_object_id: str | None = None,
    active_region_code: str | None = None,
) -> ActiveCabinetContextDTO:
    return build_active_cabinet_context(
        user,
        access_context=access_context,
        active_cabinet_id=active_cabinet_id,
        active_object_id=active_object_id,
        active_region_code=active_region_code,
    )


def getActiveCabinetContext(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    active_cabinet_id: str | None = None,
    active_object_id: str | None = None,
    active_region_code: str | None = None,
) -> ActiveCabinetContextDTO:
    return get_active_cabinet_context(
        user,
        access_context=access_context,
        active_cabinet_id=active_cabinet_id,
        active_object_id=active_object_id,
        active_region_code=active_region_code,
    )


def _cabinet_options(data: dict[str, Any]) -> list[CabinetOption]:
    items = (
        _list_value(data.get("availableCabinets"))
        or _list_value(data.get("module8Cabinets"))
        or _list_value(data.get("cabinets"))
    )
    if not items:
        items = _list_value(data.get("workspaces") or data.get("workspaceContexts"))
        return [_cabinet_from_workspace(item, index=index) for index, item in enumerate(items)]
    return [_cabinet_from_value(item, index=index) for index, item in enumerate(items)]


def _cabinet_from_workspace(value: Any, *, index: int) -> CabinetOption:
    data = _dict_value(value)
    workspace_id = _string_or_none(data.get("workspaceId") or data.get("id")) or f"workspace-preview-{index + 1}"
    workspace_type = _string_or_none(data.get("workspaceType") or data.get("type")) or "SPECIALIST"
    role_code = _string_or_none(data.get("roleCode") or data.get("businessRole")) or _role_from_workspace_type(workspace_type)
    cabinet_type = _cabinet_type_from_workspace(workspace_type, role_code)
    title = _string_or_none(data.get("workspaceTitle") or data.get("title")) or "Participant cabinet"
    return CabinetOption(
        cabinetId=f"module8-preview:{workspace_id}:{role_code}",
        activeCabinetType=cabinet_type,
        activeCabinetTitle=title,
        activeBusinessRole=role_code,
        workspaceId=workspace_id,
        status=_string_or_none(data.get("status")) or "PREVIEW",
        isActive=bool(data.get("isActive")) or index == 0,
    )


def _cabinet_from_value(value: Any, *, index: int) -> CabinetOption:
    data = _dict_value(value)
    cabinet_id = _string_or_none(data.get("cabinetId") or data.get("id")) or f"module8-cabinet-preview-{index + 1}"
    cabinet_type = normalize_cabinet_type(
        _string_or_none(data.get("activeCabinetType") or data.get("cabinetType") or data.get("type"))
    ) or "SPECIALIST"
    title = _string_or_none(data.get("activeCabinetTitle") or data.get("title")) or "Participant cabinet"
    return CabinetOption(
        cabinetId=cabinet_id,
        activeCabinetType=cabinet_type,
        activeCabinetTitle=title,
        activeBusinessRole=_string_or_none(data.get("activeBusinessRole") or data.get("businessRole") or data.get("roleCode")),
        workspaceId=_string_or_none(data.get("workspaceId") or data.get("workspace_id")),
        status=_string_or_none(data.get("status")) or "ACTIVE",
        isActive=bool(data.get("isActive")),
    )


def _region_options(data: dict[str, Any], active_region_code: str | None) -> list[RegionOption]:
    items = _list_value(data.get("availableRegions"))
    if not items and active_region_code:
        items = [
            {
                "activeRegionCode": active_region_code,
                "title": data.get("activeRegionName") or active_region_code,
                "isActive": True,
            }
        ]
    regions: list[RegionOption] = []
    for item in items:
        item_data = _dict_value(item)
        code = _string_or_none(item_data.get("activeRegionCode") or item_data.get("regionCode") or item_data.get("code"))
        if not code:
            continue
        regions.append(
            RegionOption(
                activeRegionCode=code,
                title=_string_or_none(item_data.get("title") or item_data.get("name")),
                status=_string_or_none(item_data.get("status")) or "ACTIVE",
                isActive=bool(item_data.get("isActive")) or code == active_region_code,
            )
        )
    return regions


def _visible_object_options(
    data: dict[str, Any],
    *,
    user_id: str,
    workspace_id: str | None,
    active_cabinet_id: str | None,
    active_cabinet_type: str | None,
    active_region_code: str | None,
    allowed_module_codes: list[str],
    allowed_feature_codes: list[str],
) -> list[ObjectOption]:
    items = (
        _list_value(data.get("availableObjects"))
        or _list_value(data.get("module8Objects"))
        or _list_value(data.get("linkedObjects"))
    )
    result: list[ObjectOption] = []
    for item in items:
        item_data = _dict_value(item)
        if not _object_is_allowed(
            item_data,
            user_id=user_id,
            workspace_id=workspace_id,
            active_cabinet_id=active_cabinet_id,
            active_cabinet_type=active_cabinet_type,
            active_region_code=active_region_code,
            allowed_module_codes=allowed_module_codes,
            allowed_feature_codes=allowed_feature_codes,
        ):
            continue
        object_id = _string_or_none(item_data.get("activeObjectId") or item_data.get("objectId") or item_data.get("id"))
        if not object_id:
            continue
        result.append(
            ObjectOption(
                activeObjectId=object_id,
                activeObjectTitle=_string_or_none(item_data.get("activeObjectTitle") or item_data.get("title") or item_data.get("name")) or object_id,
                objectType=_string_or_none(item_data.get("objectType") or item_data.get("type")),
                relationType=_string_or_none(item_data.get("relationType") or item_data.get("relation_type")),
                visibilityScope=_string_or_none(item_data.get("visibilityScope") or item_data.get("visibility_scope")),
                sourceModuleCode=_string_or_none(item_data.get("sourceModuleCode")) or DIGITAL_HOUSE_MODULE_CODE,
                targetModuleCode=_string_or_none(item_data.get("targetModuleCode")),
                isActive=bool(item_data.get("isActive")),
            )
        )
    return result


def _object_is_allowed(
    data: dict[str, Any],
    *,
    user_id: str,
    workspace_id: str | None,
    active_cabinet_id: str | None,
    active_cabinet_type: str | None,
    active_region_code: str | None,
    allowed_module_codes: list[str],
    allowed_feature_codes: list[str],
) -> bool:
    if data.get("isVisible") is False:
        return False
    if str(data.get("status") or "ACTIVE").upper() in {"DISABLED", "ARCHIVED", "DELETED"}:
        return False
    region_code = _string_or_none(data.get("activeRegionCode") or data.get("regionCode") or data.get("region_id"))
    if active_region_code and region_code and region_code != active_region_code:
        return False
    required_module = _string_or_none(data.get("requiredModuleCode") or data.get("sourceModuleCode")) or DIGITAL_HOUSE_MODULE_CODE
    if allowed_module_codes and required_module not in set(allowed_module_codes):
        return False
    required_feature = _string_or_none(data.get("requiredFeatureCode") or data.get("featureCode"))
    if required_feature and allowed_feature_codes and required_feature not in set(allowed_feature_codes):
        return False
    allowed_cabinet_types = set(_list_strings(data.get("allowedCabinetTypes")))
    if allowed_cabinet_types and active_cabinet_type not in allowed_cabinet_types:
        return False

    visibility = str(data.get("visibilityScope") or data.get("visibility_scope") or "WORKSPACE").upper()
    if visibility in {"PUBLIC", "REGION"}:
        return True
    if visibility == "CABINET":
        return _string_or_none(data.get("cabinetId") or data.get("activeCabinetId")) in {None, active_cabinet_id}
    if visibility == "WORKSPACE":
        object_workspace = _string_or_none(data.get("workspaceId") or data.get("workspace_id"))
        return not object_workspace or not workspace_id or object_workspace == workspace_id
    if visibility in {"OWN", "PRIVATE"}:
        owner_id = _string_or_none(data.get("ownerUserId") or data.get("owner_user_id") or data.get("userId"))
        allowed_users = set(_list_strings(data.get("allowedUserIds")))
        return owner_id == user_id or user_id in allowed_users
    return False


def _select_cabinet(cabinets: list[CabinetOption], cabinet_id: str | None) -> CabinetOption | None:
    if not cabinets:
        return None
    if cabinet_id:
        selected = next((item for item in cabinets if item.cabinetId == cabinet_id), None)
        if selected:
            return selected
    return next((item for item in cabinets if item.isActive), None) or cabinets[0]


def _select_object(objects: list[ObjectOption], object_id: str | None) -> ObjectOption | None:
    if not objects:
        return None
    if object_id:
        selected = next((item for item in objects if item.activeObjectId == object_id), None)
        if selected:
            return selected
    return next((item for item in objects if item.isActive), None) or objects[0]


def _mark_active_cabinet(cabinets: list[CabinetOption], active: CabinetOption | None) -> list[CabinetOption]:
    return [
        CabinetOption(
            **{
                **item.to_dict(),
                "isActive": bool(active and item.cabinetId == active.cabinetId),
            }
        )
        for item in cabinets
    ]


def _mark_active_region(regions: list[RegionOption], active_region_code: str | None) -> list[RegionOption]:
    return [
        RegionOption(
            activeRegionCode=item.activeRegionCode,
            title=item.title,
            status=item.status,
            isActive=item.activeRegionCode == active_region_code,
        )
        for item in regions
    ]


def _mark_active_object(objects: list[ObjectOption], active: ObjectOption | None) -> list[ObjectOption]:
    return [
        ObjectOption(
            **{
                **item.to_dict(),
                "isActive": bool(active and item.activeObjectId == active.activeObjectId),
            }
        )
        for item in objects
    ]


def _selector_mode(item_count: int) -> str:
    if item_count <= 0:
        return NO_SELECTOR
    if item_count == 1:
        return COMPACT_SELECTOR
    return FULL_SELECTOR


def _cabinet_type_from_workspace(workspace_type: str, role_code: str | None) -> str:
    return normalize_cabinet_type(role_code or workspace_type) or "SPECIALIST"


def _role_from_workspace_type(workspace_type: str) -> str:
    normalized = workspace_type.upper()
    if normalized in {"SUPPLIER", "CUSTOMER", "CONTRACTOR"}:
        return normalized
    return "SPECIALIST"


def _access_context_dict(access_context: AccessContextForCabinet | dict[str, Any] | None) -> dict[str, Any]:
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
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _list_value(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _list_strings(value: Any) -> list[str]:
    return [str(item) for item in _list_value(value) if item is not None]


def _unique_strings(value: Any) -> list[str]:
    unique: list[str] = []
    for item in _list_strings(value):
        if item not in unique:
            unique.append(item)
    return unique


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "DIGITAL_HOUSE_MODULE_CODE",
    "CabinetOption",
    "RegionOption",
    "ObjectOption",
    "ActiveCabinetContextDTO",
    "build_active_cabinet_context",
    "get_active_cabinet_context",
    "getActiveCabinetContext",
]
