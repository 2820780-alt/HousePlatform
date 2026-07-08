from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_active_cabinet_context import (
    get_active_cabinet_context as _build_active_cabinet_context,
)
from app.services.partner_portal_block_catalog import get_blocks_for_cabinet_type
from app.services.partner_portal_dashboard_preferences import (
    apply_cabinet_dashboard_preferences,
    build_default_cabinet_dashboard_preferences,
)
from app.services.partner_portal_dashboard_presets import get_dashboard_preset_for_context
from app.services.partner_portal_object_links import build_cabinet_object_link
from app.services.partner_portal_object_visibility import (
    build_object_offer_settings,
    build_object_visibility_settings,
    get_default_object_offer_settings,
    get_default_object_visibility_settings,
)


MODULE_03_USERS_ROLES = "MODULE_03_USERS_ROLES"


@dataclass(frozen=True)
class PartnerPortalServiceContext:
    userId: str
    roleCode: str | None = None
    workspaceId: str | None = None
    activeRegionCode: str | None = None
    activeCabinetId: str | None = None
    permissions: dict[str, Any] = field(default_factory=dict)
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    permissionSourceModuleCode: str = MODULE_03_USERS_ROLES

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_partner_portal_context(context: Any) -> PartnerPortalServiceContext:
    data = _dict_value(context)
    permissions = _dict_value(data.get("permissions"))
    return PartnerPortalServiceContext(
        userId=_string_or_none(data.get("userId") or data.get("user_id")) or "",
        roleCode=_string_or_none(data.get("roleCode") or data.get("role_code")),
        workspaceId=_string_or_none(data.get("workspaceId") or data.get("workspace_id")),
        activeRegionCode=_string_or_none(data.get("activeRegionCode") or data.get("active_region_code")),
        activeCabinetId=_string_or_none(data.get("activeCabinetId") or data.get("active_cabinet_id")),
        permissions=permissions,
    )


def get_active_cabinet_context(context: Any) -> dict[str, Any]:
    normalized = normalize_partner_portal_context(context)
    raw = _dict_value(context)
    return _active_context_dict(raw, normalized.activeCabinetId)


def switch_active_cabinet(cabinet_id: str, context: Any) -> dict[str, Any]:
    normalized = normalize_partner_portal_context(context)
    raw = _dict_value(context)
    result = _active_context_dict(raw, cabinet_id)
    result["previousActiveCabinetId"] = normalized.activeCabinetId
    result["switchSourceModuleCode"] = MODULE_08_PARTNER_PORTAL
    return result


def get_available_cabinets(context: Any) -> list[dict[str, Any]]:
    return get_active_cabinet_context(context).get("availableCabinets", [])


def get_cabinet_dashboard_context(cabinet_id: str | None, context: Any) -> dict[str, Any]:
    active_context = _active_context_dict(_dict_value(context), cabinet_id)
    preset = get_cabinet_dashboard_preset(cabinet_id, context)
    return {
        "cabinetId": active_context.get("activeCabinetId"),
        "activeCabinetContext": active_context,
        "dashboardPreset": preset,
        "blockCatalog": get_cabinet_block_catalog(cabinet_id, context),
        "quickActions": get_cabinet_quick_actions(cabinet_id, context),
        "widgetPreferences": get_cabinet_widget_preferences(cabinet_id, context),
        "objectLinks": get_cabinet_object_links(cabinet_id, context),
        "summary": get_cabinet_summary(context),
        "sourceModuleCode": MODULE_08_PARTNER_PORTAL,
    }


def get_cabinet_dashboard_preset(cabinet_id: str | None, context: Any) -> dict[str, Any] | None:
    active_context = _active_context_dict(_dict_value(context), cabinet_id)
    return get_dashboard_preset_for_context(
        active_context,
        access_context=_access_context(context),
        include_future=False,
    )


def get_cabinet_block_catalog(cabinet_id: str | None, context: Any) -> list[dict[str, Any]]:
    active_context = _active_context_dict(_dict_value(context), cabinet_id)
    return get_blocks_for_cabinet_type(
        active_context.get("activeCabinetType"),
        business_role=active_context.get("activeBusinessRole"),
        include_future=False,
    )


def get_cabinet_quick_actions(cabinet_id: str | None, context: Any) -> list[dict[str, Any]]:
    """Compatibility hook: cabinet presets never provide fixed quick actions."""
    return []


def get_cabinet_widget_preferences(cabinet_id: str | None, context: Any) -> dict[str, Any]:
    preset = get_cabinet_dashboard_preset(cabinet_id, context)
    if not preset:
        return _empty_preference_state(cabinet_id, context)
    return build_default_cabinet_dashboard_preferences(
        preset["presetCode"],
        access_context=_access_context(context),
        user_id=normalize_partner_portal_context(context).userId,
        workspace_id=normalize_partner_portal_context(context).workspaceId,
        cabinet_id=cabinet_id or normalize_partner_portal_context(context).activeCabinetId,
    ).to_dict()


