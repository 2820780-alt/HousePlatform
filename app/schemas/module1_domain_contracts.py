from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.models.enums import VerificationStatus
from app.schemas.material_hub_contracts import (
    MODULE_01_MATERIAL_HUB,
    CharacteristicSchema,
    DocumentRecord,
    ExtractionProfile,
    MaterialCanonicalObject,
    MaterialConstructionUsage,
    Module01Contract,
    PriceObservation,
    RawIngestionItem,
    SourceProfile,
    WorkRateObservation,
)


# Domain names from the Module №1 target architecture.
# These are DTO aliases over the existing Material Hub contracts, not new ORM models.
CanonicalMaterial = MaterialCanonicalObject
Document = DocumentRecord
DocumentEvidence = DocumentRecord
MaterialRole = MaterialConstructionUsage


class CompatibilityRule(Module01Contract):
    id: UUID | None = None
    rule_code: str
    primary_material_group_code: str | None = None
    secondary_material_group_code: str | None = None
    context: str | None = None
    decision: Literal["allowed", "warning", "forbidden"]
    reason: str | None = None
    required_additional_material_groups: list[str] = Field(default_factory=list)
    status: VerificationStatus = VerificationStatus.NEEDS_REVIEW


class AlternativeRule(Module01Contract):
    id: UUID | None = None
    rule_code: str
    source_material_group_code: str
    alternative_material_group_code: str
    alternative_type: Literal["full_analog", "technical", "functional", "conditional", "forbidden"]
    recalculation_required: bool = False
    technology_change_required: bool = False
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: VerificationStatus = VerificationStatus.NEEDS_REVIEW


class UnitConversionRule(Module01Contract):
    id: UUID | None = None
    rule_code: str
    from_unit: str
    to_unit: str
    material_group_code: str | None = None
    multiplier: Decimal | None = None
    formula_code: str | None = None
    required_characteristics: list[str] = Field(default_factory=list)
    status: VerificationStatus = VerificationStatus.NEEDS_REVIEW


class QualityScore(Module01Contract):
    id: UUID | None = None
    entity_type: Literal["material", "raw_ingestion_item", "source", "document", "technical_profile"]
    entity_id: UUID | None = None
    score: Decimal
    missing_required_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    calculated_at: str | None = None


class MaterialTechnicalProfile(Module01Contract):
    material_id: UUID | None = None
    material_group_code: str | None = None
    characteristics: dict[str, Any] = Field(default_factory=dict)
    packaging_profile: dict[str, Any] = Field(default_factory=dict)
    calculation_readiness: Literal["ready", "partial", "not_ready"] = "partial"
    missing_for_calculation: list[str] = Field(default_factory=list)
    evidence_document_ids: list[UUID] = Field(default_factory=list)


class TechnologyInputPackage(Module01Contract):
    target_module_code: str | None = "MODULE_02_KNOWLEDGE_BASE"
    material: CanonicalMaterial
    technical_profile: MaterialTechnicalProfile
    compatibility_rules: list[CompatibilityRule] = Field(default_factory=list)
    alternative_rules: list[AlternativeRule] = Field(default_factory=list)
    unit_conversion_rules: list[UnitConversionRule] = Field(default_factory=list)
    evidence_documents: list[DocumentEvidence] = Field(default_factory=list)
    source_module_code: str | None = MODULE_01_MATERIAL_HUB

