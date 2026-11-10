from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.module2_knowledge import CompatibilityRule, ConsumptionNorm, KnowledgeRule
from app.models.module2_technology import Technology, TechnologyEvidenceReference
from app.schemas.module2_estimation_contract import (
    EstimationCompatibilityConstraint,
    EstimationCondition,
    EstimationConsumptionNorm,
    EstimationEvidenceReference,
    EstimationIssue,
    EstimationKnowledgeConstraint,
    EstimationLayer,
    EstimationMaterialRequirement,
    EstimationSelector,
    EstimationTechnologyRevision,
    EstimationWorkStep,
    Module5EstimationInputPackage,
    QuantityBasis,
)
from app.schemas.module2_knowledge import (
    CompatibilityRelation,
    KnowledgeRuleOutcome,
    KnowledgeSelectorKind,
)
from app.schemas.module2_technology import TechnologyLifecycle
from app.services.module1_unit_conversion_registry import UnitConversionRegistry
from app.services.module1_work_catalog import get_work_item
from app.services.module2_foundation_quantity_rules import describe_quantity_rule
from app.services.module2_knowledge_foundation import (
    detect_compatibility_conflicts,
    detect_knowledge_rule_conflicts,
    verify_evidence_references,
)
from app.services.module2_technology_foundation import (
    read_technology,
    validate_technology_activation,
)


class Module2EstimationContractError(ValueError):
    pass


_UNIT_BASIS: Mapping[str, QuantityBasis] = {
    "m2": QuantityBasis.AREA,
    "m2_mm": QuantityBasis.AREA_THICKNESS,
    "m3": QuantityBasis.VOLUME,
    "liter": QuantityBasis.VOLUME,
    "mm": QuantityBasis.LENGTH,
    "cm": QuantityBasis.LENGTH,
    "m": QuantityBasis.LENGTH,
    "linear_meter": QuantityBasis.LENGTH,
    "piece": QuantityBasis.COUNT,
    "sheet": QuantityBasis.COUNT,
    "bag": QuantityBasis.COUNT,
    "package": QuantityBasis.COUNT,
    "roll": QuantityBasis.COUNT,
    "pallet": QuantityBasis.COUNT,
    "kg": QuantityBasis.MASS,
    "ton": QuantityBasis.MASS,
}


