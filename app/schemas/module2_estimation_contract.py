from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.module2_knowledge import (
    CompatibilityRelation,
    ConditionOperator,
    ConditionSource,
    KnowledgeRuleOutcome,
    KnowledgeSelectorKind,
)
from app.schemas.module2_technology import TechnologyLifecycle


MODULE2_ESTIMATION_CONTRACT_VERSION = "1"
MODULE2_SOURCE_MODULE_CODE = "MODULE_02_KNOWLEDGE_BASE"
MODULE5_TARGET_MODULE_CODE = "MODULE_05_ESTIMATE_ENGINE"


class EstimationContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QuantityBasis(StrEnum):
    AREA = "AREA"
    AREA_THICKNESS = "AREA_THICKNESS"
    VOLUME = "VOLUME"
    LENGTH = "LENGTH"
    COUNT = "COUNT"
    MASS = "MASS"
    UNKNOWN = "UNKNOWN"


class EstimationIssue(EstimationContractModel):
    code: str = Field(min_length=1, max_length=160)
    scope_type: str = Field(min_length=1, max_length=80)
    scope_id: UUID | None = None
    detail: str | None = None


class EstimationCondition(EstimationContractModel):
    source: ConditionSource
    field: str
    operator: ConditionOperator
    value: Any = None
    required_for_activation: bool = False


class EstimationSelector(EstimationContractModel):
    selector_kind: KnowledgeSelectorKind
    canonical_material_id: UUID | None = None
    material_category_id: UUID | None = None
    material_type_id: UUID | None = None
    material_requirement_id: UUID | None = None
    material_role_code: str | None = None
    technical_constraints: dict[str, Any] = Field(default_factory=dict)


class EstimationTechnologyRevision(EstimationContractModel):
    technology_id: UUID
    technology_code: str
    revision: int = Field(ge=1)
    lifecycle_status: TechnologyLifecycle
    system_code: str | None = None
    source_kind: str


class EstimationMaterialRequirement(EstimationContractModel):
    requirement_id: UUID
    requirement_code: str
    selector: EstimationSelector
    layer_ids: tuple[UUID, ...] = tuple()
    mandatory: bool
    restrictions: tuple[dict[str, Any], ...] = tuple()
    evidence_reference_ids: tuple[UUID, ...] = tuple()
    blockers: tuple[str, ...] = tuple()


class EstimationLayer(EstimationContractModel):
    layer_id: UUID
    order: int = Field(ge=1)
    functional_role: str
    material_requirement_id: UUID | None = None
    thickness_expression: str | None = None
    mandatory: bool
    restrictions: dict[str, Any] = Field(default_factory=dict)
    evidence_reference_ids: tuple[UUID, ...] = tuple()
    blockers: tuple[str, ...] = tuple()


class EstimationWorkStep(EstimationContractModel):
    work_step_id: UUID
    order: int = Field(ge=1)
    work_code: str
    work_group: str | None = None
    applicability_expression: str | None = None
    dependency_step_codes: tuple[str, ...] = tuple()
    consumption_norm_ids: tuple[UUID, ...] = tuple()
    evidence_reference_ids: tuple[UUID, ...] = tuple()
    blockers: tuple[str, ...] = tuple()


class EstimationConsumptionNorm(EstimationContractModel):
    norm_id: UUID
    norm_code: str
    revision: int = Field(ge=1)
    scope_layer_id: UUID | None = None
    scope_requirement_id: UUID | None = None
    scope_work_step_id: UUID | None = None
    resource: EstimationSelector
    quantity_basis: QuantityBasis
    basis_quantity: Decimal = Field(gt=0)
    basis_unit: str
    consumption_quantity: Decimal = Field(gt=0)
    consumption_unit: str
    conditions: tuple[EstimationCondition, ...] = tuple()
    evidence_reference_ids: tuple[UUID, ...] = tuple()
    blockers: tuple[str, ...] = tuple()


class EstimationCompatibilityConstraint(EstimationContractModel):
    rule_id: UUID
    rule_code: str
    revision: int = Field(ge=1)
    subject: EstimationSelector
    object: EstimationSelector
    relation: CompatibilityRelation
    conditions: tuple[EstimationCondition, ...] = tuple()
    reason: str | None = None
    symmetric: bool
    evidence_reference_ids: tuple[UUID, ...] = tuple()
    blockers: tuple[str, ...] = tuple()


class EstimationKnowledgeConstraint(EstimationContractModel):
    rule_id: UUID
    rule_code: str
    revision: int = Field(ge=1)
    scope_kind: str
    scope_reference: str | None = None
    conditions: tuple[EstimationCondition, ...] = tuple()
    outcome_type: KnowledgeRuleOutcome
    outcome_payload: dict[str, Any] = Field(default_factory=dict)
    evidence_reference_ids: tuple[UUID, ...] = tuple()
    blockers: tuple[str, ...] = tuple()


class EstimationEvidenceReference(EstimationContractModel):
    evidence_reference_id: UUID
    document_id: UUID | None = None
    knowledge_resource_id: UUID | None = None
    target_kind: str
    target_reference: str | None = None
    interpretation: str | None = None
    verified: bool


class Module5EstimationInputPackage(EstimationContractModel):
    contract_version: Literal["1"] = MODULE2_ESTIMATION_CONTRACT_VERSION
    source_module_code: Literal["MODULE_02_KNOWLEDGE_BASE"] = MODULE2_SOURCE_MODULE_CODE
    target_module_code: Literal["MODULE_05_ESTIMATE_ENGINE"] = MODULE5_TARGET_MODULE_CODE
    technology: EstimationTechnologyRevision
    ready_for_estimation: bool
    blockers: tuple[EstimationIssue, ...] = tuple()
    warnings: tuple[EstimationIssue, ...] = tuple()
    material_requirements: tuple[EstimationMaterialRequirement, ...] = tuple()
    layers: tuple[EstimationLayer, ...] = tuple()
    work_steps: tuple[EstimationWorkStep, ...] = tuple()
    consumption_norms: tuple[EstimationConsumptionNorm, ...] = tuple()
    compatibility_constraints: tuple[EstimationCompatibilityConstraint, ...] = tuple()
    knowledge_constraints: tuple[EstimationKnowledgeConstraint, ...] = tuple()
    evidence_references: tuple[EstimationEvidenceReference, ...] = tuple()
    no_object_quantity_result: Literal[True] = True
    no_price_result: Literal[True] = True
    no_side_effects: Literal[True] = True

    @model_validator(mode="after")
    def ready_package_is_active_and_unblocked(self) -> "Module5EstimationInputPackage":
        if self.ready_for_estimation and self.technology.lifecycle_status != TechnologyLifecycle.ACTIVE:
            raise ValueError("ready estimation input must reference an ACTIVE technology revision")
        if self.ready_for_estimation and self.blockers:
            raise ValueError("ready estimation input cannot contain blockers")
        return self
