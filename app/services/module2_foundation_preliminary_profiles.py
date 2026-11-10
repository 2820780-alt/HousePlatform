"""User-specified preliminary foundation profiles, not design approvals.

These proposals do not write to M1/M2, activate revisions, or resolve gaps.
Material codes refer to M1 registry candidates, never a second material store.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping
from uuid import UUID, uuid4

from app.models.module2_technology import Technology, TechnologyDefaultAssumption
from app.schemas.module2_knowledge import KnowledgeRuleDraftInput
from app.schemas.module2_technology import MaterialRequirementSelector, TechnologyMaterialRequirementInput
from app.services.module2_foundation_quantity_rules import describe_quantity_rule


@dataclass(frozen=True)
class Role:
    code: str
    element: str
    purpose: str
    material_code: str | None
    quantity_rule: str | None = None
    alternatives: tuple[str, ...] = ()
    condition: str | None = None
    missing: str | None = None
    follow_up_rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class Profile:
    technology_code: str
    profile_code: str
    roles: tuple[Role, ...]
    parameters: tuple[tuple[str, str, str], ...] = ()
    status: str = "PRELIMINARY_ESTIMATE"
    warning: str = "Предварительная комплектация для оценки стоимости, не проверка несущей способности."


@dataclass(frozen=True)
class ProfileReconciliation:
    technology_code: str
    same_code_needs_review: tuple[str, ...]
    existing_only: tuple[str, ...]
    proposed_only: tuple[str, ...]
    suggested_expansions: tuple[tuple[str, tuple[str, ...]], ...]
    unmapped_existing: tuple[str, ...]


def _r(code, element, purpose, material=None, rule=None, alternatives=(), condition=None, missing=None, follow_up_rules=()):
    return Role(code, element, purpose, material, rule, alternatives, condition, missing, follow_up_rules)


def _concrete(element="Конструкция", material="BT-02", alternatives=()):
    return _r("CONCRETE", element, "Бетон", material, "BOX_UNION_VOLUME", alternatives)


def _bar(code, element, purpose, material="RA-04", condition=None, alternatives=()):
    return _r(code, element, purpose, material, "BAR_MASS", alternatives=alternatives, condition=condition,
              missing="Нужно выбрать класс и диаметр арматуры." if material is None else None,
              follow_up_rules=("LAP_ALLOWANCE_LENGTH",))


def _stirrups(element, alternatives=()):
    return _r("STIRRUPS", element, "Поперечная арматура", "RA-10", "SPACED_ZONES_COUNT", alternatives,
              missing="Нужны осевая форма, загибы и длины концевых элементов.",
              follow_up_rules=("STIRRUP_CUT_LENGTH", "BAR_MASS"))


def _form(element, material=None):
    return _r("FORMWORK", element, "Опалубочная система", material, "FORMWORK_AREA",
              missing="Нужна выбранная система, раскрой, аренда и повторное использование.")


PROFILES = (
    Profile("FND_STRIP_MONOLITHIC_RC", "FND-STRIP-01", (
        _concrete("Лента", alternatives=("BT-03", "BT-04")),
        _bar("REBAR_TOP", "Лента", "Верхние продольные стержни", alternatives=("RA-03", "RA-05", "RA-06")),
        _bar("REBAR_BOTTOM", "Лента", "Нижние продольные стержни", alternatives=("RA-03", "RA-05", "RA-06")),
        _stirrups("Лента", alternatives=("RA-02", "RA-11")),
        _r("CORNER_REBAR", "Углы", "Дополнительные стержни", missing="Нужны материал и деталировка углов."),
        _r("JOINT_REBAR", "Примыкания", "Дополнительное армирование", missing="Нужны материал и деталировка примыканий."),
        _r("WIRE", "Каркас", "Вязальная проволока", "ARM-AUX-01", missing="Расход не подтверждён."),
        _r("SPACERS", "Каркас", "Фиксаторы", "ARM-AUX-05", missing="Число и тип уточняются по схеме."),
        _form("Лента", "FORM-01"),
        _r("PREPARATION", "Основание", "Подготовка", condition="Если предусмотрена", missing="Нужен выбранный состав подготовки."),
        _r("WATERPROOFING", "Лента", "Гидроизоляция", condition="Если предусмотрена", missing="Нужно выбрать систему."),
        _r("INSULATION", "Лента", "Теплоизоляция", condition="Если предусмотрена", missing="Нужны выбранный материал и зоны."),
    ), (("width", "400", "mm"), ("height", "600", "mm"), ("top_bar_count", "2", "piece"),
        ("bottom_bar_count", "2", "piece"), ("stirrup_spacing", "200", "mm"), ("cover", "40", "mm"))),
    Profile("FND_STRIP_PRECAST_FBS_FL", "FND-FBS-01", (
        _r("FBS_MAIN", "Стена", "Основной блок", "FBS-02", "LAYOUT_ITEM_COUNT"),
        _r("FBS_SHORT", "Стена", "Доборный блок 1180 мм", "FBS-05", "LAYOUT_ITEM_COUNT"),
        _r("FBS_SHORTER", "Стена", "Доборный блок 880 мм", "FBS-09", "LAYOUT_ITEM_COUNT"),
        _r("FL", "Основание", "Фундаментная плита", "FL-12", "LAYOUT_ITEM_COUNT"),
        _r("MORTAR", "Швы", "Кладочный раствор", "RM-01", missing="Нужна геометрия швов."),
        _r("WATERPROOFING", "Стена", "Гидроизоляция", condition="Если предусмотрена", missing="Нужно выбрать систему."),
    )),
    Profile("FND_SLAB_MONOLITHIC_RC", "FND-SLAB-01", (
        _r("CONCRETE", "Плита", "Бетон", "BT-02", "NET_AREA_VOLUME"),
        _bar("LOWER_X", "Нижняя сетка", "Арматура направления X"), _bar("LOWER_Y", "Нижняя сетка", "Арматура направления Y"),
        _bar("UPPER_X", "Верхняя сетка", "Арматура направления X"), _bar("UPPER_Y", "Верхняя сетка", "Арматура направления Y"),
        _r("LOCAL_REBAR", "Края и проёмы", "Локальное усиление", condition="Если предусмотрено", missing="Нужны материал и деталировка."),
        _r("SUPPORTS", "Сетки", "Поддерживающие элементы", "ARM-AUX-07", missing="Нужны тип и раскладка."),
        _r("SPACERS", "Сетки", "Фиксаторы защитного слоя", missing="Нужны защитный слой и схема фиксаторов."),
        _form("Торцы плиты", "FORM-01"),
        _r("PREPARATION", "Основание", "Подготовка", condition="Если предусмотрена", missing="Нужен состав слоёв."),
        _r("WATERPROOFING", "Плита", "Гидроизоляция", condition="Если предусмотрена", missing="Нужно выбрать систему."),
        _r("INSULATION", "Плита", "Теплоизоляция", condition="Если предусмотрена", missing="Нужны выбранный материал и зоны."),
    ), (("slab_thickness", "250", "mm"), ("lower_x_spacing", "200", "mm"),
        ("lower_y_spacing", "200", "mm"), ("upper_x_spacing", "200", "mm"), ("upper_y_spacing", "200", "mm"))),
    Profile("FND_SLAB_RIBBED_RC", "FND-RIBBED-SLAB-01", (
        _r("SLAB_CONCRETE", "Плита", "Бетон плиты", "BT-02", "NET_AREA_VOLUME"),
        _r("RIB_CONCRETE", "Рёбра", "Бетон рёбер", "BT-02", "BOX_VOLUME_EXCLUDING_OCCUPIED",
           missing="Нужна геометрия рёбер и уже учтённой плиты."),
        _bar("SLAB_LOWER", "Плита", "Нижняя сетка"),
        _bar("SLAB_UPPER", "Плита", "Верхняя сетка", condition="Если предусмотрена"),
        _bar("RIB_LONGITUDINAL", "Рёбра", "Продольная арматура"), _stirrups("Рёбра"),
        _r("RIB_JOINTS", "Сопряжения рёбер", "Дополнительное армирование", condition="Если предусмотрено", missing="Нужна деталировка узлов."),
        _form("Плита и рёбра"),
    ), (("stirrup_spacing", "200", "mm"),)),
    Profile("FND_SLAB_USHP", "FND-USHP-01", (
        _r("SLAB_CONCRETE", "Плита", "Бетон плиты", "BT-02", "NET_AREA_VOLUME"),
        _r("RIB_CONCRETE", "Рёбра", "Бетон рёбер", "BT-02", "BOX_VOLUME_EXCLUDING_OCCUPIED",
           missing="Нужна геометрия рёбер и уже учтённой плиты."),
        _bar("SLAB_REBAR", "Плита", "Армирование плиты"),
        _bar("RIB_REBAR", "Рёбра", "Армирование рёбер", material=None),
        _r("UNDER_SLAB_XPS", "Под плитой", "Теплоизоляция", "XPS-06", "NET_AREA"),
        _r("EDGE_XPS", "Торец", "Теплоизоляция", "XPS-04", "NET_AREA"),
        _r("SAND", "Основание", "Песчаная подготовка", "BASE-01", "NET_AREA_VOLUME"),
        _r("GRAVEL", "Основание", "Щебёночная подготовка", "BASE-02", "NET_AREA_VOLUME", ("BASE-03",)),
        _r("GEOTEXTILE", "Основание", "Разделительный слой", "BASE-04", missing="Нужна раскладка и нахлёсты."),
        _r("WATERPROOFING", "Плита", "Гидроизоляция", condition="Если предусмотрена", missing="Нужно выбрать систему."),
        _r("PENETRATIONS", "Вводы", "Гильзы", "PEN-01", "LAYOUT_ITEM_COUNT", ("PEN-02",)),
        _r("HEATING", "Пол", "Трубы отопления", condition="Если включены", missing="Учёт принадлежит выбранной инженерной системе."),
    )),
    Profile("FND_UFF", "FND-UFF-01", (
        _concrete("Фундамент"), _bar("FOUNDATION_REBAR", "Фундамент", "Армирование", material=None),
        _r("FOUNDATION_XPS", "Фундамент", "Теплоизоляция", "XPS-06", "NET_AREA"),
        _r("FLOOR_CONCRETE", "Пол по грунту", "Бетон пола", "BT-01", "NET_AREA_VOLUME"),
        _r("FLOOR_REBAR", "Пол по грунту", "Армирование пола", missing="Нужен материал и схема пола."),
        _r("FLOOR_XPS", "Пол по грунту", "Утепление пола", condition="Если предусмотрено", missing="Нужен выбранный состав пола."),
        _r("SEPARATION", "Пол по грунту", "Разделительные слои", condition="Если предусмотрены", missing="Нужен состав пола."),
        _r("PENETRATIONS", "Вводы", "Инженерные проходки", condition="Если предусмотрены", missing="Нужны схема и спецификация вводов."),
        _r("WATERPROOFING", "Фундамент", "Гидроизоляция", condition="Если предусмотрена", missing="Нужно выбрать систему."),
    )),
    Profile("FND_PILE_BORED_RC", "FND-BORED-PILE-01", (
        _r("CONCRETE", "Свая", "Бетон", "BT-03", "CYLINDER_VOLUME"),
        _bar("PILE_LONGITUDINAL", "Свая", "Продольные стержни"), _stirrups("Свая"),
        _r("SPACERS", "Каркас сваи", "Фиксаторы", missing="Нужны тип и раскладка фиксаторов."),
        _r("CASING", "Свая", "Обсадные материалы", condition="Если предусмотрены", missing="Зависит от технологии изготовления."),
    ), (("stirrup_spacing", "200", "mm"),)),
    Profile("FND_PILE_DRIVEN_RC", "FND-DRIVEN-RC-PILE-01", (
        _r("FACTORY_PILE", "Свайное поле", "Готовая заводская свая", "PILE-RC-01", "LAYOUT_ITEM_COUNT", ("PILE-RC-02",),
           missing="Нужна полная заводская марка; бетон и арматура изделия отдельно не закупаются."),
        _r("PILE_HEAD", "Оголовок", "Сопряжение", condition="Если предусмотрено", missing="Нужна система сопряжения."),
        _r("CONNECTION_MATERIALS", "Сопряжение", "Материалы соединения", condition="Если предусмотрены", missing="Нужна спецификация соединения."),
    )),
    Profile("FND_PILE_SCREW", "FND-SCREW-PILE-01", (
        _r("SCREW_PILE", "Свайное поле", "Винтовая свая", "PILE-S-02", "LAYOUT_ITEM_COUNT", ("PILE-S-01", "PILE-S-03")),
        _r("PILE_HEAD", "Оголовок", "Оголовок трубы Ø108", "PILE-S-05", "LAYOUT_ITEM_COUNT"),
        _r("CONNECTION", "Сопряжения", "Соединительные элементы", "PILE-S-06", condition="Если предусмотрены", missing="Нужны детали соединения."),
        _r("COATING", "Свая", "Защитный состав", condition="Если предусмотрен системой", missing="Нужен выбранный состав."),
    )),
    Profile("FND_PILE_GRILLAGE", "FND-PILE-GRILLAGE-01", (
        _r("PILES", "Свайное поле", "Свайная часть", missing="Нужно выбрать отдельную технологию свай; не учитывать повторно."),
        _concrete("Ростверк"), _bar("REBAR_TOP", "Ростверк", "Верхние стержни"),
        _bar("REBAR_BOTTOM", "Ростверк", "Нижние стержни"), _stirrups("Ростверк"),
        _r("WIRE", "Каркас", "Вязальная проволока", "ARM-AUX-01", missing="Расход не подтверждён."),
        _r("SPACERS", "Каркас", "Фиксаторы", "ARM-AUX-05", missing="Нужна раскладка."), _form("Ростверк"),
    ), (("stirrup_spacing", "200", "mm"),)),
    Profile("FND_COLUMN_CONCRETE_RC", "FND-COLUMN-01", (
        _concrete("Опора"), _bar("COLUMN_REBAR", "Опора", "Продольная арматура", condition="Железобетонный вариант"),
        _r("STIRRUPS", "Опора", "Поперечная арматура", "RA-10", "SPACED_ZONES_COUNT",
           condition="Железобетонный вариант", missing="Нужны форма и концевые элементы.",
           follow_up_rules=("STIRRUP_CUT_LENGTH", "BAR_MASS")),
        _r("SPACERS", "Опора", "Фиксаторы", condition="Железобетонный вариант", missing="Нужны тип и раскладка."),
        _form("Опора"),
    ), (("stirrup_spacing", "200", "mm"),)),
    Profile("FND_BASEMENT_WALL_MONOLITHIC", "FND-BASEMENT-WALL-01", (
        _r("CONCRETE", "Стена", "Бетон", "BT-03", "NET_AREA_VOLUME"),
        _bar("OUTER_VERTICAL", "Наружная грань", "Вертикальная арматура"),
        _bar("OUTER_HORIZONTAL", "Наружная грань", "Горизонтальная арматура"),
        _bar("INNER_VERTICAL", "Внутренняя грань", "Вертикальная арматура"),
        _bar("INNER_HORIZONTAL", "Внутренняя грань", "Горизонтальная арматура"),
        _r("CORNER_REBAR", "Углы", "Дополнительное армирование", missing="Нужна деталировка углов."),
        _r("OPENING_REBAR", "Проёмы", "Дополнительное армирование", missing="Нужна деталировка проёмов."),
        _r("SLAB_JOINT", "Сопряжение с плитой", "Армирование узла", missing="Нужна деталировка сопряжения."),
        _r("JOINTS", "Швы", "Материалы швов", condition="Если предусмотрены", missing="Нужна спецификация швов."),
        _r("PENETRATIONS", "Вводы", "Материалы проходок", condition="Если предусмотрены", missing="Нужна схема проходок."),
        _r("SPACERS", "Арматура", "Фиксаторы", missing="Нужны защитный слой и раскладка."),
        _form("Две грани стены"),
        _r("WATERPROOFING", "Наружная грань", "Гидроизоляция", condition="Если предусмотрена", missing="Нужно выбрать систему."),
        _r("WALL_XPS", "Наружная грань", "Теплоизоляция", "XPS-03", "NET_AREA", condition="Если предусмотрена"),
    ), (("wall_thickness", "250", "mm"), ("outer_vertical_spacing", "200", "mm"),
        ("outer_horizontal_spacing", "200", "mm"), ("inner_vertical_spacing", "200", "mm"),
        ("inner_horizontal_spacing", "200", "mm"))),
    Profile("FND_SUBSTRUCTURE_WATERPROOFING_COATING", "FND-WPR-MASTIC-01", (
        _r("PRIMER", "Покрытие", "Праймер", "WPR-02", "COATING_QUANTITY", missing="Расход системы не подтверждён."),
        _r("MASTIC", "Покрытие", "Мастика", "WPR-01", "COATING_QUANTITY", missing="Расход системы не подтверждён."),
        _r("JOINT_TAPE", "Примыкания", "Лента", "WPR-08", condition="Если предусмотрена", missing="Нужна геометрия примыканий."),
        _r("PROTECTION", "Покрытие", "Защитный материал", "WPR-10", condition="Если предусмотрен", missing="Нужна выбранная система."),
    ), (("layers", "2", "piece"),)),
    Profile("FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE", "FND-WPR-MEMBRANE-01", (
        _r("BITUMEN_MEMBRANE", "Покрытие", "Наплавляемый материал", "WPR-03", alternatives=("WPR-04",),
           missing="Нужны раскладка, нахлёсты и совместимость выбранной системы."),
        _r("PRIMER", "Основание", "Совместимый праймер", missing="Нужен праймер выбранной системы."),
        _r("PENETRATIONS", "Проходки", "Герметизация", "WPR-09", condition="Если предусмотрена", missing="Нужна совместимость системы."),
        _r("JOINTS", "Примыкания", "Комплектующие системы", missing="Нужны материалы и схема примыканий."),
        _r("PROTECTION", "Покрытие", "Защитный материал", condition="Если предусмотрен", missing="Нужна выбранная система."),
    )),
    Profile("FND_SUBSTRUCTURE_INSULATION_XPS", "FND-XPS-01", (
        _r("WALL_XPS", "Наружная стена", "Теплоизоляция стены", "XPS-03", "NET_AREA", ("XPS-02", "XPS-04", "XPS-06")),
        _r("UNDER_SLAB_XPS", "Под плитой", "Теплоизоляция основания", "XPS-06", "NET_AREA", ("XPS-08", "XPS-09", "XPS-10"), condition="Если предусмотрена"),
        _r("EDGE_XPS", "Торец плиты", "Теплоизоляция торца", condition="Если предусмотрена", missing="Нужны выбранный материал и геометрия."),
        _r("NODE_XPS", "Узлы", "Теплоизоляция узлов", condition="Если предусмотрена", missing="Нужны состав и геометрия узлов."),
        _r("ATTACHMENT", "Крепление", "Крепление или приклеивание", missing="Нужны совместимый способ и материал."),
        _r("PROTECTION", "Защита", "Защита утепления", condition="Если предусмотрена", missing="Нужен выбранный материал."),
    )),
)


# Candidates describe semantic expansion, not permission to rewrite historical links.
_ROLE_EXPANSIONS = {
    "FND_STRIP_MONOLITHIC_RC": {"REBAR": ("REBAR_TOP", "REBAR_BOTTOM", "STIRRUPS", "CORNER_REBAR", "JOINT_REBAR")},
    "FND_STRIP_PRECAST_FBS_FL": {"FBS": ("FBS_MAIN", "FBS_SHORT", "FBS_SHORTER")},
    "FND_SLAB_MONOLITHIC_RC": {"REBAR": ("LOWER_X", "LOWER_Y", "UPPER_X", "UPPER_Y", "LOCAL_REBAR")},
    "FND_SLAB_RIBBED_RC": {"CONCRETE": ("SLAB_CONCRETE", "RIB_CONCRETE"),
                           "REBAR": ("SLAB_LOWER", "SLAB_UPPER", "RIB_LONGITUDINAL", "STIRRUPS", "RIB_JOINTS")},
    "FND_SLAB_USHP": {"CONCRETE": ("SLAB_CONCRETE", "RIB_CONCRETE"), "REBAR": ("SLAB_REBAR", "RIB_REBAR"),
                      "XPS": ("UNDER_SLAB_XPS", "EDGE_XPS")},
    "FND_UFF": {"REBAR": ("FOUNDATION_REBAR",), "XPS": ("FOUNDATION_XPS",)},
    "FND_PILE_BORED_RC": {"REBAR": ("PILE_LONGITUDINAL", "STIRRUPS")},
    "FND_PILE_DRIVEN_RC": {"PILE": ("FACTORY_PILE",)},
    "FND_PILE_SCREW": {"PILE": ("SCREW_PILE",)},
    "FND_PILE_GRILLAGE": {"REBAR": ("REBAR_TOP", "REBAR_BOTTOM", "STIRRUPS")},
    "FND_COLUMN_CONCRETE_RC": {"REBAR": ("COLUMN_REBAR", "STIRRUPS")},
    "FND_BASEMENT_WALL_MONOLITHIC": {"REBAR": ("OUTER_VERTICAL", "OUTER_HORIZONTAL", "INNER_VERTICAL", "INNER_HORIZONTAL",
                                                    "CORNER_REBAR", "OPENING_REBAR", "SLAB_JOINT")},
    "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE": {"MEMBRANE": ("BITUMEN_MEMBRANE",)},
    "FND_SUBSTRUCTURE_INSULATION_XPS": {"XPS": ("WALL_XPS", "UNDER_SLAB_XPS", "EDGE_XPS", "NODE_XPS")},
}


def audit_profile_reconciliation(technology: Technology) -> ProfileReconciliation:
    """Compare names only; a shared code is not evidence of semantic equivalence."""
    profile = next((item for item in PROFILES if item.technology_code == technology.technology_code), None)
    if profile is None:
        raise ValueError("unknown foundation technology")
    existing = [item.code for item in technology.requirements]
    if any(not isinstance(code, str) or not code for code in existing) or len(set(existing)) != len(existing):
        raise ValueError("existing requirement codes require review")
    proposed = {role.code for role in profile.roles}
    existing_set = set(existing)
    candidates = _ROLE_EXPANSIONS.get(technology.technology_code, {})
    suggestions = []
    for code in sorted(existing_set):
        target_codes = candidates.get(code, (code,) if code in proposed else ())
        if not set(target_codes) <= proposed:
            raise ValueError("semantic expansion refers to an unknown proposed role")
        if target_codes:
            suggestions.append((code, target_codes))
    return ProfileReconciliation(
        technology_code=technology.technology_code,
        same_code_needs_review=tuple(sorted(existing_set & proposed)),
        existing_only=tuple(sorted(existing_set - proposed)),
        proposed_only=tuple(sorted(proposed - existing_set)),
        suggested_expansions=tuple(suggestions),
        unmapped_existing=tuple(sorted(existing_set - {item[0] for item in suggestions})),
    )


def prepare_single_role_linkage_draft(technology: Technology, materials_by_code: Mapping[str, object], *, actor_role_code: str):
    """Prepare a blocked revision; never replace a multi-role requirement or write to a database."""
    from app.models.enums import MaterialStatus
    from app.services.module1_foundation_target_package import PACKAGE
    from app.services.module2_technology_foundation import create_next_revision

    audit = audit_profile_reconciliation(technology)
    profile = next(item for item in PROFILES if item.technology_code == technology.technology_code)
    roles = {item.code: item for item in profile.roles}
    draft = create_next_revision(technology, actor_role_code=actor_role_code)
    draft.input_blockers = list(dict.fromkeys([*(draft.input_blockers or ()), "foundation_reconciliation_required"]))
    suggestions = dict(audit.suggested_expansions)
    linked, unresolved = [], []
    for requirement in draft.requirements:
        codes = suggestions.get(requirement.code, ())
        if len(codes) != 1 or not roles[codes[0]].material_code:
            unresolved.append(requirement.code)
            continue
        material_code = roles[codes[0]].material_code
        material = materials_by_code.get(material_code)
        if material is None:
            unresolved.append(requirement.code)
            continue
        marker = {item.attribute_name: item.attribute_value for item in material.attributes}
        valid = (
            isinstance(material.id, UUID)
            and material.status in {MaterialStatus.DRAFT, MaterialStatus.VERIFIED}
            and marker.get("registry_origin") == PACKAGE
            and marker.get("registry_code") == material_code
            and requirement.selector_kind == "MATERIAL_CLASS"
            and requirement.canonical_material_id is None
            and requirement.material_type_id is None
            and not requirement.technical_constraints
            and requirement.material_category_id is not None
            and material.category_id == requirement.material_category_id
        )
        if not valid:
            unresolved.append(requirement.code)
            continue
        requirement.selector_kind = "CANONICAL_MATERIAL"
        requirement.canonical_material_id = material.id
        linked.append(requirement.code)
    return draft, tuple(linked), tuple(unresolved)


def profile_requirement_proposals(technology_code: str, material_ids: Mapping[str, UUID]):
    """Return existing M2 requirement DTOs and unresolved roles; write nothing."""
    profile = next((item for item in PROFILES if item.technology_code == technology_code), None)
    if profile is None:
        raise ValueError("unknown foundation technology")
    requirements = []
    unresolved = []
    for role in profile.roles:
        material_id = material_ids.get(role.material_code) if role.material_code else None
        if not isinstance(material_id, UUID):
            unresolved.append(role.code)
            continue
        requirements.append(TechnologyMaterialRequirementInput(
            code=role.code, selector_kind=MaterialRequirementSelector.CANONICAL_MATERIAL,
            material_role_code=role.code, canonical_material_id=material_id,
            technical_constraints={},
            notes=" ".join(part for part in (
                profile.warning, f"{role.element}: {role.purpose}.", role.missing,
            ) if part),
        ))
    return tuple(requirements), tuple(unresolved)


def profile_quantity_rule_proposals(
    technology_code: str, material_ids: Mapping[str, UUID], requirement_ids: Mapping[str, UUID],
):
    """Build evidence-blocked M2 knowledge drafts for explicitly bound roles."""
    profile = next((item for item in PROFILES if item.technology_code == technology_code), None)
    if profile is None:
        raise ValueError("unknown foundation technology")
    proposals = []
    unresolved = []
    for role in profile.roles:
        steps = ((role.quantity_rule,) if role.quantity_rule else ()) + role.follow_up_rules
        if not steps:
            continue
        material_id = material_ids.get(role.material_code) if role.material_code else None
        requirement_id = requirement_ids.get(role.code)
        if not isinstance(material_id, UUID) or not isinstance(requirement_id, UUID):
            unresolved.append(role.code)
            continue
        for code in steps:
            payload = describe_quantity_rule(code, role_code=role.code, material_id=str(material_id))
            proposals.append(KnowledgeRuleDraftInput(
                rule_code=f"Q_{role.code}_{code}", scope_kind="MATERIAL_REQUIREMENT",
                scope_reference=str(requirement_id), outcome_type="INFORMATION", outcome_payload=payload,
                conditions=[{"source": "CONTEXT", "field": field["name"], "operator": "EXISTS"}
                            for field in payload["inputs"] if not field.get("required_when")],
                blockers=["evidence_review_required", "material_review_required"],
            ))
    return tuple(proposals), tuple(unresolved)


PARAMETER_DETAILS = {
    "width": ("STRIP_WIDTH_MM", "Ширина ленты"),
    "height": ("STRIP_HEIGHT_MM", "Высота ленты"),
    "top_bar_count": ("TOP_BAR_COUNT", "Число верхних стержней"),
    "bottom_bar_count": ("BOTTOM_BAR_COUNT", "Число нижних стержней"),
    "stirrup_spacing": ("STIRRUP_SPACING_MM", "Шаг хомутов"),
    "cover": ("COVER_MM", "Защитный слой"),
    "slab_thickness": ("SLAB_THICKNESS_MM", "Толщина плиты"),
    "lower_x_spacing": ("LOWER_X_SPACING_MM", "Шаг нижней сетки X"),
    "lower_y_spacing": ("LOWER_Y_SPACING_MM", "Шаг нижней сетки Y"),
    "upper_x_spacing": ("UPPER_X_SPACING_MM", "Шаг верхней сетки X"),
    "upper_y_spacing": ("UPPER_Y_SPACING_MM", "Шаг верхней сетки Y"),
    "wall_thickness": ("WALL_THICKNESS_MM", "Толщина стены"),
    "outer_vertical_spacing": ("OUTER_VERTICAL_SPACING_MM", "Шаг наружной вертикальной арматуры"),
    "outer_horizontal_spacing": ("OUTER_HORIZONTAL_SPACING_MM", "Шаг наружной горизонтальной арматуры"),
    "inner_vertical_spacing": ("INNER_VERTICAL_SPACING_MM", "Шаг внутренней вертикальной арматуры"),
    "inner_horizontal_spacing": ("INNER_HORIZONTAL_SPACING_MM", "Шаг внутренней горизонтальной арматуры"),
    "layers": ("COATING_LAYER_COUNT", "Число слоёв мастики"),
}


def profile_numeric_default_proposals(technology: Technology):
    """Build unattached existing-model defaults, reporting conflicts without overwriting."""
    if technology.status != "DRAFT" or not isinstance(technology.id, UUID):
        raise ValueError("a persisted-identity DRAFT technology is required")
    profile = next((item for item in PROFILES if item.technology_code == technology.technology_code), None)
    if profile is None:
        raise ValueError("unknown foundation technology")
    proposals = []
    conflicts = []
    reused = []
    for name, value, unit in profile.parameters:
        code, label = PARAMETER_DETAILS[name]
        if any(item.assumption_code == code and item.parameter_code != code
               for item in technology.default_assumptions):
            conflicts.append(code)
            continue
        current = [item for item in technology.default_assumptions
                   if item.status == "ACTIVE" and item.parameter_code == code]
        if current:
            try:
                allowed_units = {"мм", "mm"} if unit == "mm" else {"шт.", "шт", "piece"}
                equal = (len(current) == 1 and Decimal(str(current[0].default_value["value"])) == Decimal(value)
                         and current[0].unit in allowed_units and current[0].auto_fallback
                         and bool(current[0].warning_text))
            except (InvalidOperation, KeyError, TypeError, ValueError):
                equal = False
            (reused if equal else conflicts).append(code)
            continue
        proposals.append(TechnologyDefaultAssumption(
            id=uuid4(), technology_id=technology.id, assumption_code=code, revision=1,
            parameter_code=code, name_ru=label, value_type="NUMBER", unit="мм" if unit == "mm" else "шт.",
            default_value={"value": value}, source_kind="PLATFORM_ASSUMPTION",
            applicability={"mode": "PRELIMINARY_ONLY", "source": "USER_PROVIDED_SPRINT_SPECIFICATION",
                           "structural_safety_verified": False},
            auto_fallback=True, warning_level="CRITICAL", warning_text=profile.warning,
            allowed_values_strategy="BOUNDED_NUMBER",
            allowed_values={"min": 0, "positive": True, "integer": unit == "piece"}, status="ACTIVE",
        ))
    return tuple(proposals), tuple(reused), tuple(conflicts)


def profile_material_default_proposals(
    technology: Technology, material_ids: Mapping[str, UUID], requirement_ids: Mapping[str, UUID],
):
    """Build unattached material defaults for exact roles, never verifying products or prices."""
    if technology.status != "DRAFT" or not isinstance(technology.id, UUID):
        raise ValueError("a persisted-identity DRAFT technology is required")
    profile = next((item for item in PROFILES if item.technology_code == technology.technology_code), None)
    if profile is None:
        raise ValueError("unknown foundation technology")
    proposals, reused, conflicts, unresolved = [], [], [], []
    for role in profile.roles:
        if role.material_code is None:
            continue
        selected = material_ids.get(role.material_code)
        requirement_id = requirement_ids.get(role.code)
        requirement = next((item for item in technology.requirements if item.id == requirement_id), None)
        alternative_ids = [material_ids.get(code) for code in role.alternatives]
        if (not isinstance(selected, UUID) or not isinstance(requirement_id, UUID) or requirement is None
                or requirement.code != role.code or requirement.canonical_material_id != selected
                or not all(isinstance(item, UUID) for item in alternative_ids)):
            unresolved.append(role.code)
            continue
        allowed = [str(item) for item in (selected, *alternative_ids)]
        code = f"MATERIAL_{role.code}"
        if any(item.assumption_code == code and item.parameter_code != code
               for item in technology.default_assumptions):
            conflicts.append(code)
            continue
        current = [item for item in technology.default_assumptions
                   if item.status == "ACTIVE" and item.parameter_code == code]
        if current:
            equal = (len(current) == 1 and current[0].value_type == "MATERIAL"
                     and str(current[0].default_value.get("value")) == str(selected)
                     and set((current[0].allowed_values or {}).get("material_ids", ())) == set(allowed)
                     and (current[0].material_requirement_id or getattr(
                         current[0].__dict__.get("material_requirement"), "id", None)) == requirement_id
                     and current[0].auto_fallback and bool(current[0].warning_text))
            (reused if equal else conflicts).append(code)
            continue
        proposals.append(TechnologyDefaultAssumption(
            id=uuid4(), technology_id=technology.id, assumption_code=code, revision=1,
            parameter_code=code, name_ru=role.purpose, value_type="MATERIAL", unit=None,
            default_value={"value": str(selected)}, source_kind="PLATFORM_ASSUMPTION",
            applicability={"mode": "PRELIMINARY_ONLY", "source": "USER_PROVIDED_SPRINT_SPECIFICATION",
                           "structural_safety_verified": False, "material_verification": "REQUIRED",
                           "alternative_kind": "MANUAL_CONFIGURATION_CHANGE_NOT_EQUIVALENCE"},
            auto_fallback=True, warning_level="CRITICAL",
            warning_text=(profile.warning + " Материал требует проверки; ручная замена не подтверждает равноценность."),
            allowed_values_strategy="EXPLICIT_M1_MATERIALS", allowed_values={"material_ids": allowed},
            material_requirement_id=requirement_id, status="ACTIVE",
        ))
    return tuple(proposals), tuple(reused), tuple(conflicts), tuple(unresolved)


def populate_blocked_foundation_draft(technology: Technology, materials_by_code: Mapping[str, object], *, actor_role_code: str):
    """Add review-only role records to a blocked revision without changing legacy requirements."""
    from app.models.enums import MaterialStatus
    from app.core.access_levels import AccessLevel
    from app.services.module1_foundation_target_package import PACKAGE
    from app.services.module2_knowledge_foundation import create_knowledge_rule_draft
    from app.services.module2_technology_foundation import require_module2_access
    from app.services.module2_workbench import upsert_draft_requirement

    require_module2_access(actor_role_code, AccessLevel.EDIT)
    if technology.status != "DRAFT" or "foundation_reconciliation_required" not in (technology.input_blockers or ()):
        raise ValueError("a reconciliation-blocked DRAFT technology is required")
    ids = {}
    for code, material in materials_by_code.items():
        marker = {item.attribute_name: item.attribute_value for item in material.attributes}
        if (isinstance(material.id, UUID) and material.status in {MaterialStatus.DRAFT, MaterialStatus.VERIFIED}
                and marker.get("registry_origin") == PACKAGE and marker.get("registry_code") == code):
            ids[code] = material.id
    proposals, unresolved = profile_requirement_proposals(technology.technology_code, ids)
    added_roles, reused_roles, alias_requirements = [], [], {}
    legacy_expansions = _ROLE_EXPANSIONS.get(technology.technology_code, {})
    for command in proposals:
        same_code = next((item for item in technology.requirements if item.code == command.code), None)
        if same_code is not None:
            if (same_code.selector_kind == "CANONICAL_MATERIAL"
                    and same_code.canonical_material_id == command.canonical_material_id
                    and same_code.material_role_code != command.code):
                reused_roles.append(command.code)
                alias_requirements[command.code] = same_code
            continue
        existing = next((item for item in technology.requirements
                         if legacy_expansions.get(item.code) == (command.code,)
                         and item.selector_kind == "CANONICAL_MATERIAL"
                         and item.canonical_material_id == command.canonical_material_id), None)
        if existing is not None:
            reused_roles.append(command.code)
            alias_requirements[command.code] = existing
            continue
        upsert_draft_requirement(technology, command, actor_role_code=actor_role_code)
        added_roles.append(command.code)
    profile = next(item for item in PROFILES if item.technology_code == technology.technology_code)
    role_material_ids = {role.code: ids.get(role.material_code) for role in profile.roles if role.material_code}
    requirement_ids = {
        item.code: item.id for item in technology.requirements
        if item.selector_kind == "CANONICAL_MATERIAL" and item.material_role_code == item.code
        and item.canonical_material_id is not None and item.canonical_material_id == role_material_ids.get(item.code)
    }
    rules, missing_rules = profile_quantity_rule_proposals(technology.technology_code, ids, requirement_ids)
    alias_rules = set()
    for role in profile.roles:
        requirement = alias_requirements.get(role.code)
        if requirement is None:
            continue
        steps = ((role.quantity_rule,) if role.quantity_rule else ()) + role.follow_up_rules
        for code in steps:
            payload = describe_quantity_rule(code, role_code=requirement.material_role_code or requirement.code,
                                             material_id=str(requirement.canonical_material_id))
            rules = (*rules, KnowledgeRuleDraftInput(
                rule_code=f"Q_{role.code}_{code}", scope_kind="MATERIAL_REQUIREMENT",
                scope_reference=str(requirement.id), outcome_type="INFORMATION", outcome_payload=payload,
                conditions=[{"source": "CONTEXT", "field": field["name"], "operator": "EXISTS"}
                            for field in payload["inputs"] if not field.get("required_when")],
                blockers=["evidence_review_required", "material_review_required"],
            ))
            alias_rules.add(role.code)
    added_rules, conflicts = [], []
    for parent_code, child_codes in legacy_expansions.items():
        if len(child_codes) < 2:
            continue
        parent = next((item for item in technology.requirements if item.code == parent_code), None)
        if parent is None:
            continue
        children = []
        missing = []
        for child_code in child_codes:
            child = next((item for item in technology.requirements if item.code == child_code
                          and item.selector_kind == "CANONICAL_MATERIAL" and item.canonical_material_id
                          and item.canonical_material_id == role_material_ids.get(child_code)), None)
            if child is None:
                missing.append(child_code)
            else:
                children.append({"role_code": child_code, "requirement_id": str(child.id),
                                 "material_id": str(child.canonical_material_id)})
        payload = {"kind": "FOUNDATION_ROLE_COMPOSITION", "version": 1,
                   "parent_requirement_id": str(parent.id), "children": children,
                   "unresolved_roles": missing, "parent_is_not_an_additional_purchase": True,
                   "status": "REVIEW_REQUIRED", "structural_safety_verified": False}
        command = KnowledgeRuleDraftInput(
            rule_code=f"ROLE_COMPOSITION_{parent_code}", scope_kind="MATERIAL_REQUIREMENT",
            scope_reference=str(parent.id), outcome_type="INFORMATION", outcome_payload=payload,
            conditions=[{"source": "CONTEXT", "field": "foundation_composition_reviewed", "operator": "EQUAL", "value": True}],
            blockers=["role_reconciliation_required", "material_review_required"],
        )
        rules = (*rules, command)
    for command in rules:
        current = [item for item in technology.knowledge_rules if item.rule_code == command.rule_code]
        if current:
            if (len(current) != 1 or current[0].outcome_payload != command.outcome_payload
                    or current[0].scope_kind != command.scope_kind.value
                    or current[0].scope_reference != command.scope_reference or current[0].status != "DRAFT"
                    or current[0].conditions != [item.model_dump(mode="json") for item in command.conditions]
                    or not set(command.blockers).issubset(set(current[0].blockers or ()))):
                conflicts.append(command.rule_code)
            continue
        create_knowledge_rule_draft(technology, command, actor_role_code=actor_role_code)
        added_rules.append(command.rule_code)
    updated_defaults, completed_alias_defaults = [], set()
    for role in profile.roles:
        requirement_id = requirement_ids.get(role.code)
        requirement = alias_requirements.get(role.code) or next(
            (item for item in technology.requirements if item.id == requirement_id), None)
        selected = ids.get(role.material_code)
        alternatives = [ids.get(code) for code in role.alternatives]
        parameter_code = f"MATERIAL_{requirement.code}" if role.code in alias_requirements else f"MATERIAL_{role.code}"
        current = [item for item in technology.default_assumptions
                   if item.status == "ACTIVE" and item.parameter_code == parameter_code]
        if not requirement or not selected or not all(alternatives) or len(current) != 1:
            continue
        default = current[0]
        linked_requirement = default.material_requirement_id or getattr(
            default.__dict__.get("material_requirement"), "id", None)
        linked_evidence = default.evidence_reference_id or getattr(
            default.__dict__.get("evidence_reference"), "id", None)
        if (role.code in alias_requirements and default.value_type == "MATERIAL"
                and default.default_value == {"value": str(selected)}
                and set((default.allowed_values or {}).get("material_ids", ())) == {str(value) for value in (selected, *alternatives)}
                and linked_requirement == requirement.id and default.auto_fallback and default.warning_text):
            completed_alias_defaults.add(role.code)
            continue
        if not (
            default.assumption_code == default.parameter_code
            and default.value_type == "MATERIAL_CLASS"
            and default.source_kind == "PLATFORM_ASSUMPTION"
            and default.allowed_values_strategy == "M1_REQUIREMENT_CATEGORY"
            and linked_requirement == requirement.id and linked_evidence is None
            and requirement.material_category_id is not None
            and (default.default_value or {}) == {"value": str(requirement.material_category_id)}
        ):
            continue
        default.value_type = "MATERIAL"
        default.default_value = {"value": str(selected)}
        default.allowed_values_strategy = "EXPLICIT_M1_MATERIALS"
        default.allowed_values = {"material_ids": [str(value) for value in (selected, *alternatives)]}
        default.applicability = {"mode": "PRELIMINARY_ONLY", "source": "USER_PROVIDED_SPRINT_SPECIFICATION",
                                 "structural_safety_verified": False, "material_verification": "REQUIRED",
                                 "alternative_kind": "MANUAL_CONFIGURATION_CHANGE_NOT_EQUIVALENCE"}
        default.auto_fallback = True
        default.warning_level = "CRITICAL"
        default.warning_text = profile.warning + " Материал требует проверки; ручная замена не подтверждает равноценность."
        updated_defaults.append(default.parameter_code)
        if role.code in alias_requirements:
            completed_alias_defaults.add(role.code)
    numeric, _, numeric_conflicts = profile_numeric_default_proposals(technology)
    material_defaults, _, material_conflicts, missing_defaults = profile_material_default_proposals(
        technology, ids, requirement_ids)
    technology.default_assumptions.extend((*numeric, *material_defaults))
    return {
        "added_roles": tuple(added_roles), "reused_roles": tuple(reused_roles), "added_rules": tuple(added_rules),
        "added_defaults": len(numeric) + len(material_defaults),
        "updated_defaults": tuple(updated_defaults),
        "conflicts": tuple((*conflicts, *numeric_conflicts, *material_conflicts)),
        "unresolved": tuple(dict.fromkeys((*unresolved,
            *(code for code in missing_rules if code not in alias_rules),
            *(code for code in missing_defaults if code not in completed_alias_defaults)))),
    }
