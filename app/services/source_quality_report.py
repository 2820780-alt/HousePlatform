from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Iterable

from app.schemas.material_hub_contracts import SourceQualityReport, SourceTrustLevel
from app.services.material_normalization_rules import normalize_material_title


QUALITY_ACTION_ENABLE_CREATE_CANDIDATES = "enable_create_candidates"
QUALITY_ACTION_KEEP_PREVIEW_ONLY = "keep_preview_only"
QUALITY_ACTION_IMPROVE_CATEGORY_MAPPING = "improve_category_mapping"
QUALITY_ACTION_ADD_UNIT_CONVERTER = "add_unit_converter"
QUALITY_ACTION_ADD_SOURCE_ALIASES = "add_source_aliases"
QUALITY_ACTION_PAUSE_SOURCE = "pause_source"
QUALITY_ACTION_MARK_BLOCKED = "mark_blocked"


def build_source_quality_report(
    *,
    source: Any = None,
    parameters: dict | None = None,
    products: Iterable[Any] | None = None,
    documents: Iterable[Any] | None = None,
    parsed_rows: Iterable[Any] | None = None,
    summary: dict | None = None,
    parser_problems: Iterable[str] | None = None,
) -> SourceQualityReport:
    params = parameters or {}
    summary_payload = summary or {}
    products_list = list(products or [])
    documents_list = list(documents or [])
    parsed_rows_list = list(parsed_rows or [])
    product_like_rows = products_list or parsed_rows_list
    problems = [problem for problem in (parser_problems or []) if problem]

    detected_categories = _unique(
        _get(item, "raw_category", "rawCategory", "supplier_category", "supplierCategory")
        for item in product_like_rows
    )
    units = Counter(
        str(unit)
        for unit in (_get(item, "unit", "original_unit", "raw_unit", "rawUnit") for item in product_like_rows)
        if unit
    )
    normalizations = [
        normalize_material_title(
            _get(item, "raw_name", "rawName", "original_name", "originalName"),
            brand=_get(item, "raw_brand", "rawBrand", "brand"),
            manufacturer=_get(item, "raw_manufacturer", "rawManufacturer", "manufacturer"),
            category=_get(item, "raw_category", "rawCategory", "supplier_category", "supplierCategory"),
            unit=_get(item, "unit", "original_unit", "raw_unit", "rawUnit"),
            price=_get(item, "price", "original_price", "raw_price", "rawPrice"),
            availability=_get(item, "availability"),
            region=_get(item, "region"),
            city=_get(item, "city"),
        )
        for item in product_like_rows
        if _get(item, "raw_name", "rawName", "original_name", "originalName")
    ]
    mapped_atom_categories = _unique(item.direction_title or item.direction_code for item in normalizations)
    products_scanned = _int(summary_payload.get("productsScanned") or summary_payload.get("fetched"), len(product_like_rows))
    products_parsed = _int(
        summary_payload.get("productsParsed") or summary_payload.get("created") or summary_payload.get("rows_processed"),
        len([item for item in product_like_rows if _get(item, "raw_name", "rawName", "original_name", "originalName")]),
    )
    products_need_review = _int(
        summary_payload.get("productsNeedReview") or summary_payload.get("match_candidates") or summary_payload.get("rows_needs_review"),
        len([item for item in normalizations if item.needs_review_reasons]),
    )
    products_ignored = _int(
        summary_payload.get("productsIgnored"),
        len([item for item in normalizations if item.ignored_candidate_reasons]),
    )
    prices_detected = _int(
        summary_payload.get("pricesDetected") or summary_payload.get("price_changes"),
        len([item for item in product_like_rows if _get(item, "price", "original_price", "raw_price", "rawPrice") is not None]),
    )
    availability_detected = _int(
        summary_payload.get("availabilityDetected"),
        len([item for item in product_like_rows if _get(item, "availability")]),
    )
    certificates_detected = len([
        item for item in documents_list if "сертифик" in str(_get(item, "document_type", "documentType") or "").lower()
    ])
    documents_detected = _int(summary_payload.get("documentsDetected") or summary_payload.get("fetched"), len(documents_list))
    problems.extend(_summary_problems(summary_payload))
    recommended = recommended_next_action(
        parser_problems=problems,
        products_scanned=products_scanned,
        products_parsed=products_parsed,
        products_need_review=products_need_review,
        products_ignored=products_ignored,
        detected_categories=detected_categories,
        mapped_atom_categories=mapped_atom_categories,
        common_units=dict(units),
        trust_level=_trust_level(params),
    )
    issues = [{"code": _problem_code(problem), "message": problem} for problem in problems]

    return SourceQualityReport(
        source_code=params.get("sourceCode") or params.get("source_code") or _source_code(source),
        source_name=_source_name(source, params),
        source_url=params.get("baseUrl") or params.get("base_url") or getattr(source, "url", None),
        region=params.get("region") or params.get("focusRegion") or params.get("activeRegionCode"),
        city=params.get("city") or params.get("source_city_name"),
        source_type=params.get("sourceType") or params.get("data_source_kind") or getattr(source, "source_type", None),
        generated_at=datetime.now(UTC),
        parser_status=params.get("parserStatus") or params.get("parser_status") or summary_payload.get("parserStatus"),
        trust_level=_trust_level(params),
        products_checked=products_scanned,
        detected_categories=detected_categories,
        mapped_atom_categories=mapped_atom_categories,
        products_scanned=products_scanned,
        products_parsed=products_parsed,
        products_classified_high_confidence=_int(
            summary_payload.get("productsClassifiedHighConfidence"),
            len([item for item in normalizations if not item.needs_review_reasons]),
        ),
        products_need_review=products_need_review,
        products_ignored=products_ignored,
        prices_detected=prices_detected,
        availability_detected=availability_detected,
        documents_checked=documents_detected,
        documents_detected=documents_detected,
        certificates_detected=_int(summary_payload.get("certificatesDetected"), certificates_detected),
        document_candidates_found=_int(summary_payload.get("document_candidates_found"), len(documents_list)),
        document_duplicates_skipped=_int(summary_payload.get("document_duplicates_skipped"), 0),
        common_units=dict(units),
        parser_problems=problems,
        recommended_next_action=recommended,
        issues=issues,
        recommendations=_recommendations(recommended),
    )


