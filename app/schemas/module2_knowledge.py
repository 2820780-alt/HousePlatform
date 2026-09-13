from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.module2_technology import TechnologyLifecycle


class StrictKnowledgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConditionSource(StrEnum):
    M1_MATERIAL_PROPERTY = "M1_MATERIAL_PROPERTY"
    CONTEXT = "CONTEXT"


class ConditionOperator(StrEnum):
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    IN = "IN"
    NOT_IN = "NOT_IN"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    BETWEEN = "BETWEEN"
    EXISTS = "EXISTS"


class EvidenceTargetKind(StrEnum):
    TECHNOLOGY = "TECHNOLOGY"
    LAYER = "LAYER"
    MATERIAL_REQUIREMENT = "MATERIAL_REQUIREMENT"
    NODE = "NODE"
    WORK_STEP = "WORK_STEP"
    CONSUMPTION_NORM = "CONSUMPTION_NORM"
    COMPATIBILITY_RULE = "COMPATIBILITY_RULE"
    KNOWLEDGE_RULE = "KNOWLEDGE_RULE"


class KnowledgeSelectorKind(StrEnum):
    CANONICAL_MATERIAL = "CANONICAL_MATERIAL"
    MATERIAL_CLASS = "MATERIAL_CLASS"
    MATERIAL_REQUIREMENT = "MATERIAL_REQUIREMENT"
    TECHNICAL_CONSTRAINTS = "TECHNICAL_CONSTRAINTS"
    ROLE = "ROLE"


class CompatibilityRelation(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"


class KnowledgeRuleOutcome(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    WARNING = "WARNING"
    PROHIBITION = "PROHIBITION"
    CONSTRAINT = "CONSTRAINT"
    INFORMATION = "INFORMATION"


class KnowledgeScopeKind(StrEnum):
    TECHNOLOGY = "TECHNOLOGY"
    LAYER = "LAYER"
    MATERIAL_REQUIREMENT = "MATERIAL_REQUIREMENT"
    NODE = "NODE"
    WORK_STEP = "WORK_STEP"
    CONSUMPTION_NORM = "CONSUMPTION_NORM"
    COMPATIBILITY_RULE = "COMPATIBILITY_RULE"


class EvaluationState(StrEnum):
    APPLIES = "APPLIES"
    DOES_NOT_APPLY = "DOES_NOT_APPLY"
    UNKNOWN = "UNKNOWN"
    REVIEW = "REVIEW"


class StructuredCondition(StrictKnowledgeModel):
    source: ConditionSource
    field: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z][A-Za-z0-9_.]*$",
    )
    operator: ConditionOperator
    value: Any = None
    required_for_activation: bool = False

    @model_validator(mode="after")
    def validate_operator_value(self) -> "StructuredCondition":
        if self.operator == ConditionOperator.EXISTS:
            if self.value is not None and not isinstance(self.value, bool):
                raise ValueError("EXISTS value must be boolean or omitted")
            return self
        if self.value is None:
            raise ValueError(f"{self.operator.value} requires a value")
        if self.operator in {ConditionOperator.IN, ConditionOperator.NOT_IN}:
            if not isinstance(self.value, (list, tuple)) or not self.value:
                raise ValueError(f"{self.operator.value} requires a non-empty list")
        if self.operator == ConditionOperator.BETWEEN:
            if not isinstance(self.value, (list, tuple)) or len(self.value) != 2:
                raise ValueError("BETWEEN requires exactly two boundary values")
        return self


