from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VerificationStatus
from app.models.material import Material
from app.models.material_category import MaterialCategory
from app.models.material_specification import MaterialSpecification
from app.models.specification_template import SpecificationTemplate


@dataclass(frozen=True)
class TaxonomyPath:
    section: str
    category: str
    product_type: str | None = None


@dataclass(frozen=True)
class SpecificationField:
    name: str
    field_key: str
    field_type: str = "string"
    unit: str | None = None
    is_required: bool = False
    weight_for_matching: Decimal = Decimal("1.0")


BAUCENTER_CATEGORY_MAP: tuple[tuple[tuple[str, ...], TaxonomyPath], ...] = (
    (("плиты osb", "osb", "осп", "осб"), TaxonomyPath("Строительные материалы", "Листовые материалы", "OSB")),
    (("фанера",), TaxonomyPath("Строительные материалы", "Листовые материалы", "Фанера")),
    (("плиты хдф", "хдф", "hdf"), TaxonomyPath("Строительные материалы", "Листовые материалы", "ХДФ")),
    (("гипсокартон", "гкл", "гипсоволокнист", "гвл"), TaxonomyPath("Строительные материалы", "Материалы для сухого строительства", "Гипсовые листы")),
    (("профили для гипсокартона", "профиль потолочный", "профиль направляющий"), TaxonomyPath("Строительные материалы", "Материалы для сухого строительства", "Профили для гипсокартона")),
    (("газобетон", "газобетонный блок", "стеновой блок", "bonolit", "vkblock", "вкблок"), TaxonomyPath("Строительные материалы", "Стеновые материалы", "Газобетонные блоки")),
    (("клей для кладки", "кладочная смесь", "клей монтажный", "ячеистого бетона"), TaxonomyPath("Строительные материалы", "Сухие смеси", "Клеи для кладки")),
    (("шпатлев", "шпаклев", "штукатур"), TaxonomyPath("Строительные материалы", "Сухие смеси", "Шпатлевки и штукатурки")),
    (("металлочереп", "монтеррей", "монтерей"), TaxonomyPath("Кровля и водосток", "Кровельные материалы", "Металлочерепица")),
    (("гибкая черепица", "shinglas", "tegola"), TaxonomyPath("Кровля и водосток", "Кровельные материалы", "Гибкая черепица")),
    (("снегозадерж", "snegozader"), TaxonomyPath("Кровля и водосток", "Комплектующие кровли", "Снегозадержатели")),
    (("доборные элементы кровли", "конек", "ендова", "планка примыкания"), TaxonomyPath("Кровля и водосток", "Комплектующие кровли", "Доборные элементы")),
    (("водосток", "желоб", "труба водосточная"), TaxonomyPath("Кровля и водосток", "Водосточные системы", "Комплектующие водостока")),
    (("сайдинг",), TaxonomyPath("Фасады", "Фасадные материалы", "Сайдинг")),
    (("фасадные панели",), TaxonomyPath("Фасады", "Фасадные материалы", "Фасадные панели")),
    (("софит",), TaxonomyPath("Фасады", "Фасадные материалы", "Софиты")),
    (("отлив", "доборные элементы фасада"), TaxonomyPath("Фасады", "Доборные элементы", "Отливы")),
    (("саморезы с прессшайбой", "прессшайб"), TaxonomyPath("Крепеж", "Саморезы", "С прессшайбой")),
    (("саморезы для гипсокартона",), TaxonomyPath("Крепеж", "Саморезы", "Для гипсокартона")),
    (("саморезы семечки", "семечки для профиля"), TaxonomyPath("Крепеж", "Саморезы", "Для профиля")),
    (("саморез",), TaxonomyPath("Крепеж", "Саморезы", None)),
    (("анкеры", "анкер", "дюбель"), TaxonomyPath("Крепеж", "Анкеры и дюбели", None)),
    (("лампа", "освещение", "светильник", "трековые"), TaxonomyPath("Электрика и освещение", "Освещение", "Лампы и светильники")),
    (("кабель", "провод", "ввг"), TaxonomyPath("Электрика и освещение", "Кабель и провод", "Силовой кабель")),
    (("запчасти для смесителей", "прокладки", "смесител"), TaxonomyPath("Сантехника", "Смесители и комплектующие", "Запчасти и прокладки")),
    (("прокладки для труб",), TaxonomyPath("Сантехника", "Трубы и фитинги", "Прокладки")),
    (("душевые системы",), TaxonomyPath("Сантехника", "Душевые системы", None)),
    (("печи для бани", "печь-каменка", "сауны"), TaxonomyPath("Бани и сауны", "Печи", "Печи-каменки")),
    (("электролобзик", "штроборез", "шуруповерт", "перфоратор", "дрель", "ушм"), TaxonomyPath("Инструмент", "Электроинструмент", None)),
    (("сетчатая система хранения", "сборные стеллажи", "шкафов-купе", "раздвижных дверей"), TaxonomyPath("Дом и хранение", "Системы хранения", None)),
    (("экраны для радиаторов",), TaxonomyPath("Отопление", "Радиаторы и комплектующие", "Экраны для радиаторов")),
)


