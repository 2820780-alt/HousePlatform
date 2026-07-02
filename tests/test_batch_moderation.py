from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.schemas.material_hub_contracts import BatchModerationAction
from app.services.batch_moderation import (
    build_batch_moderation_queue,
    build_rule_memory_payload_for_candidate,
    new_batch_decision,
)
from app.services.rule_memory import build_rule_memory_attributes


def _candidate(target_material_id, name="Газоблок D500 600х300х200"):
    source = SimpleNamespace(name="source-a")
    product = SimpleNamespace(
        id=uuid4(),
        source=source,
        source_id=uuid4(),
        raw_name=name,
        normalized_name="газобетонный блок d500 600x300x200",
        raw_category="Газобетон / блоки",
        raw_brand="Bonolit",
        raw_manufacturer="Bonolit",
        unit="шт",
        region="Краснодарский край",
        material_id=None,
    )
    return SimpleNamespace(
        id=uuid4(),
        catalog_product_id=product.id,
        catalog_product=product,
        candidate_material_id=target_material_id,
        match_score=Decimal("0.96"),
        match_reason="same source/category/brand/size",
    )


def test_batch_moderation_queue_groups_repeatable_candidates():
    target_material_id = uuid4()
    candidates = [_candidate(target_material_id) for _ in range(3)]

    queue = build_batch_moderation_queue(candidates, minimum_group_size=3)

    assert queue.total_candidates == 3
    assert queue.manual_review_candidate_ids == []
    assert len(queue.groups) == 1
    group = queue.groups[0]
    assert group.candidate_count == 3
    assert group.source_code == "source-a"
    assert group.atom_category_path == "Газобетон / блоки"
    assert group.matched_material_id == target_material_id
    assert group.dimensions == "600x300x200"
    assert group.normalization_rule == "WALL_MATERIALS"
    assert group.active_material_creation_allowed is False
    assert group.can_confirm_safely is True
    assert group.rule_suggestion is not None
    assert group.rule_suggestion.allowed_scope["sourceCode"] == "source-a"
    assert "sourceCode: source-a" in group.grouping_reasons


def test_small_group_stays_in_manual_review_queue():
    candidate = _candidate(uuid4())

    queue = build_batch_moderation_queue([candidate], minimum_group_size=3)

    assert queue.groups == []
    assert queue.manual_review_candidate_ids == [candidate.id]


def test_batch_decision_does_not_create_active_material():
    target_material_id = uuid4()
    group = build_batch_moderation_queue([_candidate(target_material_id) for _ in range(3)]).groups[0]

    decision = new_batch_decision(BatchModerationAction.CONFIRM_GROUP, group=group)

    assert decision.target_material_id == target_material_id
    assert decision.candidate_ids == group.candidate_ids
    assert decision.creates_active_material is False
    assert decision.rollback_available is True


def test_rule_memory_payload_is_scoped_and_visible():
    target_material_id = uuid4()
    moderator_id = uuid4()
    candidate = _candidate(target_material_id)
    group = build_batch_moderation_queue([candidate, _candidate(target_material_id), _candidate(target_material_id)]).groups[0]
    decision = new_batch_decision(BatchModerationAction.CONFIRM_GROUP, group=group, moderator_id=moderator_id)

    payload = build_rule_memory_payload_for_candidate(
        candidate,
        group=group,
        decision=decision,
        moderator_id=moderator_id,
    )

    assert payload["incoming"]["rawName"] == "Газоблок D500 600х300х200"
    assert payload["normalized"]["normalizedName"] == "газобетонный блок d500 600x300x200"
    assert payload["target"]["materialId"] == str(target_material_id)
    assert payload["sourceCode"] == "source-a"
    assert payload["atomCategoryPath"] == "Газобетон / блоки"
    assert payload["materialType"] == "WALL_MATERIALS"
    assert payload["confirmedBy"] == str(moderator_id)
    assert payload["ruleScope"]["sourceCode"] == "source-a"


def test_rule_memory_attributes_store_required_moderator_context():
    material = SimpleNamespace(id=uuid4(), canonical_name="Газобетонный блок D500 600x300x200")

    payload = build_rule_memory_attributes(
        attributes={"incoming": {"rawName": "Газоблок"}},
        material=material,
        source="batch_moderation",
        confidence_boost=Decimal("0.15"),
        rule_scope={
            "sourceCode": "source-a",
            "atomCategoryPath": "Газобетон / блоки",
            "materialType": "WALL_MATERIALS",
        },
        confirmed_by="moderator-1",
        review_required_at="2026-10-01T00:00:00",
    )

    assert payload["incoming"]["rawName"] == "Газоблок"
    assert payload["target"]["materialId"] == str(material.id)
    assert payload["confidenceBoost"] == "0.15"
    assert payload["confirmedBy"] == "moderator-1"
    assert payload["sourceCode"] == "source-a"
    assert payload["materialType"] == "WALL_MATERIALS"
    assert "RuleMemory does not create ACTIVE Material." in payload["guardrails"]
