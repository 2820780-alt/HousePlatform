from __future__ import annotations

import json
import uuid
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_levels import AccessLevel
from app.models.knowledge_resource import KnowledgeResource
from app.models.material_document import MaterialDocument
from app.models.module2_knowledge import CompatibilityRule, ConsumptionNorm, KnowledgeRule
from app.models.module2_technology import (
    MODULE2_OWNER_CODE,
    Technology,
    TechnologyEvidenceReference,
    TechnologyLayer,
    TechnologyMaterialRequirement,
    TechnologyNode,
    TechnologyWorkStep,
)
from app.schemas.module2_knowledge import (
    CompatibilityEvaluation,
    CompatibilityRelation,
    CompatibilityRuleDraftInput,
    ConditionOperator,
    ConditionSource,
    ConsumptionNormDraftInput,
    EvaluationState,
    EvidenceTargetKind,
    KnowledgeEvidenceInput,
    KnowledgeRuleDraftInput,
    KnowledgeRuleEvaluation,
    KnowledgeRuleOutcome,
    KnowledgeScopeKind,
    KnowledgeSelectorInput,
    KnowledgeSelectorKind,
    StructuredCondition,
)
from app.schemas.module2_technology import TechnologyLifecycle
from app.services.module1_export_packages import Module2TechnologyInputPackage
from app.services.module1_unit_conversion_registry import normalize_unit
from app.services.module2_technology_foundation import require_module2_access


KnowledgeEntity = ConsumptionNorm | CompatibilityRule | KnowledgeRule
EvidenceTarget = (
    Technology
    | TechnologyLayer
    | TechnologyMaterialRequirement
    | TechnologyNode
    | TechnologyWorkStep
    | KnowledgeEntity
)

_ALLOWED_TRANSITIONS = {
    TechnologyLifecycle.DRAFT: {TechnologyLifecycle.REVIEW},
    TechnologyLifecycle.REVIEW: {
        TechnologyLifecycle.DRAFT,
        TechnologyLifecycle.ACTIVE,
    },
    TechnologyLifecycle.ACTIVE: {TechnologyLifecycle.ARCHIVED},
    TechnologyLifecycle.ARCHIVED: set(),
}


class Module2KnowledgeError(ValueError):
    pass


def create_consumption_norm_draft(
    technology: Technology,
    data: ConsumptionNormDraftInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
) -> ConsumptionNorm:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    command = _as_command(data, ConsumptionNormDraftInput)
    _validate_norm_scope(technology, command)
    _validate_selector_against_technology(technology, command.resource)

    norm = ConsumptionNorm(
        id=uuid.uuid4(),
        technology_id=technology.id,
        norm_code=command.norm_code,
        revision=1,
        scope_layer_id=command.scope_layer_id,
        scope_requirement_id=command.scope_requirement_id,
        scope_work_step_id=command.scope_work_step_id,
        resource_kind=command.resource.selector_kind.value,
        resource_selector=_selector_payload(command.resource),
        basis_quantity=command.basis_quantity,
        basis_unit=_canonical_unit(command.basis_unit),
        consumption_quantity=command.consumption_quantity,
        consumption_unit=_canonical_unit(command.consumption_unit),
        conditions=_condition_payload(command.conditions),
        status=TechnologyLifecycle.DRAFT.value,
        owner_module_code=MODULE2_OWNER_CODE,
        source_kind=command.source_kind,
        blockers=list(_unique(command.blockers)),
        created_by_user_id=created_by_user_id,
    )
    technology.consumption_norms.append(norm)
    return norm


def create_compatibility_rule_draft(
    technology: Technology,
    data: CompatibilityRuleDraftInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
) -> CompatibilityRule:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    command = _as_command(data, CompatibilityRuleDraftInput)
    _validate_selector_against_technology(technology, command.subject)
    _validate_selector_against_technology(technology, command.object)

    rule = CompatibilityRule(
        id=uuid.uuid4(),
        technology_id=technology.id,
        rule_code=command.rule_code,
        revision=1,
        subject_kind=command.subject.selector_kind.value,
        subject_selector=_selector_payload(command.subject),
        object_kind=command.object.selector_kind.value,
        object_selector=_selector_payload(command.object),
        relation=command.relation.value,
        conditions=_condition_payload(command.conditions),
        reason=command.reason,
        is_symmetric=command.is_symmetric,
        status=TechnologyLifecycle.DRAFT.value,
        owner_module_code=MODULE2_OWNER_CODE,
        source_kind=command.source_kind,
        blockers=list(_unique(command.blockers)),
        created_by_user_id=created_by_user_id,
    )
    technology.compatibility_rules.append(rule)
    return rule


