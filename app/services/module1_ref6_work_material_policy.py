from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from app.config import settings
from app.services.module1_work_catalog import get_work_item


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
ARTIFACT_SET_ID = "ref6-runtime-v1-2256595bd388"
APPROVAL_ID = "ref6-activation-v1-2256595bd388"
DEFAULT_ARTIFACT_DIR = RUNTIME_REFERENCE_ROOT / ARTIFACT_SET_ID
DEFAULT_APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / APPROVAL_ID / "approval_manifest.json"
EXPECTED_MANIFEST_SHA256 = "40a4036ff6fa004d60d78432993343865fee19935d4cacdcf390d8f1604083b0"
EXPECTED_APPROVAL_SHA256 = "b9163fe3f6d79ea09cbd3f3928bae28295e16963bfa42559bff1aa865ac09d0c"
EXPECTED_ARTIFACT_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "conditional_role_hints.json": "64205efb68075acee986eb691c96a64e7b296500c5dfc84b6eaa056a8f5dbcfa",
        "consumer_contracts.json": "f96fd43193cfc48f850e72778fde2a8976b28f236e26f5aefb1825e8234c5f46",
        "legacy_material_role_evidence.json": "d3a7dc28183433a3aa50b9d1d735983f171b077bb0b69419dcbf621a7455fc2e",
        "no_material_works.json": "3d1629138de13ccda1b21e81bd2a3316e02fecb6129fc77c9c78017d47fc0876",
        "review_queue.json": "fd1488c9b855ecb48e4d242c533623cb46a5b287532392ed1e85981ff4c13315",
        "safe_role_hints.json": "fd6067238a785f2e4cc3734d1f989718d73b46ec90817d2d58374faacdb446f0",
        "work_profiles.json": "73079934bc906030a4c8fa98a8e835b337f334f5bb3d7cd0cb2fbae4095c5e8e",
    }
)
EXPECTED_COUNTS: Mapping[str, int] = MappingProxyType(
    {
        "automatic_database_write_rules": 0,
        "automatic_material_creation_rules": 0,
        "conditional_role_hints": 104,
        "conditional_works": 87,
        "direct_works": 80,
        "existing_material_role_evidence_rows": 42,
        "no_material_works": 39,
        "quantity_rules_activated": 0,
        "ref1_material_types": 978,
        "review_only_role_mappings": 7,
        "review_only_works": 3,
        "review_queue_items": 10,
        "role_mappings": 193,
        "safe_role_hints": 82,
        "sku_selection_rules": 0,
        "work_groups": 24,
        "works": 209,
    }
)
SUPPORTED_MODES = frozenset({"legacy", "approved"})


class Module1Ref6ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Module1Ref6Issue:
    code: str
    message: str


@dataclass(frozen=True)
class Ref6WorkMaterialHint:
    mapping_id: str
    work_code: str
    role_code: str
    role_kind: str
    target_material_type_ids: tuple[str, ...]
    conditions: tuple[str, ...]
    required_fields_policy: str
    execution_status: str
    type_hint_execution_allowed: bool
    quantity_calculation_allowed: bool = False
    ref3_formula_activation_allowed: bool = False
    sku_selection_allowed: bool = False
    catalog_product_selection_allowed: bool = False
    material_creation_allowed: bool = False
    database_write_allowed: bool = False
    module2_execution_allowed: bool = False
    module5_costing_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "catalog_product_selection_allowed": self.catalog_product_selection_allowed,
            "conditions": list(self.conditions),
            "database_write_allowed": self.database_write_allowed,
            "execution_status": self.execution_status,
            "mapping_id": self.mapping_id,
            "material_creation_allowed": self.material_creation_allowed,
            "module2_execution_allowed": self.module2_execution_allowed,
            "module5_costing_allowed": self.module5_costing_allowed,
            "quantity_calculation_allowed": self.quantity_calculation_allowed,
            "ref3_formula_activation_allowed": self.ref3_formula_activation_allowed,
            "required_fields_policy": self.required_fields_policy,
            "role_code": self.role_code,
            "role_kind": self.role_kind,
            "sku_selection_allowed": self.sku_selection_allowed,
            "target_material_type_ids": list(self.target_material_type_ids),
            "type_hint_execution_allowed": self.type_hint_execution_allowed,
            "work_code": self.work_code,
        }


