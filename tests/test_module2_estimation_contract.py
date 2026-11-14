from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.models.enums import DocumentStatus, DocumentType, UserRole
from app.models.material_document import MaterialDocument
from app.models.module2_knowledge import ConsumptionNorm
from app.models.module2_technology import Technology
from app.models.user import User
from app.schemas.module2_estimation_contract import (
    EstimationContractModel,
    EstimationMaterialRequirement,
    EstimationSelector,
    Module5EstimationInputPackage,
    QuantityBasis,
)
from app.schemas.module2_knowledge import (
    CompatibilityRelation,
    CompatibilityRuleDraftInput,
    ConditionOperator,
    ConditionSource,
    ConsumptionNormDraftInput,
    KnowledgeEvidenceInput,
    KnowledgeRuleDraftInput,
    KnowledgeRuleOutcome,
    KnowledgeScopeKind,
    KnowledgeSelectorInput,
    KnowledgeSelectorKind,
    StructuredCondition,
)
from app.schemas.module2_technology import (
    MaterialRequirementSelector,
    TechnologyDraftInput,
    TechnologyLayerInput,
    TechnologyLifecycle,
    TechnologyMaterialRequirementInput,
    TechnologyWorkStepInput,
)
from app.services.module1_work_catalog import list_work_items
from app.services.module2_estimation_export import (
    Module2EstimationContractError,
    build_module5_estimation_input_package,
)
from app.services.module2_knowledge_foundation import (
    attach_evidence_reference,
    create_compatibility_rule_draft,
    create_consumption_norm_draft,
    create_knowledge_rule_draft,
    transition_compatibility_rule,
    transition_consumption_norm,
    transition_knowledge_rule,
    verify_evidence_references,
)
from app.services.module2_technology_foundation import (
    build_draft_technology,
    create_next_revision,
    persist_technology_draft,
    transition_technology,
)


ROOT = Path(__file__).resolve().parents[1]
ADMIN = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)


@asynccontextmanager
async def _session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            session.add(
                User(
                    id=ADMIN.id,
                    email="module2-estimation-contract@example.test",
                    password_hash="test-only",
                    role=ADMIN.role,
                )
            )
            await session.flush()
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()
    await engine.dispose()


def _draft(*, revision_code: str | None = None) -> Technology:
    requirement = TechnologyMaterialRequirementInput(
        code="ADHESIVE",
        selector_kind=MaterialRequirementSelector.ROLE,
        material_role_code="MASONRY_ADHESIVE",
    )
    return build_draft_technology(
        TechnologyDraftInput(
            technology_code=revision_code or f"ESTIMATION_{uuid4().hex[:10].upper()}",
            name="Synthetic estimation contract fixture",
            system_code="EXTERNAL_WALL",
            requirements=[requirement],
            layers=[
                TechnologyLayerInput(
                    position=1,
                    functional_role="MASONRY",
                    requirement_code="ADHESIVE",
                    thickness_expression="project_wall_thickness_mm",
                    restrictions={"minimum_temperature_c": 5},
                )
            ],
            work_steps=[
                TechnologyWorkStepInput(
                    position=1,
                    work_code=list_work_items()[0].work_code,
                    applicability_expression="wall_area_m2 > 0",
                )
            ],
        ),
        actor_role_code="ADMIN",
        created_by_user_id=ADMIN.id,
    )


def _requirement_selector(technology: Technology) -> KnowledgeSelectorInput:
    return KnowledgeSelectorInput(
        selector_kind=KnowledgeSelectorKind.MATERIAL_REQUIREMENT,
        material_requirement_id=technology.requirements[0].id,
    )


