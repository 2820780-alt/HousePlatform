from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.catalog_product import CatalogProduct
from app.models.enums import CatalogProductStatus, SourceActionType, TaskResultType
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.source_task_result import SourceTaskResult
from app.services import source_task_runner as runner
from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_data_quality_dashboard import (
    build_data_quality_dashboard_report,
    build_material_quality_snapshot,
)
from app.services.module1_export_packages import (
    build_bulk_export_report,
    build_export_readiness_report,
    build_material_export_bundle,
    build_module5_estimate_input_hint_package,
)
from app.services.module1_matching_dedup import (
    MaterialMatchCandidateDTO,
    build_match_candidate,
)
from app.services.module1_material_normalizer import (
    NormalizedMaterialCandidate,
    build_normalization_report,
)
from app.services.module1_moderation_core import (
    MaterialModerationDecision,
    build_moderation_queue_item,
    validate_moderation_decision,
)
from app.services.module1_raw_ingestion_pipeline import (
    Module1RawIngestionItem,
    validate_raw_ingestion_item,
)
from app.source_integrations.base import SourceProduct


class FakeDB:
    def __init__(self):
        self.added = []
        self.flushes = 0

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushes += 1


class FakeIntegration:
    def __init__(self, products):
        self._products = products

    async def fetch_products(self, action_type, parameters):
        return list(self._products)


def _task():
    source = SimpleNamespace(
        id=uuid4(),
        name="Test Source",
        url="https://example.test/catalog",
        source_type="supplier_site",
        status=None,
        last_price_update_at=None,
    )
    return SimpleNamespace(
        id=uuid4(),
        source_id=source.id,
        source=source,
        action_type=SourceActionType.UPDATE_PRICES,
        parameters={},
        result_summary=None,
    )


def _product(price):
    return SourceProduct(
        external_id="p-1",
        external_url="https://example.test/product/p-1",
        raw_name="Gas block D500 600x300x200",
        raw_category="Aerated concrete blocks",
        price=price,
        currency="RUB",
        unit="m3",
        availability="in_stock",
        region="Krasnodar krai",
    )


def _raw_item(price=None) -> Module1RawIngestionItem:
    return Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="YUFO_VKBLOCK",
        source_type="manufacturer_site",
        source_url="https://example.test/product/p-1",
        raw_title="Gas block D500 600x300x200",
        raw_category="Aerated concrete blocks",
        raw_price=price,
        raw_unit="piece",
        raw_characteristics={
            "length_mm": 600,
            "width_mm": 300,
            "height_mm": 200,
            "density_class": "D500",
            "strength_class": "B2.5",
            "frost_resistance": "F35",
            "thermal_conductivity": "0.12",
            "pieces_per_m3": 27.8,
            "volume_per_piece_m3": "0.036",
        },
        raw_documents=({"url": "https://example.test/cert.pdf", "type": "certificate"},),
        captured_at=datetime(2026, 7, 1, 10, 0),
        observed_at=datetime(2026, 7, 1, 10, 0),
    )


