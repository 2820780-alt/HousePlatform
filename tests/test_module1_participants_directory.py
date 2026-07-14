from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_participants_directory import (
    MaterialParticipantRecord,
    build_participant_directory_package,
    build_participant_readiness_report,
    build_participant_record_from_material_ref,
    build_participant_record_from_price_ref,
    build_participant_record_from_source,
    build_participant_record_from_supplier,
    build_participant_source_links,
    deduplicate_participant_records,
    list_participants_for_material,
    normalize_participant_name,
    normalize_participant_type,
)


def _canonical_view(
    *,
    supplier_price_refs: tuple[dict, ...] = tuple(),
    source_refs: tuple[dict, ...] = tuple(),
    source_provenance: dict | None = None,
    technical_profile_hints: dict | None = None,
) -> MaterialCanonicalView:
    return MaterialCanonicalView(
        material_id="mat-001",
        canonical_name="Aerated concrete block D500",
        category={"slug": "aerated_concrete_block", "name": "Blocks"},
        subcategory=None,
        group={"code": "aerated_concrete_block", "name": "Aerated concrete"},
        characteristics=tuple(),
        technical_profile_hints=technical_profile_hints or {},
        evidence=MaterialEvidenceSummary(
            document_count=0,
            source_ref_count=len(source_refs),
            documents=tuple(),
            source_refs=source_refs,
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
        source_provenance=source_provenance
        or {
            "canonicalBase": "Material",
            "rawDataIsCanonical": False,
            "manufacturer": "Bonolit",
            "brand": "Bonolit D500",
        },
        status="ACTIVE",
        warnings=tuple(),
        created_at=None,
        updated_at=None,
    )


def test_build_participant_record_from_supplier_uses_legacy_supplier_shape() -> None:
    supplier = SimpleNamespace(
        id="supplier-1",
        name="  Supplier One  ",
        inn="2300000000",
        site="https://supplier.example.test",
        email="sales@supplier.example.test",
        phone="+7 861 000-00-00",
        region="Krasnodar krai",
        city="Krasnodar",
        address="Industrial street, 1",
        status=SimpleNamespace(value="ACTIVE"),
    )

    participant = build_participant_record_from_supplier(
        supplier,
        material_id="mat-001",
        material_group="aerated_concrete_block",
        material_name="Aerated concrete block D500",
    )

    assert isinstance(participant, MaterialParticipantRecord)
    assert participant.participant_type == "supplier"
    assert participant.participant_id == "supplier-1"
    assert participant.display_name == "Supplier One"
    assert participant.supplier_name == "Supplier One"
    assert participant.contacts.email == "sales@supplier.example.test"
    assert participant.contacts.site == "https://supplier.example.test"
    assert participant.regions[0].region == "Krasnodar krai"
    assert participant.material_links[0].relation == "supplier"
    assert participant.confidence == Decimal("0.90")


def test_build_participant_record_from_source_creates_source_data_record() -> None:
    source = SimpleNamespace(
        id="source-1",
        name="Manufacturer website",
        source_type=SimpleNamespace(value="manufacturer_site"),
        url="https://manufacturer.example.test",
        region="Krasnodar krai",
        status=SimpleNamespace(value="ACTIVE"),
    )

    participant = build_participant_record_from_source(
        source,
        material_id="mat-001",
        material_group="aerated_concrete_block",
    )

    assert participant.participant_type == "manufacturer"
    assert participant.display_name == "Manufacturer website"
    assert participant.manufacturer_name == "Manufacturer website"
    assert participant.source_links[0].source_id == "source-1"
    assert participant.source_links[0].source_type == "manufacturer_site"
    assert build_participant_source_links(participant) == participant.source_links


def test_material_and_price_refs_create_brand_manufacturer_supplier_records_without_price_calculation() -> None:
    brand = build_participant_record_from_material_ref(
        {"brand": "Grand Line"},
        material_id="mat-roof",
        material_group="metal_tile",
    )
    price_supplier = build_participant_record_from_price_ref(
        {
            "priceId": "price-1",
            "supplierId": "supplier-1",
            "supplierName": "Roof Distributor",
            "price": "123.45",
            "currency": "RUB",
            "region": "Krasnodar krai",
        },
        material_id="mat-roof",
        material_group="metal_tile",
    )

    assert brand.participant_type == "brand"
    assert brand.brand_name == "Grand Line"
    assert price_supplier.participant_type == "supplier"
    assert price_supplier.related_price_refs[0]["price"] == "123.45"
    assert price_supplier.material_links[0].price_ref_ids == ("price-1",)
    assert price_supplier.regions[0].region == "Krasnodar krai"


def test_directory_package_collects_participants_from_canonical_material_view() -> None:
    view = _canonical_view(
        supplier_price_refs=(
            {
                "priceId": "price-1",
                "supplierId": "supplier-1",
                "supplierName": "Supplier One",
                "region": "Krasnodar krai",
                "price": "120.00",
            },
            {
                "priceId": "price-2",
                "supplierId": "supplier-1",
                "supplierName": "Supplier One",
                "region": "Krasnodar krai",
                "price": "121.00",
            },
        ),
        source_refs=(
            {
                "sourceId": "source-1",
                "sourceName": "Manufacturer source",
                "sourceType": "manufacturer_site",
                "externalUrl": "https://manufacturer.example.test/product",
                "status": "NEEDS_REVIEW",
            },
        ),
    )

    package = build_participant_directory_package(view)
    participants = {item.participant_type: item for item in package.participants}

    assert package.material_id == "mat-001"
    assert package.material_group == "aerated_concrete_block"
    assert "manufacturer" in participants
    assert "brand" in participants
    assert "supplier" in participants
    assert package.readiness.has_supplier is True
    assert package.readiness.has_manufacturer is True
    assert package.readiness.has_brand is True
    assert package.readiness.has_region is True
    assert package.readiness.has_source_evidence is True
    assert any("supplier:id:supplier-1" in key for key in package.readiness.duplicate_stable_keys)


def test_readiness_report_flags_missing_unknown_and_duplicate_participants() -> None:
    view = _canonical_view(
        supplier_price_refs=tuple(),
        source_refs=tuple(),
        source_provenance={"canonicalBase": "Material", "rawDataIsCanonical": False},
    )
    report = build_participant_readiness_report(view)
    unknown = build_participant_record_from_material_ref({"displayName": "Mystery"})
    duplicate_a = build_participant_record_from_material_ref({"supplierName": "Same Supplier"})
    duplicate_b = build_participant_record_from_material_ref({"supplierName": "Same Supplier"})
    deduped = deduplicate_participant_records((duplicate_a, duplicate_b))

    assert report.status == "missing_participants"
    assert "supplier" in report.missing_details
    assert "manufacturer" in report.missing_details
    assert unknown.participant_type == "unknown"
    assert len(deduped) == 1
    assert "Duplicate participant record merged." in deduped[0].warnings


def test_normalization_helpers_keep_supported_participant_contract() -> None:
    assert normalize_participant_type("supplier_site") == "supplier"
    assert normalize_participant_type("manufacturer_site") == "manufacturer"
    assert normalize_participant_type("dealer") == "distributor"
    assert normalize_participant_type("unexpected-system-type") == "unknown"
    assert normalize_participant_name("  Grand   Line ") == "Grand Line"


def test_participants_directory_service_is_read_only_and_not_module3_user_layer() -> None:
    source = Path("app/services/module1_participants_directory.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "Module3" not in source
    assert "create_user" not in source
    assert "rbac" not in source.lower()
    assert "send_request" not in source


def test_list_participants_for_material_returns_deduplicated_records() -> None:
    view = _canonical_view(
        supplier_price_refs=(
            {"priceId": "price-1", "supplierId": "supplier-1", "supplierName": "Supplier One"},
            {"priceId": "price-2", "supplierId": "supplier-1", "supplierName": "Supplier One"},
        ),
        source_refs=tuple(),
    )

    participants = list_participants_for_material(view)
    supplier_records = [item for item in participants if item.participant_type == "supplier"]

    assert len(supplier_records) == 1
    assert {ref["priceId"] for ref in supplier_records[0].related_price_refs} == {"price-1", "price-2"}
