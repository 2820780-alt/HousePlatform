from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.database import engine
from app.main import app
from app.models.catalog_product import CatalogProduct
from app.models.enums import (
    MaterialStatus,
    SourceActionType,
    SourceStatus,
    SourceType,
    TaskStatus,
    UserRole,
)
from app.models.material import Material
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.source_task_result import SourceTaskResult
from app.services.material_normalization_rules import normalize_material_title
from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_documents_evidence import (
    build_document_evidence_from_raw_link,
    validate_document_record,
)
from app.services.module1_export_packages import (
    build_export_readiness_report,
    build_material_export_bundle,
)
from app.services.module1_material_normalizer import build_normalization_report
from app.services.module1_matching_dedup import build_match_candidate
from app.services.module1_moderation_core import build_moderation_queue_item
from app.services.module1_raw_ingestion_pipeline import (
    Module1RawIngestionItem,
    validate_raw_ingestion_item,
)
from app.services.module1_ref4_normalization_policy import (
    Module1Ref45ConfigurationError,
    clear_module1_ref45_runtime_cache,
    require_module1_ref45_runtime,
    resolve_ref4_alias,
)
from app.services.module1_ref5_compatibility_policy import list_ref5_substitution_policies
from app.services.module1_ref6_work_material_policy import (
    Module1Ref6ConfigurationError,
    clear_module1_ref6_runtime_cache,
    require_module1_ref6_runtime,
    resolve_work_material_hints,
)
from app.services.module1_ref_runtime_artifacts import (
    Module1RefRuntimeConfigurationError,
    validate_module1_ref_runtime,
)
from app.services.module1_source_profile_registry import Module1SourceProfileRegistry
from app.services.module1_work_catalog import list_work_items
from app.services.module1_work_cost_export_contract import (
    build_work_cost_offer_export_package_from_offers,
    work_cost_export_package_to_dict,
)
from app.services.source_task_runner import _run_product_scan
from app.source_integrations.base import SourceProduct


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FUTURE_ANALYZER_PATH = (
    PROJECT_ROOT / "docs" / "Modules" / "module1" / "M1-ANALYZER-SOURCE-LIFECYCLE-FUTURE.md"
)
MODE_SCENARIOS = (
    ("legacy", "legacy", "legacy"),
    ("artifact_validation", "legacy", "legacy"),
    ("dual_read", "legacy", "legacy"),
    ("ref1_read", "approved", "legacy"),
    ("ref2_read", "approved", "legacy"),
    ("ref3_read", "approved", "approved"),
)
FIXTURE_SOURCE_NAME = "ATOM_MODULE1_PRODUCTION_READINESS_FIXTURE"
FIXTURE_EXTERNAL_ID = "atom-module1-readiness-product-v1"


class _FixtureIntegration:
    def __init__(self, products: list[SourceProduct]):
        self.products = products

    async def fetch_products(self, action_type: Any, parameters: Any) -> list[SourceProduct]:
        return list(self.products)


def _source_product(price: Any = Decimal("12500.00")) -> SourceProduct:
    return SourceProduct(
        external_id=FIXTURE_EXTERNAL_ID,
        external_url="https://fixture.atom.test/products/gas-block-001",
        raw_name="Газоблок Bonolit D500 B2.5 600x250x200 мм",
        raw_category="Газобетонные блоки",
        raw_brand="Bonolit",
        raw_manufacturer="Bonolit",
        price=price,
        currency="RUB",
        unit="м3",
        availability="in_stock",
        region="Краснодарский край",
    )


def _raw_item(*, price: Any = Decimal("12500.00"), unit: str = "м3") -> Module1RawIngestionItem:
    return Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_id="fixture-source-001",
        source_code="BAUCENTER",
        source_type="supplier_site",
        source_url="https://fixture.atom.test/products/gas-block-001",
        raw_title="Газоблок Bonolit D500 B2.5 600x250x200 мм",
        raw_description="Стеновой газобетонный блок для детерминированного локального теста.",
        raw_category="gas block",
        raw_price=price,
        raw_unit=unit,
        raw_characteristics={
            "length_mm": 600,
            "width_mm": 250,
            "height_mm": 200,
            "density_class": "D500",
            "strength_class": "B2.5",
            "frost_resistance": "F35",
            "pieces_per_m3": "33.33",
        },
        raw_documents=(
            {
                "title": "Technical sheet",
                "url": "https://fixture.atom.test/documents/gas-block-001-tds.pdf",
                "source_url": "https://fixture.atom.test/products/gas-block-001",
                "source_code": "BAUCENTER",
            },
        ),
        raw_availability="in_stock",
        raw_supplier="ATOM Fixture Supplier",
        raw_manufacturer="Bonolit",
        region="Краснодарский край",
        city="Краснодар",
        observed_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        adapter_version="fixture-v1",
        source_task_version="fixture-run-v1",
        confidence=Decimal("0.98"),
        raw_payload={"external_id": FIXTURE_EXTERNAL_ID},
    )


