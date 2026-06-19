from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog_product import CatalogProduct
from app.models.material_category import MaterialCategory
from app.services.material_taxonomy import TaxonomyPath, infer_baucenter_taxonomy


@dataclass(frozen=True)
class CategoryPath:
    parent: str
    category: str
    subcategory: str | None = None


@dataclass(frozen=True)
class MaterialClassification:
    canonical_name: str
    category_path: CategoryPath | None
    brand: str | None = None
    manufacturer: str | None = None
    region: str | None = None
    confidence: float = 0.75
    rule_code: str = "fallback"


CITY_FORMS = {
    "краснодаре": "Краснодар",
    "москве": "Москва",
    "санкт-петербурге": "Санкт-Петербург",
    "ростове-на-дону": "Ростов-на-Дону",
    "новороссийске": "Новороссийск",
    "сочи": "Сочи",
}


KNauf_REVIEW_MARKERS = [
    "аквамарин",
    "сапфир",
    "гипсокартон",
    "гипсоволокнист",
    "суперлист",
    "суперпол",
    "аквапанель",
    "цементная плита",
    "профиль",
    "профили",
    "огнезащитные материалы",
]


def needs_specification_review(product: CatalogProduct, classification: MaterialClassification) -> bool:
    text = f"{product.raw_name or ''} {product.raw_category or ''} {product.external_url or ''}".lower()
    brand_text = f"{product.raw_brand or ''} {product.raw_manufacturer or ''}".lower()
    if "knauf" in brand_text or "кнауф" in text:
        if classification.rule_code == "drywall_profile":
            return not _has_explicit_size_marker(text)
        if any(marker in text for marker in KNauf_REVIEW_MARKERS):
            return not _has_dimension_marker(text)
    if classification.rule_code == "drywall_profile":
        return not _has_explicit_size_marker(text)
    return False


