from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_material_seed_registry import MaterialKnowledgeSeedRegistry


APPROVAL_ID = "ref1-read-v1-1a15fed6ebdd"
APPROVAL_VERSION = "1.0"
APPROVAL_SCHEMA_VERSION = "1.0"
EXPECTED_APPROVAL_SHA256 = "55c9f09aa1db034f22108f02a2f2afe692bdf58650ff4d2a8d0d8b70b1799973"
APPROVED_PURPOSES = ("admin_taxonomy_read", "internal_diagnostics")
DENIED_PURPOSES = (
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
)
CONSUMER_BINDINGS = {
    "admin_taxonomy_read": "module1.admin.taxonomy_view",
    "internal_diagnostics": "module1.internal.ref_diagnostics",
}


@dataclass(frozen=True)
class Module1Ref1ReadIssue:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class Ref1TaxonomyRecord:
    code: str
    name_ru: str
    canonical_parent: str | None
    read_status: str
    artifact_set_id: str

    def as_dict(self) -> dict[str, str | None]:
        return {
            "artifact_set_id": self.artifact_set_id,
            "canonical_parent": self.canonical_parent,
            "code": self.code,
            "name_ru": self.name_ru,
            "read_status": self.read_status,
        }


@dataclass(frozen=True)
class Ref1TaxonomyProjection:
    groups: tuple[Ref1TaxonomyRecord, ...]
    material_types: tuple[Ref1TaxonomyRecord, ...]
    compatibility_metadata: Mapping[str, Mapping[str, Any]]

    def filtered(
        self,
        *,
        code: str | None = None,
        name: str | None = None,
        parent: str | None = None,
    ) -> Ref1TaxonomyProjection:
        normalized_code = _text(code)
        normalized_name = _text(name)
        normalized_parent = _text(parent)

        def matches(record: Ref1TaxonomyRecord) -> bool:
            return (
                (not normalized_code or record.code == normalized_code)
                and (not normalized_name or normalized_name.casefold() in record.name_ru.casefold())
                and (not normalized_parent or record.canonical_parent == normalized_parent)
            )

        return Ref1TaxonomyProjection(
            groups=tuple(item for item in self.groups if matches(item)),
            material_types=tuple(item for item in self.material_types if matches(item)),
            compatibility_metadata=self.compatibility_metadata,
        )


@dataclass(frozen=True)
class Ref1EligibilityResult:
    code: str
    recognised_for_legacy_read: bool
    recognised_for_ref_read: bool
    eligible_for_material_write: bool
    eligible_for_catalog_product_write: bool
    eligible_for_normalizer_output: bool
    eligible_for_matching: bool
    eligible_for_moderation_approval: bool
    reason: str
    source: str
    package_version: str
    approval_version: str


@dataclass(frozen=True)
class Module1Ref1ReadPolicy:
    package_version: str
    approval_version: str
    legacy_codes: frozenset[str]
    ref_codes: frozenset[str]

    def purpose_allowed(self, purpose: str) -> bool:
        return purpose in APPROVED_PURPOSES

    def eligibility(self, code: str, *, purpose: str) -> Ref1EligibilityResult:
        normalized_code = str(code or "").strip()
        purpose_is_allowed = self.purpose_allowed(purpose)
        is_legacy = normalized_code in self.legacy_codes
        is_ref = normalized_code in self.ref_codes
        is_ref_only = is_ref and not is_legacy

        if is_legacy:
            reason = "legacy_behavior_unchanged"
            source = "legacy"
        elif is_ref_only and purpose_is_allowed:
            reason = "ref_only_read_only"
            source = "ref1"
        elif is_ref_only:
            reason = "purpose_denied"
            source = "ref1"
        else:
            reason = "unknown_code"
            source = "none"

        return Ref1EligibilityResult(
            code=normalized_code,
            recognised_for_legacy_read=is_legacy,
            recognised_for_ref_read=is_ref and purpose_is_allowed,
            eligible_for_material_write=is_legacy,
            eligible_for_catalog_product_write=is_legacy,
            eligible_for_normalizer_output=is_legacy,
            eligible_for_matching=is_legacy,
            eligible_for_moderation_approval=is_legacy,
            reason=reason,
            source=source,
            package_version=self.package_version,
            approval_version=self.approval_version,
        )


