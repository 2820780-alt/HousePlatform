from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

import app.models  # noqa: F401
from app.models.module2_knowledge import CompatibilityRule, ConsumptionNorm, KnowledgeRule
from app.models.module2_technology import (
    Technology,
    TechnologyLayer,
    TechnologyMaterialRequirement,
    TechnologyNode,
    TechnologyWorkStep,
)
from app.schemas.module2_knowledge import (
    CompatibilityRelation,
    CompatibilityRuleDraftInput,
    ConditionOperator,
    ConditionSource,
    ConsumptionNormDraftInput,
    EvaluationState,
    KnowledgeEvidenceInput,
    KnowledgeRuleDraftInput,
    KnowledgeRuleOutcome,
    KnowledgeScopeKind,
    KnowledgeSelectorInput,
    KnowledgeSelectorKind,
    StructuredCondition,
)
from app.schemas.module2_technology import TechnologyLifecycle
from app.services.module1_export_packages import (
    CleanMaterialPackage,
    Module2TechnologyInputPackage,
    TechnicalProfilePackage,
)
from app.services.module2_knowledge_foundation import (
    Module2KnowledgeError,
    attach_evidence_reference,
    create_compatibility_rule_draft,
    create_compatibility_rule_revision,
    create_consumption_norm_draft,
    create_consumption_norm_revision,
    create_knowledge_rule_draft,
    create_knowledge_rule_revision,
    detect_compatibility_conflicts,
    evaluate_compatibility_rules,
    evaluate_knowledge_rule,
    evaluate_structured_conditions,
    persist_knowledge_draft,
    transition_compatibility_rule,
    transition_consumption_norm,
    transition_knowledge_rule,
    validate_knowledge_activation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "database"
    / "migrations"
    / "20260913_module02_knowledge_foundation.sql"
)
SERVICE_PATH = PROJECT_ROOT / "app" / "services" / "module2_knowledge_foundation.py"


def _technology() -> Technology:
    technology = Technology(
        id=uuid4(),
        technology_code="SYNTHETIC_WALL_TECH",
        revision=1,
        name="Synthetic test technology",
        status=TechnologyLifecycle.DRAFT.value,
        input_missing_fields=[],
        input_blockers=[],
    )
    requirement = TechnologyMaterialRequirement(
        id=uuid4(),
        code="ADHESIVE",
        selector_kind="ROLE",
        material_role_code="ADHESIVE",
        technical_constraints={},
    )
    technology.requirements.append(requirement)
    technology.layers.append(
        TechnologyLayer(
            id=uuid4(),
            position=1,
            functional_role="PRIMARY",
            material_requirement=requirement,
            is_mandatory=True,
            restrictions={},
        )
    )
    technology.nodes.append(
        TechnologyNode(
            id=uuid4(),
            code="JOINT",
            node_type="JUNCTION",
            name="Synthetic joint",
            conditions={},
        )
    )
    technology.work_steps.append(
        TechnologyWorkStep(
            id=uuid4(),
            position=1,
            work_code="SYNTHETIC_TEST_WORK",
            dependency_step_codes=[],
        )
    )
    return technology


def _package(
    *,
    properties: dict | None = None,
    missing_fields: tuple[str, ...] = tuple(),
) -> Module2TechnologyInputPackage:
    material_id = uuid4()
    values = properties or {"density_class": 500, "strength_class": "B2.5"}
    return Module2TechnologyInputPackage(
        clean_material=CleanMaterialPackage(
            material_id=str(material_id),
            canonical_name="M1-owned synthetic material",
            group={"code": "synthetic"},
            category=None,
            subcategory=None,
            material_type=None,
            base_unit="m3",
            normalized_characteristics=values,
            quality_score=100,
            readiness_status="ready_for_module2",
            warnings=tuple(),
            provenance={"source": "M1"},
            source_refs=tuple(),
        ),
        technical_profile=TechnicalProfilePackage(
            material_id=str(material_id),
            material_group="synthetic",
            technical_characteristics=values,
            module2_required_fields=tuple(values),
            missing_module2_fields=missing_fields,
            packaging_profile={},
            conversion_capabilities=tuple(),
            calculation_readiness={"ready": not missing_fields},
            warnings=tuple(),
        ),
        material_role_hints=tuple(),
        compatibility_hints=tuple(),
        alternative_hints=tuple(),
        unit_conversion_hints=tuple(),
        missing_fields=missing_fields,
        blockers=tuple(),
    )


