from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.config import settings
from app.services.module1_ref4_normalization_policy import require_module1_ref45_runtime


ACTIVE_STATUSES = frozenset({"active_read_only_policy", "active_safety_guard"})


@dataclass(frozen=True)
class Ref5CompatibilityResult:
    state: str
    relation_id: str | None
    relation_type: str | None
    source_material_type_id: str
    target_material_type_id: str
    allowed_as_candidate: bool
    automatic_selection_allowed: bool
    automatic_write_allowed: bool
    execution_allowed: bool
    missing_fields: tuple[str, ...]
    conflicting_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    policy: Mapping[str, Any] | None = None


def list_ref5_context_rules(*, mode: str | None = None) -> tuple[Mapping[str, Any], ...]:
    selected_mode = str(mode if mode is not None else settings.MODULE1_REF45_MODE).strip().lower()
    if selected_mode == "legacy":
        return tuple()
    return require_module1_ref45_runtime(selected_mode).context_rules


def list_ref5_substitution_policies(
    *,
    include_review: bool = True,
    mode: str | None = None,
) -> tuple[Mapping[str, Any], ...]:
    selected_mode = str(mode if mode is not None else settings.MODULE1_REF45_MODE).strip().lower()
    if selected_mode == "legacy":
        return tuple()
    rules = require_module1_ref45_runtime(selected_mode).substitution_rules
    if include_review:
        return rules
    return tuple(item for item in rules if item.get("status") in ACTIVE_STATUSES)


def evaluate_ref5_compatibility(
    source_material_type_id: str,
    target_material_type_id: str,
    *,
    source_characteristics: Mapping[str, Any] | None = None,
    target_characteristics: Mapping[str, Any] | None = None,
    source_unit: str | None = None,
    target_unit: str | None = None,
    mode: str | None = None,
) -> Ref5CompatibilityResult:
    source_type = str(source_material_type_id or "").strip()
    target_type = str(target_material_type_id or "").strip()
    rules = list_ref5_substitution_policies(include_review=True, mode=mode)
    matching = [
        item
        for item in rules
        if item.get("source_material_type_id") == source_type
        and item.get("target_material_type_id") == target_type
    ]
    if not matching:
        return _result("unknown", source_type, target_type)
    rule = matching[0]
    relation_id = str(rule.get("relation_id") or "") or None
    relation_type = str(rule.get("relation_type") or "") or None
    status = str(rule.get("status") or "")
    if status not in ACTIVE_STATUSES:
        return _result(
            "review_required",
            source_type,
            target_type,
            relation_id=relation_id,
            relation_type=relation_type,
            policy=rule,
            warnings=("REF-5 relation remains review-only.",),
        )
    if relation_type == "forbidden_replacement":
        return _result(
            "forbidden",
            source_type,
            target_type,
            relation_id=relation_id,
            relation_type=relation_type,
            policy=rule,
            warnings=("REF-5 safety guard forbids this replacement.",),
        )

    source = dict(source_characteristics or {})
    target = dict(target_characteristics or {})
    required = tuple(str(item) for item in rule.get("required_matching_field_codes", ()))
    missing = tuple(
        field
        for field in required
        if _is_missing(source.get(field)) or _is_missing(target.get(field))
    )
    conflicts = tuple(
        field
        for field in required
        if field not in missing and _normalized(source.get(field)) != _normalized(target.get(field))
    )
    unit_missing = bool(source_unit) != bool(target_unit)
    unit_conflict = bool(source_unit and target_unit and _normalized(source_unit) != _normalized(target_unit))
    if unit_missing:
        missing = tuple(dict.fromkeys((*missing, "unit")))
    if unit_conflict:
        conflicts = tuple(dict.fromkeys((*conflicts, "unit")))
    if missing or conflicts:
        warnings = []
        if missing:
            warnings.append("Required technical fields are missing.")
        if conflicts:
            warnings.append("Required technical fields or units differ.")
        return _result(
            "review_required",
            source_type,
            target_type,
            relation_id=relation_id,
            relation_type=relation_type,
            policy=rule,
            missing=missing,
            conflicts=conflicts,
            warnings=tuple(warnings),
        )
    if relation_type == "full_analog" and source_type != target_type:
        return _result(
            "review_required",
            source_type,
            target_type,
            relation_id=relation_id,
            relation_type=relation_type,
            policy=rule,
            warnings=("Full analog requires the same material type.",),
        )
    state = "full_analog_candidate" if relation_type == "full_analog" else "read_only_policy"
    return _result(
        state,
        source_type,
        target_type,
        relation_id=relation_id,
        relation_type=relation_type,
        policy=rule,
        allowed_as_candidate=True,
        warnings=("Policy is read-only; automatic replacement is disabled.",),
    )


def _result(
    state: str,
    source: str,
    target: str,
    *,
    relation_id: str | None = None,
    relation_type: str | None = None,
    policy: Mapping[str, Any] | None = None,
    allowed_as_candidate: bool = False,
    missing: tuple[str, ...] = tuple(),
    conflicts: tuple[str, ...] = tuple(),
    warnings: tuple[str, ...] = tuple(),
) -> Ref5CompatibilityResult:
    return Ref5CompatibilityResult(
        state=state,
        relation_id=relation_id,
        relation_type=relation_type,
        source_material_type_id=source,
        target_material_type_id=target,
        allowed_as_candidate=allowed_as_candidate,
        automatic_selection_allowed=False,
        automatic_write_allowed=False,
        execution_allowed=False,
        missing_fields=missing,
        conflicting_fields=conflicts,
        warnings=warnings,
        policy=policy,
    )


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _normalized(value: Any) -> str:
    return str(value).strip().casefold()