def _canonical_view(*, price: str | None = "12500.00") -> MaterialCanonicalView:
    price_refs = tuple()
    if price is not None:
        price_refs = (
            {
                "priceId": "fixture-price-001",
                "supplierId": "fixture-supplier-001",
                "supplierName": "ATOM Fixture Supplier",
                "price": price,
                "currency": "RUB",
                "unit": "м3",
                "region": "Краснодарский край",
                "observedAt": "2026-07-21T12:00:00+00:00",
            },
        )
    return MaterialCanonicalView(
        material_id="fixture-material-001",
        canonical_name="Газобетонный блок D500 B2.5",
        category={"slug": "blocks_and_bricks", "name": "Blocks"},
        subcategory={"slug": "wall_blocks", "name": "Wall blocks"},
        group={"code": "aerated_concrete_block", "name": "Aerated concrete block"},
        characteristics=(
            MaterialCharacteristicView("length_mm", 600, "mm"),
            MaterialCharacteristicView("width_mm", 250, "mm"),
            MaterialCharacteristicView("height_mm", 200, "mm"),
            MaterialCharacteristicView("density_class", "D500"),
            MaterialCharacteristicView("strength_class", "B2.5"),
            MaterialCharacteristicView("frost_resistance", "F35"),
            MaterialCharacteristicView("thermal_conductivity", "0.12"),
            MaterialCharacteristicView("pieces_per_m3", "33.33"),
            MaterialCharacteristicView("volume_per_piece_m3", "0.03"),
            MaterialCharacteristicView("weight_per_piece_kg", "18"),
            MaterialCharacteristicView("pieces_per_pallet", 60),
            MaterialCharacteristicView("package_unit", "pallet"),
        ),
        technical_profile_hints={"baseUnit": {"abbreviation": "m3"}},
        evidence=MaterialEvidenceSummary(
            document_count=3,
            source_ref_count=1,
            documents=(
                {
                    "documentId": "fixture-document-001",
                    "title": "Technical sheet",
                    "documentType": "technical_sheet",
                    "fileUrl": "https://fixture.atom.test/documents/gas-block-001-tds.pdf",
                    "sourceUrl": "https://fixture.atom.test/products/gas-block-001",
                    "status": "active",
                },
                {
                    "documentId": "fixture-document-002",
                    "title": "Certificate",
                    "documentType": "certificate",
                    "fileUrl": "https://fixture.atom.test/documents/gas-block-001-cert.pdf",
                    "status": "active",
                },
                {
                    "documentId": "fixture-document-003",
                    "title": "Declaration",
                    "documentType": "declaration",
                    "fileUrl": "https://fixture.atom.test/documents/gas-block-001-decl.pdf",
                    "status": "active",
                },
            ),
            source_refs=(
                {
                    "sourceId": "fixture-source-001",
                    "sourceCode": "BAUCENTER",
                    "externalId": FIXTURE_EXTERNAL_ID,
                    "externalUrl": "https://fixture.atom.test/products/gas-block-001",
                },
            ),
            moderation_preview_refs=tuple(),
            warnings=tuple(),
        ),
        supplier_price_refs=price_refs,
        moderation_status="approved",
        quality=MaterialQualitySummary("ok", 0, 0, 0, tuple(), tuple()),
        source_provenance={
            "canonicalBase": "Material",
            "rawDataIsCanonical": False,
            "sourceCode": "BAUCENTER",
            "externalId": FIXTURE_EXTERNAL_ID,
        },
        status="VERIFIED",
        warnings=tuple(),
        created_at="2026-07-21T12:00:00+00:00",
        updated_at="2026-07-21T12:00:00+00:00",
    )