SPECIFICATION_TEMPLATES: dict[tuple[str, str, str | None], tuple[SpecificationField, ...]] = {
    ("Кровля и водосток", "Кровельные материалы", "Металлочерепица"): (
        SpecificationField("Профиль", "profile", is_required=True, weight_for_matching=Decimal("1.8")),
        SpecificationField("Толщина", "thickness", "number", "мм", True, Decimal("2.0")),
        SpecificationField("Тип покрытия", "coating_type", is_required=True, weight_for_matching=Decimal("1.7")),
        SpecificationField("Цвет RAL", "ral_color", is_required=True, weight_for_matching=Decimal("1.5")),
        SpecificationField("Длина", "length", "number", "мм", False, Decimal("0.8")),
        SpecificationField("Ширина полезная", "working_width", "number", "мм", False, Decimal("0.8")),
    ),
    ("Кровля и водосток", "Кровельные материалы", "Гибкая черепица"): (
        SpecificationField("Коллекция", "collection", is_required=True, weight_for_matching=Decimal("1.6")),
        SpecificationField("Форма нарезки", "cut_shape", weight_for_matching=Decimal("1.2")),
        SpecificationField("Цвет", "color", is_required=True, weight_for_matching=Decimal("1.4")),
        SpecificationField("Площадь упаковки", "package_area", "number", "м2", False, Decimal("0.8")),
    ),
    ("Фасады", "Фасадные материалы", "Сайдинг"): (
        SpecificationField("Тип", "siding_type", is_required=True, weight_for_matching=Decimal("1.4")),
        SpecificationField("Профиль", "profile", weight_for_matching=Decimal("1.2")),
        SpecificationField("Цвет", "color", is_required=True, weight_for_matching=Decimal("1.4")),
        SpecificationField("Длина", "length", "number", "мм"),
    ),
    ("Фасады", "Фасадные материалы", "Фасадные панели"): (
        SpecificationField("Фактура", "texture", is_required=True, weight_for_matching=Decimal("1.3")),
        SpecificationField("Коллекция", "collection", weight_for_matching=Decimal("1.1")),
        SpecificationField("Цвет", "color", is_required=True, weight_for_matching=Decimal("1.4")),
    ),
    ("Фасады", "Доборные элементы", "Отливы"): (
        SpecificationField("Ширина", "width", "number", "мм", True, Decimal("1.8")),
        SpecificationField("Толщина", "thickness", "number", "мм", True, Decimal("1.6")),
        SpecificationField("Покрытие", "coating_type", is_required=True, weight_for_matching=Decimal("1.4")),
        SpecificationField("Цвет RAL", "ral_color", is_required=True, weight_for_matching=Decimal("1.4")),
        SpecificationField("Длина", "length", "number", "м"),
    ),
    ("Строительные материалы", "Стеновые материалы", "Газобетонные блоки"): (
        SpecificationField("Длина", "length", "number", "мм", True, Decimal("1.5")),
        SpecificationField("Ширина", "width", "number", "мм", True, Decimal("1.7")),
        SpecificationField("Высота", "height", "number", "мм", True, Decimal("1.5")),
        SpecificationField("Плотность", "density", is_required=True, weight_for_matching=Decimal("1.8")),
        SpecificationField("Класс прочности", "strength_class", weight_for_matching=Decimal("1.1")),
    ),
    ("Строительные материалы", "Листовые материалы", "OSB"): (
        SpecificationField("Толщина", "thickness", "number", "мм", True, Decimal("2.0")),
        SpecificationField("Длина", "length", "number", "мм", True, Decimal("1.2")),
        SpecificationField("Ширина", "width", "number", "мм", True, Decimal("1.2")),
        SpecificationField("Влагостойкость", "moisture_resistance", "boolean", None, False, Decimal("0.8")),
    ),
    ("Строительные материалы", "Листовые материалы", "Фанера"): (
        SpecificationField("Толщина", "thickness", "number", "мм", True, Decimal("1.8")),
        SpecificationField("Сорт", "grade", is_required=True, weight_for_matching=Decimal("1.4")),
        SpecificationField("Марка", "plywood_mark", weight_for_matching=Decimal("1.2")),
        SpecificationField("Длина", "length", "number", "мм"),
        SpecificationField("Ширина", "width", "number", "мм"),
    ),
    ("Строительные материалы", "Сухие смеси", "Клеи для кладки"): (
        SpecificationField("Назначение", "application", is_required=True, weight_for_matching=Decimal("1.4")),
        SpecificationField("Вес мешка", "package_weight", "number", "кг", True, Decimal("1.2")),
        SpecificationField("Основание", "base_material", weight_for_matching=Decimal("1.1")),
    ),
    ("Крепеж", "Саморезы", "С прессшайбой"): (
        SpecificationField("Диаметр", "diameter", "number", "мм", True, Decimal("1.6")),
        SpecificationField("Длина", "length", "number", "мм", True, Decimal("1.6")),
        SpecificationField("Наконечник", "tip_type", is_required=True, weight_for_matching=Decimal("1.2")),
        SpecificationField("Количество в упаковке", "package_quantity", "number", "шт"),
    ),
    ("Кровля и водосток", "Комплектующие кровли", "Снегозадержатели"): (
        SpecificationField("Тип", "snow_guard_type", is_required=True, weight_for_matching=Decimal("1.4")),
        SpecificationField("Длина", "length", "number", "м", False, Decimal("1.1")),
        SpecificationField("Покрытие", "coating_type", is_required=False, weight_for_matching=Decimal("1.1")),
        SpecificationField("Цвет RAL", "ral_color", is_required=False, weight_for_matching=Decimal("1.1")),
    ),
    ("Электрика и освещение", "Кабель и провод", "Силовой кабель"): (
        SpecificationField("Марка кабеля", "cable_mark", is_required=True, weight_for_matching=Decimal("2.0")),
        SpecificationField("Количество жил", "cores", "number", "шт", True, Decimal("1.5")),
        SpecificationField("Сечение", "cross_section", "number", "мм2", True, Decimal("1.7")),
        SpecificationField("Напряжение", "voltage", "number", "кВ", False, Decimal("0.9")),
    ),
}