@dataclass(frozen=True)
class Module1Ref1ReadActivation:
    mode: str
    status: str
    is_valid: bool
    package_validated: bool
    approval_validated: bool
    artifact_set_id: str | None
    manifest_sha256: str | None
    approval_id: str | None
    approval_sha256: str | None
    counts: Mapping[str, int]
    issues: tuple[Module1Ref1ReadIssue, ...]
    registry_mutated: bool
    database_writes: int
    business_reads_enabled: bool
    ref_only_writes_enabled: bool
    loaded_object_count: int
    validation_duration_ms: float
    approval_validation_duration_ms: float
    projection_load_duration_ms: float
    total_duration_ms: float
    projection_size_bytes: int
    projection: Ref1TaxonomyProjection | None
    policy: Module1Ref1ReadPolicy | None

    @property
    def success(self) -> bool:
        return self.is_valid

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowlist_purposes": list(APPROVED_PURPOSES),
            "approval_id": self.approval_id,
            "approval_sha256": self.approval_sha256,
            "approval_validated": self.approval_validated,
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


def activate_module1_ref1_read(
    *,
    artifact_dir: Path,
    approval_dir: Path,
    approval_allowed_root: Path,
    package_validation: Any,
    registry: MaterialKnowledgeSeedRegistry,
) -> Module1Ref1ReadActivation:
    started = time.perf_counter()
    approval_started = time.perf_counter()
    issues: list[Module1Ref1ReadIssue] = []
    approval_sha256: str | None = None
    approval_payload: dict[str, Any] = {}
    manifest_payload: dict[str, Any] = {}
    projection: Ref1TaxonomyProjection | None = None
    policy: Module1Ref1ReadPolicy | None = None
    counts: dict[str, int] = {}
    projection_size_bytes = 0
    registry_before = _registry_snapshot(registry)

    if not package_validation.is_valid:
        issues.extend(
            Module1Ref1ReadIssue(issue.code, issue.message)
            for issue in package_validation.issues
        )
    else:
        try:
            confined_approval = _confined_approval_dir(approval_dir, approval_allowed_root)
        except ValueError as exc:
            issues.append(Module1Ref1ReadIssue("APPROVAL_PATH_INVALID", str(exc)))
            confined_approval = approval_dir

        approval_path = confined_approval / "approval_manifest.json"
        if not approval_path.is_file():
            issues.append(Module1Ref1ReadIssue("APPROVAL_MISSING", "REF-1 read approval is missing"))
        else:
            approval_sha256 = _sha256_file(approval_path)
            if approval_sha256 != EXPECTED_APPROVAL_SHA256:
                issues.append(Module1Ref1ReadIssue("APPROVAL_HASH_INVALID", "REF-1 read approval hash is invalid"))
            approval_payload = _read_json(approval_path, "APPROVAL_INVALID_JSON", issues)

        manifest_path = artifact_dir / "manifest.json"
        manifest_payload = _read_json(manifest_path, "MANIFEST_RELOAD_FAILED", issues)
        if package_validation.manifest_sha256 != _sha256_file_or_none(manifest_path):
            issues.append(Module1Ref1ReadIssue("RUNTIME_MANIFEST_CHANGED", "Runtime manifest changed after package validation"))

        if approval_payload and manifest_payload:
            _validate_approval_contract(
                approval_payload,
                manifest_payload,
                package_validation.manifest_sha256,
                issues,
            )

    approval_duration_ms = (time.perf_counter() - approval_started) * 1000
    projection_started = time.perf_counter()
    if not issues:
        taxonomy = _read_validated_artifact(artifact_dir, manifest_payload, "taxonomy.json", issues)
        compatibility = _read_validated_artifact(artifact_dir, manifest_payload, "compatibility.json", issues)
        if taxonomy and compatibility:
            projection, policy, counts = _build_projection(
                taxonomy,
                compatibility,
                approval_payload,
                registry,
                issues,
            )
            if projection is not None:
                projection_size_bytes = len(
                    json.dumps(
                        {
                            "groups": [item.as_dict() for item in projection.groups],
                            "material_types": [item.as_dict() for item in projection.material_types],
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
    projection_duration_ms = (time.perf_counter() - projection_started) * 1000

    registry_mutated = registry_before != _registry_snapshot(registry)
    if registry_mutated:
        issues.append(Module1Ref1ReadIssue("REGISTRY_MUTATION_DETECTED", "REF-1 read activation changed the legacy registry"))

    total_duration_ms = (time.perf_counter() - started) * 1000
    is_valid = not issues and projection is not None and policy is not None
    return Module1Ref1ReadActivation(
        mode="ref1_read",
        status="PASS" if is_valid else "BLOCKED",
        is_valid=is_valid,
        package_validated=package_validation.is_valid,
        approval_validated=is_valid,
        artifact_set_id=package_validation.artifact_set_id,
        manifest_sha256=package_validation.manifest_sha256,
        approval_id=approval_payload.get("approval_id") if approval_payload else None,
        approval_sha256=approval_sha256,
        counts=MappingProxyType(dict(sorted(counts.items()))),
        issues=tuple(issues),
        registry_mutated=registry_mutated,
        database_writes=0,
        business_reads_enabled=is_valid,
        ref_only_writes_enabled=False,
        loaded_object_count=sum(counts.get(key, 0) for key in ("groups", "material_types")),
        validation_duration_ms=package_validation.validation_duration_ms,
        approval_validation_duration_ms=approval_duration_ms,
        projection_load_duration_ms=projection_duration_ms,
        total_duration_ms=total_duration_ms,
        projection_size_bytes=projection_size_bytes,
        projection=projection if is_valid else None,
        policy=policy if is_valid else None,
    )


def _validate_approval_contract(
    approval: Mapping[str, Any],
    manifest: Mapping[str, Any],
    manifest_sha256: str | None,
    issues: list[Module1Ref1ReadIssue],
) -> None:
    source_hashes = {
        str(item.get("filename")): str(item.get("sha256"))
        for item in manifest.get("source_packages", [])
        if isinstance(item, Mapping)
    }
    checks = (
        (approval.get("approval_schema_version") == APPROVAL_SCHEMA_VERSION, "APPROVAL_SCHEMA_INVALID"),
        (approval.get("approval_id") == APPROVAL_ID, "APPROVAL_ID_INVALID"),
        (approval.get("approval_version") == APPROVAL_VERSION, "APPROVAL_VERSION_INVALID"),
        (approval.get("decision_number") == "036", "APPROVAL_DECISION_INVALID"),
        (approval.get("approved_modes") == ["ref1_read"], "APPROVED_MODES_INVALID"),
        (approval.get("runtime_package_id") == manifest.get("artifact_set_id"), "APPROVAL_PACKAGE_ID_INVALID"),
        (approval.get("runtime_manifest_hash") == manifest_sha256, "APPROVAL_MANIFEST_HASH_INVALID"),
        (approval.get("source_hashes") == dict(sorted(source_hashes.items())), "APPROVAL_SOURCE_HASHES_INVALID"),
        (approval.get("source_bundle_hash") == manifest.get("source_bundle_sha256"), "APPROVAL_SOURCE_BUNDLE_INVALID"),
        (approval.get("artifact_schema_version") == manifest.get("artifact_schema_version") == "1.0", "APPROVAL_ARTIFACT_SCHEMA_INVALID"),
        (approval.get("compatibility_map_version") == manifest.get("compatibility_map_version") == "1.0", "APPROVAL_COMPATIBILITY_VERSION_INVALID"),
        (approval.get("consumer_allowlist") == list(APPROVED_PURPOSES), "APPROVAL_ALLOWLIST_INVALID"),
        (approval.get("consumer_bindings") == CONSUMER_BINDINGS, "APPROVAL_BINDINGS_INVALID"),
        (approval.get("consumer_denylist") == list(DENIED_PURPOSES), "APPROVAL_DENYLIST_INVALID"),
        (approval.get("read_policy", {}).get("unknown_purpose") == "deny", "UNKNOWN_PURPOSE_POLICY_INVALID"),
        (approval.get("read_policy", {}).get("unknown_code") == "deny", "UNKNOWN_CODE_POLICY_INVALID"),
        (approval.get("integration_allowed_for_read") is True, "READ_INTEGRATION_NOT_APPROVED"),
        (approval.get("runtime_activation_allowed") is True, "RUNTIME_ACTIVATION_NOT_APPROVED"),
        (approval.get("write_activation_allowed") is False, "WRITE_ACTIVATION_APPROVED"),
        (approval.get("ref2_activation_allowed") is False, "REF2_ACTIVATION_APPROVED"),
        (approval.get("ref3_activation_allowed") is False, "REF3_ACTIVATION_APPROVED"),
        (approval.get("rollback_policy", {}).get("mode") == "legacy", "ROLLBACK_MODE_INVALID"),
        (approval.get("rollback_policy", {}).get("saved_ref_only_preferences_allowed") is False, "SAVED_PREFERENCES_INVALID"),
        (_liquid_policy_valid(approval), "LIQUID_WATERPROOFING_POLICY_INVALID"),
        (_lm_policy_valid(approval), "LM_POLICY_INVALID"),
    )
    for passed, code in checks:
        if not passed:
            issues.append(Module1Ref1ReadIssue(code, code.replace("_", " ").title()))


def _build_projection(
    taxonomy: Mapping[str, Any],
    compatibility: Mapping[str, Any],
    approval: Mapping[str, Any],
    registry: MaterialKnowledgeSeedRegistry,
    issues: list[Module1Ref1ReadIssue],
) -> tuple[Ref1TaxonomyProjection | None, Module1Ref1ReadPolicy | None, dict[str, int]]:
    groups = _unique_by_code(taxonomy.get("groups"), "groups", issues)
    material_types = _unique_by_code(taxonomy.get("material_types"), "material_types", issues)
    legacy_codes = frozenset(child for group in registry.taxonomy for child in group.children)
    ref_codes = frozenset(material_types)
    ref_only_codes = ref_codes - legacy_codes
    ref_only_groups = {code for code, item in groups.items() if item.get("legacy_recognized") is not True}

    counts = {
        "groups": len(groups),
        "legacy_groups": len(groups) - len(ref_only_groups),
        "legacy_material_types": len(ref_codes & legacy_codes),
        "material_types": len(material_types),
        "ref_only_groups": len(ref_only_groups),
        "ref_only_material_types": len(ref_only_codes),
    }
    expected_counts = {
        "groups": 37,
        "legacy_groups": 19,
        "legacy_material_types": 192,
        "material_types": 978,
        "ref_only_groups": 18,
        "ref_only_material_types": 786,
    }
    if counts != expected_counts:
        issues.append(Module1Ref1ReadIssue("PROJECTION_COUNT_MISMATCH", f"Expected {expected_counts}; got {counts}"))

    compatibility_taxonomy = compatibility.get("taxonomy", {})
    if _compatibility_codes(compatibility_taxonomy.get("ref_only_material_types")) != ref_only_codes:
        issues.append(Module1Ref1ReadIssue("REF_ONLY_COMPATIBILITY_MISMATCH", "REF-only compatibility set differs from projection"))
    if _compatibility_codes(compatibility_taxonomy.get("legacy_material_types")) != ref_codes & legacy_codes:
        issues.append(Module1Ref1ReadIssue("LEGACY_COMPATIBILITY_MISMATCH", "Legacy compatibility set differs from projection"))

    liquid = material_types.get("liquid_waterproofing")
    if liquid is None or liquid.get("canonical_parent") != "waterproofing":
        issues.append(Module1Ref1ReadIssue("LIQUID_WATERPROOFING_CANONICAL_INVALID", "liquid_waterproofing must have one waterproofing parent"))

    if issues:
        return None, None, counts

    artifact_set_id = str(taxonomy.get("artifact_set_id"))
    group_records = tuple(
        Ref1TaxonomyRecord(
            code=code,
            name_ru=str(item.get("name_ru") or code),
            canonical_parent=None,
            read_status="LEGACY_COMPATIBLE_READ_ONLY" if item.get("legacy_recognized") is True else "REF_ONLY_READ_ONLY",
            artifact_set_id=artifact_set_id,
        )
        for code, item in sorted(groups.items())
    )
    type_records = tuple(
        Ref1TaxonomyRecord(
            code=code,
            name_ru=str(item.get("name_ru") or code),
            canonical_parent=_text(item.get("canonical_parent")),
            read_status="LEGACY_COMPATIBLE_READ_ONLY" if code in legacy_codes else "REF_ONLY_READ_ONLY",
            artifact_set_id=artifact_set_id,
        )
        for code, item in sorted(material_types.items())
    )
    liquid_conflict = next(
        item
        for item in compatibility_taxonomy.get("special_conflicts", [])
        if item.get("code") == "liquid_waterproofing"
    )
    compatibility_metadata = MappingProxyType(
        {
            "liquid_waterproofing": MappingProxyType(
                {
                    "canonical_parent": "waterproofing",
                    "legacy_parent_paths": tuple(liquid_conflict.get("legacy_parent_paths", [])),
                    "legacy_paths_metadata_only": True,
                    "write_eligible": False,
                }
            )
        }
    )
    projection = Ref1TaxonomyProjection(
        groups=group_records,
        material_types=type_records,
        compatibility_metadata=compatibility_metadata,
    )
    policy = Module1Ref1ReadPolicy(
        package_version=artifact_set_id,
        approval_version=str(approval.get("approval_version")),
        legacy_codes=legacy_codes,
        ref_codes=ref_codes,
    )
    return projection, policy, counts


def _confined_approval_dir(path: Path, allowed_root: Path) -> Path:
    resolved = path.resolve()
    root = allowed_root.resolve()
    if root not in resolved.parents or resolved.name != APPROVAL_ID:
        raise ValueError("Approval directory is outside the configured approval root")
    return resolved


def _read_validated_artifact(
    artifact_dir: Path,
    manifest: Mapping[str, Any],
    filename: str,
    issues: list[Module1Ref1ReadIssue],
) -> dict[str, Any]:
    path = artifact_dir / filename
    contract = manifest.get("artifacts", {}).get(filename, {})
    if not path.is_file() or _sha256_file_or_none(path) != contract.get("sha256"):
        issues.append(Module1Ref1ReadIssue("ARTIFACT_CHANGED_AFTER_VALIDATION", f"Artifact changed after validation: {filename}"))
        return {}
    return _read_json(path, "ARTIFACT_RELOAD_FAILED", issues)


def _unique_by_code(
    records: Any,
    label: str,
    issues: list[Module1Ref1ReadIssue],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    duplicates: set[str] = set()
    for item in records if isinstance(records, list) else []:
        if not isinstance(item, Mapping):
            continue
        code = _text(item.get("code"))
        if not code:
            continue
        if code in result:
            duplicates.add(code)
        result[code] = item
    if duplicates:
        issues.append(Module1Ref1ReadIssue("DUPLICATE_CANONICAL_TYPE", f"Duplicate {label}: {sorted(duplicates)}"))
    return result


def _compatibility_codes(records: Any) -> frozenset[str]:
    values: set[str] = set()
    for item in records if isinstance(records, list) else []:
        value = item.get("code") if isinstance(item, Mapping) else item
        code = _text(value)
        if code:
            values.add(code)
    return frozenset(values)


def _liquid_policy_valid(approval: Mapping[str, Any]) -> bool:
    policy = approval.get("canonical_conflict_policies", {}).get("liquid_waterproofing", {})
    return (
        policy.get("code") == "liquid_waterproofing"
        and policy.get("canonical_ref_parent") == "waterproofing"
        and policy.get("legacy_paths") == ["primers_chemicals_sealants", "waterproofing"]
        and policy.get("legacy_paths_metadata_only") is True
        and policy.get("existing_records_migrated") is False
        and policy.get("duplicate_canonical_registration_allowed") is False
        and policy.get("ref_only_write_allowed") is False
        and policy.get("legacy_business_lookups_changed") is False
    )


def _lm_policy_valid(approval: Mapping[str, Any]) -> bool:
    policy = approval.get("canonical_conflict_policies", {}).get("lm", {})
    return (
        policy.get("canonical_code") == "lm"
        and policy.get("canonical_meaning") == "lumen"
        and policy.get("linear_meter_canonical_code") == "linear_meter"
        and policy.get("legacy_lm_to_linear_meter") == "context_required"
        and policy.get("automatic_normalization_allowed") is False
        and policy.get("ref3_activation_allowed") is False
    )


def _registry_snapshot(registry: MaterialKnowledgeSeedRegistry) -> tuple[Any, ...]:
    return (
        registry.version,
        tuple((group.code, group.name, group.children) for group in registry.taxonomy),
        tuple(sorted(registry.characteristic_schemas)),
        tuple(sorted(registry.role_mappings)),
    )


def _read_json(
    path: Path,
    error_code: str,
    issues: list[Module1Ref1ReadIssue],
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        issues.append(Module1Ref1ReadIssue(error_code, f"Cannot read JSON: {path.name}"))
        return {}
    if not isinstance(payload, dict):
        issues.append(Module1Ref1ReadIssue(error_code, f"JSON root must be an object: {path.name}"))
        return {}
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_file_or_none(path: Path) -> str | None:
    try:
        return _sha256_file(path)
    except OSError:
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
