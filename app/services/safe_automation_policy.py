from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from app.schemas.material_hub_contracts import (
    AutomationAction,
    AutomationDecision,
    ResultWriteMode,
    SafeAutomationPolicy,
    SourceTrustLevel,
)


DEFAULT_SAFE_AUTOMATION_POLICY = SafeAutomationPolicy()


def can_auto_update_price(
    catalog_product: Any,
    source_profile: Any,
    changes: dict[str, Any] | None,
    policy: SafeAutomationPolicy | None = None,
) -> AutomationDecision:
    policy = policy or DEFAULT_SAFE_AUTOMATION_POLICY
    changes = dict(changes or {})
    trust_level = _source_trust_level(source_profile)

    if trust_level == policy.source_trust.test_level_requires_preview:
        return _decision(
            AutomationAction.PREVIEW_ONLY,
            "Source trust level TEST allows preview only; price update must not be written automatically.",
            Decimal("0"),
            source_profile,
            policy,
        )
    if trust_level not in policy.source_trust.allowed_levels_for_price_update:
        return _decision(
            AutomationAction.SOURCE_STRUCTURE_ERROR,
            "Source trust level does not allow automatic price updates.",
            Decimal("0"),
            source_profile,
            policy,
        )
    if policy.auto_price_update.require_material_link and not _get(catalog_product, "material_id", "materialId"):
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            "CatalogProduct is not linked to a confirmed Material; price can only become candidate data.",
            Decimal("0"),
            source_profile,
            policy,
        )
    if policy.auto_price_update.require_stable_source_identity and not _has_stable_source_identity(catalog_product):
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            "CatalogProduct has no stable source identity such as external_id, sourceProductId or external_url.",
            Decimal("0"),
            source_profile,
            policy,
        )

    blocked_changes = set(changes).intersection(policy.auto_price_update.blocked_change_fields)
    if blocked_changes:
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            f"Automatic price update cannot change Material/product identity fields: {', '.join(sorted(blocked_changes))}.",
            _product_confidence(catalog_product),
            source_profile,
            policy,
        )

    unit_change = changes.get("unit")
    current_unit = _get(catalog_product, "unit")
    if policy.auto_price_update.require_same_unit and unit_change is not None and _normalized(unit_change) != _normalized(current_unit):
        return _decision(
            AutomationAction.NEEDS_UNIT_REVIEW,
            "Price unit changed or current unit is unknown; moderator must check unit semantics before writing price history.",
            _product_confidence(catalog_product),
            source_profile,
            policy,
        )

    allowed_change_fields = set(policy.auto_price_update.allowed_change_fields)
    unknown_fields = set(changes).difference(allowed_change_fields).difference({"unit"})
    if unknown_fields:
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            f"Automatic price update received unsupported changed fields: {', '.join(sorted(unknown_fields))}.",
            _product_confidence(catalog_product),
            source_profile,
            policy,
        )

    confidence = _product_confidence(catalog_product, default=Decimal("0.99"))
    if confidence < policy.auto_price_update.minimum_confidence:
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            "Existing CatalogProduct confidence is below the automatic price update threshold.",
            confidence,
            source_profile,
            policy,
        )

    return _decision(
        AutomationAction.AUTO_PRICE_UPDATED,
        "Only price, availability, date or regional availability changed for an already linked CatalogProduct.",
        confidence,
        source_profile,
        policy,
        allowed=True,
    )


