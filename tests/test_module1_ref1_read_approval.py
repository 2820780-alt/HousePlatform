from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.config import settings
from app.services.module1_material_seed_registry import get_material_knowledge_seed_registry
from app.services.module1_ref_dual_read import build_legacy_taxonomy_snapshot
from app.services.module1_ref_runtime_artifacts import SUPPORTED_MODES
from tools.module1_ref_projection.ref1_read_approval import (
    APPROVAL_ID,
    APPROVAL_PATH,
    APPROVAL_SCHEMA_VERSION,
    APPROVAL_VERSION,
    APPROVED_PURPOSES,
    DENIED_PURPOSES,
    RUNTIME_PACKAGE_DIR,
    RUNTIME_PACKAGE_ID,
    build_expected_ref1_read_approval,
    serialize_ref1_read_approval,
    validate_ref1_read_approval,
    write_expected_ref1_read_approval,
)


EXPECTED_MANIFEST_SHA256 = "1a15fed6ebddb77c293b8a77539f790b5733215ef3a748a52f3c83a33fe75e9f"
EXPECTED_SOURCE_HASHES = {
    "ATOM_REF1_Material_Taxonomy_v2_PRELIMINARY_APPROVED.json": "48ed52a10d0192eecc7be649608c1ebc2ee5635617c34198133b030584ae0100",
    "ATOM_REF2_Field_Dictionary_v1_DRAFT.json": "22b3201b55381a1da626aab2e8fea066e94882f97a237495b8ac7307c50adc5d",
    "ATOM_REF2_Material_Characteristic_Profiles_v1_DRAFT.json": "1ac98e68f88c6f8288c534452bd46de5308808ae1e6f60446f124e0af08beb3c",
    "ATOM_REF3_Geometry_Coverage_Consumption_Rules_v1_DRAFT.json": "23eefba57ef415527db3f9cf0fa395614d7064c06d2db753f4072209560b7b28",
    "ATOM_REF3_Package_Manifest_v1_DRAFT.json": "30bde8789f2352797b41cf41cf8f86bea35103f026d5222741a7988bb750799a",
    "ATOM_REF3_Packaging_Quantity_Profiles_v1_DRAFT.json": "e42f6b0dede8eff8bd33146477ae909990892924d802b5cb37e326262977252b",
    "ATOM_REF3_Unit_Dictionary_v1_DRAFT.json": "342957cf9ea88ee9873595d1bac4c848d50b3423d2a61fdeadf2556f3e522cfb",
}
EXPECTED_DENYLIST = {
    "analyzer_business_processing",
    "catalog_product_write",
    "dashboard",
    "existing_material_details",
    "existing_materials_table",
    "matching_candidate",
    "material_write",
    "moderation_approval",
    "module2_export",
    "module5_export",
    "normalizer_output",
    "readiness_export",
    "widgets",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: dict) -> None:
    path.write_bytes(serialize_ref1_read_approval(payload))


def test_approval_artifact_parse_identity_and_scope() -> None:
    payload = _read(APPROVAL_PATH)

    assert payload["approval_schema_version"] == APPROVAL_SCHEMA_VERSION == "1.0"
    assert payload["approval_id"] == APPROVAL_ID == "ref1-read-v1-1a15fed6ebdd"
    assert payload["approval_version"] == APPROVAL_VERSION == "1.0"
    assert payload["decision_number"] == "036"
    assert payload["approved_scope"] == "module1_ref1_read_only_taxonomy_projection"
    assert payload["approved_modes"] == ["ref1_read"]
    assert payload["activation_effect"] == "approval_metadata_only_no_runtime_activation"


def test_runtime_package_and_source_hashes_are_exactly_pinned() -> None:
    payload = _read(APPROVAL_PATH)
    manifest_path = RUNTIME_PACKAGE_DIR / "manifest.json"
    manifest = _read(manifest_path)

    assert payload["runtime_package_id"] == manifest["artifact_set_id"] == RUNTIME_PACKAGE_ID
    assert payload["runtime_manifest_hash"] == _sha256(manifest_path) == EXPECTED_MANIFEST_SHA256
    assert payload["source_hashes"] == EXPECTED_SOURCE_HASHES
    assert payload["source_hashes"] == {
        item["filename"]: item["sha256"] for item in manifest["source_packages"]
    }
    assert payload["source_bundle_hash"] == manifest["source_bundle_sha256"]
    assert payload["artifact_schema_version"] == manifest["artifact_schema_version"] == "1.0"
    assert payload["compatibility_map_version"] == manifest["compatibility_map_version"] == "1.0"


def test_allowlist_is_exact_and_unknown_purpose_denies() -> None:
    payload = _read(APPROVAL_PATH)

    assert tuple(payload["consumer_allowlist"]) == APPROVED_PURPOSES
    assert payload["consumer_allowlist"] == ["admin_taxonomy_read", "internal_diagnostics"]
    assert payload["consumer_bindings"] == {
        "admin_taxonomy_read": "module1.admin.taxonomy_view",
        "internal_diagnostics": "module1.internal.ref_diagnostics",
    }
    assert payload["read_policy"]["unknown_purpose"] == "deny"
    assert payload["read_policy"]["unknown_code"] == "deny"