async def _persist_active_fixture(session: AsyncSession) -> tuple[Technology, MaterialDocument]:
    document = MaterialDocument(
        document_type=DocumentType.TECH_CARD,
        title="Synthetic M2 estimation contract evidence",
        status=DocumentStatus.ACTIVE,
    )
    session.add(document)
    technology = _draft()
    await persist_technology_draft(session, technology)
    await session.flush()
    await session.refresh(
        technology,
        attribute_names=[
            "requirements",
            "layers",
            "nodes",
            "work_steps",
            "evidence_references",
            "consumption_norms",
            "compatibility_rules",
            "knowledge_rules",
        ],
    )
    transition_technology(technology, TechnologyLifecycle.REVIEW, actor_role_code="ADMIN")
    transition_technology(technology, TechnologyLifecycle.ACTIVE, actor_role_code="ADMIN")

    condition = StructuredCondition(
        source=ConditionSource.CONTEXT,
        field="air_temperature_c",
        operator=ConditionOperator.GTE,
        value=5,
    )
    norm = create_consumption_norm_draft(
        technology,
        ConsumptionNormDraftInput(
            norm_code="ADHESIVE_PER_AREA",
            scope_layer_id=technology.layers[0].id,
            scope_requirement_id=technology.requirements[0].id,
            scope_work_step_id=technology.work_steps[0].id,
            resource=_requirement_selector(technology),
            basis_quantity="1",
            basis_unit="m2",
            consumption_quantity="5",
            consumption_unit="kg",
            conditions=[condition],
        ),
        actor_role_code="ADMIN",
        created_by_user_id=ADMIN.id,
    )
    compatibility = create_compatibility_rule_draft(
        technology,
        CompatibilityRuleDraftInput(
            rule_code="ADHESIVE_SUBSTRATE_CONDITION",
            subject=_requirement_selector(technology),
            object=_requirement_selector(technology),
            relation=CompatibilityRelation.CONDITIONAL,
            conditions=[condition],
            reason="Synthetic test rule only",
        ),
        actor_role_code="ADMIN",
        created_by_user_id=ADMIN.id,
    )
    rule = create_knowledge_rule_draft(
        technology,
        KnowledgeRuleDraftInput(
            rule_code="MINIMUM_APPLICATION_TEMPERATURE",
            scope_kind=KnowledgeScopeKind.CONSUMPTION_NORM,
            scope_reference=str(norm.id),
            conditions=[condition],
            outcome_type=KnowledgeRuleOutcome.CONSTRAINT,
            outcome_payload={"minimum_temperature_c": 5},
        ),
        actor_role_code="ADMIN",
        created_by_user_id=ADMIN.id,
    )

    evidence = []
    for entity in (norm, compatibility, rule):
        evidence.append(
            attach_evidence_reference(
                technology,
                entity,
                KnowledgeEvidenceInput(
                    document_id=document.id,
                    interpretation="Synthetic fixture traceability",
                ),
                actor_role_code="ADMIN",
            )
        )
    await session.flush()
    verified = await verify_evidence_references(session, technology.evidence_references)

    transition_consumption_norm(
        norm,
        TechnologyLifecycle.REVIEW,
        technology=technology,
        evidence_references=technology.evidence_references,
        actor_role_code="ADMIN",
    )
    transition_consumption_norm(
        norm,
        TechnologyLifecycle.ACTIVE,
        technology=technology,
        evidence_references=technology.evidence_references,
        verified_evidence_reference_ids=verified,
        actor_role_code="ADMIN",
    )
    transition_compatibility_rule(
        compatibility,
        TechnologyLifecycle.REVIEW,
        technology=technology,
        evidence_references=technology.evidence_references,
        actor_role_code="ADMIN",
    )
    transition_compatibility_rule(
        compatibility,
        TechnologyLifecycle.ACTIVE,
        technology=technology,
        evidence_references=technology.evidence_references,
        verified_evidence_reference_ids=verified,
        peer_rules=technology.compatibility_rules,
        actor_role_code="ADMIN",
    )
    transition_knowledge_rule(
        rule,
        TechnologyLifecycle.REVIEW,
        technology=technology,
        evidence_references=technology.evidence_references,
        actor_role_code="ADMIN",
    )
    transition_knowledge_rule(
        rule,
        TechnologyLifecycle.ACTIVE,
        technology=technology,
        evidence_references=technology.evidence_references,
        verified_evidence_reference_ids=verified,
        peer_rules=technology.knowledge_rules,
        actor_role_code="ADMIN",
    )
    await session.flush()
    return technology, document


