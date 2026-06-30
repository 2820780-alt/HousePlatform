from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL


CABINET_DOCUMENTS_FEATURE = "CABINET_DOCUMENTS"
MATERIAL_DOCUMENTS_SOURCE_MODULE = "MODULE_01_MATERIAL_HUB"


@dataclass(frozen=True)
class CabinetContactDTO:
    cabinetId: str | None = None
    contactType: str = "GENERAL"
    title: str | None = None
    contactPerson: str | None = None
    phone: str | None = None
    email: str | None = None
    messenger: str | None = None
    isPrimary: bool = False
    visibilityScope: str = "CABINET"
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetBranchDTO:
    cabinetId: str | None = None
    branchCode: str | None = None
    title: str | None = None
    branchType: str | None = None
    regionCode: str | None = None
    cityId: str | None = None
    address: str | None = None
    isPrimary: bool = False
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetServiceRegionDTO:
    cabinetId: str | None = None
    regionCode: str | None = None
    regionTitle: str | None = None
    serviceType: str | None = None
    isPrimary: bool = False
    isActive: bool = True
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetDeliveryZoneDTO:
    cabinetId: str | None = None
    deliveryZoneCode: str | None = None
    regionCode: str | None = None
    cityId: str | None = None
    title: str | None = None
    deliveryType: str | None = None
    isActive: bool = True
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetDocumentDTO:
    cabinetId: str | None = None
    documentCode: str | None = None
    documentType: str = "COMPANY_DOCUMENT"
    title: str | None = None
    fileRef: str | None = None
    externalUrl: str | None = None
    documentStatus: str = "DRAFT"
    issuedAt: str | None = None
    expiresAt: str | None = None
    visibilityScope: str = "CABINET"
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    featureCode: str = CABINET_DOCUMENTS_FEATURE
    materialDocumentsSourceModuleCode: str = MATERIAL_DOCUMENTS_SOURCE_MODULE
    boundaryNote: str = (
        "CabinetDocument stores participant/company cabinet documents. "
        "Material certificates and technical sheets stay in Module 1."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetProfileDTO:
    cabinetId: str | None = None
    sourceModuleCode: str = MODULE_08_PARTNER_PORTAL
    contacts: list[CabinetContactDTO] | None = None
    branches: list[CabinetBranchDTO] | None = None
    serviceRegions: list[CabinetServiceRegionDTO] | None = None
    deliveryZones: list[CabinetDeliveryZoneDTO] | None = None
    documents: list[CabinetDocumentDTO] | None = None
    isMock: bool = True
    updatedAt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cabinetId": self.cabinetId,
            "sourceModuleCode": self.sourceModuleCode,
            "contacts": [item.to_dict() for item in self.contacts or []],
            "branches": [item.to_dict() for item in self.branches or []],
            "serviceRegions": [item.to_dict() for item in self.serviceRegions or []],
            "deliveryZones": [item.to_dict() for item in self.deliveryZones or []],
            "documents": [item.to_dict() for item in self.documents or []],
            "isMock": self.isMock,
            "updatedAt": self.updatedAt,
        }


def build_cabinet_profile(
    *,
    cabinet_id: str | None = None,
    contacts: list[dict[str, Any]] | None = None,
    branches: list[dict[str, Any]] | None = None,
    service_regions: list[dict[str, Any]] | None = None,
    delivery_zones: list[dict[str, Any]] | None = None,
    documents: list[dict[str, Any]] | None = None,
) -> CabinetProfileDTO:
    return CabinetProfileDTO(
        cabinetId=cabinet_id,
        contacts=[_contact(item, cabinet_id=cabinet_id) for item in contacts or []],
        branches=[_branch(item, cabinet_id=cabinet_id) for item in branches or []],
        serviceRegions=[_service_region(item, cabinet_id=cabinet_id) for item in service_regions or []],
        deliveryZones=[_delivery_zone(item, cabinet_id=cabinet_id) for item in delivery_zones or []],
        documents=[_document(item, cabinet_id=cabinet_id) for item in documents or []],
        updatedAt=datetime.now(UTC).isoformat(),
    )