async def _persistence_counts(session: AsyncSession) -> dict[str, int]:
    models = (Material, CatalogProduct, PriceHistory, MaterialMatchCandidate, SourceTaskResult)
    return {
        model.__tablename__: int(await session.scalar(select(func.count()).select_from(model)) or 0)
        for model in models
    }


def test_full_in_memory_contract_chain_preserves_module_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "approved")
    clear_module1_ref45_runtime_cache()
    raw = _raw_item()
    source_profile = Module1SourceProfileRegistry().get_source_profile(raw.source_code or "")
    validation = validate_raw_ingestion_item(raw)
    normalization = build_normalization_report(raw)

    assert source_profile is not None
    assert validation.is_valid is True
    assert normalization.is_ready_for_matching is True
    assert normalization.candidate.suggested_group_code == "aerated_concrete_block"
    assert (normalization.candidate.brand or "").casefold() == "bonolit"
    assert normalization.candidate.manufacturer == "Bonolit"
    assert normalization.candidate.normalized_characteristics["length_mm"] == Decimal("600")
    assert normalization.candidate.normalized_characteristics["density_class"] == "D500"

    existing = {
        "id": "fixture-material-001",
        "canonical_name": normalization.candidate.normalized_title,
        "group_code": "aerated_concrete_block",
        "characteristics": dict(normalization.candidate.normalized_characteristics),
        "manufacturer": "Bonolit",
        "brand": "Bonolit",
        "unit": normalization.candidate.normalized_unit,
    }
    match = build_match_candidate(normalization.candidate, [existing])
    moderation = build_moderation_queue_item(match)
    assert match.matched_material_reference is not None
    assert match.decision_hint in {"exact_match", "strong_match"}
    assert "create_new_material_candidate" not in moderation.allowed_decisions

    document_evidence = build_document_evidence_from_raw_link(
        raw.raw_documents[0],
        material_id="fixture-material-001",
        material_group="aerated_concrete_block",
    )
    assert document_evidence.document is not None
    assert validate_document_record(document_evidence.document).is_valid is True
    product_page = build_document_evidence_from_raw_link(
        {"title": raw.raw_title, "url": raw.source_url},
        material_id="fixture-material-001",
    )
    assert product_page.raw_link is not None
    assert product_page.raw_link.is_document is False
    assert product_page.document is None

    ready_view = _canonical_view()
    no_price_view = _canonical_view(price=None)
    readiness = build_export_readiness_report(ready_view)
    bundle = build_material_export_bundle(ready_view)
    no_price = build_export_readiness_report(no_price_view)
    assert readiness.ready_for_module2 is True
    assert readiness.ready_for_module5_selection is True
    assert bundle.validation_report.is_valid is True
    assert no_price.ready_for_module2 is False
    assert no_price.ready_for_module5_selection is False
    assert no_price.blocked_by_missing_positive_price is True

    conditional = resolve_work_material_hints(
        "walls_masonry_montazh_karkasnoy_steny",
        {"technology_context": "future-module2"},
        mode="approved",
    )
    assert conditional.state == "conditional_hints"
    assert conditional.quantity_calculation_allowed is False
    assert conditional.module2_execution_allowed is False
    assert conditional.module5_costing_allowed is False
    assert all(item.sku_selection_allowed is False for item in conditional.hints)

    work = next(item for item in list_work_items() if item.is_range_allowed)
    offer = ProviderWorkCostOffer(
        id="00000000-0000-0000-0000-000000000101",
        work_code=work.work_code,
        owner_user_id="00000000-0000-0000-0000-000000000102",
        region="Краснодарский край",
        pricing_mode="range",
        fixed_amount=None,
        minimum_amount=Decimal("1200.00"),
        maximum_amount=Decimal("1800.00"),
        currency="RUB",
        pricing_unit=work.allowed_units[0],
        valid_from=date(2026, 1, 1),
        valid_until=date(2026, 12, 31),
        status="active",
        created_at=datetime(2026, 7, 21, 10, 0),
        updated_at=datetime(2026, 7, 21, 11, 0),
    )
    work_cost_payload = work_cost_export_package_to_dict(
        build_work_cost_offer_export_package_from_offers(
            [offer], generated_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
        )
    )
    assert work_cost_payload["record_count"] == 1
    assert work_cost_payload["no_estimate_total"] is True
    assert work_cost_payload["no_selected_offer"] is True
    assert "supplier_price_refs" not in repr(work_cost_payload)
    assert "work_cost" not in repr(bundle)

    ref5_rules = list_ref5_substitution_policies(mode="approved", include_review=True)
    assert len(ref5_rules) == 13
    assert not any(item["automatic_selection_allowed"] for item in ref5_rules)
    assert not any(item["automatic_write_allowed"] for item in ref5_rules)
    clear_module1_ref45_runtime_cache()


