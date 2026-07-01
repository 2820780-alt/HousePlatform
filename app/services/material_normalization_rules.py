from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class DirectionNormalizationRule:
    direction_code: str
    title: str
    key_characteristics: tuple[str, ...]
    required_fields: tuple[str, ...]
    units: tuple[str, ...]
    synonyms: dict[str, str]
    auto_checks: tuple[str, ...]
    needs_review_conditions: tuple[str, ...]
    ignored_candidate_conditions: tuple[str, ...]


@dataclass
class NormalizedMaterialTitle:
    original_title: str
    normalized_title: str
    search_title: str
    direction_code: str | None = None
    direction_title: str | None = None
    normalized_unit: str | None = None
    normalized_availability: str | None = None
    normalized_region: str | None = None
    normalized_price: Decimal | None = None
    removed_tokens: list[str] = field(default_factory=list)
    preserved_tokens: list[str] = field(default_factory=list)
    synonyms_applied: list[str] = field(default_factory=list)
    extracted: dict[str, Any] = field(default_factory=dict)
    needs_review_reasons: list[str] = field(default_factory=list)
    ignored_candidate_reasons: list[str] = field(default_factory=list)

    @property
    def ignored_candidate_status(self) -> str | None:
        return "ignored_candidate" if self.ignored_candidate_reasons else None

    def model_dump(self) -> dict[str, Any]:
        return {
            "original_title": self.original_title,
            "normalized_title": self.normalized_title,
            "search_title": self.search_title,
            "direction_code": self.direction_code,
            "direction_title": self.direction_title,
            "normalized_unit": self.normalized_unit,
            "normalized_availability": self.normalized_availability,
            "normalized_region": self.normalized_region,
            "normalized_price": str(self.normalized_price) if self.normalized_price is not None else None,
            "removed_tokens": self.removed_tokens,
            "preserved_tokens": self.preserved_tokens,
            "synonyms_applied": self.synonyms_applied,
            "extracted": self.extracted,
            "needs_review_reasons": self.needs_review_reasons,
            "ignored_candidate_reasons": self.ignored_candidate_reasons,
            "ignored_candidate_status": self.ignored_candidate_status,
        }


PROMO_TOKENS = (
    "акция",
    "хит",
    "новинка",
    "выгодно",
    "дешевле",
    "купить",
    "цена",
    "доставка",
)

SERVICE_MARKERS = (
    "аренда",
    "монтаж",
    "демонтаж",
    "услуга",
    "доставка",
    "разгрузка",
    "подъем",
    "замер",
    "установка",
)

TOOL_MARKERS = (
    "дрел",
    "дрель",
    "шуруповерт",
    "перфоратор",
    "болгарка",
    "лобзик",
    "пила циркулярная",
    "инструмент",
    "станок",
)

GARBAGE_MARKERS = (
    "подарочный сертификат",
    "купоны",
    "мерч",
    "сувенир",
)

UNIT_ALIASES = {
    "шт": "шт",
    "штука": "шт",
    "штуки": "шт",
    "м2": "м²",
    "м²": "м²",
    "кв.м": "м²",
    "кв м": "м²",
    "m2": "м²",
    "м3": "м³",
    "м³": "м³",
    "куб.м": "м³",
    "куб м": "м³",
    "m3": "м³",
    "пог.м": "пог. м",
    "пог м": "пог. м",
    "м.п.": "пог. м",
    "пм": "пог. м",
    "м": "м",
    "кг": "кг",
    "т": "т",
    "л": "л",
    "уп": "упаковка",
    "уп.": "упаковка",
    "упак": "упаковка",
    "упаковка": "упаковка",
    "подд": "поддон",
    "поддон": "поддон",
    "рул": "рулон",
    "рулон": "рулон",
    "лист": "лист",
    "бухта": "бухта",
}

