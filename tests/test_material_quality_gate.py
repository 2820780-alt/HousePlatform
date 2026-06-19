from decimal import Decimal

from app.models.catalog_product import CatalogProduct
from app.services.material_classification import assess_material_quality, classify_catalog_product


def _product(
    raw_name: str,
    raw_category: str | None = None,
    raw_brand: str | None = None,
    raw_manufacturer: str | None = None,
    external_url: str | None = None,
) -> CatalogProduct:
    return CatalogProduct(
        raw_name=raw_name,
        raw_category=raw_category,
        raw_brand=raw_brand,
        raw_manufacturer=raw_manufacturer,
        external_url=external_url,
        price=Decimal("100.00"),
        currency="RUB",
    )


def test_catalog_section_is_not_auto_material():
    product = _product(
        "Фасады для дома",
        raw_category="Фасадные материалы",
        external_url="https://example.test/fasady-dlya-doma/",
    )

    classification = classify_catalog_product(product)
    quality = assess_material_quality(product, classification)

    assert classification.rule_code == "facade_material"
    assert quality.can_create_material is False
    assert quality.needs_review is True


def test_aerated_concrete_name_region_and_quality():
    product = _product(
        "ВКБлок из газобетона Размер/мм 625x200x250 Плотность D500 в Краснодаре",
        raw_category="Газобетонные блоки",
    )

    classification = classify_catalog_product(product)
    quality = assess_material_quality(product, classification)

    assert classification.canonical_name == "Газобетонный блок 625*200*250 D500"
    assert classification.region == "Краснодар"
    assert classification.category_path is not None
    assert classification.category_path.category == "Стеновые материалы"
    assert classification.category_path.subcategory == "Газобетонные блоки"
    assert quality.can_create_material is True


def test_knauf_profile_without_size_needs_review():
    product = _product(
        "Металлические профили КНАУФ",
        raw_category="Профили для гипсокартона",
        raw_brand="КНАУФ",
        raw_manufacturer="КНАУФ",
    )

    classification = classify_catalog_product(product)
    quality = assess_material_quality(product, classification)

    assert classification.rule_code in {"baucenter_taxonomy", "drywall_profile"}
    assert quality.can_create_material is False
    assert quality.needs_review is True
