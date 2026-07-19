from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from app.services.module1_material_seed_registry import (
    MaterialKnowledgeSeedRegistry,
    get_material_knowledge_seed_registry,
)

if TYPE_CHECKING:
    from app.services.module1_ref_dual_read import Module1RefDualReadResult
    from app.services.module1_ref1_read_policy import Module1Ref1ReadActivation
    from app.services.module1_ref2_read_policy import Module1Ref2ReadActivation
    from app.services.module1_ref3_read_policy import Module1Ref3ReadActivation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
APPROVAL_ROOT = RUNTIME_REFERENCE_ROOT / "approvals"
DEFAULT_ARTIFACT_SET_ID = "ref-runtime-v1-122079b1c558fefc"
DEFAULT_ARTIFACT_DIR = RUNTIME_REFERENCE_ROOT / DEFAULT_ARTIFACT_SET_ID
DEFAULT_APPROVAL_ID = "ref1-read-v1-1a15fed6ebdd"
DEFAULT_APPROVAL_DIR = APPROVAL_ROOT / DEFAULT_APPROVAL_ID
DEFAULT_REF2_APPROVAL_ID = "ref2-read-v1-1a15fed6ebdd"
DEFAULT_REF2_APPROVAL_DIR = APPROVAL_ROOT / DEFAULT_REF2_APPROVAL_ID
DEFAULT_REF3_APPROVAL_ID = "ref3-read-v1-1a15fed6ebdd"
DEFAULT_REF3_APPROVAL_DIR = APPROVAL_ROOT / DEFAULT_REF3_APPROVAL_ID
ARTIFACT_SCHEMA_VERSION = "1.0"
COMPATIBILITY_MAP_VERSION = "1.0"
ARTIFACT_SUPPORTED_MODES = frozenset({"legacy", "artifact_validation"})
SUPPORTED_MODES = frozenset({"legacy", "artifact_validation", "dual_read", "ref1_read", "ref2_read", "ref3_read"})
REQUIRED_ARTIFACT_FILES = frozenset(
    {
        "taxonomy.json",
        "fields.json",
        "characteristic_assignments.json",
        "units.json",
        "conversions.json",
        "packaging.json",
        "rules_metadata.json",
        "compatibility.json",
    }
)
EXPECTED_FILES = REQUIRED_ARTIFACT_FILES | {"manifest.json"}


class Module1RefRuntimeConfigurationError(ValueError):
    pass


class Module1RefArtifactValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Module1RefValidationIssue:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class Module1RefValidationResult:
    mode: str
    status: str
    is_valid: bool
    package_validated: bool
    artifact_set_id: str | None
    manifest_sha256: str | None
    counts: Mapping[str, Any]
    issues: tuple[Module1RefValidationIssue, ...]
    registry_mutated: bool
    database_writes: int
    business_reads_enabled: bool
    ref_only_writes_enabled: bool
    loaded_object_count: int
    validation_duration_ms: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_set_id": self.artifact_set_id,
            "business_reads_enabled": self.business_reads_enabled,
            "counts": dict(self.counts),
            "database_writes": self.database_writes,
            "is_valid": self.is_valid,
            "issues": [issue.as_dict() for issue in self.issues],
            "loaded_object_count": self.loaded_object_count,
            "manifest_sha256": self.manifest_sha256,
            "mode": self.mode,
            "package_validated": self.package_validated,
            "ref_only_writes_enabled": self.ref_only_writes_enabled,
            "registry_mutated": self.registry_mutated,
            "status": self.status,
            "validation_duration_ms": self.validation_duration_ms,
        }


