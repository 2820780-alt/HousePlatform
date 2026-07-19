from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
ARTIFACT_SET_ID = "ref45-runtime-v1-5fe5e067d0dd"
ARTIFACT_SCHEMA_VERSION = "1.0"
GENERATOR_VERSION = "1.0"
SOURCE_FILES: Mapping[str, tuple[str, str]] = {
    "REF-4": (
        "ATOM_REF4_Synonyms_Normalization_v1.0.1_PRELIMINARY_APPROVED.json",
        "22f030cc1dfee3e638999ab1f918552b38b8ffb5fe410969881c0daa181a632d",
    ),
    "REF-5": (
        "ATOM_REF5_Analogs_Alternatives_Compatibility_v1_PRELIMINARY_APPROVED.json",
        "8fd9a2bbeb95ee52b2879c5f6f1b269c0f80e75e37a24403cee26f9b1a9fb12d",
    ),
    "REF-45-MANIFEST": (
        "ATOM_REF45_Package_Manifest_v1.0.1_PRELIMINARY_APPROVED.json",
        "5fe5e067d0dd7235ac54062ed34bad640f1689d358b365dc98b728d0e9682ff7",
    ),
    "REF-45-SUMMARY": (
        "ATOM_REF45_Summary_v1.0.1_PRELIMINARY_APPROVED.json",
        "a0564f86eae192d5925af2829fb9225f7d2feafe0cee170267c0e6b54b2a287d",
    ),
    "REF-45-APPROVAL": (
        "ATOM_REF45_Approval_Record_v1.0.1.md",
        "1d7251d648a5c5b38a61a551e413fcd8cb4ff2b14ed5d695a51f4e40aa1682ee",
    ),
    "REF-45-CORRECTION": (
        "ATOM_REF45_Correction_Record_v1.0.1.json",
        "770d7f0e71974e930cfb65a037cd34c77cd7fa969b78e74c44dcd2b7c0dbf9f3",
    ),
}
ARTIFACT_FILENAMES = (
    "ref4_alias_rules.json",
    "ref4_material_type_profiles.json",
    "ref4_normalization_policy.json",
    "ref5_context_compatibility.json",
    "ref5_substitution_policies.json",
    "review_queue.json",
    "legacy_compatibility.json",
)
MANIFEST_FILENAME = "manifest.json"
EXPECTED_COUNTS = {
    "taxonomy_material_types": 978,
    "ref4_alias_rules": 89,
    "ref4_trusted_alias_rules": 44,
    "ref4_review_rules": 45,
    "ref5_context_rules": 15,
    "ref5_substitution_rules": 13,
    "ref5_active_substitution_policies": 3,
    "ref5_review_rules": 10,
    "automatic_replacements": 0,
    "work_material_mappings": 0,
}


class Ref45BuildError(ValueError):
    pass


@dataclass(frozen=True)
class Ref45BuildResult:
    artifact_set_id: str
    output_dir: Path
    artifact_hashes: Mapping[str, str]
    manifest_sha256: str
    source_hashes: Mapping[str, str]
    counts: Mapping[str, int]
    idempotent: bool


