"""Shared display labels for the existing M1 material attributes."""
from app.models.material import Material

ATTRIBUTE_LABELS = {
    "mixture_type": ("Вид смеси", ""), "concrete_class": ("Класс бетона", ""),
    "water_resistance": ("Водонепроницаемость", ""), "frost_type": ("Тип морозостойкости", ""),
    "frost_cycles": ("Морозостойкость", "циклов"), "mobility_class": ("Подвижность", ""),
    "steel_class": ("Класс арматуры", ""), "diameter_mm": ("Диаметр", "мм"),
    "profile": ("Профиль", ""), "declared_theoretical_mass_kg_per_m": ("Масса погонного метра (заявлена)", "кг/м"),
    "thickness_mm": ("Толщина", "мм"), "cs_10_y_kpa": ("Прочность CS(10/Y)", "кПа"),
    "declared_mark": ("Марка (заявлена)", ""), "length_mm": ("Длина", "мм"),
    "width_mm": ("Ширина", "мм"), "height_mm": ("Высота", "мм"),
    "load_group": ("Группа несущей способности", ""), "concrete_type": ("Тип бетона", ""),
    "declared_standard": ("Стандарт (заявлен)", ""), "strength_mark": ("Марка прочности", ""),
    "mobility_mark": ("Подвижность", ""), "tube_diameter_mm": ("Диаметр трубы", "мм"),
    "wall_thickness_mm": ("Толщина стенки", "мм"), "blade_diameter_mm": ("Диаметр лопасти", "мм"),
    "section_width_mm": ("Ширина сечения", "мм"), "section_height_mm": ("Высота сечения", "мм"),
    "mass_kg": ("Масса", "кг"),
}
INTERNAL_ATTRIBUTES = frozenset({"registry_origin", "registry_key", "registry_code", "declared_source", "ui_purpose"})


def humanize_material_field_key(value: str | None) -> str:
    if not value:
        return "Характеристика"
    known = {"length_mm": "Длина, мм", "width_mm": "Ширина, мм", "height_mm": "Высота, мм",
             "thickness_mm": "Толщина, мм", "density_class": "Марка плотности", "strength_class": "Класс прочности",
             "frost_resistance": "Морозостойкость", "sheet_area_m2": "Площадь листа, м²", "board_type": "Тип листа",
             "edge_type": "Тип кромки", "weight_kg": "Вес, кг", "sheets_per_pack": "Листов в упаковке",
             "application": "Применение"}
    key = str(value).strip()
    return known.get(key, key.replace("_", " ").replace("-", " "))


def material_attribute_rows(material: Material) -> list[dict[str, str]]:
    rows = []
    for attribute in material.attributes:
        name, value = attribute.attribute_name, attribute.attribute_value
        if name in INTERNAL_ATTRIBUTES or name.endswith("_id") or not value:
            continue
        label, unit = ATTRIBUTE_LABELS.get(name, (humanize_material_field_key(name), ""))
        rows.append({"label": label, "value": value, "unit": unit})
    return rows


def material_ui_attribute_rows(material: Material) -> list[dict]:
    rows = []
    for attribute in material.attributes:
        name, value = attribute.attribute_name, attribute.attribute_value
        if name in INTERNAL_ATTRIBUTES or name.endswith("_id") or not value:
            continue
        label, fallback_unit = ATTRIBUTE_LABELS.get(name, (humanize_material_field_key(name), ""))
        stored_unit = attribute.unit.abbreviation if attribute.unit else None
        rows.append({"label": label, "value": value,
                     "unit": {"mm": "мм", "kPa": "кПа"}.get(stored_unit, stored_unit) if stored_unit else fallback_unit,
                     "unit_inferred": bool(fallback_unit and not attribute.unit)})
    return rows
