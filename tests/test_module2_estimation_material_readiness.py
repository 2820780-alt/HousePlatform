from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.enums import MaterialStatus
from decimal import Decimal

from app.models.module2_knowledge import CompatibilityRule, ConsumptionNorm, KnowledgeRule
from app.models.module2_technology import Technology, TechnologyEvidenceReference, TechnologyLayer, TechnologyMaterialRequirement
import app.services.module2_estimation_export as export
from app.services.module2_foundation_quantity_rules import describe_quantity_rule


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [
    (MaterialStatus.DRAFT, "canonical_material_not_verified"),
    (MaterialStatus.ARCHIVED, "canonical_material_not_verified"),
    (MaterialStatus.VERIFIED, None),
    (None, "canonical_material_missing"),
])
async def test_m5_input_reports_unverified_or_missing_canonical_material(monkeypatch, status, expected):
    material_id = uuid4()
    requirement = TechnologyMaterialRequirement(
        id=uuid4(), code="CONCRETE", selector_kind="CANONICAL_MATERIAL",
        canonical_material_id=material_id, technical_constraints={},
    )
    layer = TechnologyLayer(id=uuid4(), position=1, functional_role="CONCRETE",
                            material_requirement_id=requirement.id, is_mandatory=True, restrictions={})
    technology = Technology(id=uuid4(), technology_code="TEST_FOUNDATION", revision=1, status="ACTIVE",
                            name="Test", source_kind="HUMAN_CURATED", input_missing_fields=[], input_blockers=[])
    technology.requirements.append(requirement)
    technology.layers.append(layer)
    monkeypatch.setattr(export, "read_technology", AsyncMock(return_value=technology))
    rows = [] if status is None else [(material_id, status)]
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)))

    package = await export.build_module5_estimation_input_package(db, technology.id)

    local = package.material_requirements[0].blockers
    if expected:
        assert expected in local
        assert not package.ready_for_estimation
    else:
        assert "canonical_material_not_verified" not in local
        assert "canonical_material_missing" not in local
    assert db.execute.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("alteration,expected", [
    (None, None),
    ("formula", "invalid_foundation_quantity_rule"),
    ("role", "quantity_rule_role_unresolved"),
    ("scope", "quantity_rule_role_unresolved"),
    ("draft", "canonical_material_not_verified"),
])
async def test_typed_quantity_rule_flows_through_existing_m5_contract(monkeypatch, alteration, expected):
    material_id = uuid4()
    requirement = TechnologyMaterialRequirement(
        id=uuid4(), code="TOP_REBAR", selector_kind="CANONICAL_MATERIAL",
        material_role_code="TOP_REBAR", canonical_material_id=material_id, technical_constraints={},
    )
    layer = TechnologyLayer(id=uuid4(), position=1, functional_role="REINFORCEMENT",
                            material_requirement_id=requirement.id, is_mandatory=True, restrictions={})
    technology = Technology(id=uuid4(), technology_code="TEST_FOUNDATION", revision=1, status="ACTIVE",
                            name="Test", source_kind="HUMAN_CURATED", input_missing_fields=[], input_blockers=[])
    technology.requirements.append(requirement)
    technology.layers.append(layer)
    payload = describe_quantity_rule("BAR_MASS", role_code="TOP_REBAR", material_id=str(material_id))
    if alteration == "formula":
        payload["expression"] = "untrusted arbitrary expression"
    elif alteration == "role":
        payload = describe_quantity_rule("BAR_MASS", role_code="OTHER_ROLE", material_id=str(material_id))
    rule = KnowledgeRule(id=uuid4(), rule_code="REBAR_QUANTITY", revision=1, status="ACTIVE",
                         scope_kind="TECHNOLOGY" if alteration == "scope" else "MATERIAL_REQUIREMENT",
                         scope_reference=None if alteration == "scope" else str(requirement.id),
                         conditions=[], outcome_type="INFORMATION",
                         outcome_payload=payload, blockers=[])
    technology.knowledge_rules.append(rule)
    evidence = TechnologyEvidenceReference(id=uuid4(), document_id=uuid4(), target_kind="KNOWLEDGE_RULE",
                                           target_reference=str(rule.id))
    technology.evidence_references.append(evidence)
    monkeypatch.setattr(export, "read_technology", AsyncMock(return_value=technology))
    monkeypatch.setattr(export, "verify_evidence_references", AsyncMock(return_value=frozenset({evidence.id})))
    status = MaterialStatus.DRAFT if alteration == "draft" else MaterialStatus.VERIFIED
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(material_id, status)])))

    package = await export.build_module5_estimation_input_package(db, technology.id)

    assert len(package.knowledge_constraints) == 1
    constraint = package.knowledge_constraints[0]
    assert constraint.outcome_payload == payload
    assert package.no_object_quantity_result is True
    if expected:
        assert expected in constraint.blockers
        assert not package.ready_for_estimation
    else:
        assert not constraint.blockers


@pytest.mark.asyncio
async def test_direct_norm_and_compatibility_selectors_check_m1_status(monkeypatch):
    material_id = uuid4()
    requirement = TechnologyMaterialRequirement(id=uuid4(), code="REBAR", selector_kind="ROLE",
                                                material_role_code="REBAR", technical_constraints={})
    layer = TechnologyLayer(id=uuid4(), position=1, functional_role="REINFORCEMENT",
                            material_requirement_id=requirement.id, is_mandatory=True, restrictions={})
    technology = Technology(id=uuid4(), technology_code="TEST_FOUNDATION", revision=1, status="ACTIVE",
                            name="Test", source_kind="HUMAN_CURATED", input_missing_fields=[], input_blockers=[])
    technology.requirements.append(requirement)
    technology.layers.append(layer)
    selector = {"canonical_material_id": str(material_id)}
    norm = ConsumptionNorm(id=uuid4(), norm_code="TEST_NORM", revision=1, status="ACTIVE",
                           resource_kind="CANONICAL_MATERIAL", resource_selector=selector,
                           basis_quantity=Decimal("1"), basis_unit="m2", consumption_quantity=Decimal("1"),
                           consumption_unit="kg", conditions=[], blockers=[])
    rule = CompatibilityRule(id=uuid4(), rule_code="TEST_COMPATIBILITY", revision=1, status="ACTIVE",
                             subject_kind="CANONICAL_MATERIAL", subject_selector=selector,
                             object_kind="ROLE", object_selector={"material_role_code": "REBAR"},
                             relation="INCOMPATIBLE", conditions=[], blockers=[], is_symmetric=True)
    technology.consumption_norms.append(norm)
    technology.compatibility_rules.append(rule)
    refs = [TechnologyEvidenceReference(id=uuid4(), document_id=uuid4(), target_kind=kind,
                                       target_reference=str(item.id))
            for kind, item in (("CONSUMPTION_NORM", norm), ("COMPATIBILITY_RULE", rule))]
    technology.evidence_references.extend(refs)
    monkeypatch.setattr(export, "read_technology", AsyncMock(return_value=technology))
    monkeypatch.setattr(export, "verify_evidence_references", AsyncMock(return_value=frozenset(ref.id for ref in refs)))
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(material_id, MaterialStatus.DRAFT)])))

    package = await export.build_module5_estimation_input_package(db, technology.id)

    assert "canonical_material_not_verified" in package.consumption_norms[0].blockers
    assert "canonical_material_not_verified" in package.compatibility_constraints[0].blockers
    assert not package.ready_for_estimation
