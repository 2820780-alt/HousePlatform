from uuid import uuid4

import pytest

from app.services.module1_foundation_target_package import targets
from app.services.module2_foundation_preliminary_profiles import (
    PROFILES, audit_profile_reconciliation, profile_material_default_proposals, profile_numeric_default_proposals,
    profile_quantity_rule_proposals, profile_requirement_proposals, prepare_single_role_linkage_draft,
    populate_blocked_foundation_draft,
)
from app.services.module2_foundation_quantity_rules import RULES


def test_single_role_linkage_preserves_active_technology_and_blocks_publication():
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.models.material_attribute import MaterialAttribute
    from app.models.module2_technology import Technology, TechnologyLayer, TechnologyMaterialRequirement
    from app.services.module1_foundation_target_package import PACKAGE
    from app.services.module2_technology_foundation import Module2TechnologyError, transition_technology

    category_id = uuid4()
    technology = Technology(id=uuid4(), technology_code="FND_STRIP_MONOLITHIC_RC", revision=1,
                            name="Лента", status="ACTIVE", input_missing_fields=[], input_blockers=[])
    concrete = TechnologyMaterialRequirement(id=uuid4(), code="CONCRETE", selector_kind="MATERIAL_CLASS",
                                              material_category_id=category_id, technical_constraints={})
    rebar = TechnologyMaterialRequirement(id=uuid4(), code="REBAR", selector_kind="MATERIAL_CLASS",
                                           material_category_id=uuid4(), technical_constraints={})
    technology.requirements = [concrete, rebar]
    technology.layers = [TechnologyLayer(id=uuid4(), position=1, functional_role="CONCRETE",
                                         material_requirement=concrete, restrictions={})]
    candidate = Material(id=uuid4(), canonical_name="Бетон", status=MaterialStatus.DRAFT, category_id=category_id)
    candidate.attributes = [MaterialAttribute(attribute_name="registry_origin", attribute_value=PACKAGE),
                            MaterialAttribute(attribute_name="registry_code", attribute_value="BT-02")]
    draft, linked, unresolved = prepare_single_role_linkage_draft(
        technology, {"BT-02": candidate}, actor_role_code="ENGINEER_DESIGNER")
    assert linked == ("CONCRETE",) and unresolved == ("REBAR",)
    assert concrete.selector_kind == "MATERIAL_CLASS" and concrete.canonical_material_id is None
    assert draft.requirements[0].canonical_material_id == candidate.id
    assert draft.requirements[0].material_category_id == category_id
    assert draft.requirements[1].selector_kind == "MATERIAL_CLASS"
    assert draft.layers[0].material_requirement is draft.requirements[0]
    assert "foundation_reconciliation_required" in draft.input_blockers
    draft.status = "REVIEW"
    with pytest.raises(Module2TechnologyError, match="incomplete M1 input"):
        transition_technology(draft, "ACTIVE", actor_role_code="MODERATOR")


def test_single_role_linkage_rejects_unowned_or_wrong_category_candidates():
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.models.material_attribute import MaterialAttribute
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement
    from app.services.module1_foundation_target_package import PACKAGE

    technology = Technology(id=uuid4(), technology_code="FND_PILE_SCREW", revision=1,
                            name="Свая", status="ACTIVE", input_missing_fields=[], input_blockers=[])
    technology.requirements = [TechnologyMaterialRequirement(
        id=uuid4(), code="PILE", selector_kind="MATERIAL_CLASS", material_category_id=uuid4(), technical_constraints={})]
    candidate = Material(id=uuid4(), canonical_name="Свая", status=MaterialStatus.DRAFT, category_id=uuid4())
    candidate.attributes = [MaterialAttribute(attribute_name="registry_origin", attribute_value=PACKAGE),
                            MaterialAttribute(attribute_name="registry_code", attribute_value="PILE-S-02")]
    draft, linked, unresolved = prepare_single_role_linkage_draft(
        technology, {"PILE-S-02": candidate}, actor_role_code="ENGINEER_DESIGNER")
    assert linked == () and unresolved == ("PILE",)
    assert draft.requirements[0].canonical_material_id is None


