from app.services.module1_fnd2_materials import MaterialCandidate, candidate_attributes, category_slug
from app.services.module1_fnd2_works import REVIEWED_MATCHES
from app.services.module2_fnd2_material_links import CONDITIONAL_ROLES, MATERIAL_LINKS
from app.services.module2_fnd2_work_links import BUNDLE_NOTE, WORKS


def test_foundation_material_characteristics_are_preserved_without_filling_gaps():
    candidate = MaterialCandidate("BASE-02", "Щебень фракции 5–20 мм", "Подготовка основания", "m3", "фракция=5–20 мм")
    assert candidate_attributes(candidate) == {"фракция": "5–20 мм"}
    assert category_slug(candidate) == "m1-ui-bulk-materials"


def test_foundation_material_categories_preserve_distinct_purposes():
    def candidate(key):
        return MaterialCandidate(key, "material", "group", "piece", "description")

    assert category_slug(candidate("BASE-04")) == "m1-ui-insulation"
    assert category_slug(candidate("FORM-10")) == "m1-ui-mixes-chemicals"
    assert category_slug(candidate("DRN-03-DN110")) == "m1-ui-pipes-drainage"
    assert category_slug(candidate("ARM-AUX-03")) == "m1-ui-fasteners"


def test_work_matches_do_not_replace_meter_based_boring_with_per_pile_price():
    assert "FND-WK-026" not in REVIEWED_MATCHES
    assert "FND-WK-013" not in REVIEWED_MATCHES
    assert REVIEWED_MATCHES["FND-WK-029"] == "foundations_concrete_pogruzhenie_zhelezobetonnyh_svay"


def test_foundation_material_choices_cover_drafts_without_components_of_factory_piles():
    assert len(MATERIAL_LINKS) == 15
    factory_piles = MATERIAL_LINKS["FND_PILE_DRIVEN_RC"]
    assert all(not key.startswith(("BT-", "RA-")) for key in factory_piles)
    assert {"WPR-03", "WPR-04"}.issubset(MATERIAL_LINKS["FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE"])


def test_bundled_works_are_not_automatically_mixed_with_their_components():
    assert set(WORKS) == set(MATERIAL_LINKS)
    assert WORKS["FND_PILE_GRILLAGE"] == ()
    assert WORKS["FND_SUBSTRUCTURE_WATERPROOFING_COATING"] == ()
    assert WORKS["FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE"] == ()
    assert WORKS["FND_SUBSTRUCTURE_INSULATION_XPS"] == ()
    assert 23 in WORKS["FND_STRIP_PRECAST_FBS_FL"]
    assert WORKS["FND_STRIP_PRECAST_FBS_FL"].index(23) < WORKS["FND_STRIP_PRECAST_FBS_FL"].index(22)
    assert "не суммировать" in BUNDLE_NOTE


def test_unspecified_foundation_choices_remain_thirteen_conditional_roles():
    assert len(CONDITIONAL_ROLES) == 13
    assert "FND_PILE_SCREW" in CONDITIONAL_ROLES["PILE-S-06"]
    assert all(set(destinations) <= set(MATERIAL_LINKS) for destinations in CONDITIONAL_ROLES.values())
import json
from pathlib import Path



def test_all_reviewed_material_candidates_have_a_conditional_technology_choice():
    source = json.loads(Path("src/modules/module1/seeds/fnd2_candidates.json").read_text(encoding="utf-8"))
    material_keys = {row[0] for row in source["materials"]}
    assert len(material_keys) == 34
    assert material_keys <= {key for keys in MATERIAL_LINKS.values() for key in keys}
