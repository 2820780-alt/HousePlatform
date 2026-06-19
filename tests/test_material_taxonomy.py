from app.services.material_taxonomy import (
    extract_specification_values,
    infer_baucenter_taxonomy,
)


def test_infer_baucenter_osb_category_and_filters():
    path = infer_baucenter_taxonomy(
        "Плита OSB влагостойкая 2440х1220х12 мм",
        "Плиты OSB",
        "https://baucenter.ru/product/plita-osb-643000283/",
    )

    assert path is not None
    assert path.section == "Строительные материалы"
    assert path.category == "Листовые материалы"
    assert path.product_type == "OSB"

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
    assert path.category == "Сухие смеси"
    assert path.product_type == "Полимерные шпатлевки"

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
    assert path.category == "Сухие смеси"
    assert path.product_type == "Гипсовые штукатурки"
