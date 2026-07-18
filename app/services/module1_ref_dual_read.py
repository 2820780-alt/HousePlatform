from __future__ import annotations

import hashlib
import json
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_material_seed_registry import (
    MaterialKnowledgeSeedRegistry,
    get_material_knowledge_seed_registry,
)


DUAL_READ_RESULT_SCHEMA_VERSION = "1.0"
SUPPORTED_DUAL_READ_RESULT_SCHEMAS = frozenset({DUAL_READ_RESULT_SCHEMA_VERSION})


@dataclass(frozen=True)
class Module1RefComparisonIssue:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class Module1RefComparisonEntry:
    code: str
    kind: str
    classification: str
    legacy_title: str | None = None
    ref_title: str | None = None
    legacy_parent_paths: tuple[str, ...] = tuple()
    canonical_ref_parent: str | None = None
    write_eligible: bool = False
    notes: tuple[str, ...] = tuple()

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_ref_parent": self.canonical_ref_parent,
            "classification": self.classification,
            "code": self.code,
            "kind": self.kind,
            "legacy_parent_paths": list(self.legacy_parent_paths),
            "legacy_title": self.legacy_title,
            "notes": list(self.notes),
            "ref_title": self.ref_title,
            "write_eligible": self.write_eligible,
        }


@dataclass(frozen=True)
class Module1RefDualReadResult:
    result_schema_version: str
    mode: str
    status: str
    is_valid: bool
    package_validated: bool
    artifact_set_id: str | None
    artifact_package_version: str | None
    artifact_manifest_hash: str | None
    legacy_registry_fingerprint: str
    compared_at_runtime_start: str
    counts: Mapping[str, int]
    categories: Mapping[str, tuple[Module1RefComparisonEntry, ...]]
    conflicts: tuple[Module1RefComparisonEntry, ...]
    compatibility_decisions: Mapping[str, Any]
    mutation_summary: Mapping[str, Any]
    write_summary: Mapping[str, Any]
    warnings: tuple[Module1RefComparisonIssue, ...]
    blockers: tuple[Module1RefComparisonIssue, ...]
    registry_mutated: bool
    database_writes: int
    business_reads_enabled: bool
    ref_only_writes_enabled: bool
    loaded_object_count: int
    validation_duration_ms: float
    comparison_duration_ms: float
    total_duration_ms: float
    legacy_snapshot_size_bytes: int
    comparison_entry_count: int

    @property
    def success(self) -> bool:
        return self.is_valid

    @property
    def issues(self) -> tuple[Module1RefComparisonIssue, ...]:
        return self.blockers

    @property
    def manifest_sha256(self) -> str | None:
        return self.artifact_manifest_hash

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_manifest_hash": self.artifact_manifest_hash,
            "artifact_package_version": self.artifact_package_version,
            "artifact_set_id": self.artifact_set_id,
            "blockers": [item.as_dict() for item in self.blockers],
            "business_reads_enabled": self.business_reads_enabled,
            "categories": {
                key: [entry.as_dict() for entry in entries]
                for key, entries in self.categories.items()
            },
            "compared_at_runtime_start": self.compared_at_runtime_start,
            "comparison_duration_ms": self.comparison_duration_ms,
            "comparison_entry_count": self.comparison_entry_count,
            "compatibility_decisions": _thaw(self.compatibility_decisions),
            "counts": dict(self.counts),
            "conflicts": [entry.as_dict() for entry in self.conflicts],
            "database_writes": self.database_writes,
            "is_valid": self.is_valid,
            "legacy_registry_fingerprint": self.legacy_registry_fingerprint,
            "legacy_snapshot_size_bytes": self.legacy_snapshot_size_bytes,
            "loaded_object_count": self.loaded_object_count,
            "mode": self.mode,
            "mutation_summary": _thaw(self.mutation_summary),
            "package_validated": self.package_validated,
            "ref_only_writes_enabled": self.ref_only_writes_enabled,
            "registry_mutated": self.registry_mutated,
            "result_schema_version": self.result_schema_version,
            "status": self.status,
            "success": self.success,
            "total_duration_ms": self.total_duration_ms,
            "validation_duration_ms": self.validation_duration_ms,
            "warnings": [item.as_dict() for item in self.warnings],
            "write_summary": _thaw(self.write_summary),
        }