def create_knowledge_rule_draft(
    technology: Technology,
    data: KnowledgeRuleDraftInput | Mapping[str, Any],
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
) -> KnowledgeRule:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    command = _as_command(data, KnowledgeRuleDraftInput)
    _validate_rule_scope(technology, command.scope_kind, command.scope_reference)

    rule = KnowledgeRule(
        id=uuid.uuid4(),
        technology_id=technology.id,
        rule_code=command.rule_code,
        revision=1,
        scope_kind=command.scope_kind.value,
        scope_reference=command.scope_reference,
        conditions=_condition_payload(command.conditions),
        outcome_type=command.outcome_type.value,
        outcome_payload=deepcopy(command.outcome_payload),
        status=TechnologyLifecycle.DRAFT.value,
        owner_module_code=MODULE2_OWNER_CODE,
        source_kind=command.source_kind,
        blockers=list(_unique(command.blockers)),
        created_by_user_id=created_by_user_id,
    )
    technology.knowledge_rules.append(rule)
    return rule


def attach_evidence_reference(
    technology: Technology,
    target: EvidenceTarget,
    data: KnowledgeEvidenceInput | Mapping[str, Any],
    *,
    actor_role_code: str,
) -> TechnologyEvidenceReference:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    command = _as_command(data, KnowledgeEvidenceInput)
    target_kind, target_reference = _evidence_target(technology, target)

    target_status = getattr(target, "status", technology.status)
    if target_status != TechnologyLifecycle.DRAFT.value:
        raise Module2KnowledgeError("evidence can only be changed on DRAFT knowledge")

    reference = TechnologyEvidenceReference(
        id=uuid.uuid4(),
        technology_id=technology.id,
        document_id=command.document_id,
        knowledge_resource_id=command.knowledge_resource_id,
        target_kind=target_kind.value,
        target_reference=target_reference,
        interpretation=command.interpretation,
    )
    technology.evidence_references.append(reference)
    return reference


async def verify_evidence_references(
    db: AsyncSession,
    references: Sequence[TechnologyEvidenceReference],
) -> frozenset[uuid.UUID]:
    document_ids = {item.document_id for item in references if item.document_id}
    resource_ids = {
        item.knowledge_resource_id
        for item in references
        if item.knowledge_resource_id
    }
    existing_documents: set[uuid.UUID] = set()
    existing_resources: set[uuid.UUID] = set()

    if document_ids:
        result = await db.execute(
            select(MaterialDocument.id).where(MaterialDocument.id.in_(document_ids))
        )
        existing_documents = set(result.scalars().all())
    if resource_ids:
        result = await db.execute(
            select(KnowledgeResource.id).where(KnowledgeResource.id.in_(resource_ids))
        )
        existing_resources = set(result.scalars().all())

    return frozenset(
        item.id
        for item in references
        if (
            item.document_id in existing_documents
            or item.knowledge_resource_id in existing_resources
        )
    )



def validate_knowledge_activation(
    entity: KnowledgeEntity,
    technology: Technology,
    evidence_references: Sequence[TechnologyEvidenceReference],
    *,
    verified_evidence_reference_ids: Iterable[uuid.UUID] = (),
    input_package: Module2TechnologyInputPackage | None = None,
) -> tuple[str, ...]:
    blockers = list(entity.blockers or ())
    if entity.technology_id != technology.id:
        blockers.append("entity_belongs_to_another_technology")
    if technology.status != TechnologyLifecycle.ACTIVE.value:
        blockers.append("technology_not_active")
    blockers.extend(f"technology_input:{item}" for item in technology.input_blockers or ())
    blockers.extend(
        f"technology_missing_field:{item}"
        for item in technology.input_missing_fields or ()
    )

    target_kind = _entity_target_kind(entity)
    linked = _target_evidence(evidence_references, target_kind, entity.id)
    if not linked:
        blockers.append("missing_evidence")
    else:
        verified = set(verified_evidence_reference_ids)
        for reference in linked:
            if reference.id not in verified:
                blockers.append(f"broken_or_unverified_evidence:{reference.id}")

    conditions = [
        StructuredCondition.model_validate(item)
        for item in entity.conditions or ()
    ]
    required_m1_fields = {
        item.field
        for item in conditions
        if item.source == ConditionSource.M1_MATERIAL_PROPERTY
        and item.required_for_activation
    }
    if required_m1_fields:
        properties = _module1_properties(input_package)
        for field in sorted(required_m1_fields):
            found, _ = _lookup(properties, field)
            if not found:
                blockers.append(f"missing_m1_property:{field}")

    return _unique(blockers)


