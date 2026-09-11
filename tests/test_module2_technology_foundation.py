from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

import app.models  # noqa: F401
from app.models.knowledge_candidate import KnowledgeCandidate
from app.models.knowledge_resource import KnowledgeResource
from app.models.knowledge_resource_link import KnowledgeResourceLink
from app.models.module2_technology import (
    MODULE2_OWNER_CODE,
    Technology,
    TechnologyEvidenceReference,
    TechnologyLayer,
    TechnologyMaterialRequirement,
    TechnologyNode,
    TechnologyWorkStep,
)
from app.schemas.module2_technology import (
    ConsumptionNormContract,
    KnowledgeRuleContract,
    MaterialRequirementSelector,
    TechnologyDraftInput,
    TechnologyDraftUpdate,
    TechnologyEvidenceReferenceInput,
    TechnologyLayerInput,
    TechnologyLifecycle,
    TechnologyMaterialRequirementInput,
    TechnologyNodeInput,
    TechnologyWorkStepInput,
)
from app.services.module1_export_packages import (
    CleanMaterialPackage,
    Module2TechnologyInputPackage,
    TechnicalProfilePackage,
)
from app.services.module1_work_catalog import list_work_items
from app.services.module2_technology_foundation import (
    Module2TechnologyError,
    Module2TechnologyPermissionError,
    accept_module1_input,
    build_draft_technology,
    create_next_revision,
    material_requirement_from_module1,
    persist_technology_draft,
    transition_technology,
    update_draft_technology,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "database"
    / "migrations"
    / "20260911_module02_technology_foundation.sql"
)
SERVICE_PATH = PROJECT_ROOT / "app" / "services" / "module2_technology_foundation.py"


def _package(
    *,
    material_id: UUID | None = None,
    missing_fields: tuple[str, ...] = tuple(),
    blockers: tuple[str, ...] = tuple(),
) -> Module2TechnologyInputPackage:
    resolved_id = material_id or uuid4()
    clean = CleanMaterialPackage(
        material_id=str(resolved_id),
        canonical_name="Canonical material owned by M1",
        group={"code": "wall_block"},
        category={"id": "m1-category"},
        subcategory=None,
        material_type=None,
        base_unit="m3",
        normalized_characteristics={"strength_class": "B2.5"},
        quality_score=95,
        readiness_status="ready_for_module2",
        warnings=tuple(),
        provenance={"source": "M1"},
        source_refs=({"sourceId": "m1-source"},),
    )
    technical = TechnicalProfilePackage(
        material_id=str(resolved_id),
        material_group="wall_block",
        technical_characteristics={"strength_class": "B2.5"},
        module2_required_fields=("strength_class",),
        missing_module2_fields=missing_fields,
        packaging_profile={},
        conversion_capabilities=tuple(),
        calculation_readiness={"ready": not missing_fields},
        warnings=tuple(),
    )
    return Module2TechnologyInputPackage(
        clean_material=clean,
        technical_profile=technical,
        material_role_hints=tuple(),
        compatibility_hints=tuple(),
        alternative_hints=tuple(),
        unit_conversion_hints=tuple(),
        missing_fields=missing_fields,
        blockers=blockers,
    )


def _draft_input(
    *,
    package: Module2TechnologyInputPackage | None = None,
    document_id: UUID | None = None,
) -> TechnologyDraftInput:
    material_package = package or _package()
    material_requirement = material_requirement_from_module1(
        material_package,
        code="WALL_BLOCK",
        material_role_code="LOAD_BEARING_LAYER",
    )
    work_code = list_work_items()[0].work_code
    return TechnologyDraftInput(
        technology_code="AERATED_WALL_SYSTEM",
        name="Aerated concrete wall system",
        description="M2 engineering interpretation over M1 references.",
        system_code="EXTERNAL_WALL",
        requirements=[material_requirement],
        layers=[
            TechnologyLayerInput(
                position=2,
                functional_role="FINISH",
                thickness_expression="finish_thickness_mm",
            ),
            TechnologyLayerInput(
                position=1,
                functional_role="LOAD_BEARING",
                requirement_code="WALL_BLOCK",
                thickness_expression="wall_thickness_mm",
            ),
        ],
        nodes=[
            TechnologyNodeInput(
                code="OPENING_LINTEL",
                node_type="OPENING",
                name="Opening lintel",
            )
        ],
        work_steps=[
            TechnologyWorkStepInput(position=1, work_code=work_code),
        ],
        evidence_references=[
            TechnologyEvidenceReferenceInput(document_id=document_id or uuid4())
        ],
    )