def _requirement_selector(technology: Technology) -> KnowledgeSelectorInput:
    return KnowledgeSelectorInput(
        selector_kind=KnowledgeSelectorKind.MATERIAL_REQUIREMENT,
        material_requirement_id=technology.requirements[0].id,
    )


def _class_selector() -> KnowledgeSelectorInput:
    return KnowledgeSelectorInput(
        selector_kind=KnowledgeSelectorKind.MATERIAL_CLASS,
        material_category_id=uuid4(),
    )


def _canonical_selector(material_id: UUID | None = None) -> KnowledgeSelectorInput:
    return KnowledgeSelectorInput(
        selector_kind=KnowledgeSelectorKind.CANONICAL_MATERIAL,
        canonical_material_id=material_id or uuid4(),
    )


def _norm(
    technology: Technology,
    *,
    conditions: list[StructuredCondition] | None = None,
) -> ConsumptionNorm:
    return create_consumption_norm_draft(
        technology,
        ConsumptionNormDraftInput(
            norm_code="ADHESIVE_PER_AREA",
            scope_layer_id=technology.layers[0].id,
            scope_requirement_id=technology.requirements[0].id,
            resource=_requirement_selector(technology),
            basis_quantity="1",
            basis_unit="m2",
            consumption_quantity="5",
            consumption_unit="kg",
            conditions=conditions or [],
        ),
        actor_role_code="ENGINEER_DESIGNER",
    )


def _compatibility_rule(
    technology: Technology,
    relation: CompatibilityRelation,
    *,
    subject: KnowledgeSelectorInput | None = None,
    object_: KnowledgeSelectorInput | None = None,
    conditions: list[StructuredCondition] | None = None,
    rule_code: str | None = None,
) -> CompatibilityRule:
    return create_compatibility_rule_draft(
        technology,
        CompatibilityRuleDraftInput(
            rule_code=rule_code or f"SYNTHETIC_{relation.value}",
            subject=subject or _class_selector(),
            object=object_ or _class_selector(),
            relation=relation,
            conditions=conditions or [],
            reason="Synthetic test fixture only",
        ),
        actor_role_code="ENGINEER_DESIGNER",
    )


def _knowledge_rule(
    technology: Technology,
    outcome: KnowledgeRuleOutcome = KnowledgeRuleOutcome.REQUIREMENT,
) -> KnowledgeRule:
    return create_knowledge_rule_draft(
        technology,
        KnowledgeRuleDraftInput(
            rule_code=f"SYNTHETIC_{outcome.value}",
            scope_kind=KnowledgeScopeKind.TECHNOLOGY,
            conditions=[
                StructuredCondition(
                    source=ConditionSource.CONTEXT,
                    field="temperature_c",
                    operator=ConditionOperator.GTE,
                    value=5,
                )
            ],
            outcome_type=outcome,
            outcome_payload={"code": "SYNTHETIC_FIXTURE"},
        ),
        actor_role_code="ENGINEER_DESIGNER",
    )


def _activate(entity, technology: Technology, transition) -> object:
    evidence = attach_evidence_reference(
        technology,
        entity,
        KnowledgeEvidenceInput(document_id=uuid4(), interpretation="Synthetic evidence"),
        actor_role_code="ENGINEER_DESIGNER",
    )
    technology.status = TechnologyLifecycle.ACTIVE.value
    transition(
        entity,
        TechnologyLifecycle.REVIEW,
        technology=technology,
        evidence_references=technology.evidence_references,
        actor_role_code="ENGINEER_DESIGNER",
    )
    transition(
        entity,
        TechnologyLifecycle.ACTIVE,
        technology=technology,
        evidence_references=technology.evidence_references,
        actor_role_code="MODERATOR",
        verified_evidence_reference_ids={evidence.id},
    )
    return evidence


def test_new_entities_are_module2_owned_tables() -> None:
    assert ConsumptionNorm.__tablename__ == "module2_consumption_norms"
    assert CompatibilityRule.__tablename__ == "module2_compatibility_rules"
    assert KnowledgeRule.__tablename__ == "module2_knowledge_rules"