def transition_consumption_norm(
    norm: ConsumptionNorm,
    target: TechnologyLifecycle | str,
    *,
    technology: Technology,
    evidence_references: Sequence[TechnologyEvidenceReference],
    actor_role_code: str,
    verified_evidence_reference_ids: Iterable[uuid.UUID] = (),
    input_package: Module2TechnologyInputPackage | None = None,
) -> ConsumptionNorm:
    _transition_entity(
        norm,
        target,
        technology=technology,
        evidence_references=evidence_references,
        actor_role_code=actor_role_code,
        verified_evidence_reference_ids=verified_evidence_reference_ids,
        input_package=input_package,
    )
    return norm


def transition_compatibility_rule(
    rule: CompatibilityRule,
    target: TechnologyLifecycle | str,
    *,
    technology: Technology,
    evidence_references: Sequence[TechnologyEvidenceReference],
    actor_role_code: str,
    verified_evidence_reference_ids: Iterable[uuid.UUID] = (),
    input_package: Module2TechnologyInputPackage | None = None,
    peer_rules: Sequence[CompatibilityRule] = (),
) -> CompatibilityRule:
    target_status = TechnologyLifecycle(target)
    if target_status == TechnologyLifecycle.ACTIVE:
        conflicts = detect_compatibility_conflicts(rule, peer_rules)
        if conflicts:
            raise Module2KnowledgeError(
                "activation blocked by conflicting compatibility rules: "
                + ", ".join(str(item) for item in conflicts)
            )
    _transition_entity(
        rule,
        target_status,
        technology=technology,
        evidence_references=evidence_references,
        actor_role_code=actor_role_code,
        verified_evidence_reference_ids=verified_evidence_reference_ids,
        input_package=input_package,
    )
    return rule


def transition_knowledge_rule(
    rule: KnowledgeRule,
    target: TechnologyLifecycle | str,
    *,
    technology: Technology,
    evidence_references: Sequence[TechnologyEvidenceReference],
    actor_role_code: str,
    verified_evidence_reference_ids: Iterable[uuid.UUID] = (),
    input_package: Module2TechnologyInputPackage | None = None,
    peer_rules: Sequence[KnowledgeRule] = (),
) -> KnowledgeRule:
    target_status = TechnologyLifecycle(target)
    if target_status == TechnologyLifecycle.ACTIVE:
        conflicts = detect_knowledge_rule_conflicts(rule, peer_rules)
        if conflicts:
            raise Module2KnowledgeError(
                "activation blocked by conflicting knowledge rules: "
                + ", ".join(str(item) for item in conflicts)
            )
    _transition_entity(
        rule,
        target_status,
        technology=technology,
        evidence_references=evidence_references,
        actor_role_code=actor_role_code,
        verified_evidence_reference_ids=verified_evidence_reference_ids,
        input_package=input_package,
    )
    return rule


def _transition_entity(
    entity: KnowledgeEntity,
    target: TechnologyLifecycle | str,
    *,
    technology: Technology,
    evidence_references: Sequence[TechnologyEvidenceReference],
    actor_role_code: str,
    verified_evidence_reference_ids: Iterable[uuid.UUID],
    input_package: Module2TechnologyInputPackage | None,
) -> None:
    current = TechnologyLifecycle(entity.status)
    target_status = TechnologyLifecycle(target)
    if target_status not in _ALLOWED_TRANSITIONS[current]:
        raise Module2KnowledgeError(
            f"unsupported knowledge lifecycle transition: "
            f"{current.value} -> {target_status.value}"
        )

    required_access = AccessLevel.EDIT
    if target_status in {TechnologyLifecycle.ACTIVE, TechnologyLifecycle.DRAFT}:
        required_access = AccessLevel.APPROVE
    elif target_status == TechnologyLifecycle.ARCHIVED:
        required_access = AccessLevel.ADMIN
    require_module2_access(actor_role_code, required_access)

    if target_status == TechnologyLifecycle.ACTIVE:
        blockers = validate_knowledge_activation(
            entity,
            technology,
            evidence_references,
            verified_evidence_reference_ids=verified_evidence_reference_ids,
            input_package=input_package,
        )
        if blockers:
            raise Module2KnowledgeError(
                "knowledge activation blocked: " + ", ".join(blockers)
            )
    entity.status = target_status.value


