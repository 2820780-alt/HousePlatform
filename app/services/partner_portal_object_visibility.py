from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL


MODULE_03_USERS_ROLES = "MODULE_03_USERS_ROLES"
MODULE_07_DIGITAL_HOUSE = "MODULE_07_DIGITAL_HOUSE"


@dataclass(frozen=True)
class ObjectVisibilitySettingsDTO:
    cabinetId: str | None = None
    objectId: str | None = None
    visibilityScope: str = "PRIVATE"
    visibleToCabinetTypes: list[str] | None = None
    visibleToRoleCodes: list[str] | None = None
    showInSelections: bool = False
    showRegion: bool = True
    showExactAddress: bool = False
    showTechnology: bool = False
    showEstimate: bool = False
    showProcurementNeed: bool = False
    showCustomerContacts: bool = False
    showFinancialData: bool = False
    showPersonalData: bool = False
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    targetModuleCode: str = MODULE_07_DIGITAL_HOUSE
    permissionSourceModuleCode: str = MODULE_03_USERS_ROLES
    privacyMode: str = "PRIVACY_FIRST"
    boundaryNote: str = (
        "Object visibility settings describe what may be shown from object context. "
        "Object data stays in Module 07 and permissions are checked by Module 03."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["visibleToCabinetTypes"] = list(self.visibleToCabinetTypes or [])
        data["visibleToRoleCodes"] = list(self.visibleToRoleCodes or [])
        return data


@dataclass(frozen=True)
class ObjectOfferSettingsDTO:
    cabinetId: str | None = None
    objectId: str | None = None
    targetObjectId: str | None = None
    targetCabinetId: str | None = None
    offerScope: str = "NONE"
    allowedOfferTypes: list[str] | None = None
    canSendOffer: bool = False
    canReceiveOffers: bool = False
    offerVisibilityEnabled: bool = False
    offerContactPolicy: str = "HIDDEN"
    offerSourceModule: str = MODULE_08_PARTNER_PORTAL
    receiveSupplierOffers: bool = False
    receiveConstructionCompanyOffers: bool = False
    receiveSpecialistOffers: bool = False
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    targetModuleCode: str = MODULE_07_DIGITAL_HOUSE
    permissionSourceModuleCode: str = MODULE_03_USERS_ROLES
    privacyMode: str = "OPT_IN"
    boundaryNote: str = (
        "Offer settings only prepare offer visibility and contact policy. Module 08 does not create "
        "deals, commercial proposals, procurement, vitrina project catalog cards or negotiations."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["allowedOfferTypes"] = list(self.allowedOfferTypes or [])
        return data


def get_default_object_visibility_settings(
    *,
    cabinet_id: str | None = None,
    object_id: str | None = None,
) -> ObjectVisibilitySettingsDTO:
    return ObjectVisibilitySettingsDTO(
        cabinetId=cabinet_id,
        objectId=object_id,
    )


def get_default_object_offer_settings(
    *,
    cabinet_id: str | None = None,
    object_id: str | None = None,
) -> ObjectOfferSettingsDTO:
    return ObjectOfferSettingsDTO(
        cabinetId=cabinet_id,
        objectId=object_id,
        targetCabinetId=cabinet_id,
        targetObjectId=object_id,
    )


def build_object_visibility_settings(
    data: Any,
    *,
    cabinet_id: str | None = None,
    object_id: str | None = None,
) -> ObjectVisibilitySettingsDTO:
    payload = _dict_value(data)
    return ObjectVisibilitySettingsDTO(
        cabinetId=_string_or_none(payload.get("cabinetId") or payload.get("cabinet_id") or cabinet_id),
        objectId=_string_or_none(payload.get("objectId") or payload.get("object_id") or object_id),
        visibilityScope=_visibility_scope(payload.get("visibilityScope") or payload.get("visibility_scope")),
        visibleToCabinetTypes=_list_strings(payload.get("visibleToCabinetTypes") or payload.get("visible_to_cabinet_types")),
        visibleToRoleCodes=_list_strings(payload.get("visibleToRoleCodes") or payload.get("visible_to_role_codes")),
        showInSelections=_bool(payload, "showInSelections", "show_in_selections", default=False),
        showRegion=_bool(payload, "showRegion", "show_region", default=True),
        showExactAddress=_bool(payload, "showExactAddress", "show_exact_address", default=False),
        showTechnology=_bool(payload, "showTechnology", "show_technology", default=False),
        showEstimate=_bool(payload, "showEstimate", "show_estimate", default=False),
        showProcurementNeed=_bool(payload, "showProcurementNeed", "show_procurement_need", default=False),
        showCustomerContacts=_bool(payload, "showCustomerContacts", "show_customer_contacts", default=False),
        showFinancialData=_bool(payload, "showFinancialData", "show_financial_data", default=False),
        showPersonalData=_bool(payload, "showPersonalData", "show_personal_data", default=False),
    )


def build_object_offer_settings(
    data: Any,
    *,
    cabinet_id: str | None = None,
    object_id: str | None = None,
) -> ObjectOfferSettingsDTO:
    payload = _dict_value(data)
    receive_supplier = _bool(payload, "receiveSupplierOffers", "receive_supplier_offers", default=False)
    receive_company = _bool(
        payload,
        "receiveConstructionCompanyOffers",
        "receive_construction_company_offers",
        default=False,
    )
    receive_specialist = _bool(payload, "receiveSpecialistOffers", "receive_specialist_offers", default=False)
    allowed_offer_types = _offer_types(
        payload.get("allowedOfferTypes") or payload.get("allowed_offer_types"),
        receive_supplier=receive_supplier,
        receive_company=receive_company,
        receive_specialist=receive_specialist,
    )
    can_receive_offers = _bool(
        payload,
        "canReceiveOffers",
        "can_receive_offers",
        default=bool(allowed_offer_types),
    )
    offer_visibility_enabled = _bool(
        payload,
        "offerVisibilityEnabled",
        "offer_visibility_enabled",
        default=can_receive_offers,
    )
    return ObjectOfferSettingsDTO(
        cabinetId=_string_or_none(payload.get("cabinetId") or payload.get("cabinet_id") or cabinet_id),
        objectId=_string_or_none(payload.get("objectId") or payload.get("object_id") or object_id),
        targetObjectId=_string_or_none(
            payload.get("targetObjectId")
            or payload.get("target_object_id")
            or payload.get("objectId")
            or payload.get("object_id")
            or object_id
        ),
        targetCabinetId=_string_or_none(
            payload.get("targetCabinetId")
            or payload.get("target_cabinet_id")
            or payload.get("cabinetId")
            or payload.get("cabinet_id")
            or cabinet_id
        ),
        offerScope=_offer_scope(payload.get("offerScope") or payload.get("offer_scope"), allowed_offer_types),
        allowedOfferTypes=allowed_offer_types,
        canSendOffer=_bool(payload, "canSendOffer", "can_send_offer", default=False),
        canReceiveOffers=can_receive_offers,
        offerVisibilityEnabled=offer_visibility_enabled,
        offerContactPolicy=_offer_contact_policy(payload.get("offerContactPolicy") or payload.get("offer_contact_policy")),
        offerSourceModule=_string_or_none(payload.get("offerSourceModule") or payload.get("offer_source_module"))
        or MODULE_08_PARTNER_PORTAL,
        receiveSupplierOffers=receive_supplier,
        receiveConstructionCompanyOffers=receive_company,
        receiveSpecialistOffers=receive_specialist,
    )


def getDefaultObjectVisibilitySettings(
    *,
    cabinet_id: str | None = None,
    object_id: str | None = None,
) -> ObjectVisibilitySettingsDTO:
    return get_default_object_visibility_settings(cabinet_id=cabinet_id, object_id=object_id)


def getDefaultObjectOfferSettings(
    *,
    cabinet_id: str | None = None,
    object_id: str | None = None,
) -> ObjectOfferSettingsDTO:
    return get_default_object_offer_settings(cabinet_id=cabinet_id, object_id=object_id)


def buildObjectVisibilitySettings(
    data: Any,
    *,
    cabinet_id: str | None = None,
    object_id: str | None = None,
) -> ObjectVisibilitySettingsDTO:
    return build_object_visibility_settings(data, cabinet_id=cabinet_id, object_id=object_id)


def buildObjectOfferSettings(
    data: Any,
    *,
    cabinet_id: str | None = None,
    object_id: str | None = None,
) -> ObjectOfferSettingsDTO:
    return build_object_offer_settings(data, cabinet_id=cabinet_id, object_id=object_id)


def _offer_types(
    values: Any,
    *,
    receive_supplier: bool,
    receive_company: bool,
    receive_specialist: bool,
) -> list[str]:
    result = _list_strings(values)
    if receive_supplier and "SUPPLIER" not in result:
        result.append("SUPPLIER")
    if receive_company and "CONSTRUCTION_COMPANY" not in result:
        result.append("CONSTRUCTION_COMPANY")
    if receive_specialist and "SPECIALIST" not in result:
        result.append("SPECIALIST")
    return result


def _offer_scope(value: Any, allowed_offer_types: list[str]) -> str:
    if not allowed_offer_types:
        return "NONE"
    if value is None:
        return "SELECTED_TYPES"
    normalized = str(value).upper()
    allowed = {"NONE", "SELECTED_TYPES", "ALL_ALLOWED"}
    return normalized if normalized in allowed else "SELECTED_TYPES"


def _visibility_scope(value: Any) -> str:
    if value is None:
        return "PRIVATE"
    normalized = str(value).upper()
    allowed = {"PRIVATE", "LIMITED", "WORKSPACE", "REGION", "PUBLIC"}
    return normalized if normalized in allowed else "PRIVATE"


def _offer_contact_policy(value: Any) -> str:
    if value is None:
        return "HIDDEN"
    normalized = str(value).upper()
    allowed = {"HIDDEN", "PLATFORM_RELAY", "AFTER_APPROVAL", "DIRECT"}
    return normalized if normalized in allowed else "HIDDEN"


def _bool(data: dict[str, Any], *keys: str, default: bool) -> bool:
    for key in keys:
        if key in data:
            return bool(data[key])
    return default


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
    "MODULE_03_USERS_ROLES",
    "MODULE_07_DIGITAL_HOUSE",
    "ObjectVisibilitySettingsDTO",
    "ObjectOfferSettingsDTO",
    "get_default_object_visibility_settings",
    "get_default_object_offer_settings",
    "build_object_visibility_settings",
    "build_object_offer_settings",
    "getDefaultObjectVisibilitySettings",
    "getDefaultObjectOfferSettings",
    "buildObjectVisibilitySettings",
    "buildObjectOfferSettings",
]