@dataclass(frozen=True)
class Ref6WorkMaterialResolution:
    mode: str
    state: str
    work_code: str
    known_work: bool
    material_policy: str | None
    hints: tuple[Ref6WorkMaterialHint, ...]
    review_items: tuple[Mapping[str, Any], ...]
    no_material: bool
    context_received: bool
    quantity_calculation_allowed: bool = False
    ref3_formula_activation_allowed: bool = False
    sku_selection_allowed: bool = False
    catalog_product_selection_allowed: bool = False
    material_creation_allowed: bool = False
    database_write_allowed: bool = False
    module2_execution_allowed: bool = False
    module5_costing_allowed: bool = False
    warnings: tuple[str, ...] = tuple()

    def as_dict(self) -> dict[str, Any]:
        return {
            "catalog_product_selection_allowed": self.catalog_product_selection_allowed,
            "context_received": self.context_received,
            "database_write_allowed": self.database_write_allowed,
            "hints": [item.as_dict() for item in self.hints],
            "known_work": self.known_work,
            "material_creation_allowed": self.material_creation_allowed,
            "material_policy": self.material_policy,
            "mode": self.mode,
            "module2_execution_allowed": self.module2_execution_allowed,
            "module5_costing_allowed": self.module5_costing_allowed,
            "no_material": self.no_material,
            "quantity_calculation_allowed": self.quantity_calculation_allowed,
            "ref3_formula_activation_allowed": self.ref3_formula_activation_allowed,
            "review_items": [dict(item) for item in self.review_items],
            "sku_selection_allowed": self.sku_selection_allowed,
            "state": self.state,
            "warnings": list(self.warnings),
            "work_code": self.work_code,
        }


@dataclass(frozen=True)
class Module1Ref6Activation:
    mode: str
    is_valid: bool
    artifact_set_id: str | None
    approval_id: str | None
    manifest_sha256: str | None
    approval_sha256: str | None
    counts: Mapping[str, int]
    work_profiles: tuple[Mapping[str, Any], ...]
    safe_hints: tuple[Mapping[str, Any], ...]
    conditional_hints: tuple[Mapping[str, Any], ...]
    review_mappings: tuple[Mapping[str, Any], ...]
    review_items: tuple[Mapping[str, Any], ...]
    no_material_works: tuple[Mapping[str, Any], ...]
    legacy_evidence: tuple[Mapping[str, Any], ...]
    consumer_contracts: Mapping[str, Any]
    issues: tuple[Module1Ref6Issue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "approval_sha256": self.approval_sha256,
            "artifact_set_id": self.artifact_set_id,
            "counts": dict(self.counts),
            "database_write_allowed": False,
            "is_valid": self.is_valid,
            "issues": [{"code": item.code, "message": item.message} for item in self.issues],
            "manifest_sha256": self.manifest_sha256,
            "mode": self.mode,
            "module2_execution_allowed": False,
            "module5_costing_allowed": False,
            "quantity_calculation_allowed": False,
            "ref3_formula_activation_allowed": False,
            "write_activation_allowed": False,
        }