def create_consumption_norm_revision(
    norm: ConsumptionNorm,
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
) -> ConsumptionNorm:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    _require_active(norm)
    return ConsumptionNorm(
        id=uuid.uuid4(),
        technology_id=norm.technology_id,
        norm_code=norm.norm_code,
        revision=norm.revision + 1,
        scope_layer_id=norm.scope_layer_id,
        scope_requirement_id=norm.scope_requirement_id,
        scope_work_step_id=norm.scope_work_step_id,
        resource_kind=norm.resource_kind,
        resource_selector=deepcopy(norm.resource_selector),
        basis_quantity=norm.basis_quantity,
        basis_unit=norm.basis_unit,
        consumption_quantity=norm.consumption_quantity,
        consumption_unit=norm.consumption_unit,
        conditions=deepcopy(norm.conditions),
        status=TechnologyLifecycle.DRAFT.value,
        owner_module_code=MODULE2_OWNER_CODE,
        source_kind=norm.source_kind,
        blockers=deepcopy(norm.blockers),
        supersedes=norm,
        created_by_user_id=created_by_user_id,
    )


def create_compatibility_rule_revision(
    rule: CompatibilityRule,
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
) -> CompatibilityRule:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    _require_active(rule)
    return CompatibilityRule(
        id=uuid.uuid4(),
        technology_id=rule.technology_id,
        rule_code=rule.rule_code,
        revision=rule.revision + 1,
        subject_kind=rule.subject_kind,
        subject_selector=deepcopy(rule.subject_selector),
        object_kind=rule.object_kind,
        object_selector=deepcopy(rule.object_selector),
        relation=rule.relation,
        conditions=deepcopy(rule.conditions),
        reason=rule.reason,
        is_symmetric=rule.is_symmetric,
        status=TechnologyLifecycle.DRAFT.value,
        owner_module_code=MODULE2_OWNER_CODE,
        source_kind=rule.source_kind,
        blockers=deepcopy(rule.blockers),
        supersedes=rule,
        created_by_user_id=created_by_user_id,
    )


def create_knowledge_rule_revision(
    rule: KnowledgeRule,
    *,
    actor_role_code: str,
    created_by_user_id: uuid.UUID | None = None,
) -> KnowledgeRule:
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    _require_active(rule)
    return KnowledgeRule(
        id=uuid.uuid4(),
        technology_id=rule.technology_id,
        rule_code=rule.rule_code,
        revision=rule.revision + 1,
        scope_kind=rule.scope_kind,
        scope_reference=rule.scope_reference,
        conditions=deepcopy(rule.conditions),
        outcome_type=rule.outcome_type,
        outcome_payload=deepcopy(rule.outcome_payload),
        status=TechnologyLifecycle.DRAFT.value,
        owner_module_code=MODULE2_OWNER_CODE,
        source_kind=rule.source_kind,
        blockers=deepcopy(rule.blockers),
        supersedes=rule,
        created_by_user_id=created_by_user_id,
    )



