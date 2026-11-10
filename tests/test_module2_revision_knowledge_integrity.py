from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.module2_knowledge import CompatibilityRule, ConsumptionNorm, KnowledgeRule
from app.models.module2_technology import (
    Technology, TechnologyEvidenceReference, TechnologyLayer, TechnologyMaterialRequirement,
)
from app.services.module2_technology_foundation import Module2TechnologyError, create_next_revision


def _technology():
    tech = Technology(id=uuid4(), technology_code="EXAMPLE", revision=1, name="Example",
                      status="ACTIVE", system_code="FOUNDATION", source_kind="HUMAN_CURATED",
                      input_missing_fields=[], input_blockers=[])
    requirement = TechnologyMaterialRequirement(id=uuid4(), code="STEEL", selector_kind="ROLE",
                                                material_role_code="REINFORCEMENT", technical_constraints={})
    layer = TechnologyLayer(id=uuid4(), position=1, functional_role="REINFORCEMENT",
                            material_requirement=requirement, is_mandatory=True, restrictions={})
    tech.requirements.append(requirement)
    tech.layers.append(layer)
    selector = {"selector_kind": "MATERIAL_REQUIREMENT", "material_requirement_id": str(requirement.id)}
    norm = ConsumptionNorm(id=uuid4(), norm_code="TEST_NORM", revision=1, scope_layer_id=layer.id,
                           scope_requirement_id=requirement.id, resource_kind="MATERIAL_REQUIREMENT",
                           resource_selector=selector, basis_quantity=Decimal("1"), basis_unit="m",
                           consumption_quantity=Decimal("1"), consumption_unit="m", conditions=[],
                           status="ACTIVE", owner_module_code="MODULE_02", source_kind="HUMAN_CURATED", blockers=[])
    rule = CompatibilityRule(id=uuid4(), rule_code="TEST_RULE", revision=1, subject_kind="MATERIAL_REQUIREMENT",
                             subject_selector=selector, object_kind="ROLE", object_selector={"material_role_code": "X"},
                             relation="UNKNOWN", conditions=[], is_symmetric=True, status="ACTIVE",
                             owner_module_code="MODULE_02", source_kind="HUMAN_CURATED", blockers=[])
    knowledge = KnowledgeRule(id=uuid4(), rule_code="TEST_KNOWLEDGE", revision=1,
                              scope_kind="CONSUMPTION_NORM", scope_reference=str(norm.id), conditions=[],
                              outcome_type="INFORMATION", outcome_payload={}, status="ACTIVE",
                              owner_module_code="MODULE_02", source_kind="HUMAN_CURATED", blockers=[])
    tech.consumption_norms.append(norm)
    tech.compatibility_rules.append(rule)
    tech.knowledge_rules.append(knowledge)
    for kind, item in (("LAYER", layer), ("CONSUMPTION_NORM", norm),
                       ("COMPATIBILITY_RULE", rule), ("KNOWLEDGE_RULE", knowledge)):
        tech.evidence_references.append(TechnologyEvidenceReference(
            id=uuid4(), knowledge_resource_id=uuid4(), target_kind=kind, target_reference=str(item.id)))
    return tech


def test_revision_preserves_and_retargets_engineering_records_and_evidence():
    source = _technology()
    revised = create_next_revision(source, actor_role_code="ENGINEER_DESIGNER")
    assert source.status == "ACTIVE" and revised.status == "DRAFT"
    requirement = revised.requirements[0]
    layer = revised.layers[0]
    norm = revised.consumption_norms[0]
    rule = revised.compatibility_rules[0]
    knowledge = revised.knowledge_rules[0]
    assert norm.scope_layer_id == layer.id
    assert norm.scope_requirement_id == requirement.id
    assert norm.resource_selector["material_requirement_id"] == str(requirement.id)
    assert rule.subject_selector["material_requirement_id"] == str(requirement.id)
    assert knowledge.scope_reference == str(norm.id)
    assert {ref.target_kind: ref.target_reference for ref in revised.evidence_references} == {
        "LAYER": str(layer.id), "CONSUMPTION_NORM": str(norm.id),
        "COMPATIBILITY_RULE": str(rule.id), "KNOWLEDGE_RULE": str(knowledge.id),
    }
    assert norm.supersedes_id == source.consumption_norms[0].id
    assert source.knowledge_rules[0].scope_reference == str(source.consumption_norms[0].id)


def test_revision_rejects_dangling_evidence():
    source = _technology()
    source.evidence_references[0].target_reference = str(uuid4())
    with pytest.raises(Module2TechnologyError, match="cannot copy LAYER reference"):
        create_next_revision(source, actor_role_code="ENGINEER_DESIGNER")


