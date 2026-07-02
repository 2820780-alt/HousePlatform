from app.services.material_hub_first_wave import first_wave_yufo_source_seed
from app.services.source_adapter_template import (
    NEW_SITE_ADAPTER_STEPS,
    REQUIRED_TEMPLATE_SECTIONS,
    build_source_adapter_template,
)


def test_source_adapter_template_contains_required_sections_and_gates():
    seed = first_wave_yufo_source_seed("ЮгКабель")
    template = build_source_adapter_template(
        seed,
        test_urls=[
            "https://yugkabel.ru/products/example-1",
            "https://yugkabel.ru/products/example-2",
            "https://yugkabel.ru/products/example-3",
            "https://yugkabel.ru/products/example-4",
            "https://yugkabel.ru/products/example-5",
        ],
    )

    assert template["sourceCode"] == "YUFO_YUGKABEL"
    assert template["trustLevel"] == "TEST"
    assert template["writeMode"] == "preview_only"
    assert template["parserStatus"] == "TEST"
    assert template["requiredSections"] == REQUIRED_TEMPLATE_SECTIONS
    assert template["onboardingSteps"] == NEW_SITE_ADAPTER_STEPS
    assert template["SourceProfile"]["source_code"] == "YUFO_YUGKABEL"
    assert template["ExtractionProfile"]["parsing_rules"]["document_rules"]["site_page_is_document"] is False
    assert template["DocumentExtractionRules"]["document_markers"]
    assert template["ExpectedFields"]
    assert template["QualityReport"]["recommended_next_action"] == "keep_preview_only"
    assert template["qualityGates"]["previewOnlyFirst"] is True
    assert template["qualityGates"]["activeMaterialCreationAllowed"] is False