def compare_module1_ref_runtime(
    *,
    artifact_dir: str | Path,
    allowed_root: str | Path,
    registry: MaterialKnowledgeSeedRegistry | None = None,
) -> Module1RefDualReadResult:
    from app.services.module1_ref_runtime_artifacts import (
        snapshot_legacy_material_registry,
        validate_module1_ref_runtime,
    )

    started = time.perf_counter()
    compared_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    effective_registry = registry or get_material_knowledge_seed_registry()
    registry_before = snapshot_legacy_material_registry(effective_registry)
    legacy_snapshot = build_legacy_taxonomy_snapshot(effective_registry)
    fingerprint_before = fingerprint_legacy_registry_snapshot(legacy_snapshot)
    snapshot_size = len(_canonical_json_bytes(_thaw(legacy_snapshot)))

    validation = validate_module1_ref_runtime(
        "artifact_validation",
        artifact_dir=artifact_dir,
        allowed_root=allowed_root,
        registry=effective_registry,
    )
    if not validation.is_valid:
        blockers = tuple(
            Module1RefComparisonIssue(item.code, item.message)
            for item in validation.issues
        )
        return _build_result(
            started=started,
            compared_at=compared_at,
            validation=validation,
            fingerprint=fingerprint_before,
            snapshot_size=snapshot_size,
            blockers=blockers,
        )

    comparison_started = time.perf_counter()
    blockers: list[Module1RefComparisonIssue] = []
    warnings: list[Module1RefComparisonIssue] = []
    target = Path(artifact_dir).resolve()
    manifest = _read_json(target / "manifest.json", blockers)
    taxonomy = _read_json(target / "taxonomy.json", blockers)
    compatibility = _read_json(target / "compatibility.json", blockers)

    if manifest and validation.manifest_sha256 != _sha256_file(target / "manifest.json"):
        blockers.append(Module1RefComparisonIssue("MANIFEST_CHANGED_AFTER_VALIDATION", "Manifest changed after package validation"))
    _verify_reloaded_artifact_hash(manifest, target, "taxonomy.json", blockers)
    _verify_reloaded_artifact_hash(manifest, target, "compatibility.json", blockers)

    categories, counts, comparison_warnings, comparison_blockers = _compare_taxonomy(
        legacy_snapshot,
        taxonomy,
        compatibility,
    )
    warnings.extend(comparison_warnings)
    blockers.extend(comparison_blockers)

    liquid_decision = _liquid_waterproofing_decision(taxonomy, compatibility, blockers)
    lm_decision = _lm_compatibility_decision(compatibility, blockers)
    categories["diagnostics"].extend(
        (
            Module1RefComparisonEntry(
                code="liquid_waterproofing",
                kind="material_type",
                classification="compatibility_only",
                legacy_parent_paths=tuple(liquid_decision["legacy_parent_paths"]),
                canonical_ref_parent=liquid_decision["canonical_ref_parent"],
                write_eligible=False,
                notes=("single_ref_parent", "legacy_paths_preserved", "runtime_mutation_false"),
            ),
            Module1RefComparisonEntry(
                code="lm",
                kind="unit_alias",
                classification="review_required",
                canonical_ref_parent=None,
                write_eligible=False,
                notes=("canonical_lumen", "linear_meter_separate", "context_required"),
            ),
        )
    )

    registry_after = snapshot_legacy_material_registry(effective_registry)
    legacy_snapshot_after = build_legacy_taxonomy_snapshot(effective_registry)
    fingerprint_after = fingerprint_legacy_registry_snapshot(legacy_snapshot_after)
    registry_mutated = registry_before != registry_after or fingerprint_before != fingerprint_after
    if registry_mutated:
        blockers.append(Module1RefComparisonIssue("REGISTRY_MUTATION_DETECTED", "Dual-read comparison changed the legacy registry"))

    result_schema_version = DUAL_READ_RESULT_SCHEMA_VERSION
    if result_schema_version not in SUPPORTED_DUAL_READ_RESULT_SCHEMAS:
        blockers.append(Module1RefComparisonIssue("RESULT_SCHEMA_UNSUPPORTED", "Dual-read result schema is unsupported"))

    comparison_duration_ms = (time.perf_counter() - comparison_started) * 1000
    total_duration_ms = (time.perf_counter() - started) * 1000
    immutable_categories = MappingProxyType(
        {key: tuple(entries) for key, entries in sorted(categories.items())}
    )
    conflicts = tuple(immutable_categories["duplicate_parent_conflicts"])
    compatibility_decisions = _freeze_mapping(
        {
            "liquid_waterproofing": liquid_decision,
            "lm_alias": lm_decision,
        }
    )
    mutation_summary = _freeze_mapping(
        {
            "database_writes": 0,
            "fingerprint_after": fingerprint_after,
            "fingerprint_before": fingerprint_before,
            "registry_mutated": registry_mutated,
            "snapshot_equal": registry_before == registry_after,
        }
    )
    write_summary = _freeze_mapping(
        {
            "business_reads_enabled": False,
            "public_lookup_source": "legacy",
            "ref_only_writes_enabled": False,
            "runtime_activation_allowed": False,
            "write_activation_allowed": False,
        }
    )
    entry_count = sum(len(entries) for entries in immutable_categories.values())
    status = "BLOCKED" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return Module1RefDualReadResult(
        result_schema_version=result_schema_version,
        mode="dual_read",
        status=status,
        is_valid=not blockers,
        package_validated=True,
        artifact_set_id=validation.artifact_set_id,
        artifact_package_version=validation.artifact_set_id,
        artifact_manifest_hash=validation.manifest_sha256,
        legacy_registry_fingerprint=fingerprint_before,
        compared_at_runtime_start=compared_at,
        counts=MappingProxyType(dict(sorted(counts.items()))),
        categories=immutable_categories,
        conflicts=conflicts,
        compatibility_decisions=compatibility_decisions,
        mutation_summary=mutation_summary,
        write_summary=write_summary,
        warnings=tuple(warnings),
        blockers=tuple(blockers),
        registry_mutated=registry_mutated,
        database_writes=0,
        business_reads_enabled=False,
        ref_only_writes_enabled=False,
        loaded_object_count=validation.loaded_object_count,
        validation_duration_ms=validation.validation_duration_ms,
        comparison_duration_ms=comparison_duration_ms,
        total_duration_ms=total_duration_ms,
        legacy_snapshot_size_bytes=snapshot_size,
        comparison_entry_count=entry_count,
    )


