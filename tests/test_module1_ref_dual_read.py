from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

import app.services.module1_ref_dual_read as dual_read_module
import app.services.module1_ref_runtime_artifacts as loader_module
from app.config import settings
from app.services.module1_material_seed_registry import get_material_knowledge_seed_registry
from app.services.module1_ref_dual_read import (
    DUAL_READ_RESULT_SCHEMA_VERSION,
    Module1RefDualReadResult,
    build_legacy_taxonomy_snapshot,
    fingerprint_legacy_registry_snapshot,
)
from app.services.module1_ref_runtime_artifacts import (
    DEFAULT_ARTIFACT_DIR,
    SUPPORTED_MODES,
    Module1RefRuntimeConfigurationError,
    snapshot_legacy_material_registry,
    validate_module1_ref_runtime,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _copy_package(tmp_path: Path) -> Path:
    root = tmp_path / "runtime_reference"
    package = root / DEFAULT_ARTIFACT_DIR.name
    shutil.copytree(DEFAULT_ARTIFACT_DIR, package)
    return package


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rehash(package: Path, filename: str) -> None:
    manifest_path = package / "manifest.json"
    manifest = _read(manifest_path)
    content = (package / filename).read_bytes()
    manifest["artifacts"][filename]["sha256"] = hashlib.sha256(content).hexdigest()
    manifest["artifacts"][filename]["size_bytes"] = len(content)
    _write(manifest_path, manifest)


def _compare_copy(package: Path) -> Module1RefDualReadResult:
    result = validate_module1_ref_runtime(
        "dual_read",
        artifact_dir=package,
        allowed_root=package.parent,
    )
    assert isinstance(result, Module1RefDualReadResult)
    return result


def test_modes_are_explicit_and_default_remains_legacy() -> None:
    assert SUPPORTED_MODES == {"legacy", "artifact_validation", "dual_read", "ref1_read", "ref2_read"}
    assert settings.MODULE1_REF_RUNTIME_MODE == "legacy"
    assert validate_module1_ref_runtime("legacy").package_validated is False
    assert validate_module1_ref_runtime("artifact_validation").status == "PASS"
    assert validate_module1_ref_runtime("ref1_read").status == "PASS"
    with pytest.raises(Module1RefRuntimeConfigurationError, match="Unsupported"):
        validate_module1_ref_runtime("ref1_write")


def test_dual_read_returns_versioned_immutable_diagnostic_result() -> None:
    result = validate_module1_ref_runtime("dual_read")

    assert isinstance(result, Module1RefDualReadResult)
    assert result.result_schema_version == DUAL_READ_RESULT_SCHEMA_VERSION == "1.0"
    assert result.artifact_package_version == DEFAULT_ARTIFACT_DIR.name
    assert result.mode == "dual_read"
    assert result.status == "PASS_WITH_WARNINGS"
    assert result.is_valid is result.success is True
    assert isinstance(result.counts, MappingProxyType)
    assert isinstance(result.categories, MappingProxyType)
    with pytest.raises(FrozenInstanceError):
        result.mode = "legacy"  # type: ignore[misc]


def test_legacy_snapshot_and_fingerprint_are_deterministic_and_stable() -> None:
    registry = get_material_knowledge_seed_registry()
    registry_before = snapshot_legacy_material_registry(registry)
    first = build_legacy_taxonomy_snapshot(registry)
    second = build_legacy_taxonomy_snapshot(registry)

    assert first == second
    assert fingerprint_legacy_registry_snapshot(first) == fingerprint_legacy_registry_snapshot(second)
    result = validate_module1_ref_runtime("dual_read", registry=registry)
    assert result.legacy_registry_fingerprint == fingerprint_legacy_registry_snapshot(first)
    assert result.mutation_summary["fingerprint_before"] == result.mutation_summary["fingerprint_after"]
    assert result.mutation_summary["snapshot_equal"] is True
    assert snapshot_legacy_material_registry(registry) == registry_before


def test_ref1_comparison_counts_match_the_computed_baseline() -> None:
    result = validate_module1_ref_runtime("dual_read")

    assert dict(result.counts) == {
        "blocked_write_codes": 978,
        "compatibility_only_matches": 1,
        "duplicate_parent_conflicts": 1,
        "exact_groups": 19,
        "exact_material_types": 192,
        "legacy_groups": 19,
        "legacy_material_types": 192,
        "legacy_only_groups": 0,
        "legacy_only_material_types": 0,
        "parent_path_mismatches": 1,
        "ref_groups": 37,
        "ref_material_types": 978,
        "ref_only_groups": 18,
        "ref_only_material_types": 786,
        "title_mismatches": 0,
    }
    assert len(result.categories["exact_groups"]) == 19
    assert len(result.categories["exact_material_types"]) == 192
    assert all(item.classification == "exact_semantic_match" for item in result.categories["exact_groups"])


def test_parent_and_compatibility_classifications_are_structured() -> None:
    result = validate_module1_ref_runtime("dual_read")

    mismatch = result.categories["parent_path_mismatches"]
    compatibility_only = result.categories["compatibility_only_matches"]
    assert [item.code for item in mismatch] == ["liquid_waterproofing"]
    assert mismatch[0].classification == "exact_code_parent_difference"
    assert [item.code for item in compatibility_only] == ["liquid_waterproofing"]
    assert compatibility_only[0].classification == "compatibility_only"
    assert [item.code for item in result.conflicts] == ["liquid_waterproofing"]
    assert {item.code for item in result.categories["diagnostics"]} == {"liquid_waterproofing", "lm"}


def test_liquid_waterproofing_has_one_canonical_code_and_no_write_access() -> None:
    result = validate_module1_ref_runtime("dual_read")
    decision = result.compatibility_decisions["liquid_waterproofing"]

    assert decision["valid"] is True
    assert decision["canonical_code_count"] == 1
    assert decision["canonical_ref_parent"] == "waterproofing"
    assert set(decision["legacy_parent_paths"]) == {
        "primers_chemicals_sealants",
        "waterproofing",
    }
    assert decision["runtime_mutation"] is False
    assert decision["write_eligible"] is False


def test_lm_remains_lumen_and_linear_meter_requires_context() -> None:
    result = validate_module1_ref_runtime("dual_read")
    decision = result.compatibility_decisions["lm_alias"]

    assert decision["valid"] is True
    assert decision["canonical_lm_meaning"] == "lumen"
    assert decision["linear_meter_canonical_code"] == "linear_meter"
    assert decision["context_required"] is True
    assert decision["automatic_mapping_allowed"] is False


def test_ref_only_codes_are_not_exposed_by_public_legacy_lookup() -> None:
    registry = get_material_knowledge_seed_registry()
    result = validate_module1_ref_runtime("dual_read", registry=registry)
    ref_only_group = result.categories["ref_only_groups"][0].code
    ref_only_type = result.categories["ref_only_material_types"][0].code

    assert registry.get_taxonomy_group(ref_only_group) is None
    assert registry.has_material_group(ref_only_group) is False
    assert registry.has_material_group(ref_only_type) is False
    assert result.business_reads_enabled is False
    assert result.ref_only_writes_enabled is False
    assert result.write_summary["public_lookup_source"] == "legacy"


def test_dual_read_has_no_business_consumer_or_public_registry_dependency() -> None:
    adapter_source = (PROJECT_ROOT / "app/services/module1_ref_dual_read.py").read_text(encoding="utf-8")
    loader_source = (PROJECT_ROOT / "app/services/module1_ref_runtime_artifacts.py").read_text(encoding="utf-8")
    business_paths = (
        "app/services/module1_material_normalizer.py",
        "app/services/module1_matching_dedup.py",
        "app/services/module1_moderation_core.py",
        "app/services/module1_canonical_material_store.py",
        "app/services/module1_export_packages.py",
    )

    assert "reference_data" not in adapter_source
    assert "tools.module1_ref_projection" not in adapter_source
    assert "from app.models" not in adapter_source
    assert "from app.database" not in adapter_source
    assert "public_registry" not in adapter_source
    assert "tools.module1_ref_projection" not in loader_source
    for relative_path in business_paths:
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "module1_ref_dual_read" not in source
        assert "module1_ref_runtime_artifacts" not in source


def test_dual_read_is_fail_closed_for_package_validation_errors(tmp_path: Path) -> None:
    missing = _copy_package(tmp_path / "missing")
    (missing / "manifest.json").unlink()
    missing_result = _compare_copy(missing)
    assert {item.code for item in missing_result.blockers} == {"MANIFEST_MISSING"}
    assert missing_result.categories == {}

    changed = _copy_package(tmp_path / "hash")
    (changed / "taxonomy.json").write_bytes((changed / "taxonomy.json").read_bytes() + b" ")
    changed_result = _compare_copy(changed)
    assert "ARTIFACT_HASH_MISMATCH" in {item.code for item in changed_result.blockers}

    count = _copy_package(tmp_path / "count")
    taxonomy = _read(count / "taxonomy.json")
    taxonomy["groups"].pop()
    _write(count / "taxonomy.json", taxonomy)
    _rehash(count, "taxonomy.json")
    count_result = _compare_copy(count)
    assert "PACKAGE_COUNT_MISMATCH" in {item.code for item in count_result.blockers}


def test_dual_read_detects_compatibility_mismatch_after_valid_package(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    compatibility = _read(package / "compatibility.json")
    compatibility["taxonomy"]["legacy_groups"][0] = "unknown_legacy_group"
    _write(package / "compatibility.json", compatibility)
    _rehash(package, "compatibility.json")

    result = _compare_copy(package)

    assert "COMPATIBILITY_MAP_MISMATCH" in {item.code for item in result.blockers}
    assert result.business_reads_enabled is False
    assert result.database_writes == 0


def test_duplicate_canonical_and_unexpected_legacy_codes_are_blockers() -> None:
    registry = get_material_knowledge_seed_registry()
    legacy = build_legacy_taxonomy_snapshot(registry)
    taxonomy = _read(DEFAULT_ARTIFACT_DIR / "taxonomy.json")
    compatibility = _read(DEFAULT_ARTIFACT_DIR / "compatibility.json")
    taxonomy["material_types"].append(dict(taxonomy["material_types"][0]))

    _, _, _, duplicate_blockers = dual_read_module._compare_taxonomy(legacy, taxonomy, compatibility)
    assert "DUPLICATE_CANONICAL_CODE" in {item.code for item in duplicate_blockers}

    mutable_legacy = dual_read_module._thaw(legacy)
    mutable_legacy["material_types"].append({"code": "legacy_only_test", "parent_paths": ["roofing"]})
    _, _, _, legacy_blockers = dual_read_module._compare_taxonomy(mutable_legacy, _read(DEFAULT_ARTIFACT_DIR / "taxonomy.json"), compatibility)
    assert "UNEXPECTED_LEGACY_ONLY_CODE" in {item.code for item in legacy_blockers}


def test_registry_mutation_and_unknown_result_schema_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original_snapshot = loader_module.snapshot_legacy_material_registry
    calls = 0

    def changing_snapshot(registry):
        nonlocal calls
        calls += 1
        return original_snapshot(registry) + (calls,)

    monkeypatch.setattr(loader_module, "snapshot_legacy_material_registry", changing_snapshot)
    mutation_result = validate_module1_ref_runtime("dual_read")
    assert "REGISTRY_MUTATION_DETECTED" in {item.code for item in mutation_result.blockers}
    assert mutation_result.business_reads_enabled is False

    monkeypatch.setattr(loader_module, "snapshot_legacy_material_registry", original_snapshot)
    monkeypatch.setattr(dual_read_module, "DUAL_READ_RESULT_SCHEMA_VERSION", "999")
    schema_result = validate_module1_ref_runtime("dual_read")
    assert "RESULT_SCHEMA_UNSUPPORTED" in {item.code for item in schema_result.blockers}


def test_database_write_and_performance_contract_is_explicit() -> None:
    result = validate_module1_ref_runtime("dual_read")

    assert result.database_writes == 0
    assert result.mutation_summary["database_writes"] == 0
    assert result.registry_mutated is False
    assert result.validation_duration_ms > 0
    assert result.comparison_duration_ms > 0
    assert result.total_duration_ms >= result.comparison_duration_ms
    assert result.legacy_snapshot_size_bytes > 0
    assert result.comparison_entry_count > 0