def test_single_role_alias_reuses_legacy_requirement_without_duplicate():
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.models.material_attribute import MaterialAttribute
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement
    from app.services.module1_foundation_target_package import PACKAGE

    category = uuid4()
    technology = Technology(id=uuid4(), technology_code="FND_PILE_SCREW", revision=1,
                            name="Свая", status="ACTIVE", input_missing_fields=[], input_blockers=[])
    technology.requirements = [TechnologyMaterialRequirement(id=uuid4(), code="PILE", selector_kind="MATERIAL_CLASS",
        material_role_code="STEEL_PILE", material_category_id=category, technical_constraints={})]
    candidate = Material(id=uuid4(), canonical_name="Свая", status=MaterialStatus.DRAFT, category_id=category)
    candidate.attributes = [MaterialAttribute(attribute_name="registry_origin", attribute_value=PACKAGE),
                            MaterialAttribute(attribute_name="registry_code", attribute_value="PILE-S-02")]
    draft, linked, _ = prepare_single_role_linkage_draft(
        technology, {"PILE-S-02": candidate}, actor_role_code="ENGINEER_DESIGNER")
    report = populate_blocked_foundation_draft(draft, {"PILE-S-02": candidate}, actor_role_code="ENGINEER_DESIGNER")
    assert linked == ("PILE",) and report["reused_roles"] == ("SCREW_PILE",)
    assert [item.code for item in draft.requirements] == ["PILE"]
    quantity = next(item for item in draft.knowledge_rules if item.rule_code == "Q_SCREW_PILE_LAYOUT_ITEM_COUNT")
    assert quantity.scope_reference == str(draft.requirements[0].id)
    assert quantity.outcome_payload["material_role_code"] == "STEEL_PILE"
    assert quantity.outcome_payload["canonical_material_id"] == str(candidate.id)


def test_same_requirement_code_with_legacy_functional_role_is_reused():
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.models.material_attribute import MaterialAttribute
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement
    from app.services.module1_foundation_target_package import PACKAGE

    category = uuid4()
    technology = Technology(id=uuid4(), technology_code="FND_STRIP_PRECAST_FBS_FL", revision=1,
                            name="Фундамент", status="ACTIVE", input_missing_fields=[], input_blockers=[])
    technology.requirements = [TechnologyMaterialRequirement(id=uuid4(), code="FL", selector_kind="MATERIAL_CLASS",
        material_role_code="FOOTING_SLAB", material_category_id=category, technical_constraints={})]
    candidate = Material(id=uuid4(), canonical_name="ФЛ", status=MaterialStatus.DRAFT, category_id=category)
    candidate.attributes = [MaterialAttribute(attribute_name="registry_origin", attribute_value=PACKAGE),
                            MaterialAttribute(attribute_name="registry_code", attribute_value="FL-12")]
    draft, linked, _ = prepare_single_role_linkage_draft(
        technology, {"FL-12": candidate}, actor_role_code="ENGINEER_DESIGNER")
    report = populate_blocked_foundation_draft(draft, {"FL-12": candidate}, actor_role_code="ENGINEER_DESIGNER")
    assert linked == ("FL",) and "FL" in report["reused_roles"]
    assert [item.code for item in draft.requirements] == ["FL"]
    rule = next(item for item in draft.knowledge_rules if item.rule_code == "Q_FL_LAYOUT_ITEM_COUNT")
    assert rule.scope_reference == str(draft.requirements[0].id)
    assert rule.outcome_payload["material_role_code"] == "FOOTING_SLAB"


