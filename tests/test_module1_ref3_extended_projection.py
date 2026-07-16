from __future__ import annotations

import json
from pathlib import Path

from tools.module1_ref_projection.cli import run as run_projection_cli
from tools.module1_ref_projection.ref1 import REF1_FILENAME
from tools.module1_ref_projection.ref2 import REF2A_FILENAME, REF2B_FILENAME
from tools.module1_ref_projection.ref3_extended import REF3B_FILENAME, REF3C_FILENAME, project_ref3_extended, write_ref3_extended_projection_outputs
from tools.module1_ref_projection.ref3_units import REF3A_FILENAME

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
WORK_CATALOG = PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "work_catalog_seed.json"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_reference(reference_root: Path, *, ref2_fields: list[str] | None = None, ref2_assignment_fields: list[str] | None = None, ref3b_assignment: dict[str, object] | None = None, ref3c_rule: dict[str, object] | None = None, ref3c_assignment: dict[str, object] | None = None, review_queue: list[dict[str, object]] | None = None) -> None:
    ref2_fields = ref2_fields or ["known_field", "package_area_m2", "volume_per_piece_m3"]
    ref2_assignment_fields = ref2_assignment_fields or ["known_field"]
    _write_json(reference_root / REF1_FILENAME, {"package_id": "REF-1", "version": "0.3-preliminary-approved", "status": "preliminary_approved_editable", "approval": {"integration_allowed": False}, "groups": [{"group_id": "group"}], "material_types": [{"material_type_id": "type", "group_id": "group"}]})
    _write_json(reference_root / REF2A_FILENAME, {"package_id": "REF-2A", "version": "0.1-draft", "status": "draft_for_user_review", "fields": [{"field_code": code} for code in ref2_fields]})
    _write_json(reference_root / REF2B_FILENAME, {"package_id": "REF-2B", "version": "0.1-draft", "status": "draft_for_user_review", "profiles": [{"profile_id": "profile", "required": ["known_field"]}], "material_type_assignments": [{"material_type_id": "type", "profile_id": "profile", "all_field_codes": ref2_assignment_fields}], "review_queue": []})
    _write_json(reference_root / REF3A_FILENAME, {"package_id": "REF-3A", "version": "0.3-draft", "status": "draft_for_user_review", "approval": {"integration_allowed": False}, "units": [{"unit_code": "m2"}, {"unit_code": "m3"}, {"unit_code": "kg"}, {"unit_code": "piece"}]})
    assignment = ref3b_assignment or {"material_type_id": "type", "packaging_profile_id": "profile_pack", "preferred_quantity_unit": "piece", "allowed_quantity_units": ["piece"], "candidate_price_basis_units": ["piece"], "required_packaging_fields": ["known_field"], "recommended_packaging_fields": []}
    _write_json(reference_root / REF3B_FILENAME, {"package_id": "REF-3B", "version": "0.1-draft", "status": "draft_for_user_review", "approval": {"integration_allowed": False}, "packaging_profiles": [{"profile_id": "profile_pack", "name_ru": "Profile", "primary_quantity_units": ["piece"], "allowed_price_basis_units": ["piece"], "allowed_package_units": ["piece"], "required_fields": [], "recommended_fields": []}], "material_type_assignments": [assignment], "review_queue": review_queue or []})
    rule = ref3c_rule or {"rule_id": "rule", "name_ru": "Rule", "semantic_type": "derived_geometry", "output_field": "volume_per_piece_m3", "output_unit": "m3", "required_fields": ["known_field"], "formula": "known_field", "formula_inputs": [{"name": "known_field", "source": "material_field", "field_code": "known_field", "unit_code": "m2"}], "formula_outputs": [{"name": "volume_per_piece_m3", "field_code": "volume_per_piece_m3", "unit_code": "m3"}]}
    rule_assignment = ref3c_assignment or {"material_type_id": "type", "geometry_rule_ids": ["rule"], "coverage_consumption_rule_ids": [], "status": "draft_for_user_review"}
    _write_json(reference_root / REF3C_FILENAME, {"package_id": "REF-3C", "version": "0.2-draft", "status": "draft_for_user_review", "approval": {"integration_allowed": False}, "geometry_rules": [rule], "coverage_consumption_rules": [], "material_type_rule_assignments": [rule_assignment], "legacy_field_aliases": {}})


def test_actual_ref3_extended_projection_counts_match_audit_checkpoints() -> None:
    result = project_ref3_extended(REFERENCE_ROOT)

    assert result.counts["packaging_profiles"] == 21
    assert result.counts["packaging_assignments"] == 978
    assert result.counts["packaging_ref2_mismatches"] == 345
    assert result.counts["ref3b_review_required"] == 51
    assert result.counts["ref3b_review_auto_activatable"] == 0
    assert result.counts["geometry_rules"] == 7
    assert result.counts["coverage_rules"] == 2
    assert result.counts["yield_rules"] == 1
    assert result.counts["consumption_rules"] == 5
    assert result.counts["work_groups"] == 24
    assert result.counts["works"] == 209
    assert result.counts["executable_work_material_mappings_before"] == 0
    assert result.counts["executable_work_material_mappings_after"] == 0
    assert result.counts["blockers"] == 0


