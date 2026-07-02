from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog_product import CatalogProduct
from app.models.enums import AdminDecision, CatalogProductStatus, MatchCandidateStatus
from app.models.material import Material
from app.models.material_match_candidate import MaterialMatchCandidate
from app.schemas.material_hub_contracts import (
    BatchModerationAction,
    BatchModerationDecision,
    BatchModerationQueue,
    BatchRuleSuggestion,
    CandidateGroup,
)
from app.services.material_normalization_rules import normalize_material_title
from app.services.rule_memory import build_rule_patterns, remember_material_rule


BATCH_GROUP_FIELDS = [
    "sourceCode",
    "atomCategoryPath",
    "matchedMaterialId",
    "brand",
    "manufacturer",
    "dimensions",
    "unit",
    "normalizationRule",
    "reviewReason",
]

CONFIRM_ACTIONS = {
    BatchModerationAction.CONFIRM_GROUP,
    BatchModerationAction.CONFIRM_SELECTED,
    BatchModerationAction.CREATE_RULE,
}


def build_batch_moderation_queue(
    candidates: Iterable[Any],
    *,
    minimum_group_size: int = 3,
    now: datetime | None = None,
) -> BatchModerationQueue:
    collected = list(candidates)
    buckets: dict[str, list[Any]] = {}
    keys: dict[str, dict[str, Any]] = {}
    for candidate in collected:
        group_key = build_candidate_group_key(candidate)
        group_id = _group_id(group_key)
        buckets.setdefault(group_id, []).append(candidate)
        keys[group_id] = group_key

    groups: list[CandidateGroup] = []
    manual_review_ids: list[UUID] = []
    for group_id, grouped_candidates in buckets.items():
        if len(grouped_candidates) < minimum_group_size:
            manual_review_ids.extend(_candidate_id(candidate) for candidate in grouped_candidates if _candidate_id(candidate))
            continue
        group = build_candidate_group(grouped_candidates, group_id=group_id, group_key=keys[group_id])
        group.rule_suggestion = build_batch_rule_suggestion(group)
        groups.append(group)

    groups.sort(key=lambda item: (-item.candidate_count, item.source_code or "", item.atom_category_path or ""))
    return BatchModerationQueue(
        queue_id=f"batch-moderation-{_short_hash([group.group_id for group in groups])}",
        groups=groups,
        manualReviewCandidateIds=manual_review_ids,
        totalCandidates=len(collected),
        groupByFields=BATCH_GROUP_FIELDS,
        createdAt=now or datetime.now(UTC),
        notes=[
            "Batch moderation groups candidates only; it does not create ACTIVE Material.",
            "Group confirmation links candidates to an existing Material and writes constrained RuleMemory.",
            "Moderator can split, reject, confirm selected candidates, or send the group back to manual review.",
        ],
    )


def build_candidate_group(
    candidates: Iterable[Any],
    *,
    group_id: str | None = None,
    group_key: dict[str, Any] | None = None,
) -> CandidateGroup:
    grouped = list(candidates)
    first_key = group_key or (build_candidate_group_key(grouped[0]) if grouped else {})
    candidate_ids = [_candidate_id(candidate) for candidate in grouped if _candidate_id(candidate)]
    confidence_values = [_candidate_confidence(candidate) for candidate in grouped if _candidate_confidence(candidate) is not None]
    confidence_min = min(confidence_values) if confidence_values else None
    confidence_max = max(confidence_values) if confidence_values else None
    confidence_avg = (
        sum(confidence_values, Decimal("0")) / Decimal(len(confidence_values))
        if confidence_values
        else None
    )
    matched_material_id = _uuid_or_none(first_key.get("matchedMaterialId"))
    can_confirm_safely = bool(matched_material_id and candidate_ids)

    return CandidateGroup(
        group_id=group_id or _group_id(first_key),
        group_key=first_key,
        candidate_ids=candidate_ids,
        sourceCode=first_key.get("sourceCode"),
        atomCategoryPath=first_key.get("atomCategoryPath"),
        matchedMaterialId=matched_material_id,
        brand=first_key.get("brand"),
        manufacturer=first_key.get("manufacturer"),
        dimensions=first_key.get("dimensions"),
        unit=first_key.get("unit"),
        normalizationRule=first_key.get("normalizationRule"),
        reviewReason=first_key.get("reviewReason"),
        candidateCount=len(grouped),
        confidenceMin=confidence_min,
        confidenceMax=confidence_max,
        confidenceAvg=confidence_avg,
        groupingReasons=_grouping_reasons(first_key),
        canConfirmSafely=can_confirm_safely,
        activeMaterialCreationAllowed=False,
    )