AVAILABILITY_ALIASES = {
    "да": "in_stock",
    "есть": "in_stock",
    "в наличии": "in_stock",
    "наличие": "in_stock",
    "под заказ": "on_order",
    "заказ": "on_order",
    "нет": "out_of_stock",
    "нет в наличии": "out_of_stock",
    "отсутствует": "out_of_stock",
}

GENERAL_SYNONYMS = {
    "газоблок": "газобетонный блок",
    "газосиликатный блок": "газобетонный блок",
    "газобетон блок": "газобетонный блок",
    "лотковый блок": "u-блок",
    "u block": "u-блок",
    "профлист": "профнастил",
    "осп": "osb",
    "осб": "osb",
    "гкл": "гипсокартонный лист",
    "гвл": "гипсоволокнистый лист",
    "минвата": "минеральная вата",
    "каменная вата": "базальтовая вата",
    "эппс": "xps",
    "экструдированный пенополистирол": "xps",
    "пп труба": "полипропиленовая труба",
    "пнд": "полиэтилен низкого давления",
    "саморез кровельный": "саморез с epdm шайбой",
    "водосток": "водосточная система",
}


DIRECTION_RULES: dict[str, DirectionNormalizationRule] = {
    "WALL_MATERIALS": DirectionNormalizationRule(
        direction_code="WALL_MATERIALS",
        title="Стеновые материалы",
        key_characteristics=("material_type", "size", "density", "strength", "frost_resistance", "brand"),
        required_fields=("material_type", "size", "unit"),
        units=("шт", "м³", "поддон"),
        synonyms={
            "газоблок": "газобетонный блок",
            "газосиликат": "газобетон",
            "поризованный блок": "керамический блок",
            "рядовой кирпич": "кирпич рядовой",
        },
        auto_checks=(
            "gas_concrete_volume_per_piece_m3 = length_mm * width_mm * height_mm / 1_000_000_000",
            "pcs_per_m3_calc = 1 / volume_per_piece_m3",
            "brick_size_must_not_conflict_with_category",
        ),
        needs_review_conditions=(
            "missing_size_for_block",
            "density_or_strength_conflict",
            "unknown_unit",
            "ambiguous_wall_material_type",
        ),
        ignored_candidate_conditions=("service_or_delivery_only", "decor_item_without_wall_material"),
    ),
    "ROOFING_DRAINAGE": DirectionNormalizationRule(
        direction_code="ROOFING_DRAINAGE",
        title="Кровля и водосток",
        key_characteristics=("profile", "coating", "color", "thickness", "length", "system_type"),
        required_fields=("material_type", "unit"),
        units=("м²", "пог. м", "шт", "рулон"),
        synonyms={
            "профлист": "профнастил",
            "металлочерепица": "металлочерепица",
            "водосток": "водосточная система",
            "гидроизоляция рулонная": "рулонная гидроизоляция",
        },
        auto_checks=(
            "ral_color_preserved_in_search_title",
            "coating_preserved_as_characteristic",
            "sheet_length_and_width_should_match_unit",
        ),
        needs_review_conditions=("missing_profile_or_coating_when_required", "unknown_color", "unit_area_length_conflict"),
        ignored_candidate_conditions=("roofing_service_only", "decorative_roof_accessory_without_material"),
    ),
    "LUMBER_SHEET": DirectionNormalizationRule(
        direction_code="LUMBER_SHEET",
        title="Пиломатериалы и листовые материалы",
        key_characteristics=("thickness", "width", "length", "grade", "wood_type", "sheet_type"),
        required_fields=("material_type", "size", "unit"),
        units=("м³", "м²", "шт", "лист", "пог. м"),
        synonyms={
            "осп": "osb",
            "осб": "osb",
            "доска обрезная": "обрезная доска",
            "брусок": "брусок",
        },
        auto_checks=(
            "volume_per_piece_m3 = thickness_mm * width_mm * length_m / 1_000_000",
            "price_per_m3 = price_per_piece / volume_per_piece_m3",
            "sheet_dimensions_preserved",
        ),
        needs_review_conditions=("missing_dimensions", "wood_grade_unknown", "unit_volume_piece_conflict"),
        ignored_candidate_conditions=("tool_or_consumable_for_woodworking", "furniture_item"),
    ),
    "METAL_ROLLING": DirectionNormalizationRule(
        direction_code="METAL_ROLLING",
        title="Металлопрокат",
        key_characteristics=("diameter", "profile", "wall_thickness", "steel_grade", "length", "coating"),
        required_fields=("material_type", "unit"),
        units=("м", "пог. м", "кг", "т", "шт"),
        synonyms={
            "ф": "диаметр",
            "арматура а500с": "арматура а500с",
            "проф труба": "профильная труба",
            "швеллер": "швеллер",
        },
        auto_checks=("rebar_weight_kg_per_m = diameter_mm * diameter_mm * 0.00617", "profile_size_preserved"),
        needs_review_conditions=("missing_diameter_for_rebar", "unknown_steel_grade", "price_unit_conflict"),
        ignored_candidate_conditions=("metal_cutting_service_only", "tool_or_equipment"),
    ),
    "DRY_MIXES_CHEMISTRY": DirectionNormalizationRule(
        direction_code="DRY_MIXES_CHEMISTRY",
        title="Сухие смеси и химия",
        key_characteristics=("mix_type", "packing_weight", "consumption", "layer_thickness", "base", "class"),
        required_fields=("material_type", "packing", "unit"),
        units=("кг", "упаковка", "шт", "л"),
        synonyms={
            "пескобетон": "пескобетон",
            "штукатурка гипс": "гипсовая штукатурка",
            "клей плиточный": "плиточный клей",
            "клей для газобетона": "клей для кладки газобетона",
        },
        auto_checks=(
            "packing_weight_required_for_price_comparison",
            "consumption_is_material_characteristic_only",
            "layer_thickness_required_when_consumption_depends_on_thickness",
        ),
        needs_review_conditions=("missing_packing", "unknown_consumption_unit", "ambiguous_mix_purpose"),
        ignored_candidate_conditions=("tool_for_mixing", "mixing_service"),
    ),
    "INSULATION_MEMBRANES": DirectionNormalizationRule(
        direction_code="INSULATION_MEMBRANES",
        title="Утеплители и мембраны",
        key_characteristics=("material_type", "density", "thickness", "area_per_pack", "vapor_permeability", "fire_class"),
        required_fields=("material_type", "size", "unit"),
        units=("м²", "м³", "упаковка", "рулон", "шт"),
        synonyms={
            "минвата": "минеральная вата",
            "каменная вата": "базальтовая вата",
            "эппс": "xps",
            "ветрозащита": "ветрозащитная мембрана",
            "пароизоляция": "пароизоляционная мембрана",
        },
        auto_checks=("density_preserved", "thickness_preserved", "pack_area_should_match_unit"),
        needs_review_conditions=("missing_density_for_wool", "missing_thickness", "membrane_type_unknown"),
        ignored_candidate_conditions=("insulation_install_service", "clothing_or_nonconstruction_insulation"),
    ),
    "ELECTRICAL_LIGHTING": DirectionNormalizationRule(
        direction_code="ELECTRICAL_LIGHTING",
        title="Электрика и освещение",
        key_characteristics=("cable_type", "cores", "section", "conductor_material", "fire_rating", "length"),
        required_fields=("material_type", "unit"),
        units=("м", "пог. м", "бухта", "шт"),
        synonyms={
            "ввгнг": "ввгнг",
            "пнд труба": "полиэтиленовая труба низкого давления",
            "гофра": "гофрированная труба",
            "светильник led": "светодиодный светильник",
        },
        auto_checks=("cable_core_count_and_section_preserved", "price_per_meter_or_coil_detected"),
        needs_review_conditions=("missing_cable_section", "unknown_fire_rating", "unit_meter_coil_conflict"),
        ignored_candidate_conditions=("electrical_tool", "installation_service"),
    ),
    "FASTENERS_HARDWARE": DirectionNormalizationRule(
        direction_code="FASTENERS_HARDWARE",
        title="Крепеж и метизы",
        key_characteristics=("diameter", "length", "head_type", "coating", "pack_quantity", "thread_type"),
        required_fields=("material_type", "size", "unit"),
        units=("шт", "упаковка", "кг"),
        synonyms={
            "саморез кровельный": "саморез с epdm шайбой",
            "дюбель гвоздь": "дюбель-гвоздь",
            "анк болт": "анкерный болт",
        },
        auto_checks=("diameter_and_length_preserved", "package_quantity_required_for_pack_price"),
        needs_review_conditions=("missing_diameter_or_length", "unknown_coating", "pack_quantity_unknown_for_pack_unit"),
        ignored_candidate_conditions=("fastener_tool", "mounting_service"),
    ),
    "ENGINEERING_PLUMBING_HVAC": DirectionNormalizationRule(
        direction_code="ENGINEERING_PLUMBING_HVAC",
        title="Инженерная сантехника / отопление / вентиляция",
        key_characteristics=("diameter", "pressure_class", "material", "connection_type", "thread", "flow_rate"),
        required_fields=("material_type", "size", "unit"),
        units=("шт", "м", "пог. м", "упаковка"),
        synonyms={
            "пп труба": "полипропиленовая труба",
            "пнд": "полиэтилен низкого давления",
            "метапол": "металлопластиковая труба",
            "фитинг": "фитинг",
        },
        auto_checks=("pipe_diameter_preserved", "pressure_class_preserved", "connection_type_preserved"),
        needs_review_conditions=("missing_diameter", "unknown_pressure_class", "ambiguous_pipe_or_fitting"),
        ignored_candidate_conditions=("plumbing_service_only", "tool_or_equipment"),
    ),
}