def test_denylist_contains_only_the_approved_legacy_and_forbidden_consumers() -> None:
    payload = _read(APPROVAL_PATH)

    assert tuple(payload["consumer_denylist"]) == DENIED_PURPOSES
    assert set(payload["consumer_denylist"]) == EXPECTED_DENYLIST
    assert set(payload["consumer_allowlist"]).isdisjoint(payload["consumer_denylist"])


def test_activation_metadata_allows_future_read_but_no_write_ref2_or_ref3() -> None:
    payload = _read(APPROVAL_PATH)

    assert payload["integration_allowed_for_read"] is True
    assert payload["runtime_activation_allowed"] is True
    assert payload["write_activation_allowed"] is False
    assert payload["ref2_activation_allowed"] is False
    assert payload["ref3_activation_allowed"] is False


def test_legacy_and_ref_only_write_policies_are_separated() -> None:
    payload = _read(APPROVAL_PATH)
    reads = payload["read_policy"]
    writes = payload["write_policy"]
    ref_only = writes["ref_only_material_types"]

    assert reads["legacy_material_types"] == {
        "count": 192,
        "recognised_for_legacy_read": True,
        "write_behavior": "unchanged_legacy",
    }
    assert reads["ref_only_material_types"] == {
        "count": 786,
        "recognised_for_ref_read": "allowlisted_purpose_only",
    }
    assert writes["legacy_material_types"] == {
        "count": 192,
        "write_behavior": "unchanged_legacy",
    }
    assert ref_only["count"] == 786
    assert ref_only["eligible_for_material_write"] is False
    assert ref_only["eligible_for_catalog_product_write"] is False
    assert ref_only["eligible_for_normalizer_output"] is False
    assert ref_only["eligible_for_matching"] is False
    assert ref_only["eligible_for_moderation_approval"] is False
    assert ref_only["eligible_for_export"] is False


def test_liquid_waterproofing_policy_keeps_one_ref_parent_and_legacy_metadata() -> None:
    policy = _read(APPROVAL_PATH)["canonical_conflict_policies"]["liquid_waterproofing"]

    assert policy["code"] == "liquid_waterproofing"
    assert policy["canonical_ref_parent"] == "waterproofing"
    assert policy["legacy_paths"] == ["primers_chemicals_sealants", "waterproofing"]
    assert policy["legacy_paths_metadata_only"] is True
    assert policy["admin_read_uses_canonical_ref_parent"] is True
    assert policy["existing_records_migrated"] is False
    assert policy["duplicate_canonical_registration_allowed"] is False
    assert policy["ref_only_write_allowed"] is False
    assert policy["legacy_business_lookups_changed"] is False


def test_lm_policy_keeps_lumen_and_linear_meter_separate() -> None:
    policy = _read(APPROVAL_PATH)["canonical_conflict_policies"]["lm"]

    assert policy["canonical_code"] == "lm"
    assert policy["canonical_meaning"] == "lumen"
    assert policy["linear_meter_canonical_code"] == "linear_meter"
    assert policy["legacy_lm_to_linear_meter"] == "context_required"
    assert policy["automatic_normalization_allowed"] is False
    assert policy["ref3_activation_allowed"] is False


def test_rollback_is_legacy_only_without_database_or_artifact_changes() -> None:
    policy = _read(APPROVAL_PATH)["rollback_policy"]

    assert policy["mode"] == "legacy"
    assert policy["restart_required"] is True
    assert policy["database_migration_required"] is False
    assert policy["reclassification_required"] is False
    assert policy["artifact_deletion_required"] is False
    assert policy["saved_ref_only_preferences_allowed"] is False
    assert policy["stale_ref_only_code_behavior"] == "ignore_as_unknown_without_mapping_or_write"


def test_approval_bytes_are_deterministic_and_match_two_rebuilds(tmp_path: Path) -> None:
    first = write_expected_ref1_read_approval(tmp_path / "first" / "approval_manifest.json")
    second = write_expected_ref1_read_approval(tmp_path / "second" / "approval_manifest.json")

    assert first.read_bytes() == second.read_bytes() == APPROVAL_PATH.read_bytes()
    assert _sha256(first) == _sha256(second) == _sha256(APPROVAL_PATH)
    assert APPROVAL_PATH.read_bytes() == serialize_ref1_read_approval(
        build_expected_ref1_read_approval()
    )
    text = APPROVAL_PATH.read_text(encoding="utf-8")
    for forbidden in ("generated_at", "current_timestamp", "absolute_path", "username", "hostname"):
        assert forbidden not in text