def evaluate_compatibility_rules(
    rules: Sequence[CompatibilityRule],
    subject: KnowledgeSelectorInput | Mapping[str, Any],
    object_: KnowledgeSelectorInput | Mapping[str, Any],
    *,
    evidence_references: Sequence[TechnologyEvidenceReference] = (),
    input_package: Module2TechnologyInputPackage | None = None,
    context: Mapping[str, Any] | None = None,
) -> CompatibilityEvaluation:
    subject_selector = _as_command(subject, KnowledgeSelectorInput)
    object_selector = _as_command(object_, KnowledgeSelectorInput)
    applicable: list[CompatibilityRule] = []
    unresolved = False
    blockers: list[str] = []

    for rule in rules:
        if rule.status != TechnologyLifecycle.ACTIVE.value:
            continue
        if not _compatibility_selector_match(rule, subject_selector, object_selector):
            continue
        state, condition_blockers = evaluate_structured_conditions(
            rule.conditions,
            input_package=input_package,
            context=context,
        )
        blockers.extend(condition_blockers)
        if state == EvaluationState.APPLIES:
            applicable.append(rule)
        elif state == EvaluationState.UNKNOWN:
            unresolved = True

    rule_ids = tuple(item.id for item in applicable)
    evidence_ids = _evidence_ids_for_entities(
        evidence_references,
        EvidenceTargetKind.COMPATIBILITY_RULE,
        rule_ids,
    )
    relations = {CompatibilityRelation(item.relation) for item in applicable}

    if CompatibilityRelation.INCOMPATIBLE in relations and relations.intersection(
        {CompatibilityRelation.COMPATIBLE, CompatibilityRelation.CONDITIONAL}
    ):
        return CompatibilityEvaluation(
            state=EvaluationState.REVIEW,
            relation=CompatibilityRelation.UNKNOWN,
            blockers=_unique((*blockers, "conflicting_active_compatibility_rules")),
            matched_rule_ids=rule_ids,
            evidence_reference_ids=evidence_ids,
        )
    if not applicable:
        reason = "insufficient_evidence" if unresolved else "no_matching_active_rule"
        return CompatibilityEvaluation(
            state=EvaluationState.UNKNOWN,
            blockers=_unique((*blockers, reason)),
        )
    if CompatibilityRelation.UNKNOWN in relations:
        return CompatibilityEvaluation(
            state=EvaluationState.UNKNOWN,
            blockers=_unique((*blockers, "insufficient_evidence")),
            matched_rule_ids=rule_ids,
            evidence_reference_ids=evidence_ids,
        )

    relation = (
        CompatibilityRelation.INCOMPATIBLE
        if CompatibilityRelation.INCOMPATIBLE in relations
        else CompatibilityRelation.CONDITIONAL
        if CompatibilityRelation.CONDITIONAL in relations
        else CompatibilityRelation.COMPATIBLE
    )
    return CompatibilityEvaluation(
        state=EvaluationState.APPLIES,
        relation=relation,
        blockers=_unique(blockers),
        matched_rule_ids=rule_ids,
        evidence_reference_ids=evidence_ids,
    )


def evaluate_knowledge_rule(
    rule: KnowledgeRule,
    *,
    evidence_references: Sequence[TechnologyEvidenceReference] = (),
    input_package: Module2TechnologyInputPackage | None = None,
    context: Mapping[str, Any] | None = None,
) -> KnowledgeRuleEvaluation:
    if rule.status != TechnologyLifecycle.ACTIVE.value:
        return KnowledgeRuleEvaluation(
            state=EvaluationState.UNKNOWN,
            blockers=("rule_not_active",),
        )

    state, blockers = evaluate_structured_conditions(
        rule.conditions,
        input_package=input_package,
        context=context,
    )
    evidence_ids = _evidence_ids_for_entities(
        evidence_references,
        EvidenceTargetKind.KNOWLEDGE_RULE,
        (rule.id,),
    )
    if state != EvaluationState.APPLIES:
        return KnowledgeRuleEvaluation(
            state=state,
            blockers=blockers,
            evidence_reference_ids=evidence_ids,
        )
    return KnowledgeRuleEvaluation(
        state=EvaluationState.APPLIES,
        outcome_type=KnowledgeRuleOutcome(rule.outcome_type),
        outcome_payload=deepcopy(rule.outcome_payload),
        evidence_reference_ids=evidence_ids,
    )


def evaluate_structured_conditions(
    conditions: Sequence[StructuredCondition | Mapping[str, Any]],
    *,
    input_package: Module2TechnologyInputPackage | None = None,
    context: Mapping[str, Any] | None = None,
) -> tuple[EvaluationState, tuple[str, ...]]:
    properties = _module1_properties(input_package)
    contextual = context or {}
    blockers: list[str] = []

    for raw in conditions:
        condition = _as_command(raw, StructuredCondition)
        values = (
            properties
            if condition.source == ConditionSource.M1_MATERIAL_PROPERTY
            else contextual
        )
        found, actual = _lookup(values, condition.field)
        if condition.operator == ConditionOperator.EXISTS:
            expected = True if condition.value is None else condition.value
            if found is not expected:
                return EvaluationState.DOES_NOT_APPLY, tuple()
            continue
        if not found:
            blockers.append(f"missing_{condition.source.value.lower()}:{condition.field}")
            continue
        if not _compare(actual, condition.operator, condition.value):
            return EvaluationState.DOES_NOT_APPLY, tuple()

    if blockers:
        return EvaluationState.UNKNOWN, _unique(blockers)
    return EvaluationState.APPLIES, tuple()


