from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.module1_ref_projection.cli import main as projection_cli_main
from tools.module1_ref_projection.cli import run as run_projection_cli
from tools.module1_ref_projection.combined import project_combined_ref_validation, write_combined_projection_outputs
from tools.module1_ref_projection.loader import DEFAULT_PACKAGE_FILES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
MATERIAL_SEED = PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "material_knowledge_seed.json"
UNIT_SERVICE = PROJECT_ROOT / "app" / "services" / "module1_unit_conversion_registry.py"
WORK_CATALOG = PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "work_catalog_seed.json"


def test_actual_combined_validation_counts_and_gates() -> None:
    result = project_combined_ref_validation(REFERENCE_ROOT)
    details = result.counts["details"]

    assert result.counts["status"] == "PASS_WITH_WARNINGS"
    assert result.combined_activation_allowed is False
    assert "review_subsets_exist" in result.activation_blockers
    assert "integration_allowed_not_true" in result.activation_blockers
    assert result.counts["severity"]["blockers"] == 0
    assert result.counts["severity"]["warnings"] >= 1

    assert result.counts["ref1"]["ref_groups"] == 37
    assert result.counts["ref1"]["ref_types"] == 978
    assert result.counts["ref1"]["runtime_groups"] == 19
    assert result.counts["ref1"]["runtime_types"] == 192
    assert details["ref1_exact_groups"] == 19
    assert details["ref1_exact_material_types"] == 192
    assert details["ref1_exact_total_entities"] == 211
    assert result.counts["ref1"]["ref_only"] == 804
    assert result.counts["ref1"]["runtime_only"] == 0
    assert result.counts["ref1"]["broken_references"] == 0

    assert result.counts["ref2"]["ref_fields"] == 558
    assert result.counts["ref2"]["runtime_fields"] == 74
    assert details["ref2_runtime_field_usages"] == 113
    assert details["ref2_runtime_field_usages_current"] == 125
    assert result.counts["ref2"]["field_overlap"] == 46
    assert result.counts["ref2"]["field_ref_only"] == 512
    assert result.counts["ref2"]["field_runtime_only"] == 28
    assert result.counts["ref2"]["profiles"] == 177
    assert result.counts["ref2"]["assignments"] == 978
    assert result.counts["ref2"]["broken_references"] == 0
    assert result.counts["ref2"]["field_type_mismatches"] == 0
    assert result.counts["ref2"]["field_unit_mismatches"] == 0

    assert result.counts["ref3_units"]["ref_units"] == 90
    assert result.counts["ref3_units"]["runtime_units"] == 16
    assert result.counts["ref3_units"]["exact"] == 16
    assert result.counts["ref3_units"]["ref_only"] == 74
    assert result.counts["ref3_units"]["runtime_only"] == 0
    assert result.counts["ref3_units"]["dimension_conflicts"] == 0
    assert result.counts["ref3_units"]["ambiguous"] == 0
    assert details["runtime_conversion_simple"] == 12
    assert details["runtime_conversion_technical"] == 28
    assert details["runtime_conversion_seed"] == 7
    assert details["runtime_conversion_total"] == 47

    assert result.counts["ref3_extended"]["packaging_profiles"] == 21
    assert result.counts["ref3_extended"]["packaging_assignments"] == 978
    assert details["packaging_ref2_mismatches"] == 345
    assert details["ref3c_geometry_rules"] == 7
    assert details["ref3c_coverage_rules"] == 2
    assert details["ref3c_yield_rules"] == 1
    assert details["ref3c_consumption_rules"] == 5
    assert details["ref3c_non_geometry_total"] == 8

    assert details["ref2_review_queue"] == 48
    assert details["ref3a_review_queue"] == 17
    assert details["ref3b_review_queue"] == 51
    assert details["review_auto_activatable_total"] == 0
    assert details["executable_work_material_mappings_before"] == 0
    assert details["executable_work_material_mappings_after"] == 0
    assert details["unknown_references"] == 0
    assert details["canonical_alias_ambiguities"] == 0
    assert details["object_work_quantity_calculations"] == 0

    assert result.runtime_isolation["production_imports_tooling"] == 0
    assert result.runtime_isolation["production_reads_reference_data"] == 0
    assert any(issue.code == "COMBINED_PACKAGING_REF2_MISMATCHES" and issue.severity.value == "WARNING" for issue in result.issues)


