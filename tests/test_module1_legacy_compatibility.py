from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.models.catalog_product import CatalogProduct
from app.models.enums import (
    CatalogProductStatus,
    DocumentStatus,
    DocumentType,
    MaterialStatus,
    MatchCandidateStatus,
    SourceActionType,
    SourceStatus,
    SourceType,
    TaskResultType,
    TaskStatus,
    UploadRowStatus,
)
from app.models.material import Material
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.source_task_result import SourceTaskResult
from app.models.supplier_price import SupplierPrice
from app.models.supplier_upload_row import SupplierUploadRow
from app.schemas import module1_domain_contracts as domain
from app.schemas.material_hub_contracts import (
    CollectionObject,
    DocumentFileType,
    IngestionRecordStatus,
    MaterialCanonicalObject,
    RawIngestionItem,
    SourceAdapterStatus,
)
from app.services.module1_legacy_compatibility import (
    canonical_material_from_material,
    document_record_from_material_document,
    extraction_profile_from_source_task,
    get_module1_legacy_compatibility_map,
    match_candidate_contract_from_material_match_candidate,
    price_observation_from_price_history,
    price_observation_from_supplier_price,
    raw_ingestion_from_catalog_product,
    raw_ingestion_from_source_task_result,
    raw_ingestion_from_supplier_upload_row,
    source_profile_from_source,
)


def test_domain_contracts_are_dto_aliases_not_parallel_orm_models():
    assert domain.CanonicalMaterial is MaterialCanonicalObject
    assert domain.DocumentEvidence is domain.Document
    assert domain.RawIngestionItem is RawIngestionItem

    assert not Path("app/models/canonical_material.py").exists()
    assert not Path("app/models/raw_ingestion_item.py").exists()
    assert not Path("app/models/price_observation.py").exists()
    assert not Path("database/migrations/module1_domain_skeleton.sql").exists()


def test_legacy_compatibility_map_covers_target_architecture():
    mapping = {item.target_entity: item for item in get_module1_legacy_compatibility_map()}

    assert mapping["CanonicalMaterial"].legacy_entities[0] == "Material"
    assert "CatalogProduct" in mapping["RawIngestionItem"].legacy_entities
    assert "SupplierUploadRow" in mapping["RawIngestionItem"].legacy_entities
    assert mapping["PriceObservation"].legacy_entities == ("SupplierPrice", "PriceHistory")
    assert "MaterialDocument" in mapping["DocumentEvidence"].legacy_entities
    assert mapping["SourcePipeline"].legacy_entities == ("Source", "SourceTask", "SourceTaskResult")
    assert mapping["MatchingModeration"].legacy_entities == ("MaterialMatchCandidate",)
    assert mapping["WorkRateObservation"].status == "gap"


def test_material_maps_to_canonical_material_contract():
    material_id = uuid4()
    material = Material(
        id=material_id,
        canonical_name="Газоблок D500 600x300x200",
        article="GB-D500",
        brand="Bonolit",
        manufacturer="Bonolit",
        description="Канонический материал из legacy Material.",
        status=MaterialStatus.VERIFIED,
    )

    contract = canonical_material_from_material(material)

    assert contract.id == material_id
    assert contract.canonical_name == "Газоблок D500 600x300x200"
    assert contract.status == MaterialStatus.VERIFIED
    assert contract.brand == "Bonolit"


def test_catalog_product_maps_to_raw_ingestion_without_canonical_material():
    product = CatalogProduct(
        id=uuid4(),
        source_id=uuid4(),
        external_id="sku-42",
        external_url="https://supplier.example/products/42",
        raw_name="Доска 25x150x6000",
        normalized_name="Доска 25x150x6000",
        raw_category="Пиломатериалы",
        raw_brand="",
        price=Decimal("820.50"),
        currency="RUB",
        unit="шт",
        availability="in_stock",
        region="Краснодарский край",
        match_confidence=Decimal("0.73"),
        status=CatalogProductStatus.NEEDS_REVIEW,
    )

    raw = raw_ingestion_from_catalog_product(product)

    assert raw.id == product.id
    assert raw.raw_name == "Доска 25x150x6000"
    assert raw.raw_price == Decimal("820.50")
    assert raw.status == IngestionRecordStatus.NEEDS_REVIEW
    assert raw.raw_payload["legacy_entity"] == "CatalogProduct"
    assert not hasattr(raw, "material_id")


def test_supplier_upload_row_maps_to_raw_ingestion_layer():
    row = SupplierUploadRow(
        id=uuid4(),
        upload_id=uuid4(),
        row_number=7,
        raw_name="Арматура A500C 12 мм",
        normalized_name="Арматура A500C d12",
        raw_category="Металлопрокат",
        raw_unit="т",
        raw_price=Decimal("61000"),
        raw_quantity=Decimal("1"),
        raw_article="A500C-12",
        parsed_data={"diameter": "12"},
        status=UploadRowStatus.NORMALIZED,
    )

    raw = raw_ingestion_from_supplier_upload_row(row)

    assert raw.supplier_upload_id == row.upload_id
    assert raw.status == IngestionRecordStatus.NORMALIZED
    assert raw.raw_payload["legacy_entity"] == "SupplierUploadRow"
    assert raw.raw_payload["parsed_data"] == {"diameter": "12"}


