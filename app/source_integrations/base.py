from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.models.enums import SourceActionType


@dataclass
class SourceProduct:
    external_id: str | None
    external_url: str | None
    raw_name: str
    normalized_name: str | None = None
    raw_category: str | None = None
    raw_brand: str | None = None
    raw_manufacturer: str | None = None
    price: Decimal | None = None
    currency: str = "RUB"
    unit: str | None = None
    availability: str | None = None
    region: str | None = None


@dataclass
class SourceDocument:
    title: str
    document_type: str
    file_url: str | None = None
    source_url: str | None = None
    material_id: UUID | None = None
    manufacturer_id: UUID | None = None


@dataclass
class HealthCheckResult:
    ok: bool
    status_code: int | None = None
    message: str | None = None


class SourceIntegration:
    supported_actions: set[SourceActionType] = set()

    async def check_health(self) -> HealthCheckResult:
        raise NotImplementedError

    async def fetch_products(self, action_type: SourceActionType) -> list[SourceProduct]:
        raise NotImplementedError

    async def fetch_documents(self, action_type: SourceActionType) -> list[SourceDocument]:
        return []