def validate_module1_ref_runtime(
    mode: str = "legacy",
    *,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    allowed_root: str | Path = RUNTIME_REFERENCE_ROOT,
    approval_dir: str | Path = DEFAULT_APPROVAL_DIR,
    ref2_approval_dir: str | Path = DEFAULT_REF2_APPROVAL_DIR,
    ref3_approval_dir: str | Path = DEFAULT_REF3_APPROVAL_DIR,
    approval_allowed_root: str | Path = APPROVAL_ROOT,
    registry: MaterialKnowledgeSeedRegistry | None = None,
) -> Module1RefValidationResult | Module1RefDualReadResult | Module1Ref1ReadActivation | Module1Ref2ReadActivation | Module1Ref3ReadActivation:
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in SUPPORTED_MODES:
        raise Module1RefRuntimeConfigurationError(
            f"Unsupported Module 1 REF runtime mode: {mode!r}"
        )
    if normalized_mode == "dual_read":
        from app.services.module1_ref_dual_read import compare_module1_ref_runtime

        return compare_module1_ref_runtime(
            artifact_dir=artifact_dir,
            allowed_root=allowed_root,
            registry=registry,
        )
    if normalized_mode == "ref1_read":
        from app.services.module1_ref1_read_policy import activate_module1_ref1_read

        effective_registry = registry or get_material_knowledge_seed_registry()
        package_validation = validate_module1_ref_runtime(
            "artifact_validation",
            artifact_dir=artifact_dir,
            allowed_root=allowed_root,
            registry=effective_registry,
        )
        return activate_module1_ref1_read(
            artifact_dir=Path(artifact_dir),
            approval_dir=Path(approval_dir),
            approval_allowed_root=Path(approval_allowed_root),
            package_validation=package_validation,
            registry=effective_registry,
        )
    if normalized_mode == "ref2_read":
        from app.services.module1_ref2_read_policy import activate_module1_ref2_read

        effective_registry = registry or get_material_knowledge_seed_registry()
        package_validation = validate_module1_ref_runtime(
            "artifact_validation",
            artifact_dir=artifact_dir,
            allowed_root=allowed_root,
            registry=effective_registry,
        )
        return activate_module1_ref2_read(
            artifact_dir=Path(artifact_dir),
            ref1_approval_dir=Path(approval_dir),
            ref2_approval_dir=Path(ref2_approval_dir),
            approval_allowed_root=Path(approval_allowed_root),
            package_validation=package_validation,
            registry=effective_registry,
        )
    if normalized_mode == "ref3_read":
        from app.services.module1_ref3_read_policy import activate_module1_ref3_read

        effective_registry = registry or get_material_knowledge_seed_registry()
        package_validation = validate_module1_ref_runtime(
            "artifact_validation",
            artifact_dir=artifact_dir,
            allowed_root=allowed_root,
            registry=effective_registry,
        )
        return activate_module1_ref3_read(
            artifact_dir=Path(artifact_dir),
            ref1_approval_dir=Path(approval_dir),
            ref2_approval_dir=Path(ref2_approval_dir),
            ref3_approval_dir=Path(ref3_approval_dir),
            approval_allowed_root=Path(approval_allowed_root),
            package_validation=package_validation,
            registry=effective_registry,
        )
    if normalized_mode == "legacy":
        return Module1RefValidationResult(
            mode="legacy",
            status="LEGACY",
            is_valid=True,
            package_validated=False,
            artifact_set_id=None,
            manifest_sha256=None,
            counts={},
            issues=tuple(),
            registry_mutated=False,
            database_writes=0,
            business_reads_enabled=False,
            ref_only_writes_enabled=False,
            loaded_object_count=0,
            validation_duration_ms=0.0,
        )

    started = time.perf_counter()
    effective_registry = registry or get_material_knowledge_seed_registry()
    registry_before = snapshot_legacy_material_registry(effective_registry)
    issues: list[Module1RefValidationIssue] = []
    manifest: dict[str, Any] = {}
    payloads: dict[str, dict[str, Any]] = {}
    manifest_hash: str | None = None
    artifact_set_id: str | None = None

    try:
        target = _confined_artifact_dir(Path(artifact_dir), Path(allowed_root))
    except Module1RefArtifactValidationError as exc:
        issues.append(Module1RefValidationIssue("ARTIFACT_PATH_INVALID", str(exc)))
        target = Path(artifact_dir)

    if not issues:
        manifest_path = target / "manifest.json"
        if not manifest_path.is_file():
            issues.append(Module1RefValidationIssue("MANIFEST_MISSING", "Artifact manifest is missing"))
        else:
            manifest_hash = _sha256_file(manifest_path)
            manifest = _read_json(manifest_path, "MANIFEST_INVALID_JSON", issues)
            artifact_set_id = _string_or_none(manifest.get("artifact_set_id"))

    if manifest and not issues:
        _validate_manifest(target, manifest, issues)
        if not issues:
            payloads = _load_artifacts(target, manifest, issues)
        if not issues:
            _validate_artifact_contracts(manifest, payloads, issues)

    registry_after = snapshot_legacy_material_registry(effective_registry)
    registry_mutated = registry_before != registry_after
    if registry_mutated:
        issues.append(
            Module1RefValidationIssue(
                "REGISTRY_MUTATION_DETECTED",
                "Artifact validation changed the legacy MaterialKnowledgeSeedRegistry",
            )
        )

    duration_ms = (time.perf_counter() - started) * 1000
    loaded_object_count = _loaded_object_count(payloads)
    is_valid = not issues
    return Module1RefValidationResult(
        mode="artifact_validation",
        status="PASS" if is_valid else "BLOCKED",
        is_valid=is_valid,
        package_validated=is_valid,
        artifact_set_id=artifact_set_id,
        manifest_sha256=manifest_hash,
        counts=manifest.get("counts", {}) if manifest else {},
        issues=tuple(issues),
        registry_mutated=registry_mutated,
        database_writes=0,
        business_reads_enabled=False,
        ref_only_writes_enabled=False,
        loaded_object_count=loaded_object_count,
        validation_duration_ms=duration_ms,
    )


