from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_data_quality_dashboard import (
    DataQualityActionHint,
    DataQualityIssue,
    build_data_quality_dashboard_report,
    build_export_readiness_summary,
    build_material_quality_snapshot,
    build_quality_action_hints,
    calculate_material_quality_score,
    collect_characteristic_quality_issues,
    collect_document_quality_issues,
    collect_moderation_quality_issues,
    collect_participant_quality_issues,
    collect_price_observation_quality_issues,
    group_quality_issues_by_dimension,
)


def _char(name: str, value, unit: str | None = None) -> MaterialCharacteristicView:
    return MaterialCharacteristicView(name=name, value=value, unit=unit)


def _view(
    *,
    material_id: str | None = "mat-001",
    name: str = "Aerated concrete block D500",
    group_code: str = "aerated_concrete_block",
    characteristics: tuple[MaterialCharacteristicView, ...] = tuple(),
    documents: tuple[dict, ...] = tuple(),
    source_refs: tuple[dict, ...] = tuple(),
    supplier_price_refs: tuple[dict, ...] = tuple(),
    quality_open_issues: int = 0,
    moderation_status: str = "approved",
    source_provenance: dict | None = None,
) -> MaterialCanonicalView:
    return MaterialCanonicalView(
        material_id=material_id,
        canonical_name=name,
        category={"slug": group_code, "name": group_code},
        subcategory=None,
        group={"code": group_code, "name": group_code},
        characteristics=characteristics,
        technical_profile_hints={},
        evidence=MaterialEvidenceSummary(
            document_count=len(documents),
            source_ref_count=len(source_refs),
            documents=documents,
            source_refs=source_refs,
            moderation_preview_refs=tuple(),
            warnings=tuple(),
        ),
        supplier_price_refs=supplier_price_refs,
        moderation_status=moderation_status,
        quality=MaterialQualitySummary(
            status="needs_review" if quality_open_issues else "ok",
            open_issues=quality_open_issues,
            critical_issues=quality_open_issues,
            warning_issues=0,
            issues=tuple(),
            warnings=("Quality issue is open.",) if quality_open_issues else tuple(),
        ),
        source_provenance=source_provenance
        or {
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


def _complete_gas_block() -> MaterialCanonicalView:
    return _view(
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
        documents=(
            {
                "documentId": "doc-cert",
                "title": "Certificate",
                "documentType": "certificate",
                "fileUrl": "https://example.test/cert.pdf",
                "status": "active",
            },
            {
                "documentId": "doc-decl",
                "title": "Declaration",
                "documentType": "declaration",
                "fileUrl": "https://example.test/decl.pdf",
                "status": "active",
            },
            {
                "documentId": "doc-tds",
                "title": "Technical sheet",
                "documentType": "technical_sheet",
                "fileUrl": "https://example.test/tds.pdf",
                "status": "active",
            },
        ),
        source_refs=(
            {
                "sourceId": "source-1",
                "sourceName": "Manufacturer source",
                "externalUrl": "https://example.test/item",
                "matchConfidence": "0.93",
            },
        ),
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
        ),
    )


def test_gas_block_missing_strength_and_pieces_reports_quality_issues_and_hints() -> None:
    view = _view(
        characteristics=(
            _char("length_mm", 600),
            _char("width_mm", 300),
            _char("height_mm", 200),
            _char("density_class", "D500"),
        ),
        documents=tuple(),
        source_refs=tuple(),
        supplier_price_refs=tuple(),
    )

    snapshot = build_material_quality_snapshot(view)
    issue_types = {issue.issue_type for issue in snapshot.issues}

    assert "missing_required_characteristic" in issue_types
    assert "missing_module2_field" in issue_types
    assert "missing_packaging_field" in issue_types
    assert "missing_required_document" in issue_types
    assert "missing_price_observation" in issue_types
    assert snapshot.readiness_status in {"needs_more_data", "insufficient_quality"}
    assert snapshot.overall_quality_score < 80
    assert any(isinstance(hint, DataQualityActionHint) and hint.safe_to_auto_apply is False for hint in snapshot.action_hints)


def test_complete_material_gets_high_quality_score_and_export_summary() -> None:
    snapshot = build_material_quality_snapshot(_complete_gas_block())

    assert snapshot.overall_quality_score >= 75
    assert snapshot.export_readiness["autoFixApplied"] is False
    assert snapshot.module2_readiness["module2Calculations"] == "not_performed_by_module1"
    assert snapshot.module5_readiness_hint["estimateCalculated"] is False
    assert all(hint.safe_to_auto_apply is False for hint in snapshot.action_hints)


def test_document_participant_price_and_moderation_collectors_emit_expected_issue_types() -> None:
    view = _view(
        characteristics=(_char("length_mm", 600),),
        documents=tuple(),
        source_refs=tuple(),
        supplier_price_refs=(
            {
                "priceId": "price-1",
                "supplierId": "supplier-1",
                "supplierName": "Supplier One",
                "price": "0",
                "currency": "RUB",
                "unit": "м3",
            },
        ),
        quality_open_issues=1,
        moderation_status="needs_review",
        source_provenance={"canonicalBase": "Material", "rawDataIsCanonical": False},
    )

    document_types = {issue.issue_type for issue in collect_document_quality_issues(view)}
    participant_types = {issue.issue_type for issue in collect_participant_quality_issues(view)}
    price_types = {issue.issue_type for issue in collect_price_observation_quality_issues(view)}
    moderation_types = {issue.issue_type for issue in collect_moderation_quality_issues(view)}

    assert "missing_required_document" in document_types
    assert "missing_manufacturer" in participant_types
    assert "missing_brand" in participant_types
    assert "suspicious_price_observation" in price_types
    assert "pending_moderation" in moderation_types


def test_moderation_items_report_duplicates_pending_and_low_confidence() -> None:
    issues = collect_moderation_quality_issues(
        _complete_gas_block(),
        moderation_items=(
            {"issueType": "possible_duplicate", "status": "pending", "confidence": "0.42"},
        ),
    )
    issue_types = {issue.issue_type for issue in issues}

    assert "possible_duplicate" in issue_types
    assert "pending_moderation" in issue_types
    assert "low_confidence_match" in issue_types


def test_aggregate_dashboard_report_counts_status_severity_dimension_and_top_blockers() -> None:
    report = build_data_quality_dashboard_report(
        (
            _complete_gas_block(),
            _view(material_id=None, name="", group_code="aerated_concrete_block"),
        )
    )

    assert report.total_materials_checked == 2
    assert report.count_by_readiness_status
    assert report.count_by_severity["critical"] >= 1
    assert report.count_by_issue_type["export_blocked"] >= 1
    assert report.count_by_dimension["identity"] >= 1
    assert report.top_blocking_issues
    assert report.export_readiness_summary["total"] == 2
    assert report.export_readiness_summary["autoFixApplied"] is False


def test_grouping_score_and_action_hints_are_read_only_contracts() -> None:
    issues = (
        DataQualityIssue("missing_required_document", "documents", "high", "Missing certificate", "certificate"),
        DataQualityIssue("missing_supplier", "participants", "high", "Missing supplier", "supplier"),
    )
    grouped = group_quality_issues_by_dimension(issues)
    snapshot = build_material_quality_snapshot(_complete_gas_block())
    export = build_export_readiness_summary(snapshot)
    hints = build_quality_action_hints(
        MaterialCanonicalView.__dataclass_fields__ and snapshot  # keep same immutable snapshot object
    )

    assert set(grouped) == {"documents", "participants"}
    assert calculate_material_quality_score(snapshot) == snapshot.overall_quality_score
    assert export["module1Only"] is True
    assert hints
    assert all(hint.safe_to_auto_apply is False for hint in hints)


def test_characteristic_collector_uses_seed_required_fields() -> None:
    issues = collect_characteristic_quality_issues(
        _view(characteristics=(_char("length_mm", 600), _char("width_mm", 300)))
    )

    assert any(issue.field == "height_mm" for issue in issues)
    assert any(issue.issue_type == "missing_required_characteristic" for issue in issues)


def test_data_quality_dashboard_service_is_read_only_not_global_dashboard_or_analytics() -> None:
    source = Path("app/services/module1_data_quality_dashboard.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "create_material" not in source.lower()
    assert "apply_moderation" not in source.lower()
    assert "quick_action" not in source.lower()
    assert "module11" not in source.lower()