async def build_module5_estimation_input_package(
    db: AsyncSession,
    technology_id: uuid.UUID,
) -> Module5EstimationInputPackage:
    technology = await read_technology(db, technology_id)
    if technology is None:
        raise Module2EstimationContractError("technology revision was not found")
    if technology.status != TechnologyLifecycle.ACTIVE.value:
        raise Module2EstimationContractError(
            "production estimation input requires an ACTIVE technology revision"
        )

    verified_evidence = await verify_evidence_references(
        db,
        technology.evidence_references,
    )
    blockers: list[EstimationIssue] = []
    warnings: list[EstimationIssue] = []

    material_ids = {item.canonical_material_id for item in technology.requirements if item.canonical_material_id}
    direct_selectors = [
        (item.resource_kind, item.resource_selector)
        for item in technology.consumption_norms if item.status == TechnologyLifecycle.ACTIVE.value
    ]
    direct_selectors.extend(
        pair for item in technology.compatibility_rules if item.status == TechnologyLifecycle.ACTIVE.value
        for pair in ((item.subject_kind, item.subject_selector), (item.object_kind, item.object_selector))
    )
    for kind, selector in direct_selectors:
        if kind == KnowledgeSelectorKind.CANONICAL_MATERIAL.value:
            try:
                material_ids.add(uuid.UUID(str((selector or {}).get("canonical_material_id"))))
            except (ValueError, TypeError, AttributeError):
                pass
    for item in technology.knowledge_rules:
        payload = item.outcome_payload or {}
        if item.status == TechnologyLifecycle.ACTIVE.value and payload.get("kind") == "FOUNDATION_QUANTITY_RULE":
            try:
                material_ids.add(uuid.UUID(str(payload.get("canonical_material_id"))))
            except (ValueError, TypeError, AttributeError):
                pass
    material_statuses = {}
    if material_ids:
        material_statuses = dict((await db.execute(
            select(Material.id, Material.status).where(Material.id.in_(material_ids))
        )).all())

    for code in validate_technology_activation(technology):
        _append_issue(blockers, code, "TECHNOLOGY", technology.id)

    layers_by_requirement: dict[uuid.UUID, list[Any]] = {}
    for layer in technology.layers:
        if layer.material_requirement_id:
            layers_by_requirement.setdefault(layer.material_requirement_id, []).append(layer)

    material_requirements = []
    for requirement in sorted(technology.requirements, key=lambda item: (item.code, str(item.id))):
        selector, local_blockers = _selector(
            requirement.selector_kind,
            {
                "canonical_material_id": requirement.canonical_material_id,
                "material_category_id": requirement.material_category_id,
                "material_type_id": requirement.material_type_id,
                "material_role_code": requirement.material_role_code,
                "technical_constraints": requirement.technical_constraints,
            },
        )
        local_blockers = list(local_blockers)
        local_blockers.extend(_canonical_material_blockers(selector, material_statuses))
        scoped_layers = sorted(
            layers_by_requirement.get(requirement.id, ()),
            key=lambda item: item.position,
        )
        local_blockers = _record_local_blockers(
            blockers,
            local_blockers,
            "MATERIAL_REQUIREMENT",
            requirement.id,
        )
        material_requirements.append(
            EstimationMaterialRequirement(
                requirement_id=requirement.id,
                requirement_code=requirement.code,
                selector=selector,
                layer_ids=tuple(item.id for item in scoped_layers),
                mandatory=any(item.is_mandatory for item in scoped_layers),
                restrictions=tuple(dict(item.restrictions or {}) for item in scoped_layers),
                evidence_reference_ids=_evidence_ids(
                    technology.evidence_references,
                    "MATERIAL_REQUIREMENT",
                    requirement.id,
                ),
                blockers=local_blockers,
            )
        )

    layers = []
    requirement_ids = {item.id for item in technology.requirements}
    for layer in sorted(technology.layers, key=lambda item: (item.position, str(item.id))):
        local_blockers = []
        if layer.is_mandatory and layer.material_requirement_id is None:
            local_blockers.append("mandatory_layer_without_requirement")
        elif layer.material_requirement_id and layer.material_requirement_id not in requirement_ids:
            local_blockers.append("unresolved_material_requirement")
        local_blockers = _record_local_blockers(
            blockers,
            local_blockers,
            "LAYER",
            layer.id,
        )
        layers.append(
            EstimationLayer(
                layer_id=layer.id,
                order=layer.position,
                functional_role=layer.functional_role,
                material_requirement_id=layer.material_requirement_id,
                thickness_expression=layer.thickness_expression,
                mandatory=layer.is_mandatory,
                restrictions=dict(layer.restrictions or {}),
                evidence_reference_ids=_evidence_ids(
                    technology.evidence_references,
                    "LAYER",
                    layer.id,
                ),
                blockers=local_blockers,
            )
        )

    active_norms = tuple(
        sorted(
            (item for item in technology.consumption_norms if item.status == TechnologyLifecycle.ACTIVE.value),
            key=lambda item: (item.norm_code, item.revision, str(item.id)),
        )
    )
    _warn_for_inactive_knowledge(
        warnings,
        technology.consumption_norms,
        "CONSUMPTION_NORM",
    )
    if not active_norms:
        _append_issue(
            blockers,
            "missing_active_consumption_norm",
            "TECHNOLOGY",
            technology.id,
        )

    norm_ids_by_work_step: dict[uuid.UUID, list[uuid.UUID]] = {}
    consumption_norms = []
    unit_registry = UnitConversionRegistry()
    for norm in active_norms:
        if norm.scope_work_step_id:
            norm_ids_by_work_step.setdefault(norm.scope_work_step_id, []).append(norm.id)
        consumption_norms.append(
            _build_norm(
                technology,
                norm,
                unit_registry,
                verified_evidence,
                blockers,
                material_statuses,
            )
        )

    work_steps = []
    for step in sorted(technology.work_steps, key=lambda item: (item.position, str(item.id))):
        local_blockers = []
        work_item = get_work_item(step.work_code)
        if work_item is None:
            local_blockers.append("unknown_m1_work_code")
        local_blockers = _record_local_blockers(
            blockers,
            local_blockers,
            "WORK_STEP",
            step.id,
        )
        work_steps.append(
            EstimationWorkStep(
                work_step_id=step.id,
                order=step.position,
                work_code=step.work_code,
                work_group=work_item.work_group if work_item else None,
                applicability_expression=step.applicability_expression,
                dependency_step_codes=tuple(step.dependency_step_codes or ()),
                consumption_norm_ids=tuple(sorted(norm_ids_by_work_step.get(step.id, ()), key=str)),
                evidence_reference_ids=_evidence_ids(
                    technology.evidence_references,
                    "WORK_STEP",
                    step.id,
                ),
                blockers=local_blockers,
            )
        )

    active_compatibility = tuple(
        item
        for item in technology.compatibility_rules
        if item.status == TechnologyLifecycle.ACTIVE.value
    )
    _warn_for_inactive_knowledge(
        warnings,
        technology.compatibility_rules,
        "COMPATIBILITY_RULE",
    )
    compatibility_constraints = []
    for rule in sorted(
        (
            item
            for item in active_compatibility
            if item.relation != CompatibilityRelation.COMPATIBLE.value
        ),
        key=lambda item: (item.rule_code, item.revision, str(item.id)),
    ):
        compatibility_constraints.append(
            _build_compatibility_constraint(
                technology,
                rule,
                active_compatibility,
                verified_evidence,
                blockers,
                warnings,
                material_statuses,
            )
        )

    active_rules = tuple(
        item
        for item in technology.knowledge_rules
        if item.status == TechnologyLifecycle.ACTIVE.value
    )
    _warn_for_inactive_knowledge(warnings, technology.knowledge_rules, "KNOWLEDGE_RULE")
    knowledge_constraints = []
    for rule in sorted(
        (
            item
            for item in active_rules
            if item.outcome_type != KnowledgeRuleOutcome.INFORMATION.value
            or (item.outcome_payload or {}).get("kind") in {"FOUNDATION_QUANTITY_RULE", "FOUNDATION_ROLE_COMPOSITION"}
        ),
        key=lambda item: (item.rule_code, item.revision, str(item.id)),
    ):
        knowledge_constraints.append(
            _build_knowledge_constraint(
                technology,
                rule,
                active_rules,
                verified_evidence,
                blockers,
                material_statuses,
            )
        )

    relevant_targets = {
        ("TECHNOLOGY", None),
        *(("MATERIAL_REQUIREMENT", str(item.requirement_id)) for item in material_requirements),
        *(("LAYER", str(item.layer_id)) for item in layers),
        *(("WORK_STEP", str(item.work_step_id)) for item in work_steps),
        *(("CONSUMPTION_NORM", str(item.norm_id)) for item in consumption_norms),
        *(("COMPATIBILITY_RULE", str(item.rule_id)) for item in compatibility_constraints),
        *(("KNOWLEDGE_RULE", str(item.rule_id)) for item in knowledge_constraints),
    }
    evidence_references = tuple(
        EstimationEvidenceReference(
            evidence_reference_id=item.id,
            document_id=item.document_id,
            knowledge_resource_id=item.knowledge_resource_id,
            target_kind=item.target_kind,
            target_reference=item.target_reference,
            interpretation=item.interpretation,
            verified=item.id in verified_evidence,
        )
        for item in sorted(technology.evidence_references, key=lambda value: str(value.id))
        if (item.target_kind, item.target_reference) in relevant_targets
    )

    return Module5EstimationInputPackage(
        technology=EstimationTechnologyRevision(
            technology_id=technology.id,
            technology_code=technology.technology_code,
            revision=technology.revision,
            lifecycle_status=TechnologyLifecycle(technology.status),
            system_code=technology.system_code,
            source_kind=technology.source_kind,
        ),
        ready_for_estimation=not blockers,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        material_requirements=tuple(material_requirements),
        layers=tuple(layers),
        work_steps=tuple(work_steps),
        consumption_norms=tuple(consumption_norms),
        compatibility_constraints=tuple(compatibility_constraints),
        knowledge_constraints=tuple(knowledge_constraints),
        evidence_references=evidence_references,
    )