DIRECTION_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("WALL_MATERIALS", ("газобетон", "газоблок", "газосиликат", "кирпич", "керамический блок", "пеноблок")),
    ("ROOFING_DRAINAGE", ("кров", "профнастил", "профлист", "металлочереп", "водосток", "гидроизоляц")),
    ("LUMBER_SHEET", ("доска", "брус", "osb", "осп", "фанера", "плита", "лист")),
    ("METAL_ROLLING", ("арматур", "швеллер", "металлопрокат", "уголок", "труба профильная", "лист сталь")),
    ("DRY_MIXES_CHEMISTRY", ("смесь", "штукатур", "клей", "цемент", "грунтов", "шпаклев", "пескобетон")),
    ("INSULATION_MEMBRANES", ("утепл", "вата", "xps", "эппс", "мембран", "пароизоляц", "ветрозащит")),
    ("ELECTRICAL_LIGHTING", ("кабель", "провод", "гофра", "розетка", "светильник", "лампа", "щит")),
    ("FASTENERS_HARDWARE", ("саморез", "дюбель", "анкер", "болт", "гайка", "шайба", "гвозд")),
    ("ENGINEERING_PLUMBING_HVAC", ("труба", "фитинг", "радиатор", "котел", "вентиляц", "канализац", "сантех")),
)