def test_combined_outputs_are_deterministic_and_written_only_to_output_dir(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    write_combined_projection_outputs(REFERENCE_ROOT, first)
    write_combined_projection_outputs(REFERENCE_ROOT, second)

    expected = [
        "combined_projection_issues.json",
        "combined_projection_report.md",
        "combined_projection_summary.json",
    ]
    assert sorted(path.name for path in first.iterdir()) == expected
    assert {path.name: path.read_text(encoding="utf-8") for path in first.iterdir()} == {
        path.name: path.read_text(encoding="utf-8") for path in second.iterdir()
    }


def test_cli_combined_mode_uses_existing_output_pattern(tmp_path: Path) -> None:
    output_dir = tmp_path / "combined"

    payload = run_projection_cli(REFERENCE_ROOT, output_dir, include_combined=True)

    assert payload["combined"]["combined_activation_allowed"] is False
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "combined_projection_issues.json",
        "combined_projection_report.md",
        "combined_projection_summary.json",
        "foundation_summary.json",
    ]


def test_missing_ref_file_is_combined_blocker(tmp_path: Path) -> None:
    _copy_reference_packages(tmp_path)
    (tmp_path / DEFAULT_PACKAGE_FILES["REF-3C"]).unlink()

    result = project_combined_ref_validation(tmp_path)

    assert result.counts["status"] == "BLOCKED"
    assert any(issue.code == "REF_MISSING_FILE" and issue.severity.value == "BLOCKER" for issue in result.issues)


def test_invalid_json_is_combined_blocker(tmp_path: Path) -> None:
    _copy_reference_packages(tmp_path)
    (tmp_path / DEFAULT_PACKAGE_FILES["REF-2A"]).write_text("{broken-json", encoding="utf-8")

    result = project_combined_ref_validation(tmp_path)

    assert result.counts["status"] == "BLOCKED"
    assert any(issue.code == "REF_MALFORMED_JSON" and issue.severity.value == "BLOCKER" for issue in result.issues)


def test_cli_without_output_dir_is_controlled_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        projection_cli_main(["--reference-root", str(REFERENCE_ROOT), "--include-combined"])

    assert exc.value.code == 2
    assert list(tmp_path.iterdir()) == []


def test_protected_output_path_is_blocked_before_write() -> None:
    protected = PROJECT_ROOT / "app" / "_blocked_ref_projection_output"

    with pytest.raises(ValueError):
        run_projection_cli(REFERENCE_ROOT, protected, include_combined=True)

    assert not protected.exists()


def test_external_output_path_is_allowed(tmp_path: Path) -> None:
    output_dir = tmp_path / "external"

    run_projection_cli(REFERENCE_ROOT, output_dir, include_combined=True)

    assert (output_dir / "combined_projection_summary.json").exists()


def test_combined_validation_does_not_mutate_sources_or_runtime(tmp_path: Path) -> None:
    source_paths = [
        *[REFERENCE_ROOT / filename for filename in DEFAULT_PACKAGE_FILES.values()],
        MATERIAL_SEED,
        UNIT_SERVICE,
        WORK_CATALOG,
    ]
    before = {path: path.read_bytes() for path in source_paths}

    write_combined_projection_outputs(REFERENCE_ROOT, tmp_path / "out")

    assert {path: path.read_bytes() for path in source_paths} == before


def test_importing_combined_tooling_has_no_write_side_effects(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())
    __import__("tools.module1_ref_projection.combined")

    assert set(tmp_path.iterdir()) == before


def test_production_does_not_import_combined_tooling_or_ref_sources() -> None:
    result = project_combined_ref_validation(REFERENCE_ROOT)

    assert result.runtime_isolation["tooling_import_hits"] == []
    assert result.runtime_isolation["reference_data_hits"] == []


def _copy_reference_packages(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for filename in DEFAULT_PACKAGE_FILES.values():
        (destination / filename).write_bytes((REFERENCE_ROOT / filename).read_bytes())