def detect_compatibility_conflicts(
    candidate: CompatibilityRule,
    peer_rules: Sequence[CompatibilityRule],
) -> tuple[uuid.UUID, ...]:
    candidate_relation = CompatibilityRelation(candidate.relation)
    conflicts: list[uuid.UUID] = []
    for peer in peer_rules:
        if peer.id == candidate.id or peer.status != TechnologyLifecycle.ACTIVE.value:
            continue
        if not _same_compatibility_scope(candidate, peer):
            continue
        peer_relation = CompatibilityRelation(peer.relation)
        if (
            CompatibilityRelation.INCOMPATIBLE in {candidate_relation, peer_relation}
            and {candidate_relation, peer_relation}.intersection(
                {CompatibilityRelation.COMPATIBLE, CompatibilityRelation.CONDITIONAL}
            )
        ):
            conflicts.append(peer.id)
    return tuple(conflicts)


def detect_knowledge_rule_conflicts(
    candidate: KnowledgeRule,
    peer_rules: Sequence[KnowledgeRule],
) -> tuple[uuid.UUID, ...]:
    conflicts: list[uuid.UUID] = []
    for peer in peer_rules:
        if peer.id == candidate.id or peer.status != TechnologyLifecycle.ACTIVE.value:
            continue
        same_scope = (
            peer.technology_id == candidate.technology_id
            and peer.scope_kind == candidate.scope_kind
            and peer.scope_reference == candidate.scope_reference
            and _canonical_json(peer.conditions) == _canonical_json(candidate.conditions)
        )
        outcomes = {peer.outcome_type, candidate.outcome_type}
        if same_scope and "PROHIBITION" in outcomes and len(outcomes) > 1:
            conflicts.append(peer.id)
    return tuple(conflicts)


async def persist_knowledge_draft(
    db: AsyncSession,
    entity: KnowledgeEntity,
) -> KnowledgeEntity:
    if entity.status != TechnologyLifecycle.DRAFT.value:
        raise Module2KnowledgeError("only DRAFT M2 knowledge may enter draft persistence")
    db.add(entity)
    await db.flush()
    return entity


async def list_consumption_norms(
    db: AsyncSession,
    technology_id: uuid.UUID,
    *,
    status: TechnologyLifecycle | None = None,
) -> tuple[ConsumptionNorm, ...]:
    statement = select(ConsumptionNorm).where(
        ConsumptionNorm.technology_id == technology_id
    )
    if status:
        statement = statement.where(ConsumptionNorm.status == status.value)
    result = await db.execute(
        statement.order_by(ConsumptionNorm.norm_code, ConsumptionNorm.revision.desc())
    )
    return tuple(result.scalars().all())


async def list_compatibility_rules(
    db: AsyncSession,
    technology_id: uuid.UUID,
    *,
    status: TechnologyLifecycle | None = None,
) -> tuple[CompatibilityRule, ...]:
    statement = select(CompatibilityRule).where(
        CompatibilityRule.technology_id == technology_id
    )
    if status:
        statement = statement.where(CompatibilityRule.status == status.value)
    result = await db.execute(
        statement.order_by(
            CompatibilityRule.rule_code,
            CompatibilityRule.revision.desc(),
        )
    )
    return tuple(result.scalars().all())


async def list_knowledge_rules(
    db: AsyncSession,
    technology_id: uuid.UUID,
    *,
    status: TechnologyLifecycle | None = None,
) -> tuple[KnowledgeRule, ...]:
    statement = select(KnowledgeRule).where(
        KnowledgeRule.technology_id == technology_id
    )
    if status:
        statement = statement.where(KnowledgeRule.status == status.value)
    result = await db.execute(
        statement.order_by(KnowledgeRule.rule_code, KnowledgeRule.revision.desc())
    )
    return tuple(result.scalars().all())