def build_candidate_group_key(candidate: Any) -> dict[str, Any]:
    product = _get(candidate, "catalog_product", "catalogProduct")
    material_id = _get(candidate, "candidate_material_id", "candidateMaterialId")
    product_material_id = _get(product, "material_id", "materialId")
    material = _get(candidate, "candidate_material", "candidateMaterial")
    raw_name = _get(product, "raw_name", "rawName") or _get(candidate, "raw_name", "rawName")
    raw_category = _get(product, "raw_category", "rawCategory") or _get(candidate, "raw_category", "rawCategory")
    brand = _get(product, "raw_brand", "rawBrand") or _get(material, "brand")
    manufacturer = _get(product, "raw_manufacturer", "rawManufacturer") or _get(material, "manufacturer")
    unit = _get(product, "unit")
    normalization = normalize_material_title(
        raw_name,
        brand=brand,
        manufacturer=manufacturer,
        category=raw_category,
        unit=unit,
        region=_get(product, "region"),
    )
    source = _get(product, "source")
    source_code = (
        _get(candidate, "sourceCode", "source_code")
        or _get(product, "sourceCode", "source_code")
        or _get(source, "name")
        or _string_or_none(_get(product, "source_id", "sourceId"))
    )
    matched_material_id = material_id or product_material_id

    return {
        "sourceCode": _clean_key_value(source_code),
        "atomCategoryPath": _clean_key_value(raw_category),
        "matchedMaterialId": _string_or_none(matched_material_id),
        "brand": _clean_key_value(brand),
        "manufacturer": _clean_key_value(manufacturer),
        "dimensions": normalization.extracted.get("size") or normalization.extracted.get("diameter"),
        "unit": normalization.normalized_unit or _clean_key_value(unit),
        "normalizationRule": normalization.direction_code,
        "reviewReason": _clean_review_reason(_get(candidate, "match_reason", "matchReason")),
    }


def build_batch_rule_suggestion(group: CandidateGroup) -> BatchRuleSuggestion:
    confidence_boost = _confidence_boost_for_group(group)
    allowed_scope = {
        "sourceCode": group.source_code,
        "atomCategoryPath": group.atom_category_path,
        "materialType": group.normalization_rule,
        "brand": group.brand,
        "manufacturer": group.manufacturer,
        "unit": group.unit,
    }
    rule_payload = {
        "groupId": group.group_id,
        "groupKey": group.group_key,
        "candidateIds": [str(candidate_id) for candidate_id in group.candidate_ids],
        "targetMaterialId": str(group.matched_material_id) if group.matched_material_id else None,
        "confidenceBoost": str(confidence_boost),
        "allowedScope": allowed_scope,
        "reviewRequiredAt": (datetime.now(UTC) + timedelta(days=90)).isoformat(),
    }
    return BatchRuleSuggestion(
        suggestion_id=f"batch-rule-{group.group_id}",
        group_id=group.group_id,
        suggested_rule_key=_short_hash(group.group_key),
        sourceCode=group.source_code,
        atomCategoryPath=group.atom_category_path,
        materialType=group.normalization_rule,
        targetMaterialId=group.matched_material_id,
        normalizationRule=group.normalization_rule,
        confidenceBoost=confidence_boost,
        allowedScope=allowed_scope,
        reviewRequiredAt=datetime.now(UTC) + timedelta(days=90),
        reasons=[
            "The rule is scoped to this source/category/material type group.",
            "A single moderator decision must not become a global rule.",
            "RuleMemory remains visible as the reason for future auto-link decisions.",
        ],
        ruleMemoryPayload=rule_payload,
    )


