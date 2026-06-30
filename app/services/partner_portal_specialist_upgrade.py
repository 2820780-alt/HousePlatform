from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.access_context_for_cabinet import AccessContextForCabinet
from app.services.partner_portal_construction_company_cabinet import (
    ConstructionCompanyCabinetDTO,
    build_construction_company_cabinet_context,
)
from app.services.partner_portal_specialist_cabinet import (
    SpecialistCabinetDTO,
    build_specialist_cabinet_context,
)


SPECIALIST_TO_COMPANY_UPGRADE = "SPECIALIST_TO_CONSTRUCTION_COMPANY"
UPGRADE_STATUS_REQUESTED = "REQUESTED"
UPGRADE_EVENT_REQUESTED = "UPGRADE_REQUESTED"
FOUNDER_OWNER_RELATION = "FOUNDER_OWNER"


@dataclass(frozen=True)
class CabinetUpgradeRequestDTO:
    upgradeRequestId: str
    upgradeType: str = SPECIALIST_TO_COMPANY_UPGRADE
    sourceCabinetType: str = "SPECIALIST"
    targetCabinetType: str = "CONSTRUCTION_COMPANY"
    sourceCabinetId: str | None = None
    requestedByUserId: str | None = None
    targetCompanyTitle: str | None = None
    requestStatus: str = UPGRADE_STATUS_REQUESTED
    preserveSourceCabinet: bool = True
    reason: str | None = None
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    targetModuleCode: str = MODULE_08_PARTNER_PORTAL
    createdAt: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetUpgradeHistoryDTO:
    historyId: str
    upgradeRequestId: str
    eventType: str = UPGRADE_EVENT_REQUESTED
    actorUserId: str | None = None
    sourceCabinetId: str | None = None
    targetCabinetId: str | None = None
    previousStatus: str | None = None
    newStatus: str = UPGRADE_STATUS_REQUESTED
    reason: str | None = None
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    createdAt: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpecialistToCompanyLinkDTO:
    linkId: str
    specialistCabinetId: str | None
    constructionCompanyCabinetId: str
    userId: str | None
    relationType: str = FOUNDER_OWNER_RELATION
    isActive: bool = True
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    targetModuleCode: str = MODULE_08_PARTNER_PORTAL
    linkedAt: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpecialistToCompanyUpgradePlanDTO:
    request: CabinetUpgradeRequestDTO
    history: list[CabinetUpgradeHistoryDTO]
    specialistCabinet: SpecialistCabinetDTO
    constructionCompanyCabinet: ConstructionCompanyCabinetDTO
    link: SpecialistToCompanyLinkDTO
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    isDryRun: bool = True
    compatibilityNote: str = (
        "Module 08 prepares the cabinet upgrade context. SpecialistCabinet is preserved, "
        "ConstructionCompanyCabinet is created as a new cabinet context, and the specialist "
        "is linked as founder / owner. Company projects, estimates, works and procurement data "
        "stay in owning modules."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["request"] = self.request.to_dict()
        data["history"] = [item.to_dict() for item in self.history]
        data["specialistCabinet"] = self.specialistCabinet.to_dict()
        data["constructionCompanyCabinet"] = self.constructionCompanyCabinet.to_dict()
        data["link"] = self.link.to_dict()
        return data


def prepare_specialist_to_company_upgrade(
    user: Any,
    *,
    specialist_cabinet_id: str | None = None,
    requested_by_user_id: str | None = None,
    target_company_title: str | None = None,
    organization_id: str | None = None,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    reason: str | None = None,
) -> SpecialistToCompanyUpgradePlanDTO:
    user_data = _dict_value(user)
    user_id = _string_or_none(user_data.get("userId") or user_data.get("id"))
    actor_user_id = requested_by_user_id or user_id
    request_id = _new_id()
    company_cabinet_id = _new_id()

    specialist = build_specialist_cabinet_context(
        user,
        specialization_code=_string_or_none(user_data.get("specializationCode")),
        access_context=access_context,
    )
    company = build_construction_company_cabinet_context(
        user,
        access_context=access_context,
        organization_id=organization_id,
    )
    request = CabinetUpgradeRequestDTO(
        upgradeRequestId=request_id,
        sourceCabinetId=specialist_cabinet_id,
        requestedByUserId=actor_user_id,
        targetCompanyTitle=target_company_title,
        reason=reason,
    )
    history = CabinetUpgradeHistoryDTO(
        historyId=_new_id(),
        upgradeRequestId=request_id,
        actorUserId=actor_user_id,
        sourceCabinetId=specialist_cabinet_id,
        targetCabinetId=company_cabinet_id,
        reason=reason,
    )
    link = SpecialistToCompanyLinkDTO(
        linkId=_new_id(),
        specialistCabinetId=specialist_cabinet_id,
        constructionCompanyCabinetId=company_cabinet_id,
        userId=user_id,
    )
    return SpecialistToCompanyUpgradePlanDTO(
        request=request,
        history=[history],
        specialistCabinet=specialist,
        constructionCompanyCabinet=company,
        link=link,
    )


def prepareSpecialistToCompanyUpgrade(
    user: Any,
    *,
    specialist_cabinet_id: str | None = None,
    requested_by_user_id: str | None = None,
    target_company_title: str | None = None,
    organization_id: str | None = None,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
    reason: str | None = None,
) -> SpecialistToCompanyUpgradePlanDTO:
    return prepare_specialist_to_company_upgrade(
        user,
        specialist_cabinet_id=specialist_cabinet_id,
        requested_by_user_id=requested_by_user_id,
        target_company_title=target_company_title,
        organization_id=organization_id,
        access_context=access_context,
        reason=reason,
    )


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


def _new_id() -> str:
    return str(uuid.uuid4())


__all__ = [
    "SPECIALIST_TO_COMPANY_UPGRADE",
    "UPGRADE_STATUS_REQUESTED",
    "UPGRADE_EVENT_REQUESTED",
    "FOUNDER_OWNER_RELATION",
    "CabinetUpgradeRequestDTO",
    "CabinetUpgradeHistoryDTO",
    "SpecialistToCompanyLinkDTO",
    "SpecialistToCompanyUpgradePlanDTO",
    "prepare_specialist_to_company_upgrade",
    "prepareSpecialistToCompanyUpgrade",
]
