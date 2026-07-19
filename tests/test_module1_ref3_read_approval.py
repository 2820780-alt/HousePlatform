from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.config import settings
from app.services.module1_ref_runtime_artifacts import SUPPORTED_MODES
from tools.module1_ref_projection.ref3_read_approval import (
    APPROVAL_ID,
    APPROVAL_PATH,
    APPROVAL_SCHEMA_VERSION,
    APPROVAL_VERSION,
    EXPECTED_COUNTS,
    PURPOSE_ALLOWLIST,
    PURPOSE_DENYLIST,
    REF1_APPROVAL_ID,
    REF1_APPROVAL_PATH,
    REF1_APPROVAL_SHA256,
    REF2_APPROVAL_ID,
    REF2_APPROVAL_PATH,
    REF2_APPROVAL_SHA256,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PACKAGE_DIR,
    RUNTIME_PACKAGE_ID,
    TOP_LEVEL_KEYS,
    build_expected_ref3_read_approval,
    serialize_ref3_read_approval,
    validate_ref3_read_approval,
    write_expected_ref3_read_approval,
)

EXPECTED_ARTIFACT_HASHES = {
    "compatibility": "43cf3b1bce4f0424ec9204de51cb09138b452ab2a365f3a7747292937848c726",
    "conversions": "4a3e6371391a3fc798a6d7ba92f8f95a9c188785ae28e0f827c4b3bb167b2555",
    "packaging": "1ab014d3e349d6486c9dceb8f13601a438de2be8c0fd0c3f1fe3e0316ca0ec2a",
    "rules": "53a293dfad1913e873dfd6b370c58573b50213d3e0e3357c3808aa86f932334f",
    "units": "7a3f8a6298977bb88616aeaafa0e9fa49a09cc10b653ec9d59bd96e318fb8e38",
}
EXPECTED_SOURCE_HASHES = {
    "ATOM_REF1_Material_Taxonomy_v2_PRELIMINARY_APPROVED.json": "48ed52a10d0192eecc7be649608c1ebc2ee5635617c34198133b030584ae0100",
    "ATOM_REF2_Field_Dictionary_v1_DRAFT.json": "22b3201b55381a1da626aab2e8fea066e94882f97a237495b8ac7307c50adc5d",
    "ATOM_REF2_Material_Characteristic_Profiles_v1_DRAFT.json": "1ac98e68f88c6f8288c534452bd46de5308808ae1e6f60446f124e0af08beb3c",
    "ATOM_REF3_Geometry_Coverage_Consumption_Rules_v1_DRAFT.json": "23eefba57ef415527db3f9cf0fa395614d7064c06d2db753f4072209560b7b28",
    "ATOM_REF3_Package_Manifest_v1_DRAFT.json": "30bde8789f2352797b41cf41cf8f86bea35103f026d5222741a7988bb750799a",
    "ATOM_REF3_Packaging_Quantity_Profiles_v1_DRAFT.json": "e42f6b0dede8eff8bd33146477ae909990892924d802b5cb37e326262977252b",
    "ATOM_REF3_Unit_Dictionary_v1_DRAFT.json": "342957cf9ea88ee9873595d1bac4c848d50b3423d2a61fdeadf2556f3e522cfb",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_path(tmp_path: Path) -> Path:
    return tmp_path / "approvals" / APPROVAL_ID / "approval_manifest.json"


def _write_candidate(tmp_path: Path, payload: dict) -> Path:
    path = _candidate_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(serialize_ref3_read_approval(payload))
    return path


def test_exact_identity_path_schema_scope_mode_and_keys() -> None:
    payload = _read(APPROVAL_PATH)
    project_root = Path(__file__).resolve().parents[1]

    assert APPROVAL_PATH.relative_to(project_root).as_posix() == (
        "src/modules/module1/runtime_reference/approvals/"
        "ref3-read-v1-1a15fed6ebdd/approval_manifest.json"
    )
    assert payload["approval_id"] == APPROVAL_ID == "ref3-read-v1-1a15fed6ebdd"
    assert APPROVAL_ID == f"ref3-read-v1-{RUNTIME_MANIFEST_SHA256[:12]}"
    assert payload["approval_schema_version"] == APPROVAL_SCHEMA_VERSION == "1.0"
    assert payload["approval_version"] == APPROVAL_VERSION == "1.0"
    assert set(payload) == TOP_LEVEL_KEYS
    assert payload["decision_number"] == 38
    assert payload["approved_scope"] == "module1_ref3_read_only_admin_projections"
    assert payload["approved_modes"] == ["ref3_read"]


def test_prerequisite_approvals_are_exact_and_immutable() -> None:
    prerequisites = _read(APPROVAL_PATH)["prerequisite_approvals"]

    assert prerequisites == [
        {"approval_id": REF1_APPROVAL_ID, "approval_sha256": REF1_APPROVAL_SHA256, "required_mode": "ref1_read"},
        {"approval_id": REF2_APPROVAL_ID, "approval_sha256": REF2_APPROVAL_SHA256, "required_mode": "ref2_read"},
    ]
    assert _sha256(REF1_APPROVAL_PATH) == REF1_APPROVAL_SHA256
    assert _sha256(REF2_APPROVAL_PATH) == REF2_APPROVAL_SHA256


def test_runtime_package_artifacts_and_sources_are_pinned() -> None:
    payload = _read(APPROVAL_PATH)
    manifest = _read(RUNTIME_PACKAGE_DIR / "manifest.json")
    runtime = payload["runtime_package"]

    assert runtime["package_id"] == RUNTIME_PACKAGE_ID == manifest["artifact_set_id"]
    assert runtime["manifest_sha256"] == RUNTIME_MANIFEST_SHA256
    assert runtime["manifest_sha256"] == _sha256(RUNTIME_PACKAGE_DIR / "manifest.json")
    assert runtime["artifact_schema_version"] == "1.0"
    assert runtime["compatibility_map_version"] == "1.0"
    assert runtime["artifact_hashes"] == EXPECTED_ARTIFACT_HASHES
    assert runtime["source_hashes"] == EXPECTED_SOURCE_HASHES
    artifact_files = {
        "compatibility": "compatibility.json",
        "conversions": "conversions.json",
        "packaging": "packaging.json",
        "rules": "rules_metadata.json",
        "units": "units.json",
    }
    for key, filename in artifact_files.items():
        assert runtime["artifact_hashes"][key] == _sha256(RUNTIME_PACKAGE_DIR / filename)


def test_all_counts_are_exact_including_computed_packaging_overlap() -> None:
    counts = _read(APPROVAL_PATH)["counts"]
    compatibility = _read(RUNTIME_PACKAGE_DIR / "compatibility.json")
    review = set(compatibility["review_exclusions"]["ref3_packaging_material_types"])
    mismatches = {
        item["material_type_id"]
        for item in compatibility["diagnostics"]["packaging_ref2_mismatches"]
    }

    assert counts == EXPECTED_COUNTS
    assert len(review) == 51
    assert len(compatibility["diagnostics"]["packaging_ref2_mismatches"]) == 345
    assert len(mismatches) == 316
    assert len(review & mismatches) == counts["packaging_review_mismatch_overlap"] == 22
    assert counts["packaging_assignments_total"] - len(review | mismatches) == 633


def test_purpose_projection_and_unit_policies_are_exact() -> None:
    payload = _read(APPROVAL_PATH)

    assert payload["purpose_policy"] == {
        "allow": list(PURPOSE_ALLOWLIST),
        "deny": list(PURPOSE_DENYLIST),
        "purpose_source": "server_owned",
        "unknown_purpose": "deny",
    }
    assert payload["projection_policy"] == {
        "cache_bounded": True,
        "cache_invalidation": "restart_or_package_approval_change",
        "cache_key_components": ["runtime_package_id", "ref3_approval_id", "purpose"],
        "existing_public_registries_extended": False,
        "lazy_load": True,
        "projection_names": ["units_and_conversions", "packaging", "extended_rules"],
        "projection_scope": "private_internal",
        "second_public_registry_allowed": False,
        "startup_behavior": "validate_package_and_approvals_only",
    }
    assert payload["unit_alias_policy"] == {
        "automatic_legacy_lm_mapping_allowed": False,
        "canonical_lm_meaning": "lumen",
        "canonical_output_for_linear_meter": "linear_meter",
        "legacy_lm_to_linear_meter": "context_required",
        "linear_meter_canonical_code": "linear_meter",
        "review_excluded_codes": ["linear_meter", "m2_mm"],
    }
    assert payload["unit_policy"] == {
        "eligible_units_visible_for_admin_read": True,
        "existing_runtime_registry_extended": False,
        "existing_runtime_registry_replaced": False,
        "legacy_unit_execution_source_of_truth": True,
        "ref_only_unit_write_allowed": False,
        "review_excluded_interpretation": "unit_review_excluded",
        "review_excluded_units_visible_as_approved": False,
    }


def test_conversion_packaging_and_rule_policies_are_non_executable() -> None:
    payload = _read(APPROVAL_PATH)

    assert payload["conversion_policy"] == {
        "formula_conversion_execution_allowed": False,
        "formula_conversions": "metadata_only",
        "legacy_conversion_executor_source_of_truth": True,
        "ref_conversion_execution_allowed": False,
        "simple_conversions": "admin_metadata_only",
        "technical_conversions": "parameters_required_metadata_only",
        "technical_execution_without_parameters_allowed": False,
    }
    assert payload["packaging_policy"] == {
        "automatic_correction_allowed": False,
        "eligible_assignments_visible_for_admin_read": True,
        "mismatch_policy": "diagnostics_only",
        "package_quantity_is_characteristic": False,
        "packaging_write_allowed": False,
        "price_basis_is_characteristic": False,
        "ref2_field_injection_allowed": False,
        "review_excluded_interpretation": "packaging_review_excluded",
        "review_excluded_visible_as_approved": False,
    }
    assert payload["rule_policy"] == {
        "formula_strings_executable": False,
        "module2_execution_allowed": False,
        "object_scope_calculation_allowed": False,
        "ref6_mapping_required_for_work_execution": True,
        "rule_execution_allowed": False,
        "rule_visibility": "admin_metadata_only",
        "work_scope_calculation_allowed": False,
    }


def test_write_execution_rollback_and_activation_policies_are_exact() -> None:
    payload = _read(APPROVAL_PATH)

    assert payload["write_execution_policy"] == {
        "catalog_product_write_for_ref3_only_metadata": False,
        "legacy_behavior_unchanged": True,
        "matching_for_ref3_only_metadata": False,
        "material_write_for_ref3_only_metadata": False,
        "moderation_for_ref3_only_metadata": False,
        "module2_execution": False,
        "module5_execution": False,
        "normalizer_output_for_ref3_only_metadata": False,
        "readiness_export_for_ref3_only_metadata": False,
        "work_cost_usage": False,
    }
    assert payload["rollback_policy"] == {
        "allowed_target_modes": ["ref2_read"],
        "artifact_deletion_required": False,
        "database_migration_required": False,
        "database_update_required": False,
        "existing_records_reclassification_required": False,
        "legacy_registry_update_required": False,
        "requires_restart": True,
        "stale_ref3_code_behavior": "ignore_as_unknown",
    }
    assert payload["activation_flags"] == {
        "conversion_execution_allowed": False,
        "module2_execution_allowed": False,
        "module5_execution_allowed": False,
        "packaging_write_allowed": False,
        "rule_execution_allowed": False,
        "runtime_activation_allowed": True,
        "write_activation_allowed": False,
    }


def test_canonical_serialization_is_exact_and_deterministic(tmp_path: Path) -> None:
    payload = build_expected_ref3_read_approval()
    first = write_expected_ref3_read_approval(_candidate_path(tmp_path / "first"))
    second = write_expected_ref3_read_approval(_candidate_path(tmp_path / "second"))
    raw = APPROVAL_PATH.read_bytes()

    assert payload["canonical_serialization"] == {
        "bom": False, "encoding": "UTF-8", "ensure_ascii": False,
        "hash_algorithm": "SHA-256", "indent": 2, "line_ending": "LF",
        "sort_keys": True, "trailing_newline": True,
    }
    assert first.read_bytes() == second.read_bytes() == raw
    assert raw == serialize_ref3_read_approval(payload)
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert _sha256(first) == _sha256(second) == _sha256(APPROVAL_PATH)
    assert b"C:\\" not in raw and b"timestamp" not in raw and b"uuid" not in raw


def test_pure_validator_accepts_committed_approval() -> None:
    result = validate_ref3_read_approval()

    assert result.is_valid is True
    assert result.issues == ()
    assert result.approval_sha256 == _sha256(APPROVAL_PATH)


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    [
        (lambda p: p.update(extra=True), "TOP_LEVEL_KEYS_EXTRA"),
        (lambda p: p.pop("counts"), "TOP_LEVEL_KEYS_MISSING"),
        (lambda p: p.update(approval_schema_version="2.0"), "SCHEMA_VERSION_INVALID"),
        (lambda p: p.update(approved_modes=["ref2_read"]), "APPROVED_MODES_INVALID"),
        (lambda p: p["prerequisite_approvals"][0].update(approval_sha256="0" * 64), "PREREQUISITE_CONTRACT_INVALID"),
        (lambda p: p["runtime_package"].update(manifest_sha256="0" * 64), "RUNTIME_PACKAGE_INVALID"),
        (lambda p: p["purpose_policy"].update(unknown_purpose="allow"), "PURPOSE_POLICY_INVALID"),
        (lambda p: p["unit_alias_policy"].update(automatic_legacy_lm_mapping_allowed=True), "UNIT_ALIAS_POLICY_INVALID"),
        (lambda p: p["conversion_policy"].update(ref_conversion_execution_allowed=True), "CONVERSION_POLICY_INVALID"),
        (lambda p: p["packaging_policy"].update(automatic_correction_allowed=True), "PACKAGING_POLICY_INVALID"),
        (lambda p: p["rule_policy"].update(rule_execution_allowed=True), "RULE_POLICY_INVALID"),
        (lambda p: p["write_execution_policy"].update(material_write_for_ref3_only_metadata=True), "WRITE_EXECUTION_POLICY_INVALID"),
        (lambda p: p["activation_flags"].update(write_activation_allowed=True), "ACTIVATION_FLAGS_INVALID"),
    ],
)
def test_validator_fails_closed_for_contract_mutations(tmp_path: Path, mutation, expected_issue: str) -> None:
    payload = build_expected_ref3_read_approval()
    mutation(payload)
    result = validate_ref3_read_approval(_write_candidate(tmp_path, payload))

    assert result.is_valid is False
    assert expected_issue in {issue.code for issue in result.issues}


