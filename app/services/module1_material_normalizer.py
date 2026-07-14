from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from app.services.material_normalization_rules import normalize_material_title as legacy_normalize_material_title
from app.services.module1_characteristic_schema_registry import CharacteristicSchemaRegistry
from app.services.module1_extraction_blueprint_registry import ExtractionBlueprintRegistry
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


GROUP_CATEGORY_HINTS: Mapping[str, str] = {
    "aerated_concrete_block": "blocks_and_bricks",
    "gypsum_board_moisture_resistant": "sheet_materials",
    "rebar": "metal_rolling",
    "ready_mix_concrete": "concrete",
    "board": "lumber",
    "metal_tile": "roofing",
    "gypsum_plaster": "dry_mixes",
    "deep_penetration_primer": "construction_chemistry",
    "porcelain_tile": "tiles",
    "mineral_wool_slab": "insulation",
}


@dataclass(frozen=True)
class NormalizedMaterialCandidate:
    normalized_title: str
    source_title: str | None
    suggested_group_code: str | None
    suggested_category: str | None
    manufacturer: str | None
    brand: str | None
    normalized_characteristics: Mapping[str, Any]
    normalized_unit: str | None
    price_hint: Decimal | None
    source_metadata: Mapping[str, Any]
    confidence: Decimal
    warnings: tuple[str, ...]
    missing_required_fields: tuple[str, ...]
    module2_missing_fields: tuple[str, ...]
    evidence: Mapping[str, Any]


@dataclass(frozen=True)
class MaterialNormalizationReport:
    candidate: NormalizedMaterialCandidate
    is_ready_for_matching: bool
    warnings: tuple[str, ...]
    missing_required_fields: tuple[str, ...]
    module2_missing_fields: tuple[str, ...]
    message: str


def normalize_raw_ingestion_item(raw_item: Module1RawIngestionItem) -> NormalizedMaterialCandidate:
    normalized_title = normalize_title(raw_item.raw_title)
    group_code = infer_material_group(raw_item)
    characteristics = normalize_characteristics(group_code, raw_item.raw_characteristics or {}, raw_item.raw_title)
    normalized_unit = UnitConversionRegistry().normalize_unit(raw_item.raw_unit)
    manufacturer, brand = _extract_manufacturer_brand(raw_item, normalized_title)
    missing_required, module2_missing = _missing_schema_fields(group_code, characteristics)
    warnings = list_normalizer_warnings(raw_item, group_code, characteristics, normalized_unit, missing_required, module2_missing)
    confidence = calculate_normalization_confidence(
        raw_item=raw_item,
        group_code=group_code,
        normalized_characteristics=characteristics,
        normalized_unit=normalized_unit,
        warnings=warnings,
        missing_required_fields=missing_required,
    )
    return NormalizedMaterialCandidate(
        normalized_title=normalized_title,
        source_title=raw_item.raw_title,
        suggested_group_code=group_code,
        suggested_category=GROUP_CATEGORY_HINTS.get(group_code or ""),
        manufacturer=manufacturer,
        brand=brand,
        normalized_characteristics=characteristics,
        normalized_unit=normalized_unit,
        price_hint=raw_item.raw_price,
        source_metadata={
            "source_id": raw_item.source_id,
            "source_code": raw_item.source_code,
            "source_type": raw_item.source_type,
            "source_url": raw_item.source_url,
            "legacy_source": raw_item.legacy_source,
            "region": raw_item.region,
            "city": raw_item.city,
            "captured_at": raw_item.captured_at,
            "observed_at": raw_item.observed_at,
        },
        confidence=confidence,
        warnings=warnings,
        missing_required_fields=missing_required,
        module2_missing_fields=module2_missing,
        evidence={
            "raw_title": raw_item.raw_title,
            "raw_category": raw_item.raw_category,
            "raw_documents": raw_item.raw_documents,
            "raw_images": raw_item.raw_images,
            "extraction_profile_reference": raw_item.extraction_profile_reference,
            "adapter_version": raw_item.adapter_version,
            "source_task_version": raw_item.source_task_version,
        },
    )


def normalize_title(raw_title: str | None) -> str:
    title = _clean_text(raw_title or "")
    if not title:
        return ""
    legacy = legacy_normalize_material_title(title)
    legacy_title = getattr(legacy, "search_title", "") or getattr(legacy, "normalized_title", "")
    cleaned = _clean_text(legacy_title or title)
    return cleaned


