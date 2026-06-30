from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL


MODULE_03_USERS_ROLES = "MODULE_03_USERS_ROLES"
MODULE_07_DIGITAL_HOUSE = "MODULE_07_DIGITAL_HOUSE"

OBJECT_RELATION_OWNER = "OWNER"
OBJECT_RELATION_INVITED = "INVITED"
OBJECT_RELATION_SUPPLIER_REQUEST = "SUPPLIER_REQUEST"
OBJECT_RELATION_CONTRACTOR_REQUEST = "CONTRACTOR_REQUEST"
OBJECT_RELATION_ACTIVE_SUPPLY = "ACTIVE_SUPPLY"
OBJECT_RELATION_ACTIVE_WORK = "ACTIVE_WORK"
OBJECT_RELATION_COMPLETED_DEAL = "COMPLETED_DEAL"
OBJECT_RELATION_OFFER_ALLOWED = "OFFER_ALLOWED"
OBJECT_RELATION_ARCHIVED = "ARCHIVED"

OBJECT_LINK_RELATION_TYPES: tuple[str, ...] = (
    OBJECT_RELATION_OWNER,
    OBJECT_RELATION_INVITED,
    OBJECT_RELATION_SUPPLIER_REQUEST,
    OBJECT_RELATION_CONTRACTOR_REQUEST,
    OBJECT_RELATION_ACTIVE_SUPPLY,
    OBJECT_RELATION_ACTIVE_WORK,
    OBJECT_RELATION_COMPLETED_DEAL,
    OBJECT_RELATION_OFFER_ALLOWED,
    OBJECT_RELATION_ARCHIVED,
)

NON_OWNING_OBJECT_RELATION_TYPES: tuple[str, ...] = tuple(
    item
    for item in OBJECT_LINK_RELATION_TYPES
    if item != OBJECT_RELATION_OWNER
)


