from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    build_canonical_material_update_plan,
    build_canonical_material_view,
    build_material_characteristics_view,
    build_material_evidence_summary,
    build_material_quality_summary,
    get_canonical_material,
    list_canonical_materials,
    validate_canonical_material_update,
)


def _enum(value: str) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _material(**overrides) -> SimpleNamespace:
    category = SimpleNamespace(id="cat-blocks", name="Blocks", slug="blocks", status="ACTIVE")
    subcategory = SimpleNamespace(id="sub-aerated", name="Aerated concrete", slug="aerated", status="ACTIVE")
    material_type = SimpleNamespace(id="type-gas-block", name="Gas block", code="aerated_concrete_block")
    unit = SimpleNamespace(id="unit-piece", name="Piece", abbreviation="pcs", unit_type=_enum("COUNT"))
    source = SimpleNamespace(id="source-baucenter", name="Baucenter", url="https://example.test")
    supplier = SimpleNamespace(id="supplier-1", name="Supplier One")
    base = {
        "id": "mat-001",
        "canonical_name": "Aerated concrete block D500 600x300x200",
        "category": category,
        "category_id": category.id,
        "subcategory": subcategory,
        "subcategory_id": subcategory.id,
        "material_type": material_type,
        "material_type_id": material_type.id,
        "base_unit": unit,
        "base_unit_id": unit.id,
        "article": "GB-D500",
        "brand": "ATOM",
        "manufacturer": "Factory",
        "description": "Wall block",
        "status": _enum("ACTIVE"),
        "created_at": datetime(2026, 7, 1, 10, 0),
        "updated_at": datetime(2026, 7, 2, 11, 30),
        "attributes": [
            SimpleNamespace(attribute_name="length_mm", attribute_value="600", unit=SimpleNamespace(abbreviation="mm"), sort_order=1),
            SimpleNamespace(attribute_name="width_mm", attribute_value="300", unit=SimpleNamespace(abbreviation="mm"), sort_order=2),
            SimpleNamespace(attribute_name="height_mm", attribute_value="200", unit=SimpleNamespace(abbreviation="mm"), sort_order=3),
        ],
        "specifications": [
            SimpleNamespace(
                template=SimpleNamespace(title="Density"),
                value="D500",
                unit=None,
                source=source,
                source_id=source.id,
                confidence=Decimal("0.95"),
                verified_status=_enum("VERIFIED"),
            )
        ],
        "documents": [
            SimpleNamespace(
                id="doc-1",
                title="Certificate",
                document_type=_enum("CERTIFICATE"),
                status=_enum("ACTIVE"),
                file_url="/files/cert.pdf",
                source_url=None,
                issue_date=date(2026, 1, 10),
                expiry_date=date(2027, 1, 10),
            )
        ],
        "catalog_products": [
            SimpleNamespace(
                id="cat-product-1",
                source=source,
                source_id=source.id,
                external_url="https://example.test/item",
                raw_name="Raw supplier title",
                normalized_name="Aerated concrete block D500",
                match_confidence=Decimal("0.93"),
                status=_enum("NEEDS_REVIEW"),
            )
        ],
        "supplier_prices": [
            SimpleNamespace(
                id="price-1",
                supplier=supplier,
                supplier_id=supplier.id,
                price=Decimal("123.45"),
                currency="RUB",
                unit="pcs",
                region="Krasnodar",
                availability="in_stock",
                valid_until=date(2026, 8, 1),
            )
        ],
        "quality_issues": [],
    }
    base.update(overrides)
    return SimpleNamespace(**base)



def _supplier_price(price: Decimal | None, price_id: str = "price-custom") -> SimpleNamespace:
    supplier = SimpleNamespace(id="supplier-1", name="Supplier One")
    return SimpleNamespace(
        id=price_id,
        supplier=supplier,
        supplier_id=supplier.id,
        price=price,
        currency="RUB",
        unit="pcs",
        region="Krasnodar",
        availability="in_stock",
        valid_until=date(2026, 8, 1),
    )
def test_existing_material_is_exposed_as_canonical_compatibility_view() -> None:
    view = build_canonical_material_view(_material())

    assert isinstance(view, MaterialCanonicalView)
    assert view.material_id == "mat-001"
    assert view.canonical_name == "Aerated concrete block D500 600x300x200"
    assert view.category["name"] == "Blocks"
    assert view.subcategory["name"] == "Aerated concrete"
    assert view.group["code"] == "aerated_concrete_block"
    assert view.status == "ACTIVE"
    assert view.moderation_status == "approved"
    assert view.source_provenance["canonicalBase"] == "Material"
    assert view.source_provenance["rawDataIsCanonical"] is False
    assert "raw_payload" not in view.source_provenance