def classify_catalog_product(product: CatalogProduct) -> MaterialClassification:
    raw_name = _clean_text(product.raw_name)
    text = f"{raw_name} {product.raw_category or ''} {product.external_url or ''}".lower()
    name_without_region, region = _extract_region(raw_name)
    taxonomy_path = infer_baucenter_taxonomy(product.raw_name, product.raw_category, product.external_url)

    if product.raw_category and taxonomy_path:
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=_taxonomy_category_path(taxonomy_path),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.88,
            rule_code="baucenter_taxonomy",
        )

    if _has_any(text, ["vkblok", "bonolit", "газобетон", "газобетона", "газобетонный", "стеновой блок"]):
        size = _extract_size(text)
        density = _extract_density(text)
        if size:
            canonical = f"Газобетонный блок {size}"
            if density:
                canonical = f"{canonical} {density}"
        else:
            canonical = _remove_brand_and_noise(name_without_region, ["вкблок"])
        return MaterialClassification(
            canonical_name=canonical,
            category_path=CategoryPath("Стеновые материалы", "Газобетонные блоки"),
            brand=product.raw_brand or ("Bonolit" if "bonolit" in text else "ВКБлок"),
            manufacturer=product.raw_manufacturer or ("Bonolit" if "bonolit" in text else "ВКБлок"),
            region=region or product.region,
            confidence=0.95 if size else 0.85,
            rule_code="wall_material_aerated_concrete",
        )

    if _has_any(text, ["клей", "klej", "kley", "кладочная смесь", "smes suhaya", "шпатлев", "штукатур"]):
        canonical = _normalize_mix_name(name_without_region)
        if _has_any(text, ["шпатлев", "штукатур"]):
            category = "Шпатлевки и штукатурки"
        elif _has_any(text, ["газобетон", "ячеистого бетона", "kladki"]):
            category = "Клеи для кладки"
        else:
            category = "Сухие строительные смеси"
        return MaterialClassification(
            canonical_name=canonical,
            category_path=CategoryPath("Сухие смеси", category),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.84,
            rule_code="dry_mix",
        )

    if _has_any(text, ["lampa-lon", "лампа лон", "лампа накаливания"]):
        canonical = _normalize_lamp_name(name_without_region)
        return MaterialClassification(
            canonical_name=canonical,
            category_path=CategoryPath("Электротовары", "Освещение", "Лампы накаливания"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.9,
            rule_code="electrical_incandescent_lamp",
        )

    if _has_any(text, ["kabel-vvg", "ввг", "кабель"]):
        return MaterialClassification(
            canonical_name=_normalize_cable_name(name_without_region),
            category_path=CategoryPath("Электротовары", "Кабель и провод", "Силовой кабель"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.86,
            rule_code="electrical_power_cable",
        )

    if _has_any(text, ["штроборез"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Инструмент", "Ручной инструмент"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.82,
            rule_code="tool_wall_chaser",
        )

    if _has_any(text, ["профиль", "профили", "profili metallicheskie"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Материалы для сухого строительства", "Профили для гипсокартона"),
            brand=product.raw_brand or "Knauf",
            manufacturer=product.raw_manufacturer or "Knauf",
            region=region or product.region,
            confidence=0.7,
            rule_code="drywall_profile",
        )

    if _has_any(text, ["masterprof", "проклад", "смесител", "кранбукс", "сантех"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Сантехника", "Комплектующие для смесителей"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.84,
            rule_code="plumbing_mixer_parts",
        )

    if _has_any(text, ["аквапанель", "aquapanel", "цементная плита"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Листовые и плитные материалы", "Цементные плиты"),
            brand=product.raw_brand or "Knauf",
            manufacturer=product.raw_manufacturer or "Knauf",
            region=region or product.region,
            confidence=0.86,
            rule_code="sheet_cement_board",
        )

    if _has_any(text, ["гипсоволокнист", "гвл", "суперлист", "суперпол"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Листовые и плитные материалы", "Гипсоволокнистые листы"),
            brand=product.raw_brand or "Knauf",
            manufacturer=product.raw_manufacturer or "Knauf",
            region=region or product.region,
            confidence=0.86,
            rule_code="sheet_gvl",
        )

    if _has_any(text, ["гипсокартон", "gipsokarton", "гипсоплита", "сайлентборд", "файерборд"]):
        return MaterialClassification(
            canonical_name=_normalize_sheet_name(name_without_region),
            category_path=CategoryPath("Листовые и плитные материалы", "Гипсовые листовые материалы"),
            brand=product.raw_brand or "Knauf",
            manufacturer=product.raw_manufacturer or "Knauf",
            region=region or product.region,
            confidence=0.86,
            rule_code="sheet_gypsum_material",
        )

    if _has_any(text, ["фанера", "fanera"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Листовые и плитные материалы", "Фанера"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.86,
            rule_code="sheet_plywood",
        )

    if _has_any(text, ["хдф", "hdf"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Листовые и плитные материалы", "ХДФ"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.84,
            rule_code="sheet_hdf",
        )

    if _has_any(text, ["osb", "осп", "осб"]):
        return MaterialClassification(
            canonical_name=_normalize_board_name(name_without_region, "OSB"),
            category_path=CategoryPath("Листовые и плитные материалы", "OSB"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.86,
            rule_code="sheet_osb",
        )

    if _has_any(text, ["shinglas", "гибкая черепица", "cherepitsa"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Кровля", "Гибкая черепица"),
            brand=product.raw_brand or "ТЕХНОНИКОЛЬ",
            manufacturer=product.raw_manufacturer or "ТЕХНОНИКОЛЬ",
            region=region or product.region,
            confidence=0.84,
            rule_code="roof_flexible_shingles",
        )

    if _has_any(text, ["каменная вата", "rocklight", "техноблок", "teploizolyaciya", "uteplit"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Теплоизоляция", "Каменная вата"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.82,
            rule_code="thermal_insulation_stone_wool",
        )

    if _has_any(text, ["xps", "экструзион", "carbon eco"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Теплоизоляция", "XPS"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.82,
            rule_code="thermal_insulation_xps",
        )

    if _has_any(text, ["fasad", "сайдинг", "saiding", "фасадные панели", "декоративная система", "soffit", "софит", "отлив"]):
        facade_category = "Фасадные материалы"
        facade_subcategory = None
        if _has_any(text, ["отлив", "dobornye-elementy-fasada"]):
            facade_category = "Доборные элементы"
        elif _has_any(text, ["сайдинг", "saiding"]):
            facade_category = "Сайдинг"
        elif _has_any(text, ["фасадные панели", "panel", "панел"]):
            facade_category = "Фасадные панели"
        elif _has_any(text, ["софит", "soffit"]):
            facade_category = "Софиты"
        elif _has_any(text, ["декоративная система", "dekorativ"]):
            facade_category = "Декоративные фасадные системы"
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Фасады", facade_category, facade_subcategory),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.78,
            rule_code="facade_material",
        )

    if _has_any(text, ["snegozader", "кровельн", "dobornye-elementy", "элементы кровли"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Кровля", "Комплектующие кровли"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.78,
            rule_code="roof_accessories",
        )

    if _has_any(text, ["саморез", "ankery", "анкер", "krepezh", "крепеж"]):
        if _has_any(text, ["прессшайб", "pressshayb"]):
            category_path = CategoryPath("Крепеж", "Саморезы", "С прессшайбой")
        elif _has_any(text, ["саморез"]):
            category_path = CategoryPath("Крепеж", "Саморезы")
        else:
            category_path = CategoryPath("Крепеж", "Строительный крепеж")
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=category_path,
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.78,
            rule_code="fasteners",
        )

    if _has_any(text, ["печь-каменка", "печи для бани", "банн", "саун", "kamenka"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Бани и сауны", "Печи"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.84,
            rule_code="bath_sauna_stove",
        )

    if _has_any(text, ["дрел", "шуруповерт", "перфоратор", "электролобзик", "инструмент", "пила", "ушм"]):
        return MaterialClassification(
            canonical_name=_normalize_product_line_name(name_without_region),
            category_path=CategoryPath("Инструмент", "Электроинструмент"),
            brand=product.raw_brand,
            manufacturer=product.raw_manufacturer,
            region=region or product.region,
            confidence=0.72,
            rule_code="power_tool",
        )

    return MaterialClassification(
        canonical_name=name_without_region,
        category_path=None,
        brand=product.raw_brand,
        manufacturer=product.raw_manufacturer,
        region=region or product.region,
        confidence=0.5,
        rule_code="fallback",
    )


async def apply_classification_categories(
    db: AsyncSession,
    classification: MaterialClassification,
) -> tuple[MaterialCategory | None, MaterialCategory | None]:
    if not classification.category_path:
        return None, None
    parent = await _get_or_create_category(db, classification.category_path.parent, None, 0)
    category = await _get_or_create_category(db, classification.category_path.category, parent, 1)
    subcategory = None
    if classification.category_path.subcategory:
        subcategory = await _get_or_create_category(db, classification.category_path.subcategory, category, 2)
    return category, subcategory


async def _get_or_create_category(
    db: AsyncSession,
    name: str,
    parent: MaterialCategory | None,
    level: int,
) -> MaterialCategory:
    slug = _slugify(name)
    result = await db.execute(select(MaterialCategory).where(MaterialCategory.slug == slug))
    category = result.scalar_one_or_none()
    if category:
        return category
    category = MaterialCategory(
        parent_id=parent.id if parent else None,
        name=name,
        slug=slug,
        level=level,
    )
    db.add(category)
    await db.flush()
    return category


def _extract_region(name: str) -> tuple[str, str | None]:
    match = re.search(r"\s+в\s+([А-Яа-яЁё-]+)\s*$", name)
    if not match:
        return name, None
    city_raw = match.group(1).lower()
    city = CITY_FORMS.get(city_raw, match.group(1))
    return name[: match.start()].strip(), city


def _taxonomy_category_path(path: TaxonomyPath) -> CategoryPath:
    return CategoryPath(path.section, path.category, path.product_type)


def _extract_size(text: str) -> str | None:
    match = re.search(r"(\d{3,4})\s*[xх*]\s*(\d{2,4})\s*[xх*]\s*(\d{2,4})", text, re.IGNORECASE)
    if not match:
        return None
    return f"{match.group(1)}*{match.group(2)}*{match.group(3)}"


def _extract_density(text: str) -> str | None:
    match = re.search(r"\b(d\s*\d{3})\b", text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper().replace(" ", "")


def _has_dimension_marker(text: str) -> bool:
    return bool(
        re.search(r"\d+\s*[xх*]\s*\d+", text, re.IGNORECASE)
        or re.search(r"\b\d+(?:[,.]\d+)?\s*(?:мм|mm|м2|m2)\b", text, re.IGNORECASE)
        or re.search(r"\b(?:пн|пс|пп|ппу|шн)-?\s*\d+", text, re.IGNORECASE)
    )


def _has_explicit_size_marker(text: str) -> bool:
    return bool(
        re.search(r"\d+\s*[xх*]\s*\d+", text, re.IGNORECASE)
        or re.search(r"\b\d+(?:[,.]\d+)?\s*(?:мм|mm)\b", text, re.IGNORECASE)
        or "толщина" in text
        or "длина" in text
        or "ширина" in text
    )


def _normalize_lamp_name(name: str) -> str:
    normalized = _remove_brand_and_noise(name, [])
    watt = re.search(r"(\d+)\s*Вт", normalized, re.IGNORECASE)
    kelvin = re.search(r"(\d{4})\s*К", normalized, re.IGNORECASE)
    socket = re.search(r"\b(E\d{2})\b", normalized, re.IGNORECASE)
    parts = ["Лампа накаливания ЛОН"]
    if watt:
        parts.append(f"{watt.group(1)}Вт")
    if socket:
        parts.append(socket.group(1).upper())
    if kelvin:
        parts.append(f"{kelvin.group(1)}К")
    return " ".join(parts) if len(parts) > 1 else normalized


def _normalize_cable_name(name: str) -> str:
    cleaned = _remove_brand_and_noise(name, [])
    mark = re.search(r"(ВВГ(?:нг)?(?:\([А-ЯA-Z]\))?(?:-?П)?(?:-?LS)?)", cleaned, re.IGNORECASE)
    section = re.search(r"(\d+\s*[xх]\s*\d+(?:[,.]\d+)?)", cleaned, re.IGNORECASE)
    voltage = re.search(r"\(?\s*(0[,.]66|1)\s*кВ\s*\)?", cleaned, re.IGNORECASE)
    parts = ["Кабель"]
    if mark:
        parts.append(_format_cable_mark(mark.group(1)))
    if section:
        parts.append(section.group(1).replace("х", "x").replace(",", ".").replace(" ", ""))
    if voltage:
        parts.append(f"{voltage.group(1).replace(',', '.')}кВ")
    return " ".join(parts) if len(parts) > 1 else cleaned


def _normalize_mix_name(name: str) -> str:
    cleaned = _remove_brand_and_noise(name, ["вкблок"])
    mark = re.search(r"\b(ВК-\d{2,4})\b", cleaned, re.IGNORECASE)
    if _has_any(cleaned.lower(), ["клей", "клад"]):
        base = "Клей для кладки газобетона"
    elif _has_any(cleaned.lower(), ["шпатлев"]):
        base = "Шпатлевка цементная"
    elif _has_any(cleaned.lower(), ["штукатур"]):
        base = "Штукатурка"
    else:
        base = "Сухая строительная смесь"
    return f"{base} {mark.group(1).upper()}" if mark else base


def _normalize_sheet_name(name: str) -> str:
    cleaned = _remove_brand_and_noise(name, ["knauf", "кнауф"])
    lower = cleaned.lower()
    if "аквамарин" in lower:
        return "Гипсокартон влагостойкий Аквамарин"
    if "сапфир" in lower:
        return "Гипсокартон Сапфир"
    if "сайлентборд" in lower:
        return "Гипсокартон звукоизоляционный Сайлентборд"
    if "файерборд" in lower:
        return "Плита негорючая Файерборд"
    if "гипсоплита" in lower and "влаг" in lower:
        return "Гипсоплита влагостойкая"
    if "гипсоплита" in lower:
        return "Гипсоплита стандарт"
    return cleaned


def _normalize_board_name(name: str, board_type: str) -> str:
    cleaned = _remove_brand_and_noise(name, [])
    size = _extract_size(cleaned.lower())
    thickness = re.search(r"(\d{1,3})\s*мм", cleaned, re.IGNORECASE)
    parts = [board_type]
    if size:
        parts.append(size)
    elif thickness:
        parts.append(f"{thickness.group(1)}мм")
    return " ".join(parts)


def _normalize_product_line_name(name: str) -> str:
    cleaned = _remove_brand_and_noise(name, ["технониколь", "grand line", "кнауф", "вкблок"])
    cleaned = re.sub(r"\bгост\s*[\d\-: ]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bфинальная распродажа\b", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" -")


def _format_cable_mark(value: str) -> str:
    formatted = value.replace(" ", "")
    formatted = re.sub(r"ввг", "ВВГ", formatted, flags=re.IGNORECASE)
    formatted = re.sub(r"нг", "нг", formatted, flags=re.IGNORECASE)
    formatted = re.sub(r"\(а\)", "(А)", formatted, flags=re.IGNORECASE)
    formatted = re.sub(r"ls", "LS", formatted, flags=re.IGNORECASE)
    formatted = formatted.replace("-P", "-П").replace("-p", "-П")
    return formatted


def _remove_brand_and_noise(name: str, brands: list[str]) -> str:
    cleaned = name
    for brand in brands:
        cleaned = re.sub(re.escape(brand), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bразмер/мм\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -")


def _has_any(text: str, markers: list[str]) -> bool:
    return any(marker.lower() in text for marker in markers)


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def _slugify(value: str) -> str:
    replacements = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ы": "y",
        "э": "e", "ю": "yu", "я": "ya", "ь": "", "ъ": "",
    }
    chars: list[str] = []
    for char in value.lower():
        if char in replacements:
            chars.append(replacements[char])
        elif char.isalnum():
            chars.append(char)
        else:
            chars.append("-")
    slug = re.sub(r"-+", "-", "".join(chars)).strip("-")
    return slug or "category"
