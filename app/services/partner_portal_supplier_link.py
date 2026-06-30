from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL


MODULE_01_MATERIAL_HUB = "MODULE_01_MATERIAL_HUB"


@dataclass(frozen=True)
class SupplierCabinetLinkDTO:
    supplierId: str
    cabinetId: str | None = None
    linkStatus: str = "PENDING"
    verificationStatus: str = "UNVERIFIED"
    sourceModuleCode: str = MODULE_01_MATERIAL_HUB
    targetModuleCode: str = MODULE_08_PARTNER_PORTAL
    boundaryNote: str = (
        "SupplierCabinetLink connects a Material Hub supplier to a Module 08 cabinet. "
        "Module 08 does not create materials, prices, price lists or canonical suppliers."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_supplier_cabinet_link(
    data: Any,
    *,
    supplier_id: str | None = None,
    cabinet_id: str | None = None,
) -> SupplierCabinetLinkDTO:
    payload = _dict_value(data)
    resolved_supplier_id = _string_or_none(payload.get("supplierId") or payload.get("supplier_id") or supplier_id)
    if not resolved_supplier_id:
        raise ValueError("supplierId is required to link Material Hub supplier to Module 08 cabinet.")

    return SupplierCabinetLinkDTO(
        supplierId=resolved_supplier_id,
        cabinetId=_string_or_none(payload.get("cabinetId") or payload.get("cabinet_id") or cabinet_id),
        linkStatus=_status(payload.get("linkStatus") or payload.get("link_status"), default="PENDING"),
        verificationStatus=_status(
            payload.get("verificationStatus") or payload.get("verification_status"),
            default="UNVERIFIED",
        ),
        sourceModuleCode=MODULE_01_MATERIAL_HUB,
        targetModuleCode=MODULE_08_PARTNER_PORTAL,
    )


def buildSupplierCabinetLink(
    data: Any,
    *,
    supplier_id: str | None = None,
    cabinet_id: str | None = None,
) -> SupplierCabinetLinkDTO:
    return build_supplier_cabinet_link(data, supplier_id=supplier_id, cabinet_id=cabinet_id)


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
    "MODULE_01_MATERIAL_HUB",
    "SupplierCabinetLinkDTO",
    "build_supplier_cabinet_link",
    "buildSupplierCabinetLink",
]
