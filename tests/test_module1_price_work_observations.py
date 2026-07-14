from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_price_work_observations import (
    MaterialPriceObservation,
    build_observation_readiness_report,
    build_price_observation_from_catalog_product,
    build_price_observation_from_price_history,
    build_price_observation_from_raw_ingestion,
    build_price_observation_from_supplier_price,
    build_price_observation_package,
    build_work_rate_observation,
    build_work_rate_observation_package,
    classify_observation_type,
    deduplicate_price_observations,
    normalize_observation_currency,
    normalize_observation_unit,
    validate_price_observation,
    validate_work_rate_observation,
)
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem


def _enum(value: str) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _canonical_view(
    *,
    supplier_price_refs: tuple[dict, ...] = tuple(),
    group_code: str = "aerated_concrete_block",
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
            document_count=0,
            source_ref_count=0,
            documents=tuple(),
            source_refs=tuple(),
            moderation_preview_refs=tuple(),
            warnings=tuple(),
        ),
        supplier_price_refs=supplier_price_refs,
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


def test_supplier_price_shape_builds_material_price_observation() -> None:
    supplier = SimpleNamespace(id="supplier-1", name="Supplier One")
    source = SimpleNamespace(id="source-1", name="Supplier site", source_type=_enum("supplier_site"), url="https://supplier.test")
    catalog_product = SimpleNamespace(id="catalog-1", source=source, external_url="https://supplier.test/item")
    supplier_price = SimpleNamespace(
        id="price-1",
        supplier=supplier,
        supplier_id="supplier-1",
        material_id="mat-001",
        catalog_product=catalog_product,
        price=Decimal("123.45"),
        currency="rub",
        unit="м3",
        region="Krasnodar krai",
        city="Krasnodar",
        valid_until=date(2026, 8, 1),
        created_at=datetime(2026, 7, 1, 12, 30),
        delivery_included=True,
    )

    observation = build_price_observation_from_supplier_price(
        supplier_price,
        material_group="aerated_concrete_block",
        material_name="Aerated concrete block D500",
    )
    report = validate_price_observation(observation)

    assert isinstance(observation, MaterialPriceObservation)
    assert observation.observation_type == "supplier_price"
    assert observation.price_value == Decimal("123.45")
    assert observation.currency == "RUB"
    assert observation.unit_info.normalized_unit == "m3"
    assert observation.participant is not None
    assert observation.participant.display_name == "Supplier One"
    assert observation.source_ref is not None
    assert observation.source_ref.source_name == "Supplier site"
    assert observation.region.region == "Krasnodar krai"
    assert observation.valid_to == "2026-08-01"
    assert observation.delivery_included is True
    assert report.is_valid is True


def test_price_history_shape_is_read_only_observation_input() -> None:
    history = SimpleNamespace(
        id="history-1",
        material_id="mat-001",
        source_id="source-1",
        supplier_id="supplier-1",
        price=Decimal("130.00"),
        currency="RUB",
        unit="шт",
        region="Krasnodar krai",
        collected_at=datetime(2026, 7, 2, 9, 0),
        price_date=date(2026, 7, 2),
    )

    observation = build_price_observation_from_price_history(
        history,
        material_group="aerated_concrete_block",
        material_name="Aerated concrete block D500",
    )

    assert observation.observation_type == "material_price"
    assert observation.price_value == Decimal("130.00")
    assert observation.unit_info.normalized_unit == "piece"
    assert observation.source_ref is not None
    assert observation.source_ref.source_id == "source-1"
    assert observation.valid_from == "2026-07-02"


def test_catalog_product_and_raw_ingestion_create_catalog_price_observations_without_parsing() -> None:
    catalog_observation = build_price_observation_from_catalog_product(
        {
            "id": "catalog-1",
            "raw_name": "Raw title",
            "price": "220.50",
            "unit": "мешок",
            "currency": "RUB",
            "region": "Krasnodar krai",
            "updated_at": "2026-07-03T10:00:00",
            "external_url": "https://supplier.test/catalog/item",
        },
        material_group="gypsum_plaster",
    )
    raw_observation = build_price_observation_from_raw_ingestion(
        Module1RawIngestionItem(
            legacy_source="SourceTaskResult",
            source_code="BAUCENTER",
            source_type="supplier_site",
            source_url="https://supplier.test/item",
            raw_title="Dry mix",
            raw_price=Decimal("410.00"),
            raw_unit="кг",
            region="Krasnodar krai",
            observed_at=datetime(2026, 7, 4, 11, 0),
            confidence=Decimal("0.77"),
        ),
        material_id="mat-002",
        material_group="gypsum_plaster",
    )

    assert catalog_observation.observation_type == "catalog_price"
    assert catalog_observation.unit_info.normalized_unit == "bag"
    assert catalog_observation.source_ref is not None
    assert catalog_observation.source_ref.url == "https://supplier.test/catalog/item"
    assert raw_observation.observation_type == "catalog_price"
    assert raw_observation.unit_info.normalized_unit == "kg"
    assert raw_observation.confidence == Decimal("0.77")