def require_module1_ref_runtime_validation(
    mode: str = "legacy",
    *,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    allowed_root: str | Path = RUNTIME_REFERENCE_ROOT,
    approval_dir: str | Path = DEFAULT_APPROVAL_DIR,
    ref2_approval_dir: str | Path = DEFAULT_REF2_APPROVAL_DIR,
    ref3_approval_dir: str | Path = DEFAULT_REF3_APPROVAL_DIR,
    approval_allowed_root: str | Path = APPROVAL_ROOT,
    registry: MaterialKnowledgeSeedRegistry | None = None,
) -> Module1RefValidationResult | Module1RefDualReadResult | Module1Ref1ReadActivation | Module1Ref2ReadActivation | Module1Ref3ReadActivation:
    result = validate_module1_ref_runtime(
        mode,
        artifact_dir=artifact_dir,
        allowed_root=allowed_root,
        approval_dir=approval_dir,
        ref2_approval_dir=ref2_approval_dir,
        ref3_approval_dir=ref3_approval_dir,
        approval_allowed_root=approval_allowed_root,
        registry=registry,
    )
    if not result.is_valid:
        codes = ", ".join(issue.code for issue in result.issues)
        raise Module1RefArtifactValidationError(
            f"Module 1 REF artifact validation failed: {codes}"
        )
    return result


def validate_configured_module1_ref_runtime() -> Module1RefValidationResult | Module1RefDualReadResult | Module1Ref1ReadActivation | Module1Ref2ReadActivation | Module1Ref3ReadActivation:
    from app.config import settings

    artifact_dir = RUNTIME_REFERENCE_ROOT / settings.MODULE1_REF_ARTIFACT_SET_ID
    return require_module1_ref_runtime_validation(
        settings.MODULE1_REF_RUNTIME_MODE,
        artifact_dir=artifact_dir,
        approval_dir=APPROVAL_ROOT / settings.MODULE1_REF_APPROVAL_ID,
        ref2_approval_dir=APPROVAL_ROOT / settings.MODULE1_REF2_APPROVAL_ID,
        ref3_approval_dir=APPROVAL_ROOT / settings.MODULE1_REF3_APPROVAL_ID,
    )


def snapshot_legacy_material_registry(
    registry: MaterialKnowledgeSeedRegistry,
) -> tuple[Any, ...]:
    return (
        registry.version,
        registry.module,
        registry.purpose,
        tuple(sorted(dict(registry.boundaries).items())),
        tuple((item.code, item.name, item.children) for item in registry.taxonomy),
        tuple(
            (code, item.required, item.module2_required, item.recommended)
            for code, item in sorted(registry.characteristic_schemas.items())
        ),
        tuple((code, item.roles) for code, item in sorted(registry.role_mappings.items())),
        registry.compatibility_rules,
        registry.alternative_rules,
        registry.unit_conversions,
    )


def _confined_artifact_dir(path: Path, allowed_root: Path) -> Path:
    resolved = path.resolve()
    root = allowed_root.resolve()
    if resolved == root or root not in resolved.parents:
        raise Module1RefArtifactValidationError("Artifact directory is outside the configured runtime root")
    return resolved


