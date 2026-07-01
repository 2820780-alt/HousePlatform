from decimal import Decimal

from app.schemas.material_hub_contracts import AutomationAction, SourceTrustLevel
from app.services.safe_automation_policy import (
    can_auto_link_to_material,
    can_auto_update_price,
    can_create_draft_material,
    get_automation_reason,
    should_go_to_batch_moderation,
    should_require_manual_review,
)


def test_can_auto_update_price_for_linked_catalog_product():
    decision = can_auto_update_price(
        {
            "material_id": "material-1",
            "external_id": "source-product-1",
            "unit": "шт",
            "match_confidence": Decimal("0.99"),
        },
        {"source_code": "stroi_s", "trust_level": SourceTrustLevel.TRUSTED},
        {"price": Decimal("120.50"), "availability": "in_stock", "unit": "шт"},
    )

    assert decision.allowed is True
    assert decision.action == AutomationAction.AUTO_PRICE_UPDATED
    dumped = decision.model_dump(mode="json", by_alias=True)
    assert dumped["sourceCode"] == "stroi_s"
    assert dumped["sourceTrustLevel"] == "TRUSTED"
    assert dumped["systemUser"] == "module01_safe_automation_policy"


def test_auto_price_update_requires_material_link():
    decision = can_auto_update_price(
        {"external_id": "source-product-1", "unit": "м³", "match_confidence": Decimal("0.99")},
        {"source_code": "supplier_file", "trust_level": SourceTrustLevel.TRUSTED},
        {"price": Decimal("1200"), "unit": "м³"},
    )

    assert decision.allowed is False
    assert decision.action == AutomationAction.NEEDS_REVIEW
    assert "not linked" in decision.reason


def test_can_auto_link_to_existing_material_with_confirmed_rule_memory():
    decision = can_auto_link_to_material(
        {"raw_brand": "Bonolit", "raw_category": "gas_block", "unit": "шт"},
        {
            "candidate_material_id": "material-1",
            "classification_confidence": Decimal("0.96"),
            "match_score": Decimal("0.97"),
            "brand": "Bonolit",
            "category": "gas_block",
            "unit": "шт",
            "moderator_rule_memory_id": "rule-memory-1",
        },
        {"source_code": "bonolit", "trust_level": SourceTrustLevel.TRUSTED},
    )

    assert decision.allowed is True
    assert decision.action == AutomationAction.AUTO_LINKED_TO_MATERIAL
    assert decision.moderator_rule_memory_id == "rule-memory-1"
    assert "canonical Material remains unchanged" in decision.reason


def test_auto_link_does_not_create_active_material():
    decision = can_auto_link_to_material(
        {"raw_brand": "NoName", "raw_category": "unknown", "unit": "шт"},
        {"classification_confidence": Decimal("0.99"), "match_score": Decimal("0.99")},
        {"source_code": "trusted_source", "trust_level": SourceTrustLevel.TRUSTED},
    )

    assert decision.allowed is False
    assert decision.action == AutomationAction.NEEDS_REVIEW
    assert "must not create ACTIVE Material" in decision.reason


def test_can_create_draft_material_but_not_active_material():
    decision = can_create_draft_material(
        {
            "raw_name": "Газоблок D500 600x300x200",
            "raw_category": "Газобетон",
            "unit": "шт",
            "classification_confidence": Decimal("0.93"),
        },
        {"source_code": "ksmk", "trust_level": SourceTrustLevel.TRUSTED, "write_mode": "CREATE_CANDIDATES"},
    )

    assert decision.allowed is True
    assert decision.action == AutomationAction.DRAFT_MATERIAL_CREATED
    assert "ACTIVE Material creation is explicitly forbidden" in decision.reason


def test_preview_mode_blocks_draft_material_creation():
    decision = can_create_draft_material(
        {
            "raw_name": "Кирпич рядовой",
            "raw_category": "Кирпич",
            "unit": "шт",
            "classification_confidence": Decimal("0.95"),
        },
        {"source_code": "preview_source", "trust_level": SourceTrustLevel.TRUSTED, "write_mode": "PREVIEW"},
    )

    assert decision.allowed is False
    assert decision.action == AutomationAction.PREVIEW_ONLY


def test_region_needs_review_requires_manual_review():
    candidate = {"region_status": "needs_review", "confidence": Decimal("0.88")}

    decision = should_require_manual_review(candidate)

    assert decision.allowed is True
    assert decision.action == AutomationAction.NEEDS_REGION_REVIEW
    assert get_automation_reason(candidate) == "Candidate region_status is needs_review."


def test_batch_moderation_ready_for_repeatable_group():
    decision = should_go_to_batch_moderation(
        {
            "sourceCode": "supplier_price",
            "group_size": 8,
            "confidence": Decimal("0.82"),
            "normalization_rule": "gas_block_size_rule_v1",
        }
    )

    assert decision.allowed is True
    assert decision.action == AutomationAction.BATCH_READY
