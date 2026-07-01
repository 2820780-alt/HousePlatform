from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.models.enums import SourceActionType
from app.schemas.material_hub_contracts import (
    DocumentFileType,
    DocumentOrigin,
    DocumentParseStatus,
    TextExtractionSuitability,
)
from app.services.source_document_refs import source_documents_from_parameters


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
    file_type: DocumentFileType | str | None = None
    mime_type: str | None = None
    origin: DocumentOrigin | str = DocumentOrigin.EXTERNAL_LINK
    extraction_suitability: TextExtractionSuitability | str = TextExtractionSuitability.UNKNOWN
    parse_status: DocumentParseStatus | str = DocumentParseStatus.NOT_PROCESSED
    source_code: str | None = None
    linked_catalog_product_id: UUID | None = None
    applicable_category_ids: list[UUID] | None = None
    checksum: str | None = None
    fetched_at: datetime | None = None
    needs_review: bool = True
    review_reason: str | None = None
    dedupe_key: str | None = None
    metadata: dict | None = None


@dataclass
class HealthCheckResult:
    ok: bool
    status_code: int | None = None
    message: str | None = None


class SourceIntegration:
    supported_actions: set[SourceActionType] = set()

    async def check_health(self) -> HealthCheckResult:
        raise NotImplementedError

    async def fetch_products(
        self,
        action_type: SourceActionType,
        parameters: dict | None = None,
    ) -> list[SourceProduct]:
        raise NotImplementedError

    async def fetch_documents(
        self,
        action_type: SourceActionType,
        parameters: dict | None = None,
    ) -> list[SourceDocument]:
        refs = source_documents_from_parameters(
            parameters,
            source_code=getattr(getattr(self, "source", None), "name", None),
            source_url=getattr(getattr(self, "source", None), "url", None),
        )
        return [
            SourceDocument(
                title=ref.title,
                document_type=getattr(ref.document_type, "value", str(ref.document_type)),
                file_url=ref.url,
                source_url=ref.source_url,
                material_id=ref.linked_material_id,
                file_type=ref.file_type,
                mime_type=ref.mime_type,
                origin=ref.origin,
                extraction_suitability=ref.extraction_suitability,
                parse_status=ref.parse_status,
                source_code=ref.source_code,
                linked_catalog_product_id=ref.linked_catalog_product_id,
                applicable_category_ids=ref.applicable_category_ids,
                checksum=ref.checksum,
                fetched_at=ref.fetched_at,
                needs_review=ref.needs_review,
                review_reason=ref.review_reason,
                dedupe_key=ref.dedupe_key,
                metadata=ref.metadata,
            )
            for ref in refs
        ]