def test_validator_fails_closed_for_missing_or_changed_prerequisites(tmp_path: Path) -> None:
    missing_ref1 = validate_ref3_read_approval(ref1_approval_path=tmp_path / "missing-ref1.json")
    changed_ref2 = tmp_path / "changed-ref2.json"
    changed_ref2.write_bytes(REF2_APPROVAL_PATH.read_bytes() + b"\n")
    invalid_ref2 = validate_ref3_read_approval(ref2_approval_path=changed_ref2)

    assert "REF1_READ_APPROVAL_MISSING" in {issue.code for issue in missing_ref1.issues}
    assert "REF2_READ_APPROVAL_HASH_INVALID" in {issue.code for issue in invalid_ref2.issues}


def test_decision_and_approved_ref3_runtime_integration_are_present() -> None:
    project_root = Path(__file__).resolve().parents[1]
    decisions = (project_root / "docs" / "Decisions.md").read_text(encoding="utf-8")
    config = (project_root / "app" / "config.py").read_text(encoding="utf-8")
    app_sources = "\n".join(path.read_text(encoding="utf-8") for path in (project_root / "app").rglob("*.py"))

    heading = "## Решение №038"
    assert decisions.count(heading) == 1
    assert "Статус:\nПринято." in decisions.split(heading, 1)[1]
    assert settings.MODULE1_REF_RUNTIME_MODE == "legacy"
    assert "ref3_read" in SUPPORTED_MODES
    assert "MODULE1_REF3_APPROVAL_ID" in config
    assert "module1_ref_projection.ref3_read_approval" not in app_sources
    assert "module1_ref3_read_policy" in app_sources
    assert "/ref3-units" in app_sources
    assert "/ref3-conversions" in app_sources
    assert "/ref3-packaging" in app_sources
    assert "/ref3-extended-rules" in app_sources


def test_tooling_has_no_database_orm_ui_or_runtime_imports() -> None:
    path = Path(__file__).resolve().parents[1] / "tools/module1_ref_projection/ref3_read_approval.py"
    text = path.read_text(encoding="utf-8")

    for forbidden in (
        "sqlalchemy", "app.database", "app.models", "app.services", "templates",
        "Dashboard", "Quick Actions", "module1_unit_conversion_registry",
    ):
        assert forbidden not in text
