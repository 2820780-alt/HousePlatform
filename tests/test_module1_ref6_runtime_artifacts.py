from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from tools.module1_ref_projection.ref6 import (
    ARTIFACT_FILENAMES,
    ARTIFACT_SET_ID,
    EXPECTED_COUNTS,
    EXPECTED_REVIEW_WORK_CODES,
    SAFE_EXAMPLES,
    SOURCE_HASHES,
    build_ref6_runtime_artifacts,
    load_ref6_source_package,
    validate_ref6_runtime_artifacts,
)
from tools.module1_ref_projection.ref6_approval import (
    APPROVAL_ID,
    build_expected_ref6_approval,
    validate_ref6_approval,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
RUNTIME_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
FUTURE_ANALYZER_PATH = (
    PROJECT_ROOT / "docs" / "Modules" / "module1" / "M1-ANALYZER-SOURCE-LIFECYCLE-FUTURE.md"
)
FUTURE_ANALYZER_SHA256 = "caf223aab4c7dd9ac5197416f6c6cff0581807250e3d33e3310e44b202fba444"
WORK_CATALOG_SHA256 = "2129670ddc418b2ce91a15c5d8a7b82130c352a5405f5a423e4121b57d45d78b"


def test_approved_source_and_future_analyzer_hashes_are_exact() -> None:
    for name, expected in SOURCE_HASHES.items():
        assert _sha256(REFERENCE_ROOT / name) == expected
    assert _sha256(FUTURE_ANALYZER_PATH) == FUTURE_ANALYZER_SHA256
    assert _sha256(
        PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "work_catalog_seed.json"
    ) == WORK_CATALOG_SHA256


def test_source_counts_work_parity_and_ref1_targets_are_exact() -> None:
    source, hashes = load_ref6_source_package()
    work_catalog = _json(
        PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "work_catalog_seed.json"
    )
    ref1 = _json(
        REFERENCE_ROOT / "ATOM_REF1_Material_Taxonomy_v2_PRELIMINARY_APPROVED.json"
    )
    profiles = source["work_profiles"]
    mappings = source["role_mappings"]
    assert source["status"] == "preliminary_approved"
    assert source["approval"]["approved_by_user"] is True
    assert source["approval"]["codex_may_expand_content"] is False
    assert hashes == dict(SOURCE_HASHES)
    assert source["counts"] == dict(EXPECTED_COUNTS)
    assert len(work_catalog["groups"]) == 24
    assert len(work_catalog["works"]) == 209
    work_codes = [item["work_code"] for item in work_catalog["works"]]
    profile_codes = [item["work_code"] for item in profiles]
    assert len(work_codes) == len(set(work_codes))
    assert len(profile_codes) == len(set(profile_codes))
    assert set(work_codes) == set(profile_codes)
    assert Counter(item["material_policy"] for item in profiles) == Counter(
        {"NO_MATERIAL": 39, "DIRECT": 80, "CONDITIONAL": 87, "REVIEW_ONLY": 3}
    )
    assert Counter(item["execution_status"] for item in mappings) == Counter(
        {"SAFE_HINT": 82, "CONDITIONAL_HINT": 104, "REVIEW_ONLY": 7}
    )
    mapping_ids = [item["mapping_id"] for item in mappings]
    mapping_keys = [
        (item["work_code"], item["role_code"], tuple(item["target_material_type_ids"]))
        for item in mappings
    ]
    assert len(mapping_ids) == len(set(mapping_ids))
    assert len(mapping_keys) == len(set(mapping_keys))
    ref1_types = {item["material_type_id"] for item in ref1["material_types"]}
    targets = {target for item in mappings for target in item["target_material_type_ids"]}
    assert len(ref1_types) == 978
    assert targets <= ref1_types


def test_safe_review_no_material_and_evidence_contracts_are_preserved() -> None:
    source, _ = load_ref6_source_package()
    mappings = source["role_mappings"]
    review = source["review_queue"]
    evidence = source["existing_material_role_evidence"]
    for work_code, target in SAFE_EXAMPLES.items():
        assert any(
            item["work_code"] == work_code
            and item["execution_status"] == "SAFE_HINT"
            and target in item["target_material_type_ids"]
            for item in mappings
        )
    assert len(review) == 10
    assert Counter(item["review_kind"] for item in review) == Counter(
        {"work_classification": 3, "role_mapping": 7}
    )
    assert {item["work_code"] for item in review} == EXPECTED_REVIEW_WORK_CODES
    assert all(item["automatic_approval_allowed"] is False for item in review)
    assert len(evidence) == 42
    assert all(item["status"] == "evidence_only" for item in evidence)
    assert all(
        item["promoted_to_executable_mapping_automatically"] is False
        for item in evidence
    )
    assert all(
        item["quantity_calculation_allowed"] is False
        and item["quantity_formula_activation_allowed"] is False
        and item["sku_selection_allowed"] is False
        and item["catalog_product_selection_allowed"] is False
        and item["material_creation_allowed"] is False
        and item["database_write_allowed"] is False
        and item["module2_execution_allowed"] is False
        and item["module5_costing_allowed"] is False
        for item in mappings
    )


def test_artifacts_are_exact_deterministic_and_canonical(tmp_path: Path) -> None:
    first = build_ref6_runtime_artifacts(output_root=tmp_path / "first")
    second = build_ref6_runtime_artifacts(output_root=tmp_path / "second")
    expected_files = set(ARTIFACT_FILENAMES) | {"manifest.json"}
    assert {item.name for item in first.artifact_dir.iterdir()} == expected_files
    assert {item.name for item in second.artifact_dir.iterdir()} == expected_files
    for name in expected_files:
        first_bytes = (first.artifact_dir / name).read_bytes()
        second_bytes = (second.artifact_dir / name).read_bytes()
        assert first_bytes == second_bytes
        assert not first_bytes.startswith(b"\xef\xbb\xbf")
        assert b"\r\n" not in first_bytes
        assert first_bytes.endswith(b"\n")
    manifest = validate_ref6_runtime_artifacts(first.artifact_dir)
    assert manifest["counts"] == dict(EXPECTED_COUNTS)
    assert manifest["quantity_calculation_allowed"] is False
    assert manifest["ref3_formula_activation_allowed"] is False
    assert manifest["database_write_allowed"] is False


def test_repository_runtime_artifact_and_approval_are_valid() -> None:
    artifact = RUNTIME_ROOT / ARTIFACT_SET_ID
    manifest = validate_ref6_runtime_artifacts(artifact)
    validation = validate_ref6_approval()
    approval = build_expected_ref6_approval()
    assert manifest["artifact_set_id"] == ARTIFACT_SET_ID
    assert manifest["counts"] == dict(EXPECTED_COUNTS)
    assert validation.is_valid is True
    assert validation.issues == tuple()
    assert approval["approval_id"] == APPROVAL_ID
    assert approval["decision_number"] == 41
    assert approval["approved_modes"] == ["approved"]
    assert approval["approved_scope"] == "module1_ref6_governed_work_material_hints"
    assert approval["activation_flags"]["safe_role_hint_execution_as_type_hint_allowed"] is True
    assert approval["activation_flags"]["conditional_hint_execution_allowed"] is False
    assert approval["activation_flags"]["database_write_allowed"] is False
    assert approval["rollback_policy"]["target_mode"] == "legacy"
    assert approval["rollback_policy"]["database_update"] is False


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