def test_blocked_draft_adds_distinct_roles_and_review_only_rules_without_changing_legacy():
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.models.material_attribute import MaterialAttribute
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement
    from app.services.module1_foundation_target_package import PACKAGE

    technology = Technology(id=uuid4(), technology_code="FND_STRIP_MONOLITHIC_RC", revision=1,
                            name="Лента", status="ACTIVE", input_missing_fields=[], input_blockers=[])
    legacy = TechnologyMaterialRequirement(id=uuid4(), code="REBAR", selector_kind="MATERIAL_CLASS",
                                            material_category_id=uuid4(), technical_constraints={})
    technology.requirements = [legacy]
    candidate = Material(id=uuid4(), canonical_name="Арматура", status=MaterialStatus.DRAFT, category_id=legacy.material_category_id)
    candidate.attributes = [MaterialAttribute(attribute_name="registry_origin", attribute_value=PACKAGE),
                            MaterialAttribute(attribute_name="registry_code", attribute_value="RA-04")]
    draft, _, unresolved = prepare_single_role_linkage_draft(
        technology, {"RA-04": candidate}, actor_role_code="ENGINEER_DESIGNER")
    report = populate_blocked_foundation_draft(draft, {"RA-04": candidate}, actor_role_code="ENGINEER_DESIGNER")
    assert unresolved == ("REBAR",)
    assert {"REBAR_TOP", "REBAR_BOTTOM"} <= set(report["added_roles"])
    assert legacy.selector_kind == "MATERIAL_CLASS" and legacy.canonical_material_id is None
    assert next(item for item in draft.requirements if item.code == "REBAR").selector_kind == "MATERIAL_CLASS"
    new = [item for item in draft.requirements if item.code in {"REBAR_TOP", "REBAR_BOTTOM"}]
    assert len(new) == 2 and all(item.canonical_material_id == candidate.id for item in new)
    assert draft.knowledge_rules and all(rule.status == "DRAFT" for rule in draft.knowledge_rules)
    quantity_rules = [rule for rule in draft.knowledge_rules if rule.outcome_payload.get("kind") == "FOUNDATION_QUANTITY_RULE"]
    composition = next(rule for rule in draft.knowledge_rules if rule.outcome_payload.get("kind") == "FOUNDATION_ROLE_COMPOSITION")
    assert all("evidence_review_required" in rule.blockers for rule in quantity_rules)
    assert "role_reconciliation_required" in composition.blockers
    assert composition.scope_reference == str(next(item for item in draft.requirements if item.code == "REBAR").id)
    assert composition.outcome_payload["parent_is_not_an_additional_purchase"] is True
    assert {child["role_code"] for child in composition.outcome_payload["children"]} == {"REBAR_TOP", "REBAR_BOTTOM"}
    assert "STIRRUPS" in composition.outcome_payload["unresolved_roles"]
    again = populate_blocked_foundation_draft(draft, {"RA-04": candidate}, actor_role_code="ENGINEER_DESIGNER")
    assert not again["added_roles"] and not again["added_rules"] and again["added_defaults"] == 0
    assert "foundation_reconciliation_required" in draft.input_blockers
    quantity_rules[0].scope_reference = str(uuid4())
    mismatched = populate_blocked_foundation_draft(draft, {"RA-04": candidate}, actor_role_code="ENGINEER_DESIGNER")
    assert quantity_rules[0].rule_code in mismatched["conflicts"]


def test_draft_population_requires_edit_permission_and_reconciliation_blocker():
    from app.models.module2_technology import Technology
    from app.services.module2_technology_foundation import Module2TechnologyPermissionError

    draft = Technology(id=uuid4(), technology_code="FND_STRIP_MONOLITHIC_RC", revision=2,
                       name="Лента", status="DRAFT", input_blockers=["foundation_reconciliation_required"])
    with pytest.raises(Module2TechnologyPermissionError):
        populate_blocked_foundation_draft(draft, {}, actor_role_code="CUSTOMER")
    draft.input_blockers = []
    with pytest.raises(ValueError, match="reconciliation-blocked"):
        populate_blocked_foundation_draft(draft, {}, actor_role_code="ENGINEER_DESIGNER")
    assert not draft.requirements and not draft.knowledge_rules


def test_reconciliation_blocker_has_a_user_facing_label():
    from app.services.module2_workbench import blocker_label

    assert "foundation_reconciliation_required" not in blocker_label("m1_blocker:foundation_reconciliation_required")
    assert "согласовать" in blocker_label("m1_blocker:foundation_reconciliation_required")


@pytest.mark.asyncio
async def test_all_foundation_drafts_preserve_gaps_and_are_idempotent_on_isolated_database():
    from sqlalchemy import func, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload
    from sqlalchemy.pool import NullPool
    from app.config import settings
    from app.models.material import Material
    from app.models.material_attribute import MaterialAttribute
    from app.models.module2_material_gap import Module2MaterialGap
    from app.models.module2_technology import Technology
    from app.services.module1_foundation_target_package import PACKAGE
    from app.services.module2_technology_foundation import read_technology

    if make_url(settings.DATABASE_URL).database != "houseplatform_fnd_m1_m2_20261110":
        pytest.skip("requires the dedicated restored foundation database")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine)() as db:
        materials = (await db.scalars(select(Material).join(MaterialAttribute).where(
            MaterialAttribute.attribute_name == "registry_origin", MaterialAttribute.attribute_value == PACKAGE,
        ).options(selectinload(Material.attributes)))).all()
        material_map = {}
        for material in materials:
            attrs = {item.attribute_name: item.attribute_value for item in material.attributes}
            if attrs.get("registry_code"):
                material_map[attrs["registry_code"]] = material
        technology_ids = (await db.scalars(select(Technology.id).where(
            Technology.status == "ACTIVE", Technology.technology_code.like("FND_%")))).all()
        assert len(technology_ids) == 15
        before = await db.scalar(select(func.count()).select_from(Module2MaterialGap))
        compositions = 0
        for technology_id in technology_ids:
            technology = await read_technology(db, technology_id)
            draft, _, _ = prepare_single_role_linkage_draft(technology, material_map, actor_role_code="ENGINEER_DESIGNER")
            populate_blocked_foundation_draft(draft, material_map, actor_role_code="ENGINEER_DESIGNER")
            db.add(draft)
            await db.flush()
            repeat = populate_blocked_foundation_draft(draft, material_map, actor_role_code="ENGINEER_DESIGNER")
            assert not repeat["added_roles"] and not repeat["added_rules"]
            assert not repeat["added_defaults"] and not repeat["updated_defaults"]
            assert "foundation_reconciliation_required" in draft.input_blockers
            compositions += sum((item.outcome_payload or {}).get("kind") == "FOUNDATION_ROLE_COMPOSITION"
                                for item in draft.knowledge_rules)
        assert compositions > 0
        assert await db.scalar(select(func.count()).select_from(Module2MaterialGap)) == before
        await db.rollback()
    await engine.dispose()