@pytest.mark.asyncio
async def test_persistent_source_identity_price_history_and_readback_are_idempotent() -> None:
    product = _source_product()
    normalized = normalize_material_title(
        product.raw_name,
        brand=product.raw_brand,
        manufacturer=product.raw_manufacturer,
        category=product.raw_category,
        unit=product.unit,
        price=product.price,
        availability=product.availability,
        region=product.region,
    )
    async with engine.connect() as connection:
        before_session = AsyncSession(bind=connection, expire_on_commit=False)
        before = await _persistence_counts(before_session)
        await before_session.close()
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        source_id = material_id = product_id = None
        try:
            source = Source(
                name=FIXTURE_SOURCE_NAME,
                source_type=SourceType.SUPPLIER,
                url="https://fixture.atom.test",
                status=SourceStatus.ACTIVE,
            )
            material = Material(
                canonical_name=normalized.normalized_title,
                brand="Bonolit",
                manufacturer="Bonolit",
                status=MaterialStatus.VERIFIED,
            )
            session.add_all((source, material))
            await session.flush()
            source_id, material_id = source.id, material.id

            first_task = SourceTask(
                source=source,
                action_type=SourceActionType.UPDATE_PRICES,
                status=TaskStatus.RUNNING,
                parameters={"fixture": True, "run_type": "PRICE_REFRESH"},
            )
            session.add(first_task)
            await session.flush()
            await _run_product_scan(session, first_task, _FixtureIntegration([product]))
            await session.flush()
            catalog_product = (
                await session.execute(
                    select(CatalogProduct).where(
                        CatalogProduct.source_id == source_id,
                        CatalogProduct.external_id == FIXTURE_EXTERNAL_ID,
                    )
                )
            ).scalar_one()
            product_id = catalog_product.id
            assert catalog_product.material_id == material_id
            assert first_task.result_summary["created"] == 1
            assert first_task.result_summary["price_changes"] == 1
            assert await session.scalar(
                select(func.count()).select_from(PriceHistory).where(
                    PriceHistory.catalog_product_id == product_id
                )
            ) == 1

            second_task = SourceTask(
                source=source,
                action_type=SourceActionType.UPDATE_PRICES,
                status=TaskStatus.RUNNING,
                parameters={"fixture": True, "run_type": "PRICE_REFRESH"},
            )
            session.add(second_task)
            await session.flush()
            await _run_product_scan(session, second_task, _FixtureIntegration([product]))
            await session.flush()
            assert second_task.result_summary["unchanged"] == 1
            assert second_task.result_summary["price_changes"] == 0
            assert await session.scalar(
                select(func.count()).select_from(CatalogProduct).where(
                    CatalogProduct.source_id == source_id,
                    CatalogProduct.external_id == FIXTURE_EXTERNAL_ID,
                )
            ) == 1
            assert await session.scalar(
                select(func.count()).select_from(PriceHistory).where(
                    PriceHistory.catalog_product_id == product_id
                )
            ) == 1

            no_price = _source_product(None)
            no_price.external_id = f"{FIXTURE_EXTERNAL_ID}-no-price"
            no_price.external_url = f"{product.external_url}-no-price"
            third_task = SourceTask(
                source=source,
                action_type=SourceActionType.UPDATE_PRICES,
                status=TaskStatus.RUNNING,
                parameters={"fixture": True, "run_type": "PRICE_REFRESH"},
            )
            session.add(third_task)
            await session.flush()
            await _run_product_scan(session, third_task, _FixtureIntegration([no_price]))
            await session.flush()
            assert third_task.result_summary["rejected_no_price"] == 1
            assert await session.scalar(
                select(func.count()).select_from(CatalogProduct).where(
                    CatalogProduct.source_id == source_id,
                    CatalogProduct.external_id == no_price.external_id,
                )
            ) == 0

            await session.close()
            readback = AsyncSession(bind=connection, expire_on_commit=False)
            persisted = await readback.get(CatalogProduct, product_id)
            assert persisted is not None
            assert persisted.external_id == FIXTURE_EXTERNAL_ID
            assert persisted.material_id == material_id
            assert persisted.price == Decimal("12500.00")
            await readback.close()
        finally:
            if session.is_active:
                await session.close()
            await transaction.rollback()

        after_session = AsyncSession(bind=connection, expire_on_commit=False)
        after = await _persistence_counts(after_session)
        assert after == before
        if source_id is not None:
            assert await after_session.get(Source, source_id) is None
        if material_id is not None:
            assert await after_session.get(Material, material_id) is None
        if product_id is not None:
            assert await after_session.get(CatalogProduct, product_id) is None
        await after_session.close()