def _validate_manifest(
    target: Path,
    manifest: Mapping[str, Any],
    issues: list[Module1RefValidationIssue],
) -> None:
    if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        issues.append(Module1RefValidationIssue("SCHEMA_VERSION_UNSUPPORTED", "Unsupported artifact schema version"))
    if manifest.get("compatibility_map_version") != COMPATIBILITY_MAP_VERSION:
        issues.append(Module1RefValidationIssue("COMPATIBILITY_VERSION_UNSUPPORTED", "Unsupported compatibility map version"))
    if manifest.get("artifact_set_id") != target.name:
        issues.append(Module1RefValidationIssue("ARTIFACT_SET_ID_MISMATCH", "Manifest artifact_set_id differs from directory name"))
    if manifest.get("runtime_activation_allowed") is not False:
        issues.append(Module1RefValidationIssue("RUNTIME_ACTIVATION_FORBIDDEN", "Runtime activation flag must remain false"))
    if manifest.get("write_activation_allowed") is not False:
        issues.append(Module1RefValidationIssue("WRITE_ACTIVATION_FORBIDDEN", "Write activation flag must remain false"))
    if manifest.get("integration_allowed") is not False:
        issues.append(Module1RefValidationIssue("SOURCE_INTEGRATION_FORBIDDEN", "Source integration flag must remain false"))
    if manifest.get("default_loader_mode") != "legacy":
        issues.append(Module1RefValidationIssue("DEFAULT_MODE_INVALID", "Default loader mode must be legacy"))
    if set(manifest.get("supported_loader_modes") or []) != ARTIFACT_SUPPORTED_MODES:
        issues.append(Module1RefValidationIssue("LOADER_MODES_INVALID", "Artifact package supports only legacy and artifact_validation"))

    source_packages = manifest.get("source_packages")
    if not isinstance(source_packages, list):
        issues.append(Module1RefValidationIssue("SOURCE_PACKAGES_INVALID", "Manifest source_packages must be a list"))
    else:
        source_hashes = {
            str(item.get("package_id")): str(item.get("sha256"))
            for item in source_packages
            if isinstance(item, dict)
        }
        expected_bundle = _sha256_bytes(_json_bytes(dict(sorted(source_hashes.items()))))
        if manifest.get("source_bundle_sha256") != expected_bundle:
            issues.append(Module1RefValidationIssue("SOURCE_HASH_MISMATCH", "Source package hash bundle is inconsistent"))

    actual_files = {path.name for path in target.iterdir() if path.is_file()}
    if actual_files != EXPECTED_FILES:
        missing = sorted(EXPECTED_FILES - actual_files)
        extra = sorted(actual_files - EXPECTED_FILES)
        issues.append(Module1RefValidationIssue("ARTIFACT_FILE_SET_INVALID", f"Missing={missing}; extra={extra}"))

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != REQUIRED_ARTIFACT_FILES:
        issues.append(Module1RefValidationIssue("ARTIFACT_MANIFEST_INCOMPLETE", "Manifest artifact set is incomplete or unknown"))
        return
    for filename, metadata in artifacts.items():
        path = target / filename
        if not path.is_file():
            continue
        if not isinstance(metadata, dict) or metadata.get("sha256") != _sha256_file(path):
            issues.append(Module1RefValidationIssue("ARTIFACT_HASH_MISMATCH", f"Hash mismatch for {filename}"))
        if isinstance(metadata, dict) and metadata.get("size_bytes") != path.stat().st_size:
            issues.append(Module1RefValidationIssue("ARTIFACT_SIZE_MISMATCH", f"Size mismatch for {filename}"))


def _load_artifacts(
    target: Path,
    manifest: Mapping[str, Any],
    issues: list[Module1RefValidationIssue],
) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for filename in sorted(REQUIRED_ARTIFACT_FILES):
        payload = _read_json(target / filename, "ARTIFACT_INVALID_JSON", issues)
        if not payload:
            continue
        if payload.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
            issues.append(Module1RefValidationIssue("ARTIFACT_SCHEMA_MISMATCH", f"Schema mismatch in {filename}"))
        if payload.get("artifact_set_id") != manifest.get("artifact_set_id"):
            issues.append(Module1RefValidationIssue("ARTIFACT_SET_MISMATCH", f"Set mismatch in {filename}"))
        if payload.get("runtime_activation_allowed") is not False or payload.get("write_activation_allowed") is not False:
            issues.append(Module1RefValidationIssue("ARTIFACT_ACTIVATION_FLAG_INVALID", f"Activation flag invalid in {filename}"))
        payloads[filename] = payload
    return payloads