def test_exact_legacy_category_default_is_updated_only_in_new_draft():
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.models.material_attribute import MaterialAttribute
    from app.models.module2_technology import Technology, TechnologyDefaultAssumption, TechnologyMaterialRequirement
    from app.services.module1_foundation_target_package import PACKAGE

    category = uuid4()
    technology = Technology(id=uuid4(), technology_code="FND_STRIP_MONOLITHIC_RC", revision=1,
                            name="Лента", status="ACTIVE", input_missing_fields=[], input_blockers=[])
    requirement = TechnologyMaterialRequirement(id=uuid4(), code="CONCRETE", selector_kind="MATERIAL_CLASS",
        material_role_code="CONCRETE", material_category_id=category, technical_constraints={})
    technology.requirements = [requirement]
    default = TechnologyDefaultAssumption(id=uuid4(), assumption_code="MATERIAL_CONCRETE", revision=1,
        parameter_code="MATERIAL_CONCRETE", name_ru="Бетон", value_type="MATERIAL_CLASS",
        default_value={"value": str(category)}, source_kind="PLATFORM_ASSUMPTION", applicability={},
        auto_fallback=True, warning_level="WARNING", warning_text="Предварительно",
        allowed_values_strategy="M1_REQUIREMENT_CATEGORY", allowed_values={},
        material_requirement_id=requirement.id, status="ACTIVE")
    technology.default_assumptions = [default]
    materials = {}
    for code in ("BT-02", "BT-03", "BT-04"):
        material = Material(id=uuid4(), canonical_name=code, category_id=category, status=MaterialStatus.DRAFT)
        material.attributes = [MaterialAttribute(attribute_name="registry_origin", attribute_value=PACKAGE),
                               MaterialAttribute(attribute_name="registry_code", attribute_value=code)]
        materials[code] = material
    draft, linked, _ = prepare_single_role_linkage_draft(technology, materials, actor_role_code="ENGINEER_DESIGNER")
    report = populate_blocked_foundation_draft(draft, materials, actor_role_code="ENGINEER_DESIGNER")
    assert linked == ("CONCRETE",) and report["updated_defaults"] == ("MATERIAL_CONCRETE",)
    assert default.value_type == "MATERIAL_CLASS" and default.default_value == {"value": str(category)}
    copied = next(item for item in draft.default_assumptions if item.parameter_code == "MATERIAL_CONCRETE")
    assert copied.value_type == "MATERIAL" and copied.default_value == {"value": str(materials["BT-02"].id)}
    assert copied.applicability["structural_safety_verified"] is False
    again = populate_blocked_foundation_draft(draft, materials, actor_role_code="ENGINEER_DESIGNER")
    assert not again["updated_defaults"] and not again["conflicts"]


def test_reconciliation_reports_names_without_assuming_equivalence_or_mutating():
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement

    technology = Technology(technology_code="FND_STRIP_MONOLITHIC_RC", name="Лента", status="ACTIVE")
    technology.requirements = [TechnologyMaterialRequirement(code="CONCRETE"),
                               TechnologyMaterialRequirement(code="REBAR")]
    result = audit_profile_reconciliation(technology)
    assert result.same_code_needs_review == ("CONCRETE",)
    assert result.existing_only == ("REBAR",)
    assert {"REBAR_TOP", "REBAR_BOTTOM"} <= set(result.proposed_only)
    assert dict(result.suggested_expansions)["REBAR"][:2] == ("REBAR_TOP", "REBAR_BOTTOM")
    assert result.unmapped_existing == ()
    assert [item.code for item in technology.requirements] == ["CONCRETE", "REBAR"]
    technology.requirements.append(TechnologyMaterialRequirement(code="REBAR"))
    with pytest.raises(ValueError, match="require review"):
        audit_profile_reconciliation(technology)