def _draft(
    *,
    package: Module2TechnologyInputPackage | None = None,
) -> Technology:
    material_package = package or _package()
    return build_draft_technology(
        _draft_input(package=material_package),
        actor_role_code="ENGINEER_DESIGNER",
        input_package=material_package,
    )


def test_existing_knowledge_models_remain_evidence_foundation_not_technology() -> None:
    assert KnowledgeResource.__tablename__ == "knowledge_resources"
    assert KnowledgeResourceLink.__tablename__ == "knowledge_resource_links"
    assert KnowledgeCandidate.__tablename__ == "knowledge_candidates"
    assert Technology.__tablename__ == "module2_technologies"
    assert Technology.__tablename__ not in {
        KnowledgeResource.__tablename__,
        KnowledgeResourceLink.__tablename__,
        KnowledgeCandidate.__tablename__,
    }


def test_m1_package_is_accepted_as_reference_without_copying_material_payload() -> None:
    material_id = uuid4()
    acceptance = accept_module1_input(_package(material_id=material_id))

    assert acceptance.accepted_for_active_technology is True
    assert acceptance.canonical_material_id == material_id
    assert acceptance.ownership == "M1_REFERENCE_ONLY"
    acceptance_fields = type(acceptance).model_fields
    assert "canonical_name" not in acceptance_fields
    assert "normalized_characteristics" not in acceptance_fields
    assert "price" not in acceptance_fields


def test_technology_is_m2_entity_with_ordered_layers_and_node_foundation() -> None:
    technology = _draft()

    assert technology.owner_module_code == MODULE2_OWNER_CODE
    assert technology.status == TechnologyLifecycle.DRAFT.value
    assert technology.revision == 1
    assert [layer.position for layer in technology.layers] == [1, 2]
    assert technology.layers[0].material_requirement.code == "WALL_BLOCK"
    assert technology.nodes[0].code == "OPENING_LINTEL"


def test_duplicate_layer_order_is_rejected_deterministically() -> None:
    package = _package()
    with pytest.raises(ValidationError, match="duplicate layer position"):
        TechnologyDraftInput(
            technology_code="DUPLICATE_LAYER_TEST",
            name="Duplicate layer test",
            requirements=[
                material_requirement_from_module1(
                    package,
                    code="MATERIAL",
                    material_role_code="PRIMARY",
                )
            ],
            layers=[
                TechnologyLayerInput(position=1, functional_role="PRIMARY"),
                TechnologyLayerInput(position=1, functional_role="FINISH"),
            ],
        )


def test_material_requirement_supports_reference_or_requirement_semantics() -> None:
    canonical = material_requirement_from_module1(
        _package(),
        code="CANONICAL",
        material_role_code="PRIMARY",
    )
    material_class = TechnologyMaterialRequirementInput(
        code="CLASS",
        selector_kind=MaterialRequirementSelector.MATERIAL_CLASS,
        material_category_id=uuid4(),
    )
    constraints = TechnologyMaterialRequirementInput(
        code="CONSTRAINTS",
        selector_kind=MaterialRequirementSelector.TECHNICAL_CONSTRAINTS,
        technical_constraints={"frost_resistance": {"minimum": "F35"}},
    )
    role = TechnologyMaterialRequirementInput(
        code="ROLE",
        selector_kind=MaterialRequirementSelector.ROLE,
        material_role_code="ADHESIVE",
    )

    assert canonical.canonical_material_id is not None
    assert material_class.material_category_id is not None
    assert constraints.technical_constraints
    assert role.material_role_code == "ADHESIVE"