def test_consumption_norm_is_relative_and_normalizes_existing_units() -> None:
    technology = _technology()
    norm = _norm(technology)

    assert norm.status == "DRAFT"
    assert norm.basis_quantity == 1
    assert norm.basis_unit == "m2"
    assert norm.consumption_quantity == 5
    assert norm.consumption_unit == "kg"
    assert not hasattr(norm, "object_area")
    assert not hasattr(norm, "price")


@pytest.mark.parametrize(
    ("field", "value"),
    (("basis_quantity", 0), ("consumption_quantity", 0)),
)
def test_consumption_norm_requires_positive_quantities(field: str, value: int) -> None:
    technology = _technology()
    payload = {
        "norm_code": "INVALID_QUANTITY",
        "resource": _requirement_selector(technology),
        "basis_quantity": 1,
        "basis_unit": "m2",
        "consumption_quantity": 1,
        "consumption_unit": "kg",
        field: value,
    }
    with pytest.raises(ValidationError):
        ConsumptionNormDraftInput.model_validate(payload)


def test_consumption_norm_rejects_unknown_unit_without_implicit_conversion() -> None:
    technology = _technology()
    command = ConsumptionNormDraftInput(
        norm_code="UNKNOWN_UNIT",
        resource=_requirement_selector(technology),
        basis_quantity=1,
        basis_unit="mystery_unit",
        consumption_quantity=1,
        consumption_unit="kg",
    )
    with pytest.raises(Module2KnowledgeError, match="unknown canonical unit"):
        create_consumption_norm_draft(
            technology,
            command,
            actor_role_code="ENGINEER_DESIGNER",
        )


def test_consumption_norm_scope_must_belong_to_technology_revision() -> None:
    technology = _technology()
    command = ConsumptionNormDraftInput(
        norm_code="FOREIGN_SCOPE",
        scope_layer_id=uuid4(),
        resource=_requirement_selector(technology),
        basis_quantity=1,
        basis_unit="m2",
        consumption_quantity=1,
        consumption_unit="kg",
    )
    with pytest.raises(Module2KnowledgeError, match="does not belong"):
        create_consumption_norm_draft(
            technology,
            command,
            actor_role_code="ENGINEER_DESIGNER",
        )


def test_norm_evidence_is_m1_reference_plus_m2_interpretation() -> None:
    technology = _technology()
    norm = _norm(technology)
    document_id = uuid4()
    evidence = attach_evidence_reference(
        technology,
        norm,
        KnowledgeEvidenceInput(
            document_id=document_id,
            interpretation="Applies to the synthetic norm",
        ),
        actor_role_code="ENGINEER_DESIGNER",
    )

    assert evidence.document_id == document_id
    assert evidence.target_kind == "CONSUMPTION_NORM"
    assert evidence.target_reference == str(norm.id)
    assert evidence.interpretation == "Applies to the synthetic norm"
    assert not hasattr(evidence, "document_body")
    assert not hasattr(evidence, "source_url")



@pytest.mark.parametrize(
    ("target_getter", "expected_kind"),
    (
        (lambda technology: technology, "TECHNOLOGY"),
        (lambda technology: technology.layers[0], "LAYER"),
        (lambda technology: technology.requirements[0], "MATERIAL_REQUIREMENT"),
        (lambda technology: technology.nodes[0], "NODE"),
        (lambda technology: technology.work_steps[0], "WORK_STEP"),
    ),
)
def test_existing_evidence_link_supports_all_technology_scopes(
    target_getter,
    expected_kind: str,
) -> None:
    technology = _technology()
    reference = attach_evidence_reference(
        technology,
        target_getter(technology),
        KnowledgeEvidenceInput(knowledge_resource_id=uuid4()),
        actor_role_code="ENGINEER_DESIGNER",
    )
    assert reference.target_kind == expected_kind


def test_broken_evidence_reference_blocks_activation() -> None:
    technology = _technology()
    norm = _norm(technology)
    evidence = attach_evidence_reference(
        technology,
        norm,
        KnowledgeEvidenceInput(document_id=uuid4()),
        actor_role_code="ENGINEER_DESIGNER",
    )
    transition_consumption_norm(
        norm,
        "REVIEW",
        technology=technology,
        evidence_references=technology.evidence_references,
        actor_role_code="ENGINEER_DESIGNER",
    )
    with pytest.raises(Module2KnowledgeError, match="broken_or_unverified_evidence"):
        transition_consumption_norm(
            norm,
            "ACTIVE",
            technology=technology,
            evidence_references=technology.evidence_references,
            actor_role_code="MODERATOR",
            verified_evidence_reference_ids=set(),
        )
    assert evidence.id not in set()


