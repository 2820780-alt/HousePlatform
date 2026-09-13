from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.module2_technology import MODULE2_OWNER_CODE


class ConsumptionNorm(Base):
    __tablename__ = "module2_consumption_norms"
    __table_args__ = (
        UniqueConstraint(
            "technology_id",
            "norm_code",
            "revision",
            name="uq_module2_consumption_norm_revision",
        ),
        CheckConstraint("revision >= 1", name="ck_module2_consumption_norm_revision"),
        CheckConstraint("basis_quantity > 0", name="ck_module2_consumption_norm_basis"),
        CheckConstraint(
            "consumption_quantity > 0",
            name="ck_module2_consumption_norm_quantity",
        ),
        CheckConstraint(
            "resource_kind IN ('CANONICAL_MATERIAL', 'MATERIAL_CLASS', "
            "'MATERIAL_REQUIREMENT', 'TECHNICAL_CONSTRAINTS', 'ROLE')",
            name="ck_module2_consumption_norm_resource_kind",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'REVIEW', 'ACTIVE', 'ARCHIVED')",
            name="ck_module2_consumption_norm_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    norm_code: Mapped[str] = mapped_column(String(120), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scope_layer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_technology_layers.id", ondelete="SET NULL"),
        index=True,
    )
    scope_requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_technology_material_requirements.id", ondelete="SET NULL"),
        index=True,
    )
    scope_work_step_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_technology_work_steps.id", ondelete="SET NULL"),
        index=True,
    )
    resource_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_selector: Mapped[dict] = mapped_column(JSON, nullable=False)
    basis_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    basis_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    consumption_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    consumption_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    conditions: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    owner_module_code: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default=MODULE2_OWNER_CODE,
    )
    source_kind: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="HUMAN_CURATED",
    )
    blockers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_consumption_norms.id", ondelete="SET NULL"),
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

    technology = relationship("Technology", back_populates="consumption_norms")
    scope_layer = relationship("TechnologyLayer", foreign_keys=[scope_layer_id])
    scope_requirement = relationship(
        "TechnologyMaterialRequirement",
        foreign_keys=[scope_requirement_id],
    )
    scope_work_step = relationship("TechnologyWorkStep", foreign_keys=[scope_work_step_id])
    supersedes = relationship(
        "ConsumptionNorm",
        remote_side=[id],
        foreign_keys=[supersedes_id],
    )


class CompatibilityRule(Base):
    __tablename__ = "module2_compatibility_rules"
    __table_args__ = (
        UniqueConstraint(
            "technology_id",
            "rule_code",
            "revision",
            name="uq_module2_compatibility_rule_revision",
        ),
        CheckConstraint("revision >= 1", name="ck_module2_compatibility_rule_revision"),
        CheckConstraint(
            "subject_kind IN ('CANONICAL_MATERIAL', 'MATERIAL_CLASS', "
            "'MATERIAL_REQUIREMENT', 'TECHNICAL_CONSTRAINTS', 'ROLE')",
            name="ck_module2_compatibility_subject_kind",
        ),
        CheckConstraint(
            "object_kind IN ('CANONICAL_MATERIAL', 'MATERIAL_CLASS', "
            "'MATERIAL_REQUIREMENT', 'TECHNICAL_CONSTRAINTS', 'ROLE')",
            name="ck_module2_compatibility_object_kind",
        ),
        CheckConstraint(
            "relation IN ('COMPATIBLE', 'INCOMPATIBLE', 'CONDITIONAL', 'UNKNOWN')",
            name="ck_module2_compatibility_relation",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'REVIEW', 'ACTIVE', 'ARCHIVED')",
            name="ck_module2_compatibility_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_code: Mapped[str] = mapped_column(String(120), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    subject_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_selector: Mapped[dict] = mapped_column(JSON, nullable=False)
    object_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    object_selector: Mapped[dict] = mapped_column(JSON, nullable=False)
    relation: Mapped[str] = mapped_column(String(30), nullable=False)
    conditions: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    reason: Mapped[str | None] = mapped_column(Text)
    is_symmetric: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    owner_module_code: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default=MODULE2_OWNER_CODE,
    )
    source_kind: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="HUMAN_CURATED",
    )
    blockers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_compatibility_rules.id", ondelete="SET NULL"),
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

    technology = relationship("Technology", back_populates="compatibility_rules")
    supersedes = relationship(
        "CompatibilityRule",
        remote_side=[id],
        foreign_keys=[supersedes_id],
    )


class KnowledgeRule(Base):
    __tablename__ = "module2_knowledge_rules"
    __table_args__ = (
        UniqueConstraint(
            "technology_id",
            "rule_code",
            "revision",
            name="uq_module2_knowledge_rule_revision",
        ),
        CheckConstraint(
            "revision >= 1",
            name="ck_module2_knowledge_rule_revision",
        ),
        CheckConstraint(
            "scope_kind IN ('TECHNOLOGY', 'LAYER', 'MATERIAL_REQUIREMENT', "
            "'NODE', 'WORK_STEP', 'CONSUMPTION_NORM', 'COMPATIBILITY_RULE')",
            name="ck_module2_knowledge_rule_scope_kind",
        ),
        CheckConstraint(
            "scope_kind = 'TECHNOLOGY' OR scope_reference IS NOT NULL",
            name="ck_module2_knowledge_rule_scope_reference",
        ),
        CheckConstraint(
            "outcome_type IN ('REQUIREMENT', 'WARNING', 'PROHIBITION', "
            "'CONSTRAINT', 'INFORMATION')",
            name="ck_module2_knowledge_rule_outcome",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'REVIEW', 'ACTIVE', 'ARCHIVED')",
            name="ck_module2_knowledge_rule_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    technology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module2_technologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_code: Mapped[str] = mapped_column(String(120), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scope_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_reference: Mapped[str | None] = mapped_column(String(120))
    conditions: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    outcome_type: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    owner_module_code: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default=MODULE2_OWNER_CODE,
    )
    source_kind: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="HUMAN_CURATED",
    )
    blockers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module2_knowledge_rules.id", ondelete="SET NULL"),
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

    technology = relationship("Technology", back_populates="knowledge_rules")
    supersedes = relationship(
        "KnowledgeRule",
        remote_side=[id],
        foreign_keys=[supersedes_id],
    )