def build_rule_memory_payload_for_candidate(
    candidate: Any,
    *,
    group: CandidateGroup | None = None,
    decision: BatchModerationDecision | None = None,
    moderator_id: UUID | None = None,
    applied_rule: str | None = None,
) -> dict[str, Any]:
    product = _get(candidate, "catalog_product", "catalogProduct")
    group_key = group.group_key if group else build_candidate_group_key(candidate)
    raw_name = _get(product, "raw_name", "rawName")
    normalized_name = _get(product, "normalized_name", "normalizedName")
    target_material_id = (
        _get(decision, "target_material_id", "targetMaterialId")
        or group_key.get("matchedMaterialId")
        or _get(candidate, "candidate_material_id", "candidateMaterialId")
    )
    return {
        "incoming": {
            "rawName": raw_name,
            "rawCategory": _get(product, "raw_category", "rawCategory"),
            "sourceCode": group_key.get("sourceCode"),
            "unit": _get(product, "unit"),
            "brand": _get(product, "raw_brand", "rawBrand"),
            "manufacturer": _get(product, "raw_manufacturer", "rawManufacturer"),
        },
        "normalized": {
            "normalizedName": normalized_name,
            "groupKey": group_key,
            "normalizationRule": group_key.get("normalizationRule"),
        },
        "target": {
            "materialId": str(target_material_id) if target_material_id else None,
            "matchedMaterialId": group_key.get("matchedMaterialId"),
        },
        "appliedRule": _enum_value(applied_rule or _get(decision, "action") or "BATCH_MODERATION"),
        "confirmedBy": str(moderator_id or _get(decision, "moderator_id", "moderatorId") or "module01_moderator"),
        "confirmedAt": datetime.now(UTC).isoformat(),
        "sourceCode": group_key.get("sourceCode"),
        "atomCategoryPath": group_key.get("atomCategoryPath"),
        "materialType": group_key.get("normalizationRule"),
        "confidenceBoost": str(
            _get(_get(decision, "rule_suggestion", "ruleSuggestion"), "confidence_boost", "confidenceBoost")
            or _confidence_boost_for_count(_get(group, "candidate_count", "candidateCount") or 1)
        ),
        "reviewRequiredAt": _datetime_string(
            _get(_get(decision, "rule_suggestion", "ruleSuggestion"), "review_required_at", "reviewRequiredAt")
            or (datetime.now(UTC) + timedelta(days=90))
        ),
        "ruleScope": {
            "sourceCode": group_key.get("sourceCode"),
            "atomCategoryPath": group_key.get("atomCategoryPath"),
            "materialType": group_key.get("normalizationRule"),
            "unit": group_key.get("unit"),
            "brand": group_key.get("brand"),
            "manufacturer": group_key.get("manufacturer"),
        },
    }


async def apply_batch_moderation_decision(
    db: AsyncSession,
    candidates: Iterable[MaterialMatchCandidate],
    decision: BatchModerationDecision,
    *,
    moderator_id: UUID | None = None,
) -> BatchModerationDecision:
    loaded_candidates = [candidate for candidate in candidates if _candidate_selected(candidate, decision)]
    before = [_candidate_snapshot(candidate) for candidate in loaded_candidates]
    rule_memory_written = False

    if decision.action in CONFIRM_ACTIONS:
        target_material_id = decision.target_material_id or _first_matched_material_id(loaded_candidates)
        if not target_material_id:
            raise ValueError("Batch confirmation requires target_material_id or matchedMaterialId.")
        material = await _load_material(db, target_material_id)
        group = build_candidate_group(loaded_candidates) if loaded_candidates else None
        for candidate in loaded_candidates:
            product = candidate.catalog_product
            if product is not None:
                product.material_id = material.id
                product.status = CatalogProductStatus.ACTIVE
                db.add(product)
            candidate.candidate_material_id = material.id
            candidate.status = MatchCandidateStatus.APPROVED
            candidate.admin_decision = AdminDecision.APPROVE
            db.add(candidate)
            payload = build_rule_memory_payload_for_candidate(
                candidate,
                group=group,
                decision=decision,
                moderator_id=moderator_id,
            )
            await remember_material_rule(
                db,
                material,
                build_rule_patterns(
                    _get(product, "raw_name", "rawName"),
                    _get(product, "normalized_name", "normalizedName"),
                    _get(product, "raw_category", "rawCategory"),
                ),
                source="batch_moderation",
                attributes=payload,
                confidence_boost=Decimal(str(payload["confidenceBoost"])),
                rule_scope=payload["ruleScope"],
                confirmed_by=payload["confirmedBy"],
                review_required_at=payload["reviewRequiredAt"],
            )
            rule_memory_written = True

    elif decision.action == BatchModerationAction.REJECT_GROUP:
        for candidate in loaded_candidates:
            candidate.status = MatchCandidateStatus.REJECTED
            candidate.admin_decision = AdminDecision.REJECT
            if decision.reason:
                candidate.match_reason = f"{candidate.match_reason or ''}\nBatch reject: {decision.reason}".strip()
            db.add(candidate)

    elif decision.action in {
        BatchModerationAction.SPLIT_GROUP,
        BatchModerationAction.SEND_TO_MANUAL_REVIEW,
        BatchModerationAction.ROLLBACK_TO_REVIEW,
    }:
        for candidate in loaded_candidates:
            candidate.status = MatchCandidateStatus.NEEDS_REVIEW
            candidate.admin_decision = AdminDecision.SEND_TO_REVIEW
            db.add(candidate)

    else:
        raise ValueError(f"Unsupported batch moderation action: {decision.action}")

    await db.flush()
    after = [_candidate_snapshot(candidate) for candidate in loaded_candidates]
    return decision.model_copy(
        update={
            "candidate_ids": [_candidate_id(candidate) for candidate in loaded_candidates if _candidate_id(candidate)],
            "old_value": {"candidates": before},
            "new_value": {"candidates": after},
            "moderator_id": moderator_id or decision.moderator_id,
            "decided_at": datetime.now(UTC),
            "creates_active_material": False,
            "rule_memory_written": rule_memory_written,
            "rollback_available": True,
        }
    )