def test_active_norm_is_immutable_and_changes_use_revision() -> None:
    technology = _technology()
    norm = _norm(technology)
    _activate(norm, technology, transition_consumption_norm)

    with pytest.raises(Module2KnowledgeError, match="DRAFT"):
        attach_evidence_reference(
            technology,
            norm,
            KnowledgeEvidenceInput(document_id=uuid4()),
            actor_role_code="ENGINEER_DESIGNER",
        )

    revised = create_consumption_norm_revision(
        norm,
        actor_role_code="ENGINEER_DESIGNER",
    )
    assert norm.status == "ACTIVE"
    assert revised.status == "DRAFT"
    assert revised.revision == norm.revision + 1
    assert revised.supersedes is norm


@pytest.mark.parametrize(
    "relation",
    (
        CompatibilityRelation.COMPATIBLE,
        CompatibilityRelation.INCOMPATIBLE,
        CompatibilityRelation.CONDITIONAL,
        CompatibilityRelation.UNKNOWN,
    ),
)
def test_compatibility_supports_required_relations(
    relation: CompatibilityRelation,
) -> None:
    technology = _technology()
    subject = _canonical_selector()
    object_ = _class_selector()
    rule = _compatibility_rule(
        technology,
        relation,
        subject=subject,
        object_=object_,
    )
    _activate(rule, technology, transition_compatibility_rule)

    result = evaluate_compatibility_rules(
        [rule],
        subject,
        object_,
        evidence_references=technology.evidence_references,
    )
    expected_state = (
        EvaluationState.UNKNOWN
        if relation == CompatibilityRelation.UNKNOWN
        else EvaluationState.APPLIES
    )
    assert result.state == expected_state
    assert result.relation == relation


def test_conditional_compatibility_uses_structured_context() -> None:
    technology = _technology()
    subject = _class_selector()
    object_ = _class_selector()
    rule = _compatibility_rule(
        technology,
        CompatibilityRelation.CONDITIONAL,
        subject=subject,
        object_=object_,
        conditions=[
            StructuredCondition(
                source=ConditionSource.CONTEXT,
                field="primer_applied",
                operator=ConditionOperator.EQUAL,
                value=True,
            )
        ],
    )
    _activate(rule, technology, transition_compatibility_rule)

    applies = evaluate_compatibility_rules(
        [rule],
        subject,
        object_,
        context={"primer_applied": True},
    )
    unknown = evaluate_compatibility_rules([rule], subject, object_, context={})

    assert applies.relation == CompatibilityRelation.CONDITIONAL
    assert unknown.state == EvaluationState.UNKNOWN
    assert "insufficient_evidence" in unknown.blockers


def test_conflicting_active_compatibility_rules_return_review_with_both_chains() -> None:
    technology = _technology()
    subject = _canonical_selector()
    object_ = _class_selector()
    allowed = _compatibility_rule(
        technology,
        CompatibilityRelation.COMPATIBLE,
        subject=subject,
        object_=object_,
        rule_code="ALLOW_PAIR",
    )
    denied = _compatibility_rule(
        technology,
        CompatibilityRelation.INCOMPATIBLE,
        subject=subject,
        object_=object_,
        rule_code="DENY_PAIR",
    )
    allowed_evidence = attach_evidence_reference(
        technology,
        allowed,
        KnowledgeEvidenceInput(document_id=uuid4()),
        actor_role_code="ENGINEER_DESIGNER",
    )
    denied.status = "DRAFT"
    denied_evidence = attach_evidence_reference(
        technology,
        denied,
        KnowledgeEvidenceInput(knowledge_resource_id=uuid4()),
        actor_role_code="ENGINEER_DESIGNER",
    )
    allowed.status = "ACTIVE"
    denied.status = "ACTIVE"

    result = evaluate_compatibility_rules(
        [allowed, denied],
        subject,
        object_,
        evidence_references=technology.evidence_references,
    )

    assert result.state == EvaluationState.REVIEW
    assert result.relation == CompatibilityRelation.UNKNOWN
    assert set(result.evidence_reference_ids) == {
        allowed_evidence.id,
        denied_evidence.id,
    }
    assert detect_compatibility_conflicts(denied, [allowed]) == (allowed.id,)