def validate_module1_ref6_runtime(
    mode: str | None = None,
    *,
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    approval_path: str | Path = DEFAULT_APPROVAL_PATH,
    allowed_root: str | Path = RUNTIME_REFERENCE_ROOT,
) -> Module1Ref6Activation:
    selected = str(mode if mode is not None else settings.MODULE1_REF6_MODE).strip().lower()
    if selected not in SUPPORTED_MODES:
        return _empty_activation(
            selected,
            (Module1Ref6Issue("MODE_UNSUPPORTED", f"Unsupported MODULE1_REF6_MODE: {selected}"),),
        )
    if selected == "legacy":
        return _empty_activation("legacy", tuple(), is_valid=True)
    issues: list[Module1Ref6Issue] = []
    try:
        artifact = _confined_path(Path(artifact_dir), Path(allowed_root))
        approval = _confined_path(Path(approval_path), Path(allowed_root))
    except Module1Ref6ConfigurationError as exc:
        return _empty_activation(selected, (Module1Ref6Issue("PATH_INVALID", str(exc)),))
    manifest_hash = _verify_hash(
        artifact / "manifest.json", EXPECTED_MANIFEST_SHA256, "MANIFEST", issues
    )
    approval_hash = _verify_hash(approval, EXPECTED_APPROVAL_SHA256, "APPROVAL", issues)
    manifest = _read_json(artifact / "manifest.json", "MANIFEST", issues)
    approval_payload = _read_json(approval, "APPROVAL", issues)
    _validate_manifest(manifest, issues)
    _validate_approval(approval_payload, manifest_hash, issues)
    payloads = {
        name: _read_json(artifact / name, name.removesuffix(".json").upper(), issues)
        for name in EXPECTED_ARTIFACT_HASHES
    }
    for name, expected_hash in EXPECTED_ARTIFACT_HASHES.items():
        _verify_hash(artifact / name, expected_hash, "ARTIFACT", issues)
    work_profiles = _items(payloads["work_profiles.json"])
    safe_hints = _items(payloads["safe_role_hints.json"])
    conditional_hints = _items(payloads["conditional_role_hints.json"])
    review_payload = payloads["review_queue.json"]
    review_items = _items(review_payload)
    review_mappings = tuple(
        _readonly(item) for item in review_payload.get("mapping_items", []) if isinstance(item, dict)
    )
    no_material = _items(payloads["no_material_works.json"])
    evidence = _items(payloads["legacy_material_role_evidence.json"])
    if (
        len(work_profiles) != 209
        or len(safe_hints) != 82
        or len(conditional_hints) != 104
        or len(review_items) != 10
        or len(review_mappings) != 7
        or len(no_material) != 39
        or len(evidence) != 42
    ):
        issues.append(Module1Ref6Issue("ARTIFACT_COUNTS_INVALID", "REF-6 artifact item counts differ"))
    return Module1Ref6Activation(
        mode=selected,
        is_valid=not issues,
        artifact_set_id=ARTIFACT_SET_ID,
        approval_id=APPROVAL_ID,
        manifest_sha256=manifest_hash,
        approval_sha256=approval_hash,
        counts=MappingProxyType(dict(manifest.get("counts") or {})),
        work_profiles=work_profiles,
        safe_hints=safe_hints,
        conditional_hints=conditional_hints,
        review_mappings=review_mappings,
        review_items=review_items,
        no_material_works=no_material,
        legacy_evidence=evidence,
        consumer_contracts=_readonly(payloads["consumer_contracts.json"]),
        issues=tuple(issues),
    )


def require_module1_ref6_runtime(mode: str | None = None) -> Module1Ref6Activation:
    activation = validate_module1_ref6_runtime(mode)
    if not activation.is_valid:
        detail = "; ".join(f"{item.code}: {item.message}" for item in activation.issues)
        raise Module1Ref6ConfigurationError(detail)
    return activation