def normalize_material_title(
    original_title: str | None,
    *,
    brand: str | None = None,
    manufacturer: str | None = None,
    category: str | None = None,
    unit: str | None = None,
    price: Any = None,
    availability: str | None = None,
    region: str | None = None,
    city: str | None = None,
) -> NormalizedMaterialTitle:
    original = (original_title or "").strip()
    base = _normalize_text(original)
    preserved_tokens = _extract_preserved_tokens(base)
    text, removed_tokens = _remove_noise_tokens(base)
    text, brand_removed = _remove_repeated_named_value(text, brand)
    if not brand_removed:
        text, brand_removed = _remove_repeated_named_value(text, manufacturer)
    removed_tokens.extend(brand_removed)

    text = _normalize_size_separators(text)
    text = _normalize_diameter_marker(text)
    text, synonyms_applied = _apply_synonyms(text, GENERAL_SYNONYMS)
    direction_code = detect_direction(" ".join(filter(None, [text, category])))
    direction_rule = DIRECTION_RULES.get(direction_code or "")
    if direction_rule:
        text, direction_synonyms = _apply_synonyms(text, direction_rule.synonyms)
        synonyms_applied.extend(direction_synonyms)

    text = _collapse_spaces(text)
    search_title = _build_search_title(text)
    extracted = _extract_characteristic_hints(search_title)
    normalized_unit = normalize_unit(unit)
    normalized_availability = normalize_availability(availability)
    normalized_region = normalize_region(region, city)
    normalized_price = normalize_price(price)
    needs_review = _collect_needs_review(
        direction_rule=direction_rule,
        extracted=extracted,
        unit=normalized_unit,
        region=normalized_region,
    )
    ignored = _collect_ignored_reasons(search_title)

    return NormalizedMaterialTitle(
        original_title=original,
        normalized_title=text,
        search_title=search_title,
        direction_code=direction_rule.direction_code if direction_rule else None,
        direction_title=direction_rule.title if direction_rule else None,
        normalized_unit=normalized_unit,
        normalized_availability=normalized_availability,
        normalized_region=normalized_region,
        normalized_price=normalized_price,
        removed_tokens=removed_tokens,
        preserved_tokens=preserved_tokens,
        synonyms_applied=synonyms_applied,
        extracted=extracted,
        needs_review_reasons=needs_review,
        ignored_candidate_reasons=ignored,
    )