def build_legacy_taxonomy_snapshot(
    registry: MaterialKnowledgeSeedRegistry,
) -> Mapping[str, Any]:
    parents: dict[str, set[str]] = {}
    groups: list[dict[str, Any]] = []
    for group in sorted(registry.taxonomy, key=lambda item: item.code):
        children = tuple(sorted(group.children))
        groups.append({"children": children, "code": group.code, "title": group.name})
        for child in children:
            parents.setdefault(child, set()).add(group.code)
    material_types = tuple(
        {
            "code": code,
            "parent_paths": tuple(sorted(parent_codes)),
        }
        for code, parent_codes in sorted(parents.items())
    )
    return _freeze_mapping(
        {
            "boundaries": dict(sorted(registry.boundaries.items())),
            "groups": tuple(groups),
            "material_types": material_types,
            "module": registry.module,
            "purpose": registry.purpose,
            "version": registry.version,
        }
    )


def fingerprint_legacy_registry_snapshot(snapshot: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(_thaw(snapshot))).hexdigest()


def _compare_taxonomy(
    legacy_snapshot: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    compatibility: Mapping[str, Any],
) -> tuple[
    dict[str, list[Module1RefComparisonEntry]],
    dict[str, int],
    list[Module1RefComparisonIssue],
    list[Module1RefComparisonIssue],
]:
    warnings: list[Module1RefComparisonIssue] = []
    blockers: list[Module1RefComparisonIssue] = []
    legacy_groups = {item["code"]: item for item in legacy_snapshot.get("groups", ())}
    legacy_types = {item["code"]: item for item in legacy_snapshot.get("material_types", ())}
    ref_group_records = list(taxonomy.get("groups", []))
    ref_type_records = list(taxonomy.get("material_types", []))
    ref_groups, duplicate_groups = _unique_records(ref_group_records)
    ref_types, duplicate_types = _unique_records(ref_type_records)
    if duplicate_groups or duplicate_types:
        blockers.append(
            Module1RefComparisonIssue(
                "DUPLICATE_CANONICAL_CODE",
                f"Duplicate groups={duplicate_groups}; material_types={duplicate_types}",
            )
        )

    exact_group_codes = sorted(set(legacy_groups) & set(ref_groups))
    exact_type_codes = sorted(set(legacy_types) & set(ref_types))
    ref_only_group_codes = sorted(set(ref_groups) - set(legacy_groups))
    ref_only_type_codes = sorted(set(ref_types) - set(legacy_types))
    legacy_only_group_codes = sorted(set(legacy_groups) - set(ref_groups))
    legacy_only_type_codes = sorted(set(legacy_types) - set(ref_types))

    categories: dict[str, list[Module1RefComparisonEntry]] = {
        "blocked_write_codes": [],
        "compatibility_only_matches": [],
        "diagnostics": [],
        "duplicate_parent_conflicts": [],
        "exact_groups": [],
        "exact_material_types": [],
        "legacy_only_groups": [],
        "legacy_only_material_types": [],
        "parent_path_mismatches": [],
        "ref_only_groups": [],
        "ref_only_material_types": [],
        "title_mismatches": [],
    }

    for code in exact_group_codes:
        legacy = legacy_groups[code]
        ref = ref_groups[code]
        classification = (
            "exact_semantic_match"
            if _normalize_title(legacy.get("title")) == _normalize_title(ref.get("name_ru"))
            else "exact_code_title_difference"
        )
        entry = _entry(code, "group", classification, legacy, ref)
        categories["exact_groups"].append(entry)
        if classification == "exact_code_title_difference":
            categories["title_mismatches"].append(entry)

    for code in exact_type_codes:
        legacy = legacy_types[code]
        ref = ref_types[code]
        legacy_parents = tuple(legacy.get("parent_paths", ()))
        canonical_parent = _text(ref.get("canonical_parent"))
        parent_differs = set(legacy_parents) != ({canonical_parent} if canonical_parent else set())
        classification = "exact_code_parent_difference" if parent_differs else "exact_semantic_match"
        entry = _entry(code, "material_type", classification, legacy, ref)
        categories["exact_material_types"].append(entry)
        if parent_differs:
            categories["parent_path_mismatches"].append(entry)
        if len(legacy_parents) > 1:
            conflict = _entry(code, "material_type", "compatibility_only", legacy, ref)
            categories["duplicate_parent_conflicts"].append(conflict)
            categories["compatibility_only_matches"].append(conflict)

    categories["ref_only_groups"] = [
        _entry(code, "group", "blocked", None, ref_groups[code])
        for code in ref_only_group_codes
    ]
    categories["ref_only_material_types"] = [
        _entry(code, "material_type", "blocked", None, ref_types[code])
        for code in ref_only_type_codes
    ]
    categories["legacy_only_groups"] = [
        _entry(code, "group", "review_required", legacy_groups[code], None)
        for code in legacy_only_group_codes
    ]
    categories["legacy_only_material_types"] = [
        _entry(code, "material_type", "review_required", legacy_types[code], None)
        for code in legacy_only_type_codes
    ]
    categories["blocked_write_codes"] = [
        _entry(code, "material_type", "blocked", legacy_types.get(code), ref)
        for code, ref in sorted(ref_types.items())
        if ref.get("write_eligible") is not True
    ]

    if legacy_only_group_codes or legacy_only_type_codes:
        blockers.append(
            Module1RefComparisonIssue(
                "UNEXPECTED_LEGACY_ONLY_CODE",
                f"Legacy-only groups={legacy_only_group_codes}; material_types={legacy_only_type_codes}",
            )
        )

    taxonomy_compat = compatibility.get("taxonomy", {})
    expected_sets = {
        "legacy_groups": set(exact_group_codes),
        "legacy_material_types": set(exact_type_codes),
        "ref_only_groups": set(ref_only_group_codes),
        "ref_only_material_types": set(ref_only_type_codes),
    }
    for key, expected in expected_sets.items():
        if _compatibility_codes(taxonomy_compat.get(key, [])) != expected:
            blockers.append(Module1RefComparisonIssue("COMPATIBILITY_MAP_MISMATCH", f"Compatibility set differs for {key}"))

    if categories["title_mismatches"]:
        warnings.append(Module1RefComparisonIssue("TITLE_MISMATCHES", f"Title mismatches: {len(categories['title_mismatches'])}"))
    if categories["duplicate_parent_conflicts"]:
        warnings.append(Module1RefComparisonIssue("DUPLICATE_PARENT_COMPATIBILITY", f"Compatibility-only duplicate parents: {len(categories['duplicate_parent_conflicts'])}"))

    counts = {
        "blocked_write_codes": len(categories["blocked_write_codes"]),
        "compatibility_only_matches": len(categories["compatibility_only_matches"]),
        "duplicate_parent_conflicts": len(categories["duplicate_parent_conflicts"]),
        "exact_groups": len(exact_group_codes),
        "exact_material_types": len(exact_type_codes),
        "legacy_groups": len(legacy_groups),
        "legacy_material_types": len(legacy_types),
        "legacy_only_groups": len(legacy_only_group_codes),
        "legacy_only_material_types": len(legacy_only_type_codes),
        "parent_path_mismatches": len(categories["parent_path_mismatches"]),
        "ref_groups": len(ref_groups),
        "ref_material_types": len(ref_types),
        "ref_only_groups": len(ref_only_group_codes),
        "ref_only_material_types": len(ref_only_type_codes),
        "title_mismatches": len(categories["title_mismatches"]),
    }
    return categories, counts, warnings, blockers