def test_legacy_requirement_without_semantic_target_remains_explicitly_unmapped():
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement

    technology = Technology(technology_code="FND_SLAB_USHP", name="УШП", status="ACTIVE")
    technology.requirements = [TechnologyMaterialRequirement(code="UNRECOGNIZED_LEGACY_ROLE")]
    result = audit_profile_reconciliation(technology)
    assert result.unmapped_existing == ("UNRECOGNIZED_LEGACY_ROLE",)
    assert technology.requirements[0].code == "UNRECOGNIZED_LEGACY_ROLE"


def test_semantic_candidates_cover_the_audited_40_requirements_without_losing_gaps():
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement

    audited = {
        "FND_STRIP_MONOLITHIC_RC": "CONCRETE FORMWORK INSULATION REBAR WATERPROOFING",
        "FND_STRIP_PRECAST_FBS_FL": "FBS FL MORTAR WATERPROOFING",
        "FND_SLAB_MONOLITHIC_RC": "CONCRETE FORMWORK INSULATION REBAR WATERPROOFING",
        "FND_SLAB_RIBBED_RC": "CONCRETE FORMWORK REBAR",
        "FND_SLAB_USHP": "CONCRETE REBAR WATERPROOFING XPS",
        "FND_UFF": "CONCRETE REBAR WATERPROOFING XPS",
        "FND_PILE_BORED_RC": "CASING CONCRETE REBAR",
        "FND_PILE_DRIVEN_RC": "PILE", "FND_PILE_SCREW": "PILE",
        "FND_PILE_GRILLAGE": "CONCRETE REBAR", "FND_COLUMN_CONCRETE_RC": "CONCRETE REBAR",
        "FND_BASEMENT_WALL_MONOLITHIC": "CONCRETE REBAR WATERPROOFING",
        "FND_SUBSTRUCTURE_WATERPROOFING_COATING": "MASTIC",
        "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE": "MEMBRANE",
        "FND_SUBSTRUCTURE_INSULATION_XPS": "XPS",
    }
    assert sum(len(codes.split()) for codes in audited.values()) == 40
    unresolved = []
    for code, codes in audited.items():
        technology = Technology(technology_code=code, name="Тест", status="ACTIVE")
        technology.requirements = [TechnologyMaterialRequirement(code=item) for item in codes.split()]
        audit = audit_profile_reconciliation(technology)
        unresolved.extend((code, item) for item in audit.unmapped_existing)
    assert unresolved == []


def test_every_existing_foundation_technology_has_one_preliminary_profile():
    expected = {
        "FND_STRIP_MONOLITHIC_RC", "FND_STRIP_PRECAST_FBS_FL", "FND_SLAB_MONOLITHIC_RC",
        "FND_SLAB_RIBBED_RC", "FND_SLAB_USHP", "FND_UFF", "FND_PILE_BORED_RC",
        "FND_PILE_DRIVEN_RC", "FND_PILE_SCREW", "FND_PILE_GRILLAGE", "FND_COLUMN_CONCRETE_RC",
        "FND_BASEMENT_WALL_MONOLITHIC", "FND_SUBSTRUCTURE_WATERPROOFING_COATING",
        "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE", "FND_SUBSTRUCTURE_INSULATION_XPS",
    }
    assert len(PROFILES) == 15
    assert {item.technology_code for item in PROFILES} == expected
    assert len({item.profile_code for item in PROFILES}) == 15
    registry_codes = {dict(item.properties).get("registry_code") for item in targets()}
    for profile in PROFILES:
        assert profile.status == "PRELIMINARY_ESTIMATE"
        assert "не проверка несущей способности" in profile.warning
        assert len({role.code for role in profile.roles}) == len(profile.roles)
        for role in profile.roles:
            assert role.material_code is None or role.material_code in registry_codes
            assert all(code in registry_codes for code in role.alternatives)
            assert role.quantity_rule is None or role.quantity_rule in RULES
            assert all(code in RULES for code in role.follow_up_rules)
            assert role.material_code or role.missing


def test_basement_four_roles_share_one_m1_card_without_merging_roles():
    profile = next(item for item in PROFILES if item.technology_code == "FND_BASEMENT_WALL_MONOLITHIC")
    assert [item.code for item in profile.roles if item.material_code == "RA-04"] == [
        "OUTER_VERTICAL", "OUTER_HORIZONTAL", "INNER_VERTICAL", "INNER_HORIZONTAL",
    ]
    material_id = uuid4()
    proposals, unresolved = profile_requirement_proposals(profile.technology_code, {"RA-04": material_id})
    assert len(proposals) == 4 and len(unresolved) > 0
    assert len({item.code for item in proposals}) == 4
    assert {item.canonical_material_id for item in proposals} == {material_id}
    assert all(item.technical_constraints == {} for item in proposals)
    assert all("Предварительная комплектация" in item.notes for item in proposals)
    parameters = {name: (value, unit) for name, value, unit in profile.parameters}
    assert all(parameters[name] == ("200", "mm") for name in (
        "outer_vertical_spacing", "outer_horizontal_spacing", "inner_vertical_spacing", "inner_horizontal_spacing"))
    assert "mesh_spacing" not in parameters