def can_auto_link_to_material(
    catalog_product: Any,
    material_candidate: Any,
    source_profile: Any,
    policy: SafeAutomationPolicy | None = None,
) -> AutomationDecision:
    policy = policy or DEFAULT_SAFE_AUTOMATION_POLICY
    trust_level = _source_trust_level(source_profile)
    applied_rule_id = _applied_rule_id(material_candidate)
    moderator_rule_memory_id = _moderator_rule_memory_id(material_candidate)

    if trust_level not in policy.source_trust.trusted_levels_for_auto_link:
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            "Auto-link requires a trusted source profile and confirmed matching pattern.",
            Decimal("0"),
            source_profile,
            policy,
            applied_rule_id=applied_rule_id,
            moderator_rule_memory_id=moderator_rule_memory_id,
        )
    candidate_material_id = _get(
        material_candidate,
        "candidate_material_id",
        "candidateMaterialId",
        "material_id",
        "materialId",
    )
    if not candidate_material_id:
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            "Auto-link requires an existing candidate Material; safe automation must not create ACTIVE Material.",
            Decimal("0"),
            source_profile,
            policy,
            applied_rule_id=applied_rule_id,
            moderator_rule_memory_id=moderator_rule_memory_id,
        )

    classification_confidence = _confidence(
        material_candidate,
        "classification_confidence",
        "classificationConfidence",
        "classification_score",
        "classificationScore",
    )
    matching_confidence = _confidence(
        material_candidate,
        "matching_confidence",
        "matchingConfidence",
        "match_score",
        "matchScore",
        default=_product_confidence(catalog_product),
    )
    confidence = min(classification_confidence, matching_confidence)
    if classification_confidence < policy.auto_link.minimum_classification_confidence:
        return _decision(
            AutomationAction.NEEDS_CLASSIFICATION,
            "Classification confidence is below the auto-link threshold.",
            confidence,
            source_profile,
            policy,
            applied_rule_id=applied_rule_id,
            moderator_rule_memory_id=moderator_rule_memory_id,
        )
    if matching_confidence < policy.auto_link.minimum_matching_confidence:
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            "Matching confidence is below the auto-link threshold.",
            confidence,
            source_profile,
            policy,
            applied_rule_id=applied_rule_id,
            moderator_rule_memory_id=moderator_rule_memory_id,
        )

    conflict_reason = _matching_conflict_reason(catalog_product, material_candidate, policy)
    if conflict_reason:
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            conflict_reason,
            confidence,
            source_profile,
            policy,
            applied_rule_id=applied_rule_id,
            moderator_rule_memory_id=moderator_rule_memory_id,
        )
    if policy.auto_link.require_moderator_memory_or_rule and not (applied_rule_id or moderator_rule_memory_id):
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            "Auto-link requires an applied rule or moderator RuleMemory from a previously confirmed pattern.",
            confidence,
            source_profile,
            policy,
        )

    return _decision(
        AutomationAction.AUTO_LINKED_TO_MATERIAL,
        "High-confidence candidate may be linked to an existing Material; canonical Material remains unchanged.",
        confidence,
        source_profile,
        policy,
        applied_rule_id=applied_rule_id,
        moderator_rule_memory_id=moderator_rule_memory_id,
        allowed=True,
    )


def can_create_draft_material(
    catalog_product: Any,
    source_profile: Any,
    policy: SafeAutomationPolicy | None = None,
) -> AutomationDecision:
    policy = policy or DEFAULT_SAFE_AUTOMATION_POLICY
    trust_level = _source_trust_level(source_profile)
    write_mode = _write_mode(source_profile, catalog_product)

    if write_mode == ResultWriteMode.PREVIEW:
        return _decision(
            AutomationAction.PREVIEW_ONLY,
            "Write mode PREVIEW forbids creating even draft/pending Material records.",
            Decimal("0"),
            source_profile,
            policy,
        )
    if write_mode not in policy.draft_material.allowed_write_modes:
        return _decision(
            AutomationAction.PENDING_CONFIRMATION,
            "Write mode does not allow draft creation; keep the record as candidate data.",
            Decimal("0"),
            source_profile,
            policy,
        )
    if trust_level in policy.source_trust.blocked_levels:
        return _decision(
            AutomationAction.SOURCE_STRUCTURE_ERROR,
            "Source trust level blocks draft Material creation.",
            Decimal("0"),
            source_profile,
            policy,
        )
    if trust_level not in policy.source_trust.allowed_levels_for_draft_material:
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            "Source trust level is not sufficient for draft Material creation.",
            Decimal("0"),
            source_profile,
            policy,
        )
    if _get(catalog_product, "material_id", "materialId"):
        return _decision(
            AutomationAction.PENDING_CONFIRMATION,
            "CatalogProduct is already linked to Material; create a price/update candidate instead of a draft Material.",
            _product_confidence(catalog_product),
            source_profile,
            policy,
        )
    if not (_get(catalog_product, "normalized_name") or _get(catalog_product, "raw_name") or _get(catalog_product, "title")):
        return _decision(
            AutomationAction.NEEDS_REVIEW,
            "Draft Material requires a source product name.",
            Decimal("0"),
            source_profile,
            policy,
        )
    if policy.draft_material.require_category and not _get(
        catalog_product,
        "category_id",
        "categoryId",
        "raw_category",
        "rawCategory",
        "category",
    ):
        return _decision(
            AutomationAction.NEEDS_CLASSIFICATION,
            "Draft Material requires a classified category.",
            Decimal("0"),
            source_profile,
            policy,
        )
    if policy.draft_material.require_unit and not _get(catalog_product, "unit", "raw_unit", "rawUnit"):
        return _decision(
            AutomationAction.NEEDS_UNIT_REVIEW,
            "Draft Material requires a normalized or reviewable unit.",
            Decimal("0"),
            source_profile,
            policy,
        )

    confidence = _confidence(
        catalog_product,
        "classification_confidence",
        "classificationConfidence",
        "match_confidence",
        "matchConfidence",
    )
    if confidence < policy.draft_material.minimum_classification_confidence:
        return _decision(
            AutomationAction.NEEDS_CLASSIFICATION,
            "Classification confidence is below the draft Material threshold.",
            confidence,
            source_profile,
            policy,
        )

    return _decision(
        AutomationAction.DRAFT_MATERIAL_CREATED,
        "Draft/Pending Material may be prepared for moderation; ACTIVE Material creation is explicitly forbidden.",
        confidence,
        source_profile,
        policy,
        allowed=True,
    )


