from pathlib import Path

import pytest

from app.models.catalog_product import CatalogProduct
from app.models.enums import MatchCandidateStatus
from app.models.material_match_candidate import MaterialMatchCandidate
from app.schemas.material_hub_contracts import RawIngestionItem
from app.services.material_pipeline_guard import canonical_name_from_candidate


def test_raw_ingestion_contract_exists_before_canonical_material():
    raw = RawIngestionItem(
        source_id=None,
        raw_name="Доска 50x200",
        raw_payload={"name": "Доска 50x200"},
        detected_region_id=None,
        region_status="needs_review",
    )

    assert raw.raw_payload["name"] == "Доска 50x200"
    assert raw.region_status == "needs_review"


def test_source_task_runner_does_not_create_material_directly():
    source = Path("app/services/source_task_runner.py").read_text(encoding="utf-8")

    assert "Material(" not in source
    assert "_match_or_create_material" not in source
    assert "_ensure_match_candidate" in source
    assert "Кандидат подготовлен без прямого создания Material" in source


def test_document_scan_keeps_site_page_separate_from_document_record():
    source = Path("app/services/source_profiles.py").read_text(encoding="utf-8")

    assert '"site_page_is_document": False' in source
    assert "Documents are detected only by explicit file/external-link rules." in source


def test_canonical_material_requires_candidate_name():
    candidate = MaterialMatchCandidate(
        catalog_product_id="00000000-0000-0000-0000-000000000001",
        status=MatchCandidateStatus.NEEDS_REVIEW,
    )
    catalog_product = CatalogProduct(
        source_id="00000000-0000-0000-0000-000000000002",
        raw_name="",
    )

    with pytest.raises(ValueError):
        canonical_name_from_candidate(candidate, catalog_product)