@dataclass(frozen=True)
class CabinetObjectLinkDTO:
    cabinetId: str | None = None
    objectId: str | None = None
    objectType: str = "DIGITAL_HOUSE"
    relationType: str = OBJECT_RELATION_INVITED
    visibilityScope: str = "LIMITED"
    isActive: bool = True
    isOwnershipRelation: bool = False
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    targetModuleCode: str = MODULE_07_DIGITAL_HOUSE
    createdAt: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    boundaryNote: str = (
        "A linked object is not necessarily an owned object. Visibility is controlled by "
        "Module 08 visibility settings and Module 03 permissions."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParticipantObjectAccessDTO:
    cabinetId: str | None = None
    participantUserId: str | None = None
    participantCabinetId: str | None = None
    objectId: str | None = None
    objectType: str = "DIGITAL_HOUSE"
    relationType: str = OBJECT_RELATION_INVITED
    visibilityScope: str = "LIMITED"
    accessStatus: str = "ACTIVE"
    allowedDataScopes: list[str] = field(default_factory=list)
    deniedDataScopes: list[str] = field(default_factory=list)
    isOwnerAccess: bool = False
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    targetModuleCode: str = MODULE_07_DIGITAL_HOUSE
    permissionSourceModuleCode: str = MODULE_03_USERS_ROLES
    visibilitySourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    boundaryNote: str = (
        "ParticipantObjectAccess stores visibility context only. Backend access checks still "
        "belong to Module 03 Permission Guard and object data belongs to Module 07."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_object_relation_type(value: str | None) -> str:
    if not value:
        return OBJECT_RELATION_INVITED
    normalized = str(value).upper()
    aliases = {
        "OWNER_OBJECT": OBJECT_RELATION_OWNER,
        "OWNED": OBJECT_RELATION_OWNER,
        "INVITE": OBJECT_RELATION_INVITED,
        "REQUEST_SUPPLIER": OBJECT_RELATION_SUPPLIER_REQUEST,
        "REQUEST_CONTRACTOR": OBJECT_RELATION_CONTRACTOR_REQUEST,
        "SUPPLY": OBJECT_RELATION_ACTIVE_SUPPLY,
        "WORK": OBJECT_RELATION_ACTIVE_WORK,
        "DEAL_DONE": OBJECT_RELATION_COMPLETED_DEAL,
        "OFFER": OBJECT_RELATION_OFFER_ALLOWED,
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in OBJECT_LINK_RELATION_TYPES:
        return OBJECT_RELATION_INVITED
    return normalized


def build_cabinet_object_link(
    data: Any,
    *,
    cabinet_id: str | None = None,
) -> CabinetObjectLinkDTO:
    link_data = _dict_value(data)
    relation_type = normalize_object_relation_type(
        _string_or_none(link_data.get("relationType") or link_data.get("relation_type"))
    )
    return CabinetObjectLinkDTO(
        cabinetId=_string_or_none(link_data.get("cabinetId") or link_data.get("cabinet_id") or cabinet_id),
        objectId=_string_or_none(link_data.get("objectId") or link_data.get("object_id")),
        objectType=_string_or_none(link_data.get("objectType") or link_data.get("object_type")) or "DIGITAL_HOUSE",
        relationType=relation_type,
        visibilityScope=_normalize_visibility_scope(
            _string_or_none(link_data.get("visibilityScope") or link_data.get("visibility_scope"))
        ),
        isActive=bool(link_data.get("isActive", link_data.get("is_active", True))),
        isOwnershipRelation=relation_type == OBJECT_RELATION_OWNER,
    )


def build_participant_object_access(
    data: Any,
    *,
    cabinet_id: str | None = None,
    participant_user_id: str | None = None,
    participant_cabinet_id: str | None = None,
) -> ParticipantObjectAccessDTO:
    access_data = _dict_value(data)
    relation_type = normalize_object_relation_type(
        _string_or_none(access_data.get("relationType") or access_data.get("relation_type"))
    )
    return ParticipantObjectAccessDTO(
        cabinetId=_string_or_none(access_data.get("cabinetId") or access_data.get("cabinet_id") or cabinet_id),
        participantUserId=_string_or_none(
            access_data.get("participantUserId")
            or access_data.get("participant_user_id")
            or participant_user_id
        ),
        participantCabinetId=_string_or_none(
            access_data.get("participantCabinetId")
            or access_data.get("participant_cabinet_id")
            or participant_cabinet_id
        ),
        objectId=_string_or_none(access_data.get("objectId") or access_data.get("object_id")),
        objectType=_string_or_none(access_data.get("objectType") or access_data.get("object_type")) or "DIGITAL_HOUSE",
        relationType=relation_type,
        visibilityScope=_normalize_visibility_scope(
            _string_or_none(access_data.get("visibilityScope") or access_data.get("visibility_scope"))
        ),
        accessStatus=_string_or_none(access_data.get("accessStatus") or access_data.get("access_status")) or "ACTIVE",
        allowedDataScopes=_relation_default_scopes(relation_type),
        deniedDataScopes=[] if relation_type != OBJECT_RELATION_ARCHIVED else ["ACTIVE_DATA"],
        isOwnerAccess=relation_type == OBJECT_RELATION_OWNER,
    )


def buildCabinetObjectLink(
    data: Any,
    *,
    cabinet_id: str | None = None,
) -> CabinetObjectLinkDTO:
    return build_cabinet_object_link(data, cabinet_id=cabinet_id)


def buildParticipantObjectAccess(
    data: Any,
    *,
    cabinet_id: str | None = None,
    participant_user_id: str | None = None,
    participant_cabinet_id: str | None = None,
) -> ParticipantObjectAccessDTO:
    return build_participant_object_access(
        data,
        cabinet_id=cabinet_id,
        participant_user_id=participant_user_id,
        participant_cabinet_id=participant_cabinet_id,
    )


def _relation_default_scopes(relation_type: str) -> list[str]:
    scopes = {
        OBJECT_RELATION_OWNER: ["OBJECT_SUMMARY", "OBJECT_PROFILE", "VISIBILITY_SETTINGS"],
        OBJECT_RELATION_INVITED: ["OBJECT_SUMMARY"],
        OBJECT_RELATION_SUPPLIER_REQUEST: ["REQUEST_SUMMARY", "OFFER_CONTEXT"],
        OBJECT_RELATION_CONTRACTOR_REQUEST: ["REQUEST_SUMMARY", "WORK_CONTEXT"],
        OBJECT_RELATION_ACTIVE_SUPPLY: ["SUPPLY_CONTEXT", "DELIVERY_STATUS"],
        OBJECT_RELATION_ACTIVE_WORK: ["WORK_CONTEXT", "TASK_STATUS"],
        OBJECT_RELATION_COMPLETED_DEAL: ["DEAL_HISTORY"],
        OBJECT_RELATION_OFFER_ALLOWED: ["OFFER_CONTEXT"],
        OBJECT_RELATION_ARCHIVED: [],
    }
    return list(scopes.get(relation_type, []))


def _normalize_visibility_scope(value: str | None) -> str:
    if not value:
        return "LIMITED"
    normalized = str(value).upper()
    allowed = {"PRIVATE", "LIMITED", "WORKSPACE", "PUBLIC", "ARCHIVED"}
    return normalized if normalized in allowed else "LIMITED"


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


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "MODULE_03_USERS_ROLES",
    "MODULE_07_DIGITAL_HOUSE",
    "OBJECT_RELATION_OWNER",
    "OBJECT_RELATION_INVITED",
    "OBJECT_RELATION_SUPPLIER_REQUEST",
    "OBJECT_RELATION_CONTRACTOR_REQUEST",
    "OBJECT_RELATION_ACTIVE_SUPPLY",
    "OBJECT_RELATION_ACTIVE_WORK",
    "OBJECT_RELATION_COMPLETED_DEAL",
    "OBJECT_RELATION_OFFER_ALLOWED",
    "OBJECT_RELATION_ARCHIVED",
    "OBJECT_LINK_RELATION_TYPES",
    "NON_OWNING_OBJECT_RELATION_TYPES",
    "CabinetObjectLinkDTO",
    "ParticipantObjectAccessDTO",
    "normalize_object_relation_type",
    "build_cabinet_object_link",
    "build_participant_object_access",
    "buildCabinetObjectLink",
    "buildParticipantObjectAccess",
]