def test_dangling_material_profile_unit_field_and_rule_references_are_blockers(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    _write_reference(
        reference_root,
        ref3b_assignment={"material_type_id": "missing_type", "packaging_profile_id": "missing_profile", "preferred_quantity_unit": "ghost_unit", "allowed_quantity_units": ["ghost_unit"], "candidate_price_basis_units": ["ghost_unit"], "required_packaging_fields": [], "recommended_packaging_fields": []},
        ref3c_rule={"rule_id": "rule", "name_ru": "Rule", "semantic_type": "derived_geometry", "output_field": "missing_field", "output_unit": "ghost_unit", "required_fields": ["missing_field"], "formula": "missing_field", "formula_inputs": [{"name": "missing_field", "source": "material_field", "field_code": "missing_field", "unit_code": "ghost_unit"}], "formula_outputs": [{"name": "out", "field_code": "missing_field", "unit_code": "ghost_unit"}]},
        ref3c_assignment={"material_type_id": "missing_type", "geometry_rule_ids": ["missing_rule"], "coverage_consumption_rule_ids": ["missing_coverage"], "status": "draft_for_user_review"},
    )

    result = project_ref3_extended(reference_root, tmp_path / "missing_work_catalog.json")
    codes = {issue.code for issue in result.issues}

    assert "REF3B_UNKNOWN_MATERIAL_TYPE" in codes
    assert "REF3B_UNKNOWN_PACKAGING_PROFILE" in codes
    assert "REF3B_UNKNOWN_UNIT" in codes
    assert "REF3C_UNKNOWN_FIELD" in codes
    assert "REF3C_UNKNOWN_UNIT" in codes
    assert "REF3C_ASSIGNMENT_UNKNOWN_GEOMETRY_RULE" in codes
    assert "REF3C_ASSIGNMENT_UNKNOWN_COVERAGE_RULE" in codes
    assert result.counts["blockers"] >= 7


def test_missing_formula_declaration_and_packaging_profile_conflict_are_reported(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    _write_reference(
        reference_root,
        ref2_assignment_fields=["known_field"],
        ref3b_assignment={"material_type_id": "type", "packaging_profile_id": "profile_pack", "preferred_quantity_unit": "piece", "allowed_quantity_units": ["piece"], "candidate_price_basis_units": ["piece"], "required_packaging_fields": ["package_area_m2"], "recommended_packaging_fields": []},
        ref3c_rule={"rule_id": "rule", "name_ru": "Rule", "semantic_type": "coverage_rate", "rate_field": "known_field", "rate_unit": "m2", "formula_hint": "quantity = area_m2 * known_field"},
    )

    result = project_ref3_extended(reference_root, tmp_path / "missing_work_catalog.json")

    assert len(result.packaging_mismatches) == 1
    assert result.packaging_mismatches[0]["field_code"] == "package_area_m2"
    assert any(issue.code == "REF3C_MISSING_FORMULA_DECLARATION" for issue in result.issues)


def test_ref3b_review_records_are_isolated(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    _write_reference(reference_root, review_queue=[{"material_type_id": "type"}])

    result = project_ref3_extended(reference_root, tmp_path / "missing_work_catalog.json")
    review_entities = [entity for entity in result.matrix if entity.classification.value == "REVIEW_REQUIRED"]

    assert result.counts["ref3b_review_required"] == 1
    assert result.counts["ref3b_review_auto_activatable"] == 0
    assert review_entities[0].payload["auto_activatable"] is False


def test_ref3_extended_outputs_are_deterministic_and_cli_gated(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    first = tmp_path / "first"
    second = tmp_path / "second"
    cli_out = tmp_path / "cli"
    work_catalog = tmp_path / "work_catalog.json"
    _write_reference(reference_root)
    _write_json(work_catalog, {"groups": [{"work_group": "g"}], "works": [{"work_code": "w"}]})

    write_ref3_extended_projection_outputs(reference_root, first, work_catalog)
    write_ref3_extended_projection_outputs(reference_root, second, work_catalog)
    payload = run_projection_cli(reference_root, cli_out, include_ref3_extended=True, work_catalog_path=work_catalog)

    expected = ["ref3_extended_issues.json", "ref3_extended_matrix.json", "ref3_extended_report.md", "ref3_extended_summary.json", "ref3_packaging_mismatches.json"]
    assert sorted(path.name for path in first.iterdir()) == expected
    assert {path.name: path.read_text(encoding="utf-8") for path in first.iterdir()} == {path.name: path.read_text(encoding="utf-8") for path in second.iterdir()}
    assert payload["ref3_extended"]["counts"]["executable_work_material_mappings_before"] == 0
    assert sorted(path.name for path in cli_out.iterdir()) == ["foundation_summary.json"] + expected


def test_ref3_extended_projection_does_not_change_sources() -> None:
    source_paths = [
        REFERENCE_ROOT / REF3B_FILENAME,
        REFERENCE_ROOT / REF3C_FILENAME,
        WORK_CATALOG,
    ]
    before = {path: path.read_bytes() for path in source_paths}

    project_ref3_extended(REFERENCE_ROOT)

    assert {path: path.read_bytes() for path in source_paths} == before


def test_production_does_not_import_ref3_extended_tooling_or_reference_data() -> None:
    hits: list[str] = []
    for root in (PROJECT_ROOT / "app", PROJECT_ROOT / "src"):
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8-sig")
            if "module1_ref_projection" in text or "ATOM_REF3_" in text or "docs/Modules/module1/reference_data" in text:
                hits.append(str(path.relative_to(PROJECT_ROOT)))

    assert hits == []