class KnowledgeSelectorInput(StrictKnowledgeModel):
    selector_kind: KnowledgeSelectorKind
    canonical_material_id: UUID | None = None
    material_category_id: UUID | None = None
    material_type_id: UUID | None = None
    material_requirement_id: UUID | None = None
    material_role_code: str | None = Field(default=None, max_length=120)
    technical_constraints: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def selector_has_reference(self) -> "KnowledgeSelectorInput":
        valid = {
            KnowledgeSelectorKind.CANONICAL_MATERIAL: self.canonical_material_id is not None,
            KnowledgeSelectorKind.MATERIAL_CLASS: any(
                (self.material_category_id, self.material_type_id)
            ),
            KnowledgeSelectorKind.MATERIAL_REQUIREMENT: self.material_requirement_id
            is not None,
            KnowledgeSelectorKind.TECHNICAL_CONSTRAINTS: bool(
                self.technical_constraints
            ),
            KnowledgeSelectorKind.ROLE: bool(self.material_role_code),
        }
        if not valid[self.selector_kind]:
            raise ValueError(
                f"{self.selector_kind.value} requires matching reference semantics"
            )
        return self


class KnowledgeEvidenceInput(StrictKnowledgeModel):
    document_id: UUID | None = None
    knowledge_resource_id: UUID | None = None
    interpretation: str | None = None

    @model_validator(mode="after")
    def exactly_one_m1_reference(self) -> "KnowledgeEvidenceInput":
        if (self.document_id is None) == (self.knowledge_resource_id is None):
            raise ValueError(
                "evidence must reference exactly one M1 document or knowledge resource"
            )
        return self


class ConsumptionNormDraftInput(StrictKnowledgeModel):
    norm_code: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    scope_layer_id: UUID | None = None
    scope_requirement_id: UUID | None = None
    scope_work_step_id: UUID | None = None
    resource: KnowledgeSelectorInput
    basis_quantity: Decimal = Field(gt=0)
    basis_unit: str = Field(min_length=1, max_length=20)
    consumption_quantity: Decimal = Field(gt=0)
    consumption_unit: str = Field(min_length=1, max_length=20)
    conditions: list[StructuredCondition] = Field(default_factory=list)
    source_kind: str = Field(default="HUMAN_CURATED", max_length=40)
    blockers: list[str] = Field(default_factory=list)


class CompatibilityRuleDraftInput(StrictKnowledgeModel):
    rule_code: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    subject: KnowledgeSelectorInput
    object: KnowledgeSelectorInput
    relation: CompatibilityRelation
    conditions: list[StructuredCondition] = Field(default_factory=list)
    reason: str | None = None
    is_symmetric: bool = True
    source_kind: str = Field(default="HUMAN_CURATED", max_length=40)
    blockers: list[str] = Field(default_factory=list)


class KnowledgeRuleDraftInput(StrictKnowledgeModel):
    rule_code: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    scope_kind: KnowledgeScopeKind
    scope_reference: str | None = Field(default=None, max_length=120)
    conditions: list[StructuredCondition] = Field(min_length=1)
    outcome_type: KnowledgeRuleOutcome
    outcome_payload: dict[str, Any] = Field(default_factory=dict)
    source_kind: str = Field(default="HUMAN_CURATED", max_length=40)
    blockers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def scoped_reference_is_present(self) -> "KnowledgeRuleDraftInput":
        if (
            self.scope_kind != KnowledgeScopeKind.TECHNOLOGY
            and not self.scope_reference
        ):
            raise ValueError("non-technology rule scope requires scope_reference")
        return self


class CompatibilityEvaluation(StrictKnowledgeModel):
    state: EvaluationState
    relation: CompatibilityRelation = CompatibilityRelation.UNKNOWN
    blockers: tuple[str, ...] = tuple()
    matched_rule_ids: tuple[UUID, ...] = tuple()
    evidence_reference_ids: tuple[UUID, ...] = tuple()


class KnowledgeRuleEvaluation(StrictKnowledgeModel):
    state: EvaluationState
    outcome_type: KnowledgeRuleOutcome | None = None
    outcome_payload: dict[str, Any] = Field(default_factory=dict)
    blockers: tuple[str, ...] = tuple()
    evidence_reference_ids: tuple[UUID, ...] = tuple()


KnowledgeLifecycle = TechnologyLifecycle
