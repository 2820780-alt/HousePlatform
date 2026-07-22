from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.services.module1_material_seed_registry import get_material_knowledge_seed_registry
from app.services.module1_ref_runtime_artifacts import (
    DEFAULT_ARTIFACT_DIR,
    Module1RefArtifactValidationError,
    Module1RefRuntimeConfigurationError,
    require_module1_ref_runtime_validation,
    snapshot_legacy_material_registry,
    validate_configured_module1_ref_runtime,
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rehash(package: Path, filename: str) -> None:
    manifest_path = package / "manifest.json"
    manifest = _read(manifest_path)
    content = (package / filename).read_bytes()
    manifest["artifacts"][filename]["sha256"] = hashlib.sha256(content).hexdigest()
    manifest["artifacts"][filename]["size_bytes"] = len(content)
    _write(manifest_path, manifest)


def _validate_copy(package: Path):
    return validate_module1_ref_runtime(
        "artifact_validation",
        artifact_dir=package,
        allowed_root=package.parent,
    )


def test_default_config_and_legacy_mode_do_not_read_artifacts(tmp_path: Path) -> None:
    explicit = validate_module1_ref_runtime("legacy", artifact_dir=tmp_path / "missing")
    configured = validate_configured_module1_ref_runtime()

    assert explicit.status == configured.status == "LEGACY"
    assert explicit.is_valid is configured.is_valid is True
    assert explicit.package_validated is configured.package_validated is False
    assert explicit.loaded_object_count == configured.loaded_object_count == 0
    assert explicit.registry_mutated is configured.registry_mutated is False
    assert explicit.database_writes == configured.database_writes == 0


def test_artifact_validation_is_structured_and_does_not_mutate_registry_or_database() -> None:
    registry = get_material_knowledge_seed_registry()
    before = snapshot_legacy_material_registry(registry)

    result = validate_module1_ref_runtime("artifact_validation", registry=registry)

    assert result.status == "PASS"
    assert result.is_valid is True
    assert result.package_validated is True
    assert result.artifact_set_id == DEFAULT_ARTIFACT_DIR.name
    assert result.loaded_object_count == 3292
    assert result.registry_mutated is False
    assert result.database_writes == 0
    assert result.business_reads_enabled is False
    assert result.ref_only_writes_enabled is False
    assert snapshot_legacy_material_registry(registry) == before


def test_unknown_mode_is_an_explicit_configuration_error() -> None:
    with pytest.raises(Module1RefRuntimeConfigurationError, match="Unsupported"):
        validate_module1_ref_runtime("ref1_write")


def test_missing_manifest_fails_closed(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    (package / "manifest.json").unlink()

    result = _validate_copy(package)

    assert result.status == "BLOCKED"
    assert {item.code for item in result.issues} == {"MANIFEST_MISSING"}
    assert result.business_reads_enabled is False
    assert result.database_writes == 0


def test_artifact_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    payload = _read(package / "fields.json")
    payload["fields"][0]["label_ru"] += " changed"
    _write(package / "fields.json", payload)

    result = _validate_copy(package)

    assert "ARTIFACT_HASH_MISMATCH" in {item.code for item in result.issues}
    assert result.is_valid is False


def test_source_hash_bundle_mismatch_fails_closed(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    manifest = _read(package / "manifest.json")
    manifest["source_packages"][0]["sha256"] = "0" * 64
    _write(package / "manifest.json", manifest)

    result = _validate_copy(package)

    assert "SOURCE_HASH_MISMATCH" in {item.code for item in result.issues}


def test_manifest_and_artifact_schema_versions_fail_closed(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    manifest = _read(package / "manifest.json")
    manifest["artifact_schema_version"] = "999"
    _write(package / "manifest.json", manifest)

    assert "SCHEMA_VERSION_UNSUPPORTED" in {item.code for item in _validate_copy(package).issues}

    package = _copy_package(tmp_path / "artifact")
    fields = _read(package / "fields.json")
    fields["artifact_schema_version"] = "999"
    _write(package / "fields.json", fields)
    _rehash(package, "fields.json")

    assert "ARTIFACT_SCHEMA_MISMATCH" in {item.code for item in _validate_copy(package).issues}


def test_missing_or_extra_artifact_fails_closed(tmp_path: Path) -> None:
    missing = _copy_package(tmp_path / "missing")
    (missing / "units.json").unlink()
    assert "ARTIFACT_FILE_SET_INVALID" in {item.code for item in _validate_copy(missing).issues}

    extra = _copy_package(tmp_path / "extra")
    (extra / "unknown.json").write_text("{}\n", encoding="utf-8")
    assert "ARTIFACT_FILE_SET_INVALID" in {item.code for item in _validate_copy(extra).issues}


def test_record_count_mismatch_fails_closed(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    fields = _read(package / "fields.json")
    fields["fields"].pop()
    _write(package / "fields.json", fields)
    _rehash(package, "fields.json")

    result = _validate_copy(package)

    assert "PACKAGE_COUNT_MISMATCH" in {item.code for item in result.issues}


def test_review_entry_leak_fails_closed(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    compatibility = _read(package / "compatibility.json")
    leaked_code = compatibility["review_exclusions"]["ref2_assignment_material_types"][0]
    assignments = _read(package / "characteristic_assignments.json")
    assignments["assignments"].append(
        {
            "all_field_codes": [],
            "conditional": [],
            "group_code": "review",
            "inheritance_resolved": True,
            "material_type_id": leaked_code,
            "module2_required": [],
            "recommended": [],
            "required": [],
            "required_semantics_active": False,
            "source_profile_id": "review",
            "write_eligible": False,
        }
    )
    _write(package / "characteristic_assignments.json", assignments)
    _rehash(package, "characteristic_assignments.json")

    result = _validate_copy(package)

    assert "REF2_REVIEW_ENTRY_ACTIVE" in {item.code for item in result.issues}


def test_liquid_waterproofing_compatibility_conflict_fails_closed(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    taxonomy = _read(package / "taxonomy.json")
    record = next(item for item in taxonomy["material_types"] if item["code"] == "liquid_waterproofing")
    record["canonical_parent"] = "primers_chemicals_sealants"
    _write(package / "taxonomy.json", taxonomy)
    _rehash(package, "taxonomy.json")

    result = _validate_copy(package)

    assert "LIQUID_WATERPROOFING_CANONICAL_CONFLICT" in {item.code for item in result.issues}


def test_ambiguous_lm_auto_normalization_fails_closed(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    compatibility = _read(package / "compatibility.json")
    rule = next(item for item in compatibility["units"]["special_alias_rules"] if item["alias"] == "lm")
    rule["automatic_mapping_allowed"] = True
    _write(package / "compatibility.json", compatibility)
    _rehash(package, "compatibility.json")

    result = _validate_copy(package)

    assert "LM_AUTO_NORMALIZATION_ENABLED" in {item.code for item in result.issues}


def test_require_validation_raises_without_partial_fallback(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    (package / "manifest.json").unlink()

    with pytest.raises(Module1RefArtifactValidationError, match="MANIFEST_MISSING"):
        require_module1_ref_runtime_validation(
            "artifact_validation",
            artifact_dir=package,
            allowed_root=package.parent,
        )


def test_production_loader_does_not_import_tooling_sources_or_database() -> None:
    loader_source = (PROJECT_ROOT / "app" / "services" / "module1_ref_runtime_artifacts.py").read_text(encoding="utf-8")
    main_source = (PROJECT_ROOT / "app" / "main.py").read_text(encoding="utf-8")

    assert "tools.module1_ref_projection" not in loader_source
    assert "reference_data" not in loader_source
    assert "from app.models" not in loader_source
    assert "from app.database" not in loader_source
    assert main_source.index("validate_configured_module1_ref_runtime()") < main_source.index("await init_db()")