def normalize_unit(value: str | None) -> str | None:
    if not value:
        return None
    text = _normalize_text(value)
    return UNIT_ALIASES.get(text, text)


def normalize_availability(value: str | None) -> str | None:
    if not value:
        return None
    text = _normalize_text(value)
    return AVAILABILITY_ALIASES.get(text, text)


def normalize_region(region: str | None, city: str | None = None) -> str | None:
    parts = [_normalize_text(part) for part in (region, city) if part and str(part).strip()]
    return ", ".join(parts) if parts else None


def normalize_price(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    if not text:
        return None
    for token in ("rub", "руб", "р.", "₽"):
        text = text.lower().replace(token, "")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def detect_direction(value: str | None) -> str | None:
    text = _normalize_text(value or "")
    for direction_code, markers in DIRECTION_MARKERS:
        if any(marker in text for marker in markers):
            return direction_code
    return None


def get_direction_rule(direction_code: str) -> DirectionNormalizationRule | None:
    return DIRECTION_RULES.get(direction_code)


def get_all_direction_rules() -> list[DirectionNormalizationRule]:
    return list(DIRECTION_RULES.values())


def get_normalization_profile_snapshot() -> dict[str, Any]:
    return {
        "version": "MODULE_01_NORMALIZATION_RULES_V1",
        "pipeline_boundary": "Rules normalize raw source data into candidates; they do not create ACTIVE Material.",
        "title_flow": "original_title -> normalized_title -> search_title",
        "search_title_preserves": [
            "size",
            "density",
            "strength",
            "grade",
            "series",
            "color",
            "coating",
            "article",
        ],
        "removed_noise_tokens": list(PROMO_TOKENS),
        "general_synonyms": GENERAL_SYNONYMS,
        "unit_aliases": UNIT_ALIASES,
        "availability_aliases": AVAILABILITY_ALIASES,
        "ignored_candidate_markers": {
            "services": list(SERVICE_MARKERS),
            "tools": list(TOOL_MARKERS),
            "garbage": list(GARBAGE_MARKERS),
        },
        "direction_rules": [asdict(rule) for rule in get_all_direction_rules()],
    }


def get_source_normalization_rule_specs() -> list[dict[str, Any]]:
    return [
        {
            "rule_code": "normalize_material_title_flow",
            "target": "name",
            "transform": "original_title_to_normalized_title_to_search_title",
            "priority": 10,
            "confidence": Decimal("0.90"),
            "status": "ACTIVE",
        },
        {
            "rule_code": "remove_promo_noise_from_title",
            "target": "name",
            "pattern": "|".join(PROMO_TOKENS),
            "replacement": "",
            "priority": 20,
            "confidence": Decimal("0.90"),
            "status": "ACTIVE",
        },
        {
            "rule_code": "preserve_material_identity_tokens_in_search_title",
            "target": "name",
            "transform": "preserve_size_density_strength_grade_series_color_coating_article",
            "priority": 30,
            "confidence": Decimal("0.95"),
            "status": "ACTIVE",
        },
        {
            "rule_code": "normalize_unit_aliases",
            "target": "unit",
            "transform": "unit_aliases_to_canonical_units",
            "priority": 40,
            "confidence": Decimal("0.90"),
            "status": "ACTIVE",
        },
        {
            "rule_code": "flag_services_tools_and_garbage_candidates",
            "target": "category",
            "transform": "ignored_candidate_when_not_material_data",
            "priority": 50,
            "confidence": Decimal("0.80"),
            "status": "ACTIVE",
        },
        {
            "rule_code": "direction_specific_normalization",
            "target": "category",
            "transform": "apply_first_wave_direction_rules",
            "priority": 60,
            "confidence": Decimal("0.80"),
            "status": "ACTIVE",
        },
    ]


def _normalize_text(value: str) -> str:
    text = str(value).lower().replace("ё", "е").replace("\xa0", " ")
    text = text.replace("×", "x").replace("х", "x")
    text = text.replace("м.кв", "м2").replace("кв.м", "м2")
    text = text.replace("м.куб", "м3").replace("куб.м", "м3")
    return _collapse_spaces(text)


def _remove_noise_tokens(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    result = text
    for token in PROMO_TOKENS:
        pattern = rf"(?<!\w){re.escape(token)}(?!\w)"
        if re.search(pattern, result, flags=re.IGNORECASE):
            removed.append(token)
            result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    result = re.sub(r"[^\w\s./+№#*,-]", " ", result, flags=re.UNICODE)
    result = re.sub(r"[_]+", " ", result)
    return _collapse_spaces(result), removed


def _remove_repeated_named_value(text: str, value: str | None) -> tuple[str, list[str]]:
    if not value or not value.strip():
        return text, []
    removed: list[str] = []
    result = text
    for part in _normalize_text(value).split():
        if len(part) < 3:
            continue
        pattern = rf"(?<!\w){re.escape(part)}(?!\w)"
        if re.search(pattern, result):
            result = re.sub(pattern, " ", result)
            removed.append(part)
    return _collapse_spaces(result), removed


def _normalize_size_separators(text: str) -> str:
    result = re.sub(r"(\d)\s*[x*]\s*(\d)", r"\1x\2", text)
    result = re.sub(r"\s+мм\b", " мм", result)
    return _collapse_spaces(result)


def _normalize_diameter_marker(text: str) -> str:
    result = re.sub(r"(?<!\w)[фф]\s*(\d{1,3})(?!\w)", r"\1 мм", text)
    return _collapse_spaces(result)


def _apply_synonyms(text: str, synonyms: dict[str, str]) -> tuple[str, list[str]]:
    result = text
    applied: list[str] = []
    for source, target in sorted(synonyms.items(), key=lambda item: len(item[0]), reverse=True):
        source_norm = _normalize_text(source)
        target_norm = _normalize_text(target)
        pattern = rf"(?<!\w){re.escape(source_norm)}(?!\w)"
        if re.search(pattern, result):
            result = re.sub(pattern, target_norm, result)
            applied.append(f"{source_norm}->{target_norm}")
    return _collapse_spaces(result), applied


def _extract_preserved_tokens(text: str) -> list[str]:
    patterns = [
        r"\b\d{2,4}x\d{1,4}(?:x\d{1,4})?\b",
        r"\bd\s*\d{2,4}\b",
        r"\bb\s*\d{1,3}(?:[.,]\d)?\b",
        r"\bm\s*\d{2,4}\b",
        r"\bм\s*\d{2,4}\b",
        r"\bral\s*\d{3,4}\b",
        r"\bарт\.?\s*[\w-]+\b",
        r"\b[a-zа-я0-9-]+(?:серия|series)\s*[\w-]+\b",
        r"\b\d{1,3}(?:[.,]\d+)?\s*мм\b",
    ]
    tokens: list[str] = []
    for pattern in patterns:
        tokens.extend(match.group(0).strip() for match in re.finditer(pattern, text, flags=re.IGNORECASE))
    return list(dict.fromkeys(tokens))


def _extract_characteristic_hints(text: str) -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    size = re.search(r"\b(\d{2,4}x\d{1,4}(?:x\d{1,4})?)\b", text)
    if size:
        extracted["size"] = size.group(1)
    density = re.search(r"\bd\s*(\d{2,4})\b", text)
    if density:
        extracted["density"] = f"D{density.group(1)}"
    strength = re.search(r"\bb\s*(\d{1,3}(?:[.,]\d)?)\b", text)
    if strength:
        extracted["strength"] = f"B{strength.group(1)}"
    grade = re.search(r"\b(?:м|m)\s*(\d{2,4})\b", text)
    if grade:
        extracted["grade"] = f"M{grade.group(1)}"
    ral = re.search(r"\bral\s*(\d{3,4})\b", text)
    if ral:
        extracted["color"] = f"RAL {ral.group(1)}"
    article = re.search(r"\bарт\.?\s*([\w-]+)\b", text)
    if article:
        extracted["article"] = article.group(1)
    diameter = re.search(r"\b(\d{1,3})\s*мм\b", text)
    if diameter:
        extracted["diameter"] = f"{diameter.group(1)} мм"
    packing = re.search(r"\b(\d{1,2}(?:[.,]\d+)?)\s*(кг|л)\b", text)
    if packing:
        extracted["packing"] = f"{packing.group(1)} {packing.group(2)}"
    if any(marker in text for marker in ("газобетон", "кирпич", "профнастил", "саморез", "кабель", "труба")):
        extracted["material_type"] = True
    return extracted


def _collect_needs_review(
    *,
    direction_rule: DirectionNormalizationRule | None,
    extracted: dict[str, Any],
    unit: str | None,
    region: str | None,
) -> list[str]:
    reasons: list[str] = []
    if not direction_rule:
        reasons.append("needs_classification")
    else:
        for field_name in direction_rule.required_fields:
            if field_name == "unit" and not unit:
                reasons.append("needs_unit_review")
            elif field_name not in {"unit", "category"} and field_name not in extracted:
                reasons.append(f"missing_{field_name}")
        if unit and unit not in direction_rule.units:
            reasons.append("unit_direction_mismatch")
    if not region:
        reasons.append("needs_region_review")
    return list(dict.fromkeys(reasons))


def _collect_ignored_reasons(text: str) -> list[str]:
    reasons: list[str] = []
    if any(marker in text for marker in SERVICE_MARKERS):
        reasons.append("service_or_delivery_only")
    if any(marker in text for marker in TOOL_MARKERS):
        reasons.append("tool_product_not_material")
    if any(marker in text for marker in GARBAGE_MARKERS):
        reasons.append("garbage_or_non_material_product")
    return reasons


def _build_search_title(text: str) -> str:
    return _collapse_spaces(text)


def _collapse_spaces(value: str) -> str:
    return " ".join(str(value).split())