def should_go_to_batch_moderation(
    candidate: Any,
    policy: SafeAutomationPolicy | None = None,
) -> AutomationDecision:
    policy = policy or DEFAULT_SAFE_AUTOMATION_POLICY
    source_profile = _get(candidate, "source_profile", "sourceProfile")
    group_size = int(_decimal(_get(candidate, "group_size", "groupSize", "similar_count", "similarCount"), Decimal("0")))
    confidence = _candidate_confidence(candidate)
    has_repeatable_rule = bool(
        _get(candidate, "normalization_rule", "normalizationRule", "applied_rule_id", "appliedRuleId")
    )

    if group_size >= policy.batch_moderation.minimum_group_size and (
        confidence >= policy.batch_moderation.minimum_batch_confidence or has_repeatable_rule
    ):
        return _decision(
            AutomationAction.BATCH_READY,
            "Candidate group is repeatable enough for batch moderation; moderator can confirm, split or reject the group.",
            confidence,
            source_profile,
            policy,
            applied_rule_id=_applied_rule_id(candidate),
            moderator_rule_memory_id=_moderator_rule_memory_id(candidate),
            allowed=True,
        )

    return _decision(
        AutomationAction.NEEDS_REVIEW,
        "Candidate is not repeatable enough for batch moderation; keep it in ordinary review flow.",
        confidence,
        source_profile,
        policy,
        applied_rule_id=_applied_rule_id(candidate),
        moderator_rule_memory_id=_moderator_rule_memory_id(candidate),
    )


def should_require_manual_review(
    candidate: Any,
    source_profile: Any | None = None,
    policy: SafeAutomationPolicy | None = None,
) -> AutomationDecision:
    policy = policy or DEFAULT_SAFE_AUTOMATION_POLICY
    source_profile = source_profile or _get(candidate, "source_profile", "sourceProfile")
    action, reason = _manual_review_action_reason(candidate, source_profile, policy)
    confidence = _candidate_confidence(candidate)

    return _decision(
        action,
        reason,
        confidence,
        source_profile,
        policy,
        applied_rule_id=_applied_rule_id(candidate),
        moderator_rule_memory_id=_moderator_rule_memory_id(candidate),
        allowed=action
        in {
            AutomationAction.NEEDS_REVIEW,
            AutomationAction.NEEDS_CLASSIFICATION,
            AutomationAction.NEEDS_REGION_REVIEW,
            AutomationAction.NEEDS_UNIT_REVIEW,
            AutomationAction.NEEDS_DOCUMENT_REVIEW,
            AutomationAction.SOURCE_STRUCTURE_ERROR,
        },
    )


def get_automation_reason(candidate: Any) -> str:
    source_profile = _get(candidate, "source_profile", "sourceProfile")
    _, reason = _manual_review_action_reason(candidate, source_profile, DEFAULT_SAFE_AUTOMATION_POLICY)
    return reason


