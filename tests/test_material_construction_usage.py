from app.models.construction_group import ConstructionGroup
from app.models.material import Material
from app.models.material_category import MaterialCategory
from app.models.material_type import MaterialType
from app.schemas.material_hub_contracts import (
    ConstructionUsageModerationAction,
    ConstructionUsageStatus,
    MaterialConstructionUsageModerationDecision,
    Module2TechnologyKnowledgeRef,
    RequiredCharacteristicRef,
)
from app.services.material_construction_usage import (
    MODULE_02_KNOWLEDGE_BASE,
    apply_construction_usage_moderation_decision,
    build_module2_construction_usage_candidate,
    get_material_construction_usage,
    get_starter_construction_applicability_catalog,
)


def test_material_construction_usage_is_not_material_category():
    material = Material(canonical_name="Доска 50x200")
    material.category = MaterialCategory(name="Пиломатериалы", slug="timber")
    material.material_type = MaterialType(name="Доска", slug="board")
    material.material_type.construction_group = ConstructionGroup(name="Кровля", slug="roof")

    usages = get_material_construction_usage(material)

    assert len(usages) == 1
    assert usages[0].construction_group == "Кровля"
    assert usages[0].construction_group != material.category.name
    assert usages[0].status == ConstructionUsageStatus.NEEDS_REVIEW
    assert usages[0].verified_by_moderator is False


def test_module2_knowledge_becomes_candidate_not_verified_usage():
    candidate = build_module2_construction_usage_candidate(
        Module2TechnologyKnowledgeRef(
            technology="Каркасная технология",
            construction="Стропильная система",
            material_name="Доска 50x200",
            material_role="стропила",
            construction_group="Кровля",
            construction_subgroup="стропила",
            usage_condition="Подходит по сечению для стропильной системы.",
            required_characteristics=[
                RequiredCharacteristicRef(
                    characteristic_name="сечение",
                    expected_value="50x200",
                    expected_unit="мм",
                )
            ],
            confidence="0.72",
            source_reference_id="module2-node-1",
        )
    )

    assert candidate.status == ConstructionUsageStatus.NEEDS_REVIEW
    assert candidate.proposed_usage.source_module == MODULE_02_KNOWLEDGE_BASE
    assert candidate.proposed_usage.verified_by_moderator is False
    assert candidate.proposed_usage.required_characteristics[0].characteristic_name == "сечение"


def test_moderator_approval_marks_construction_usage_verified():
    candidate = build_module2_construction_usage_candidate(
        {
            "construction_group": "Фундамент",
            "construction_subgroup": "опалубка",
            "material_name": "Доска",
            "material_role": "вспомогательный материал",
            "usage_condition": "Может применяться для временной опалубки.",
        }
    )

    moderated = apply_construction_usage_moderation_decision(
        candidate,
        MaterialConstructionUsageModerationDecision(
            action=ConstructionUsageModerationAction.APPROVE,
            moderator_note="Проверено по технологической карте.",
        ),
    )

    assert moderated.status == ConstructionUsageStatus.ACTIVE
    assert moderated.proposed_usage.status == ConstructionUsageStatus.ACTIVE
    assert moderated.proposed_usage.verified_by_moderator is True
    assert moderated.proposed_usage.moderator_note == "Проверено по технологической карте."


def test_starter_construction_catalog_keeps_groups_open_ended():
    catalog = get_starter_construction_applicability_catalog()

    assert "Фундамент" in catalog
    assert "Кровля" in catalog
    assert "опалубка" in catalog["Фундамент"]
    assert "стропила" in catalog["Кровля"]