def _validate_norm_scope(
    technology: Technology,
    command: ConsumptionNormDraftInput,
) -> None:
    _ensure_member(technology.layers, command.scope_layer_id, "layer")
    _ensure_member(
        technology.requirements,
        command.scope_requirement_id,
        "material requirement",
    )
    _ensure_member(
        technology.work_steps,
        command.scope_work_step_id,
        "work step",
    )


def _validate_selector_against_technology(
    technology: Technology,
    selector: KnowledgeSelectorInput,
) -> None:
    if selector.selector_kind == KnowledgeSelectorKind.MATERIAL_REQUIREMENT:
        _ensure_member(
            technology.requirements,
            selector.material_requirement_id,
            "resource material requirement",
        )


def _validate_rule_scope(
    technology: Technology,
    scope_kind: KnowledgeScopeKind,
    scope_reference: str | None,
) -> None:
    if scope_kind == KnowledgeScopeKind.TECHNOLOGY:
        return
    collections = {
        KnowledgeScopeKind.LAYER: technology.layers,
        KnowledgeScopeKind.MATERIAL_REQUIREMENT: technology.requirements,
        KnowledgeScopeKind.NODE: technology.nodes,
        KnowledgeScopeKind.WORK_STEP: technology.work_steps,
        KnowledgeScopeKind.CONSUMPTION_NORM: technology.consumption_norms,
        KnowledgeScopeKind.COMPATIBILITY_RULE: technology.compatibility_rules,
    }
    if scope_reference not in {str(item.id) for item in collections[scope_kind]}:
        raise Module2KnowledgeError(
            f"{scope_kind.value} scope does not belong to this Technology revision"
        )


def _evidence_target(
    technology: Technology,
    target: EvidenceTarget,
) -> tuple[EvidenceTargetKind, str | None]:
    if isinstance(target, Technology):
        if target is not technology and target.id != technology.id:
            raise Module2KnowledgeError("evidence target belongs to another Technology")
        return EvidenceTargetKind.TECHNOLOGY, None

    kind_by_type = {
        TechnologyLayer: EvidenceTargetKind.LAYER,
        TechnologyMaterialRequirement: EvidenceTargetKind.MATERIAL_REQUIREMENT,
        TechnologyNode: EvidenceTargetKind.NODE,
        TechnologyWorkStep: EvidenceTargetKind.WORK_STEP,
        ConsumptionNorm: EvidenceTargetKind.CONSUMPTION_NORM,
        CompatibilityRule: EvidenceTargetKind.COMPATIBILITY_RULE,
        KnowledgeRule: EvidenceTargetKind.KNOWLEDGE_RULE,
    }
    kind = kind_by_type.get(type(target))
    if kind is None:
        raise Module2KnowledgeError("unsupported evidence target")
    if not _target_belongs_to_technology(technology, target):
        raise Module2KnowledgeError("evidence target belongs to another Technology")
    return kind, str(target.id)


def _target_belongs_to_technology(
    technology: Technology,
    target: EvidenceTarget,
) -> bool:
    return (
        getattr(target, "technology", None) is technology
        or getattr(target, "technology_id", None) == technology.id
    )


def _target_evidence(
    references: Sequence[TechnologyEvidenceReference],
    target_kind: EvidenceTargetKind,
    entity_id: uuid.UUID,
) -> tuple[TechnologyEvidenceReference, ...]:
    target_reference = str(entity_id)
    return tuple(
        item
        for item in references
        if item.target_kind == target_kind.value
        and item.target_reference == target_reference
    )


def _entity_target_kind(entity: KnowledgeEntity) -> EvidenceTargetKind:
    if isinstance(entity, ConsumptionNorm):
        return EvidenceTargetKind.CONSUMPTION_NORM
    if isinstance(entity, CompatibilityRule):
        return EvidenceTargetKind.COMPATIBILITY_RULE
    return EvidenceTargetKind.KNOWLEDGE_RULE


def _module1_properties(
    package: Module2TechnologyInputPackage | None,
) -> Mapping[str, Any]:
    if package is None:
        return {}
    if (
        not package.no_side_effects
        or not package.no_calculation_result
        or not package.technical_profile.no_side_effects
    ):
        raise Module2KnowledgeError("M1 input contract must be read-only")
    properties = dict(package.clean_material.normalized_characteristics)
    properties.update(package.technical_profile.technical_characteristics)
    return properties