def test_work_rate_observation_is_reference_rate_not_estimate() -> None:
    observation = build_work_rate_observation(
        {
            "id": "rate-1",
            "work_type": "plastering",
            "work_code": "PLASTER_M2",
            "usage_context": "interior walls",
            "region": "Krasnodar krai",
            "city": "Krasnodar",
            "rate_value": "650",
            "currency": "RUB",
            "unit": "м2",
            "source_name": "Manual reference",
            "observed_at": "2026-07-05T08:00:00",
        }
    )
    report = validate_work_rate_observation(observation)
    package = build_work_rate_observation_package((observation,))

    assert observation.work_type == "plastering"
    assert observation.rate_value == Decimal("650")
    assert observation.unit_info.normalized_unit == "m2"
    assert report.is_valid is True
    assert package.observations == (observation,)
    assert package.validation_reports[0].is_valid is True


def test_price_observation_package_deduplicates_and_reports_readiness() -> None:
    view = _canonical_view(
        supplier_price_refs=(
            {
                "priceId": "price-1",
                "supplierId": "supplier-1",
                "supplierName": "Supplier One",
                "price": "120.00",
                "currency": "RUB",
                "unit": "м3",
                "region": "Krasnodar krai",
                "validUntil": "2026-08-01",
            },
            {
                "priceId": "price-2",
                "supplierId": "supplier-1",
                "supplierName": "Supplier One",
                "price": "120.00",
                "currency": "RUB",
                "unit": "м3",
                "region": "Krasnodar krai",
                "validUntil": "2026-08-01",
            },
        ),
    )

    package = build_price_observation_package(view)
    readiness = build_observation_readiness_report(view)

    assert len(package.observations) == 1
    assert package.observations[0].price_value == Decimal("120.00")
    assert readiness.has_prices is True
    assert readiness.has_region is True
    assert readiness.has_supported_units is True
    assert readiness.status == "needs_review"
    assert readiness.duplicate_stable_keys


def test_validation_reports_missing_unknown_unit_and_suspicious_price() -> None:
    observation = build_price_observation_from_catalog_product(
        {
            "id": "catalog-suspicious",
            "price": "0",
            "unit": "unknown-unit",
            "currency": "RUB",
            "updated_at": "2026-07-03T10:00:00",
        },
        material_group="aerated_concrete_block",
    )

    report = validate_price_observation(observation)

    assert report.is_valid is False
    assert report.suspicious is True
    assert "supported_unit" in report.missing_fields
    assert "region" in report.missing_fields
    assert "Unit 'unknown-unit' is not supported" in " ".join(report.warnings)


def test_deduplicate_price_observations_merges_provenance_without_writing_db() -> None:
    first = build_price_observation_from_catalog_product(
        {
            "id": "catalog-1",
            "price": "100",
            "unit": "kg",
            "region": "Krasnodar krai",
            "updated_at": "2026-07-03T10:00:00",
        },
        material_id="mat-1",
    )
    duplicate = build_price_observation_from_catalog_product(
        {
            "id": "catalog-2",
            "price": "100",
            "unit": "kg",
            "region": "Krasnodar krai",
            "updated_at": "2026-07-03T10:00:00",
        },
        material_id="mat-1",
    )

    deduped = deduplicate_price_observations((first, duplicate))

    assert len(deduped) == 1
    assert "Duplicate price observation merged." in deduped[0].warnings


def test_observation_normalization_helpers_support_contract_values() -> None:
    assert normalize_observation_unit("м.п.").normalized_unit == "linear_meter"
    assert normalize_observation_unit("м2").normalized_unit == "m2"
    assert normalize_observation_unit("bad-unit").is_supported is False
    assert normalize_observation_currency("rur") == "RUB"
    assert classify_observation_type("SupplierPrice") == "supplier_price"
    assert classify_observation_type("regional_average") == "regional_average_hint"
    assert classify_observation_type("delivery") == "delivery_price_hint"


def test_price_work_observations_service_is_read_only_and_not_module5_or_module11() -> None:
    source = Path("app/services/module1_price_work_observations.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "module5" not in source.lower()
    assert "module11" not in source.lower()
    assert "dashboard_" not in source.lower()
    assert "quick_action" not in source.lower()
    assert "requests." not in source
    assert "httpx." not in source
