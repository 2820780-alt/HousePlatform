from app.services.material_taxonomy import (
    extract_specification_values,
    infer_baucenter_taxonomy,
)
from app.models.catalog_product import CatalogProduct
from app.services.material_classification import classify_catalog_product


def test_infer_baucenter_osb_category_and_filters():
    path = infer_baucenter_taxonomy(
        "Плита OSB влагостойкая 2440х1220х12 мм",
        "Плиты OSB",
        "https://baucenter.ru/product/plita-osb-643000283/",
    )

    assert path is not None
    assert path.section == "Листовые и плитные материалы"
    assert path.category == "OSB"
    assert path.product_type is None

    values = extract_specification_values("Плита OSB влагостойкая 2440х1220х12 мм", "Плиты OSB", path)

    assert values["length"] == "2440"
    assert values["width"] == "1220"
    assert values["height"] == "12"
    assert values["thickness"] == "12"


def test_extract_metal_tile_marketplace_filters():
    path = infer_baucenter_taxonomy(
        "Металлочерепица Монтерей 0,45 ПЭ RAL 7024 мокрый асфальт",
        "Металлочерепица",
        None,
    )

    assert path is not None
    values = extract_specification_values(
        "Металлочерепица Монтерей 0,45 ПЭ RAL 7024 мокрый асфальт",
        "Металлочерепица",
        path,
    )

    assert values["profile"] == "Монтерей"
    assert values["thickness"] == "0.45"
    assert values["coating_type"] == "Полиэстер"
    assert values["ral_color"] == "RAL 7024"


def test_extract_aerated_concrete_filters():
    path = infer_baucenter_taxonomy(
        "Газобетонный блок 625x200x250 D500",
        "Газобетонные блоки",
        None,
    )

    assert path is not None
    values = extract_specification_values("Газобетонный блок 625x200x250 D500", "Газобетонные блоки", path)

    assert values["length"] == "625"
    assert values["width"] == "200"
    assert values["height"] == "250"
    assert values["density"] == "D500"


def test_extract_presswasher_screw_filters():
    path = infer_baucenter_taxonomy(
        "Саморезы с прессшайбой 4,2х19 мм 50 шт со сверлом KOELNER",
        "Саморезы с прессшайбой по металлу",
        None,
    )

    assert path is not None
    values = extract_specification_values(
        "Саморезы с прессшайбой 4,2х19 мм 50 шт со сверлом KOELNER",
        "Саморезы с прессшайбой по металлу",
        path,
    )

    assert values["diameter"] == "4.2"
    assert values["length"] == "19"
    assert values["package_quantity"] == "50"
    assert values["tip_type"] == "со сверлом"


def test_split_dry_mix_subcategories_and_consumption():
    path = infer_baucenter_taxonomy(
        "Шпатлевка полимерная финишная 20 кг расход 1,2 кг/м2",
        "Шпатлевка полимерная",
        None,
    )

    assert path is not None
    assert path.section == "Сухие смеси"
    assert path.category == "Полимерные шпатлевки"
    assert path.product_type is None

    values = extract_specification_values(
        "Шпатлевка полимерная финишная 20 кг расход 1,2 кг/м2",
        "Шпатлевка полимерная",
        path,
    )

    assert values["package_weight"] == "20"
    assert values["consumption_rate"] == "1.2"


def test_split_gypsum_plaster_subcategory():
    path = infer_baucenter_taxonomy(
        "Штукатурка гипсовая 30 кг расход 8 кг/м2",
        "Штукатурка гипсовая",
        None,
    )

    assert path is not None
    assert path.section == "Сухие смеси"
    assert path.category == "Гипсовые штукатурки"
    assert path.product_type is None


def test_classify_technonikol_roll_waterproofing():
    product = CatalogProduct(
        raw_name="Техноэласт",
        raw_category="rulonnye bitumnye materialy",
        raw_brand="ТЕХНОНИКОЛЬ",
        raw_manufacturer="ТЕХНОНИКОЛЬ",
    )

    classification = classify_catalog_product(product)

    assert classification.category_path is not None
    assert classification.category_path.parent == "Кровля"
    assert classification.category_path.category == "Кровельные материалы"
    assert classification.category_path.subcategory == "Рулонная гидроизоляция"


def test_classify_technonikol_stone_wool():
    product = CatalogProduct(
        raw_name="Плиты из каменной ваты IZOVOL",
        raw_category="kamennaya vata izovol",
        raw_brand="ТЕХНОНИКОЛЬ",
        raw_manufacturer="ТЕХНОНИКОЛЬ",
    )

    classification = classify_catalog_product(product)

    assert classification.category_path is not None
    assert classification.category_path.parent == "Тепло/Звукоизоляция"
    assert classification.category_path.category == "Каменная вата"


def test_classify_knauf_acoustic_board():
    product = CatalogProduct(
        raw_name="Звукопоглощающая плита КНАУФ-Акустика Б",
        raw_category="listovye i plitnye materialy",
        raw_brand="Knauf",
        raw_manufacturer="Knauf",
    )

    classification = classify_catalog_product(product)

    assert classification.category_path is not None
    assert classification.category_path.parent == "Тепло/Звукоизоляция"
    assert classification.category_path.category == "Акустические плиты"


def test_vkblock_dry_mix_wins_over_gazobeton_keyword():
    product = CatalogProduct(
        raw_name="ВК-100 Клей монтажный для кладки из ячеистого бетона ГОСТ 31357-2007 в Краснодаре",
        raw_category="vkblok iz gazobetona",
        raw_brand="ВКБлок",
        raw_manufacturer="ВКБлок",
    )

    classification = classify_catalog_product(product)

    assert classification.canonical_name == "Клей для кладки газобетона ВК-100"
    assert classification.category_path is not None
    assert classification.category_path.parent == "Сухие смеси"
    assert classification.category_path.category == "Клеи для кладки"
    assert classification.category_path.subcategory is None


def test_led_lamp_is_not_incandescent():
    product = CatalogProduct(
        raw_name="Лампа светодиод. 18W 4000К 1600Лм G13 T8 220V (1200мм.)",
        raw_category="Освещение",
        raw_brand="",
        raw_manufacturer="",
    )

    classification = classify_catalog_product(product)

    assert classification.canonical_name.startswith("Лампа светодиодная")
    assert "накаливания" not in classification.canonical_name.lower()