def resolve_work_material_hints(
    work_code: str,
    context: Mapping[str, Any] | None = None,
    *,
    mode: str | None = None,
) -> Ref6WorkMaterialResolution:
    selected = str(mode if mode is not None else settings.MODULE1_REF6_MODE).strip().lower()
    normalized_code = str(work_code or "").strip()
    if selected == "legacy":
        known = get_work_item(normalized_code) is not None
        return _resolution(
            mode="legacy",
            state="legacy" if known else "unknown_work",
            work_code=normalized_code,
            known_work=known,
            context=context,
            warnings=tuple() if known else ("Unknown work code; no material hint returned.",),
        )
    activation = require_module1_ref6_runtime(selected)
    profile = next(
        (item for item in activation.work_profiles if item.get("work_code") == normalized_code),
        None,
    )
    if profile is None:
        return _resolution(
            mode=selected,
            state="unknown_work",
            work_code=normalized_code,
            known_work=False,
            context=context,
            warnings=("Unknown work code; REF-6 fails closed.",),
        )
    policy = str(profile.get("material_policy") or "")
    safe = tuple(item for item in activation.safe_hints if item.get("work_code") == normalized_code)
    conditional = tuple(
        item for item in activation.conditional_hints if item.get("work_code") == normalized_code
    )
    review_mappings = tuple(
        item for item in activation.review_mappings if item.get("work_code") == normalized_code
    )
    review_items = tuple(
        item for item in activation.review_items if item.get("work_code") == normalized_code
    )
    if policy == "NO_MATERIAL":
        state = "no_material"
        rows: tuple[Mapping[str, Any], ...] = tuple()
        warnings = ("Work explicitly requires no material role.",)
    elif safe:
        state = "safe_hints"
        rows = safe
        warnings = ("Type-level role hints only; quantity and SKU selection are disabled.",)
    elif conditional:
        state = "conditional_hints"
        rows = conditional
        warnings = ("Conditional hints require Module 2 context and are not executable here.",)
    else:
        state = "review_required"
        rows = review_mappings
        warnings = ("REF-6 work or mapping requires expert review.",)
    hints = tuple(_hint_from_payload(item) for item in rows)
    return _resolution(
        mode=selected,
        state=state,
        work_code=normalized_code,
        known_work=True,
        material_policy=policy,
        hints=hints,
        review_items=review_items,
        no_material=policy == "NO_MATERIAL",
        context=context,
        warnings=warnings,
    )


def build_work_material_consumer_contract(
    work_code: str,
    context: Mapping[str, Any] | None = None,
    *,
    mode: str | None = None,
) -> dict[str, Any]:
    result = resolve_work_material_hints(work_code, context, mode=mode)
    return {
        "consumer_contract_version": "module1.ref6.work_material_hints.v1",
        "module1_output": result.as_dict(),
        "ownership": {
            "module1": "role_type_conditions_restrictions",
            "module2": "technology_geometry_volume_quantity",
            "module5": "price_packaging_rounding_estimate",
        },
        "price_data_included": False,
        "resolved_material_requirement": False,
        "side_effects": False,
    }


def _hint_from_payload(payload: Mapping[str, Any]) -> Ref6WorkMaterialHint:
    return Ref6WorkMaterialHint(
        mapping_id=str(payload.get("mapping_id") or ""),
        work_code=str(payload.get("work_code") or ""),
        role_code=str(payload.get("role_code") or ""),
        role_kind=str(payload.get("role_kind") or ""),
        target_material_type_ids=tuple(str(item) for item in payload.get("target_material_type_ids", [])),
        conditions=tuple(str(item) for item in payload.get("conditions", [])),
        required_fields_policy=str(payload.get("required_fields_policy") or ""),
        execution_status=str(payload.get("execution_status") or ""),
        type_hint_execution_allowed=payload.get("execution_status") == "SAFE_HINT",
    )


def _resolution(
    *,
    mode: str,
    state: str,
    work_code: str,
    known_work: bool,
    context: Mapping[str, Any] | None,
    material_policy: str | None = None,
    hints: tuple[Ref6WorkMaterialHint, ...] = tuple(),
    review_items: tuple[Mapping[str, Any], ...] = tuple(),
    no_material: bool = False,
    warnings: tuple[str, ...] = tuple(),
) -> Ref6WorkMaterialResolution:
    return Ref6WorkMaterialResolution(
        mode=mode,
        state=state,
        work_code=work_code,
        known_work=known_work,
        material_policy=material_policy,
        hints=hints,
        review_items=review_items,
        no_material=no_material,
        context_received=bool(context),
        warnings=warnings,
    )


def _empty_activation(
    mode: str,
    issues: tuple[Module1Ref6Issue, ...],
    *,
    is_valid: bool = False,
) -> Module1Ref6Activation:
    return Module1Ref6Activation(
        mode=mode,
        is_valid=is_valid,
        artifact_set_id=None,
        approval_id=None,
        manifest_sha256=None,
        approval_sha256=None,
        counts=MappingProxyType({}),
        work_profiles=tuple(),
        safe_hints=tuple(),
        conditional_hints=tuple(),
        review_mappings=tuple(),
        review_items=tuple(),
        no_material_works=tuple(),
        legacy_evidence=tuple(),
        consumer_contracts=MappingProxyType({}),
        issues=issues,
    )