def test_ref_mode_matrix_and_rollback_are_read_only_and_fail_closed() -> None:
    assert {item[0] for item in MODE_SCENARIOS} == {
        "legacy",
        "artifact_validation",
        "dual_read",
        "ref1_read",
        "ref2_read",
        "ref3_read",
    }
    for main_mode, ref45_mode, ref6_mode in MODE_SCENARIOS:
        main = validate_module1_ref_runtime(main_mode)
        ref45 = require_module1_ref45_runtime(ref45_mode)
        ref6 = require_module1_ref6_runtime(ref6_mode)
        assert main.status in {"LEGACY", "PASS", "PASS_WITH_WARNINGS"}
        assert ref45.is_valid is True
        assert ref6.is_valid is True
        assert getattr(main, "database_writes", 0) == 0
        assert ref45.as_dict()["read_only"] is True
        assert ref45.as_dict()["write_activation_allowed"] is False
        assert ref6.as_dict()["database_write_allowed"] is False

    rollback = (
        ("ref3_read", "approved", "approved"),
        ("ref2_read", "approved", "legacy"),
        ("ref1_read", "legacy", "legacy"),
        ("legacy", "legacy", "legacy"),
    )
    for main_mode, ref45_mode, ref6_mode in rollback:
        assert validate_module1_ref_runtime(main_mode).status in {
            "LEGACY",
            "PASS",
            "PASS_WITH_WARNINGS",
        }
        assert require_module1_ref45_runtime(ref45_mode).mode == ref45_mode
        assert require_module1_ref6_runtime(ref6_mode).mode == ref6_mode

    with pytest.raises(Module1RefRuntimeConfigurationError):
        validate_module1_ref_runtime("unknown")
    with pytest.raises(Module1Ref45ConfigurationError):
        require_module1_ref45_runtime("unknown")
    with pytest.raises(Module1Ref6ConfigurationError):
        require_module1_ref6_runtime("unknown")
    clear_module1_ref45_runtime_cache()
    clear_module1_ref6_runtime_cache()


def test_immutable_ref45_and_ref6_cached_paths_parse_disk_once(monkeypatch: pytest.MonkeyPatch) -> None:
    counters = Counter()
    original_bytes = Path.read_bytes
    original_text = Path.read_text

    def counted_bytes(path: Path) -> bytes:
        counters["bytes"] += 1
        return original_bytes(path)

    def counted_text(path: Path, *args: Any, **kwargs: Any) -> str:
        counters["text"] += 1
        return original_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", counted_bytes)
    monkeypatch.setattr(Path, "read_text", counted_text)
    clear_module1_ref45_runtime_cache()
    clear_module1_ref6_runtime_cache()

    for _ in range(10):
        resolve_ref4_alias("газоблок", mode="approved")
    ref45_reads = dict(counters)
    counters.clear()
    for _ in range(10):
        resolve_work_material_hints(
            "earthworks_ustroystvo_peschanoy_podushki", mode="approved"
        )
    ref6_reads = dict(counters)

    assert ref45_reads == {"bytes": 9, "text": 9}
    assert ref6_reads == {"bytes": 9, "text": 9}
    clear_module1_ref45_runtime_cache()
    clear_module1_ref6_runtime_cache()