def _build_norm(
    technology: Technology,
    norm: ConsumptionNorm,
    unit_registry: UnitConversionRegistry,
    verified_evidence: frozenset[uuid.UUID],
    package_blockers: list[EstimationIssue],
    material_statuses: Mapping[uuid.UUID, MaterialStatus],
) -> EstimationConsumptionNorm:
    local_blockers = list(norm.blockers or ())
    basis_unit = unit_registry.normalize_unit(norm.basis_unit)
    consumption_unit = unit_registry.normalize_unit(norm.consumption_unit)
    quantity_basis = _UNIT_BASIS.get(basis_unit or "", QuantityBasis.UNKNOWN)
    if basis_unit is None:
        local_blockers.append("unknown_basis_unit")
    elif quantity_basis == QuantityBasis.UNKNOWN:
        local_blockers.append("unsupported_quantity_basis")
    if consumption_unit is None:
        local_blockers.append("unknown_consumption_unit")

    membership = {
        "scope_layer_id": {item.id for item in technology.layers},
        "scope_requirement_id": {item.id for item in technology.requirements},
        "scope_work_step_id": {item.id for item in technology.work_steps},
    }
    for field, valid_ids in membership.items():
        value = getattr(norm, field)
        if value and value not in valid_ids:
            local_blockers.append(f"unresolved_{field}")

    resource, selector_blockers = _selector(norm.resource_kind, norm.resource_selector)
    local_blockers.extend(selector_blockers)
    local_blockers.extend(_canonical_material_blockers(resource, material_statuses))
    evidence_ids = _evidence_ids(
        technology.evidence_references,
        "CONSUMPTION_NORM",
        norm.id,
    )
    local_blockers.extend(
        _evidence_blockers(evidence_ids, verified_evidence, required=True)
    )
    conditions, condition_blockers = _conditions(norm.conditions)
    local_blockers.extend(condition_blockers)
    local_blockers = _record_local_blockers(
        package_blockers,
        local_blockers,
        "CONSUMPTION_NORM",
        norm.id,
    )
    return EstimationConsumptionNorm(
        norm_id=norm.id,
        norm_code=norm.norm_code,
        revision=norm.revision,
        scope_layer_id=norm.scope_layer_id,
        scope_requirement_id=norm.scope_requirement_id,
        scope_work_step_id=norm.scope_work_step_id,
        resource=resource,
        quantity_basis=quantity_basis,
        basis_quantity=norm.basis_quantity,
        basis_unit=basis_unit or norm.basis_unit,
        consumption_quantity=norm.consumption_quantity,
        consumption_unit=consumption_unit or norm.consumption_unit,
        conditions=conditions,
        evidence_reference_ids=evidence_ids,
        blockers=local_blockers,
    )


