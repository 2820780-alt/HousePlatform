from __future__ import annotations

import json
from pathlib import Path

from tools.module1_ref_projection import CompatibilityClassification
from tools.module1_ref_projection.cli import run as run_projection_cli
from tools.module1_ref_projection.ref1 import (
    REF1_FILENAME,
    project_ref1_taxonomy,
    write_ref1_projection_outputs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
MATERIAL_SEED = PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "material_knowledge_seed.json"


def _write_ref1_package(reference_root: Path, *, groups: list[dict[str, object]], material_types: list[dict[str, object]]) -> None:
    reference_root.mkdir(parents=True, exist_ok=True)
    (reference_root / REF1_FILENAME).write_text(
        json.dumps(
            {
                "package_id": "REF-1",
                "version": "0.3-preliminary-approved",
                "status": "preliminary_approved_editable",
                "integration_allowed": False,
                "groups": groups,
                "material_types": material_types,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_runtime_taxonomy(path: Path, taxonomy: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"taxonomy": taxonomy}, ensure_ascii=False, indent=2), encoding="utf-8")


def _entities_by_type(result, entity_type: str) -> dict[str, object]:
    return {entity.entity_id: entity for entity in result.compatibility_matrix if entity.entity_type == entity_type}


def test_actual_ref1_taxonomy_projects_expected_counts() -> None:
    result = project_ref1_taxonomy(REFERENCE_ROOT)

    assert result.counts == {
        "ref_groups": 37,
        "ref_types": 978,
        "runtime_groups": 19,
        "runtime_types": 192,
        "exact": 211,
        "alias_candidates": 0,
        "ambiguous": 0,
        "ref_only": 804,
        "runtime_only": 0,
        "broken_references": 0,
        "issues": 0,
        "blockers": 0,
        "warnings": 0,
    }


def test_synthetic_projection_classifies_exact_ref_only_and_runtime_only(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1_package(
        reference_root,
        groups=[
            {"group_id": "runtime_group", "name_ru": "Runtime group"},
            {"group_id": "extra_group", "name_ru": "Extra group"},
        ],
        material_types=[
            {"material_type_id": "runtime_type", "clean_name_ru": "Runtime type", "group_id": "runtime_group"},
            {"material_type_id": "extra_type", "clean_name_ru": "Extra type", "group_id": "extra_group"},
        ],
    )
    _write_runtime_taxonomy(
        runtime_path,
        [
            {"code": "runtime_group", "children": ["runtime_type", "runtime_only_type"]},
            {"code": "runtime_only_group", "children": []},
        ],
    )

    result = project_ref1_taxonomy(reference_root, runtime_path)
    groups = _entities_by_type(result, "material_group")
    types = _entities_by_type(result, "material_type")

    assert groups["runtime_group"].classification is CompatibilityClassification.EXACT_MATCH
    assert groups["extra_group"].classification is CompatibilityClassification.REF_ONLY
    assert groups["runtime_only_group"].classification is CompatibilityClassification.RUNTIME_ONLY
    assert types["runtime_type"].classification is CompatibilityClassification.EXACT_MATCH
    assert types["extra_type"].classification is CompatibilityClassification.REF_ONLY
    assert types["runtime_only_type"].classification is CompatibilityClassification.RUNTIME_ONLY


def test_synthetic_alias_candidate_is_diagnostic_only(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1_package(
        reference_root,
        groups=[{"group_id": "cement_group", "name_ru": "Cement", "aliases": ["binders"]}],
        material_types=[
            {
                "material_type_id": "cement_ref",
                "clean_name_ru": "Cement ref",
                "group_id": "cement_group",
                "aliases": ["cement"],
            }
        ],
    )
    _write_runtime_taxonomy(runtime_path, [{"code": "binders", "children": ["cement"]}])

    result = project_ref1_taxonomy(reference_root, runtime_path)
    groups = _entities_by_type(result, "material_group")
    types = _entities_by_type(result, "material_type")

    assert groups["cement_group"].classification is CompatibilityClassification.ALIAS_MATCH
    assert types["cement_ref"].classification is CompatibilityClassification.ALIAS_MATCH
    assert result.counts["alias_candidates"] == 2


def test_synthetic_ambiguous_alias_is_reported(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1_package(
        reference_root,
        groups=[{"group_id": "group", "name_ru": "Group"}],
        material_types=[
            {"material_type_id": "first_ref", "clean_name_ru": "First", "group_id": "group", "aliases": ["shared"]},
            {"material_type_id": "second_ref", "clean_name_ru": "Second", "group_id": "group", "aliases": ["shared"]},
        ],
    )
    _write_runtime_taxonomy(runtime_path, [{"code": "group", "children": ["shared"]}])

    result = project_ref1_taxonomy(reference_root, runtime_path)
    types = _entities_by_type(result, "material_type")

    assert types["first_ref"].classification is CompatibilityClassification.AMBIGUOUS
    assert types["second_ref"].classification is CompatibilityClassification.AMBIGUOUS
    assert result.counts["ambiguous"] == 2
    assert any(issue.code == "REF1_ALIAS_COLLISION" for issue in result.issues)


def test_duplicate_normalized_code_is_blocker(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1_package(
        reference_root,
        groups=[{"group_id": "A!", "name_ru": "First"}, {"group_id": "a", "name_ru": "Second"}],
        material_types=[],
    )
    _write_runtime_taxonomy(runtime_path, [])

    result = project_ref1_taxonomy(reference_root, runtime_path)

    assert any(issue.code == "REF1_DUPLICATE_NORMALIZED_CODE" and issue.severity.value == "BLOCKER" for issue in result.issues)
    assert result.counts["blockers"] == 1


def test_broken_type_to_group_reference_is_invalid_reference(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1_package(
        reference_root,
        groups=[{"group_id": "existing_group", "name_ru": "Existing"}],
        material_types=[{"material_type_id": "broken_type", "clean_name_ru": "Broken", "group_id": "missing_group"}],
    )
    _write_runtime_taxonomy(runtime_path, [{"code": "existing_group", "children": []}])

    result = project_ref1_taxonomy(reference_root, runtime_path)
    types = _entities_by_type(result, "material_type")

    assert types["broken_type"].classification is CompatibilityClassification.INVALID_REFERENCE
    assert result.counts["broken_references"] == 1
    assert any(issue.code == "REF1_UNKNOWN_GROUP" for issue in result.issues)


def test_ref1_reports_are_deterministic(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    _write_ref1_package(
        reference_root,
        groups=[{"group_id": "group", "name_ru": "Group"}],
        material_types=[{"material_type_id": "type", "clean_name_ru": "Type", "group_id": "group"}],
    )
    _write_runtime_taxonomy(runtime_path, [{"code": "group", "children": ["type"]}])

    write_ref1_projection_outputs(reference_root, first_output, runtime_path)
    write_ref1_projection_outputs(reference_root, second_output, runtime_path)

    assert sorted(path.name for path in first_output.iterdir()) == [
        "ref1_compatibility_matrix.json",
        "ref1_issues.json",
        "ref1_projection_summary.json",
        "ref1_report.md",
    ]
    assert {path.name: path.read_text(encoding="utf-8") for path in first_output.iterdir()} == {
        path.name: path.read_text(encoding="utf-8") for path in second_output.iterdir()
    }


def test_cli_generates_ref1_outputs_only_when_requested(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    output_dir = tmp_path / "out"
    _write_ref1_package(
        reference_root,
        groups=[{"group_id": "group", "name_ru": "Group"}],
        material_types=[{"material_type_id": "type", "clean_name_ru": "Type", "group_id": "group"}],
    )
    _write_runtime_taxonomy(runtime_path, [{"code": "group", "children": ["type"]}])

    payload = run_projection_cli(reference_root, output_dir, include_ref1=True, runtime_taxonomy_path=runtime_path)

    assert payload["ref1"]["counts"]["exact"] == 2
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "foundation_summary.json",
        "ref1_compatibility_matrix.json",
        "ref1_issues.json",
        "ref1_projection_summary.json",
        "ref1_report.md",
    ]


def test_ref1_projection_does_not_change_runtime_registries(tmp_path: Path) -> None:
    before = MATERIAL_SEED.read_bytes()

    project_ref1_taxonomy(REFERENCE_ROOT)

    assert MATERIAL_SEED.read_bytes() == before


def test_production_does_not_import_ref1_projection_tooling_or_reference_data() -> None:
    production_roots = [PROJECT_ROOT / "app", PROJECT_ROOT / "src"]
    hits: list[str] = []
    for root in production_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8-sig")
            if "module1_ref_projection" in text or "ATOM_REF1_Material_Taxonomy" in text:
                hits.append(str(path.relative_to(PROJECT_ROOT)))

    assert hits == []
