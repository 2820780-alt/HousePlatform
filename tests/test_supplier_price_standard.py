from decimal import Decimal

from app.processing.file_parser import parse_file
from app.processing.file_validator import FileType
from app.services.supplier_price_standard import (
    REQUIRED_COLUMNS,
    build_supplier_price_template_csv,
    build_supplier_price_template_xlsx,
    supplier_price_standard_validation_error,
)


def test_standard_supplier_price_csv_parses_required_fields():
    content = (
        "Название товара;Артикул поставщика;Категория поставщика;Единица измерения;Цена;Валюта;Наличие;Регион;Город;Дата актуальности цены\n"
        "Газоблок D500;GB-1;Газобетон;шт;245,50;RUB;в наличии;Краснодарский край;Краснодар;2026-07-01\n"
    ).encode("utf-8")

    result = parse_file(content, FileType.CSV)

    assert result.standard_valid is True
    assert result.missing_required_columns == []
    assert result.rows[0].original_name == "Газоблок D500"
    assert result.rows[0].sku == "GB-1"
    assert result.rows[0].supplier_category == "Газобетон"
    assert result.rows[0].original_price == Decimal("245.50")
    assert result.rows[0].currency == "RUB"
    assert result.rows[0].region == "Краснодарский край"
    assert result.rows[0].city == "Краснодар"
    assert result.rows[0].price_date == "2026-07-01"
    assert result.rows[0].normalized_title == "газобетонный блок d500"
    assert result.rows[0].search_title == "газобетонный блок d500"
    assert result.rows[0].normalization_direction == "WALL_MATERIALS"
    assert "missing_size" in result.rows[0].review_reasons


def test_missing_required_columns_returns_validation_error():
    content = "Название товара;Цена;Единица измерения\nOSB;1200;лист\n".encode("utf-8")

    result = parse_file(content, FileType.CSV)

    assert result.standard_valid is False
    assert "Артикул поставщика" in result.missing_required_columns
    assert "Регион" in result.missing_required_columns
    assert "ATOM_supplier_price_template" in supplier_price_standard_validation_error(result)


def test_unknown_columns_are_kept_for_mapping_preview():
    content = (
        "Название товара;Артикул поставщика;Категория поставщика;Единица измерения;Цена;Валюта;Наличие;Регион;Город;Дата актуальности цены;Складской код\n"
        "Кирпич;BR-1;Кирпич;шт;30;RUB;да;Краснодарский край;Краснодар;2026-07-01;A-77\n"
    ).encode("utf-8")

    result = parse_file(content, FileType.CSV)

    assert result.standard_valid is True
    assert result.mapping_preview["name"] == "Название товара"
    assert "Складской код" in result.unknown_columns
    assert result.rows[0].raw_data["Складской код"] == "A-77"


def test_unknown_unit_and_missing_region_go_to_review_state():
    content = (
        "Название товара;Артикул поставщика;Категория поставщика;Единица измерения;Цена;Валюта;Наличие;Регион;Город;Дата актуальности цены\n"
        "Материал;M-1;Прочее;коробищи;100;RUB;да;;;2026-07-01\n"
    ).encode("utf-8")

    row = parse_file(content, FileType.CSV).rows[0]

    assert row.unit_review_status == "needs_unit_review"
    assert row.region_review_status == "needs_region_review"
    assert "Единица измерения не распознана" in row.review_reasons
    assert "Регион или город не указаны" in row.review_reasons


def test_service_or_tool_row_is_marked_as_ignored_candidate():
    content = (
        "Название товара;Артикул поставщика;Категория поставщика;Единица измерения;Цена;Валюта;Наличие;Регион;Город;Дата актуальности цены\n"
        "Аренда дрели;S-1;Инструмент;шт;500;RUB;да;Краснодарский край;Краснодар;2026-07-01\n"
    ).encode("utf-8")

    row = parse_file(content, FileType.CSV).rows[0]

    assert row.ignored_candidate_status == "ignored_candidate"
    assert "tool_product_not_material" in row.normalization_profile["ignored_candidate_reasons"]


def test_template_builders_include_required_columns():
    csv_bytes = build_supplier_price_template_csv()
    xlsx_bytes = build_supplier_price_template_xlsx()

    csv_text = csv_bytes.decode("utf-8-sig")
    for column in REQUIRED_COLUMNS:
        assert column in csv_text
    assert len(xlsx_bytes) > 1000