def _validate_artifact_contracts(
    manifest: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    issues: list[Module1RefValidationIssue],
) -> None:
    if set(payloads) != REQUIRED_ARTIFACT_FILES:
        issues.append(Module1RefValidationIssue("ARTIFACT_PACKAGE_INCOMPLETE", "Not all artifacts could be loaded"))
        return

    for filename, payload in payloads.items():
        expected_counts = manifest["artifacts"][filename].get("counts", {})
        if payload.get("counts", {}) != expected_counts:
            issues.append(Module1RefValidationIssue("ARTIFACT_COUNT_MISMATCH", f"Manifest counts differ for {filename}"))

    taxonomy = payloads["taxonomy.json"]
    fields = payloads["fields.json"]
    assignments = payloads["characteristic_assignments.json"]
    units = payloads["units.json"]
    conversions = payloads["conversions.json"]
    packaging = payloads["packaging.json"]
    rules = payloads["rules_metadata.json"]
    compatibility = payloads["compatibility.json"]

    actual_counts = {
        "characteristic_assignments": {
            **assignments["counts"],
            "assignments": len(assignments.get("assignments", [])),
        },
        "conversions": {
            **conversions["counts"],
            "conversions": len(conversions.get("conversions", [])),
        },
        "fields": {"fields": len(fields.get("fields", []))},
        "packaging": {
            **packaging["counts"],
            "assignments": len(packaging.get("assignments", [])),
            "profiles": len(packaging.get("profiles", [])),
        },
        "rules": {
            **rules["counts"],
            "geometry": len(rules.get("geometry_rules", [])),
            "rules": len(rules.get("geometry_rules", [])) + len(rules.get("extended_rules", [])),
        },
        "taxonomy": {
            "groups": len(taxonomy.get("groups", [])),
            "material_types": len(taxonomy.get("material_types", [])),
        },
        "units": {
            **units["counts"],
            "eligible_units": len(units.get("units", [])),
        },
    }
    if actual_counts != manifest.get("counts"):
        issues.append(Module1RefValidationIssue("PACKAGE_COUNT_MISMATCH", "Package record counts do not match manifest"))

    expected_exact = {
        "taxonomy": {"groups": 37, "material_types": 978},
        "fields": {"fields": 558},
    }
    for section, expected in expected_exact.items():
        if manifest.get("counts", {}).get(section) != expected:
            issues.append(Module1RefValidationIssue("PACKAGE_COMPATIBILITY_MISMATCH", f"Unexpected {section} contract"))

    exclusion_contract = manifest.get("exclusions") or {}
    review = compatibility.get("review_exclusions") or {}
    if len(review.get("ref2_assignment_material_types", [])) != exclusion_contract.get("ref2_review_assignments"):
        issues.append(Module1RefValidationIssue("REF2_REVIEW_EXCLUSION_MISMATCH", "REF-2 review exclusions are inconsistent"))
    if len(review.get("ref3_unit_codes", [])) != exclusion_contract.get("ref3_review_units"):
        issues.append(Module1RefValidationIssue("UNIT_REVIEW_EXCLUSION_MISMATCH", "REF-3 unit review exclusions are inconsistent"))
    if len(review.get("ref3_packaging_material_types", [])) != exclusion_contract.get("ref3_packaging_review_assignments"):
        issues.append(Module1RefValidationIssue("PACKAGING_REVIEW_EXCLUSION_MISMATCH", "REF-3 packaging review exclusions are inconsistent"))
    diagnostics = compatibility.get("diagnostics") or {}
    if diagnostics.get("packaging_ref2_mismatch_count") != exclusion_contract.get("packaging_ref2_mismatches"):
        issues.append(Module1RefValidationIssue("PACKAGING_DIAGNOSTIC_MISMATCH", "Packaging mismatch diagnostics are inconsistent"))

    review_assignments = set(review.get("ref2_assignment_material_types", []))
    eligible_assignments = {item.get("material_type_id") for item in assignments.get("assignments", [])}
    if review_assignments & eligible_assignments:
        issues.append(Module1RefValidationIssue("REF2_REVIEW_ENTRY_ACTIVE", "A REF-2 review assignment leaked into eligible artifacts"))
    review_units = set(review.get("ref3_unit_codes", []))
    eligible_units = {item.get("code") for item in units.get("units", [])}
    if review_units & eligible_units:
        issues.append(Module1RefValidationIssue("UNIT_REVIEW_ENTRY_ACTIVE", "A review unit leaked into eligible artifacts"))
    review_packaging = set(review.get("ref3_packaging_material_types", []))
    eligible_packaging = {item.get("material_type_id") for item in packaging.get("assignments", [])}
    if review_packaging & eligible_packaging:
        issues.append(Module1RefValidationIssue("PACKAGING_REVIEW_ENTRY_ACTIVE", "A packaging review entry leaked into eligible artifacts"))

    taxonomy_compatibility = compatibility.get("taxonomy") or {}
    if len(taxonomy_compatibility.get("legacy_groups", [])) != 19:
        issues.append(Module1RefValidationIssue("LEGACY_GROUP_COUNT_MISMATCH", "Expected 19 recognized legacy groups"))
    if len(taxonomy_compatibility.get("legacy_material_types", [])) != 192:
        issues.append(Module1RefValidationIssue("LEGACY_TYPE_COUNT_MISMATCH", "Expected 192 recognized legacy material types"))
    if len(taxonomy_compatibility.get("ref_only_groups", [])) != 18:
        issues.append(Module1RefValidationIssue("REF_ONLY_GROUP_COUNT_MISMATCH", "Expected 18 inactive REF-only groups"))
    if len(taxonomy_compatibility.get("ref_only_material_types", [])) != 786:
        issues.append(Module1RefValidationIssue("REF_ONLY_TYPE_COUNT_MISMATCH", "Expected 786 inactive REF-only material types"))
    _validate_liquid_waterproofing(taxonomy, taxonomy_compatibility, issues)
    _validate_lm_compatibility(compatibility, issues)

    field_compatibility = compatibility.get("fields") or {}
    if len(field_compatibility.get("runtime_fields", [])) != 74:
        issues.append(Module1RefValidationIssue("RUNTIME_FIELD_COUNT_MISMATCH", "Expected 74 runtime fields"))
    if field_compatibility.get("runtime_only_fields") != 28:
        issues.append(Module1RefValidationIssue("RUNTIME_ONLY_FIELD_COUNT_MISMATCH", "Expected 28 preserved runtime-only fields"))
    schema_comparison = field_compatibility.get("schema_comparison") or {}
    if schema_comparison.get("legacy_schema_count") != 13 or schema_comparison.get("required_equal") != 0:
        issues.append(Module1RefValidationIssue("LEGACY_SCHEMA_SEMANTICS_MISMATCH", "Legacy schema compatibility contract changed"))
    if assignments.get("authoring_inheritance_present") is not False:
        issues.append(Module1RefValidationIssue("AUTHORING_INHERITANCE_ACTIVE", "Authoring inheritance is forbidden in runtime artifacts"))
    if any(item.get("required_semantics_active") is not False for item in assignments.get("assignments", [])):
        issues.append(Module1RefValidationIssue("REF_REQUIRED_SEMANTICS_ACTIVE", "REF required semantics must remain inactive"))

    if conversions.get("counts") != {"conversions": 47, "formula": 7, "simple": 12, "technical": 28}:
        issues.append(Module1RefValidationIssue("CONVERSION_COUNT_MISMATCH", "Unexpected conversion compatibility counts"))
    if any(item.get("executable") is not False for item in conversions.get("conversions", [])):
        issues.append(Module1RefValidationIssue("CONVERSION_EXECUTION_ENABLED", "Conversion metadata became executable"))
    if packaging.get("characteristic_contract_separate") is not True:
        issues.append(Module1RefValidationIssue("PACKAGING_CHARACTERISTIC_MIX", "Packaging must remain separate from characteristics"))
    if rules.get("counts") != {"consumption": 5, "coverage": 2, "geometry": 7, "rules": 15, "yield": 1}:
        issues.append(Module1RefValidationIssue("RULE_COUNT_MISMATCH", "Unexpected REF-3 extended rule counts"))
    if rules.get("executable_rule_count") != 0 or rules.get("object_work_quantity_calculations") != 0:
        issues.append(Module1RefValidationIssue("RULE_EXECUTION_ENABLED", "Extended rules must remain inactive metadata"))

    behavior = compatibility.get("behavior_contracts") or {}
    required_false = (
        "artifact_business_reads",
        "database_writes",
        "public_parallel_registry_allowed",
        "ref_only_writes",
        "registry_mutation",
    )
    if any(behavior.get(key) is not False for key in required_false):
        issues.append(Module1RefValidationIssue("BEHAVIOR_CONTRACT_INVALID", "Validation-only behavior contract is not fail-closed"))
    if behavior.get("legacy_registry_authoritative") is not True:
        issues.append(Module1RefValidationIssue("LEGACY_AUTHORITY_LOST", "Legacy registry must remain authoritative"))