def recommended_next_action(
    *,
    parser_problems: list[str],
    products_scanned: int,
    products_parsed: int,
    products_need_review: int,
    products_ignored: int,
    detected_categories: list[str],
    mapped_atom_categories: list[str],
    common_units: dict[str, int],
    trust_level: SourceTrustLevel,
) -> str:
    problem_text = " ".join(parser_problems).lower()
    if "blocked" in problem_text or "captcha" in problem_text or "403" in problem_text:
        return QUALITY_ACTION_MARK_BLOCKED
    if parser_problems and products_parsed == 0:
        return QUALITY_ACTION_PAUSE_SOURCE
    if products_scanned and not mapped_atom_categories:
        return QUALITY_ACTION_IMPROVE_CATEGORY_MAPPING
    if any("?" in unit or "unknown" in unit.lower() for unit in common_units):
        return QUALITY_ACTION_ADD_UNIT_CONVERTER
    if products_scanned >= 5 and products_need_review > max(3, products_parsed // 2):
        return QUALITY_ACTION_ADD_SOURCE_ALIASES
    if trust_level == SourceTrustLevel.TEST:
        return QUALITY_ACTION_KEEP_PREVIEW_ONLY
    if products_parsed and products_need_review <= max(2, products_parsed // 5) and products_ignored <= max(1, products_parsed // 10):
        return QUALITY_ACTION_ENABLE_CREATE_CANDIDATES
    return QUALITY_ACTION_KEEP_PREVIEW_ONLY


def _recommendations(action: str) -> list[str]:
    mapping = {
        QUALITY_ACTION_ENABLE_CREATE_CANDIDATES: [
            "Quality is acceptable for create_candidates, but ACTIVE Material still requires approved rules/moderation.",
        ],
        QUALITY_ACTION_KEEP_PREVIEW_ONLY: [
            "Keep source in preview_only until test URLs, mapping, units, documents and region are verified.",
        ],
        QUALITY_ACTION_IMPROVE_CATEGORY_MAPPING: [
            "Detected categories are not mapped to ATOM categories. Improve SourceCategoryMapping first.",
        ],
        QUALITY_ACTION_ADD_UNIT_CONVERTER: [
            "Unknown or unstable units detected. Add UnitNormalizationRule/UnitConversionRule.",
        ],
        QUALITY_ACTION_ADD_SOURCE_ALIASES: [
            "Many products need review. Add source aliases and normalization rules before candidates.",
        ],
        QUALITY_ACTION_PAUSE_SOURCE: [
            "Parser produced errors without useful products. Pause source and inspect extraction rules.",
        ],
        QUALITY_ACTION_MARK_BLOCKED: [
            "Source appears blocked or protected. Do not bypass protection; mark blocked or use supplier file workflow.",
        ],
    }
    return mapping.get(action, [])


def source_quality_report_dict(report: SourceQualityReport) -> dict[str, Any]:
    return report.model_dump(mode="json")


def _summary_problems(summary: dict) -> list[str]:
    problems: list[str] = []
    if summary.get("validation_error"):
        problems.append(str(summary["validation_error"]))
    for item in summary.get("parse_errors") or []:
        problems.append(str(item))
    for item in summary.get("parserProblems") or summary.get("parser_problems") or []:
        problems.append(str(item))
    return problems


def _trust_level(params: dict) -> SourceTrustLevel:
    raw = params.get("trustLevel") or params.get("trust_level") or SourceTrustLevel.NORMAL.value
    try:
        return SourceTrustLevel(str(raw).upper())
    except ValueError:
        return SourceTrustLevel.NORMAL


def _source_code(source: Any) -> str | None:
    name = getattr(source, "name", None)
    return str(name).lower().replace(" ", "_") if name else None


def _source_name(source: Any, params: dict) -> str | None:
    return params.get("displayName") or params.get("source_name") or getattr(source, "name", None)


def _unique(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _int(value: Any, fallback: int) -> int:
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _problem_code(problem: str) -> str:
    text = str(problem).lower()
    if "unit" in text or "единиц" in text:
        return "unit_mapping"
    if "region" in text or "регион" in text:
        return "region_mapping"
    if "category" in text or "категор" in text:
        return "category_mapping"
    if "blocked" in text or "captcha" in text:
        return "source_blocked"
    return "parser_problem"


def _get(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None