def _build_compatibility_constraint(
    technology: Technology,
    rule: CompatibilityRule,
    peer_rules: Sequence[CompatibilityRule],
    verified_evidence: frozenset[uuid.UUID],
    package_blockers: list[EstimationIssue],
    package_warnings: list[EstimationIssue],
    material_statuses: Mapping[uuid.UUID, MaterialStatus],
) -> EstimationCompatibilityConstraint:
    subject, subject_blockers = _selector(rule.subject_kind, rule.subject_selector)
    object_, object_blockers = _selector(rule.object_kind, rule.object_selector)
    local_blockers = [*(rule.blockers or ()), *subject_blockers, *object_blockers]
    local_blockers.extend(_canonical_material_blockers(subject, material_statuses))
    local_blockers.extend(_canonical_material_blockers(object_, material_statuses))
    conflicts = detect_compatibility_conflicts(rule, peer_rules)
    if conflicts:
        local_blockers.append("conflicting_active_compatibility_rule")
    if rule.relation == CompatibilityRelation.UNKNOWN.value:
        _append_issue(
            package_warnings,
            "unresolved_compatibility",
            "COMPATIBILITY_RULE",
            rule.id,
        )
    evidence_ids = _evidence_ids(
        technology.evidence_references,
        "COMPATIBILITY_RULE",
        rule.id,
    )
    local_blockers.extend(_evidence_blockers(evidence_ids, verified_evidence, required=True))
    conditions, condition_blockers = _conditions(rule.conditions)
    local_blockers.extend(condition_blockers)
    local_blockers = _record_local_blockers(
        package_blockers,
        local_blockers,
        "COMPATIBILITY_RULE",
        rule.id,
    )
    return EstimationCompatibilityConstraint(
        rule_id=rule.id,
        rule_code=rule.rule_code,
        revision=rule.revision,
        subject=subject,
        object=object_,
        relation=CompatibilityRelation(rule.relation),
        conditions=conditions,
        reason=rule.reason,
        symmetric=rule.is_symmetric,
        evidence_reference_ids=evidence_ids,
        blockers=local_blockers,
    )