def _validate_manifest(payload: Mapping[str, Any], issues: list[Module1Ref6Issue]) -> None:
    checks = (
        (payload.get("artifact_set_id") == ARTIFACT_SET_ID, "MANIFEST_ID_INVALID"),
        (payload.get("counts") == dict(EXPECTED_COUNTS), "MANIFEST_COUNTS_INVALID"),
        (payload.get("write_activation_allowed") is False, "MANIFEST_WRITE_INVALID"),
        (payload.get("quantity_calculation_allowed") is False, "MANIFEST_QUANTITY_INVALID"),
        (payload.get("ref3_formula_activation_allowed") is False, "MANIFEST_REF3_INVALID"),
    )
    for valid, code in checks:
        if not valid:
            issues.append(Module1Ref6Issue(code, "REF-6 runtime manifest contract mismatch"))
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}
    for name, expected in EXPECTED_ARTIFACT_HASHES.items():
        if artifacts.get(name, {}).get("sha256") != expected:
            issues.append(Module1Ref6Issue("MANIFEST_ARTIFACT_HASH_INVALID", name))


def _validate_approval(
    payload: Mapping[str, Any],
    manifest_sha256: str | None,
    issues: list[Module1Ref6Issue],
) -> None:
    flags = payload.get("activation_flags") if isinstance(payload.get("activation_flags"), dict) else {}
    checks = (
        (payload.get("approval_id") == APPROVAL_ID, "APPROVAL_ID_INVALID"),
        (payload.get("decision_number") == 41, "APPROVAL_DECISION_INVALID"),
        (payload.get("approved_modes") == ["approved"], "APPROVAL_MODE_INVALID"),
        (
            payload.get("approved_scope") == "module1_ref6_governed_work_material_hints",
            "APPROVAL_SCOPE_INVALID",
        ),
        (payload.get("counts") == dict(EXPECTED_COUNTS), "APPROVAL_COUNTS_INVALID"),
        (
            payload.get("runtime_artifact", {}).get("manifest_sha256") == manifest_sha256,
            "APPROVAL_MANIFEST_INVALID",
        ),
        (flags.get("safe_role_hint_execution_as_type_hint_allowed") is True, "APPROVAL_SAFE_INVALID"),
        (flags.get("conditional_hint_execution_allowed") is False, "APPROVAL_CONDITIONAL_INVALID"),
        (flags.get("quantity_calculation_allowed") is False, "APPROVAL_QUANTITY_INVALID"),
        (flags.get("database_write_allowed") is False, "APPROVAL_WRITE_INVALID"),
    )
    for valid, code in checks:
        if not valid:
            issues.append(Module1Ref6Issue(code, "REF-6 approval contract mismatch"))


def _verify_hash(
    path: Path,
    expected: str,
    prefix: str,
    issues: list[Module1Ref6Issue],
) -> str | None:
    if not path.is_file():
        issues.append(Module1Ref6Issue(f"{prefix}_MISSING", path.name))
        return None
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        issues.append(Module1Ref6Issue(f"{prefix}_HASH_INVALID", path.name))
    return actual


def _read_json(
    path: Path,
    prefix: str,
    issues: list[Module1Ref6Issue],
) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(Module1Ref6Issue(f"{prefix}_JSON_INVALID", str(exc)))
        return {}
    if not isinstance(payload, dict):
        issues.append(Module1Ref6Issue(f"{prefix}_TYPE_INVALID", "Expected JSON object"))
        return {}
    return payload


def _items(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(_readonly(item) for item in payload.get("items", []) if isinstance(item, dict))


def _readonly(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(payload))


def _confined_path(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    allowed = root.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise Module1Ref6ConfigurationError(f"REF-6 path escapes runtime root: {resolved}")
    return resolved