def test_synthetic_1000_observations_are_deterministic_and_side_effect_free(
    monkeypatch: pytest.MonkeyPatch,
    record_property: Any,
) -> None:
    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "approved")
    clear_module1_ref45_runtime_cache()
    counts = Counter()
    source_identities: set[str] = set()
    existing = {
        "id": "fixture-material-001",
        "canonical_name": "газобетонный блок d500 b2.5 600x250x200 мм",
        "group_code": "aerated_concrete_block",
        "characteristics": dict(_raw_item().raw_characteristics or {}),
        "manufacturer": "Bonolit",
        "brand": "Bonolit",
        "unit": "m3",
    }
    for index in range(1000):
        bucket = index % 10
        if bucket <= 5:
            raw = _raw_item()
            counts["positive"] += 1
        elif bucket <= 7:
            raw = _raw_item(price=None)
            counts["no_price"] += 1
        elif bucket == 8:
            raw = Module1RawIngestionItem(
                legacy_source="raw_payload",
                source_code="BAUCENTER",
                source_url=f"https://fixture.atom.test/ambiguous/{(index // 10) % 10}",
                raw_title="ГКЛ 2500x1200x12.5 мм",
                raw_category="gypsum board",
                raw_price=Decimal("390.00"),
                raw_unit="sheet",
                raw_payload={"external_id": f"ambiguous-{(index // 10) % 10}"},
            )
            counts["ambiguous"] += 1
        else:
            raw = _raw_item(unit="unsupported_fixture_unit")
            counts["invalid_unit"] += 1

        identity = str((raw.raw_payload or {}).get("external_id") or FIXTURE_EXTERNAL_ID)
        if identity in source_identities:
            counts["duplicates"] += 1
        source_identities.add(identity)
        validation = validate_raw_ingestion_item(raw)
        report = build_normalization_report(raw)
        if raw.raw_price is None:
            assert report.is_ready_for_matching is False
            assert build_match_candidate(report.candidate, []).decision_hint == "price_required_review"
        elif bucket == 8:
            assert report.candidate.suggested_group_code is None
            assert report.is_ready_for_matching is False
        elif bucket == 9:
            assert validation.is_valid is False
            assert report.is_ready_for_matching is False
        else:
            assert report.is_ready_for_matching is True
            match = build_match_candidate(report.candidate, [existing])
            queue = build_moderation_queue_item(match)
            assert match.decision_hint in {"exact_match", "strong_match", "possible_duplicate"}
            assert "create_new_material_candidate" not in queue.allowed_decisions

    assert counts == {
        "positive": 600,
        "no_price": 200,
        "ambiguous": 100,
        "invalid_unit": 100,
        "duplicates": 989,
    }
    assert len(source_identities) == 11
    record_property("synthetic_observations", 1000)
    record_property("synthetic_unique_source_identities", len(source_identities))
    clear_module1_ref45_runtime_cache()


def test_material_hub_views_have_bounded_read_only_query_counts() -> None:
    operations: list[str] = []

    def capture(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        operations.append(statement.lstrip().split(None, 1)[0].lower())

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        with TestClient(app) as client:
            anonymous = client.get("/api/v1/admin/material-hub/view")
            assert anonymous.status_code == 401
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                id="00000000-0000-0000-0000-000000000001",
                role=UserRole.ADMIN,
                roleCode=UserRole.ADMIN.value,
            )
            checks = (
                ("/api/v1/admin/material-hub/view", 2),
                ("/api/v1/admin/material-hub/view/materials", 50),
                ("/api/v1/admin/material-hub/view/documents", 5),
                ("/api/v1/admin/material-hub/view/work-costs", 2),
            )
            for path, budget in checks:
                operations.clear()
                response = client.get(path)
                assert response.status_code == 200
                assert set(operations) <= {"select"}
                assert len(operations) <= budget
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        event.remove(engine.sync_engine, "before_cursor_execute", capture)


def test_future_analyzer_contract_is_tracked_but_not_implemented() -> None:
    import hashlib

    content = FUTURE_ANALYZER_PATH.read_text(encoding="utf-8")
    assert hashlib.sha256(FUTURE_ANALYZER_PATH.read_bytes()).hexdigest() == (
        "caf223aab4c7dd9ac5197416f6c6cff0581807250e3d33e3310e44b202fba444"
    )
    for mode in (
        "INITIAL_PRODUCT_HARVEST",
        "PRICE_REFRESH",
        "INITIAL_DOCUMENT_HARVEST",
        "DOCUMENT_REFRESH",
        "MANUAL_REINDEX",
    ):
        assert mode in content
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "app").rglob("*.py")
    )
    assert "INITIAL_PRODUCT_HARVEST" not in production
    assert "DOCUMENT_REFRESH" not in production