def _manual_review_action_reason(
    candidate: Any,
    source_profile: Any | None,
    policy: SafeAutomationPolicy,
) -> tuple[AutomationAction, str]:
    trust_level = _source_trust_level(source_profile)
    if trust_level in policy.source_trust.blocked_levels:
        return AutomationAction.SOURCE_STRUCTURE_ERROR, "Source is problem, blocked or archived; moderator must review source state."

    status_text = _normalized(_get(candidate, "status", "automation_status", "automationStatus"))
    if status_text in {"NEEDS_REGION_REVIEW", "REGION_NEEDS_REVIEW"}:
        return AutomationAction.NEEDS_REGION_REVIEW, "Candidate has unresolved region context."
    if status_text in {"NEEDS_UNIT_REVIEW", "UNIT_NEEDS_REVIEW"}:
        return AutomationAction.NEEDS_UNIT_REVIEW, "Candidate has unresolved unit context."
    if status_text in {"NEEDS_DOCUMENT_REVIEW", "DOCUMENT_NEEDS_REVIEW"}:
        return AutomationAction.NEEDS_DOCUMENT_REVIEW, "Candidate has document links that need manual review."
    if status_text in {"NEEDS_CLASSIFICATION", "CLASSIFICATION_NEEDS_REVIEW"}:
        return AutomationAction.NEEDS_CLASSIFICATION, "Candidate classification needs manual review."

    region_status = _normalized(_get(candidate, "region_status", "regionStatus"))
    if region_status == "NEEDS_REVIEW":
        return AutomationAction.NEEDS_REGION_REVIEW, "Candidate region_status is needs_review."
    if _truthy(_get(candidate, "unit_conflict", "unitConflict", "needs_unit_review", "needsUnitReview")):
        return AutomationAction.NEEDS_UNIT_REVIEW, "Candidate unit is missing or conflicts with source data."
    if _truthy(_get(candidate, "document_needs_review", "documentNeedsReview", "needs_document_review", "needsDocumentReview")):
        return AutomationAction.NEEDS_DOCUMENT_REVIEW, "Candidate document reference requires review or deduplication."
    if _has_conflict_flag(candidate):
        return AutomationAction.NEEDS_REVIEW, "Candidate has conflicts in characteristics, category, brand, price unit or source data."

    confidence = _candidate_confidence(candidate)
    if confidence and confidence < Decimal("0.70"):
        return AutomationAction.NEEDS_REVIEW, "Candidate confidence is too low for safe automation."

    return AutomationAction.PENDING_CONFIRMATION, "No blocking automation reason was detected; candidate can continue normal pipeline checks."


def _decision(
    action: AutomationAction,
    reason: str,
    confidence: Decimal,
    source_profile: Any,
    policy: SafeAutomationPolicy,
    *,
    applied_rule_id: Any = None,
    moderator_rule_memory_id: Any = None,
    allowed: bool = False,
) -> AutomationDecision:
    return AutomationDecision(
        action=action,
        reason=reason,
        confidence=_decimal(confidence),
        sourceCode=_source_code(source_profile),
        sourceTrustLevel=_source_trust_level(source_profile),
        appliedRuleId=applied_rule_id,
        moderatorRuleMemoryId=moderator_rule_memory_id,
        createdAt=datetime.now(timezone.utc),
        createdBy=policy.system_user,
        systemUser=policy.system_user,
        allowed=allowed,
    )


