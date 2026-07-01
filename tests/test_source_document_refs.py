import pytest

from app.models.enums import DocumentType, SourceActionType, SourceStatus, SourceType
from app.models.source import Source
from app.services.source_document_refs import (
    build_source_document_ref,
    is_document_url,
    source_documents_from_parameters,
)
from app.source_integrations.base import SourceIntegration


def test_source_document_ref_has_required_metadata_and_dedupe_key():
    ref = build_source_document_ref(
        {
            "title": "Сертификат соответствия Bonolit",
            "url": "https://bonolit.ru/docs/certificate.pdf",
            "sourceCode": "bonolit",
        },
        source_url="https://bonolit.ru/",
    )

    assert ref is not None
    assert ref.document_type == DocumentType.CERTIFICATE.value
    assert ref.file_type.value == "PDF"
    assert ref.mime_type == "application/pdf"
    assert ref.extraction_suitability.value == "TEXT_READY"
    assert ref.parse_status.value == "not_processed"
    assert ref.source_code == "bonolit"
    assert ref.needs_review is True
    assert ref.dedupe_key


def test_catalog_and_product_html_pages_are_not_documents():
    assert is_document_url("https://example.ru/catalog/gazobeton/", title="Газобетон") is False
    assert is_document_url("https://example.ru/product/gazoblok-123/", title="Газоблок") is False
    assert is_document_url("https://example.ru/certificates/certificat.html", title="Сертификаты") is True


def test_document_refs_from_parameters_are_deduplicated():
    refs = source_documents_from_parameters(
        {
            "document_urls": [
                "https://example.ru/docs/passport.pdf",
                "https://example.ru/docs/passport.pdf",
            ]
        },
        source_code="example",
        source_url="https://example.ru/",
    )

    assert len(refs) == 1
    assert refs[0].file_type.value == "PDF"


class _ProfileDrivenIntegration(SourceIntegration):
    supported_actions = {SourceActionType.UPDATE_TECH_DOCUMENTS}

    async def check_health(self):
        raise NotImplementedError

    async def fetch_products(self, action_type, parameters=None):
        return []


@pytest.mark.asyncio
async def test_base_source_integration_fetches_profile_document_refs():
    integration = _ProfileDrivenIntegration()
    integration.source = Source(
        name="ProfileSource",
        source_type=SourceType.SUPPLIER,
        url="https://example.ru/",
        status=SourceStatus.ACTIVE,
    )

    documents = await integration.fetch_documents(
        SourceActionType.UPDATE_TECH_DOCUMENTS,
        {"document_refs": [{"title": "Технический лист", "url": "/docs/tech-list.pdf"}]},
    )

    assert len(documents) == 1
    assert documents[0].title == "Технический лист"
    assert documents[0].file_type.value == "PDF"
    assert documents[0].source_code == "ProfileSource"
