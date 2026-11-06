from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TechnologyLifecycle(StrEnum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class MaterialRequirementSelector(StrEnum):
    CANONICAL_MATERIAL = "CANONICAL_MATERIAL"
    MATERIAL_CLASS = "MATERIAL_CLASS"
    TECHNICAL_CONSTRAINTS = "TECHNICAL_CONSTRAINTS"
    ROLE = "ROLE"


class TechnologyMaterialRequirementInput(BaseModel):
    code: str = Field(min_length=1, max_length=120, pattern=r"^[A-Z][A-Z0-9_]*$")
    selector_kind: MaterialRequirementSelector
    material_role_code: str | None = Field(default=None, max_length=120)
    canonical_material_id: UUID | None = None
    material_category_id: UUID | None = None
    material_type_id: UUID | None = None
    technical_constraints: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    @model_validator(mode="after")
    def selector_has_reference_semantics(self) -> "TechnologyMaterialRequirementInput":
        selectors = {
            MaterialRequirementSelector.CANONICAL_MATERIAL: self.canonical_material_id is not None,
            MaterialRequirementSelector.MATERIAL_CLASS: any(
                (self.material_category_id, self.material_type_id)
            ),
            MaterialRequirementSelector.TECHNICAL_CONSTRAINTS: bool(self.technical_constraints),
            MaterialRequirementSelector.ROLE: bool(self.material_role_code),
        }
        if not selectors[self.selector_kind]:
            raise ValueError(f"{self.selector_kind.value} requires its matching reference semantics")
        return self


class TechnologyLayerInput(BaseModel):
    position: int = Field(ge=1)
    functional_role: str = Field(min_length=1, max_length=120)
    requirement_code: str | None = Field(default=None, max_length=120)
    thickness_expression: str | None = Field(default=None, max_length=500)
    is_mandatory: bool = True
    notes: str | None = None
    restrictions: dict[str, Any] = Field(default_factory=dict)


class TechnologyNodeInput(BaseModel):
    code: str = Field(min_length=1, max_length=120, pattern=r"^[A-Z][A-Z0-9_]*$")
    node_type: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)


class TechnologyWorkStepInput(BaseModel):
    position: int = Field(ge=1)
    work_code: str = Field(min_length=1, max_length=120)
    applicability_expression: str | None = None
    dependency_step_codes: list[str] = Field(default_factory=list)
    instructions: str | None = None


class TechnologyEvidenceReferenceInput(BaseModel):
    document_id: UUID | None = None
    knowledge_resource_id: UUID | None = None
    target_kind: str = Field(default="TECHNOLOGY", max_length=40)
    target_reference: str | None = Field(default=None, max_length=120)
    interpretation: str | None = None

    @model_validator(mode="after")
    def exactly_one_m1_reference(self) -> "TechnologyEvidenceReferenceInput":
        if (self.document_id is None) == (self.knowledge_resource_id is None):
            raise ValueError("evidence must reference exactly one M1 document or knowledge resource")
        allowed_targets = {
            "TECHNOLOGY",
            "LAYER",
            "MATERIAL_REQUIREMENT",
            "NODE",
            "WORK_STEP",
            "CONSUMPTION_NORM",
            "COMPATIBILITY_RULE",
            "KNOWLEDGE_RULE",
        }
        if self.target_kind not in allowed_targets:
            raise ValueError("unsupported Module2 evidence target_kind")
        if (
            self.target_kind != "TECHNOLOGY"
            and not self.target_reference
        ):
            raise ValueError("non-technology evidence requires target_reference")
        return self


class TechnologyDraftInput(BaseModel):
    technology_code: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    system_code: str | None = Field(default=None, max_length=120)
    category_id: UUID | None = None
    source_kind: str = Field(default="HUMAN_CURATED", max_length=40)
    requirements: list[TechnologyMaterialRequirementInput] = Field(default_factory=list)
    layers: list[TechnologyLayerInput] = Field(default_factory=list)
    nodes: list[TechnologyNodeInput] = Field(default_factory=list)
    work_steps: list[TechnologyWorkStepInput] = Field(default_factory=list)
    evidence_references: list[TechnologyEvidenceReferenceInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def aggregate_keys_are_unique(self) -> "TechnologyDraftInput":
        _require_unique((item.code for item in self.requirements), "requirement code")
        _require_unique((item.position for item in self.layers), "layer position")
        _require_unique((item.code for item in self.nodes), "node code")
        _require_unique((item.position for item in self.work_steps), "work-step position")

        requirement_codes = {item.code for item in self.requirements}
        missing = {
            item.requirement_code
            for item in self.layers
            if item.requirement_code and item.requirement_code not in requirement_codes
        }
        if missing:
            raise ValueError(f"layers reference unknown requirements: {sorted(missing)}")
        return self


class TechnologyDraftUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    system_code: str | None = Field(default=None, max_length=120)
    category_id: UUID | None = None


class Module2InputAcceptance(BaseModel):
    canonical_material_id: UUID | None = None
    missing_fields: tuple[str, ...] = tuple()
    blockers: tuple[str, ...] = tuple()
    accepted_for_active_technology: bool = False
    ownership: str = "M1_REFERENCE_ONLY"


class ConsumptionNormContract(BaseModel):
    technology_code: str
    technology_revision: int = Field(ge=1)
    requirement_code: str
    basis_quantity: Decimal = Field(gt=0)
    basis_unit: str
    consumption_quantity: Decimal = Field(gt=0)
    consumption_unit: str
    conditions: dict[str, Any] = Field(default_factory=dict)
    evidence_reference_ids: list[UUID] = Field(default_factory=list)


class KnowledgeRuleContract(BaseModel):
    technology_code: str
    technology_revision: int = Field(ge=1)
    condition_expression: dict[str, Any]
    effect_type: str
    effect_payload: dict[str, Any]
    evidence_reference_ids: list[UUID] = Field(default_factory=list)


def _require_unique(values, label: str) -> None:
    sequence = list(values)
    if len(sequence) != len(set(sequence)):
        raise ValueError(f"duplicate {label}")
