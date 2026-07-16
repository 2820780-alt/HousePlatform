from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.services.module1_raw_ingestion_pipeline import (
    Module1RawIngestionItem,
    build_raw_ingestion_item_from_catalog_product,
    build_raw_ingestion_item_from_source_task_result,
    build_raw_ingestion_item_from_supplier_upload_row,
    build_raw_ingestion_readiness_report,
    enrich_raw_ingestion_with_extraction_blueprint,
    enrich_raw_ingestion_with_source_profile,
    list_supported_raw_sources,
    validate_raw_ingestion_item,
)


def test_catalog_product_builds_raw_ingestion_item_without_canonical_creation() -> None:
    product = SimpleNamespace(
        source_code="YUFO_VKBLOCK",
        source_id="source-1",
        external_url="https://vkblock.ru/product/gazoblok",
        raw_name="Газоблок D500",
        raw_category="Газобетон",
        price="4200.50",
        unit="м3",
        raw_manufacturer="VKBlock",
        region="Краснодарский край",
        created_at=datetime(2026, 7, 1, 10, 30),
        match_confidence="0.82",
        raw_payload={
            "characteristics": {
                "length_mm": 600,
                "width_mm": 300,
                "height_mm": 200,
                "density_class": "D500",
                "strength_class": "B2.5",
            },
            "documents": [{"url": "https://vkblock.ru/cert.pdf", "type": "certificate"}],
            "images": ["https://vkblock.ru/image.jpg"],
        },
    )

    item = build_raw_ingestion_item_from_catalog_product(product)

    assert item.legacy_source == "CatalogProduct"
    assert item.source_code == "YUFO_VKBLOCK"
    assert item.source_type == "manufacturer_site"
    assert item.raw_title == "Газоблок D500"
    assert item.raw_price == Decimal("4200.50")
    assert item.raw_unit == "м3"
    assert item.raw_characteristics["density_class"] == "D500"
    assert item.raw_documents[0]["type"] == "certificate"
    assert item.raw_images == ("https://vkblock.ru/image.jpg",)
    assert item.raw_payload["legacy_entity"] == "CatalogProduct"


def test_supplier_upload_row_builds_file_raw_ingestion_item() -> None:
    row = SimpleNamespace(
        upload_id="upload-1",
        raw_name="ГКЛ влагостойкий 2500х1200х12.5",
        raw_category="ГКЛ",
        raw_price="390",
        raw_unit="лист",
        row_number=7,
        parsed_data={
            "sourceCode": "SUPPLIER_FILE_UPLOAD",
            "characteristics": {
                "length_mm": 2500,
                "width_mm": 1200,
                "thickness_mm": 12.5,
                "board_type": "moisture_resistant",
            },
            "supplier": "Поставщик",
        },
    )

    item = build_raw_ingestion_item_from_supplier_upload_row(row)

    assert item.legacy_source == "SupplierUploadRow"
    assert item.source_code == "SUPPLIER_FILE_UPLOAD"
    assert item.source_type == "file"
    assert item.raw_supplier == "Поставщик"
    assert item.raw_payload["row_number"] == 7


def test_source_task_result_builds_raw_item_from_payload() -> None:
    result = SimpleNamespace(
        entity_type="catalog_product",
        source_id="source-task-source",
        created_at=datetime(2026, 7, 2, 9, 0),
        new_value={
            "sourceCode": "YUFO_DOSKA_BRUS",
            "title": "Доска 50х150х3000",
            "category": "Пиломатериалы",
            "price": "850",
            "unit": "шт",
            "characteristics": {
                "length_mm": 3000,
                "width_mm": 150,
                "thickness_mm": 50,
            },
            "adapterVersion": "test-adapter-v1",
        },
    )

    item = build_raw_ingestion_item_from_source_task_result(result)

    assert item.legacy_source == "SourceTaskResult"
    assert item.source_code == "YUFO_DOSKA_BRUS"
    assert item.raw_title == "Доска 50х150х3000"
    assert item.adapter_version == "test-adapter-v1"
    assert item.raw_payload["legacy_entity"] == "SourceTaskResult"