def _get(source: Any, *names: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        for name in names:
            if name in source:
                return source[name]
        return default
    for name in names:
        if hasattr(source, name):
            return getattr(source, name)
    return default


def _source_code(source_profile: Any) -> str | None:
    return _get(
        source_profile,
        "source_code",
        "sourceCode",
        "profile_code",
        "profileCode",
        "source_name",
        "sourceName",
        "name",
    )


def _source_trust_level(source_profile: Any) -> SourceTrustLevel:
    raw = _get(source_profile, "trust_level", "trustLevel", "source_trust_level", "sourceTrustLevel")
    if isinstance(raw, SourceTrustLevel):
        return raw
    if raw:
        try:
            return SourceTrustLevel(str(raw).upper())
        except ValueError:
            pass

    status = _normalized(_get(source_profile, "status", "parser_status", "parserStatus"))
    if status == "ERROR":
        return SourceTrustLevel.PROBLEM
    if status in {"DISABLED", "BLOCKED"}:
        return SourceTrustLevel.BLOCKED
    if status == "ARCHIVED":
        return SourceTrustLevel.ARCHIVED
    return SourceTrustLevel.NORMAL


def _write_mode(source_profile: Any, catalog_product: Any) -> ResultWriteMode:
    raw = _get(source_profile, "write_mode", "writeMode") or _get(catalog_product, "write_mode", "writeMode")
    if isinstance(raw, ResultWriteMode):
        return raw
    if raw:
        try:
            return ResultWriteMode(str(raw).upper())
        except ValueError:
            pass
    return ResultWriteMode.CREATE_CANDIDATES


def _has_stable_source_identity(catalog_product: Any) -> bool:
    return any(
        _get(catalog_product, name)
        for name in (
            "external_id",
            "externalId",
            "source_product_id",
            "sourceProductId",
            "external_url",
            "externalUrl",
            "raw_article",
            "rawArticle",
            "article",
        )
    )


def _product_confidence(catalog_product: Any, default: Decimal = Decimal("0")) -> Decimal:
    return _confidence(catalog_product, "match_confidence", "matchConfidence", "confidence", default=default)


def _candidate_confidence(candidate: Any) -> Decimal:
    return _confidence(
        candidate,
        "confidence",
        "match_score",
        "matchScore",
        "matching_confidence",
        "matchingConfidence",
        "classification_confidence",
        "classificationConfidence",
    )


def _confidence(source: Any, *names: str, default: Decimal = Decimal("0")) -> Decimal:
    for name in names:
        value = _get(source, name)
        if value is not None:
            return _decimal(value, default)
    return default


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _normalized(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value
    if value is None:
        return ""
    return str(value).strip().upper()


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "да"}
    return bool(value)


def _applied_rule_id(candidate: Any) -> Any:
    return _get(candidate, "applied_rule_id", "appliedRuleId", "rule_id", "ruleId", "confirmed_rule_id", "confirmedRuleId")


def _moderator_rule_memory_id(candidate: Any) -> Any:
    return _get(
        candidate,
        "moderator_rule_memory_id",
        "moderatorRuleMemoryId",
        "rule_memory_id",
        "ruleMemoryId",
    )


def _has_conflict_flag(candidate: Any) -> bool:
    return any(
        _truthy(_get(candidate, name))
        for name in (
            "has_conflict",
            "hasConflict",
            "conflict",
            "characteristics_conflict",
            "characteristicsConflict",
            "price_unit_conflict",
            "priceUnitConflict",
            "brand_conflict",
            "brandConflict",
            "category_conflict",
            "categoryConflict",
        )
    )


def _matching_conflict_reason(catalog_product: Any, material_candidate: Any, policy: SafeAutomationPolicy) -> str | None:
    if policy.auto_link.require_no_characteristic_conflict and _has_conflict_flag(material_candidate):
        return "Candidate has conflict flags; moderator must review before linking to Material."

    if policy.auto_link.require_brand_or_manufacturer_match_if_present:
        product_brand = _get(catalog_product, "raw_brand", "rawBrand", "brand")
        candidate_brand = _get(material_candidate, "brand", "candidate_brand", "candidateBrand")
        product_manufacturer = _get(catalog_product, "raw_manufacturer", "rawManufacturer", "manufacturer")
        candidate_manufacturer = _get(material_candidate, "manufacturer", "candidate_manufacturer", "candidateManufacturer")
        if product_brand and candidate_brand and _normalized(product_brand) != _normalized(candidate_brand):
            return "Brand differs between CatalogProduct and Material candidate."
        if product_manufacturer and candidate_manufacturer and _normalized(product_manufacturer) != _normalized(candidate_manufacturer):
            return "Manufacturer differs between CatalogProduct and Material candidate."

    if policy.auto_link.require_unit_match_if_present:
        product_unit = _get(catalog_product, "unit", "raw_unit", "rawUnit")
        candidate_unit = _get(material_candidate, "unit", "base_unit", "baseUnit")
        if product_unit and candidate_unit and _normalized(product_unit) != _normalized(candidate_unit):
            return "Unit differs between CatalogProduct and Material candidate."

    if policy.auto_link.require_category_match_if_present:
        product_category = _get(catalog_product, "category_id", "categoryId", "raw_category", "rawCategory", "category")
        candidate_category = _get(material_candidate, "category_id", "categoryId", "category")
        if product_category and candidate_category and _normalized(product_category) != _normalized(candidate_category):
            return "Category differs between CatalogProduct and Material candidate."

    return None


canAutoUpdatePrice = can_auto_update_price
canAutoLinkToMaterial = can_auto_link_to_material
canCreateDraftMaterial = can_create_draft_material
shouldGoToBatchModeration = should_go_to_batch_moderation
shouldRequireManualReview = should_require_manual_review
getAutomationReason = get_automation_reason


__all__ = [
    "DEFAULT_SAFE_AUTOMATION_POLICY",
    "can_auto_update_price",
    "can_auto_link_to_material",
    "can_create_draft_material",
    "should_go_to_batch_moderation",
    "should_require_manual_review",
    "get_automation_reason",
    "canAutoUpdatePrice",
    "canAutoLinkToMaterial",
    "canCreateDraftMaterial",
    "shouldGoToBatchModeration",
    "shouldRequireManualReview",
    "getAutomationReason",
]
