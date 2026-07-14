from __future__ import annotations

from pathlib import Path

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_extraction_workbench import (
    ExtractionWorkbenchReport,
    build_extraction_workbench_report,
    build_field_trace,
    build_matching_preview,
    build_moderation_preview,
    build_workbench_action_hints,
    build_workbench_input,
    validate_extraction_sample,
)


def _gas_block_payload(**overrides):
    payload = {
        "sourceCode": "YUFO_VKBLOCK",
        "sourceUrl": "https://vkblock.ru/product/gazoblok-d500",
        "title": "Газоблок D500 B2.5 600x300x200",
        "category": "Газобетон",
        "price": "4200",
        "unit": "м3",
        "manufacturer": "VKBlock",
        "region": "Краснодарский край",
        "characteristics": {
            "length_mm": 600,
            "width_mm": 300,
            "height_mm": 200,
            "density_class": "D500",
            "strength_class": "B2.5",
        },
        "documentLinks": ["https://vkblock.ru/cert.pdf"],
    }
    payload.update(overrides)
    return payload


def _canonical_view() -> MaterialCanonicalView:
    return MaterialCanonicalView(
        material_id="mat-1",
        canonical_name="Газоблок D500 B2.5",
        category={"slug": "aerated_concrete_block"},
        subcategory=None,
        group={"code": "aerated_concrete_block"},
        characteristics=(
            MaterialCharacteristicView("length_mm", 600),
            MaterialCharacteristicView("width_mm", 300),
            MaterialCharacteristicView("height_mm", 200),
        ),
        technical_profile_hints={},
        evidence=MaterialEvidenceSummary(
            document_count=0,
            source_ref_count=0,
            documents=tuple(),
            source_refs=tuple(),
            moderation_preview_refs=tuple(),
            warnings=tuple(),
        ),
        supplier_price_refs=tuple(),
        moderation_status="needs_review",
        quality=MaterialQualitySummary(
            status="needs_review",
            open_issues=1,
            critical_issues=1,
            warning_issues=0,
            issues=tuple(),
            warnings=("Quality issue is open.",),
        ),
        source_provenance={"canonicalBase": "Material", "rawDataIsCanonical": False},
        status="ACTIVE",
        warnings=tuple(),
        created_at=None,
        updated_at=None,
    )


def test_gas_block_workbench_builds_traces_raw_and_normalized_previews_without_side_effects() -> None:
    workbench_input = build_workbench_input(
        _gas_block_payload(),
        source_profile_code="YUFO_VKBLOCK",
        extraction_profile_code="yufo_vkblock_extraction_profile",
        material_group="aerated_concrete_block",
    )

    report = build_extraction_workbench_report(workbench_input)

    assert isinstance(report, ExtractionWorkbenchReport)
    assert report.no_side_effects is True
    assert report.pipeline_preview.no_side_effects is True
    assert report.source_profile_summary["sourceCode"] == "YUFO_VKBLOCK"
    assert report.blueprint_summary["groupCode"] == "aerated_concrete_block"
    assert any(trace.mapped_field == "length_mm" and trace.status == "mapped" for trace in report.field_traces)
    assert report.pipeline_preview.raw_ingestion_preview["item"]["raw_title"] == "Газоблок D500 B2.5 600x300x200"
    normalized = report.pipeline_preview.normalized_candidate_preview["candidate"]
    assert normalized["suggested_group_code"] == "aerated_concrete_block"
    assert normalized["source_metadata"]["source_code"] == "YUFO_VKBLOCK"
    assert report.pipeline_preview.raw_ingestion_preview["rawDataIsCanonical"] is False


def test_unknown_unit_reports_invalid_unit_and_unit_action_hint() -> None:
    workbench_input = build_workbench_input(
        _gas_block_payload(unit="parsec"),
        source_profile_code="YUFO_VKBLOCK",
        material_group="aerated_concrete_block",
    )

    issues = validate_extraction_sample(workbench_input)
    hints = build_workbench_action_hints(build_extraction_workbench_report(workbench_input))

    assert any(issue.issue_type == "invalid_unit" for issue in issues)
    assert any(hint.hint_type == "clarify_unit_mapping" for hint in hints)