def update_cabinet_widget_preferences(cabinet_id: str | None, payload: Any, context: Any) -> dict[str, Any]:
    preset = get_cabinet_dashboard_preset(cabinet_id, context)
    if not preset:
        return _empty_preference_state(cabinet_id, context)
    state = get_cabinet_widget_preferences(cabinet_id, context)
    payload_data = _dict_value(payload)
    if "widgetPreferences" in payload_data:
        state["widgetPreferences"] = list(_list_value(payload_data.get("widgetPreferences")))
    if "blockPreferences" in payload_data:
        state["blockPreferences"] = list(_list_value(payload_data.get("blockPreferences")))
    state["quickActions"] = []
    applied = apply_cabinet_dashboard_preferences(
        preset["presetCode"],
        state,
        access_context=_access_context(context),
    )
    applied["updatedByModuleCode"] = MODULE_08_PARTNER_PORTAL
    applied["permissionSourceModuleCode"] = MODULE_03_USERS_ROLES
    return applied


def get_cabinet_object_links(cabinet_id: str | None, context: Any) -> list[dict[str, Any]]:
    raw = _dict_value(context)
    active_cabinet_id = cabinet_id or normalize_partner_portal_context(context).activeCabinetId
    links = _list_value(raw.get("objectLinks") or raw.get("linkedObjects") or raw.get("availableObjects"))
    return [
        build_cabinet_object_link(item, cabinet_id=active_cabinet_id).to_dict()
        for item in links
        if _matches_cabinet(item, active_cabinet_id)
    ]


def get_object_visibility_for_cabinet(object_id: str, cabinet_id: str | None, context: Any) -> dict[str, Any]:
    raw = _dict_value(context)
    visibility_items = _list_value(raw.get("objectVisibilitySettings") or raw.get("visibilitySettings"))
    for item in visibility_items:
        item_data = _dict_value(item)
        if _string_or_none(item_data.get("objectId") or item_data.get("object_id")) == object_id and _matches_cabinet(item, cabinet_id):
            return build_object_visibility_settings(item, cabinet_id=cabinet_id, object_id=object_id).to_dict()
    return get_default_object_visibility_settings(cabinet_id=cabinet_id, object_id=object_id).to_dict()


def update_object_offer_settings(object_id: str, payload: Any, context: Any) -> dict[str, Any]:
    cabinet_id = _string_or_none(_dict_value(payload).get("cabinetId")) or normalize_partner_portal_context(context).activeCabinetId
    return build_object_offer_settings(payload, cabinet_id=cabinet_id, object_id=object_id).to_dict()


def get_cabinet_summary(context: Any) -> dict[str, Any]:
    active_context = get_active_cabinet_context(context)
    preset = get_cabinet_dashboard_preset(active_context.get("activeCabinetId"), context) or {}
    object_links = get_cabinet_object_links(active_context.get("activeCabinetId"), context)
    return {
        "userId": active_context.get("userId"),
        "workspaceId": active_context.get("workspaceId"),
        "activeCabinetId": active_context.get("activeCabinetId"),
        "activeCabinetType": active_context.get("activeCabinetType"),
        "activeRegionCode": active_context.get("activeRegionCode"),
        "recommendedBlockCount": len(preset.get("recommendedBlockCodes", [])),
        "recommendedWidgetCount": len(preset.get("recommendedWidgetCodes", [])),
        "quickActionCount": 0,
        "linkedObjectCount": len(object_links),
        "sourceModuleCode": MODULE_08_PARTNER_PORTAL,
        "permissionSourceModuleCode": MODULE_03_USERS_ROLES,
        "isMock": True,
    }


def getActiveCabinetContext(context: Any) -> dict[str, Any]:
    return get_active_cabinet_context(context)


def switchActiveCabinet(cabinetId: str, context: Any) -> dict[str, Any]:
    return switch_active_cabinet(cabinetId, context)


def getAvailableCabinets(context: Any) -> list[dict[str, Any]]:
    return get_available_cabinets(context)


def getCabinetDashboardContext(cabinetId: str | None, context: Any) -> dict[str, Any]:
    return get_cabinet_dashboard_context(cabinetId, context)


def getCabinetDashboardPreset(cabinetId: str | None, context: Any) -> dict[str, Any] | None:
    return get_cabinet_dashboard_preset(cabinetId, context)


def getCabinetBlockCatalog(cabinetId: str | None, context: Any) -> list[dict[str, Any]]:
    return get_cabinet_block_catalog(cabinetId, context)


def getCabinetQuickActions(cabinetId: str | None, context: Any) -> list[dict[str, Any]]:
    return get_cabinet_quick_actions(cabinetId, context)


def getCabinetWidgetPreferences(cabinetId: str | None, context: Any) -> dict[str, Any]:
    return get_cabinet_widget_preferences(cabinetId, context)


def updateCabinetWidgetPreferences(cabinetId: str | None, payload: Any, context: Any) -> dict[str, Any]:
    return update_cabinet_widget_preferences(cabinetId, payload, context)