def test_source_task_result_maps_to_raw_ingestion_preview_payload():
    task = SourceTask(
        id=uuid4(),
        source_id=uuid4(),
        action_type=SourceActionType.FIND_NEW_PRODUCTS,
        status=TaskStatus.NEEDS_REVIEW,
    )
    result = SourceTaskResult(
        id=uuid4(),
        task_id=task.id,
        task=task,
        result_type=TaskResultType.NEW_PRODUCT_FOUND,
        entity_type="catalog_product",
        new_value={"raw_name": "ГКЛВ 2500x1200x12.5", "price": "390.00", "unit": "лист"},
        status="needs_review",
    )

    raw = raw_ingestion_from_source_task_result(result)

    assert raw.source_id == task.source_id
    assert raw.raw_name == "ГКЛВ 2500x1200x12.5"
    assert raw.raw_price == Decimal("390.00")
    assert raw.status == IngestionRecordStatus.NEEDS_REVIEW
    assert raw.raw_payload["legacy_entity"] == "SourceTaskResult"


def test_source_task_result_requires_human_readable_raw_name():
    result = SourceTaskResult(
        id=uuid4(),
        task_id=uuid4(),
        result_type=TaskResultType.NEEDS_REVIEW,
        new_value={"price": "100"},
    )

    with pytest.raises(ValueError, match="raw name"):
        raw_ingestion_from_source_task_result(result)


def test_supplier_price_and_history_map_to_price_observation_without_overwrite():
    material_id = uuid4()
    supplier_id = uuid4()
    supplier_price = SupplierPrice(
        id=uuid4(),
        supplier_id=supplier_id,
        material_id=material_id,
        catalog_product_id=uuid4(),
        price=Decimal("1200.00"),
        currency="RUB",
        unit="м3",
        availability="in_stock",
        valid_until=date(2026, 8, 1),
    )
    history = PriceHistory(
        id=uuid4(),
        material_id=material_id,
        supplier_id=supplier_id,
        source_id=uuid4(),
        price=Decimal("1180.00"),
        currency="RUB",
        unit="м3",
        collected_at=datetime(2026, 7, 14, 10, 30),
        price_date=date(2026, 7, 14),
    )

    current_observation = price_observation_from_supplier_price(supplier_price)
    history_observation = price_observation_from_price_history(history)

    assert current_observation.price == Decimal("1200.00")
    assert current_observation.price_date == datetime(2026, 8, 1)
    assert history_observation.price == Decimal("1180.00")
    assert history_observation.collected_at == datetime(2026, 7, 14, 10, 30)


def test_supplier_price_without_price_is_not_price_observation():
    supplier_price = SupplierPrice(id=uuid4(), supplier_id=uuid4(), material_id=uuid4(), price=None)

    with pytest.raises(ValueError, match="without price"):
        price_observation_from_supplier_price(supplier_price)


def test_material_document_maps_to_document_evidence_contract():
    document = MaterialDocument(
        id=uuid4(),
        material_id=uuid4(),
        source_id=uuid4(),
        document_type=DocumentType.CERTIFICATE,
        title="Сертификат соответствия",
        file_url="https://example.test/cert.pdf",
        issue_date=date(2026, 1, 10),
        expiry_date=date(2027, 1, 10),
        status=DocumentStatus.ACTIVE,
    )

    evidence = document_record_from_material_document(document)

    assert evidence.title == "Сертификат соответствия"
    assert evidence.file_meta.file_type == DocumentFileType.PDF
    assert evidence.status == DocumentStatus.ACTIVE


def test_source_pipeline_models_map_to_profiles_and_raw_results():
    source = Source(
        id=uuid4(),
        name="Bonolit",
        source_type=SourceType.MANUFACTURER,
        url="https://bonolit.ru",
        priority=10,
        status=SourceStatus.ACTIVE,
    )
    task = SourceTask(
        id=uuid4(),
        source_id=source.id,
        action_type=SourceActionType.UPDATE_PRICES,
        status=TaskStatus.COMPLETED,
    )

    source_profile = source_profile_from_source(source)
    extraction_profile = extraction_profile_from_source_task(task)

    assert source_profile.source_id == source.id
    assert source_profile.status.value == "ACTIVE"
    assert extraction_profile.source_id == source.id
    assert extraction_profile.status == SourceAdapterStatus.ACTIVE
    assert extraction_profile.collectable_objects == [CollectionObject.PRICES]


def test_match_candidate_remains_matching_moderation_contract():
    candidate = MaterialMatchCandidate(
        id=uuid4(),
        catalog_product_id=uuid4(),
        candidate_material_id=uuid4(),
        match_score=Decimal("0.82"),
        match_reason="Совпали размеры и плотность",
        status=MatchCandidateStatus.NEEDS_REVIEW,
    )

    contract = match_candidate_contract_from_material_match_candidate(candidate)

    assert contract.id == candidate.id
    assert contract.catalog_product_id == candidate.catalog_product_id
    assert contract.status == MatchCandidateStatus.NEEDS_REVIEW
    assert contract.match_score == Decimal("0.82")