def _compatibility_selector_match(
    rule: CompatibilityRule,
    subject: KnowledgeSelectorInput,
    object_: KnowledgeSelectorInput,
) -> bool:
    direct = (
        rule.subject_selector == _selector_payload(subject)
        and rule.object_selector == _selector_payload(object_)
    )
    reverse = (
        rule.is_symmetric
        and rule.subject_selector == _selector_payload(object_)
        and rule.object_selector == _selector_payload(subject)
    )
    return direct or reverse


def _same_compatibility_scope(
    left: CompatibilityRule,
    right: CompatibilityRule,
) -> bool:
    if left.technology_id != right.technology_id:
        return False
    left_pair = (
        _canonical_json(left.subject_selector),
        _canonical_json(left.object_selector),
    )
    right_pair = (
        _canonical_json(right.subject_selector),
        _canonical_json(right.object_selector),
    )
    selector_match = left_pair == right_pair
    if left.is_symmetric and right.is_symmetric:
        selector_match = sorted(left_pair) == sorted(right_pair)
    return (
        selector_match
        and _canonical_json(left.conditions) == _canonical_json(right.conditions)
    )


def _evidence_ids_for_entities(
    references: Sequence[TechnologyEvidenceReference],
    target_kind: EvidenceTargetKind,
    entity_ids: Sequence[uuid.UUID],
) -> tuple[uuid.UUID, ...]:
    target_ids = {str(item) for item in entity_ids}
    return tuple(
        item.id
        for item in references
        if item.target_kind == target_kind.value
        and item.target_reference in target_ids
    )


def _selector_payload(selector: KnowledgeSelectorInput) -> dict[str, Any]:
    return selector.model_dump(mode="json", exclude_none=True)


def _condition_payload(
    conditions: Sequence[StructuredCondition],
) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in conditions]


def _canonical_unit(value: str) -> str:
    canonical = normalize_unit(value)
    if canonical is None:
        raise Module2KnowledgeError(f"unknown canonical unit: {value}")
    return canonical


def _ensure_member(
    values: Sequence[Any],
    item_id: uuid.UUID | None,
    label: str,
) -> None:
    if item_id is None:
        return
    if item_id not in {item.id for item in values}:
        raise Module2KnowledgeError(f"{label} does not belong to this Technology revision")


def _lookup(values: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = values
    for segment in path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _compare(actual: Any, operator: ConditionOperator, expected: Any) -> bool:
    if operator == ConditionOperator.EQUAL:
        return actual == expected
    if operator == ConditionOperator.NOT_EQUAL:
        return actual != expected
    if operator == ConditionOperator.IN:
        return actual in expected
    if operator == ConditionOperator.NOT_IN:
        return actual not in expected
    if operator == ConditionOperator.BETWEEN:
        lower_actual, lower = _comparable_pair(actual, expected[0])
        upper_actual, upper = _comparable_pair(actual, expected[1])
        return lower_actual >= lower and upper_actual <= upper

    actual_value, expected_value = _comparable_pair(actual, expected)
    if operator == ConditionOperator.GT:
        return actual_value > expected_value
    if operator == ConditionOperator.GTE:
        return actual_value >= expected_value
    if operator == ConditionOperator.LT:
        return actual_value < expected_value
    if operator == ConditionOperator.LTE:
        return actual_value <= expected_value
    raise Module2KnowledgeError(f"unsupported condition operator: {operator.value}")


def _comparable_pair(left: Any, right: Any) -> tuple[Any, Any]:
    try:
        return Decimal(str(left)), Decimal(str(right))
    except (InvalidOperation, TypeError, ValueError):
        try:
            left < right
        except TypeError as exc:
            raise Module2KnowledgeError("condition values are not comparable") from exc
        return left, right


def _require_active(entity: KnowledgeEntity) -> None:
    if entity.status != TechnologyLifecycle.ACTIVE.value:
        raise Module2KnowledgeError(
            "a new revision can only supersede ACTIVE knowledge"
        )


def _as_command(value: Any, model_type: type[Any]) -> Any:
    return value if isinstance(value, model_type) else model_type.model_validate(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item) for item in values if str(item)))