@pytest.mark.asyncio(loop_scope="module")
async def test_active_revision_builds_ready_typed_estimation_input() -> None:
    async with _session() as session:
        technology, _ = await _persist_active_fixture(session)
        package = await build_module5_estimation_input_package(session, technology.id)

        assert package.contract_version == "1"
        assert package.technology.technology_id == technology.id
        assert package.technology.revision == 1
        assert package.technology.lifecycle_status == TechnologyLifecycle.ACTIVE
        assert package.ready_for_estimation is True
        assert package.blockers == tuple()
        assert package.consumption_norms[0].quantity_basis == QuantityBasis.AREA
        assert package.consumption_norms[0].basis_quantity == 1
        assert package.consumption_norms[0].consumption_quantity == 5
        work_item = list_work_items()[0]
        assert package.work_steps[0].work_code == work_item.work_code
        assert package.work_steps[0].work_group == work_item.work_group
        assert package.work_steps[0].order == 1
        assert package.work_steps[0].consumption_norm_ids == (
            package.consumption_norms[0].norm_id,
        )
        assert len(package.compatibility_constraints) == 1
        assert len(package.knowledge_constraints) == 1
        assert len(package.evidence_references) == 3
        assert all(item.verified for item in package.evidence_references)


@pytest.mark.asyncio(loop_scope="module")
async def test_contract_serialization_round_trip_preserves_revision_and_traceability() -> None:
    async with _session() as session:
        technology, _ = await _persist_active_fixture(session)
        package = await build_module5_estimation_input_package(session, technology.id)
        payload = package.model_dump(mode="json")
        restored = Module5EstimationInputPackage.model_validate(payload)

        assert restored == package
        assert restored.technology.technology_id == technology.id
        assert restored.work_steps[0].work_group == package.work_steps[0].work_group
        assert restored.work_steps[0].work_code == package.work_steps[0].work_code
        assert restored.work_steps[0].order == package.work_steps[0].order
        assert restored.consumption_norms[0].evidence_reference_ids
        assert set(restored.consumption_norms[0].evidence_reference_ids).issubset(
            {item.evidence_reference_id for item in restored.evidence_references}
        )


@pytest.mark.asyncio(loop_scope="module")
async def test_draft_revision_is_rejected_for_production_export() -> None:
    async with _session() as session:
        technology = _draft()
        await persist_technology_draft(session, technology)

        with pytest.raises(Module2EstimationContractError, match="ACTIVE"):
            await build_module5_estimation_input_package(session, technology.id)


@pytest.mark.asyncio(loop_scope="module")
async def test_active_norm_without_evidence_returns_structured_blocker() -> None:
    async with _session() as session:
        technology = _draft()
        await persist_technology_draft(session, technology)
        await session.refresh(
            technology,
            attribute_names=["requirements", "consumption_norms"],
        )
        transition_technology(technology, "REVIEW", actor_role_code="ADMIN")
        transition_technology(technology, "ACTIVE", actor_role_code="ADMIN")
        norm = create_consumption_norm_draft(
            technology,
            ConsumptionNormDraftInput(
                norm_code="UNVERIFIED_NORM",
                resource=_requirement_selector(technology),
                basis_quantity=1,
                basis_unit="m2",
                consumption_quantity=5,
                consumption_unit="kg",
            ),
            actor_role_code="ADMIN",
            created_by_user_id=ADMIN.id,
        )
        norm.status = TechnologyLifecycle.ACTIVE.value
        await session.flush()

        package = await build_module5_estimation_input_package(session, technology.id)

        assert package.ready_for_estimation is False
        assert any(
            issue.code == "missing_evidence"
            and issue.scope_type == "CONSUMPTION_NORM"
            and issue.scope_id == norm.id
            for issue in package.blockers
        )


@pytest.mark.asyncio(loop_scope="module")
async def test_unknown_unit_is_not_converted_or_defaulted() -> None:
    async with _session() as session:
        technology, _ = await _persist_active_fixture(session)
        norm = technology.consumption_norms[0]
        norm.basis_unit = "mystery_unit"
        await session.flush()

        package = await build_module5_estimation_input_package(session, technology.id)

        assert package.ready_for_estimation is False
        assert package.consumption_norms[0].quantity_basis == QuantityBasis.UNKNOWN
        assert package.consumption_norms[0].basis_unit == "mystery_unit"
        assert any(issue.code == "unknown_basis_unit" for issue in package.blockers)


@pytest.mark.asyncio(loop_scope="module")
async def test_builder_is_read_only_and_creates_no_m5_records() -> None:
    async with _session() as session:
        technology, _ = await _persist_active_fixture(session)
        before_technologies = await session.scalar(select(func.count()).select_from(Technology))
        before_norms = await session.scalar(select(func.count()).select_from(ConsumptionNorm))

        await build_module5_estimation_input_package(session, technology.id)

        assert await session.scalar(select(func.count()).select_from(Technology)) == before_technologies
        assert await session.scalar(select(func.count()).select_from(ConsumptionNorm)) == before_norms
        assert not session.new
        assert not session.dirty
        assert not session.deleted