def test_conflicting_rule_blocks_activation() -> None:
    technology = _technology()
    subject = _canonical_selector()
    object_ = _class_selector()
    active = _compatibility_rule(
        technology,
        CompatibilityRelation.COMPATIBLE,
        subject=subject,
        object_=object_,
        rule_code="ACTIVE_ALLOW",
    )
    active.status = "ACTIVE"
    candidate = _compatibility_rule(
        technology,
        CompatibilityRelation.INCOMPATIBLE,
        subject=subject,
        object_=object_,
        rule_code="CANDIDATE_DENY",
    )
    evidence = attach_evidence_reference(
        technology,
        candidate,
        KnowledgeEvidenceInput(document_id=uuid4()),
        actor_role_code="ENGINEER_DESIGNER",
    )
    candidate.status = "REVIEW"

    with pytest.raises(Module2KnowledgeError, match="conflicting"):
        transition_compatibility_rule(
            candidate,
            "ACTIVE",
            technology=technology,
            evidence_references=technology.evidence_references,
            actor_role_code="MODERATOR",
            verified_evidence_reference_ids={evidence.id},
            peer_rules=[active],
        )


def test_compatibility_revision_preserves_active_history() -> None:
    technology = _technology()
    rule = _compatibility_rule(technology, CompatibilityRelation.COMPATIBLE)
    _activate(rule, technology, transition_compatibility_rule)
    revised = create_compatibility_rule_revision(
        rule,
        actor_role_code="ENGINEER_DESIGNER",
    )
    assert revised.revision == 2
    assert revised.status == "DRAFT"
    assert revised.supersedes is rule


@pytest.mark.parametrize("outcome", tuple(KnowledgeRuleOutcome))
def test_knowledge_rule_outcomes_are_deterministic(
    outcome: KnowledgeRuleOutcome,
) -> None:
    technology = _technology()
    rule = _knowledge_rule(technology, outcome)
    _activate(rule, technology, transition_knowledge_rule)

    result = evaluate_knowledge_rule(
        rule,
        evidence_references=technology.evidence_references,
        context={"temperature_c": 10},
    )
    assert result.state == EvaluationState.APPLIES
    assert result.outcome_type == outcome
    assert result.outcome_payload == {"code": "SYNTHETIC_FIXTURE"}


def test_knowledge_rule_unknown_does_not_invent_missing_m1_property() -> None:
    technology = _technology()
    rule = create_knowledge_rule_draft(
        technology,
        KnowledgeRuleDraftInput(
            rule_code="MISSING_DENSITY",
            scope_kind=KnowledgeScopeKind.TECHNOLOGY,
            conditions=[
                StructuredCondition(
                    source=ConditionSource.M1_MATERIAL_PROPERTY,
                    field="density_class",
                    operator=ConditionOperator.GTE,
                    value=500,
                )
            ],
            outcome_type=KnowledgeRuleOutcome.REQUIREMENT,
        ),
        actor_role_code="ENGINEER_DESIGNER",
    )
    rule.status = "ACTIVE"

    result = evaluate_knowledge_rule(rule)
    assert result.state == EvaluationState.UNKNOWN
    assert "missing_m1_material_property:density_class" in result.blockers


def test_m1_package_supplies_read_only_material_properties() -> None:
    state, blockers = evaluate_structured_conditions(
        [
            StructuredCondition(
                source=ConditionSource.M1_MATERIAL_PROPERTY,
                field="density_class",
                operator=ConditionOperator.BETWEEN,
                value=[400, 600],
            )
        ],
        input_package=_package(properties={"density_class": 500}),
    )
    assert state == EvaluationState.APPLIES
    assert blockers == tuple()


