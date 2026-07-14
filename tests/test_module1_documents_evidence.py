from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_documents_evidence import (
    MaterialDocumentRecord,
    build_document_evidence_from_raw_link,
    build_document_package,
    build_document_readiness_report,
    build_document_record_from_material_document,
    classify_document_type,
    get_missing_document_hints,
    get_required_document_hints,
    validate_document_record,
)


def _canonical_view(
    *,
    group_code: str = "aerated_concrete_block",
    documents: tuple[dict, ...] = tuple(),
    source_refs: tuple[dict, ...] = tuple(),
    moderation_preview_refs: tuple[dict, ...] = tuple(),
) -> MaterialCanonicalView:
    return MaterialCanonicalView(
        material_id="mat-001",
        canonical_name="Aerated concrete block D500",
        category={"slug": group_code, "name": "Blocks"},
        subcategory=None,
        group={"code": group_code, "name": group_code},
        characteristics=tuple(),
        technical_profile_hints={},
        evidence=MaterialEvidenceSummary(
            document_count=len(documents),
            source_ref_count=len(source_refs),
            documents=documents,
            source_refs=source_refs,
            moderation_preview_refs=moderation_preview_refs,
            warnings=tuple(),
        ),
        supplier_price_refs=tuple(),
        moderation_status="approved",
        quality=MaterialQualitySummary(
            status="ok",
            open_issues=0,
            critical_issues=0,
            warning_issues=0,
            issues=tuple(),
            warnings=tuple(),
        ),
        source_provenance={"canonicalBase": "Material", "rawDataIsCanonical": False},
        status="ACTIVE",
        warnings=tuple(),
        created_at=None,
        updated_at=None,
    )


def test_build_document_record_from_legacy_material_document_shape() -> None:
    legacy_document = SimpleNamespace(
        id="doc-001",
        title="Certificate for aerated concrete block",
        document_type=SimpleNamespace(value="CERTIFICATE"),
        material_id="mat-001",
        manufacturer=SimpleNamespace(name="Bonolit"),
        source=SimpleNamespace(id="src-001", name="Manufacturer site", url="https://example.test/"),
        file_url="https://example.test/docs/certificate.pdf",
        source_url="https://example.test/materials/aerated-block",
        issue_date=date(2026, 1, 10),
        expiry_date=date(2027, 1, 10),
        status=SimpleNamespace(value="ACTIVE"),
        confidence="0.91",
    )

    record = build_document_record_from_material_document(
        legacy_document,
        material_group="aerated_concrete_block",
    )

    assert isinstance(record, MaterialDocumentRecord)
    assert record.document_id == "doc-001"
    assert record.document_type == "certificate"
    assert record.status == "active"
    assert record.material_id == "mat-001"
    assert record.manufacturer == "Bonolit"
    assert record.issue_date == "2026-01-10"
    assert record.expiry_date == "2027-01-10"
    assert record.confidence == Decimal("0.91")
    assert not record.warnings


def test_source_card_url_is_not_promoted_to_document_record() -> None:
    record = MaterialDocumentRecord(
        document_id="doc-card",
        title="Aerated concrete product card",
        document_type="other",
        material_id="mat-001",
        material_group="aerated_concrete_block",
        manufacturer=None,
        supplier=None,
        source_url="https://example.test/catalog/aerated-concrete/d500",
        file_url=None,
        storage_ref=None,
        issue_date=None,
        expiry_date=None,
        status="needs_review",
        confidence=None,
        evidence_refs=tuple(),
        warnings=tuple(),
    )

    report = validate_document_record(record)
    raw_evidence = build_document_evidence_from_raw_link(
        {
            "title": "Aerated concrete product card",
            "url": "https://example.test/product/aerated-concrete-d500",
        },
        material_id="mat-001",
        material_group="aerated_concrete_block",
    )

    assert report.is_valid is False
    assert "site/card" in " ".join(report.warnings)
    assert raw_evidence.raw_link is not None
    assert raw_evidence.raw_link.is_document is False
    assert raw_evidence.document is None


def test_raw_document_link_builds_evidence_without_creating_canonical_material() -> None:
    evidence = build_document_evidence_from_raw_link(
        {
            "title": "Technical sheet D500",
            "url": "https://example.test/docs/tds-d500.pdf",
            "sourceCode": "manufacturer_site",
            "confidence": "0.82",
        },
        material_id="mat-001",
        material_group="aerated_concrete_block",
    )

    assert evidence.raw_link is not None
    assert evidence.raw_link.is_document is True
    assert evidence.document is not None
    assert evidence.document.document_type == "technical_sheet"
    assert "technical_profile" in evidence.confirms
    assert evidence.source == "manufacturer_site"
    assert evidence.confidence == Decimal("0.82")


def test_document_package_uses_blueprint_hints_and_reports_missing_documents() -> None:
    view = _canonical_view(
        documents=(
            {
                "documentId": "doc-cert",
                "title": "Certificate",
                "documentType": "certificate",
                "fileUrl": "https://example.test/docs/cert.pdf",
                "status": "active",
            },
        ),
        source_refs=(
            {
                "title": "Declaration candidate",
                "documentUrl": "https://example.test/docs/declaration.pdf",
            },
            {
                "title": "Product page",
                "externalUrl": "https://example.test/catalog/aerated-concrete/d500",
            },
        ),
    )

    package = build_document_package(view)
    readiness = build_document_readiness_report(view)

    assert package.material_id == "mat-001"
    assert package.documents[0].document_type == "certificate"
    assert "certificate" in package.required_document_hints
    assert "declaration" in package.required_document_hints
    assert "technical_sheet" in package.required_document_hints
    assert "declaration" in package.missing_document_hints
    assert "technical_sheet" in package.missing_document_hints
    assert readiness.status == "missing_documents"
    assert len(readiness.raw_links_pending) == 1
    assert readiness.raw_links_pending[0].url.endswith("declaration.pdf")


def test_required_document_hints_are_normalized_from_extraction_blueprints() -> None:
    aerated_hints = get_required_document_hints("aerated_concrete_block")
    metal_tile_hints = get_required_document_hints("metal_tile")

    assert aerated_hints == ("certificate", "declaration", "technical_sheet")
    assert "warranty" in metal_tile_hints
    assert "technical_sheet" in metal_tile_hints


def test_missing_document_hints_ignore_raw_links_until_moderation() -> None:
    view = _canonical_view(
        documents=tuple(),
        source_refs=(
            {
                "title": "Certificate candidate",
                "documentUrl": "https://example.test/docs/certificate.pdf",
            },
        ),
    )

    missing = get_missing_document_hints(view)

    assert "certificate" in missing


def test_document_type_classification_supports_contract_document_types() -> None:
    assert classify_document_type("Certificate", "https://example.test/cert.pdf") == "certificate"
    assert classify_document_type("Declaration", "https://example.test/decl.pdf") == "declaration"
    assert classify_document_type("Technical datasheet", "https://example.test/tds.pdf") == "technical_sheet"
    assert classify_document_type("Installation guide", "https://example.test/install.pdf") == "installation_instruction"
    assert classify_document_type("Warranty terms", "https://example.test/warranty.pdf") == "warranty"
    assert classify_document_type("Legacy tech card", metadata={"document_type": "TECH_CARD"}) == "technical_sheet"


def test_documents_evidence_service_is_read_only_compatibility_layer() -> None:
    source = Path("app/services/module1_documents_evidence.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "requests." not in source
    assert "httpx." not in source