def build_ref45_runtime_artifacts(
    reference_root: str | Path = REFERENCE_ROOT,
    output_root: str | Path = RUNTIME_REFERENCE_ROOT,
) -> Ref45BuildResult:
    reference_root = Path(reference_root)
    output_root = Path(output_root)
    source_payloads, source_hashes = load_ref45_source_package(reference_root)
    ref4 = source_payloads["REF-4"]
    ref5 = source_payloads["REF-5"]
    correction = source_payloads["REF-45-CORRECTION"]
    compatibility = build_legacy_compatibility(ref4)
    _validate_source_content(reference_root, ref4, ref5, correction, compatibility)

    payloads: dict[str, dict[str, Any]] = {
        "ref4_alias_rules.json": {
            **_header("ref4_alias_rules"),
            "counts": {
                "rules": len(ref4["alias_rules"]),
                "trusted": sum(bool(item["automatic_material_type_resolution_allowed"]) for item in ref4["alias_rules"]),
                "review_or_context": sum(not bool(item["automatic_material_type_resolution_allowed"]) for item in ref4["alias_rules"]),
            },
            "rules": sorted(ref4["alias_rules"], key=lambda item: item["alias_rule_id"]),
        },
        "ref4_material_type_profiles.json": {
            **_header("ref4_material_type_profiles"),
            "counts": {"profiles": len(ref4["material_type_profiles"])},
            "profiles": sorted(ref4["material_type_profiles"], key=lambda item: item["material_type_id"]),
        },
        "ref4_normalization_policy.json": {
            **_header("ref4_normalization_policy"),
            "blocked_automatic_mappings": sorted(
                ref4["blocked_automatic_mappings"],
                key=lambda item: _stable_item_key(item),
            ),
            "constitutional_boundaries": ref4["constitutional_boundaries"],
            "normalization_policy": ref4["normalization_policy"],
        },
        "ref5_context_compatibility.json": {
            **_header("ref5_context_compatibility"),
            "counts": {"rules": len(ref5["context_compatibility_rules"])},
            "execution_allowed": False,
            "rules": sorted(ref5["context_compatibility_rules"], key=lambda item: item["relation_id"]),
        },
        "ref5_substitution_policies.json": {
            **_header("ref5_substitution_policies"),
            "automatic_replacement_allowed": False,
            "counts": {
                "rules": len(ref5["substitution_rules"]),
                "active_read_only_or_safety": sum(_active_substitution(item) for item in ref5["substitution_rules"]),
                "review": len(ref5["review_queue"]),
            },
            "rules": sorted(ref5["substitution_rules"], key=lambda item: item["relation_id"]),
        },
        "review_queue.json": {
            **_header("ref45_review_queue"),
            "automatic_approval_allowed": False,
            "counts": {
                "ref4": len(ref4["review_queue"]),
                "ref5": len(ref5["review_queue"]),
                "total": len(ref4["review_queue"]) + len(ref5["review_queue"]),
            },
            "ref4": sorted(ref4["review_queue"], key=lambda item: item["review_id"]),
            "ref5": sorted(ref5["review_queue"], key=lambda item: item["review_id"]),
        },
        "legacy_compatibility.json": {
            **_header("ref45_legacy_compatibility"),
            **compatibility,
        },
    }
    artifact_bytes = {name: canonical_json_bytes(payload) for name, payload in payloads.items()}
    artifact_hashes = {name: sha256_bytes(content) for name, content in artifact_bytes.items()}
    manifest = {
        **_header("ref45_manifest"),
        "artifacts": {
            name: {"bytes": len(artifact_bytes[name]), "sha256": artifact_hashes[name]}
            for name in sorted(artifact_bytes)
        },
        "canonical_serialization": canonical_serialization_contract(),
        "counts": dict(EXPECTED_COUNTS),
        "generator_version": GENERATOR_VERSION,
        "source_packages": {
            key: {"filename": SOURCE_FILES[key][0], "sha256": source_hashes[key]}
            for key in sorted(SOURCE_FILES)
        },
    }
    manifest_bytes = canonical_json_bytes(manifest)
    all_bytes = {**artifact_bytes, MANIFEST_FILENAME: manifest_bytes}
    target = output_root / ARTIFACT_SET_ID
    idempotent = _write_immutable_package(target, all_bytes)
    return Ref45BuildResult(
        artifact_set_id=ARTIFACT_SET_ID,
        output_dir=target,
        artifact_hashes=artifact_hashes,
        manifest_sha256=sha256_bytes(manifest_bytes),
        source_hashes=source_hashes,
        counts=EXPECTED_COUNTS,
        idempotent=idempotent,
    )


