from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping

from app.services.module1_matching_dedup import DedupCandidateDTO, MaterialMatchCandidateDTO


DECISION_TYPES: tuple[str, ...] = (
    "accept_match",
    "reject_match",
    "create_new_material_candidate",
    "mark_possible_duplicate",
    "request_more_data",
    "defer",
    "archive_candidate",
    "flag_quality_issue",
)

CONFIRMATION_REQUIRED_DECISIONS = frozenset(
    {
        "accept_match",
        "create_new_material_candidate",
        "mark_possible_duplicate",
        "archive_candidate",
        "flag_quality_issue",
    }
)


@dataclass(frozen=True)
class MaterialModerationQueueItem:
    queue_item_id: str
    source_candidate_id: str
    source_candidate_type: str
    queue_type: str
    priority: str
    reason: str
    normalized_candidate_snapshot: Mapping[str, Any]
    matched_material_reference: Mapping[str, Any] | None
    related_candidate_snapshot: Mapping[str, Any] | None
    confidence: Decimal
    decision_hint: str
    explanation: tuple[str, ...]
    missing_fields: tuple[str, ...]
    conflicting_fields: tuple[str, ...]
    evidence_refs: Mapping[str, Any]
    source_refs: Mapping[str, Any]
    allowed_decisions: tuple[str, ...]
    blocked_decisions: tuple[Mapping[str, str], ...]


@dataclass(frozen=True)
class MaterialModerationDecision:
    decision_type: str
    moderator_id: str | None = None
    comment: str | None = None
    confirmed: bool = False
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ModerationDecisionValidation:
    is_valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    allowed_decisions: tuple[str, ...]
    blocked_decisions: tuple[Mapping[str, str], ...]


@dataclass(frozen=True)
class ModerationDecisionPlan:
    decision_type: str
    human_readable_summary: str
    affected_candidate: Mapping[str, Any]
    target_material_reference: Mapping[str, Any] | None
    required_manual_confirmation: bool
    operations_preview: tuple[str, ...]
    warnings: tuple[str, ...]
    no_side_effects: bool


@dataclass(frozen=True)
class ModerationQueueReport:
    total_items: int
    by_queue_type: Mapping[str, int]
    by_priority: Mapping[str, int]
    blocked_decision_count: int
    summary: Mapping[str, Any]


@dataclass(frozen=True)
class ModerationRuleSuggestion:
    suggestion_id: str
    source_queue_item_id: str
    rule_type: str
    title: str
    rationale: tuple[str, ...]
    conditions: Mapping[str, Any]
    action_preview: Mapping[str, Any]
    confidence: Decimal
    saved_automatically: bool


def build_moderation_queue_item(
    match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO,
) -> MaterialModerationQueueItem:
    candidate_type = _candidate_type(match_candidate)
    queue_type = classify_moderation_queue_type(match_candidate)
    priority = classify_moderation_priority(match_candidate)
    normalized_snapshot = _normalized_snapshot(match_candidate)
    matched_material_reference = _matched_material_reference(match_candidate)
    related_candidate_snapshot = _related_candidate_snapshot(match_candidate)
    missing_fields = _missing_fields(match_candidate)
    required_missing_fields = _required_missing_fields(match_candidate)
    conflicting_fields = _conflicting_fields(match_candidate)
    has_positive_price = _has_positive_price(match_candidate)
    allowed_decisions, blocked_decisions = _decision_policy(
        queue_type=queue_type,
        matched_material_reference=matched_material_reference,
        missing_fields=required_missing_fields,
        conflicting_fields=conflicting_fields,
        has_positive_price=has_positive_price,
    )
    return MaterialModerationQueueItem(
        queue_item_id=_stable_key("m1_moderation", _candidate_id(match_candidate), queue_type),
        source_candidate_id=_candidate_id(match_candidate),
        source_candidate_type=candidate_type,
        queue_type=queue_type,
        priority=priority,
        reason=_queue_reason(queue_type, match_candidate),
        normalized_candidate_snapshot=normalized_snapshot,
        matched_material_reference=matched_material_reference,
        related_candidate_snapshot=related_candidate_snapshot,
        confidence=_confidence(match_candidate),
        decision_hint=_decision_hint(match_candidate),
        explanation=_explanation(match_candidate),
        missing_fields=missing_fields,
        conflicting_fields=conflicting_fields,
        evidence_refs=_evidence_refs(match_candidate),
        source_refs=_source_refs(match_candidate),
        allowed_decisions=allowed_decisions,
        blocked_decisions=blocked_decisions,
    )


