from __future__ import annotations

import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import pandas as pd

from app.processing.file_validator import FileType
from app.services.material_normalization_rules import normalize_material_title
from app.services.supplier_price_standard import (
    analyze_supplier_price_columns,
    normalize_currency,
    region_needs_review,
    unit_needs_review,
)


@dataclass
class ParsedRow:
    row_number: int
    original_name: str | None
    original_price: Decimal | None
    original_unit: str | None
    quantity: Decimal | None
    total_sum: Decimal | None
    sku: str | None
    brand: str | None
    manufacturer: str | None
    supplier_category: str | None = None
    currency: str | None = None
    availability: str | None = None
    region: str | None = None
    city: str | None = None
    price_date: str | None = None
    gost_tu: str | None = None
    size: str | None = None
    grade_class: str | None = None
    packing: str | None = None
    weight: Decimal | None = None
    volume: Decimal | None = None
    product_url: str | None = None
    certificate_url: str | None = None
    tech_sheet_url: str | None = None
    delivery_terms: str | None = None
    price_valid_until: str | None = None
    comment: str | None = None
    unit_review_status: str | None = None
    region_review_status: str | None = None
    normalization_review_status: str | None = None
    ignored_candidate_status: str | None = None
    normalized_title: str | None = None
    search_title: str | None = None
    normalization_direction: str | None = None
    normalization_profile: dict = field(default_factory=dict)
    review_reasons: list[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    rows: list[ParsedRow]
    errors: list[str]
    total_rows_found: int
    sheets_parsed: int = 1
    column_mapping: dict[str, str | None] = field(default_factory=dict)
    missing_required_columns: list[str] = field(default_factory=list)
    unknown_columns: list[str] = field(default_factory=list)
    mapping_preview: dict[str, str | None] = field(default_factory=dict)
    standard_valid: bool = True


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(" ", "").replace("\xa0", "").replace(",", ".")
    for token in ["rub", "руб", "р.", "$", "usd", "eur"]:
        text = text.lower().replace(token, "")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_cols = {str(c).lower().strip(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower_cols:
            return lower_cols[candidate.lower()]
    return None


def _detect_columns(df: pd.DataFrame) -> dict[str, str | None]:
    standard_report = analyze_supplier_price_columns([str(column) for column in df.columns])
    detected = {
        "name": _find_column(df, [
            "name", "description", "item", "product", "material",
            "наименование", "название", "товар", "материал",
        ]),
        "price": _find_column(df, [
            "price", "cost", "цена", "стоимость", "прайс",
        ]),
        "unit": _find_column(df, [
            "unit", "ед", "ед.", "единица", "единица измерения",
        ]),
        "quantity": _find_column(df, [
            "qty", "quantity", "количество", "кол-во", "объем", "объём",
        ]),
        "total_sum": _find_column(df, [
            "total", "amount", "сумма", "итого",
        ]),
        "sku": _find_column(df, [
            "sku", "article", "артикул", "код", "код товара",
        ]),
        "brand": _find_column(df, [
            "brand", "бренд", "марка",
        ]),
        "manufacturer": _find_column(df, [
            "manufacturer", "vendor", "производитель", "изготовитель",
        ]),
    }
    for field_name, column_name in standard_report.column_mapping.items():
        if column_name:
            detected[field_name] = column_name
    return detected


def _df_to_parsed_rows(df: pd.DataFrame, row_offset: int = 0) -> tuple[list[ParsedRow], list[str], dict]:
    rows: list[ParsedRow] = []
    errors: list[str] = []
    standard_report = analyze_supplier_price_columns([str(column) for column in df.columns])
    if df.empty:
        return rows, errors, _report_dict(standard_report)

    col_map = _detect_columns(df)
    name_col = col_map["name"] or df.columns[0]

    for i, (_, row) in enumerate(df.iterrows()):
        row_num = row_offset + i + 1
        raw_name = row.get(name_col) if name_col else None
        if raw_name is None or pd.isna(raw_name) or str(raw_name).strip() == "":
            continue

        name = str(raw_name).strip()
        price = _to_decimal(row.get(col_map["price"]) if col_map["price"] else None)

        if price is None:
            for col in df.columns:
                if col == name_col:
                    continue
                value = _to_decimal(row.get(col))
                if value is not None and value > 0:
                    price = value
                    break

        unit = _safe_str(row.get(col_map["unit"])) if col_map.get("unit") else None
        region = _safe_str(row.get(col_map["region"])) if col_map.get("region") else None
        city = _safe_str(row.get(col_map["city"])) if col_map.get("city") else None
        brand = _safe_str(row.get(col_map["brand"])) if col_map["brand"] else None
        manufacturer = _safe_str(row.get(col_map["manufacturer"])) if col_map["manufacturer"] else None
        supplier_category = _safe_str(row.get(col_map["category"])) if col_map.get("category") else None
        availability = _safe_str(row.get(col_map["availability"])) if col_map.get("availability") else None
        review_reasons: list[str] = []
        unit_review_status = None
        region_review_status = None
        normalization_review_status = None
        if unit_needs_review(unit):
            unit_review_status = "needs_unit_review"
            review_reasons.append("Единица измерения не распознана")
        if region_needs_review(region, city):
            region_review_status = "needs_region_review"
            review_reasons.append("Регион или город не указаны")
        normalization = normalize_material_title(
            name,
            brand=brand,
            manufacturer=manufacturer,
            category=supplier_category,
            unit=unit,
            price=price,
            availability=availability,
            region=region,
            city=city,
        )
        if normalization.needs_review_reasons:
            normalization_review_status = "needs_review"
            for reason in normalization.needs_review_reasons:
                if reason not in review_reasons:
                    review_reasons.append(reason)

        rows.append(ParsedRow(
            row_number=row_num,
            original_name=name,
            original_price=price,
            original_unit=unit,
            quantity=_to_decimal(row.get(col_map.get("quantity")) if col_map.get("quantity") else None),
            total_sum=_to_decimal(row.get(col_map["total_sum"]) if col_map["total_sum"] else None),
            sku=_safe_str(row.get(col_map["sku"])) if col_map["sku"] else None,
            brand=brand,
            manufacturer=manufacturer,
            supplier_category=supplier_category,
            currency=normalize_currency(_safe_str(row.get(col_map["currency"])) if col_map.get("currency") else None),
            availability=availability,
            region=region,
            city=city,
            price_date=_safe_str(row.get(col_map["price_date"])) if col_map.get("price_date") else None,
            gost_tu=_safe_str(row.get(col_map["gost_tu"])) if col_map.get("gost_tu") else None,
            size=_safe_str(row.get(col_map["size"])) if col_map.get("size") else None,
            grade_class=_safe_str(row.get(col_map["grade_class"])) if col_map.get("grade_class") else None,
            packing=_safe_str(row.get(col_map["packing"])) if col_map.get("packing") else None,
            weight=_to_decimal(row.get(col_map["weight"]) if col_map.get("weight") else None),
            volume=_to_decimal(row.get(col_map["volume"]) if col_map.get("volume") else None),
            product_url=_safe_str(row.get(col_map["product_url"])) if col_map.get("product_url") else None,
            certificate_url=_safe_str(row.get(col_map["certificate_url"])) if col_map.get("certificate_url") else None,
            tech_sheet_url=_safe_str(row.get(col_map["tech_sheet_url"])) if col_map.get("tech_sheet_url") else None,
            delivery_terms=_safe_str(row.get(col_map["delivery_terms"])) if col_map.get("delivery_terms") else None,
            price_valid_until=_safe_str(row.get(col_map["price_valid_until"])) if col_map.get("price_valid_until") else None,
            comment=_safe_str(row.get(col_map["comment"])) if col_map.get("comment") else None,
            unit_review_status=unit_review_status,
            region_review_status=region_review_status,
            normalization_review_status=normalization_review_status,
            ignored_candidate_status=normalization.ignored_candidate_status,
            normalized_title=normalization.normalized_title,
            search_title=normalization.search_title,
            normalization_direction=normalization.direction_code,
            normalization_profile=normalization.model_dump(),
            review_reasons=review_reasons,
            raw_data={str(k): str(v) for k, v in row.items() if not pd.isna(v) and str(v).strip()},
        ))

    return rows, errors, _report_dict(standard_report)


def _safe_str(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def parse_excel(content: bytes) -> ParseResult:
    rows: list[ParsedRow] = []
    errors: list[str] = []
    row_offset = 0
    sheets_parsed = 0

    try:
        excel_file = pd.ExcelFile(io.BytesIO(content))
    except Exception as exc:
        return ParseResult(rows=[], errors=[f"Could not open XLSX: {exc}"], total_rows_found=0)

    for sheet_name in excel_file.sheet_names:
        sheets_parsed += 1
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            sheet_rows, sheet_errors, sheet_report = _df_to_parsed_rows(df, row_offset)
            rows.extend(sheet_rows)
            errors.extend([f"{sheet_name}: {error}" for error in sheet_errors])
            if sheet_report.get("missing_required_columns"):
                errors.extend([
                    f"{sheet_name}: missing required column: {column}"
                    for column in sheet_report["missing_required_columns"]
                ])
            row_offset += len(df)
            if sheets_parsed == 1:
                report = sheet_report
        except Exception as exc:
            errors.append(f"{sheet_name}: {exc}")

    report = locals().get("report", {})
    return ParseResult(
        rows=rows,
        errors=errors,
        total_rows_found=len(rows),
        sheets_parsed=sheets_parsed,
        column_mapping=report.get("column_mapping", {}),
        missing_required_columns=report.get("missing_required_columns", []),
        unknown_columns=report.get("unknown_columns", []),
        mapping_preview=report.get("mapping_preview", {}),
        standard_valid=report.get("valid", True),
    )


def parse_csv(content: bytes) -> ParseResult:
    errors: list[str] = []
    encodings = ["utf-8", "utf-8-sig", "cp1251", "latin-1"]
    separators = [",", ";", "\t", "|"]
    df = None
    fallback_df = None

    for encoding in encodings:
        for sep in separators:
            try:
                candidate = pd.read_csv(io.BytesIO(content), encoding=encoding, sep=sep, on_bad_lines="skip")
                if candidate.shape[1] >= 2 and len(candidate) > 0:
                    df = candidate
                    break
                if fallback_df is None and candidate.shape[1] >= 1 and len(candidate) > 0:
                    fallback_df = candidate
            except Exception:
                continue
        if df is not None:
            break

    if df is None:
        df = fallback_df

    if df is None:
        return ParseResult(
            rows=[],
            errors=["Could not parse CSV. Check encoding and delimiter."],
            total_rows_found=0,
        )

    rows, errors, report = _df_to_parsed_rows(df)
    errors.extend([f"missing required column: {column}" for column in report["missing_required_columns"]])
    return ParseResult(
        rows=rows,
        errors=errors,
        total_rows_found=len(rows),
        sheets_parsed=1,
        column_mapping=report["column_mapping"],
        missing_required_columns=report["missing_required_columns"],
        unknown_columns=report["unknown_columns"],
        mapping_preview=report["mapping_preview"],
        standard_valid=report["valid"],
    )


def parse_file(content: bytes, file_type: FileType) -> ParseResult:
    if file_type == FileType.XLSX:
        return parse_excel(content)
    if file_type == FileType.CSV:
        return parse_csv(content)
    return ParseResult(
        rows=[],
        errors=[f"Unsupported MVP file type: {file_type}"],
        total_rows_found=0,
    )


def _report_dict(report) -> dict:
    return {
        "column_mapping": report.column_mapping,
        "missing_required_columns": report.missing_required_columns,
        "unknown_columns": report.unknown_columns,
        "mapping_preview": report.mapping_preview,
        "valid": report.valid,
    }