def test_material_requirement_rejects_selector_without_matching_reference() -> None:
    with pytest.raises(ValidationError, match="requires its matching reference semantics"):
        TechnologyMaterialRequirementInput(
            code="INVALID",
            selector_kind=MaterialRequirementSelector.CANONICAL_MATERIAL,
        )


def test_work_step_reuses_m1_catalog_without_creating_catalog_items() -> None:
    before = list_work_items()
    technology = _draft()
    after = list_work_items()

    assert len(after) == len(before)
    assert technology.work_steps[0].work_code == before[0].work_code
    assert not hasattr(technology.work_steps[0], "work_name")
    assert not hasattr(technology.work_steps[0], "pricing_unit")


def test_unknown_work_catalog_code_is_rejected() -> None:
    package = _package()
    command = _draft_input(package=package).model_copy(
        update={
            "work_steps": [
                TechnologyWorkStepInput(position=1, work_code="NOT_A_REAL_WORK_CODE")
            ]
        }
    )
    with pytest.raises(Module2TechnologyError, match="unknown Module1 Work Catalog code"):
        build_draft_technology(
            command,
            actor_role_code="ENGINEER_DESIGNER",
            input_package=package,
        )


def test_evidence_keeps_only_m1_reference_and_m2_interpretation() -> None:
    document_id = uuid4()
    technology = build_draft_technology(
        _draft_input(document_id=document_id),
        actor_role_code="ENGINEER_DESIGNER",
    )
    evidence = technology.evidence_references[0]

    assert evidence.document_id == document_id
    assert evidence.interpretation is None
    assert not hasattr(evidence, "resource_url")
    assert not hasattr(evidence, "extracted_text")
    assert not hasattr(evidence, "certificate_contents")


def test_lifecycle_uses_existing_rbac_and_active_cannot_be_edited_in_place() -> None:
    technology = _draft()

    transition_technology(
        technology,
        TechnologyLifecycle.REVIEW,
        actor_role_code="ENGINEER_DESIGNER",
    )
    transition_technology(
        technology,
        TechnologyLifecycle.ACTIVE,
        actor_role_code="MODERATOR",
    )

    assert technology.status == TechnologyLifecycle.ACTIVE.value
    with pytest.raises(Module2TechnologyError, match="only a DRAFT"):
        update_draft_technology(
            technology,
            TechnologyDraftUpdate(name="Silent overwrite"),
            actor_role_code="ENGINEER_DESIGNER",
        )


def test_incomplete_m1_package_never_activates_technology() -> None:
    package = _package(
        missing_fields=("frost_resistance",),
        blockers=("missing_technical_fields",),
    )
    technology = _draft(package=package)
    transition_technology(
        technology,
        TechnologyLifecycle.REVIEW,
        actor_role_code="ENGINEER_DESIGNER",
    )

    with pytest.raises(Module2TechnologyError, match="incomplete M1 input"):
        transition_technology(
            technology,
            TechnologyLifecycle.ACTIVE,
            actor_role_code="MODERATOR",
        )
    assert technology.input_missing_fields == ["frost_resistance"]
    assert technology.input_blockers == ["missing_technical_fields"]


def test_new_revision_preserves_active_history_and_external_references() -> None:
    technology = _draft()
    transition_technology(
        technology,
        TechnologyLifecycle.REVIEW,
        actor_role_code="ENGINEER_DESIGNER",
    )
    transition_technology(
        technology,
        TechnologyLifecycle.ACTIVE,
        actor_role_code="MODERATOR",
    )

    revised = create_next_revision(
        technology,
        actor_role_code="ENGINEER_DESIGNER",
    )

    assert technology.status == TechnologyLifecycle.ACTIVE.value
    assert revised.status == TechnologyLifecycle.DRAFT.value
    assert revised.revision == technology.revision + 1
    assert revised.supersedes is technology
    assert revised.requirements[0].canonical_material_id == (
        technology.requirements[0].canonical_material_id
    )
    assert revised.layers[0].material_requirement.code == "WALL_BLOCK"