def _liquid_waterproofing_decision(
    taxonomy: Mapping[str, Any],
    compatibility: Mapping[str, Any],
    blockers: list[Module1RefComparisonIssue],
) -> dict[str, Any]:
    records = [item for item in taxonomy.get("material_types", []) if item.get("code") == "liquid_waterproofing"]
    conflicts = [item for item in compatibility.get("taxonomy", {}).get("special_conflicts", []) if item.get("code") == "liquid_waterproofing"]
    expected_paths = {"primers_chemicals_sealants", "waterproofing"}
    valid = (
        len(records) == 1
        and records[0].get("canonical_parent") == "waterproofing"
        and len(conflicts) == 1
        and set(conflicts[0].get("legacy_parent_paths", [])) == expected_paths
        and conflicts[0].get("write_eligible") is False
    )
    if not valid:
        blockers.append(Module1RefComparisonIssue("LIQUID_WATERPROOFING_COMPATIBILITY_INVALID", "liquid_waterproofing compatibility decision is invalid"))
    return {
        "canonical_code_count": len(records),
        "canonical_ref_parent": records[0].get("canonical_parent") if len(records) == 1 else None,
        "compatibility_resolution": conflicts[0].get("compatibility_status") if len(conflicts) == 1 else None,
        "conflict_type": "duplicate_legacy_parent",
        "legacy_parent_paths": sorted(expected_paths),
        "runtime_mutation": False,
        "valid": valid,
        "write_eligible": False,
    }