def _build_knowledge_constraint(
    technology: Technology,
    rule: KnowledgeRule,
    peer_rules: Sequence[KnowledgeRule],
    verified_evidence: frozenset[uuid.UUID],
    package_blockers: list[EstimationIssue],
    material_statuses: Mapping[uuid.UUID, MaterialStatus],
) -> EstimationKnowledgeConstraint:
    local_blockers = list(rule.blockers or ())
    payload = dict(rule.outcome_payload or {})
    if payload.get("kind") == "FOUNDATION_ROLE_COMPOSITION":
        local_blockers.append("foundation_role_composition_not_supported")
    if payload.get("kind") == "FOUNDATION_QUANTITY_RULE":
        try:
            expected = describe_quantity_rule(payload["code"], role_code=payload["material_role_code"],
                                              material_id=payload["canonical_material_id"])
            if payload != expected or rule.outcome_type != KnowledgeRuleOutcome.INFORMATION.value:
                raise ValueError("invalid quantity rule payload")
            material_id = uuid.UUID(str(payload["canonical_material_id"]))
        except (KeyError, ValueError, TypeError, AttributeError):
            local_blockers.append("invalid_foundation_quantity_rule")
        else:
            if material_id not in material_statuses:
                local_blockers.append("canonical_material_missing")
            elif material_statuses[material_id] != MaterialStatus.VERIFIED:
                local_blockers.append("canonical_material_not_verified")
            matched_roles = [
                item.canonical_material_id == material_id
                and payload["material_role_code"] in {item.code, item.material_role_code}
                and rule.scope_reference == str(item.id)
                for item in technology.requirements
            ]
            if rule.scope_kind != "MATERIAL_REQUIREMENT" or not any(matched_roles):
                local_blockers.append("quantity_rule_role_unresolved")
    if detect_knowledge_rule_conflicts(rule, peer_rules):
        local_blockers.append("conflicting_active_knowledge_rule")
    evidence_ids = _evidence_ids(
        technology.evidence_references,
        "KNOWLEDGE_RULE",
        rule.id,
    )
    local_blockers.extend(_evidence_blockers(evidence_ids, verified_evidence, required=True))
    conditions, condition_blockers = _conditions(rule.conditions)
    local_blockers.extend(condition_blockers)
    local_blockers = _record_local_blockers(
        package_blockers,
        local_blockers,
        "KNOWLEDGE_RULE",
        rule.id,
    )
    return EstimationKnowledgeConstraint(
        rule_id=rule.id,
        rule_code=rule.rule_code,
        revision=rule.revision,
        scope_kind=rule.scope_kind,
        scope_reference=rule.scope_reference,
        conditions=conditions,
        outcome_type=KnowledgeRuleOutcome(rule.outcome_type),
        outcome_payload=dict(rule.outcome_payload or {}),
        evidence_reference_ids=evidence_ids,
        blockers=local_blockers,
    )