def test_characteristics_evidence_supplier_prices_and_quality_are_human_readable() -> None:
    material = _material(
        quality_issues=[
            SimpleNamespace(
                id="issue-1",
                issue_type="missing_document",
                severity="HIGH",
                reason="Need declaration",
                status="OPEN",
                created_at=datetime(2026, 7, 3, 9, 0),
            )
        ]
    )

    characteristics = build_material_characteristics_view(material)
    evidence = build_material_evidence_summary(material)
    quality = build_material_quality_summary(material)
    view = build_canonical_material_view(material)

    assert [item.name for item in characteristics][:3] == ["length_mm", "width_mm", "height_mm"]
    assert any(item.name == "Density" and item.value == "D500" for item in characteristics)
    assert evidence.document_count == 1
    assert evidence.source_ref_count == 1
    assert evidence.documents[0]["title"] == "Certificate"
    assert evidence.source_refs[0]["rawTitle"] == "Raw supplier title"
    assert quality.status == "needs_review"
    assert quality.critical_issues == 1
    assert view.supplier_price_refs[0]["price"] == "123.45"
    assert view.quality.open_issues == 1
    assert view.moderation_status == "needs_review"


def test_get_and_list_canonical_materials_filter_existing_material_snapshots() -> None:
    target = _material(id="mat-target", canonical_name="Gas block")
    other = _material(id="mat-other", canonical_name="Concrete mix", documents=[], quality_issues=[])

    found = get_canonical_material("mat-target", materials=[target, other])
    listed = list_canonical_materials({"search": "gas", "has_documents": True}, materials=[target, other])

    assert found is not None
    assert found.material_id == "mat-target"
    assert [item.material_id for item in listed] == ["mat-target"]


def test_update_validation_blocks_raw_source_payload_and_sanitizes_canonical_fields() -> None:
    validation = validate_canonical_material_update(
        {
            "canonical_name": "Updated material name",
            "brand": "New brand",
            "raw_payload": {"unsafe": True},
            "source_task_result": {"id": "raw-1"},
            "unknown_field": "ignored",
        }
    )

    assert validation.is_valid is True
    assert validation.sanitized_payload == {
        "canonical_name": "Updated material name",
        "brand": "New brand",
    }
    assert validation.blocked_fields == ("raw_payload", "source_task_result")
    assert any("Unsupported field ignored" in warning for warning in validation.warnings)
    assert any("blocked" in warning for warning in validation.warnings)


def test_update_plan_is_manual_preview_without_auto_apply_or_moderation_side_effects() -> None:
    plan = build_canonical_material_update_plan(
        _material(),
        {"canonical_name": "Updated material name", "description": "Updated description"},
    )

    assert plan.material_id == "mat-001"
    assert plan.no_side_effects is True
    assert plan.requires_manual_save is True
    assert plan.source_preview_only is True
    assert plan.sanitized_payload["canonical_name"] == "Updated material name"
    assert any("Set canonical_name" in operation for operation in plan.operations_preview)
    assert any("No moderation decision is auto-applied" in warning for warning in plan.warnings)


def test_moderation_preview_is_attached_only_as_evidence_not_canonical_data() -> None:
    view = build_canonical_material_view(
        _material(),
        moderation_preview_refs=[
            {
                "queueItemId": "queue-1",
                "decisionHint": "strong_match",
                "confidence": "94.00",
            }
        ],
    )

    assert view.evidence.moderation_preview_refs[0]["queueItemId"] == "queue-1"
    assert view.evidence.source_ref_count == 2
    assert view.source_provenance["rawDataIsCanonical"] is False



def test_canonical_store_keeps_legacy_records_but_warns_without_positive_price_observation() -> None:
    no_price = _material(id="mat-no-price", supplier_prices=[])
    zero_price = _material(id="mat-zero-price", supplier_prices=[_supplier_price(Decimal("0"), "price-zero")])
    negative_price = _material(id="mat-negative-price", supplier_prices=[_supplier_price(Decimal("-1"), "price-negative")])
    positive_price = _material(id="mat-positive-price", supplier_prices=[_supplier_price(Decimal("1"), "price-positive")])

    blocked_views = [build_canonical_material_view(material) for material in (no_price, zero_price, negative_price)]
    positive_view = build_canonical_material_view(positive_price)
    listed = list_canonical_materials(materials=(no_price, zero_price, negative_price, positive_price))

    assert all("No positive price observation is linked." in view.warnings for view in blocked_views)
    assert "No positive price observation is linked." not in positive_view.warnings
    assert {view.material_id for view in listed} == {
        "mat-no-price",
        "mat-zero-price",
        "mat-negative-price",
        "mat-positive-price",
    }
def test_canonical_material_store_does_not_define_parallel_orm_or_auto_apply() -> None:
    source = Path("app/services/module1_canonical_material_store.py").read_text(encoding="utf-8")

    assert "class CanonicalMaterial" not in source
    assert "__tablename__" not in source
    assert "\"canonical_materials\"" not in source
    assert "'canonical_materials'" not in source
    assert ".commit(" not in source
    assert ".add(" not in source
    assert "source_task_runner" not in source
    assert "apply_moderation" not in source
