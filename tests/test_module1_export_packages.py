from __future__ import annotations

from pathlib import Path

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_export_packages import (
    MaterialExportBundle,
    build_bulk_export_report,
    build_clean_material_package,
    build_export_readiness_report,
    build_material_export_bundle,
    build_material_selector_package,
    build_module11_analytics_signal_package,
    build_module2_technology_input_package,
    build_module5_estimate_input_hint_package,
    build_technical_profile_package,
    validate_export_package,
)


def _char(name: str, value, unit: str | None = None) -> MaterialCharacteristicView:
    return MaterialCharacteristicView(name=name, value=value, unit=unit)


def _view(
    *,
    material_id: str | None = "mat-001",
    name: str = "Газоблок D500 B2.5",
    group_code: str = "aerated_concrete_block",
    characteristics: tuple[MaterialCharacteristicView, ...] = tuple(),
    documents: tuple[dict, ...] = tuple(),
    source_refs: tuple[dict, ...] = tuple(),
    supplier_price_refs: tuple[dict, ...] = tuple(),
    moderation_status: str = "approved",
    quality_open_issues: int = 0,
) -> MaterialCanonicalView:
    return MaterialCanonicalView(
        material_id=material_id,
        canonical_name=name,
        category={"slug": group_code, "name": group_code},
        subcategory={"slug": "wall_blocks", "name": "Wall blocks"},
        group={"code": group_code, "name": group_code},
        characteristics=characteristics,
        technical_profile_hints={"baseUnit": {"abbreviation": "m3"}},
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
                "sourceCode": "YUFO_VKBLOCK",
                "sourceName": "Manufacturer source",
                "sourceType": "manufacturer_site",
                "externalUrl": "https://example.test/item",
                "manufacturer": "Bonolit",
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
                "observedAt": "2026-07-01",
            },
        ),
    )


def _incomplete_gas_block() -> MaterialCanonicalView:
    return _view(
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


def test_full_material_builds_export_bundle_ready_for_downstream_modules() -> None:
    bundle = build_material_export_bundle(_complete_gas_block())

    assert isinstance(bundle, MaterialExportBundle)
    assert bundle.no_side_effects is True
    assert bundle.validation_report.is_valid is True
    assert bundle.clean_material.canonical_name == "Газоблок D500 B2.5"
    assert bundle.technical_profile.material_group == "aerated_concrete_block"
    assert bundle.export_readiness_report.ready_for_module2 is True
    assert bundle.export_readiness_report.ready_for_module5_selection is True
    assert bundle.module2_package.no_calculation_result is True
    assert bundle.module5_package.no_estimate_total is True
    assert bundle.module11_signals.no_charts is True


def test_gas_block_missing_module2_fields_blocks_technology_export() -> None:
    view = _incomplete_gas_block()

    module2_package = build_module2_technology_input_package(view)
    readiness = build_export_readiness_report(view)

    assert "strength_class" in module2_package.missing_fields or "frost_resistance" in module2_package.missing_fields
    assert readiness.blocked_by_missing_technical_fields is True
    assert readiness.ready_for_module2 is False


def test_pending_moderation_blocks_or_marks_quality_review() -> None:
    view = _view(
        moderation_status="needs_review",
        characteristics=(
            _char("length_mm", 600),
            _char("width_mm", 300),
            _char("height_mm", 200),
            _char("density_class", "D500"),
            _char("strength_class", "B2.5"),
            _char("frost_resistance", "F35"),
            _char("thermal_conductivity", "0.12"),
        ),
    )

    readiness = build_export_readiness_report(view)

    assert readiness.blocked_by_pending_moderation is True
    assert readiness.ready_for_quality_review is True


def test_selector_package_contains_summaries_without_selecting_supplier_or_best_price() -> None:
    selector = build_material_selector_package(_complete_gas_block())

    assert selector.allowed_roles
    assert selector.alternatives_summary["allowedTargetGroups"] is not None
    assert selector.compatibility_summary["allowedContexts"] is not None
    assert selector.documents_summary["documentCount"] == 3
    assert selector.participants_summary["participantCount"] >= 1
    assert selector.price_observation_summary["priceObservationCount"] == 1
    assert selector.price_observation_summary["selectedSupplier"] is None
    assert selector.price_observation_summary["selectedBestPrice"] is None
    assert selector.no_selected_supplier is True
    assert selector.no_selected_best_price is True


def test_module5_package_contains_refs_but_no_estimate_total_or_best_supplier() -> None:
    package = build_module5_estimate_input_hint_package(_complete_gas_block())

    assert package.price_observation_refs
    assert package.participant_supplier_refs
    assert package.document_evidence_refs
    assert package.no_estimate_total is True
    assert package.no_selected_supplier is True
    assert package.no_selected_best_price is True
    assert all(ref["selectedAsBestPrice"] is False for ref in package.price_observation_refs)


def test_module11_signals_are_counts_and_readiness_without_charts_or_analytics() -> None:
    signals = build_module11_analytics_signal_package(_complete_gas_block())

    assert signals.quality_score > 0
    assert signals.price_observation_presence is True
    assert signals.price_observation_count == 1
    assert signals.source_provenance_presence is True
    assert signals.participant_coverage["participantCount"] >= 1
    assert signals.document_coverage["documentCount"] == 3
    assert signals.no_charts is True
    assert signals.no_dynamic_analytics is True


def test_clean_and_technical_packages_are_json_serializable_dtos() -> None:
    clean = build_clean_material_package(_complete_gas_block())
    technical = build_technical_profile_package(_complete_gas_block())

    assert validate_export_package(clean).is_valid is True
    assert validate_export_package(technical).is_valid is True
    assert technical.no_side_effects is True
    assert "length_mm" in clean.normalized_characteristics
    assert technical.conversion_capabilities


def test_bulk_export_report_counts_readiness_without_writing_files() -> None:
    report = build_bulk_export_report((_complete_gas_block(), _incomplete_gas_block()))

    assert report["totalMaterials"] == 2
    assert report["byReadiness"]["readyForModule2"] == 1
    assert report["byReadiness"]["blockedByTechnicalFields"] >= 1
    assert report["filesWritten"] is False
    assert report["no_side_effects"] is True


def test_export_packages_layer_is_read_only_and_does_not_generate_files_or_import_orm() -> None:
    source = Path("app/services/module1_export_packages.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "open(" not in source
    assert ".to_csv(" not in source
    assert ".to_excel(" not in source
    assert ".save(" not in source
    assert "pdf" not in source.lower()
    assert "xlsx" not in source.lower()