def test_required_missing_m1_property_blocks_activation() -> None:
    technology = _technology()
    norm = _norm(
        technology,
        conditions=[
            StructuredCondition(
                source=ConditionSource.M1_MATERIAL_PROPERTY,
                field="frost_resistance",
                operator=ConditionOperator.EXISTS,
                required_for_activation=True,
            )
        ],
    )
    evidence = attach_evidence_reference(
        technology,
        norm,
        KnowledgeEvidenceInput(document_id=uuid4()),
        actor_role_code="ENGINEER_DESIGNER",
    )
    blockers = validate_knowledge_activation(
        norm,
        technology,
        technology.evidence_references,
        verified_evidence_reference_ids={evidence.id},
        input_package=_package(properties={"density_class": 500}),
    )
    assert "missing_m1_property:frost_resistance" in blockers


def test_unsupported_operator_and_executable_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        StructuredCondition(
            source="CONTEXT",
            field="temperature_c",
            operator="EXECUTE",
            value="anything",
        )
    with pytest.raises(ValidationError):
        StructuredCondition.model_validate(
            {
                "source": "CONTEXT",
                "field": "temperature_c",
                "operator": "GTE",
                "value": 5,
                "expression": "__import__('os').system('unsafe')",
            }
        )


def test_rule_scope_must_resolve_to_real_technology_subject() -> None:
    technology = _technology()
    with pytest.raises(Module2KnowledgeError, match="scope does not belong"):
        create_knowledge_rule_draft(
            technology,
            KnowledgeRuleDraftInput(
                rule_code="FOREIGN_LAYER",
                scope_kind=KnowledgeScopeKind.LAYER,
                scope_reference=str(uuid4()),
                conditions=[
                    StructuredCondition(
                        source=ConditionSource.CONTEXT,
                        field="ready",
                        operator=ConditionOperator.EQUAL,
                        value=True,
                    )
                ],
                outcome_type=KnowledgeRuleOutcome.WARNING,
            ),
            actor_role_code="ENGINEER_DESIGNER",
        )


def test_knowledge_rule_revision_is_new_draft() -> None:
    technology = _technology()
    rule = _knowledge_rule(technology)
    _activate(rule, technology, transition_knowledge_rule)
    revised = create_knowledge_rule_revision(
        rule,
        actor_role_code="ENGINEER_DESIGNER",
    )
    assert revised.id != rule.id
    assert revised.revision == 2
    assert revised.status == "DRAFT"
    assert revised.supersedes is rule


def test_existing_rbac_denies_customer_draft_creation() -> None:
    technology = _technology()
    with pytest.raises(PermissionError):
        create_consumption_norm_draft(
            technology,
            ConsumptionNormDraftInput(
                norm_code="DENIED",
                resource=_requirement_selector(technology),
                basis_quantity=1,
                basis_unit="m2",
                consumption_quantity=1,
                consumption_unit="kg",
            ),
            actor_role_code="CUSTOMER",
        )


@pytest.mark.asyncio
async def test_persistence_accepts_only_module2_drafts() -> None:
    technology = _technology()
    norm = _norm(technology)

    class Session:
        def __init__(self) -> None:
            self.added = []

        def add(self, value) -> None:
            self.added.append(value)

        async def flush(self) -> None:
            return None

    session = Session()
    await persist_knowledge_draft(session, norm)
    assert session.added == [norm]
    assert session.added[0].__tablename__.startswith("module2_")

    norm.status = "ACTIVE"
    with pytest.raises(Module2KnowledgeError, match="only DRAFT"):
        await persist_knowledge_draft(session, norm)


def test_service_has_no_m1_writes_formula_runtime_or_calculation_fields() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "MaterialDocument(",
        "KnowledgeResource(",
        "Material(",
        "ProviderWorkCostOffer",
        "SupplierPrice",
        "Estimate(",
        "Procurement(",
        "eval(",
        "exec(",
        "object_area",
        "estimate_total",
    ):
        assert forbidden not in source


def test_migration_is_additive_reversible_and_limited_to_m2_schema() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    executable = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    for table_name in (
        "module2_consumption_norms",
        "module2_compatibility_rules",
        "module2_knowledge_rules",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in executable
        assert f"DROP TABLE {table_name}" in sql
    assert "ALTER TABLE module2_technology_evidence_references" in executable
    assert "ALTER TABLE materials" not in executable
    assert "ALTER TABLE material_documents" not in executable
    assert "INSERT INTO" not in executable.upper()
    assert "UPDATE " not in executable.upper()
    assert "DELETE FROM" not in executable.upper()
    assert "DROP TABLE" not in executable.upper()
