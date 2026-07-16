from __future__ import annotations

import json
from pathlib import Path

from tools.module1_ref_projection import CompatibilityClassification
from tools.module1_ref_projection.cli import run as run_projection_cli
from tools.module1_ref_projection.ref1 import REF1_FILENAME
from tools.module1_ref_projection.ref2 import (
    REF2A_FILENAME,
    REF2B_FILENAME,
    project_ref2_characteristics,
    write_ref2_projection_outputs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
MATERIAL_SEED = PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "material_knowledge_seed.json"


def _write_ref1(reference_root: Path, groups: list[dict[str, object]], material_types: list[dict[str, object]]) -> None:
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


def _write_ref2(
    reference_root: Path,
    *,
    fields: list[dict[str, object]],
    profiles: list[dict[str, object]],
    assignments: list[dict[str, object]],
    review_queue: list[dict[str, object]] | None = None,
) -> None:
    reference_root.mkdir(parents=True, exist_ok=True)
    (reference_root / REF2A_FILENAME).write_text(
        json.dumps(
            {
                "package_id": "REF-2A",
                "version": "0.1-draft",
                "status": "draft_for_user_review",
                "integration_allowed": False,
                "fields": fields,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (reference_root / REF2B_FILENAME).write_text(
        json.dumps(
            {
                "package_id": "REF-2B",
                "version": "0.1-draft",
                "status": "draft_for_user_review",
                "integration_allowed": False,
                "profiles": profiles,
                "material_type_assignments": assignments,
                "review_queue": review_queue or [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_runtime(path: Path, schemas: dict[str, object], field_definitions: dict[str, object] | None = None) -> None:
    payload = {"characteristicSchemas": schemas}
    if field_definitions is not None:
        payload["runtimeFieldDefinitions"] = field_definitions
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _field_entities(result) -> dict[str, object]:
    return {entity.entity_id: entity for entity in result.field_matrix if entity.entity_type == "characteristic_field"}


def _assignment_entities(result) -> dict[str, object]:
    return {entity.entity_id: entity for entity in result.profile_assignment_matrix if entity.entity_type == "profile_assignment"}


def test_actual_ref2_projection_counts_match_audit_checkpoints() -> None:
    result = project_ref2_characteristics(REFERENCE_ROOT)

    assert result.counts["ref_fields"] == 558
    assert result.counts["runtime_fields"] == 74
    assert result.counts["field_overlap"] == 46
    assert result.counts["field_ref_only"] == 512
    assert result.counts["field_runtime_only"] == 28
    assert result.counts["field_alias_candidates"] == 1
    assert result.counts["profiles"] == 177
    assert result.counts["runtime_schemas"] == 13
    assert result.counts["profile_ref_only"] == 177
    assert result.counts["profile_runtime_only"] == 13
    assert result.counts["assignments"] == 978
    assert result.counts["assignment_overlap"] == 13
    assert result.counts["assignment_ref_only"] == 965
    assert result.counts["review_required_assignments"] == 48
    assert result.counts["review_auto_activatable"] == 0
    assert result.counts["packaging_ref2_mismatches"] == 345
    assert result.counts["broken_references"] == 0


def test_synthetic_fields_classify_exact_ref_only_runtime_only_type_and_unit(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1(reference_root, [{"group_id": "group"}], [{"material_type_id": "runtime_type", "group_id": "group"}])
    _write_ref2(
        reference_root,
        fields=[
            {"field_code": "exact_field", "label_ru": "Exact", "data_type": "number", "unit_code": "mm"},
            {"field_code": "ref_only_field", "label_ru": "Ref only", "data_type": "string"},
            {"field_code": "type_mismatch_field", "label_ru": "Type", "data_type": "number"},
            {"field_code": "unit_mismatch_field", "label_ru": "Unit", "data_type": "number", "unit_code": "mm"},
        ],
        profiles=[{"profile_id": "profile", "required": ["exact_field"]}],
        assignments=[{"material_type_id": "runtime_type", "group_id": "group", "profile_id": "profile", "required": ["exact_field"]}],
    )
    _write_runtime(
        runtime_path,
        {"runtime_type": {"required": ["exact_field", "type_mismatch_field", "unit_mismatch_field", "runtime_only_field"]}},
        {
            "exact_field": {"data_type": "number", "unit_code": "mm"},
            "type_mismatch_field": {"data_type": "string"},
            "unit_mismatch_field": {"data_type": "number", "unit_code": "cm"},
        },
    )

    result = project_ref2_characteristics(reference_root, runtime_path)
    fields = _field_entities(result)

    assert fields["exact_field"].classification is CompatibilityClassification.EXACT_MATCH
    assert fields["ref_only_field"].classification is CompatibilityClassification.REF_ONLY
    assert fields["runtime_only_field"].classification is CompatibilityClassification.RUNTIME_ONLY
    assert fields["type_mismatch_field"].classification is CompatibilityClassification.INCOMPATIBLE_TYPE
    assert fields["unit_mismatch_field"].classification is CompatibilityClassification.INCOMPATIBLE_UNIT
    assert result.counts["field_type_mismatches"] == 1
    assert result.counts["field_unit_mismatches"] == 1


def test_broken_profile_field_is_blocker(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1(reference_root, [{"group_id": "group"}], [{"material_type_id": "type", "group_id": "group"}])
    _write_ref2(
        reference_root,
        fields=[{"field_code": "known_field", "label_ru": "Known"}],
        profiles=[{"profile_id": "profile", "required": ["missing_field"]}],
        assignments=[{"material_type_id": "type", "group_id": "group", "profile_id": "profile", "required": ["known_field"]}],
    )
    _write_runtime(runtime_path, {})

    result = project_ref2_characteristics(reference_root, runtime_path)

    assert any(issue.code == "REF2_PROFILE_UNKNOWN_FIELD" for issue in result.issues)
    assert result.counts["blockers"] == 1


def test_broken_assignment_profile_is_blocker(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1(reference_root, [{"group_id": "group"}], [{"material_type_id": "type", "group_id": "group"}])
    _write_ref2(
        reference_root,
        fields=[{"field_code": "known_field", "label_ru": "Known"}],
        profiles=[{"profile_id": "profile", "required": ["known_field"]}],
        assignments=[{"material_type_id": "type", "group_id": "group", "profile_id": "missing_profile", "required": ["known_field"]}],
    )
    _write_runtime(runtime_path, {})

    result = project_ref2_characteristics(reference_root, runtime_path)

    assert any(issue.code == "REF2_ASSIGNMENT_UNKNOWN_PROFILE" for issue in result.issues)
    assert result.counts["blockers"] == 1


def test_ambiguous_field_alias_is_diagnostic(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1(reference_root, [{"group_id": "group"}], [{"material_type_id": "type", "group_id": "group"}])
    _write_ref2(
        reference_root,
        fields=[
            {"field_code": "first_ref", "label_ru": "First", "aliases_ru": ["shared"]},
            {"field_code": "second_ref", "label_ru": "Second", "aliases_ru": ["shared"]},
        ],
        profiles=[{"profile_id": "profile", "required": ["first_ref"]}],
        assignments=[{"material_type_id": "type", "group_id": "group", "profile_id": "profile", "required": ["first_ref"]}],
    )
    _write_runtime(runtime_path, {"type": {"required": ["shared"]}})

    result = project_ref2_characteristics(reference_root, runtime_path)
    fields = _field_entities(result)

    assert fields["first_ref"].classification is CompatibilityClassification.AMBIGUOUS
    assert fields["second_ref"].classification is CompatibilityClassification.AMBIGUOUS
    assert result.counts["field_ambiguous"] == 2


def test_review_queue_assignments_are_not_auto_activatable(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    _write_ref1(reference_root, [{"group_id": "group"}], [{"material_type_id": "type", "group_id": "group"}])
    _write_ref2(
        reference_root,
        fields=[{"field_code": "known_field", "label_ru": "Known"}],
        profiles=[{"profile_id": "profile", "required": ["known_field"]}],
        assignments=[{"material_type_id": "type", "group_id": "group", "profile_id": "profile", "required": ["known_field"]}],
        review_queue=[{"material_type_id": "type", "profile_id": "profile", "flags": ["NEEDS_REVIEW"]}],
    )
    _write_runtime(runtime_path, {"type": {"required": ["known_field"]}})

    result = project_ref2_characteristics(reference_root, runtime_path)
    assignment = _assignment_entities(result)["type__profile"]

    assert result.counts["review_required_assignments"] == 1
    assert result.counts["review_auto_activatable"] == 0
    assert assignment.payload["review_required"] is True
    assert assignment.payload["auto_activatable"] is False
    assert assignment.payload["classification"] == "REVIEW_REQUIRED"


def test_ref2_outputs_are_deterministic(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    _write_ref1(reference_root, [{"group_id": "group"}], [{"material_type_id": "type", "group_id": "group"}])
    _write_ref2(
        reference_root,
        fields=[{"field_code": "known_field", "label_ru": "Known"}],
        profiles=[{"profile_id": "profile", "required": ["known_field"]}],
        assignments=[{"material_type_id": "type", "group_id": "group", "profile_id": "profile", "required": ["known_field"]}],
    )
    _write_runtime(runtime_path, {"type": {"required": ["known_field"]}})

    write_ref2_projection_outputs(reference_root, first_output, runtime_path)
    write_ref2_projection_outputs(reference_root, second_output, runtime_path)

    expected = [
        "ref2_field_matrix.json",
        "ref2_issues.json",
        "ref2_profile_assignment_matrix.json",
        "ref2_projection_summary.json",
        "ref2_report.md",
    ]
    assert sorted(path.name for path in first_output.iterdir()) == expected
    assert {path.name: path.read_text(encoding="utf-8") for path in first_output.iterdir()} == {
        path.name: path.read_text(encoding="utf-8") for path in second_output.iterdir()
    }


def test_cli_generates_ref2_outputs_only_when_requested(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_path = tmp_path / "runtime.json"
    output_dir = tmp_path / "out"
    _write_ref1(reference_root, [{"group_id": "group"}], [{"material_type_id": "type", "group_id": "group"}])
    _write_ref2(
        reference_root,
        fields=[{"field_code": "known_field", "label_ru": "Known"}],
        profiles=[{"profile_id": "profile", "required": ["known_field"]}],
        assignments=[{"material_type_id": "type", "group_id": "group", "profile_id": "profile", "required": ["known_field"]}],
    )
    _write_runtime(runtime_path, {"type": {"required": ["known_field"]}})

    payload = run_projection_cli(reference_root, output_dir, include_ref2=True, runtime_taxonomy_path=runtime_path)

    assert payload["ref2"]["counts"]["ref_fields"] == 1
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "foundation_summary.json",
        "ref2_field_matrix.json",
        "ref2_issues.json",
        "ref2_profile_assignment_matrix.json",
        "ref2_projection_summary.json",
        "ref2_report.md",
    ]


def test_ref2_projection_does_not_change_runtime_registries() -> None:
    before = MATERIAL_SEED.read_bytes()

    project_ref2_characteristics(REFERENCE_ROOT)

    assert MATERIAL_SEED.read_bytes() == before


def test_production_does_not_import_ref2_projection_tooling_or_reference_data() -> None:
    production_roots = [PROJECT_ROOT / "app", PROJECT_ROOT / "src"]
    hits: list[str] = []
    for root in production_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8-sig")
            if "module1_ref_projection" in text or "ATOM_REF2_" in text:
                hits.append(str(path.relative_to(PROJECT_ROOT)))

    assert hits == []