def _candidate_selected(candidate: Any, decision: BatchModerationDecision) -> bool:
    candidate_id = _candidate_id(candidate)
    selected_ids = set(decision.selected_candidate_ids or decision.candidate_ids or [])
    return not selected_ids or candidate_id in selected_ids


async def _load_material(db: AsyncSession, material_id: UUID) -> Material:
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalar_one_or_none()
    if material is None:
        raise ValueError("Target Material for batch moderation was not found.")
    return material


def _first_matched_material_id(candidates: list[Any]) -> UUID | None:
    for candidate in candidates:
        material_id = _uuid_or_none(_get(candidate, "candidate_material_id", "candidateMaterialId"))
        if material_id:
            return material_id
    return None


def _candidate_snapshot(candidate: Any) -> dict[str, Any]:
    product = _get(candidate, "catalog_product", "catalogProduct")
    return {
        "candidateId": _string_or_none(_candidate_id(candidate)),
        "catalogProductId": _string_or_none(_get(candidate, "catalog_product_id", "catalogProductId")),
        "materialId": _string_or_none(_get(candidate, "candidate_material_id", "candidateMaterialId")),
        "status": _enum_value(_get(candidate, "status")),
        "adminDecision": _enum_value(_get(candidate, "admin_decision", "adminDecision")),
        "rawName": _get(product, "raw_name", "rawName"),
        "normalizedName": _get(product, "normalized_name", "normalizedName"),
    }


def _candidate_id(candidate: Any) -> UUID | None:
    return _uuid_or_none(_get(candidate, "id"))


def _candidate_confidence(candidate: Any) -> Decimal | None:
    value = _get(candidate, "match_score", "matchScore")
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _grouping_reasons(group_key: dict[str, Any]) -> list[str]:
    reasons = []
    for field_name in BATCH_GROUP_FIELDS:
        value = group_key.get(field_name)
        if value not in (None, "", []):
            reasons.append(f"{field_name}: {value}")
    return reasons


def _confidence_boost_for_group(group: CandidateGroup) -> Decimal:
    return _confidence_boost_for_count(group.candidate_count)


def _confidence_boost_for_count(count: int) -> Decimal:
    if count >= 25:
        return Decimal("0.20")
    if count >= 10:
        return Decimal("0.15")
    return Decimal("0.10")


def _group_id(group_key: dict[str, Any]) -> str:
    return f"cg_{_short_hash(group_key)}"


def _short_hash(value: Any) -> str:
    payload = json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _clean_review_reason(value: Any) -> str | None:
    text = _clean_key_value(value)
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    return text[:120]


def _clean_key_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(_enum_value(value)).strip()
    return text or None


def _uuid_or_none(value: Any) -> UUID | None:
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(_enum_value(value))


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _get(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _jsonable(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return _enum_value(value)


def _datetime_string(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def new_batch_decision(
    action: BatchModerationAction,
    *,
    group: CandidateGroup | None = None,
    selected_candidate_ids: list[UUID] | None = None,
    target_material_id: UUID | None = None,
    reason: str | None = None,
    moderator_id: UUID | None = None,
) -> BatchModerationDecision:
    return BatchModerationDecision(
        decision_id=f"batch-decision-{uuid4()}",
        action=action,
        group_id=group.group_id if group else None,
        candidate_ids=group.candidate_ids if group else [],
        selectedCandidateIds=selected_candidate_ids or [],
        targetMaterialId=target_material_id or (group.matched_material_id if group else None),
        ruleSuggestion=group.rule_suggestion if group else None,
        reason=reason,
        moderatorId=moderator_id,
        decidedAt=datetime.now(UTC),
        rollbackAvailable=True,
        createsActiveMaterial=False,
    )