def test_missing_module2_fields_are_visible_in_validation_issues() -> None:
    workbench_input = build_workbench_input(
        _gas_block_payload(),
        source_profile_code="YUFO_VKBLOCK",
        material_group="aerated_concrete_block",
    )

    issues = validate_extraction_sample(workbench_input)

    assert any(issue.issue_type == "missing_module2_field" for issue in issues)


def test_document_links_are_evidence_refs_not_document_records() -> None:
    workbench_input = build_workbench_input(
        _gas_block_payload(documentLinks=["https://vkblock.ru/cert.pdf", "https://vkblock.ru/tds.pdf"]),
        source_profile_code="YUFO_VKBLOCK",
        material_group="aerated_concrete_block",
    )

    report = build_extraction_workbench_report(workbench_input)
    raw_documents = report.pipeline_preview.raw_ingestion_preview["item"]["raw_documents"]
    evidence_documents = report.pipeline_preview.normalized_candidate_preview["candidate"]["evidence"]["raw_documents"]

    assert raw_documents[0]["url"] == "https://vkblock.ru/cert.pdf"
    assert evidence_documents[1]["url"] == "https://vkblock.ru/tds.pdf"
    assert "missing_document_link" not in {issue.issue_type for issue in report.validation_issues}


def test_matching_preview_reports_existing_material_candidate_without_merge() -> None:
    workbench_input = build_workbench_input(
        _gas_block_payload(),
        source_profile_code="YUFO_VKBLOCK",
        material_group="aerated_concrete_block",
    )
    existing = {
        "canonical_name": "Газоблок D500 B2.5 600x300x200",
        "group_code": "aerated_concrete_block",
        "unit": "m3",
        "characteristics": {
            "length_mm": 600,
            "width_mm": 300,
            "height_mm": 200,
            "density_class": "D500",
            "strength_class": "B2.5",
        },
    }

    preview = build_matching_preview(workbench_input, [existing])
    report = build_extraction_workbench_report(workbench_input, [existing])

    assert preview["createsLink"] is False
    assert preview["mergesDuplicate"] is False
    assert preview["matchCandidate"]["decision_hint"] in {"exact_match", "strong_match", "possible_duplicate"}
    assert any(issue.issue_type == "possible_duplicate" for issue in report.validation_issues)


def test_moderation_preview_builds_queue_item_without_applying_decision() -> None:
    workbench_input = build_workbench_input(
        _gas_block_payload(),
        source_profile_code="YUFO_VKBLOCK",
        material_group="aerated_concrete_block",
    )

    preview = build_moderation_preview(workbench_input)
    report = build_extraction_workbench_report(workbench_input)

    assert preview["totalItems"] == 1
    assert preview["decisionApplied"] is False
    assert preview["no_side_effects"] is True
    assert any(issue.issue_type == "pending_moderation" for issue in report.validation_issues)


def test_workbench_report_includes_quality_preview_and_action_hints() -> None:
    workbench_input = build_workbench_input(
        _gas_block_payload(),
        source_profile_code="YUFO_VKBLOCK",
        material_group="aerated_concrete_block",
    )

    report = build_extraction_workbench_report(workbench_input, canonical_material_view=_canonical_view())

    assert report.pipeline_preview.quality_preview is not None
    assert report.pipeline_preview.quality_preview["no_side_effects"] is True
    assert report.validation_issues
    assert report.action_hints
    assert all(hint.safe_to_auto_apply is False for hint in report.action_hints)


def test_field_trace_marks_unknown_fields_without_failing() -> None:
    traces = build_field_trace(
        _gas_block_payload(unexpectedVendorBadge="promo"),
    )

    assert any(trace.raw_field == "unexpectedVendorBadge" and trace.status == "unknown" for trace in traces)


def test_extraction_workbench_is_read_only_and_does_not_import_network_or_orm_layers() -> None:
    source = Path("app/services/module1_extraction_workbench.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "requests" not in source
    assert "httpx" not in source
    assert "urllib" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "CatalogProduct(" not in source
    assert "SupplierUploadRow(" not in source
    assert "Material(" not in source