def load_ref45_source_package(reference_root: str | Path) -> tuple[dict[str, Any], dict[str, str]]:
    root = Path(reference_root)
    payloads: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for package_id, (filename, expected_hash) in SOURCE_FILES.items():
        path = root / filename
        if not path.is_file():
            raise Ref45BuildError(f"Missing approved source file: {filename}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise Ref45BuildError(f"Source hash mismatch for {filename}: {actual_hash}")
        hashes[package_id] = actual_hash
        if path.suffix.lower() == ".json":
            try:
                payloads[package_id] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise Ref45BuildError(f"Invalid JSON in {filename}: {exc.msg}") from exc
        else:
            payloads[package_id] = path.read_text(encoding="utf-8")
    return payloads, hashes


def build_legacy_compatibility(ref4: Mapping[str, Any]) -> dict[str, Any]:
    from app.services.material_normalization_rules import GENERAL_SYNONYMS, get_all_direction_rules
    from app.services.module1_source_profile_registry import CATEGORY_MAPPING

    actual: list[tuple[str, str, str, str]] = [
        ("general_synonym", "GLOBAL", raw, normalized)
        for raw, normalized in GENERAL_SYNONYMS.items()
    ]
    actual.extend(
        ("direction_synonym", rule.direction_code, raw, normalized)
        for rule in get_all_direction_rules()
        for raw, normalized in rule.synonyms.items()
    )
    actual.extend(
        ("source_category_mapping", material_type, raw, material_type)
        for material_type, aliases in CATEGORY_MAPPING.items()
        for raw in aliases
    )
    approved_by_key = {
        (
            item["source_rule_type"],
            item["scope"],
            item["raw_value"],
            item["legacy_normalized_value"],
        ): item
        for item in ref4["alias_rules"]
    }
    actual_set = set(actual)
    approved_set = set(approved_by_key)
    missing = sorted(actual_set - approved_set)
    extra = sorted(approved_set - actual_set)
    parity = [
        {
            "alias_rule_id": approved_by_key[item]["alias_rule_id"],
            "automatic_material_type_resolution_allowed": bool(
                approved_by_key[item]["automatic_material_type_resolution_allowed"]
            ),
            "legacy_normalized_value": item[3],
            "parity": "exact",
            "raw_value": item[2],
            "scope": item[1],
            "source_rule_type": item[0],
        }
        for item in sorted(actual)
        if item in approved_by_key
    ]
    return {
        "conflicts": [],
        "counts": {
            "approved_rules": len(approved_set),
            "exact_parity": len(parity),
            "legacy_rules": len(actual_set),
            "missing_from_approved": len(missing),
            "not_in_legacy": len(extra),
            "review_or_context": sum(not item["automatic_material_type_resolution_allowed"] for item in parity),
            "trusted": sum(item["automatic_material_type_resolution_allowed"] for item in parity),
        },
        "missing_from_approved": [_legacy_tuple_payload(item) for item in missing],
        "not_in_legacy": [_legacy_tuple_payload(item) for item in extra],
        "rules": sorted(parity, key=lambda item: item["alias_rule_id"]),
    }


def validate_ref45_runtime_artifacts(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    expected_names = set(ARTIFACT_FILENAMES) | {MANIFEST_FILENAME}
    actual_names = {item.name for item in root.iterdir() if item.is_file()} if root.is_dir() else set()
    if actual_names != expected_names:
        raise Ref45BuildError(f"Runtime artifact file set mismatch: {sorted(actual_names)}")
    manifest = _read_json(root / MANIFEST_FILENAME)
    if manifest.get("artifact_set_id") != ARTIFACT_SET_ID:
        raise Ref45BuildError("Runtime artifact set ID mismatch")
    if manifest.get("counts") != EXPECTED_COUNTS:
        raise Ref45BuildError("Runtime artifact counts mismatch")
    for name in ARTIFACT_FILENAMES:
        metadata = manifest["artifacts"].get(name)
        if not isinstance(metadata, dict) or metadata.get("sha256") != sha256_file(root / name):
            raise Ref45BuildError(f"Runtime artifact hash mismatch: {name}")
    return manifest


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def canonical_serialization_contract() -> dict[str, Any]:
    return {
        "bom": False,
        "encoding": "UTF-8",
        "ensure_ascii": False,
        "indent": 2,
        "line_ending": "LF",
        "sort_keys": True,
        "trailing_newline": True,
    }


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_source_content(
    reference_root: Path,
    ref4: Mapping[str, Any],
    ref5: Mapping[str, Any],
    correction: Mapping[str, Any],
    compatibility: Mapping[str, Any],
) -> None:
    if ref4.get("status") != "preliminary_approved" or ref5.get("status") != "preliminary_approved":
        raise Ref45BuildError("REF-4/REF-5 source status is not preliminary_approved")
    if correction.get("status") != "approved_correction" or not correction.get("approval", {}).get("approved_by_user"):
        raise Ref45BuildError("REF-4 correction record is not approved")
    aliases = ref4.get("alias_rules", [])
    profiles = ref4.get("material_type_profiles", [])
    substitutions = ref5.get("substitution_rules", [])
    counts = {
        "taxonomy_material_types": len(profiles),
        "ref4_alias_rules": len(aliases),
        "ref4_trusted_alias_rules": sum(bool(item.get("automatic_material_type_resolution_allowed")) for item in aliases),
        "ref4_review_rules": sum(not bool(item.get("automatic_material_type_resolution_allowed")) for item in aliases),
        "ref5_context_rules": len(ref5.get("context_compatibility_rules", [])),
        "ref5_substitution_rules": len(substitutions),
        "ref5_active_substitution_policies": sum(_active_substitution(item) for item in substitutions),
        "ref5_review_rules": len(ref5.get("review_queue", [])),
        "automatic_replacements": sum(bool(item.get("automatic_selection_allowed")) for item in substitutions),
        "work_material_mappings": int(ref5.get("validation", {}).get("work_material_mappings_created", -1)),
    }
    if counts != EXPECTED_COUNTS:
        raise Ref45BuildError(f"REF-4/REF-5 counts mismatch: {counts}")
    if len({item["alias_rule_id"] for item in aliases}) != len(aliases):
        raise Ref45BuildError("Duplicate REF-4 alias rule IDs")
    if compatibility["counts"]["exact_parity"] != 89 or compatibility["missing_from_approved"] or compatibility["not_in_legacy"]:
        raise Ref45BuildError("REF-4 does not have exact all-89 legacy parity")
    corrected = {item["alias_rule_id"]: item for item in aliases if item["alias_rule_id"] in {"legacy_alias_060", "legacy_alias_061", "legacy_alias_062"}}
    if set(corrected) != {"legacy_alias_060", "legacy_alias_061", "legacy_alias_062"}:
        raise Ref45BuildError("Corrected REF-4 rules are missing")
    for item in corrected.values():
        if (
            item.get("legacy_normalized_value") != "gypsum_board_regular"
            or item.get("scope") != "gypsum_board_regular"
            or item.get("classification") != "context_required"
            or item.get("status") != "review_required"
            or item.get("automatic_material_type_resolution_allowed") is not False
        ):
            raise Ref45BuildError("Corrected REF-4 rule policy mismatch")
    taxonomy = _read_json(reference_root / "ATOM_REF1_Material_Taxonomy_v2_PRELIMINARY_APPROVED.json")
    taxonomy_ids = {item["material_type_id"] for item in taxonomy.get("material_types", [])}
    ref4_targets = {target for item in aliases for target in item.get("target_material_type_ids", [])}
    if not ref4_targets <= taxonomy_ids:
        raise Ref45BuildError(f"Unknown REF-4 target IDs: {sorted(ref4_targets - taxonomy_ids)}")
    if ref4.get("normalization_policy", {}).get("automatic_alias_learning_from_match_decision") is not False:
        raise Ref45BuildError("Automatic alias learning must remain disabled")
    if any(item.get("automatic_fuzzy_matching_allowed") for item in profiles):
        raise Ref45BuildError("Fuzzy matching must remain disabled")
    if any(item.get("automatic_selection_allowed") or item.get("automatic_write_allowed") for item in substitutions):
        raise Ref45BuildError("Automatic REF-5 selection/write must remain disabled")


def _active_substitution(item: Mapping[str, Any]) -> bool:
    return item.get("status") in {"active_read_only_policy", "active_safety_guard"}


def _header(artifact_type: str) -> dict[str, Any]:
    return {
        "activation_scope": "approved_read_only_policy",
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_set_id": ARTIFACT_SET_ID,
        "artifact_type": artifact_type,
        "module2_execution_allowed": False,
        "module5_execution_allowed": False,
        "write_activation_allowed": False,
    }


def _legacy_tuple_payload(item: tuple[str, str, str, str]) -> dict[str, str]:
    return {
        "source_rule_type": item[0],
        "scope": item[1],
        "raw_value": item[2],
        "legacy_normalized_value": item[3],
    }


def _stable_item_key(item: Any) -> str:
    if isinstance(item, Mapping):
        for key in ("rule_id", "alias_rule_id", "raw_value", "material_type_id"):
            if item.get(key):
                return str(item[key])
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Ref45BuildError(f"Cannot read JSON {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Ref45BuildError(f"Expected object in {path.name}")
    return payload


def _write_immutable_package(target: Path, files: Mapping[str, bytes]) -> bool:
    if not re.fullmatch(r"ref45-runtime-v1-[0-9a-f]{12}", target.name):
        raise Ref45BuildError("Invalid REF-4/5 artifact set ID")
    if target.exists():
        existing = {item.name: item.read_bytes() for item in target.iterdir() if item.is_file()}
        if existing != dict(files):
            raise Ref45BuildError(f"Immutable runtime package already exists with different content: {target}")
        return True
    target.mkdir(parents=True, exist_ok=False)
    for name in sorted(files):
        (target / name).write_bytes(files[name])
    return False