def _lm_compatibility_decision(
    compatibility: Mapping[str, Any],
    blockers: list[Module1RefComparisonIssue],
) -> dict[str, Any]:
    rules = compatibility.get("units", {}).get("special_alias_rules", [])
    matches = [item for item in rules if item.get("alias") == "lm"]
    rule = matches[0] if len(matches) == 1 else {}
    valid = (
        len(matches) == 1
        and rule.get("canonical_owner") == "lm"
        and rule.get("canonical_owner_meaning") == "lumen"
        and rule.get("canonical_output_when_context_confirms") == "linear_meter"
        and rule.get("automatic_mapping_allowed") is False
        and rule.get("rejected_automatic_mapping") is True
    )
    if not valid:
        blockers.append(Module1RefComparisonIssue("LM_COMPATIBILITY_INVALID", "lm/linear_meter compatibility decision is invalid"))
    return {
        "automatic_mapping_allowed": False,
        "canonical_lm_meaning": "lumen",
        "context_required": True,
        "legacy_target": "linear_meter",
        "linear_meter_canonical_code": "linear_meter",
        "valid": valid,
    }


def _build_result(
    *,
    started: float,
    compared_at: str,
    validation: Any,
    fingerprint: str,
    snapshot_size: int,
    blockers: tuple[Module1RefComparisonIssue, ...],
) -> Module1RefDualReadResult:
    total_duration_ms = (time.perf_counter() - started) * 1000
    return Module1RefDualReadResult(
        result_schema_version=DUAL_READ_RESULT_SCHEMA_VERSION,
        mode="dual_read",
        status="BLOCKED",
        is_valid=False,
        package_validated=False,
        artifact_set_id=validation.artifact_set_id,
        artifact_package_version=validation.artifact_set_id,
        artifact_manifest_hash=validation.manifest_sha256,
        legacy_registry_fingerprint=fingerprint,
        compared_at_runtime_start=compared_at,
        counts=MappingProxyType({}),
        categories=MappingProxyType({}),
        conflicts=tuple(),
        compatibility_decisions=MappingProxyType({}),
        mutation_summary=_freeze_mapping({"database_writes": 0, "registry_mutated": validation.registry_mutated}),
        write_summary=_freeze_mapping({"business_reads_enabled": False, "ref_only_writes_enabled": False}),
        warnings=tuple(),
        blockers=blockers,
        registry_mutated=validation.registry_mutated,
        database_writes=0,
        business_reads_enabled=False,
        ref_only_writes_enabled=False,
        loaded_object_count=validation.loaded_object_count,
        validation_duration_ms=validation.validation_duration_ms,
        comparison_duration_ms=0.0,
        total_duration_ms=total_duration_ms,
        legacy_snapshot_size_bytes=snapshot_size,
        comparison_entry_count=0,
    )