def test_precast_and_factory_pile_keep_layout_and_do_not_add_factory_concrete():
    precast = next(item for item in PROFILES if item.technology_code == "FND_STRIP_PRECAST_FBS_FL")
    selected = {item.code: item for item in precast.roles}
    assert selected["FBS_MAIN"].material_code == "FBS-02"
    assert selected["FBS_SHORT"].material_code == "FBS-05"
    assert selected["FBS_SHORTER"].material_code == "FBS-09"
    assert selected["FL"].material_code == "FL-12"
    assert all(selected[name].quantity_rule == "LAYOUT_ITEM_COUNT" for name in ("FBS_MAIN", "FBS_SHORT", "FBS_SHORTER", "FL"))
    pile = next(item for item in PROFILES if item.technology_code == "FND_PILE_DRIVEN_RC")
    assert not any(item.material_code and item.material_code.startswith(("BT-", "RA-")) for item in pile.roles)


def test_unknown_or_unmapped_technology_fails_closed():
    with pytest.raises(ValueError):
        profile_requirement_proposals("UNKNOWN", {})
    proposals, unresolved = profile_requirement_proposals("FND_PILE_SCREW", {})
    assert not proposals and set(unresolved) == {"SCREW_PILE", "PILE_HEAD", "CONNECTION", "COATING"}


@pytest.mark.parametrize("technology_code", ["FND_SLAB_RIBBED_RC", "FND_SLAB_USHP"])
def test_slab_and_rib_concrete_are_separate_roles_with_overlap_guard(technology_code):
    profile = next(item for item in PROFILES if item.technology_code == technology_code)
    roles = {item.code: item for item in profile.roles}
    assert roles["SLAB_CONCRETE"].material_code == roles["RIB_CONCRETE"].material_code == "BT-02"
    assert roles["SLAB_CONCRETE"].quantity_rule == "NET_AREA_VOLUME"
    assert roles["RIB_CONCRETE"].quantity_rule == "BOX_VOLUME_EXCLUDING_OCCUPIED"


def test_manual_alternatives_are_not_advertised_as_automatically_equivalent():
    material_id = uuid4()
    proposals, _ = profile_requirement_proposals("FND_STRIP_MONOLITHIC_RC", {"BT-02": material_id})
    assert len(proposals) == 1
    profile = next(item for item in PROFILES if item.technology_code == "FND_STRIP_MONOLITHIC_RC")
    assert next(item for item in profile.roles if item.code == "CONCRETE").alternatives == ("BT-03", "BT-04")
    assert proposals[0].technical_constraints == {}


def test_xps_rules_report_the_registry_base_unit_of_square_metres():
    roles = [role for profile in PROFILES for role in profile.roles
             if role.material_code and role.material_code.startswith("XPS-") and role.quantity_rule]
    assert roles
    assert all(RULES[role.quantity_rule].result_unit == "m2" for role in roles)


def test_quantity_rules_are_proposed_as_blocked_m2_knowledge_not_material_constraints():
    material_id, requirement_id = uuid4(), uuid4()
    proposals, unresolved = profile_quantity_rule_proposals(
        "FND_STRIP_MONOLITHIC_RC", {"BT-02": material_id}, {"CONCRETE": requirement_id})
    assert len(proposals) == 1 and unresolved
    rule = proposals[0]
    assert rule.scope_reference == str(requirement_id)
    assert rule.outcome_payload["code"] == "BOX_UNION_VOLUME"
    assert rule.outcome_payload["canonical_material_id"] == str(material_id)
    assert "material_review_required" in rule.blockers and "evidence_review_required" in rule.blockers


