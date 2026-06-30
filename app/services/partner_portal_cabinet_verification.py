from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL


CABINET_VERIFICATION_STATUSES = (
    "DRAFT",
    "PENDING_REVIEW",
    "VERIFIED",
    "NEEDS_CLARIFICATION",
    "REJECTED",
    "RESTRICTED",
    "BLOCKED",
    "ARCHIVED",
)

CABINET_VERIFICATION_LEVELS = (
    "NOT_VERIFIED",
    "BASIC_CHECKED",
    "DOCUMENTS_CHECKED",
    "COMPANY_VERIFIED",
    "TRUSTED_PARTNER",
)


@dataclass(frozen=True)
class CabinetVerificationDTO:
    cabinetId: str | None = None
    cabinetType: str | None = None
    verificationStatus: str = "DRAFT"
    verificationLevel: str = "NOT_VERIFIED"
    reviewedByUserId: str | None = None
    reason: str | None = None
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    targetModuleCode: str = MODULE_08_PARTNER_PORTAL
    boundaryNote: str = (
        "CabinetVerification stores cabinet verification state. It does not grant permissions; "
        "Module 03 remains responsible for RBAC and server-side access checks."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetModerationLogDTO:
    cabinetId: str | None = None
    moderationEvent: str = "STATUS_CHANGED"
    previousStatus: str | None = None
    newStatus: str = "DRAFT"
    previousLevel: str | None = None
    newLevel: str | None = None
    actorUserId: str | None = None
    reason: str | None = None
    comment: str | None = None
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    targetModuleCode: str = MODULE_08_PARTNER_PORTAL
    boundaryNote: str = (
        "CabinetModerationLog records moderation history. It is not AuditLog and is not a permission source."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_cabinet_verification(data: Any) -> CabinetVerificationDTO:
    payload = _dict_value(data)
    return CabinetVerificationDTO(
        cabinetId=_string_or_none(payload.get("cabinetId") or payload.get("cabinet_id")),
        cabinetType=_string_or_none(payload.get("cabinetType") or payload.get("cabinet_type")),
        verificationStatus=_status(payload.get("verificationStatus") or payload.get("verification_status")),
        verificationLevel=_level(payload.get("verificationLevel") or payload.get("verification_level")),
        reviewedByUserId=_string_or_none(payload.get("reviewedByUserId") or payload.get("reviewed_by_user_id")),
        reason=_string_or_none(payload.get("reason")),
    )


def build_cabinet_moderation_log(data: Any) -> CabinetModerationLogDTO:
    payload = _dict_value(data)
    new_status = _status(payload.get("newStatus") or payload.get("new_status"))
    new_level_raw = payload.get("newLevel") or payload.get("new_level")
    return CabinetModerationLogDTO(
        cabinetId=_string_or_none(payload.get("cabinetId") or payload.get("cabinet_id")),
        moderationEvent=_event(payload.get("moderationEvent") or payload.get("moderation_event")),
        previousStatus=_optional_status(payload.get("previousStatus") or payload.get("previous_status")),
        newStatus=new_status,
        previousLevel=_optional_level(payload.get("previousLevel") or payload.get("previous_level")),
        newLevel=_level(new_level_raw) if new_level_raw is not None else None,
        actorUserId=_string_or_none(payload.get("actorUserId") or payload.get("actor_user_id")),
        reason=_string_or_none(payload.get("reason")),
        comment=_string_or_none(payload.get("comment")),
    )


def buildCabinetVerification(data: Any) -> CabinetVerificationDTO:
    return build_cabinet_verification(data)


def buildCabinetModerationLog(data: Any) -> CabinetModerationLogDTO:
    return build_cabinet_moderation_log(data)


def _status(value: Any) -> str:
    if value is None:
        return "DRAFT"
    normalized = str(value).upper()
    if normalized not in CABINET_VERIFICATION_STATUSES:
        raise ValueError(f"Unsupported cabinet verification status: {value}")
    return normalized


def _optional_status(value: Any) -> str | None:
    if value is None:
        return None
    return _status(value)


def _level(value: Any) -> str:
    if value is None:
        return "NOT_VERIFIED"
    normalized = str(value).upper()
    if normalized not in CABINET_VERIFICATION_LEVELS:
        raise ValueError(f"Unsupported cabinet verification level: {value}")
    return normalized


def _optional_level(value: Any) -> str | None:
    if value is None:
        return None
    return _level(value)


def _event(value: Any) -> str:
    if value is None:
        return "STATUS_CHANGED"
    return str(value).upper()


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
    "CABINET_VERIFICATION_STATUSES",
    "CABINET_VERIFICATION_LEVELS",
    "CabinetVerificationDTO",
    "CabinetModerationLogDTO",
    "build_cabinet_verification",
    "build_cabinet_moderation_log",
    "buildCabinetVerification",
    "buildCabinetModerationLog",
]