def _entry(
    code: str,
    kind: str,
    classification: str,
    legacy: Mapping[str, Any] | None,
    ref: Mapping[str, Any] | None,
) -> Module1RefComparisonEntry:
    legacy = legacy or {}
    ref = ref or {}
    return Module1RefComparisonEntry(
        code=code,
        kind=kind,
        classification=classification,
        legacy_title=_text(legacy.get("title")),
        ref_title=_text(ref.get("name_ru")),
        legacy_parent_paths=tuple(legacy.get("parent_paths", ())),
        canonical_ref_parent=_text(ref.get("canonical_parent")),
        write_eligible=ref.get("write_eligible") is True,
    )


def _unique_records(records: list[Any]) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    result: dict[str, Mapping[str, Any]] = {}
    duplicates: set[str] = set()
    for item in records:
        if not isinstance(item, dict):
            continue
        code = _text(item.get("code"))
        if not code:
            continue
        if code in result:
            duplicates.add(code)
        else:
            result[code] = item
    return result, sorted(duplicates)


def _compatibility_codes(records: Any) -> set[str]:
    result: set[str] = set()
    for item in records if isinstance(records, list) else []:
        code = item.get("code") if isinstance(item, dict) else item
        text = _text(code)
        if text:
            result.add(text)
    return result


def _verify_reloaded_artifact_hash(
    manifest: Mapping[str, Any],
    target: Path,
    filename: str,
    blockers: list[Module1RefComparisonIssue],
) -> None:
    expected = manifest.get("artifacts", {}).get(filename, {}).get("sha256")
    path = target / filename
    if not expected or not path.is_file() or _sha256_file(path) != expected:
        blockers.append(Module1RefComparisonIssue("ARTIFACT_CHANGED_AFTER_VALIDATION", f"Artifact changed after validation: {filename}"))


def _read_json(path: Path, blockers: list[Module1RefComparisonIssue]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        blockers.append(Module1RefComparisonIssue("COMPARISON_ARTIFACT_READ_FAILED", f"Cannot read validated artifact: {path.name}"))
        return {}
    if not isinstance(payload, dict):
        blockers.append(Module1RefComparisonIssue("COMPARISON_ARTIFACT_INVALID", f"Artifact root is not an object: {path.name}"))
        return {}
    return payload


def _normalize_title(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze(item) for key, item in sorted(value.items())})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
