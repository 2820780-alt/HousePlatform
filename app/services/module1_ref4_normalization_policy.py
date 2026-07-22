from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping
import unicodedata

from app.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
ARTIFACT_SET_ID = "ref45-runtime-v1-5fe5e067d0dd"
APPROVAL_ID = "ref45-activation-v1-5fe5e067d0dd"
DEFAULT_ARTIFACT_DIR = RUNTIME_REFERENCE_ROOT / ARTIFACT_SET_ID
DEFAULT_APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / APPROVAL_ID / "approval_manifest.json"
EXPECTED_MANIFEST_SHA256 = "f5d385e8cf6b7e4847ee7b6d7e5f243671ac6472914e3c0f2e093e860b58b3dc"
EXPECTED_APPROVAL_SHA256 = "2f14e03b9dc42e978769a53f99b22bd0258e36c783c8aa47e1813ad855964a9a"
EXPECTED_ARTIFACT_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "legacy_compatibility.json": "96a272b73f62427433ef5bd0b4d01e561805b05041facf20c79e12a27cb79c00",
        "ref4_alias_rules.json": "a1abb52976bd1d3abe9792d34583b191dce5fe8988a8c8f2de7ac1202f820fd4",
        "ref4_material_type_profiles.json": "4a7f8fc50738182748f14b417f4a9b7a5217540ac409a2d2a99f6dba6752c6fc",
        "ref4_normalization_policy.json": "e887ae76afafe1deb25f14f837a58cf8f09c61784d2e7d45761580d2a5561248",
        "ref5_context_compatibility.json": "9af0344b891f3a904b247f96d29c19f0a2d90373ca1da00e0a9280884c7aa9d7",
        "ref5_substitution_policies.json": "47f5eea2c7f0687dc90381907cf0479eaf2aeab8a24c57b992482169bb433a30",
        "review_queue.json": "eacf483504748561d8c5caf3e9eb803e40a7eb43bfa62a78cbb24acac2774fde",
    }
)
SUPPORTED_MODES = frozenset({"legacy", "approved"})
EXPECTED_COUNTS = MappingProxyType(
    {
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
)


class Module1Ref45ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Module1Ref45Issue:
    code: str
    message: str


@dataclass(frozen=True)
class Module1Ref45Activation:
    mode: str
    is_valid: bool
    artifact_set_id: str | None
    approval_id: str | None
    manifest_sha256: str | None
    approval_sha256: str | None
    counts: Mapping[str, int]
    alias_rules: tuple[Mapping[str, Any], ...]
    material_type_profiles: tuple[Mapping[str, Any], ...]
    normalization_policy: Mapping[str, Any]
    context_rules: tuple[Mapping[str, Any], ...]
    substitution_rules: tuple[Mapping[str, Any], ...]
    review_queue: Mapping[str, Any]
    issues: tuple[Module1Ref45Issue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "approval_sha256": self.approval_sha256,
            "artifact_set_id": self.artifact_set_id,
            "counts": dict(self.counts),
            "is_valid": self.is_valid,
            "issues": [{"code": issue.code, "message": issue.message} for issue in self.issues],
            "manifest_sha256": self.manifest_sha256,
            "mode": self.mode,
            "read_only": True,
            "write_activation_allowed": False,
        }


@dataclass(frozen=True)
class Ref4AliasResolution:
    state: str
    input_value: str
    normalized_input: str
    alias_rule_id: str | None = None
    material_type_id: str | None = None
    legacy_normalized_value: str | None = None
    scope: str | None = None
    candidate_material_type_ids: tuple[str, ...] = tuple()
    automatic_resolution_allowed: bool = False
    preserve_dimensions_and_grade_tokens: bool = True


_EMPTY_ACTIVATION = Module1Ref45Activation(
    mode="legacy",
    is_valid=True,
    artifact_set_id=None,
    approval_id=None,
    manifest_sha256=None,
    approval_sha256=None,
    counts=MappingProxyType({}),
    alias_rules=tuple(),
    material_type_profiles=tuple(),
    normalization_policy=MappingProxyType({}),
    context_rules=tuple(),
    substitution_rules=tuple(),
    review_queue=MappingProxyType({}),
    issues=tuple(),
)


def validate_module1_ref45_runtime(
    mode: str | None = None,
    *,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    approval_path: str | Path = DEFAULT_APPROVAL_PATH,
    allowed_root: str | Path = RUNTIME_REFERENCE_ROOT,
) -> Module1Ref45Activation:
    normalized_mode = str(mode if mode is not None else settings.MODULE1_REF45_MODE).strip().lower()
    if normalized_mode not in SUPPORTED_MODES:
        raise Module1Ref45ConfigurationError(
            f"Unsupported MODULE1_REF45_MODE={normalized_mode!r}; expected legacy or approved"
        )
    if normalized_mode == "legacy":
        return _EMPTY_ACTIVATION

    confinement_root = Path(allowed_root)
    artifact_dir = _confined_path(Path(artifact_dir), confinement_root)
    approval_path = _confined_path(Path(approval_path), confinement_root)
    issues: list[Module1Ref45Issue] = []
    manifest_path = artifact_dir / "manifest.json"
    manifest_sha256 = _verify_hash(manifest_path, EXPECTED_MANIFEST_SHA256, "MANIFEST", issues)
    approval_sha256 = _verify_hash(approval_path, EXPECTED_APPROVAL_SHA256, "APPROVAL", issues)
    manifest = _read_json(manifest_path, "MANIFEST", issues)
    approval = _read_json(approval_path, "APPROVAL", issues)

    artifact_payloads: dict[str, dict[str, Any]] = {}
    for name, expected_hash in EXPECTED_ARTIFACT_HASHES.items():
        path = artifact_dir / name
        _verify_hash(path, expected_hash, f"ARTIFACT_{name}", issues)
        artifact_payloads[name] = _read_json(path, f"ARTIFACT_{name}", issues)

    _validate_manifest(manifest, issues)
    _validate_approval(approval, manifest_sha256, issues)
    if issues:
        return Module1Ref45Activation(
            mode=normalized_mode,
            is_valid=False,
            artifact_set_id=manifest.get("artifact_set_id") if manifest else None,
            approval_id=approval.get("approval_id") if approval else None,
            manifest_sha256=manifest_sha256,
            approval_sha256=approval_sha256,
            counts=MappingProxyType({}),
            alias_rules=tuple(),
            material_type_profiles=tuple(),
            normalization_policy=MappingProxyType({}),
            context_rules=tuple(),
            substitution_rules=tuple(),
            review_queue=MappingProxyType({}),
            issues=tuple(issues),
        )

    alias_payload = artifact_payloads["ref4_alias_rules.json"]
    profile_payload = artifact_payloads["ref4_material_type_profiles.json"]
    policy_payload = artifact_payloads["ref4_normalization_policy.json"]
    context_payload = artifact_payloads["ref5_context_compatibility.json"]
    substitution_payload = artifact_payloads["ref5_substitution_policies.json"]
    review_payload = artifact_payloads["review_queue.json"]
    return Module1Ref45Activation(
        mode=normalized_mode,
        is_valid=True,
        artifact_set_id=ARTIFACT_SET_ID,
        approval_id=APPROVAL_ID,
        manifest_sha256=manifest_sha256,
        approval_sha256=approval_sha256,
        counts=MappingProxyType(dict(EXPECTED_COUNTS)),
        alias_rules=tuple(MappingProxyType(dict(item)) for item in alias_payload["rules"]),
        material_type_profiles=tuple(MappingProxyType(dict(item)) for item in profile_payload["profiles"]),
        normalization_policy=MappingProxyType(dict(policy_payload["normalization_policy"])),
        context_rules=tuple(MappingProxyType(dict(item)) for item in context_payload["rules"]),
        substitution_rules=tuple(MappingProxyType(dict(item)) for item in substitution_payload["rules"]),
        review_queue=MappingProxyType(dict(review_payload)),
        issues=tuple(),
    )


def require_module1_ref45_runtime(mode: str | None = None) -> Module1Ref45Activation:
    selected = str(mode if mode is not None else settings.MODULE1_REF45_MODE).strip().lower()
    activation = _load_default_module1_ref45_runtime(selected)
    if not activation.is_valid:
        detail = "; ".join(f"{issue.code}: {issue.message}" for issue in activation.issues)
        raise Module1Ref45ConfigurationError(f"REF-4/5 approved mode validation failed: {detail}")
    return activation


@lru_cache(maxsize=2)
def _load_default_module1_ref45_runtime(mode: str) -> Module1Ref45Activation:
    return validate_module1_ref45_runtime(mode)


def clear_module1_ref45_runtime_cache() -> None:
    _load_default_module1_ref45_runtime.cache_clear()


def resolve_ref4_alias(
    value: str | None,
    *,
    scope: str | None = None,
    mode: str | None = None,
) -> Ref4AliasResolution:
    raw = str(value or "")
    normalized = _normalize(raw)
    selected_mode = str(mode if mode is not None else settings.MODULE1_REF45_MODE).strip().lower()
    if selected_mode == "legacy":
        return Ref4AliasResolution("unknown", raw, normalized)
    activation = require_module1_ref45_runtime(selected_mode)
    matches = [item for item in activation.alias_rules if _alias_matches(normalized, _normalize(str(item["raw_value"])))]
    if not matches:
        return Ref4AliasResolution("unknown", raw, normalized)
    matches.sort(key=lambda item: _rule_priority(item, scope))
    rule = matches[0]
    candidates = tuple(str(item) for item in rule.get("target_material_type_ids", ()))
    automatic = bool(rule.get("automatic_material_type_resolution_allowed"))
    classification = str(rule.get("classification") or "")
    rule_scope = str(rule.get("scope") or "")
    if automatic and classification == "trusted_global" and len(candidates) == 1:
        state = "trusted_match"
        material_type_id = candidates[0]
    elif automatic and classification == "trusted_scoped" and scope == rule_scope and len(candidates) == 1:
        state = "scoped_trusted_match"
        material_type_id = candidates[0]
    elif classification == "context_required" or (automatic and classification == "trusted_scoped"):
        state = "context_required"
        material_type_id = None
        automatic = False
    else:
        state = "review_required"
        material_type_id = None
        automatic = False
    return Ref4AliasResolution(
        state=state,
        input_value=raw,
        normalized_input=normalized,
        alias_rule_id=str(rule.get("alias_rule_id")),
        material_type_id=material_type_id,
        legacy_normalized_value=str(rule.get("legacy_normalized_value") or "") or None,
        scope=rule_scope or None,
        candidate_material_type_ids=candidates,
        automatic_resolution_allowed=automatic,
        preserve_dimensions_and_grade_tokens=bool(rule.get("preserve_dimensions_and_grade_tokens", True)),
    )


def _rule_priority(rule: Mapping[str, Any], scope: str | None) -> tuple[int, int, str]:
    rule_scope = str(rule.get("scope") or "")
    classification = str(rule.get("classification") or "")
    if scope and rule_scope == scope:
        scope_rank = 0
    elif rule_scope == "GLOBAL":
        scope_rank = 1
    else:
        scope_rank = 2
    class_rank = {"trusted_scoped": 0, "trusted_global": 1, "context_required": 2, "text_normalization_only": 3}.get(classification, 4)
    return scope_rank, class_rank, str(rule.get("alias_rule_id") or "")


def _alias_matches(text: str, alias: str) -> bool:
    if not alias:
        return False
    return re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, flags=re.UNICODE) is not None


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _validate_manifest(payload: Mapping[str, Any], issues: list[Module1Ref45Issue]) -> None:
    checks = (
        (payload.get("artifact_set_id") == ARTIFACT_SET_ID, "MANIFEST_ID_INVALID"),
        (payload.get("counts") == dict(EXPECTED_COUNTS), "MANIFEST_COUNTS_INVALID"),
        (payload.get("write_activation_allowed") is False, "MANIFEST_WRITE_FLAG_INVALID"),
    )
    for valid, code in checks:
        if not valid:
            issues.append(Module1Ref45Issue(code, "REF-4/5 runtime manifest contract mismatch"))
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    for name, expected_hash in EXPECTED_ARTIFACT_HASHES.items():
        if artifacts.get(name, {}).get("sha256") != expected_hash:
            issues.append(Module1Ref45Issue("MANIFEST_ARTIFACT_HASH_INVALID", name))