def _canonical_material_blockers(
    selector: EstimationSelector, material_statuses: Mapping[uuid.UUID, MaterialStatus],
) -> tuple[str, ...]:
    material_id = selector.canonical_material_id
    if selector.selector_kind != KnowledgeSelectorKind.CANONICAL_MATERIAL or material_id is None:
        return ()
    if material_id not in material_statuses:
        return ("canonical_material_missing",)
    if material_statuses[material_id] != MaterialStatus.VERIFIED:
        return ("canonical_material_not_verified",)
    return ()


def _selector(kind: str, values: Mapping[str, Any] | None) -> tuple[EstimationSelector, tuple[str, ...]]:
    payload = dict(values or {})
    selector_kind = KnowledgeSelectorKind(kind)
    selector = EstimationSelector(
        selector_kind=selector_kind,
        canonical_material_id=payload.get("canonical_material_id"),
        material_category_id=payload.get("material_category_id"),
        material_type_id=payload.get("material_type_id"),
        material_requirement_id=payload.get("material_requirement_id"),
        material_role_code=payload.get("material_role_code"),
        technical_constraints=dict(payload.get("technical_constraints") or {}),
    )
    valid = {
        KnowledgeSelectorKind.CANONICAL_MATERIAL: selector.canonical_material_id is not None,
        KnowledgeSelectorKind.MATERIAL_CLASS: any(
            (selector.material_category_id, selector.material_type_id)
        ),
        KnowledgeSelectorKind.MATERIAL_REQUIREMENT: selector.material_requirement_id is not None,
        KnowledgeSelectorKind.TECHNICAL_CONSTRAINTS: bool(selector.technical_constraints),
        KnowledgeSelectorKind.ROLE: bool(selector.material_role_code),
    }
    return selector, tuple() if valid[selector_kind] else ("unresolved_selector",)


def _conditions(values: Iterable[Mapping[str, Any]]) -> tuple[tuple[EstimationCondition, ...], tuple[str, ...]]:
    conditions = []
    for value in values or ():
        try:
            conditions.append(EstimationCondition.model_validate(value))
        except ValidationError:
            return tuple(conditions), ("invalid_applicability_condition",)
    return tuple(conditions), tuple()


def _evidence_ids(
    references: Sequence[TechnologyEvidenceReference],
    target_kind: str,
    target_id: uuid.UUID | None,
) -> tuple[uuid.UUID, ...]:
    target_reference = str(target_id) if target_id else None
    return tuple(
        sorted(
            (
                item.id
                for item in references
                if item.target_kind == target_kind
                and item.target_reference == target_reference
            ),
            key=str,
        )
    )


def _evidence_blockers(
    evidence_ids: Sequence[uuid.UUID],
    verified_evidence: frozenset[uuid.UUID],
    *,
    required: bool,
) -> tuple[str, ...]:
    if required and not evidence_ids:
        return ("missing_evidence",)
    if any(item not in verified_evidence for item in evidence_ids):
        return ("broken_or_unverified_evidence",)
    return tuple()


def _record_local_blockers(
    package_blockers: list[EstimationIssue],
    codes: Iterable[str],
    scope_type: str,
    scope_id: uuid.UUID,
) -> tuple[str, ...]:
    unique_codes = tuple(dict.fromkeys(str(code) for code in codes if code))
    for code in unique_codes:
        _append_issue(package_blockers, code, scope_type, scope_id)
    return unique_codes


def _warn_for_inactive_knowledge(
    warnings: list[EstimationIssue],
    entities: Iterable[Any],
    scope_type: str,
) -> None:
    for entity in entities:
        if entity.status != TechnologyLifecycle.ACTIVE.value:
            _append_issue(
                warnings,
                "non_active_knowledge_excluded",
                scope_type,
                entity.id,
                detail=f"status={entity.status}",
            )


def _append_issue(
    issues: list[EstimationIssue],
    code: str,
    scope_type: str,
    scope_id: uuid.UUID | None,
    *,
    detail: str | None = None,
) -> None:
    issue = EstimationIssue(
        code=code,
        scope_type=scope_type,
        scope_id=scope_id,
        detail=detail,
    )
    key = (issue.code, issue.scope_type, issue.scope_id, issue.detail)
    if all((item.code, item.scope_type, item.scope_id, item.detail) != key for item in issues):
        issues.append(issue)