@pytest.mark.asyncio(loop_scope="module")
async def test_unknown_work_code_has_no_invented_group_and_returns_blocker() -> None:
    async with _session() as session:
        technology, _ = await _persist_active_fixture(session)
        technology.work_steps[0].work_code = "UNKNOWN_M1_WORK_CODE"
        await session.flush()

        package = await build_module5_estimation_input_package(session, technology.id)

        assert package.work_steps[0].work_group is None
        assert "unknown_m1_work_code" in package.work_steps[0].blockers
        assert any(issue.code == "unknown_m1_work_code" for issue in package.blockers)


@pytest.mark.asyncio(loop_scope="module")
async def test_package_remains_pinned_when_a_new_revision_is_created() -> None:
    async with _session() as session:
        technology, _ = await _persist_active_fixture(session)
        first = await build_module5_estimation_input_package(session, technology.id)
        first_snapshot = first.model_dump(mode="json")

        revision = create_next_revision(
            technology,
            actor_role_code="ADMIN",
            created_by_user_id=ADMIN.id,
        )
        await persist_technology_draft(session, revision)
        transition_technology(revision, "REVIEW", actor_role_code="ADMIN")
        transition_technology(revision, "ACTIVE", actor_role_code="ADMIN")
        await session.flush()
        second = await build_module5_estimation_input_package(session, revision.id)

        assert first.technology.revision == 1
        assert second.technology.revision == 2
        assert first.technology.technology_id != second.technology.technology_id
        assert first.model_dump(mode="json") == first_snapshot


def test_material_requirement_contract_keeps_m1_reference_without_material_clone() -> None:
    material_id = uuid4()
    requirement = EstimationMaterialRequirement(
        requirement_id=uuid4(),
        requirement_code="FIXED_MATERIAL",
        selector=EstimationSelector(
            selector_kind=KnowledgeSelectorKind.CANONICAL_MATERIAL,
            canonical_material_id=material_id,
        ),
        mandatory=True,
    )

    assert requirement.selector.canonical_material_id == material_id
    assert "material" not in EstimationMaterialRequirement.model_fields
    assert "supplier" not in EstimationMaterialRequirement.model_fields
    assert "manufacturer" not in EstimationMaterialRequirement.model_fields


def test_package_has_no_price_cost_total_or_object_quantity_payload() -> None:
    fields = Module5EstimationInputPackage.model_fields
    assert fields["no_object_quantity_result"].default is True
    assert fields["no_price_result"].default is True
    forbidden = {
        "price",
        "cost",
        "total_material_quantity",
        "material_total_price",
        "labor_total_price",
        "grand_total",
        "object_quantity",
        "wall_area",
    }
    all_fields = set()
    for model in EstimationContractModel.__subclasses__():
        all_fields.update(model.model_fields)
    assert forbidden.isdisjoint(all_fields)


def test_contract_boundary_has_no_estimate_persistence_or_commercial_ownership() -> None:
    schema_source = (ROOT / "app" / "schemas" / "module2_estimation_contract.py").read_text(encoding="utf-8")
    service_source = (ROOT / "app" / "services" / "module2_estimation_export.py").read_text(encoding="utf-8")
    combined = schema_source + service_source

    for forbidden in (
        "db.add(",
        "db.delete(",
        "db.flush(",
        "MaterialPrice",
        "ProviderWorkCostOffer",
        "SupplierPrice",
        "EstimateLine",
        "class Estimate(",
        "Object(",
        "Building(",
        "Room(",
        "Procurement(",
    ):
        assert forbidden not in combined


def test_contract_does_not_define_a_module2_work_catalog_clone() -> None:
    schema_source = (ROOT / "app" / "schemas" / "module2_estimation_contract.py").read_text(encoding="utf-8")
    service_source = (ROOT / "app" / "services" / "module2_estimation_export.py").read_text(encoding="utf-8")

    assert "class WorkGroup" not in schema_source + service_source
    assert "class WorkItem" not in schema_source + service_source
    assert "load_work_catalog(db)" in service_source
    assert "work_by_code.get(step.work_code)" in service_source