def test_rbac_denies_customer_edit_and_engineer_activation() -> None:
    package = _package()
    with pytest.raises(Module2TechnologyPermissionError):
        build_draft_technology(
            _draft_input(package=package),
            actor_role_code="CUSTOMER",
            input_package=package,
        )

    technology = _draft()
    transition_technology(
        technology,
        TechnologyLifecycle.REVIEW,
        actor_role_code="ENGINEER_DESIGNER",
    )
    with pytest.raises(Module2TechnologyPermissionError):
        transition_technology(
            technology,
            TechnologyLifecycle.ACTIVE,
            actor_role_code="ENGINEER_DESIGNER",
        )


@pytest.mark.asyncio
async def test_persistence_entry_accepts_only_m2_draft() -> None:
    class RecordingSession:
        def __init__(self) -> None:
            self.added = []
            self.flushed = False

        def add(self, value) -> None:
            self.added.append(value)

        async def flush(self) -> None:
            self.flushed = True

    session = RecordingSession()
    technology = _draft()

    persisted = await persist_technology_draft(session, technology)

    assert persisted is technology
    assert session.added == [technology]
    assert session.flushed is True
    assert all(item.__tablename__.startswith("module2_") for item in session.added)


def test_m2_models_do_not_own_m1_material_price_work_cost_or_documents() -> None:
    model_types = (
        Technology,
        TechnologyMaterialRequirement,
        TechnologyLayer,
        TechnologyNode,
        TechnologyWorkStep,
        TechnologyEvidenceReference,
    )
    assert all(model.__tablename__.startswith("module2_") for model in model_types)

    service_source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "ProviderWorkCostOffer",
        "SupplierPrice",
        "PriceHistory",
        "MaterialDocument(",
        "KnowledgeResource(",
        "estimate_total",
        "procurement",
        "openai",
    ):
        assert forbidden not in service_source


def test_consumption_norm_and_knowledge_rule_are_future_contracts_not_engines() -> None:
    norm = ConsumptionNormContract(
        technology_code="AERATED_WALL_SYSTEM",
        technology_revision=1,
        requirement_code="ADHESIVE",
        basis_quantity="1",
        basis_unit="m2",
        consumption_quantity="5",
        consumption_unit="kg",
        conditions={"temperature_min_c": 5},
    )
    rule = KnowledgeRuleContract(
        technology_code="AERATED_WALL_SYSTEM",
        technology_revision=1,
        condition_expression={"temperature_c": {"lt": 5}},
        effect_type="PROHIBITION",
        effect_payload={"code": "LOW_TEMPERATURE"},
    )

    assert norm.basis_unit == "m2"
    assert rule.effect_type == "PROHIBITION"
    assert not hasattr(norm, "calculate")
    assert not hasattr(rule, "execute")


def test_migration_is_additive_reversible_and_limited_to_m2_tables() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    executable = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    expected_tables = {
        "module2_technologies",
        "module2_technology_material_requirements",
        "module2_technology_layers",
        "module2_technology_nodes",
        "module2_technology_work_steps",
        "module2_technology_evidence_references",
    }

    for table_name in expected_tables:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in executable
        assert f"DROP TABLE {table_name}" in sql
    assert "ALTER TABLE" not in executable.upper()
    assert "INSERT INTO" not in executable.upper()
    assert "UPDATE " not in executable.upper()
    assert "DELETE FROM" not in executable.upper()
    assert "REFERENCES materials(id)" in executable
    assert "REFERENCES material_documents(id)" in executable
    assert "REFERENCES knowledge_resources(id)" in executable