def build_moderation_queue(
    match_candidates: Iterable[MaterialMatchCandidateDTO | DedupCandidateDTO],
) -> tuple[MaterialModerationQueueItem, ...]:
    return tuple(build_moderation_queue_item(candidate) for candidate in match_candidates)


def classify_moderation_queue_type(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> str:
    if _required_missing_fields(match_candidate):
        return "missing_required_fields"
    if _conflicting_fields(match_candidate) or _decision_hint(match_candidate) == "possible_duplicate":
        return "possible_duplicate_review"
    if _decision_hint(match_candidate) == "exact_match":
        return "exact_match_review"
    if _decision_hint(match_candidate) == "strong_match":
        return "strong_match_review"
    if _confidence(match_candidate) < Decimal("70"):
        return "low_confidence_review"
    if _decision_hint(match_candidate) == "new_material_candidate":
        return "new_material_review"
    return "new_material_review"


def classify_moderation_priority(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> str:
    queue_type = classify_moderation_queue_type(match_candidate)
    confidence = _confidence(match_candidate)
    if queue_type == "missing_required_fields":
        return "critical"
    if queue_type == "possible_duplicate_review":
        return "high"
    if queue_type in {"exact_match_review", "strong_match_review"} or confidence >= Decimal("90"):
        return "high"
    if queue_type == "low_confidence_review":
        return "medium"
    return "low"


def validate_moderation_decision(
    queue_item: MaterialModerationQueueItem,
    decision: MaterialModerationDecision,
) -> ModerationDecisionValidation:
    errors: list[str] = []
    warnings: list[str] = []

    if decision.decision_type not in DECISION_TYPES:
        errors.append(f"Unsupported decision type: {decision.decision_type}")
    if decision.decision_type not in queue_item.allowed_decisions:
        errors.append(f"Decision is not allowed for queue type {queue_item.queue_type}: {decision.decision_type}")
    if decision.decision_type in CONFIRMATION_REQUIRED_DECISIONS and not decision.confirmed:
        errors.append(f"Decision requires explicit moderator confirmation: {decision.decision_type}")
    if decision.decision_type == "accept_match" and not queue_item.matched_material_reference:
        errors.append("accept_match requires an existing target material reference")
    if decision.decision_type == "request_more_data" and not queue_item.missing_fields:
        warnings.append("request_more_data is allowed, but the queue item has no missing fields")
    if decision.decision_type in {"reject_match", "flag_quality_issue"} and not decision.comment:
        warnings.append(f"{decision.decision_type} should include a moderator comment")

    return ModerationDecisionValidation(
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        allowed_decisions=queue_item.allowed_decisions,
        blocked_decisions=queue_item.blocked_decisions,
    )


def build_decision_plan(
    queue_item: MaterialModerationQueueItem,
    decision: MaterialModerationDecision,
) -> ModerationDecisionPlan:
    validation = validate_moderation_decision(queue_item, decision)
    if not validation.is_valid:
        raise ValueError("; ".join(validation.errors))

    summary, operations = _decision_operations(queue_item, decision)
    warnings = tuple(
        list(validation.warnings)
        + [
            "This plan is a moderation preview only.",
            "No database write, alias update, duplicate merge, or canonical record creation is performed.",
        ]
    )
    return ModerationDecisionPlan(
        decision_type=decision.decision_type,
        human_readable_summary=summary,
        affected_candidate={
            "queueItemId": queue_item.queue_item_id,
            "sourceCandidateId": queue_item.source_candidate_id,
            "queueType": queue_item.queue_type,
            "confidence": str(queue_item.confidence),
        },
        target_material_reference=queue_item.matched_material_reference,
        required_manual_confirmation=decision.decision_type in CONFIRMATION_REQUIRED_DECISIONS,
        operations_preview=operations,
        warnings=warnings,
        no_side_effects=True,
    )


def build_rule_suggestion(
    queue_item: MaterialModerationQueueItem,
    decision: MaterialModerationDecision,
) -> ModerationRuleSuggestion:
    rule_type = {
        "accept_match": "matching_rule_candidate",
        "reject_match": "rejection_rule_candidate",
        "create_new_material_candidate": "new_material_rule_candidate",
        "mark_possible_duplicate": "dedup_rule_candidate",
        "request_more_data": "data_quality_rule_candidate",
        "flag_quality_issue": "quality_issue_rule_candidate",
    }.get(decision.decision_type, "moderation_rule_candidate")
    conditions = {
        "queueType": queue_item.queue_type,
        "decisionHint": queue_item.decision_hint,
        "groupCode": queue_item.normalized_candidate_snapshot.get("suggested_group_code"),
        "missingFields": queue_item.missing_fields,
        "conflictingFields": queue_item.conflicting_fields,
        "confidenceAtDecision": str(queue_item.confidence),
    }
    return ModerationRuleSuggestion(
        suggestion_id=_stable_key("m1_rule_suggestion", queue_item.queue_item_id, decision.decision_type),
        source_queue_item_id=queue_item.queue_item_id,
        rule_type=rule_type,
        title=f"Rule suggestion for {decision.decision_type}",
        rationale=(
            "Suggestion is derived from a moderator decision preview.",
            "It is not saved automatically and must be approved as a separate rule.",
        ),
        conditions=conditions,
        action_preview={
            "decisionType": decision.decision_type,
            "targetMaterialReference": queue_item.matched_material_reference,
            "noAutomaticApply": True,
        },
        confidence=queue_item.confidence,
        saved_automatically=False,
    )


def build_moderation_queue_report(
    queue_items: Iterable[MaterialModerationQueueItem],
) -> ModerationQueueReport:
    items = tuple(queue_items)
    by_queue_type: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    blocked_decision_count = 0
    for item in items:
        by_queue_type[item.queue_type] = by_queue_type.get(item.queue_type, 0) + 1
        by_priority[item.priority] = by_priority.get(item.priority, 0) + 1
        blocked_decision_count += len(item.blocked_decisions)
    return ModerationQueueReport(
        total_items=len(items),
        by_queue_type=by_queue_type,
        by_priority=by_priority,
        blocked_decision_count=blocked_decision_count,
        summary={
            "auto_apply_allowed": False,
            "requires_moderator": True,
            "queue_types": tuple(sorted(by_queue_type)),
            "priorities": tuple(sorted(by_priority)),
        },
    )


def _decision_policy(
    *,
    queue_type: str,
    matched_material_reference: Mapping[str, Any] | None,
    missing_fields: tuple[str, ...],
    conflicting_fields: tuple[str, ...],
    has_positive_price: bool,
) -> tuple[tuple[str, ...], tuple[Mapping[str, str], ...]]:
    allowed = set(DECISION_TYPES)
    blocked: list[Mapping[str, str]] = []

    if not matched_material_reference:
        allowed.discard("accept_match")
        blocked.append({"decisionType": "accept_match", "reason": "No existing material reference is available."})
    if missing_fields:
        for decision_type in ("accept_match", "create_new_material_candidate"):
            allowed.discard(decision_type)
            blocked.append(
                {
                    "decisionType": decision_type,
                    "reason": "Required fields must be completed before this decision.",
                }
            )
    if not has_positive_price:
        allowed.discard("create_new_material_candidate")
        blocked.append(
            {
                "decisionType": "create_new_material_candidate",
                "reason": "A positive price is required before creating a new material candidate.",
            }
        )
    if queue_type != "possible_duplicate_review" and not conflicting_fields:
        allowed.discard("mark_possible_duplicate")
        blocked.append({"decisionType": "mark_possible_duplicate", "reason": "No duplicate conflict signal is present."})
    if queue_type == "low_confidence_review":
        allowed.discard("accept_match")
        blocked.append({"decisionType": "accept_match", "reason": "Confidence is too low for accept_match."})
    if queue_type in {"exact_match_review", "strong_match_review"}:
        allowed.discard("create_new_material_candidate")
        blocked.append(
            {
                "decisionType": "create_new_material_candidate",
                "reason": "A matching existing material is available; reject the match first if this is wrong.",
            }
        )
    ordered_allowed = tuple(decision for decision in DECISION_TYPES if decision in allowed)
    return ordered_allowed, tuple(blocked)


def _decision_operations(
    queue_item: MaterialModerationQueueItem,
    decision: MaterialModerationDecision,
) -> tuple[str, tuple[str, ...]]:
    if decision.decision_type == "accept_match":
        return (
            "Moderator accepted the candidate as matching the existing material.",
            (
                "Record moderator approval for this candidate.",
                "Prepare a link between the raw candidate and the existing material after a separate apply step.",
                "Do not create aliases automatically.",
            ),
        )
    if decision.decision_type == "reject_match":
        return (
            "Moderator rejected the proposed match.",
            (
                "Record rejection reason for this candidate.",
                "Keep source evidence available for future review.",
            ),
        )
    if decision.decision_type == "create_new_material_candidate":
        return (
            "Moderator decided that this can become a new material candidate.",
            (
                "Prepare a draft creation package for a future manual apply step.",
                "Do not create a material row in this plan.",
            ),
        )
    if decision.decision_type == "mark_possible_duplicate":
        return (
            "Moderator marked the item as a possible duplicate.",
            (
                "Route both sides to manual duplicate review.",
                "Do not merge records automatically.",
            ),
        )
    if decision.decision_type == "request_more_data":
        fields = ", ".join(queue_item.missing_fields) or "additional evidence"
        return (
            "Moderator requested more data.",
            (f"Request or capture missing fields: {fields}.",),
        )
    if decision.decision_type == "defer":
        return ("Moderator deferred the candidate.", ("Keep the item in queue without applying changes.",))
    if decision.decision_type == "archive_candidate":
        return ("Moderator archived the candidate.", ("Mark candidate as archived in a future apply step.",))
    return (
        "Moderator flagged a quality issue.",
        ("Prepare a quality issue draft for manual review.",),
    )


def _queue_reason(queue_type: str, match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> str:
    return {
        "exact_match_review": "High-confidence exact match still requires moderator review.",
        "strong_match_review": "Strong match requires moderator review before applying.",
        "possible_duplicate_review": "Conflicting fields or duplicate signal require manual duplicate review.",
        "new_material_review": "Candidate may become a new material only after moderator approval.",
        "missing_required_fields": "Required fields are missing before a final moderation decision.",
        "low_confidence_review": "Candidate confidence is below the moderation threshold.",
    }[classify_moderation_queue_type(match_candidate)]


def _candidate_type(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> str:
    return "dedup_candidate" if isinstance(match_candidate, DedupCandidateDTO) else "match_candidate"


def _candidate_id(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> str:
    return match_candidate.candidate_id


def _normalized_snapshot(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> Mapping[str, Any]:
    if isinstance(match_candidate, DedupCandidateDTO):
        return match_candidate.left_candidate_snapshot
    return match_candidate.normalized_candidate_snapshot


def _related_candidate_snapshot(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> Mapping[str, Any] | None:
    if isinstance(match_candidate, DedupCandidateDTO):
        return match_candidate.right_candidate_snapshot
    return None


def _matched_material_reference(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> Mapping[str, Any] | None:
    if isinstance(match_candidate, DedupCandidateDTO):
        return None
    return match_candidate.matched_material_reference


def _confidence(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> Decimal:
    return match_candidate.confidence


def _decision_hint(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> str:
    return match_candidate.decision_hint


def _explanation(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> tuple[str, ...]:
    return tuple(match_candidate.explanation)


def _missing_fields(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> tuple[str, ...]:
    snapshot = _normalized_snapshot(match_candidate)
    values = list(match_candidate.missing_fields)
    values.extend(snapshot.get("missing_required_fields") or ())
    values.extend(snapshot.get("module2_missing_fields") or ())
    return _unique(values)


def _has_positive_price(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> bool:
    snapshot = _normalized_snapshot(match_candidate)
    value = snapshot.get("price_hint")
    try:
        if value in (None, ""):
            return False
        return Decimal(str(value).replace(",", ".")) > 0
    except Exception:
        return False


def _required_missing_fields(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> tuple[str, ...]:
    snapshot = _normalized_snapshot(match_candidate)
    values = list(snapshot.get("missing_required_fields") or ())
    values.extend(snapshot.get("module2_missing_fields") or ())
    return _unique(values)


def _conflicting_fields(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> tuple[str, ...]:
    return tuple(match_candidate.conflicting_fields)


def _evidence_refs(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> Mapping[str, Any]:
    if isinstance(match_candidate, DedupCandidateDTO):
        return {
            "leftCandidateEvidence": match_candidate.left_candidate_snapshot.get("evidence", {}),
            "rightCandidateEvidence": match_candidate.right_candidate_snapshot.get("evidence", {}),
        }
    return match_candidate.evidence_refs


def _source_refs(match_candidate: MaterialMatchCandidateDTO | DedupCandidateDTO) -> Mapping[str, Any]:
    if isinstance(match_candidate, DedupCandidateDTO):
        return {
            "leftCandidateSource": match_candidate.left_candidate_snapshot.get("source_metadata", {}),
            "rightCandidateSource": match_candidate.right_candidate_snapshot.get("source_metadata", {}),
        }
    return match_candidate.source_refs


def _stable_key(prefix: str, *parts: Any) -> str:
    payload = repr(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha1(payload).hexdigest()[:16]}"


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return tuple(result)