def extract_dimensions(text: str | None, raw_characteristics: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    normalized = _clean_text(text or "")
    chars = dict(raw_characteristics or {})
    result: dict[str, Any] = {}
    size = re.search(r"(?<!\d)(\d{1,4}(?:[.,]\d+)?)\s*x\s*(\d{1,4}(?:[.,]\d+)?)(?:\s*x\s*(\d{1,4}(?:[.,]\d+)?))?", normalized)
    if size:
        result["dimensions_mm"] = tuple(_number(part) for part in size.groups() if part)
    for field in ("length_mm", "width_mm", "height_mm", "thickness_mm", "diameter_mm"):
        if field in chars and chars[field] not in (None, ""):
            result[field] = _number(chars[field])
    return result


def normalize_characteristics(
    group_code: str | None,
    raw_characteristics: Mapping[str, Any] | None,
    raw_title: str | None = None,
) -> Mapping[str, Any]:
    title = _clean_text(raw_title or "")
    raw = dict(raw_characteristics or {})
    extracted = dict(extract_dimensions(title, raw))
    values: dict[str, Any] = {key: _plain_value(value) for key, value in raw.items() if value not in (None, "")}
    dimensions = extracted.get("dimensions_mm")

    if group_code == "aerated_concrete_block":
        _apply_dimensions(values, dimensions, ("length_mm", "width_mm", "height_mm"))
        if density := _match(r"\bd\s*(\d{2,4})\b", title):
            values.setdefault("density_class", f"D{density}")
        if strength := _match(r"\bb\s*(\d{1,3}(?:[.,]\d+)?)\b", title):
            values.setdefault("strength_class", f"B{strength.replace(',', '.')}")
    elif group_code == "gypsum_board_moisture_resistant":
        _apply_dimensions(values, dimensions, ("length_mm", "width_mm", "thickness_mm"))
        if "гклв" in title or "влаг" in title:
            values.setdefault("board_type", "moisture_resistant")
        elif "гкл" in title:
            values.setdefault("board_type", "standard")
    elif group_code == "rebar":
        if diameter := _match(r"(?:арматура\s*)?(?:а\d{3}[сc]?\s*)?(\d{1,2}(?:[.,]\d+)?)\s*мм\b", title):
            values.setdefault("diameter_mm", _number(diameter))
        if steel_class := _match(r"\b[аa]\s?(\d{3})\s*([сc])?\b", title):
            suffix = _match(r"\b[аa]\s?\d{3}\s*([сc])\b", title) or ""
            values.setdefault("steel_class", f"A{steel_class}{suffix.upper().replace('С', 'C')}")
    elif group_code == "ready_mix_concrete":
        if concrete_class := _match(r"\bb\s*(\d{1,3}(?:[.,]\d+)?)\b", title):
            values.setdefault("concrete_class", f"B{concrete_class.replace(',', '.')}")
        if mobility := _match(r"\b[пp]\s*(\d)\b", title):
            values.setdefault("mobility_class", f"P{mobility}")
        if frost := _match(r"\bf\s*(\d{2,3})\b", title):
            values.setdefault("frost_resistance", f"F{frost}")
        if water := _match(r"\bw\s*(\d{1,2})\b", title):
            values.setdefault("water_resistance", f"W{water}")
        values.setdefault("unit", "m3")
    elif group_code == "board":
        _apply_dimensions(values, dimensions, ("thickness_mm", "width_mm", "length_mm"))
    elif group_code == "metal_tile":
        if thickness := _match(r"(\d(?:[.,]\d+)?)\s*мм", title):
            values.setdefault("metal_thickness_mm", _number(thickness))
        if coating := _match_original(r"покрытие\s+([A-Za-zА-Яа-я0-9_-]+)", raw_title or ""):
            values.setdefault("coating", coating)

    return _filter_to_schema(group_code, values)


def infer_material_group(raw_item: Module1RawIngestionItem) -> str | None:
    text = _clean_text(" ".join(filter(None, [raw_item.raw_title, raw_item.raw_category])))
    markers = (
        ("aerated_concrete_block", ("газоблок", "газобетон", "d500", "d400", "d600")),
        ("gypsum_board_moisture_resistant", ("гклв", "гкл", "гипсокартон", "drywall")),
        ("rebar", ("арматура", "а500", "a500", "a400")),
        ("ready_mix_concrete", ("бетон", "b25", "b30", "п4", "p4")),
        ("board", ("доска", "брус", "lumber")),
        ("metal_tile", ("металлочерепица", "metal tile")),
        ("gypsum_plaster", ("штукатурка", "сухая смесь")),
        ("deep_penetration_primer", ("грунтовка", "primer")),
        ("porcelain_tile", ("керамогранит", "плитка")),
        ("mineral_wool_slab", ("минвата", "минеральная вата", "утеплитель")),
    )
    for group_code, group_markers in markers:
        if any(marker in text for marker in group_markers):
            return group_code
    return None


def build_normalization_report(raw_item: Module1RawIngestionItem) -> MaterialNormalizationReport:
    candidate = normalize_raw_ingestion_item(raw_item)
    ready = bool(candidate.suggested_group_code and not candidate.missing_required_fields)
    return MaterialNormalizationReport(
        candidate=candidate,
        is_ready_for_matching=ready,
        warnings=candidate.warnings,
        missing_required_fields=candidate.missing_required_fields,
        module2_missing_fields=candidate.module2_missing_fields,
        message="Candidate is ready for M1-9 matching." if ready else "Candidate needs normalization review before matching.",
    )


def calculate_normalization_confidence(
    *,
    raw_item: Module1RawIngestionItem,
    group_code: str | None,
    normalized_characteristics: Mapping[str, Any],
    normalized_unit: str | None,
    warnings: tuple[str, ...],
    missing_required_fields: tuple[str, ...],
) -> Decimal:
    score = Decimal("0.35")
    if raw_item.raw_title:
        score += Decimal("0.15")
    if group_code:
        score += Decimal("0.20")
    if normalized_characteristics:
        score += Decimal("0.15")
    if normalized_unit:
        score += Decimal("0.05")
    if raw_item.source_code:
        score += Decimal("0.05")
    score -= Decimal("0.05") * len(missing_required_fields)
    score -= Decimal("0.03") * len(warnings)
    return max(Decimal("0.00"), min(Decimal("0.99"), score.quantize(Decimal("0.01"))))


def list_normalizer_warnings(
    raw_item: Module1RawIngestionItem,
    group_code: str | None,
    normalized_characteristics: Mapping[str, Any],
    normalized_unit: str | None,
    missing_required_fields: tuple[str, ...],
    module2_missing_fields: tuple[str, ...],
) -> tuple[str, ...]:
    warnings: list[str] = list(raw_item.warnings)
    if not raw_item.raw_title:
        warnings.append("raw_title is missing")
    if not group_code:
        warnings.append("material group is only unknown candidate")
    if raw_item.raw_unit and normalized_unit is None:
        warnings.append(f"unit is not recognized: {raw_item.raw_unit}")
    for field in missing_required_fields:
        warnings.append(f"missing required field: {field}")
    for field in module2_missing_fields:
        warnings.append(f"module2 field missing: {field}")
    if group_code == "aerated_concrete_block" and "pieces_per_m3" not in normalized_characteristics:
        warnings.append("recommended field missing: pieces_per_m3")
    if group_code == "metal_tile" and any("screw" in key for key in normalized_characteristics):
        warnings.append("fastener consumption must stay a technology hint, not material property")
    return tuple(dict.fromkeys(warnings))


def _missing_schema_fields(group_code: str | None, characteristics: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not group_code:
        return tuple(), tuple()
    schema = CharacteristicSchemaRegistry()
    required = schema.get_required_characteristics(group_code)
    module2 = schema.get_module2_required_characteristics(group_code)
    missing_required = tuple(field for field in required if field not in characteristics)
    missing_module2 = tuple(field for field in module2 if field not in characteristics)
    blueprint = ExtractionBlueprintRegistry().get_blueprint(group_code)
    if blueprint:
        missing_required = tuple(dict.fromkeys(missing_required + tuple(field for field in blueprint.required_fields if field not in characteristics)))
    return missing_required, missing_module2


def _filter_to_schema(group_code: str | None, values: Mapping[str, Any]) -> Mapping[str, Any]:
    if not group_code:
        return dict(values)
    schema = CharacteristicSchemaRegistry().get_schema(group_code)
    allowed = set(schema.all_characteristic_codes() if schema else frozenset(values.keys()))
    if group_code == "metal_tile":
        allowed.add("coating")
    return {key: value for key, value in values.items() if key in allowed}


def _extract_manufacturer_brand(raw_item: Module1RawIngestionItem, normalized_title: str) -> tuple[str | None, str | None]:
    manufacturer = raw_item.raw_manufacturer
    brand = None
    for token in ("bonolit", "knauf", "vkblock", "satin"):
        if token in normalized_title:
            brand = token.upper() if token != "satin" else "Satin"
            break
    return manufacturer, brand


def _clean_text(value: str) -> str:
    text = str(value or "").lower().replace("ё", "е").replace("×", "x").replace("х", "x")
    text = re.sub(r"[;:|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _apply_dimensions(values: dict[str, Any], dimensions: Any, fields: tuple[str, ...]) -> None:
    if not isinstance(dimensions, tuple):
        return
    for field, value in zip(fields, dimensions, strict=False):
        values.setdefault(field, value)


def _match(pattern: str, text: str) -> str | None:
    found = re.search(pattern, text, flags=re.IGNORECASE)
    return found.group(1) if found else None


def _match_original(pattern: str, text: str) -> str | None:
    found = re.search(pattern, text, flags=re.IGNORECASE)
    return found.group(1) if found else None


def _number(value: Any) -> Decimal:
    return Decimal(str(value).replace(",", ".").strip())


def _plain_value(value: Any) -> Any:
    if isinstance(value, Mapping) and "value" in value:
        return value["value"]
    return value
