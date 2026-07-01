from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd


TEMPLATE_BASENAME = "ATOM_supplier_price_template"

REQUIRED_COLUMNS = [
    "Название товара",
    "Артикул поставщика",
    "Категория поставщика",
    "Единица измерения",
    "Цена",
    "Валюта",
    "Наличие",
    "Регион",
    "Город",
    "Дата актуальности цены",
]

OPTIONAL_COLUMNS = [
    "Бренд",
    "Производитель",
    "ГОСТ / ТУ",
    "Размер",
    "Марка / класс",
    "Фасовка",
    "Вес",
    "Объем",
    "Ссылка на товар",
    "Ссылка на сертификат",
    "Ссылка на техлист",
    "Условия доставки",
    "Срок действия цены",
    "Комментарий",
]

STANDARD_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

FIELD_COLUMN_ALIASES: dict[str, list[str]] = {
    "name": ["Название товара", "name", "description", "item", "product", "material", "наименование", "название", "товар", "материал"],
    "sku": ["Артикул поставщика", "sku", "article", "артикул", "код", "код товара"],
    "category": ["Категория поставщика", "category", "категория", "группа", "раздел"],
    "unit": ["Единица измерения", "unit", "ед", "ед.", "единица", "единица измерения"],
    "price": ["Цена", "price", "cost", "цена", "стоимость", "прайс"],
    "currency": ["Валюта", "currency", "валюта"],
    "availability": ["Наличие", "availability", "остаток", "наличие", "доступность"],
    "region": ["Регион", "region", "регион", "край", "область"],
    "city": ["Город", "city", "город", "населенный пункт"],
    "price_date": ["Дата актуальности цены", "price_date", "дата цены", "дата актуальности", "дата актуальности цены"],
    "brand": ["Бренд", "brand", "бренд", "марка"],
    "manufacturer": ["Производитель", "manufacturer", "vendor", "производитель", "изготовитель"],
    "gost_tu": ["ГОСТ / ТУ", "гост", "ту", "gost", "tu"],
    "size": ["Размер", "size", "размер", "габариты"],
    "grade_class": ["Марка / класс", "марка", "класс", "grade", "class"],
    "packing": ["Фасовка", "packing", "package", "фасовка", "упаковка"],
    "weight": ["Вес", "weight", "вес", "масса"],
    "volume": ["Объем", "Объём", "volume", "объем", "объём"],
    "product_url": ["Ссылка на товар", "product_url", "url", "ссылка"],
    "certificate_url": ["Ссылка на сертификат", "certificate_url", "сертификат"],
    "tech_sheet_url": ["Ссылка на техлист", "tech_sheet_url", "техлист", "технический лист"],
    "delivery_terms": ["Условия доставки", "delivery_terms", "доставка", "условия доставки"],
    "price_valid_until": ["Срок действия цены", "valid_until", "срок действия цены"],
    "comment": ["Комментарий", "comment", "комментарий", "примечание"],
}

KNOWN_UNITS = {
    "шт",
    "штука",
    "м",
    "пог.м",
    "погонный метр",
    "м2",
    "м²",
    "м3",
    "м³",
    "кг",
    "т",
    "л",
    "уп",
    "упак",
    "упаковка",
    "меш",
    "мешок",
    "лист",
    "рулон",
    "компл",
    "поддон",
}

KNOWN_CURRENCIES = {"RUB", "RUR", "₽", "руб", "руб.", "р."}


@dataclass
class SupplierPriceStandardReport:
    column_mapping: dict[str, str | None]
    missing_required_columns: list[str] = field(default_factory=list)
    unknown_columns: list[str] = field(default_factory=list)
    mapping_preview: dict[str, str | None] = field(default_factory=dict)
    valid: bool = True


def analyze_supplier_price_columns(columns: list[Any]) -> SupplierPriceStandardReport:
    normalized_columns = {normalize_column_name(column): str(column) for column in columns}
    column_mapping: dict[str, str | None] = {}
    mapped_columns: set[str] = set()

    for field_name, aliases in FIELD_COLUMN_ALIASES.items():
        matched = None
        for alias in aliases:
            key = normalize_column_name(alias)
            if key in normalized_columns:
                matched = normalized_columns[key]
                mapped_columns.add(matched)
                break
        column_mapping[field_name] = matched

    required_by_field = {
        "name": "Название товара",
        "sku": "Артикул поставщика",
        "category": "Категория поставщика",
        "unit": "Единица измерения",
        "price": "Цена",
        "currency": "Валюта",
        "availability": "Наличие",
        "region": "Регион",
        "city": "Город",
        "price_date": "Дата актуальности цены",
    }
    missing_required = [
        display_name
        for field_name, display_name in required_by_field.items()
        if not column_mapping.get(field_name)
    ]
    known_columns = set(STANDARD_COLUMNS)
    unknown_columns = [
        str(column)
        for column in columns
        if str(column) not in known_columns and str(column) not in mapped_columns
    ]
    return SupplierPriceStandardReport(
        column_mapping=column_mapping,
        missing_required_columns=missing_required,
        unknown_columns=unknown_columns,
        mapping_preview={field: column for field, column in column_mapping.items() if column},
        valid=not missing_required,
    )