def test_profile_proposals_fit_existing_m2_draft_services():
    from app.models.module2_technology import Technology
    from app.services.module2_knowledge_foundation import create_knowledge_rule_draft
    from app.services.module2_workbench import upsert_draft_requirement

    technology = Technology(id=uuid4(), technology_code="FND_STRIP_MONOLITHIC_RC", revision=2,
                            name="Предварительный вариант", status="DRAFT")
    material_id = uuid4()
    requirements, _ = profile_requirement_proposals(technology.technology_code, {"BT-02": material_id})
    requirement = upsert_draft_requirement(technology, requirements[0], actor_role_code="ADMIN")
    rules, _ = profile_quantity_rule_proposals(technology.technology_code, {"BT-02": material_id},
                                               {"CONCRETE": requirement.id})
    rule = create_knowledge_rule_draft(technology, rules[0], actor_role_code="ADMIN")
    assert requirement.canonical_material_id == material_id and requirement.technical_constraints == {}
    assert rule.scope_reference == str(requirement.id)
    assert rule.status == "DRAFT" and rule.outcome_payload["structural_safety_verified"] is False
    assert set(rule.blockers) == {"evidence_review_required", "material_review_required"}


@pytest.mark.asyncio
async def test_workbench_material_edit_preserves_other_characteristics():
    from unittest.mock import AsyncMock
    from app.api.v1.module2_workbench import _perform_action
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement

    technology = Technology(id=uuid4(), technology_code="FND_STRIP_MONOLITHIC_RC", revision=2,
                            name="Черновик", status="DRAFT")
    requirement = TechnologyMaterialRequirement(
        id=uuid4(), code="CONCRETE", selector_kind="ROLE", material_role_code="CONCRETE",
        technical_constraints={"concrete_class": "B25", "water_resistance": "W8", "frost_cycles": 150},
    )
    technology.requirements.append(requirement)
    form = {"item_id": str(requirement.id), "code": "CONCRETE", "selector_kind": "ROLE",
            "material_role_code": "CONCRETE", "constraint_field": "concrete_class", "constraint_value": "B30"}
    await _perform_action("save-requirement", form, technology=technology,
                          db=AsyncMock(), role_code="ADMIN", user_id=uuid4())
    assert requirement.technical_constraints == {
        "concrete_class": "B30", "water_resistance": "W8", "frost_cycles": 150,
    }


@pytest.mark.asyncio
async def test_workbench_loads_unverified_candidate_without_marking_it_selected():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.api.v1.module2_workbench import _selected_material, _technical_material_candidates
    from app.models.enums import MaterialStatus

    material = SimpleNamespace(id=uuid4(), canonical_name="БСТ B25 W6 F1 150 П4", status=MaterialStatus.DRAFT)
    requirement = SimpleNamespace(canonical_material_id=material.id, selector_kind="CANONICAL_MATERIAL")
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [material])))
    candidates = await _technical_material_candidates(db, [requirement])
    assert candidates[material.id] is material
    assert _selected_material(requirement, None, ()) is None
    assert "materials.status" in str(db.scalars.await_args.args[0])
    assert await _technical_material_candidates(db, []) == {}
    assert db.scalars.await_count == 1


def test_preliminary_default_proposals_reuse_existing_and_keep_priority():
    from app.models.module2_technology import Technology
    from app.services.module2_default_assumptions import DefaultAssumptionError, resolve_default_assumptions

    technology = Technology(id=uuid4(), technology_code="FND_STRIP_MONOLITHIC_RC", revision=2,
                            name="Черновик", status="DRAFT")
    proposals, reused, conflicts = profile_numeric_default_proposals(technology)
    assert len(proposals) == 6 and not reused and not conflicts
    technology.default_assumptions.extend(proposals)
    assert all(item.applicability["structural_safety_verified"] is False for item in proposals)
    values = {item["parameter_code"]: item for item in resolve_default_assumptions(technology)}
    assert values["STRIP_WIDTH_MM"]["resolved_value"] == "400"
    assert values["STRIP_WIDTH_MM"]["source"] == "M2_DEFAULT"
    chosen = resolve_default_assumptions(technology, project_values={"STRIP_WIDTH_MM": 500},
                                        user_overrides={"STRIP_WIDTH_MM": 600})
    assert next(item for item in chosen if item["parameter_code"] == "STRIP_WIDTH_MM")["source"] == "USER_OVERRIDE"
    with pytest.raises(DefaultAssumptionError):
        resolve_default_assumptions(technology, user_overrides={"TOP_BAR_COUNT": "2.5"})
    with pytest.raises(DefaultAssumptionError):
        resolve_default_assumptions(technology, user_overrides={"STRIP_WIDTH_MM": "0"})
    created, reused, conflicts = profile_numeric_default_proposals(technology)
    assert not created and len(reused) == 6 and not conflicts
    proposals[0].default_value = {"value": "500"}
    created, reused, conflicts = profile_numeric_default_proposals(technology)
    assert not created and "STRIP_WIDTH_MM" in conflicts and len(reused) == 5
    technology.status = "ACTIVE"
    with pytest.raises(ValueError, match="DRAFT"):
        profile_numeric_default_proposals(technology)


