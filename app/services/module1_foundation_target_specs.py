"""User-specified foundation targets. Values remain unverified M1 candidates."""

from __future__ import annotations


def _candidate(code, title, *, unit=None, category_slug=None, fields=None, standard=None, missing=()):
    properties = [("registry_code", code), ("declared_source", "USER_PROVIDED_SPRINT_SPECIFICATION")]
    if standard:
        properties.append(("declared_standard", standard))
    return {
        "key": code.lower(), "title": title, "group": "unclassified", "category_hint": title,
        "unit": unit, "expected": fields or {}, "properties": tuple(properties),
        "category_slug": category_slug,
        "missing": ("Проверка технической идентичности и области применения", *missing),
    }


def additional_targets():
    """The list is an inventory of draft identities, not verified products or offers."""
    items = []
    for code, strength, water, frost, mobility in (
        ("BT-01", "B20", "W4", "100", "P3"), ("BT-02", "B25", "W6", "150", "P4"),
        ("BT-03", "B25", "W8", "150", "P4"), ("BT-04", "B30", "W8", "200", "P4"),
    ):
        item = _candidate(code, f"БСТ {strength} {water} F1 {frost} {mobility}", unit="m3",
                          category_slug="foundation-structural-concrete", standard="ГОСТ 7473-2026",
                          fields={"mixture_type": "БСТ", "concrete_class": strength,
                                  "water_resistance": water, "frost_type": "F1",
                                  "frost_cycles": frost, "mobility_class": mobility},
                          missing=("Паспорт смеси и условия применения",))
        items.append(item)
    for code, strength in (("RM-01", "М100"), ("RM-02", "М150")):
        items.append(_candidate(code, f"Раствор цементный кладочный {strength}, Пк3", unit="m3",
            category_slug="foundation-masonry-mortar", standard="ГОСТ Р 58766-2019",
            fields={"strength_mark": strength, "mobility_mark": "Пк3"},
            missing=("Морозостойкость и паспортные характеристики раствора",)))

    blocks = (("24.3.6", 2380, 300), ("24.4.6", 2380, 400), ("24.5.6", 2380, 500),
              ("24.6.6", 2380, 600), ("12.4.6", 1180, 400), ("12.5.6", 1180, 500),
              ("12.6.6", 1180, 600), ("9.3.6", 880, 300), ("9.4.6", 880, 400),
              ("9.5.6", 880, 500), ("9.6.6", 880, 600))
    for number, (mark, length, width) in enumerate(blocks, 1):
        items.append(_candidate(f"FBS-{number:02d}", f"ФБС {mark}-Т", unit="piece",
            category_slug="foundation-fbs-blocks", standard="ГОСТ 13579-2018",
            fields={"declared_mark": f"ФБС {mark}-Т", "length_mm": str(length),
                    "width_mm": str(width), "height_mm": "580", "concrete_type": "Т"},
            missing=("Проверка марки и размеров по стандарту", "Масса по паспорту или стандарту")))

    slabs = (("8.12", (1, 3, 4)), ("8.24", (1, 3, 4)), ("10.12", (1, 2, 3, 4)),
             ("10.24", (1, 2, 3, 4)), ("12.12", (1, 2, 3, 4)), ("12.24", (1, 2, 3, 4)))
    index = 0
    for size, groups in slabs:
        width, length = size.split(".")
        for group in groups:
            index += 1
            mark = f"ФЛ{size}-{group}"
            items.append(_candidate(f"FL-{index:02d}", mark, unit="piece",
                category_slug="foundation-fl-slabs", standard="ГОСТ 13580-2021",
                fields={"declared_mark": mark, "width_mm": str(int(width) * 100),
                        "length_mm": "1180" if length == "12" else "2380", "load_group": str(group)},
                missing=("Проверка полной марки и группы по стандарту", "Высота и масса по стандарту или паспорту")))

    xps = ((30, 200), (50, 200), (100, 200), (50, 300), (80, 300),
           (100, 300), (120, 300), (150, 300), (100, 500), (150, 500))
    for index, (thickness, strength) in enumerate(xps, 1):
        items.append(_candidate(f"XPS-{index:02d}", f"XPS {thickness} мм CS(10/Y){strength}", unit="m2",
            category_slug="foundation-xps-insulation", standard="ГОСТ 32310-2020",
            fields={"thickness_mm": str(thickness), "cs_10_y_kpa": str(strength)},
            missing=("Длительная нагрузка, теплопроводность, водопоглощение и размеры изделия",)))

    groups = (
        ("BASE", ("Песок для подготовки основания", "Щебень фракции 5–20 мм", "Щебень фракции 20–40 мм",
                  "Геотекстиль нетканый 200 г/м²", "Геотекстиль нетканый 300 г/м²"), None),
        ("FORM", ("Фанера ламинированная 18 мм", "Фанера ламинированная 21 мм", "Доска 25×100 мм",
                  "Доска 40×150 мм", "Доска 50×150 мм", "Брус 50×50 мм", "Брус 50×100 мм",
                  "Стяжные элементы опалубки", "Крепёж опалубки", "Разделительный состав для опалубки"), "foundation-formwork"),
        ("ARM-AUX", ("Вязальная проволока Ø1,2 мм", "Вязальная проволока Ø1,4 мм",
                     "Фиксатор защитного слоя 25 мм", "Фиксатор защитного слоя 35 мм",
                     "Фиксатор защитного слоя 40 мм", "Фиксатор защитного слоя 50 мм",
                     "Поддерживающий элемент верхней сетки"), None),
        ("WPR", ("Битумно-полимерная мастика для подземной гидроизоляции", "Битумный праймер для системы WPR-01",
                 "Рулонная битумно-полимерная гидроизоляция 4 мм, полиэфирная основа, наплавляемая",
                 "Гидроизоляционная мембрана ПВХ-П 1,5 мм, сварные соединения",
                 "Защитная профилированная мембрана HDPE, выступ 8 мм", "Гидрошпонка рабочего шва",
                 "Гидрошпонка деформационного шва", "Лента герметизации примыканий",
                 "Герметик инженерных проходок", "Защитный материал гидроизоляционного покрытия"), None),
        ("DRN", ("Перфорированная дренажная труба DN110", "Перфорированная дренажная труба DN160",
                 "Соединительная муфта по диаметру", "Дренажный тройник по диаметру", "Дренажный отвод по диаметру",
                 "Дренажный смотровой колодец", "Комплект подключения и герметизации дренажа"), None),
        ("PEN", ("Гильза ввода коммуникаций DN110", "Гильза ввода коммуникаций DN160",
                 "Модульная система герметизации ввода", "Материалы герметизации проходки"), None),
    )
    for prefix, titles, category in groups:
        for number, title in enumerate(titles, 1):
            items.append(_candidate(f"{prefix}-{number:02d}", title, category_slug=category,
                missing=("Технические характеристики конкретного изделия и единица продажи",)))

    screw = (
        ("Труба Ø89 мм, длина 2500 мм, стенка 4 мм, лопасть Ø250 мм", "89", "2500", "250"),
        ("Труба Ø108 мм, длина 2500 мм, стенка 4 мм, лопасть Ø300 мм", "108", "2500", "300"),
        ("Труба Ø108 мм, длина 3000 мм, стенка 4 мм, лопасть Ø300 мм", "108", "3000", "300"),
    )
    for number, (title, diameter, length, blade) in enumerate(screw, 1):
        items.append(_candidate(f"PILE-S-{number:02d}", f"Винтовая свая: {title}", unit="piece",
            category_slug="foundation-screw-piles", fields={"tube_diameter_mm": diameter,
                "length_mm": length, "wall_thickness_mm": "4", "blade_diameter_mm": blade},
            missing=("Наконечник, сталь, сварка, покрытие и паспорт изделия",)))
    for number, title in ((4, "Оголовок для трубы Ø89 мм"), (5, "Оголовок для трубы Ø108 мм"),
                          (6, "Соединительные элементы винтовой свайной системы")):
        items.append(_candidate(f"PILE-S-{number:02d}", title, unit="piece",
                                missing=("Полная спецификация и совместимость соединения",)))
    for number, length in ((1, 6000), (2, 8000)):
        items.append(_candidate(f"PILE-RC-{number:02d}", f"Забивная ЖБ свая типа С 300×300×{length} мм",
            unit="piece", category_slug="foundation-rc-piles", standard="ГОСТ 19804-2021",
            fields={"section_width_mm": "300", "section_height_mm": "300", "length_mm": str(length)},
            missing=("Полная заводская марка, исполнение, армирование и паспорт",)))
    return tuple(items)