def test_pure_validator_accepts_committed_approval_and_unchanged_package() -> None:
    result = validate_ref1_read_approval()

    assert result.is_valid is True
    assert result.issues == ()
    assert result.approval_sha256 == _sha256(APPROVAL_PATH)


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    [
        (lambda p: p.update(approval_schema_version="999"), "SCHEMA_VERSION_INVALID"),
        (lambda p: p.update(decision_number="035"), "DECISION_INVALID"),
        (lambda p: p.update(runtime_package_id="wrong"), "PACKAGE_ID_INVALID"),
        (lambda p: p.update(runtime_manifest_hash="0" * 64), "MANIFEST_HASH_INVALID"),
        (lambda p: p.update(source_hashes={}), "SOURCE_HASHES_INVALID"),
        (lambda p: p.update(compatibility_map_version="999"), "COMPATIBILITY_VERSION_INVALID"),
        (lambda p: p.update(approved_modes=["dual_read"]), "APPROVED_MODES_INVALID"),
        (lambda p: p.update(consumer_allowlist=["internal_diagnostics", "unknown"]), "ALLOWLIST_INVALID"),
        (lambda p: p.update(write_activation_allowed=True), "WRITE_ACTIVATION_INVALID"),
        (lambda p: p.update(ref2_activation_allowed=True), "REF2_ACTIVATION_INVALID"),
        (lambda p: p.update(ref3_activation_allowed=True), "REF3_ACTIVATION_INVALID"),
        (lambda p: p["rollback_policy"].update(mode="ref1_read"), "ROLLBACK_MODE_INVALID"),
        (
            lambda p: p["canonical_conflict_policies"]["liquid_waterproofing"].update(
                canonical_ref_parent="primers_chemicals_sealants"
            ),
            "LIQUID_WATERPROOFING_POLICY_INVALID",
        ),
        (
            lambda p: p["canonical_conflict_policies"]["lm"].update(
                automatic_normalization_allowed=True
            ),
            "LM_POLICY_INVALID",
        ),
    ],
)
def test_validator_fails_closed_for_contract_mutations(
    tmp_path: Path,
    mutation,
    expected_issue: str,
) -> None:
    payload = build_expected_ref1_read_approval()
    mutation(payload)
    candidate = tmp_path / "approval_manifest.json"
    _write(candidate, payload)

    result = validate_ref1_read_approval(candidate)

    assert result.is_valid is False
    assert expected_issue in {issue.code for issue in result.issues}


def test_current_runtime_package_files_match_committed_manifest() -> None:
    manifest = _read(RUNTIME_PACKAGE_DIR / "manifest.json")

    assert _sha256(RUNTIME_PACKAGE_DIR / "manifest.json") == EXPECTED_MANIFEST_SHA256
    assert set(path.name for path in RUNTIME_PACKAGE_DIR.iterdir()) == {
        "manifest.json",
        *manifest["artifacts"].keys(),
    }
    for name, contract in manifest["artifacts"].items():
        artifact = RUNTIME_PACKAGE_DIR / name
        assert _sha256(artifact) == contract["sha256"]
        assert artifact.stat().st_size == contract["size_bytes"]


def test_runtime_modes_startup_and_public_registry_remain_legacy() -> None:
    assert settings.MODULE1_REF_RUNTIME_MODE == "legacy"
    assert "ref1_read" in SUPPORTED_MODES

    snapshot = build_legacy_taxonomy_snapshot(get_material_knowledge_seed_registry())
    assert len(snapshot["groups"]) == 19
    assert len(snapshot["material_types"]) == 192


def test_runtime_activation_does_not_import_build_tooling_or_database() -> None:
    project_root = Path(__file__).resolve().parents[1]
    tool_source = (
        project_root / "tools" / "module1_ref_projection" / "ref1_read_approval.py"
    ).read_text(encoding="utf-8")

    assert "sqlalchemy" not in tool_source
    assert "app.database" not in tool_source
    assert "app.models" not in tool_source
    assert "db." not in tool_source

    app_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (project_root / "app").rglob("*.py")
    )
    assert "module1_ref_projection.ref1_read_approval" not in app_sources
    assert "admin_taxonomy_read" in app_sources
    assert "/ref1-taxonomy" in app_sources
    policy_source = (
        project_root / "app" / "services" / "module1_ref1_read_policy.py"
    ).read_text(encoding="utf-8")
    assert "sqlalchemy" not in policy_source
    assert "app.database" not in policy_source
    assert "app.models" not in policy_source


def test_decision_036_is_present_with_governed_ref1_read_implementation() -> None:
    project_root = Path(__file__).resolve().parents[1]
    decisions = (project_root / "docs" / "Decisions.md").read_text(encoding="utf-8")
    main_source = (project_root / "app" / "main.py").read_text(encoding="utf-8")
    config_source = (project_root / "app" / "config.py").read_text(encoding="utf-8")

    assert decisions.count("## Решение №036") == 1
    assert "Статус:\nПринято." in decisions.split("## Решение №036", 1)[1]
    assert "ref1_read_approval" not in main_source
    assert "ref1_read" in config_source
    assert "module1_ref_runtime" in main_source
