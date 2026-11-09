from __future__ import annotations

from app.services.module2_content_catalog import category_tree


# Navigation labels and descriptions do not replace the M2 taxonomy.
HOUSE_ZONES = (
    ("preparation", "PREPARATION", "Подготовка основания", "Работы по подготовке площадки и основания перед строительством."),
    ("foundations", "FOUNDATIONS", "Фундамент и подземная часть", "Фундамент воспринимает нагрузки здания и передаёт их основанию. В разделе представлены ленточные, плитные, свайные и другие системы."),
    ("walls", "WALLS", "Стены и каркас", "Несущие стены и каркас воспринимают нагрузки и формируют конструкцию дома."),
    ("partitions", "PARTITIONS", "Внутренние перегородки", "Перегородки разделяют внутреннее пространство дома на помещения."),
    ("floors", "FLOORS_AND_STAIRS", "Перекрытия, полы и лестницы", "Перекрытия разделяют этажи, а лестницы связывают уровни дома."),
    ("roof", "ROOF", "Крыша и кровля", "Крыша перекрывает дом, а кровельная система защищает его от осадков."),
    ("facade", "FACADE_AND_OPENINGS", "Фасад, окна и двери", "Фасад и наружные заполнения отделяют внутреннее пространство от улицы."),
    ("site", "SITE_WORKS", "Работы вокруг дома", "Наружные работы включают устройство прилегающих к дому элементов и покрытий."),
    ("rough", "INTERIOR_ROUGH", "Черновая отделка", "Черновая отделка подготавливает поверхности к последующим слоям."),
    ("finish", "INTERIOR_FINISH", "Чистовая отделка", "Чистовые покрытия формируют вид и рабочую поверхность помещений."),
    ("water", "WATER_AND_SEWER", "Водоснабжение и канализация", "Системы подают воду и отводят сточные воды из дома."),
    ("heating", "HEATING_AND_DHW", "Отопление и горячая вода", "Системы отопления и горячего водоснабжения обеспечивают тепло и горячую воду."),
    ("ventilation", "VENTILATION_AND_AC", "Вентиляция и кондиционирование", "Вентиляция обеспечивает воздухообмен, кондиционирование помогает регулировать температуру."),
    ("electrical", "ELECTRICAL_AND_AUTOMATION", "Электрика и автоматика", "Электрические сети и автоматика обеспечивают питание и управление оборудованием."),
    ("gas", "GAS_AND_COMBUSTION", "Газ и дымоходы", "Раздел объединяет газовое оборудование, дымоходы и связанные сгорающие системы."),
    ("final", "FINAL_INSTALLATION", "Финальное оснащение", "Завершающее оснащение включает установку предусмотренных элементов дома."),
)

ZONE_GROUPS = (
    ("Фундамент", ("foundations", "preparation")),
    ("Стены и каркас", ("walls", "partitions")),
    ("Перекрытия и лестницы", ("floors",)),
    ("Крыша и кровля", ("roof",)),
    ("Фасад, окна и двери", ("facade",)),
    ("Отделка", ("rough", "finish", "final")),
    ("Инженерные системы", ("water", "heating", "ventilation", "electrical", "gas")),
    ("Работы вокруг дома", ("site",)),
)


def home_zones(categories):
    public = {row["category"].code: row["category"] for row in category_tree(categories, public=True)}
    return tuple({
        "part": part, "category_code": code, "name": name,
        "description": description,
        "url": f"/api/v1/module2/encyclopedia/categories/{code}" if code in public else None,
    } for part, code, name, description in HOUSE_ZONES)
