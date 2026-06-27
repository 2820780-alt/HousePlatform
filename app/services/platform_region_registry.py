from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PILOT_REGION_CODE = "KRASNODAR_KRAI"
PILOT_REGION_NAME = "Краснодарский край"

REGION_CONTEXT_FIELD_NAMES = (
    "activeRegionCode",
    "region_id",
    "city_id",
    "delivery_zone_id",
    "price_region_id",
    "supplier_region_id",
    "work_region_id",
    "object_region_id",
    "estimate_region_id",
    "audit_region_id",
    "procurement_region_id",
    "marketplace_region_id",
    "service_region_id",
    "delivery_region_id",
)


@dataclass(frozen=True)
class PlatformRegionRegistryItem:
    code: str
    name: str
    country: str
    status: str
    isPilotRegion: bool
    isActive: bool
    isOpenForUsers: bool
    isOpenForSuppliers: bool
    isOpenForMarketplace: bool
    isOpenForAnalytics: bool
    displayOrder: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PLATFORM_REGION_REGISTRY: tuple[PlatformRegionRegistryItem, ...] = (
    PlatformRegionRegistryItem(
        code=PILOT_REGION_CODE,
        name=PILOT_REGION_NAME,
        country="RU",
        status="ACTIVE",
        isPilotRegion=True,
        isActive=True,
        isOpenForUsers=False,
        isOpenForSuppliers=False,
        isOpenForMarketplace=False,
        isOpenForAnalytics=True,
        displayOrder=10,
    ),
)


def get_platform_region_registry() -> list[dict[str, Any]]:
    return [region.to_dict() for region in PLATFORM_REGION_REGISTRY]


def get_platform_region_registry_item(region_code: str | None) -> PlatformRegionRegistryItem | None:
    if not region_code:
        return None
    return next((region for region in PLATFORM_REGION_REGISTRY if region.code == region_code), None)


def is_known_platform_region_code(region_code: str | None) -> bool:
    return get_platform_region_registry_item(region_code) is not None


def get_default_active_region() -> dict[str, str]:
    return {
        "activeRegionCode": PILOT_REGION_CODE,
        "activeRegionName": PILOT_REGION_NAME,
    }
