from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL


MODULE_04_WORKS_COSTS = "MODULE_04_WORKS_COSTS"


@dataclass(frozen=True)
class WorksCostsCabinetLinkDTO:
    cabinetId: str | None = None
    workRateSourceId: str | None = None
    contractorProfileRef: str | None = None
    workProducerRef: str | None = None
    linkStatus: str = "PENDING"
    sourceModuleCode: str = MODULE_04_WORKS_COSTS
    targetModuleCode: str = MODULE_08_PARTNER_PORTAL
    boundaryNote: str = (
        "WorksCostsCabinetLink connects cabinet context to Module 04 references. "
        "Module 08 does not create WorkRate, work catalogs, rate observations or approved prices."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_works_costs_cabinet_link(
    data: Any,
    *,
    cabinet_id: str | None = None,
) -> WorksCostsCabinetLinkDTO:
    payload = _dict_value(data)
    work_rate_source_id = _string_or_none(payload.get("workRateSourceId") or payload.get("work_rate_source_id"))
    contractor_profile_ref = _string_or_none(
        payload.get("contractorProfileRef") or payload.get("contractor_profile_ref")
    )
    work_producer_ref = _string_or_none(payload.get("workProducerRef") or payload.get("work_producer_ref"))

    if not any((work_rate_source_id, contractor_profile_ref, work_producer_ref)):
        raise ValueError(
            "At least one Module 04 reference is required: workRateSourceId, "
            "contractorProfileRef or workProducerRef."
        )

    return WorksCostsCabinetLinkDTO(
        cabinetId=_string_or_none(payload.get("cabinetId") or payload.get("cabinet_id") or cabinet_id),
        workRateSourceId=work_rate_source_id,
        contractorProfileRef=contractor_profile_ref,
        workProducerRef=work_producer_ref,
        linkStatus=_status(payload.get("linkStatus") or payload.get("link_status"), default="PENDING"),
        sourceModuleCode=MODULE_04_WORKS_COSTS,
        targetModuleCode=MODULE_08_PARTNER_PORTAL,
    )


def buildWorksCostsCabinetLink(
    data: Any,
    *,
    cabinet_id: str | None = None,
) -> WorksCostsCabinetLinkDTO:
    return build_works_costs_cabinet_link(data, cabinet_id=cabinet_id)


def _status(value: Any, *, default: str) -> str:
    if value is None:
        return default
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
    "MODULE_04_WORKS_COSTS",
    "WorksCostsCabinetLinkDTO",
    "build_works_costs_cabinet_link",
    "buildWorksCostsCabinetLink",
]