def _validate_approval(
    payload: Mapping[str, Any],
    manifest_sha256: str | None,
    issues: list[Module1Ref45Issue],
) -> None:
    checks = (
        (payload.get("approval_id") == APPROVAL_ID, "APPROVAL_ID_INVALID"),
        (payload.get("decision_number") == 40, "APPROVAL_DECISION_INVALID"),
        (payload.get("approved_modes") == ["approved"], "APPROVAL_MODE_INVALID"),
        (payload.get("approved_scope") == "module1_ref4_ref5_governed_policy", "APPROVAL_SCOPE_INVALID"),
        (payload.get("counts") == dict(EXPECTED_COUNTS), "APPROVAL_COUNTS_INVALID"),
        (payload.get("runtime_artifact", {}).get("package_id") == ARTIFACT_SET_ID, "APPROVAL_ARTIFACT_ID_INVALID"),
        (payload.get("runtime_artifact", {}).get("manifest_sha256") == manifest_sha256, "APPROVAL_MANIFEST_HASH_INVALID"),
        (payload.get("activation_flags", {}).get("write_activation_allowed") is False, "APPROVAL_WRITE_FLAG_INVALID"),
        (payload.get("activation_flags", {}).get("automatic_replacement_allowed") is False, "APPROVAL_REPLACEMENT_FLAG_INVALID"),
    )
    for valid, code in checks:
        if not valid:
            issues.append(Module1Ref45Issue(code, "REF-4/5 approval contract mismatch"))


def _verify_hash(
    path: Path,
    expected: str,
    code_prefix: str,
    issues: list[Module1Ref45Issue],
) -> str | None:
    if not path.is_file():
        issues.append(Module1Ref45Issue(f"{code_prefix}_MISSING", str(path.name)))
        return None
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        issues.append(Module1Ref45Issue(f"{code_prefix}_HASH_INVALID", str(path.name)))
    return actual


def _read_json(path: Path, code_prefix: str, issues: list[Module1Ref45Issue]) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(Module1Ref45Issue(f"{code_prefix}_JSON_INVALID", str(exc)))
        return {}
    if not isinstance(payload, dict):
        issues.append(Module1Ref45Issue(f"{code_prefix}_TYPE_INVALID", "Expected JSON object"))
        return {}
    return payload


def _confined_path(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    allowed = root.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise Module1Ref45ConfigurationError(f"REF-4/5 path escapes runtime root: {resolved}")
    return resolved