def getCabinetObjectLinks(cabinetId: str | None, context: Any) -> list[dict[str, Any]]:
    return get_cabinet_object_links(cabinetId, context)


def getObjectVisibilityForCabinet(objectId: str, cabinetId: str | None, context: Any) -> dict[str, Any]:
    return get_object_visibility_for_cabinet(objectId, cabinetId, context)


def updateObjectOfferSettings(objectId: str, payload: Any, context: Any) -> dict[str, Any]:
    return update_object_offer_settings(objectId, payload, context)


def getCabinetSummary(context: Any) -> dict[str, Any]:
    return get_cabinet_summary(context)


def _active_context_dict(raw_context: dict[str, Any], cabinet_id: str | None) -> dict[str, Any]:
    context = normalize_partner_portal_context(raw_context)
    dto = _build_active_cabinet_context(
        _user_payload(raw_context, context),
        access_context=_access_context(raw_context),
        active_cabinet_id=cabinet_id or context.activeCabinetId,
        active_region_code=context.activeRegionCode,
    )
    return dto.to_dict()


def _user_payload(raw: dict[str, Any], context: PartnerPortalServiceContext) -> dict[str, Any]:
    return {
        **raw,
        "userId": context.userId,
        "roleCode": context.roleCode,
        "workspaceId": context.workspaceId,
        "activeRegionCode": context.activeRegionCode,
        "activeCabinetId": context.activeCabinetId,
        "allowedModuleCodes": _access_context(raw).get("allowedModuleCodes", []),
        "allowedFeatureCodes": _access_context(raw).get("allowedFeatureCodes", []),
    }


def _access_context(context: Any) -> dict[str, Any]:
    data = _dict_value(context)
    permissions = _dict_value(data.get("permissions"))
    return {
        "userId": _string_or_none(data.get("userId") or data.get("user_id")) or "",
        "roleCode": _string_or_none(data.get("roleCode") or data.get("role_code")),
        "workspaceId": _string_or_none(data.get("workspaceId") or data.get("workspace_id")),
        "activeRegionCode": _string_or_none(data.get("activeRegionCode") or data.get("active_region_code")),
        "allowedModuleCodes": _list_strings(data.get("allowedModuleCodes") or permissions.get("allowedModuleCodes")),
        "allowedFeatureCodes": _list_strings(data.get("allowedFeatureCodes") or permissions.get("allowedFeatureCodes")),
        "allowedWidgetCodes": _list_strings(data.get("allowedWidgetCodes") or permissions.get("allowedWidgetCodes")),
        "allowedQuickActionCodes": _list_strings(
            data.get("allowedQuickActionCodes") or permissions.get("allowedQuickActionCodes")
        ),
        "permissions": permissions,
        "sourceModuleCode": MODULE_03_USERS_ROLES,
    }


def _empty_preference_state(cabinet_id: str | None, context: Any) -> dict[str, Any]:
    normalized = normalize_partner_portal_context(context)
    return {
        "presetCode": "",
        "userId": normalized.userId,
        "workspaceId": normalized.workspaceId,
        "cabinetId": cabinet_id or normalized.activeCabinetId,
        "activeRegionCode": normalized.activeRegionCode,
        "blockPreferences": [],
        "widgetPreferences": [],
        "moduleShortcuts": [],
        "quickActions": [],
        "sourceModuleCode": MODULE_08_PARTNER_PORTAL,
        "isMock": True,
    }


def _matches_cabinet(item: Any, cabinet_id: str | None) -> bool:
    if not cabinet_id:
        return True
    data = _dict_value(item)
    item_cabinet_id = _string_or_none(data.get("cabinetId") or data.get("cabinet_id") or data.get("activeCabinetId"))
    return item_cabinet_id in {None, cabinet_id}


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


def _list_value(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _list_strings(value: Any) -> list[str]:
    return [str(item) for item in _list_value(value) if item is not None]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "MODULE_03_USERS_ROLES",
    "PartnerPortalServiceContext",
    "normalize_partner_portal_context",
    "get_active_cabinet_context",
    "switch_active_cabinet",
    "get_available_cabinets",
    "get_cabinet_dashboard_context",
    "get_cabinet_dashboard_preset",
    "get_cabinet_block_catalog",
    "get_cabinet_quick_actions",
    "get_cabinet_widget_preferences",
    "update_cabinet_widget_preferences",
    "get_cabinet_object_links",
    "get_object_visibility_for_cabinet",
    "update_object_offer_settings",
    "get_cabinet_summary",
    "getActiveCabinetContext",
    "switchActiveCabinet",
    "getAvailableCabinets",
    "getCabinetDashboardContext",
    "getCabinetDashboardPreset",
    "getCabinetBlockCatalog",
    "getCabinetQuickActions",
    "getCabinetWidgetPreferences",
    "updateCabinetWidgetPreferences",
    "getCabinetObjectLinks",
    "getObjectVisibilityForCabinet",
    "updateObjectOfferSettings",
    "getCabinetSummary",
]