def supplier_price_template_rows() -> list[dict[str, str]]:
    return [
        {
            "Название товара": "Газоблок D500 600x300x200",
            "Артикул поставщика": "GB-D500-600-300-200",
            "Категория поставщика": "Стеновые материалы / Газобетон",
            "Единица измерения": "шт",
            "Цена": "245.50",
            "Валюта": "RUB",
            "Наличие": "в наличии",
            "Регион": "Краснодарский край",
            "Город": "Краснодар",
            "Дата актуальности цены": date.today().isoformat(),
            "Бренд": "Пример",
            "Производитель": "Пример Завод",
            "ГОСТ / ТУ": "ГОСТ 31360-2007",
            "Размер": "600x300x200",
            "Марка / класс": "D500",
            "Фасовка": "поддон",
            "Вес": "",
            "Объем": "0.036",
            "Ссылка на товар": "https://example.ru/product/gb-d500",
            "Ссылка на сертификат": "https://example.ru/docs/certificate.pdf",
            "Ссылка на техлист": "https://example.ru/docs/tech-sheet.pdf",
            "Условия доставки": "доставка по Краснодару",
            "Срок действия цены": "",
            "Комментарий": "строка-пример, можно удалить",
        }
    ]


def build_supplier_price_template_csv() -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=STANDARD_COLUMNS, delimiter=";")
    writer.writeheader()
    writer.writerows(supplier_price_template_rows())
    return output.getvalue().encode("utf-8-sig")


def build_supplier_price_template_xlsx() -> bytes:
    output = io.BytesIO()
    dataframe = pd.DataFrame(supplier_price_template_rows(), columns=STANDARD_COLUMNS)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Прайс")
        rules = pd.DataFrame(
            [
                {"Поле": column, "Статус": "обязательное" if column in REQUIRED_COLUMNS else "желательное"}
                for column in STANDARD_COLUMNS
            ]
        )
        rules.to_excel(writer, index=False, sheet_name="Описание")
    return output.getvalue()


def write_supplier_price_templates(directory: str | Path) -> tuple[Path, Path]:
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    csv_path = target_dir / f"{TEMPLATE_BASENAME}.csv"
    xlsx_path = target_dir / f"{TEMPLATE_BASENAME}.xlsx"
    csv_path.write_bytes(build_supplier_price_template_csv())
    xlsx_path.write_bytes(build_supplier_price_template_xlsx())
    return csv_path, xlsx_path


def unit_needs_review(unit: str | None) -> bool:
    if not unit:
        return True
    return normalize_column_name(unit) not in {normalize_column_name(value) for value in KNOWN_UNITS}


def region_needs_review(region: str | None, city: str | None) -> bool:
    return not bool((region or "").strip() and (city or "").strip())


def normalize_currency(currency: str | None) -> str | None:
    if not currency:
        return None
    value = currency.strip()
    if value in {"₽", "руб", "руб.", "р.", "RUR"}:
        return "RUB"
    if value.upper() in KNOWN_CURRENCIES:
        return value.upper()
    return value


def supplier_price_standard_validation_error(parse_result: Any) -> str | None:
    missing = list(getattr(parse_result, "missing_required_columns", []) or [])
    if not missing:
        return None
    return (
        "Файл не соответствует стандарту прайса АТОМ. "
        "Нет обязательных колонок: "
        + ", ".join(missing)
        + ". Используйте шаблон ATOM_supplier_price_template.csv или ATOM_supplier_price_template.xlsx."
    )


def normalize_column_name(value: Any) -> str:
    return " ".join(str(value).strip().lower().replace("\xa0", " ").split())


__all__ = [
    "TEMPLATE_BASENAME",
    "REQUIRED_COLUMNS",
    "OPTIONAL_COLUMNS",
    "STANDARD_COLUMNS",
    "SupplierPriceStandardReport",
    "analyze_supplier_price_columns",
    "supplier_price_template_rows",
    "build_supplier_price_template_csv",
    "build_supplier_price_template_xlsx",
    "write_supplier_price_templates",
    "unit_needs_review",
    "region_needs_review",
    "normalize_currency",
    "supplier_price_standard_validation_error",
    "normalize_column_name",
]