def infer_baucenter_taxonomy(raw_name: str | None, raw_category: str | None, url: str | None = None) -> TaxonomyPath | None:
    text = " ".join(part for part in [raw_category, raw_name, url] if part).lower()
    for markers, path in BAUCENTER_CATEGORY_MAP:
        if any(marker in text for marker in markers):
            return path
    return None


async def ensure_specification_templates(db: AsyncSession, category: MaterialCategory | None, path: TaxonomyPath | None) -> None:
    if not category or not path:
        return
    fields = SPECIFICATION_TEMPLATES.get((path.section, path.category, path.product_type))
    if not fields:
        fields = SPECIFICATION_TEMPLATES.get((path.section, path.category, None))
    if not fields:
        return
    for field in fields:
        result = await db.execute(
            select(SpecificationTemplate).where(
                SpecificationTemplate.category_id == category.id,
                SpecificationTemplate.field_key == field.field_key,
            )
        )
        if result.scalar_one_or_none():
            continue
        db.add(
            SpecificationTemplate(
                category_id=category.id,
                name=field.name,
                field_key=field.field_key,
                field_type=field.field_type,
                unit=field.unit,
                is_required=field.is_required,
                weight_for_matching=field.weight_for_matching,
            )
        )
    await db.flush()


async def sync_extracted_specifications(
    db: AsyncSession,
    material: Material,
    source_id,
    category: MaterialCategory | None,
    path: TaxonomyPath | None,
    raw_name: str | None,
    raw_category: str | None,
) -> None:
    if not category or not path:
        return
    values = extract_specification_values(raw_name, raw_category, path)
    if not values:
        return
    await ensure_specification_templates(db, category, path)
    result = await db.execute(
        select(SpecificationTemplate).where(SpecificationTemplate.category_id == category.id)
    )
    templates = {template.field_key: template for template in result.scalars().all()}
    for field_key, value in values.items():
        template = templates.get(field_key)
        if not template:
            continue
        existing_result = await db.execute(
            select(MaterialSpecification).where(
                MaterialSpecification.material_id == material.id,
                MaterialSpecification.template_id == template.id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            if existing.verified_status == VerificationStatus.VERIFIED:
                continue
            if existing.value == value:
                continue
            existing.value = value
            existing.unit = template.unit
            existing.source_id = source_id
            existing.confidence = Decimal("0.82")
            existing.verified_status = VerificationStatus.AUTO_EXTRACTED
            db.add(existing)
            continue
        db.add(
            MaterialSpecification(
                material_id=material.id,
                template_id=template.id,
                value=value,
                unit=template.unit,
                source_id=source_id,
                confidence=Decimal("0.82"),
                verified_status=VerificationStatus.AUTO_EXTRACTED,
            )
        )
    await db.flush()


def extract_specification_values(
    raw_name: str | None,
    raw_category: str | None,
    path: TaxonomyPath | None,
) -> dict[str, str]:
    if not path:
        return {}
    text = " ".join(part for part in [raw_category, raw_name] if part)
    lower = text.lower()
    values: dict[str, str] = {}

    size = _extract_size_triplet(text)
    if size:
        values.update(size)
    thickness = _extract_thickness(text)
    if thickness:
        values["thickness"] = thickness
    ral = _extract_ral(text)
    if ral:
        values["ral_color"] = ral
    color = _extract_color(text)
    if color:
        values.setdefault("color", color)
    coating = _extract_coating(lower)
    if coating:
        values["coating_type"] = coating
    profile = _extract_profile(lower, path)
    if profile:
        values["profile"] = profile
    if path.product_type == "Снегозадержатели":
        values["snow_guard_type"] = _extract_snow_guard_type(lower)
    density = _extract_density(text)
    if density:
        values["density"] = density
    package_quantity = _extract_package_quantity(text)
    if package_quantity:
        values["package_quantity"] = package_quantity
    package_weight = _extract_package_weight(text)
    if package_weight:
        values["package_weight"] = package_weight
    cable = _extract_cable_values(text)
    values.update(cable)
    if path.category == "Саморезы" or path.section == "Крепеж":
        fastener = _extract_fastener_values(text)
        values.update(fastener)
    if "со сверлом" in lower:
        values["tip_type"] = "со сверлом"
    elif "острый" in lower:
        values["tip_type"] = "острый"
    if path.product_type == "Клеи для кладки":
        values["application"] = "кладка газобетона"
        values["base_material"] = "газобетон"
    return values


def _extract_size_triplet(text: str) -> dict[str, str]:
    match = re.search(r"(\d{3,4})\s*[xх*]\s*(\d{2,4})\s*[xх*]\s*(\d{2,4})", text, re.IGNORECASE)
    if not match:
        return {}
    return {
        "length": match.group(1),
        "width": match.group(2),
        "height": match.group(3),
    }


def _extract_thickness(text: str) -> str | None:
    match = re.search(r"(?:толщина\s*)?(\d{1,2}(?:[,.]\d{1,2})?)\s*(?:мм|mm)\b", text, re.IGNORECASE)
    if match:
        return match.group(1).replace(",", ".")
    match = re.search(r"\b0[,.]\d{2}\b", text)
    return match.group(0).replace(",", ".") if match else None


def _extract_ral(text: str) -> str | None:
    match = re.search(r"\bRAL\s*([0-9]{4})\b", text, re.IGNORECASE)
    return f"RAL {match.group(1)}" if match else None


def _extract_color(text: str) -> str | None:
    ral_match = re.search(r"\bRAL\s*[0-9]{4}\s*([^,\d()]+)?", text, re.IGNORECASE)
    if ral_match and ral_match.group(1):
        return ral_match.group(1).strip(" -")
    known_colors = [
        "мокрый асфальт",
        "терракота",
        "черный",
        "белый",
        "коричневый",
        "графит",
        "зеленый",
    ]
    lower = text.lower()
    for color in known_colors:
        if color in lower:
            return color
    return None


def _extract_coating(text: str) -> str | None:
    if "полиэстер" in text or re.search(r"\bpe\b", text, re.IGNORECASE) or "пэ" in text:
        return "Полиэстер"
    if "пурал" in text:
        return "Пурал"
    if "пластизол" in text:
        return "Пластизол"
    if "цинк" in text:
        return "Цинк"
    return None


def _extract_profile(text: str, path: TaxonomyPath) -> str | None:
    if "монтеррей" in text or "монтерей" in text:
        return "Монтерей"
    if "квадро" in text:
        return "Квадро"
    if path.product_type == "Металлочерепица":
        return None
    if "корабельн" in text:
        return "Корабельная доска"
    if "блок-хаус" in text:
        return "Блок-хаус"
    return None


def _extract_snow_guard_type(text: str) -> str:
    if "трубчат" in text:
        return "трубчатый"
    if "уголков" in text:
        return "уголковый"
    if "решет" in text:
        return "решетчатый"
    return "снегозадержатель"


def _extract_density(text: str) -> str | None:
    match = re.search(r"\bD\s*(\d{3})\b", text, re.IGNORECASE)
    return f"D{match.group(1)}" if match else None


def _extract_package_quantity(text: str) -> str | None:
    match = re.search(r"(\d+)\s*шт", text, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_package_weight(text: str) -> str | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*кг", text, re.IGNORECASE)
    return match.group(1).replace(",", ".") if match else None


def _extract_cable_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    mark = re.search(r"\b(ВВГ(?:нг)?(?:\([А-ЯA-Z]\))?(?:-?П)?(?:-?LS)?)\b", text, re.IGNORECASE)
    section = re.search(r"(\d+)\s*[xх]\s*(\d+(?:[,.]\d+)?)", text, re.IGNORECASE)
    voltage = re.search(r"\b(0[,.]66|1)\s*кВ\b", text, re.IGNORECASE)
    if mark:
        values["cable_mark"] = mark.group(1).upper().replace(",", ".")
    if section:
        values["cores"] = section.group(1)
        values["cross_section"] = section.group(2).replace(",", ".")
    if voltage:
        values["voltage"] = voltage.group(1).replace(",", ".")
    return values


def _extract_fastener_values(text: str) -> dict[str, str]:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*[xх]\s*(\d+(?:[,.]\d+)?)", text, re.IGNORECASE)
    if not match:
        return {}
    return {
        "diameter": match.group(1).replace(",", "."),
        "length": match.group(2).replace(",", "."),
    }
