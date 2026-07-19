from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.module1_ref_projection.ref45 import (
    ARTIFACT_FILENAMES,
    ARTIFACT_SET_ID,
    EXPECTED_COUNTS,
    REFERENCE_ROOT,
    SOURCE_FILES,
    Ref45BuildError,
    build_legacy_compatibility,
    build_ref45_runtime_artifacts,
    load_ref45_source_package,
    validate_ref45_runtime_artifacts,
)
from tools.module1_ref_projection.ref45_approval import (
    APPROVAL_ID,
    APPROVAL_PATH,
    TOP_LEVEL_KEYS,
    build_expected_ref45_approval,
    serialize_ref45_approval,
    validate_ref45_approval,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / "src/modules/module1/runtime_reference" / ARTIFACT_SET_ID


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_six_approved_source_hashes_status_and_correction() -> None:
    payloads, hashes = load_ref45_source_package(REFERENCE_ROOT)

    assert hashes == {key: expected for key, (_name, expected) in SOURCE_FILES.items()}
    assert payloads["REF-4"]["status"] == "preliminary_approved"
    assert payloads["REF-5"]["status"] == "preliminary_approved"
    assert payloads["REF-45-CORRECTION"]["status"] == "approved_correction"
    assert payloads["REF-45-CORRECTION"]["approval"]["approved_by_user"] is True


def test_ref4_counts_targets_and_corrected_rules() -> None:
    payloads, _ = load_ref45_source_package(REFERENCE_ROOT)
    ref4 = payloads["REF-4"]
    aliases = ref4["alias_rules"]
    corrected = {item["alias_rule_id"]: item for item in aliases if item["alias_rule_id"] in {"legacy_alias_060", "legacy_alias_061", "legacy_alias_062"}}

    assert len(ref4["material_type_profiles"]) == 978
    assert len(aliases) == 89
    assert sum(item["automatic_material_type_resolution_allowed"] for item in aliases) == 44
    assert sum(not item["automatic_material_type_resolution_allowed"] for item in aliases) == 45
    assert len({item["alias_rule_id"] for item in aliases}) == 89
    assert set(corrected) == {"legacy_alias_060", "legacy_alias_061", "legacy_alias_062"}
    for item in corrected.values():
        assert item["legacy_normalized_value"] == "gypsum_board_regular"
        assert item["scope"] == "gypsum_board_regular"
        assert item["classification"] == "context_required"
        assert item["status"] == "review_required"
        assert item["automatic_material_type_resolution_allowed"] is False

    taxonomy = _read(REFERENCE_ROOT / "ATOM_REF1_Material_Taxonomy_v2_PRELIMINARY_APPROVED.json")
    ids = {item["material_type_id"] for item in taxonomy["material_types"]}
    assert {target for item in aliases for target in item["target_material_type_ids"]} <= ids


def test_ref4_has_exact_all_89_legacy_parity() -> None:
    ref4 = load_ref45_source_package(REFERENCE_ROOT)[0]["REF-4"]
    result = build_legacy_compatibility(ref4)

    assert result["counts"] == {
        "approved_rules": 89,
        "exact_parity": 89,
        "legacy_rules": 89,
        "missing_from_approved": 0,
        "not_in_legacy": 0,
        "review_or_context": 45,
        "trusted": 44,
    }
    assert result["missing_from_approved"] == []
    assert result["not_in_legacy"] == []
    assert result["conflicts"] == []


def test_ref5_counts_review_and_execution_boundaries() -> None:
    ref5 = load_ref45_source_package(REFERENCE_ROOT)[0]["REF-5"]
    substitutions = ref5["substitution_rules"]

    assert len(ref5["context_compatibility_rules"]) == 15
    assert len(substitutions) == 13
    assert sum(item["status"] in {"active_read_only_policy", "active_safety_guard"} for item in substitutions) == 3
    assert len(ref5["review_queue"]) == 10
    assert not any(item["automatic_selection_allowed"] for item in substitutions)
    assert not any(item["automatic_write_allowed"] for item in substitutions)
    assert not any(item["module2_calculation_performed"] for item in substitutions)
    assert not any(item["module5_costing_performed"] for item in substitutions)
    assert ref5["validation"]["work_material_mappings_created"] == 0


def test_runtime_package_has_exact_files_hashes_counts_and_canonical_bytes() -> None:
    manifest = validate_ref45_runtime_artifacts(RUNTIME_DIR)

    assert {item.name for item in RUNTIME_DIR.iterdir()} == set(ARTIFACT_FILENAMES) | {"manifest.json"}
    assert manifest["counts"] == EXPECTED_COUNTS
    for name in (*ARTIFACT_FILENAMES, "manifest.json"):
        raw = (RUNTIME_DIR / name).read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")
        assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
        assert b"\r\n" not in raw
        assert json.loads(raw.decode("utf-8"))


def test_runtime_generation_is_byte_deterministic_8_of_8(tmp_path: Path) -> None:
    first = build_ref45_runtime_artifacts(output_root=tmp_path / "first").output_dir
    second = build_ref45_runtime_artifacts(output_root=tmp_path / "second").output_dir
    names = sorted(item.name for item in first.iterdir())

    assert len(names) == 8
    assert names == sorted(item.name for item in second.iterdir())
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in names)


def test_runtime_generation_rejects_changed_immutable_package(tmp_path: Path) -> None:
    result = build_ref45_runtime_artifacts(output_root=tmp_path)
    (result.output_dir / "ref4_alias_rules.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(Ref45BuildError, match="Immutable runtime package"):
        build_ref45_runtime_artifacts(output_root=tmp_path)


def test_approval_is_canonical_pinned_and_valid() -> None:
    payload = build_expected_ref45_approval()
    validation = validate_ref45_approval()

    assert set(payload) == TOP_LEVEL_KEYS
    assert payload["approval_id"] == APPROVAL_ID
    assert payload["decision_number"] == 40
    assert payload["approved_modes"] == ["approved"]
    assert payload["approved_scope"] == "module1_ref4_ref5_governed_policy"
    assert payload["counts"] == EXPECTED_COUNTS
    assert payload["activation_flags"]["automatic_replacement_allowed"] is False
    assert payload["activation_flags"]["write_activation_allowed"] is False
    assert payload["rollback_policy"]["target_mode"] == "legacy"
    assert payload["rollback_policy"]["requires_restart"] is True
    assert APPROVAL_PATH.read_bytes() == serialize_ref45_approval(payload)
    assert validation.is_valid is True
    assert validation.approval_sha256 == hashlib.sha256(APPROVAL_PATH.read_bytes()).hexdigest()


def test_approval_validation_fails_for_changed_content(tmp_path: Path) -> None:
    payload = build_expected_ref45_approval()
    payload["activation_flags"]["automatic_replacement_allowed"] = True
    candidate = tmp_path / "approval_manifest.json"
    candidate.write_bytes(serialize_ref45_approval(payload))

    validation = validate_ref45_approval(candidate)

    assert validation.is_valid is False
    assert {issue.code for issue in validation.issues} == {"APPROVAL_CONTENT_INVALID"}