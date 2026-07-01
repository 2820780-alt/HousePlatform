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
    assert snapshot["extraction_profile"]["mapping_profile"]["field_mapping_rules"]
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
