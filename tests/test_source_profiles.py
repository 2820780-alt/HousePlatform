from app.models.enums import SourceActionType, SourceStatus, SourceType
from app.models.source import Source
from app.services.source_profiles import attach_source_profile_snapshot


def test_source_profile_snapshot_for_site_source():
    source = Source(
        name="Baucenter",
        source_type=SourceType.RETAIL,
        url="https://baucenter.ru/",
        status=SourceStatus.ACTIVE,
    )

    payload = attach_source_profile_snapshot(
        source,
        SourceActionType.UPDATE_PRICES,
        {"scan_mode": "TEST", "category_url_contains": ["/catalog/"]},
    )

    snapshot = payload["source_profile_snapshot"]
    assert snapshot["source_profile"]["data_source_kind"] == "SUPPLIER_SITE"
    assert snapshot["source_profile"]["collectable_objects"] == ["PRICES"]
    assert snapshot["source_profile"]["adapter_config"]["adapter_code"] == "pending_source_adapter"
    assert snapshot["source_profile"]["normalization_rules"]
    assert snapshot["source_profile"]["moderation_rules"]
    assert snapshot["extraction_profile"]["mapping_profile"]["field_mapping_rules"]
    assert snapshot["extraction_profile"]["adapter_config"]["rate_limit_policy"]["respect_robots"] is True
    assert snapshot["source_adapter"]["config"]["trust_level"] == "NORMAL"
    assert snapshot["moderator_update_ready"] is True


def test_source_profile_snapshot_for_file_upload_accepts_needs_review_region():
    payload = attach_source_profile_snapshot(
        None,
        SourceActionType.UPLOAD_SUPPLIER_FILE,
        {
            "data_source_kind": "FILE",
            "collection_object": "MATERIALS",
            "activeRegionCode": "RU-KDA",
            "region_status": "needs_review",
        },
        adapter_code="FileUploadAdapter",
        supported_actions={SourceActionType.UPLOAD_SUPPLIER_FILE},
    )

    snapshot = payload["source_profile_snapshot"]
    assert snapshot["source_profile"]["data_source_kind"] == "FILE"
    assert snapshot["source_profile"]["collectable_objects"] == ["MATERIALS"]
    assert snapshot["source_profile"]["region_status"] is None
    assert snapshot["source_profile"]["region_detection_rules"]["region_status"] == "needs_review"
    assert snapshot["source_adapter"]["supported_actions"] == ["UPLOAD_SUPPLIER_FILE"]


def test_source_profile_snapshot_carries_document_candidates_from_profile():
    source = Source(
        name="ProfileSource",
        source_type=SourceType.SUPPLIER,
        url="https://example.ru/",
        status=SourceStatus.ACTIVE,
    )

    payload = attach_source_profile_snapshot(
        source,
        SourceActionType.UPDATE_TECH_DOCUMENTS,
        {"document_urls": ["https://example.ru/docs/manual.pdf"]},
        adapter_code="ProfileAdapter",
        supported_actions={SourceActionType.UPDATE_TECH_DOCUMENTS},
    )

    extraction = payload["source_profile_snapshot"]["extraction_profile"]
    assert extraction["document_candidates"][0]["url"] == "https://example.ru/docs/manual.pdf"
    assert extraction["document_candidates"][0]["file_type"] == "PDF"
    assert extraction["document_candidates"][0]["parse_status"] == "not_processed"
    assert extraction["parsing_rules"]["document_rules"]["site_page_is_document"] is False