def test_validate_raw_ingestion_item_reports_missing_title_and_unknown_unit() -> None:
    item = Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="BAUCENTER",
        raw_unit="parsec",
    )

    report = validate_raw_ingestion_item(item)

    assert report.is_valid is False
    assert report.missing_fields == ("raw_title",)
    assert report.unit_warnings == ("raw_unit 'parsec' is not recognized",)


def test_enrich_with_source_profile_adds_profile_reference_and_source_data() -> None:
    item = Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="YUFO_VKBLOCK",
        raw_title="Газоблок",
        raw_unit="шт",
    )

    enriched = enrich_raw_ingestion_with_source_profile(item)

    assert enriched.source_type == "manufacturer_site"
    assert enriched.source_url == "https://vkblock.ru/"
    assert enriched.extraction_profile_reference == "yufo_vkblock_extraction_profile"
    assert enriched.warnings == ()


def test_enrich_with_extraction_blueprint_reports_missing_required_fields() -> None:
    item = Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="YUFO_VKBLOCK",
        raw_title="Газоблок",
        raw_unit="шт",
        raw_characteristics={"length_mm": 600},
    )

    enriched = enrich_raw_ingestion_with_extraction_blueprint(item, "aerated_concrete_block")

    assert enriched.extraction_profile_reference == "aerated_concrete_block_blueprint"
    assert any("missing required extraction fields" in warning for warning in enriched.warnings)


def test_readiness_report_uses_source_profile_and_blueprint() -> None:
    item = Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="YUFO_VKBLOCK",
        raw_title="Газоблок D500",
        raw_unit="шт",
        raw_characteristics={
            "length_mm": 600,
            "width_mm": 300,
            "height_mm": 200,
            "density_class": "D500",
            "strength_class": "B2.5",
        },
    )

    report = build_raw_ingestion_readiness_report(item, "aerated_concrete_block")

    assert report.ready is True
    assert report.has_source_profile is True
    assert report.has_extraction_profile is True
    assert report.has_extraction_blueprint is True
    assert report.missing_raw_fields == ()
    assert report.missing_blueprint_fields == ()


def test_readiness_report_blocks_unknown_source_and_missing_blueprint_fields() -> None:
    item = Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="UNKNOWN",
        raw_title="Материал",
        raw_unit="шт",
        raw_characteristics={"length_mm": 600},
    )

    report = build_raw_ingestion_readiness_report(item, "aerated_concrete_block")

    assert report.ready is False
    assert report.has_source_profile is False
    assert report.has_extraction_profile is False
    assert "width_mm" in report.missing_blueprint_fields


def test_supported_raw_sources_are_explicit() -> None:
    assert list_supported_raw_sources() == ("CatalogProduct", "SupplierUploadRow", "SourceTaskResult", "raw_payload")



def test_raw_ingestion_item_allows_missing_price_for_source_evidence() -> None:
    item = Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="YUFO_VKBLOCK",
        raw_title="Страница газоблока без цены",
        raw_unit="шт",
        raw_price=None,
        raw_documents=({"url": "https://example.test/cert.pdf", "type": "certificate"},),
    )

    report = validate_raw_ingestion_item(item)

    assert item.raw_price is None
    assert item.raw_documents[0]["type"] == "certificate"
    assert report.is_valid is True

def test_raw_ingestion_pipeline_does_not_import_orm_or_adapters_or_create_materials() -> None:
    source = Path("app/services/module1_raw_ingestion_pipeline.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "source_task_runner" not in source
    assert "source_integrations" not in source
    assert "app.services.source_adapters" not in source
    assert "CatalogProduct(" not in source
    assert "Material(" not in source
    assert "CanonicalMaterial" not in source
