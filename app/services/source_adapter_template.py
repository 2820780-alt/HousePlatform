from __future__ import annotations

from typing import Any

from app.models.enums import SourceActionType, SourceType
from app.models.source import Source
from app.services.material_hub_first_wave import FirstWaveSourceSeed
from app.services.source_profiles import build_source_profile_snapshot
from app.services.source_quality_report import build_source_quality_report, source_quality_report_dict


NEW_SITE_ADAPTER_STEPS = [
    "Создать SourceProfile.",
    "Добавить 5-20 testUrls.",
    "Запустить preview_only.",
    "Проверить товары, цены, единицы, документы, регион.",
    "Исправить mapping.",
    "Запустить create_candidates.",
    "Оценить QualityReport.",
    "Только после этого повышать trustLevel.",
]

REQUIRED_TEMPLATE_SECTIONS = [
    "SourceProfile",
    "ExtractionProfile",
    "CategoryMapping",
    "NormalizationRules",
    "ModerationRules",
    "DocumentExtractionRules",
    "TestUrls",
    "ExpectedFields",
    "QualityReport",
]


def build_source_adapter_template(
    seed: FirstWaveSourceSeed | dict[str, Any],
    *,
    test_urls: list[str] | None = None,
) -> dict[str, Any]:
    parameters = _seed_parameters(seed)
    source = Source(
        name=parameters["source_name"],
        source_type=_source_type(parameters.get("sourceType")),
        url=parameters.get("baseUrl"),
        priority=int(parameters.get("priority") or 100),
    )
    snapshot = build_source_profile_snapshot(
        source,
        SourceActionType.INITIAL_MATERIAL_SCAN,
        {
            **parameters,
            "testUrls": test_urls or [],
            "test_urls": test_urls or [],
            "document_markers": [
                "сертификат",
                "декларация",
                "технический лист",
                "инструкция",
                "паспорт",
                "каталог",
                "прайс",
                "условия доставки",
            ],
        },
        adapter_code=None,
        supported_actions={SourceActionType.INITIAL_MATERIAL_SCAN, SourceActionType.UPDATE_PRICES},
    )
    quality_report = build_source_quality_report(source=source, parameters=parameters)
    return {
        "templateVersion": "MODULE_01_SOURCE_ADAPTER_TEMPLATE_V1",
        "requiredSections": REQUIRED_TEMPLATE_SECTIONS,
        "sourceCode": parameters["sourceCode"],
        "displayName": parameters["displayName"],
        "baseUrl": parameters.get("baseUrl"),
        "trustLevel": "TEST",
        "writeMode": "preview_only",
        "parserStatus": "TEST",
        "onboardingSteps": NEW_SITE_ADAPTER_STEPS,
        "SourceProfile": snapshot["source_profile"],
        "ExtractionProfile": snapshot["extraction_profile"],
        "CategoryMapping": snapshot["extraction_profile"].get("source_category_mappings", []),
        "NormalizationRules": snapshot["normalization_profile"],
        "ModerationRules": snapshot["extraction_profile"].get("moderation_rules", []),
        "DocumentExtractionRules": snapshot["extraction_profile"].get("parsing_rules", {}).get("document_rules", {}),
        "TestUrls": _test_urls(test_urls),
        "ExpectedFields": [
            "raw_name",
            "price",
            "unit",
            "availability",
            "raw_category",
            "raw_brand/raw_manufacturer optional",
            "region/city",
            "document_url optional",
        ],
        "QualityReport": source_quality_report_dict(quality_report),
        "qualityGates": {
            "minTestUrls": 5,
            "maxTestUrls": 20,
            "previewOnlyFirst": True,
            "createCandidatesRequiresQualityReport": True,
            "trustEscalationRequiresModeratorApproval": True,
            "activeMaterialCreationAllowed": False,
        },
        "notes": [
            "Do not bypass captcha, robots restrictions or source protection.",
            "Do not create ACTIVE Material from adapter output.",
            "Catalog pages and product pages are not DocumentRecord.",
            "Documents must be collected only by explicit document/file markers.",
        ],
    }


def _seed_parameters(seed: FirstWaveSourceSeed | dict[str, Any]) -> dict[str, Any]:
    if isinstance(seed, FirstWaveSourceSeed):
        return seed.to_profile_parameters()
    return {
        "sourceCode": seed.get("sourceCode") or seed.get("source_code"),
        "source_code": seed.get("sourceCode") or seed.get("source_code"),
        "source_name": seed.get("displayName") or seed.get("display_name") or seed.get("name"),
        "displayName": seed.get("displayName") or seed.get("display_name") or seed.get("name"),
        "baseUrl": seed.get("baseUrl") or seed.get("base_url"),
        "base_url": seed.get("baseUrl") or seed.get("base_url"),
        "sourceType": seed.get("sourceType") or seed.get("source_type") or SourceType.SUPPLIER.value,
        "priority": seed.get("priority") or 100,
        "focusRegion": seed.get("focusRegion") or seed.get("focus_region"),
        "directions": seed.get("directions") or [],
        "parserStatus": "TEST",
        "writeMode": "preview_only",
        "write_mode": "PREVIEW",
        "trustLevel": "TEST",
        "notes": seed.get("notes"),
    }


def _source_type(value: Any) -> SourceType:
    if isinstance(value, SourceType):
        return value
    try:
        return SourceType(str(value))
    except ValueError:
        return SourceType.SUPPLIER


def _test_urls(test_urls: list[str] | None) -> list[str]:
    urls = list(test_urls or [])
    return urls[:20]