def test_material_defaults_keep_roles_separate_and_alternatives_manual():
    from app.models.module2_technology import Technology
    from app.services.module2_default_assumptions import resolve_default_assumptions
    from app.services.module2_workbench import upsert_draft_requirement

    technology = Technology(id=uuid4(), technology_code="FND_STRIP_MONOLITHIC_RC", revision=2,
                            name="Черновик", status="DRAFT")
    ids = {code: uuid4() for code in ("RA-03", "RA-04", "RA-05", "RA-06")}
    requirement_inputs, _ = profile_requirement_proposals(technology.technology_code, ids)
    requirements = [upsert_draft_requirement(technology, item, actor_role_code="ADMIN")
                    for item in requirement_inputs]
    requirement_ids = {item.code: item.id for item in requirements}
    proposals, reused, conflicts, unresolved = profile_material_default_proposals(technology, ids, requirement_ids)
    assert len(proposals) == 2 and not reused and not conflicts and unresolved
    assert {item.material_requirement_id for item in proposals} == set(requirement_ids.values())
    assert {item.default_value["value"] for item in proposals} == {str(ids["RA-04"])}
    assert all(item.applicability["alternative_kind"] == "MANUAL_CONFIGURATION_CHANGE_NOT_EQUIVALENCE"
               for item in proposals)
    technology.default_assumptions.extend(proposals)
    values = resolve_default_assumptions(technology, user_overrides={"MATERIAL_REBAR_TOP": str(ids["RA-05"])})
    result = {item["parameter_code"]: item for item in values}
    assert result["MATERIAL_REBAR_TOP"]["source"] == "USER_OVERRIDE"
    assert result["MATERIAL_REBAR_BOTTOM"]["resolved_value"] == str(ids["RA-04"])
    created, reused, conflicts, _ = profile_material_default_proposals(technology, ids, requirement_ids)
    assert not created and len(reused) == 2 and not conflicts
    del ids["RA-03"]
    created, _, _, unresolved = profile_material_default_proposals(technology, ids, requirement_ids)
    assert not created and {"REBAR_TOP", "REBAR_BOTTOM"} <= set(unresolved)


def test_stirrup_count_is_not_mistaken_for_a_complete_mass_quantity():
    profile = next(item for item in PROFILES if item.technology_code == "FND_STRIP_MONOLITHIC_RC")
    stirrups = next(item for item in profile.roles if item.code == "STIRRUPS")
    assert stirrups.quantity_rule == "SPACED_ZONES_COUNT"
    assert stirrups.follow_up_rules == ("STIRRUP_CUT_LENGTH", "BAR_MASS")
    assert stirrups.missing


@pytest.mark.parametrize("technology_code,parameter", [
    ("FND_PILE_BORED_RC", "PILE_DIAMETER_MM"),
    ("FND_PILE_BORED_RC", "PILE_LENGTH_MM"),
    ("FND_SLAB_RIBBED_RC", "RIB_HEIGHT_MM"),
    ("FND_BASEMENT_WALL_MONOLITHIC", "WALL_HEIGHT_MM"),
    ("FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE", "MEMBRANE_THICKNESS_MM"),
])
def test_old_defaults_requiring_object_inputs_do_not_autofill(technology_code, parameter):
    from app.models.module2_technology import Technology, TechnologyDefaultAssumption
    from app.services.module2_default_assumptions import resolve_default_assumptions

    technology = Technology(id=uuid4(), technology_code=technology_code, revision=1, name="Test")
    technology.default_assumptions.append(TechnologyDefaultAssumption(
        id=uuid4(), assumption_code=parameter, revision=1, parameter_code=parameter, name_ru="Параметр",
        value_type="NUMBER", unit="мм", default_value={"value": 100}, source_kind="PLATFORM_ASSUMPTION",
        applicability={}, auto_fallback=True, warning_level="WARNING", warning_text="Предварительно",
        allowed_values_strategy="BOUNDED_NUMBER", allowed_values={"min": 1, "max": 5000}, status="ACTIVE",
    ))
    missing = resolve_default_assumptions(technology)[0]
    assert missing["source"] == "UNRESOLVED" and missing["resolved_value"] is None
    assert "Требуется" in missing["warning_text"]
    project = resolve_default_assumptions(technology, project_values={parameter: 200})[0]
    assert project["source"] == "PROJECT_VALUE" and project["resolved_value"] == "200"
    override = resolve_default_assumptions(technology, project_values={parameter: 200}, user_overrides={parameter: 300})[0]
    assert override["source"] == "USER_OVERRIDE" and override["resolved_value"] == "300"