def _candidate(price_hint=None) -> NormalizedMaterialCandidate:
    return NormalizedMaterialCandidate(
        normalized_title="Gas block D500 600x300x200",
        source_title="Gas block D500 600x300x200",
        suggested_group_code="aerated_concrete_block",
        suggested_category=None,
        manufacturer=None,
        brand=None,
        normalized_characteristics={
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
        normalized_unit="piece",
        price_hint=price_hint,
        source_metadata={
            "source_code": "TEST_SOURCE",
            "source_type": "supplier_site",
            "source_url": "https://example.test/item",
        },
        confidence=Decimal("0.95"),
        warnings=(),
        missing_required_fields=(),
        module2_missing_fields=(),
        evidence={
            "raw_title": "Gas block D500 600x300x200",
            "raw_category": "aerated_concrete_block",
            "raw_documents": ({"url": "https://example.test/cert.pdf", "type": "certificate"},),
            "raw_images": (),
        },
    )


def _existing_material_reference():
    return {
        "id": "mat-gas-001",
        "canonical_name": "Gas block D500 600x300x200",
        "group_code": "aerated_concrete_block",
        "normalized_characteristics": {
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
        "unit": "piece",
    }


def _char(name: str, value, unit: str | None = None) -> MaterialCharacteristicView:
    return MaterialCharacteristicView(name=name, value=value, unit=unit)


def _canonical_view(price: str | None, material_id: str = "mat-001") -> MaterialCanonicalView:
    price_refs = ()
    if price is not None:
        price_refs = (
            {
                "priceId": f"price-{material_id}",
                "supplierId": "supplier-1",
                "supplierName": "Supplier One",
                "price": price,
                "currency": "RUB",
                "unit": "m3",
                "region": "Krasnodar krai",
                "validUntil": "2026-08-01",
                "observedAt": "2026-07-01",
            },
        )
    return MaterialCanonicalView(
        material_id=material_id,
        canonical_name="Gas block D500 B2.5",
        category={"slug": "aerated_concrete_block", "name": "aerated_concrete_block"},
        subcategory={"slug": "wall_blocks", "name": "Wall blocks"},
        group={"code": "aerated_concrete_block", "name": "aerated_concrete_block"},
        characteristics=(
            _char("length_mm", 600),
            _char("width_mm", 300),
            _char("height_mm", 200),
            _char("density_class", "D500"),
            _char("strength_class", "B2.5"),
            _char("frost_resistance", "F35"),
            _char("thermal_conductivity", "0.12"),
            _char("pieces_per_m3", 27.8),
            _char("volume_per_piece_m3", "0.036"),
            _char("weight_per_piece_kg", "18"),
            _char("pieces_per_pallet", 60),
            _char("package_unit", "pallet"),
        ),
        technical_profile_hints={"baseUnit": {"abbreviation": "m3"}},
        evidence=MaterialEvidenceSummary(
            document_count=1,
            source_ref_count=1,
            documents=(
                {
                    "documentId": "doc-cert",
                    "title": "Certificate",
                    "documentType": "certificate",
                    "fileUrl": "https://example.test/cert.pdf",
                    "status": "active",
                },
            ),
            source_refs=(
                {
                    "sourceId": "source-1",
                    "sourceCode": "YUFO_VKBLOCK",
                    "sourceName": "Manufacturer source",
                    "sourceType": "manufacturer_site",
                    "externalUrl": "https://example.test/item",
                },
            ),
            moderation_preview_refs=tuple(),
            warnings=tuple(),
        ),
        supplier_price_refs=price_refs,
        moderation_status="approved",
        quality=MaterialQualitySummary(
            status="ok",
            open_issues=0,
            critical_issues=0,
            warning_issues=0,
            issues=tuple(),
            warnings=tuple(),
        ),
        source_provenance={
            "canonicalBase": "Material",
            "rawDataIsCanonical": False,
            "manufacturer": "Bonolit",
            "brand": "Bonolit",
        },
        status="ACTIVE",
        warnings=tuple(),
        created_at=None,
        updated_at=None,
    )


@pytest.mark.parametrize(
    ("price", "reason"),
    [
        (None, "missing_price"),
        (Decimal("0"), "invalid_or_non_positive_price"),
        (Decimal("-1"), "invalid_or_non_positive_price"),
        ("not-a-number", "invalid_or_non_positive_price"),
    ],
)
@pytest.mark.asyncio
async def test_source_product_without_positive_price_stays_raw_evidence_before_catalog_product(
    monkeypatch, price, reason
) -> None:
    async def fail_upsert(*args, **kwargs):
        pytest.fail("Non-positive SourceProduct must not reach CatalogProduct upsert")

    async def fail_match(*args, **kwargs):
        pytest.fail("Non-positive SourceProduct must not reach material matching")

    monkeypatch.setattr(runner, "_upsert_catalog_product", fail_upsert)
    monkeypatch.setattr(runner, "_match_or_queue_material", fail_match)

    db = FakeDB()
    task = _task()

    await runner._run_product_scan(db, task, FakeIntegration([_product(price)]))

    assert not any(isinstance(item, CatalogProduct) for item in db.added)
    assert not any(isinstance(item, MaterialMatchCandidate) for item in db.added)

    results = [item for item in db.added if isinstance(item, SourceTaskResult)]
    assert len(results) == 1
    assert results[0].status == "rejected_no_positive_price"
    assert results[0].result_type == TaskResultType.NEEDS_REVIEW
    assert results[0].new_value["rejection_reason"] == reason
    assert task.result_summary["rejected_no_price"] == 1
    assert task.result_summary["created"] == 0
    assert task.result_summary["match_candidates"] == 0


@pytest.mark.asyncio
async def test_positive_source_product_preserves_catalog_product_and_candidate_path(monkeypatch) -> None:
    calls = {"upsert": 0, "match": 0}
    catalog_product = CatalogProduct(
        id=uuid4(),
        source_id=uuid4(),
        external_id="p-1",
        external_url="https://example.test/product/p-1",
        raw_name="Gas block D500 600x300x200",
        normalized_name="gas block d500 600x300x200",
        price=Decimal("1250.00"),
        currency="RUB",
        unit="m3",
        status=CatalogProductStatus.NEEDS_REVIEW,
    )

    async def fake_upsert(db, task, product):
        calls["upsert"] += 1
        return catalog_product, TaskResultType.CREATED, False

    async def fake_match(db, product):
        calls["match"] += 1
        return "candidate"

    monkeypatch.setattr(runner, "_upsert_catalog_product", fake_upsert)
    monkeypatch.setattr(runner, "_match_or_queue_material", fake_match)

    db = FakeDB()
    task = _task()

    await runner._run_product_scan(db, task, FakeIntegration([_product(Decimal("1250.00"))]))

    assert calls == {"upsert": 1, "match": 1}
    assert task.result_summary["created"] == 1
    assert task.result_summary["match_candidates"] == 1
    assert task.result_summary["rejected_no_price"] == 0


@pytest.mark.asyncio
async def test_existing_positive_catalog_product_is_not_zeroed_by_later_no_price_scan(monkeypatch) -> None:
    existing = CatalogProduct(
        id=uuid4(),
        source_id=uuid4(),
        external_id="p-1",
        external_url="https://example.test/product/p-1",
        raw_name="Gas block D500 600x300x200",
        normalized_name="gas block d500 600x300x200",
        price=Decimal("1250.00"),
        currency="RUB",
        unit="m3",
        status=CatalogProductStatus.ACTIVE,
    )

    async def fake_find_catalog_product(db, source_id, product):
        return existing

    monkeypatch.setattr(runner, "_find_catalog_product", fake_find_catalog_product)

    db = FakeDB()
    task = _task()

    result, result_type, price_changed = await runner._upsert_catalog_product(db, task, _product(None))

    assert result is existing
    assert result_type == TaskResultType.UNCHANGED
    assert price_changed is False
    assert existing.price == Decimal("1250.00")
    assert not any(isinstance(item, MaterialMatchCandidate) for item in db.added)


def test_raw_normalizer_matching_and_moderation_block_new_material_without_positive_price() -> None:
    raw_item = _raw_item(price=None)
    validation = validate_raw_ingestion_item(raw_item)
    normalization = build_normalization_report(raw_item)

    assert validation.is_valid is True
    assert raw_item.raw_documents
    assert normalization.candidate is not None
    assert normalization.is_ready_for_matching is False
    assert "missing positive price" in normalization.warnings

    match = build_match_candidate(_candidate(price_hint=None), [])

    assert match.decision_hint == "price_required_review"
    assert match.decision_hint != "new_material_candidate"
    assert match.matched_material_reference is None

    forced_new_material = MaterialMatchCandidateDTO(
        candidate_id="match_no_price_material_001",
        normalized_candidate_snapshot={
            "normalized_title": "new no price material",
            "suggested_group_code": "dry_mix",
            "module2_missing_fields": (),
            "price_hint": None,
        },
        matched_material_reference=None,
        confidence=Decimal("82"),
        decision_hint="new_material_candidate",
        explanation=("Candidate has no safe existing material match.",),
        conflicting_fields=(),
        missing_fields=(),
        evidence_refs={"raw_title": "new no price material"},
        source_refs={"source_code": "TEST_SOURCE"},
        score_breakdown={},
    )
    queue_item = build_moderation_queue_item(forced_new_material)
    decision = MaterialModerationDecision(
        decision_type="create_new_material_candidate",
        moderator_id="moderator-1",
        confirmed=True,
    )
    moderation_validation = validate_moderation_decision(queue_item, decision)

    assert "create_new_material_candidate" not in queue_item.allowed_decisions
    assert moderation_validation.is_valid is False


def test_existing_material_enrichment_allows_no_price_evidence_without_new_material_creation() -> None:
    match = build_match_candidate(_candidate(price_hint=None), [_existing_material_reference()])
    queue_item = build_moderation_queue_item(match)
    decision = MaterialModerationDecision(
        decision_type="accept_match",
        moderator_id="moderator-1",
        confirmed=True,
    )
    validation = validate_moderation_decision(queue_item, decision)

    assert match.matched_material_reference is not None
    assert match.matched_material_reference["id"] == "mat-gas-001"
    assert match.decision_hint in {"exact_match", "strong_match"}
    assert match.evidence_refs["raw_documents"]
    assert "accept_match" in queue_item.allowed_decisions
    assert "create_new_material_candidate" not in queue_item.allowed_decisions
    assert validation.is_valid is True


def test_canonical_export_and_quality_require_positive_price_without_deleting_legacy_records() -> None:
    no_price = _canonical_view(None, material_id="mat-no-price")
    zero_price = _canonical_view("0", material_id="mat-zero-price")
    negative_price = _canonical_view("-10", material_id="mat-negative-price")
    positive_price = _canonical_view("125.50", material_id="mat-positive-price")
    legacy_records = (positive_price, no_price, zero_price, negative_price)

    for view in (no_price, zero_price, negative_price):
        readiness = build_export_readiness_report(view)
        module5_package = build_module5_estimate_input_hint_package(view)
        bundle = build_material_export_bundle(view)
        quality = build_material_quality_snapshot(view)

        assert readiness.blocked_by_missing_positive_price is True
        assert readiness.ready_for_module2 is False
        assert readiness.ready_for_module5_selection is False
        assert module5_package.price_observation_refs == tuple()
        assert bundle.validation_report.is_valid is False
        assert quality.module2_readiness["ready"] is False
        assert quality.module5_readiness_hint["readyHint"] is False

    positive_readiness = build_export_readiness_report(positive_price)
    positive_bundle = build_material_export_bundle(positive_price)

    assert positive_readiness.blocked_by_missing_positive_price is False
    assert positive_readiness.ready_for_module2 is True
    assert positive_readiness.ready_for_module5_selection is True
    assert positive_bundle.validation_report.is_valid is True

    bulk_report = build_bulk_export_report(legacy_records)
    quality_report = build_data_quality_dashboard_report(legacy_records)
    issue_types = set(quality_report.count_by_issue_type)

    assert bulk_report["totalMaterials"] == 4
    assert bulk_report["materialIds"] == (
        "mat-positive-price",
        "mat-no-price",
        "mat-zero-price",
        "mat-negative-price",
    )
    assert bulk_report["byReadiness"]["readyForModule2"] == 1
    assert bulk_report["byReadiness"]["readyForModule5Selection"] == 1
    assert bulk_report["byReadiness"]["blockedByMissingPositivePrice"] == 3
    assert quality_report.total_materials_checked == 4
    assert "missing_price_observation" in issue_types or "missing_positive_price_observation" in issue_types
    assert len(legacy_records) == 4