def test_approved_rule_in_draft_still_requires_permission_and_verified_evidence():
    from app.services.module2_knowledge_foundation import (
        Module2KnowledgeError, transition_consumption_norm,
    )
    from app.services.module2_technology_foundation import Module2TechnologyPermissionError

    tech = _technology()
    tech.status = "DRAFT"
    norm = tech.consumption_norms[0]
    norm.technology_id = tech.id
    norm.status = "REVIEW"
    evidence = next(item for item in tech.evidence_references if item.target_kind == "CONSUMPTION_NORM")
    kwargs = {"technology": tech, "evidence_references": tech.evidence_references,
              "verified_evidence_reference_ids": [evidence.id], "allow_draft_technology": True}
    with pytest.raises(Module2TechnologyPermissionError):
        transition_consumption_norm(norm, "ACTIVE", actor_role_code="CUSTOMER", **kwargs)
    with pytest.raises(Module2KnowledgeError, match="broken_or_unverified_evidence"):
        transition_consumption_norm(norm, "ACTIVE", actor_role_code="MODERATOR", **{
            **kwargs, "verified_evidence_reference_ids": []})
    with pytest.raises(Module2KnowledgeError, match="technology_not_active"):
        transition_consumption_norm(norm, "ACTIVE", actor_role_code="MODERATOR", **{
            **kwargs, "allow_draft_technology": False})
    tech.status = "REVIEW"
    with pytest.raises(Module2KnowledgeError, match="technology_not_active"):
        transition_consumption_norm(norm, "ACTIVE", actor_role_code="MODERATOR", **kwargs)
    tech.status = "DRAFT"
    transition_consumption_norm(norm, "ACTIVE", actor_role_code="MODERATOR", **kwargs)
    assert norm.status == "ACTIVE" and tech.status == "DRAFT"


def test_publication_rechecks_approved_records_and_their_evidence():
    from app.services.module2_knowledge_foundation import validate_technology_knowledge_publication

    tech = _technology()
    tech.status = "REVIEW"
    for entity in (*tech.consumption_norms, *tech.compatibility_rules, *tech.knowledge_rules):
        entity.technology_id = tech.id
    evidence_ids = [item.id for item in tech.evidence_references]
    assert not validate_technology_knowledge_publication(tech, verified_evidence_reference_ids=evidence_ids)
    evidence = next(item for item in tech.evidence_references if item.target_kind == "CONSUMPTION_NORM")
    without_norm_source = [value for value in evidence_ids if value != evidence.id]
    blockers = validate_technology_knowledge_publication(
        tech, verified_evidence_reference_ids=without_norm_source)
    assert any("broken_or_unverified_evidence" in item for item in blockers)
    assert tech.status == "REVIEW"


@pytest.mark.asyncio
async def test_workbench_does_not_publish_without_evidence():
    from unittest.mock import AsyncMock
    from app.api.v1.module2_workbench import _perform_action

    tech = _technology()
    tech.status = "REVIEW"
    for entity in (*tech.consumption_norms, *tech.compatibility_rules, *tech.knowledge_rules):
        entity.technology_id = tech.id
    tech.evidence_references.clear()
    with pytest.raises(ValueError, match="источники"):
        await _perform_action("transition", {"target": "ACTIVE"}, technology=tech,
                              db=AsyncMock(), role_code="MODERATOR", user_id=uuid4())
    assert tech.status == "REVIEW"


@pytest.mark.asyncio
async def test_existing_foundation_revisions_on_restored_database():
    from sqlalchemy import select
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.config import settings
    from app.services.module2_technology_foundation import read_technology

    if make_url(settings.DATABASE_URL).database != "houseplatform_fnd_m1_m2_20261110":
        pytest.skip("requires the dedicated restored foundation database")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine)() as db:
        ids = (await db.scalars(select(Technology.id).where(Technology.status == "ACTIVE"))).all()
        assert len(ids) == 15
        revisions = []
        for technology_id in ids:
            source = await read_technology(db, technology_id)
            revised = create_next_revision(source, actor_role_code="ENGINEER_DESIGNER")
            assert len(revised.knowledge_rules) == len(source.knowledge_rules)
            assert len(revised.consumption_norms) == len(source.consumption_norms)
            assert len(revised.compatibility_rules) == len(source.compatibility_rules)
            assert len(revised.evidence_references) == len(source.evidence_references)
            revisions.append(revised)
        db.add_all(revisions)
        await db.flush()
        await db.rollback()
    await engine.dispose()