def buildCabinetProfile(
    *,
    cabinet_id: str | None = None,
    contacts: list[dict[str, Any]] | None = None,
    branches: list[dict[str, Any]] | None = None,
    service_regions: list[dict[str, Any]] | None = None,
    delivery_zones: list[dict[str, Any]] | None = None,
    documents: list[dict[str, Any]] | None = None,
) -> CabinetProfileDTO:
    return build_cabinet_profile(
        cabinet_id=cabinet_id,
        contacts=contacts,
        branches=branches,
        service_regions=service_regions,
        delivery_zones=delivery_zones,
        documents=documents,
    )


def _contact(data: dict[str, Any], *, cabinet_id: str | None) -> CabinetContactDTO:
    return CabinetContactDTO(
        cabinetId=_string_or_none(data.get("cabinetId") or cabinet_id),
        contactType=_string_or_none(data.get("contactType")) or "GENERAL",
        title=_string_or_none(data.get("title")),
        contactPerson=_string_or_none(data.get("contactPerson")),
        phone=_string_or_none(data.get("phone")),
        email=_string_or_none(data.get("email")),
        messenger=_string_or_none(data.get("messenger")),
        isPrimary=bool(data.get("isPrimary", False)),
        visibilityScope=_string_or_none(data.get("visibilityScope")) or "CABINET",
    )


def _branch(data: dict[str, Any], *, cabinet_id: str | None) -> CabinetBranchDTO:
    return CabinetBranchDTO(
        cabinetId=_string_or_none(data.get("cabinetId") or cabinet_id),
        branchCode=_string_or_none(data.get("branchCode")),
        title=_string_or_none(data.get("title")),
        branchType=_string_or_none(data.get("branchType")),
        regionCode=_string_or_none(data.get("regionCode")),
        cityId=_string_or_none(data.get("cityId")),
        address=_string_or_none(data.get("address")),
        isPrimary=bool(data.get("isPrimary", False)),
    )


def _service_region(data: dict[str, Any], *, cabinet_id: str | None) -> CabinetServiceRegionDTO:
    return CabinetServiceRegionDTO(
        cabinetId=_string_or_none(data.get("cabinetId") or cabinet_id),
        regionCode=_string_or_none(data.get("regionCode")),
        regionTitle=_string_or_none(data.get("regionTitle")),
        serviceType=_string_or_none(data.get("serviceType")),
        isPrimary=bool(data.get("isPrimary", False)),
        isActive=bool(data.get("isActive", True)),
    )


def _delivery_zone(data: dict[str, Any], *, cabinet_id: str | None) -> CabinetDeliveryZoneDTO:
    return CabinetDeliveryZoneDTO(
        cabinetId=_string_or_none(data.get("cabinetId") or cabinet_id),
        deliveryZoneCode=_string_or_none(data.get("deliveryZoneCode")),
        regionCode=_string_or_none(data.get("regionCode")),
        cityId=_string_or_none(data.get("cityId")),
        title=_string_or_none(data.get("title")),
        deliveryType=_string_or_none(data.get("deliveryType")),
        isActive=bool(data.get("isActive", True)),
    )


def _document(data: dict[str, Any], *, cabinet_id: str | None) -> CabinetDocumentDTO:
    return CabinetDocumentDTO(
        cabinetId=_string_or_none(data.get("cabinetId") or cabinet_id),
        documentCode=_string_or_none(data.get("documentCode")),
        documentType=_string_or_none(data.get("documentType")) or "COMPANY_DOCUMENT",
        title=_string_or_none(data.get("title")),
        fileRef=_string_or_none(data.get("fileRef")),
        externalUrl=_string_or_none(data.get("externalUrl")),
        documentStatus=_string_or_none(data.get("documentStatus")) or "DRAFT",
        issuedAt=_string_or_none(data.get("issuedAt")),
        expiresAt=_string_or_none(data.get("expiresAt")),
        visibilityScope=_string_or_none(data.get("visibilityScope")) or "CABINET",
    )


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = [
    "CABINET_DOCUMENTS_FEATURE",
    "MATERIAL_DOCUMENTS_SOURCE_MODULE",
    "CabinetContactDTO",
    "CabinetBranchDTO",
    "CabinetServiceRegionDTO",
    "CabinetDeliveryZoneDTO",
    "CabinetDocumentDTO",
    "CabinetProfileDTO",
    "build_cabinet_profile",
    "buildCabinetProfile",
]
