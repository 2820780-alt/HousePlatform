from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


MODULE2_OWNER_CODE = "MODULE_02_KNOWLEDGE_BASE"


class Technology(Base):
    __tablename__ = "module2_technologies"
    __table_args__ = (
        UniqueConstraint("technology_code", "revision", name="uq_module2_technology_code_revision"),
        CheckConstraint("revision >= 1", name="ck_module2_technology_revision_positive"),
        CheckConstraint(
            "status IN ('DRAFT', 'REVIEW', 'ACTIVE', 'ARCHIVED')",
            name="ck_module2_technology_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system_code: Mapped[str | None] = mapped_column(String(120), index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_technology_categories.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    owner_module_code: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default=MODULE2_OWNER_CODE,
    )
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="HUMAN_CURATED")
    input_missing_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    input_blockers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="SET NULL"),
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    supersedes = relationship(
        "Technology",
        remote_side=[id],
        foreign_keys=[supersedes_id],
    )
    category = relationship("TechnologyCategory")
    requirements = relationship(
        "TechnologyMaterialRequirement",
        back_populates="technology",
        cascade="all, delete-orphan",
    )
    layers = relationship(
        "TechnologyLayer",
        back_populates="technology",
        cascade="all, delete-orphan",
        order_by="TechnologyLayer.position",
    )
    nodes = relationship(
        "TechnologyNode",
        back_populates="technology",
        cascade="all, delete-orphan",
    )
    work_steps = relationship(
        "TechnologyWorkStep",
        back_populates="technology",
        cascade="all, delete-orphan",
        order_by="TechnologyWorkStep.position",
    )
    evidence_references = relationship(
        "TechnologyEvidenceReference",
        back_populates="technology",
        cascade="all, delete-orphan",
    )
    consumption_norms = relationship(
        "ConsumptionNorm",
        back_populates="technology",
        cascade="all, delete-orphan",
    )
    compatibility_rules = relationship(
        "CompatibilityRule",
        back_populates="technology",
        cascade="all, delete-orphan",
    )
    knowledge_rules = relationship(
        "KnowledgeRule",
        back_populates="technology",
        cascade="all, delete-orphan",
    )


class TechnologyMaterialRequirement(Base):
    __tablename__ = "module2_technology_material_requirements"
    __table_args__ = (
        UniqueConstraint("technology_id", "code", name="uq_module2_requirement_code"),
        CheckConstraint(
            "selector_kind IN ('CANONICAL_MATERIAL', 'MATERIAL_CLASS', "
            "'TECHNICAL_CONSTRAINTS', 'ROLE')",
            name="ck_module2_requirement_selector_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    selector_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    material_role_code: Mapped[str | None] = mapped_column(String(120))
    canonical_material_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("materials.id", ondelete="RESTRICT"),
        index=True,
    )
    material_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("material_categories.id", ondelete="RESTRICT"),
        index=True,
    )
    material_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("material_types.id", ondelete="RESTRICT"),
        index=True,
    )
    technical_constraints: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)

    technology = relationship("Technology", back_populates="requirements")


class TechnologyLayer(Base):
    __tablename__ = "module2_technology_layers"
    __table_args__ = (
        UniqueConstraint("technology_id", "position", name="uq_module2_layer_position"),
        CheckConstraint("position >= 1", name="ck_module2_layer_position_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    functional_role: Mapped[str] = mapped_column(String(120), nullable=False)
    material_requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_technology_material_requirements.id", ondelete="RESTRICT"),
        index=True,
    )
    thickness_expression: Mapped[str | None] = mapped_column(String(500))
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    restrictions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    technology = relationship("Technology", back_populates="layers")
    material_requirement = relationship("TechnologyMaterialRequirement")


class TechnologyNode(Base):
    __tablename__ = "module2_technology_nodes"
    __table_args__ = (
        UniqueConstraint("technology_id", "code", name="uq_module2_node_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    node_type: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    technology = relationship("Technology", back_populates="nodes")


class TechnologyWorkStep(Base):
    __tablename__ = "module2_technology_work_steps"
    __table_args__ = (
        UniqueConstraint("technology_id", "position", name="uq_module2_work_step_position"),
        CheckConstraint("position >= 1", name="ck_module2_work_step_position_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    work_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    applicability_expression: Mapped[str | None] = mapped_column(Text)
    dependency_step_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    instructions: Mapped[str | None] = mapped_column(Text)

    technology = relationship("Technology", back_populates="work_steps")


class TechnologyEvidenceReference(Base):
    __tablename__ = "module2_technology_evidence_references"
    __table_args__ = (
        CheckConstraint(
            "(document_id IS NOT NULL AND knowledge_resource_id IS NULL) OR "
            "(document_id IS NULL AND knowledge_resource_id IS NOT NULL)",
            name="ck_module2_evidence_exactly_one_reference",
        ),
        CheckConstraint(
            "target_kind IN ('TECHNOLOGY', 'LAYER', 'MATERIAL_REQUIREMENT', "
            "'NODE', 'WORK_STEP', 'CONSUMPTION_NORM', 'COMPATIBILITY_RULE', "
            "'KNOWLEDGE_RULE')",
            name="ck_module2_evidence_target_kind",
        ),
        CheckConstraint(
            "target_kind = 'TECHNOLOGY' OR target_reference IS NOT NULL",
            name="ck_module2_evidence_target_reference",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("material_documents.id", ondelete="RESTRICT"),
        index=True,
    )
    knowledge_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_resources.id", ondelete="RESTRICT"),
        index=True,
    )
    target_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="TECHNOLOGY")
    target_reference: Mapped[str | None] = mapped_column(String(120))
    interpretation: Mapped[str | None] = mapped_column(Text)

    technology = relationship("Technology", back_populates="evidence_references")
