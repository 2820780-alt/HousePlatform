from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from app.services.module1_matching_dedup import (
    MaterialMatchCandidateDTO,
    build_match_candidate,
)
from app.services.module1_material_normalizer import NormalizedMaterialCandidate
from app.services.module1_moderation_core import (
    MaterialModerationDecision,
    MaterialModerationQueueItem,
    build_decision_plan,
    build_moderation_queue,
    build_moderation_queue_item,
    build_moderation_queue_report,
    build_rule_suggestion,
    classify_moderation_priority,
    classify_moderation_queue_type,
    validate_moderation_decision,
)


def _candidate(
    title: str = "aerated_concrete_block D500 600x300x200",
    *,
    group_code: str = "aerated_concrete_block",
    characteristics: dict | None = None,
    unit: str = "piece",
    confidence: str = "0.95",
    missing_required_fields: tuple[str, ...] = (),
    module2_missing_fields: tuple[str, ...] = (),
    price_hint: object = Decimal("100.00"),
) -> NormalizedMaterialCandidate:
    return NormalizedMaterialCandidate(
        normalized_title=title,
        source_title=title,
        suggested_group_code=group_code,
        suggested_category=None,
        manufacturer=None,
        brand=None,
        normalized_characteristics=characteristics
        or {
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
        normalized_unit=unit,
        price_hint=price_hint,
        source_metadata={
            "source_code": "TEST_SOURCE",
            "source_type": "supplier_site",
            "source_url": "https://example.test/item",
        },
        confidence=Decimal(confidence),
        warnings=(),
        missing_required_fields=missing_required_fields,
        module2_missing_fields=module2_missing_fields,
        evidence={
            "raw_title": title,
            "raw_category": group_code,
            "raw_documents": (),
            "raw_images": (),
        },
    )


def _strong_gas_block_match() -> MaterialMatchCandidateDTO:
    existing = {
        "id": "mat-gas-001",
        "canonical_name": "aerated_concrete_block D500 600x300x200",
        "group_code": "aerated_concrete_block",
        "normalized_characteristics": {
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
        "unit": "piece",
    }
    return build_match_candidate(_candidate(), [existing])


def _dimension_conflict_match() -> MaterialMatchCandidateDTO:
    existing = {
        "id": "mat-gas-002",
        "canonical_name": "aerated_concrete_block D500 600x300x300",
        "group_code": "aerated_concrete_block",
        "normalized_characteristics": {
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("300"),
            "density_class": "D500",
        },
        "unit": "piece",
    }
    return build_match_candidate(_candidate(), [existing])


def test_strong_gas_block_match_goes_to_review_queue_with_allowed_decisions() -> None:
    match = _strong_gas_block_match()
    queue_item = build_moderation_queue_item(match)

    assert isinstance(queue_item, MaterialModerationQueueItem)
    assert queue_item.queue_type in {"exact_match_review", "strong_match_review"}
    assert queue_item.priority == "high"
    assert "accept_match" in queue_item.allowed_decisions
    assert "reject_match" in queue_item.allowed_decisions
    assert "request_more_data" in queue_item.allowed_decisions
    assert queue_item.matched_material_reference["id"] == "mat-gas-001"
    assert any("review" in queue_item.reason.lower() for _ in [queue_item.reason])


def test_gas_block_dimension_conflict_goes_to_possible_duplicate_review() -> None:
    match = _dimension_conflict_match()
    queue_item = build_moderation_queue_item(match)

    assert queue_item.queue_type == "possible_duplicate_review"
    assert queue_item.priority == "high"
    assert "height_mm" in queue_item.conflicting_fields
    assert "mark_possible_duplicate" in queue_item.allowed_decisions


def test_low_confidence_candidate_goes_to_low_confidence_review() -> None:
    match = build_match_candidate(_candidate(confidence="0.45"), [])
    queue_item = build_moderation_queue_item(match)

    assert classify_moderation_queue_type(match) == "low_confidence_review"
    assert classify_moderation_priority(match) == "medium"
    assert queue_item.queue_type == "low_confidence_review"
    assert "accept_match" not in queue_item.allowed_decisions
    assert any(blocked["decisionType"] == "accept_match" for blocked in queue_item.blocked_decisions)


def test_candidate_with_missing_module2_fields_goes_to_missing_required_fields_queue() -> None:
    match = _strong_gas_block_match()
    snapshot = dict(match.normalized_candidate_snapshot)
    snapshot["module2_missing_fields"] = ("pieces_per_m3",)
    match_with_missing = replace(match, normalized_candidate_snapshot=snapshot)

    queue_item = build_moderation_queue_item(match_with_missing)

    assert queue_item.queue_type == "missing_required_fields"
    assert queue_item.priority == "critical"
    assert "pieces_per_m3" in queue_item.missing_fields
    assert "accept_match" not in queue_item.allowed_decisions
    assert "create_new_material_candidate" not in queue_item.allowed_decisions


def test_accept_match_decision_builds_plan_without_db_write_or_alias() -> None:
    queue_item = build_moderation_queue_item(_strong_gas_block_match())
    decision = MaterialModerationDecision(
        decision_type="accept_match",
        moderator_id="moderator-1",
        comment="Accepted after manual review.",
        confirmed=True,
    )

    validation = validate_moderation_decision(queue_item, decision)
    plan = build_decision_plan(queue_item, decision)

    assert validation.is_valid is True
    assert plan.decision_type == "accept_match"
    assert plan.target_material_reference["id"] == "mat-gas-001"
    assert plan.required_manual_confirmation is True
    assert plan.no_side_effects is True
    assert any("Do not create aliases automatically" in operation for operation in plan.operations_preview)
    assert any("No database write" in warning for warning in plan.warnings)


def test_create_new_material_candidate_decision_builds_plan_but_creates_nothing() -> None:
    match = MaterialMatchCandidateDTO(
        candidate_id="match_new_material_001",
        normalized_candidate_snapshot={
            "normalized_title": "new specialty mortar",
            "suggested_group_code": "dry_mix",
            "module2_missing_fields": (),
            "price_hint": Decimal("100.00"),
        },
        matched_material_reference=None,
        confidence=Decimal("82"),
        decision_hint="new_material_candidate",
        explanation=("Candidate has no safe existing material match.",),
        conflicting_fields=(),
        missing_fields=(),
        evidence_refs={"raw_title": "new specialty mortar"},
        source_refs={"source_code": "TEST_SOURCE"},
        score_breakdown={},
    )
    queue_item = build_moderation_queue_item(match)
    decision = MaterialModerationDecision(
        decision_type="create_new_material_candidate",
        moderator_id="moderator-1",
        comment="Create candidate after review.",
        confirmed=True,
    )

    plan = build_decision_plan(queue_item, decision)

    assert queue_item.queue_type == "new_material_review"
    assert "create_new_material_candidate" in queue_item.allowed_decisions
    assert plan.no_side_effects is True
    assert any("Do not create a material row" in operation for operation in plan.operations_preview)



def test_create_new_material_candidate_without_positive_price_is_blocked() -> None:
    match = MaterialMatchCandidateDTO(
        candidate_id="match_no_price_material_001",
        normalized_candidate_snapshot={
            "normalized_title": "new no price material",
            "suggested_group_code": "dry_mix",
            "module2_missing_fields": (),
            "price_hint": None,
        },
        matched_material_reference=None,
        confidence=Decimal("82"),
        decision_hint="new_material_candidate",
        explanation=("Candidate has no safe existing material match.",),
        conflicting_fields=(),
        missing_fields=(),
        evidence_refs={"raw_title": "new no price material"},
        source_refs={"source_code": "TEST_SOURCE"},
        score_breakdown={},
    )
    queue_item = build_moderation_queue_item(match)
    decision = MaterialModerationDecision(
        decision_type="create_new_material_candidate",
        moderator_id="moderator-1",
        comment="Create candidate after review.",
        confirmed=True,
    )

    validation = validate_moderation_decision(queue_item, decision)

    assert "create_new_material_candidate" not in queue_item.allowed_decisions
    assert any(block["decisionType"] == "create_new_material_candidate" for block in queue_item.blocked_decisions)
    assert validation.is_valid is False
    assert any("create_new_material_candidate" in error for error in validation.errors)


def test_accept_match_for_existing_material_is_not_blocked_by_missing_candidate_price() -> None:
    match = build_match_candidate(_candidate(price_hint=None), [
        {
            "id": "mat-gas-001",
            "canonical_name": "aerated_concrete_block D500 600x300x200",
            "group_code": "aerated_concrete_block",
            "normalized_characteristics": {
                "length_mm": Decimal("600"),
                "width_mm": Decimal("300"),
                "height_mm": Decimal("200"),
                "density_class": "D500",
            },
            "unit": "piece",
        }
    ])
    queue_item = build_moderation_queue_item(match)
    decision = MaterialModerationDecision(decision_type="accept_match", moderator_id="moderator-1", confirmed=True)

    validation = validate_moderation_decision(queue_item, decision)

    assert queue_item.matched_material_reference is not None
    assert "accept_match" in queue_item.allowed_decisions
    assert validation.is_valid is True

def test_rule_suggestion_is_created_but_not_saved_automatically() -> None:
    queue_item = build_moderation_queue_item(_strong_gas_block_match())
    decision = MaterialModerationDecision(
        decision_type="accept_match",
        moderator_id="moderator-1",
        comment="Repeatable strong match.",
        confirmed=True,
    )

    suggestion = build_rule_suggestion(queue_item, decision)

    assert suggestion.rule_type == "matching_rule_candidate"
    assert suggestion.source_queue_item_id == queue_item.queue_item_id
    assert suggestion.conditions["queueType"] == queue_item.queue_type
    assert suggestion.action_preview["noAutomaticApply"] is True
    assert suggestion.saved_automatically is False


def test_queue_report_groups_by_type_and_priority() -> None:
    strong = build_moderation_queue_item(_strong_gas_block_match())
    duplicate = build_moderation_queue_item(_dimension_conflict_match())
    low = build_moderation_queue_item(build_match_candidate(_candidate(confidence="0.45"), []))

    queue = build_moderation_queue([_strong_gas_block_match(), _dimension_conflict_match()])
    report = build_moderation_queue_report([strong, duplicate, low])

    assert len(queue) == 2
    assert report.total_items == 3
    assert report.by_queue_type[strong.queue_type] == 1
    assert report.by_queue_type["possible_duplicate_review"] == 1
    assert report.by_queue_type["low_confidence_review"] == 1
    assert report.by_priority["high"] == 2
    assert report.by_priority["medium"] == 1
    assert report.summary["auto_apply_allowed"] is False
    assert report.summary["requires_moderator"] is True


def test_moderation_core_does_not_import_orm_or_apply_decisions() -> None:
    source = Path("app/services/module1_moderation_core.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "source_task_runner" not in source
    assert "Material(" not in source
    assert "CanonicalMaterial" not in source
    assert "add_alias" not in source
    assert ".commit(" not in source
    assert ".add(" not in source