def _validate_liquid_waterproofing(
    taxonomy: Mapping[str, Any],
    compatibility: Mapping[str, Any],
    issues: list[Module1RefValidationIssue],
) -> None:
    records = [item for item in taxonomy.get("material_types", []) if item.get("code") == "liquid_waterproofing"]
    conflicts = [item for item in compatibility.get("special_conflicts", []) if item.get("code") == "liquid_waterproofing"]
    if len(records) != 1 or records[0].get("canonical_parent") != "waterproofing":
        issues.append(Module1RefValidationIssue("LIQUID_WATERPROOFING_CANONICAL_CONFLICT", "liquid_waterproofing must have one REF-1 canonical parent"))
    expected_paths = {"primers_chemicals_sealants", "waterproofing"}
    if len(conflicts) != 1 or set(conflicts[0].get("legacy_parent_paths", [])) != expected_paths:
        issues.append(Module1RefValidationIssue("LIQUID_WATERPROOFING_LEGACY_PATH_MISSING", "Both legacy parent paths must remain in compatibility metadata"))
    elif conflicts[0].get("write_eligible") is not False:
        issues.append(Module1RefValidationIssue("LIQUID_WATERPROOFING_WRITE_ENABLED", "Conflicted type must remain write-ineligible"))


def _validate_lm_compatibility(
    compatibility: Mapping[str, Any],
    issues: list[Module1RefValidationIssue],
) -> None:
    rules = compatibility.get("units", {}).get("special_alias_rules", [])
    lm_rules = [item for item in rules if item.get("alias") == "lm"]
    if len(lm_rules) != 1:
        issues.append(Module1RefValidationIssue("LM_COMPATIBILITY_MISSING", "lm compatibility rule is missing"))
        return
    rule = lm_rules[0]
    if rule.get("canonical_owner") != "lm" or rule.get("canonical_owner_meaning") != "lumen":
        issues.append(Module1RefValidationIssue("LM_CANONICAL_OWNER_INVALID", "Canonical lm must mean lumen"))
    if rule.get("automatic_mapping_allowed") is not False or rule.get("rejected_automatic_mapping") is not True:
        issues.append(Module1RefValidationIssue("LM_AUTO_NORMALIZATION_ENABLED", "Legacy lm must not auto-normalize to linear_meter"))
    if rule.get("canonical_output_when_context_confirms") != "linear_meter":
        issues.append(Module1RefValidationIssue("LINEAR_METER_CANONICAL_OUTPUT_INVALID", "Context-confirmed linear meter output must use linear_meter"))


def _loaded_object_count(payloads: Mapping[str, Mapping[str, Any]]) -> int:
    collection_names = (
        "groups",
        "material_types",
        "fields",
        "assignments",
        "units",
        "conversions",
        "profiles",
        "geometry_rules",
        "extended_rules",
    )
    return sum(
        len(payload.get(name, []))
        for payload in payloads.values()
        for name in collection_names
        if isinstance(payload.get(name), list)
    )


def _read_json(
    path: Path,
    error_code: str,
    issues: list[Module1RefValidationIssue],
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        issues.append(Module1RefValidationIssue(error_code, f"Invalid JSON file: {path.name}"))
        return {}
    if not isinstance(payload, dict):
        issues.append(Module1RefValidationIssue(error_code, f"JSON root must be an object: {path.name}"))
        return {}
    return payload


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
