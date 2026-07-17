from __future__ import annotations

import json
from pathlib import Path

from tools.module1_ref_projection.runtime_artifacts import (
    ARTIFACT_FILENAMES,
    ARTIFACT_SCHEMA_VERSION,
    MANIFEST_FILENAME,
    build_runtime_artifact_package,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
LEGACY_SEED = PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "material_knowledge_seed.json"
EXPECTED_SOURCE_HASHES = {
    "REF-1": "48ed52a10d0192eecc7be649608c1ebc2ee5635617c34198133b030584ae0100",
    "REF-2A": "22b3201b55381a1da626aab2e8fea066e94882f97a237495b8ac7307c50adc5d",
    "REF-2B": "1ac98e68f88c6f8288c534452bd46de5308808ae1e6f60446f124e0af08beb3c",
    "REF-3-MANIFEST": "30bde8789f2352797b41cf41cf8f86bea35103f026d5222741a7988bb750799a",
    "REF-3A": "342957cf9ea88ee9873595d1bac4c848d50b3423d2a61fdeadf2556f3e522cfb",
    "REF-3B": "e42f6b0dede8eff8bd33146477ae909990892924d802b5cb37e326262977252b",
    "REF-3C": "23eefba57ef415527db3f9cf0fa395614d7064c06d2db753f4072209560b7b28",
}


def _build(output_root: Path):
    return build_runtime_artifact_package(
        REFERENCE_ROOT,
        output_root,
        legacy_seed_path=LEGACY_SEED,
    )


def _payload(package: Path, name: str) -> dict:
    return json.loads((package / name).read_text(encoding="utf-8"))


def test_runtime_artifact_generation_is_byte_deterministic(tmp_path: Path) -> None:
    first = _build(tmp_path / "first")
    second = _build(tmp_path / "second")

    assert first.artifact_set_id == second.artifact_set_id == "ref-runtime-v1-122079b1c558fefc"
    assert first.artifact_hashes == second.artifact_hashes
    assert sorted(path.name for path in first.output_dir.iterdir()) == sorted((*ARTIFACT_FILENAMES, MANIFEST_FILENAME))
    assert {
        path.name: path.read_bytes() for path in first.output_dir.iterdir()
    } == {
        path.name: path.read_bytes() for path in second.output_dir.iterdir()
    }


def test_repeated_generation_to_same_set_is_idempotent(tmp_path: Path) -> None:
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert first.idempotent is False
    assert second.idempotent is True
    assert first.artifact_hashes == second.artifact_hashes


def test_manifest_has_stable_sources_hashes_and_inactive_flags(tmp_path: Path) -> None:
    result = _build(tmp_path)
    manifest = _payload(result.output_dir, "manifest.json")

    assert result.source_hashes == EXPECTED_SOURCE_HASHES
    assert manifest["artifact_schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert manifest["artifact_set_id"] == result.artifact_set_id
    assert manifest["runtime_activation_allowed"] is False
    assert manifest["write_activation_allowed"] is False
    assert manifest["integration_allowed"] is False
    assert manifest["default_loader_mode"] == "legacy"
    assert manifest["supported_loader_modes"] == ["legacy", "artifact_validation"]
    assert set(manifest["artifacts"]) == set(ARTIFACT_FILENAMES)
    assert all(len(item["sha256"]) == 64 for item in manifest["artifacts"].values())


def test_manifest_and_artifacts_have_expected_counts(tmp_path: Path) -> None:
    package = _build(tmp_path).output_dir
    manifest = _payload(package, "manifest.json")

    assert manifest["counts"]["taxonomy"] == {"groups": 37, "material_types": 978}
    assert manifest["counts"]["fields"] == {"fields": 558}
    assert manifest["counts"]["characteristic_assignments"] == {
        "assignments": 930,
        "review_excluded": 48,
        "source_assignments": 978,
    }
    assert manifest["counts"]["units"] == {
        "eligible_units": 73,
        "review_excluded": 17,
        "source_units": 90,
    }
    assert manifest["counts"]["conversions"] == {
        "conversions": 47,
        "formula": 7,
        "simple": 12,
        "technical": 28,
    }
    assert manifest["counts"]["packaging"] == {
        "assignments": 633,
        "mismatch_material_types_excluded": 316,
        "profiles": 21,
        "review_excluded": 51,
        "source_assignments": 978,
        "unique_excluded_assignments": 345,
    }
    assert manifest["counts"]["rules"] == {
        "consumption": 5,
        "coverage": 2,
        "geometry": 7,
        "rules": 15,
        "yield": 1,
    }


def test_review_entries_and_packaging_mismatches_are_excluded_and_diagnostic(tmp_path: Path) -> None:
    package = _build(tmp_path).output_dir
    compatibility = _payload(package, "compatibility.json")
    assignments = _payload(package, "characteristic_assignments.json")["assignments"]
    units = _payload(package, "units.json")["units"]
    packaging = _payload(package, "packaging.json")["assignments"]
    review = compatibility["review_exclusions"]

    assert len(review["ref2_assignment_material_types"]) == 48
    assert len(review["ref3_unit_codes"]) == 17
    assert len(review["ref3_packaging_material_types"]) == 51
    assert compatibility["diagnostics"]["packaging_ref2_mismatch_count"] == 345
    assert compatibility["diagnostics"]["packaging_ref2_mismatch_material_types"] == 316
    assert not set(review["ref2_assignment_material_types"]) & {item["material_type_id"] for item in assignments}
    assert not set(review["ref3_unit_codes"]) & {item["code"] for item in units}
    assert not set(review["ref3_packaging_material_types"]) & {item["material_type_id"] for item in packaging}


def test_taxonomy_compatibility_preserves_legacy_without_ref_writes(tmp_path: Path) -> None:
    package = _build(tmp_path).output_dir
    taxonomy = _payload(package, "taxonomy.json")
    compatibility = _payload(package, "compatibility.json")["taxonomy"]

    assert len(compatibility["legacy_groups"]) == 19
    assert len(compatibility["legacy_material_types"]) == 192
    assert len(compatibility["ref_only_groups"]) == 18
    assert len(compatibility["ref_only_material_types"]) == 786
    liquid = [item for item in taxonomy["material_types"] if item["code"] == "liquid_waterproofing"]
    conflict = compatibility["special_conflicts"][0]
    assert len(liquid) == 1
    assert liquid[0]["canonical_parent"] == "waterproofing"
    assert set(conflict["legacy_parent_paths"]) == {"primers_chemicals_sealants", "waterproofing"}
    assert conflict["write_eligible"] is False
    assert all(item["write_eligible"] is False for item in taxonomy["material_types"])


def test_lm_and_linear_meter_are_never_automatically_conflated(tmp_path: Path) -> None:
    package = _build(tmp_path).output_dir
    compatibility = _payload(package, "compatibility.json")
    rule = next(item for item in compatibility["units"]["special_alias_rules"] if item["alias"] == "lm")

    assert rule["canonical_owner"] == "lm"
    assert rule["canonical_owner_meaning"] == "lumen"
    assert rule["legacy_target"] == "linear_meter"
    assert rule["canonical_output_when_context_confirms"] == "linear_meter"
    assert rule["automatic_mapping_allowed"] is False
    assert rule["rejected_automatic_mapping"] is True


def test_ref2_is_flattened_and_legacy_fields_remain_compatibility_metadata(tmp_path: Path) -> None:
    package = _build(tmp_path).output_dir
    assignments = _payload(package, "characteristic_assignments.json")
    fields = _payload(package, "compatibility.json")["fields"]

    assert assignments["authoring_inheritance_present"] is False
    assert all(item["inheritance_resolved"] is True for item in assignments["assignments"])
    assert all(item["required_semantics_active"] is False for item in assignments["assignments"])
    assert fields["runtime_only_fields"] == 28
    assert fields["overlap_fields"] == 46
    assert fields["schema_comparison"]["legacy_schema_count"] == 13
    assert fields["schema_comparison"]["required_equal"] == 0
    assert all(item["automatic_action"] == "FORBIDDEN" for item in fields["runtime_fields"])


def test_conversions_packaging_and_extended_rules_remain_inactive(tmp_path: Path) -> None:
    package = _build(tmp_path).output_dir
    conversions = _payload(package, "conversions.json")
    packaging = _payload(package, "packaging.json")
    rules = _payload(package, "rules_metadata.json")

    assert all(item["executable"] is False for item in conversions["conversions"])
    assert packaging["characteristic_contract_separate"] is True
    assert all(item["characteristic_fields_injected"] is False for item in packaging["assignments"])
    assert rules["executable_rule_count"] == 0
    assert rules["object_work_quantity_calculations"] == 0
    assert all(item["executable"] is False for item in rules["geometry_rules"] + rules["extended_rules"])


def test_artifacts_do_not_contain_environment_specific_content(tmp_path: Path) -> None:
    result = _build(tmp_path)
    content = b"\n".join(path.read_bytes() for path in result.output_dir.iterdir()).decode("utf-8")

    assert "C:\\tmp" not in content
    assert "C:\\Users" not in content
    assert str(Path.home()) not in content
    assert "generated_at" not in content
    assert "http://" not in content
    assert "https://" not in content
    assert result.package_size_bytes < 8 * 1024 * 1024
    assert result.generation_duration_ms > 0
