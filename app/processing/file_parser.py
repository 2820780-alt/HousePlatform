from __future__ import annotations

import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import pandas as pd

from app.processing.file_validator import FileType


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
    raw_data: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    rows: list[ParsedRow]
    errors: list[str]
    total_rows_found: int
    sheets_parsed: int = 1


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
    return {
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


def _df_to_parsed_rows(df: pd.DataFrame, row_offset: int = 0) -> tuple[list[ParsedRow], list[str]]:
    rows: list[ParsedRow] = []
    errors: list[str] = []
    if df.empty:
        return rows, errors

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

        rows.append(ParsedRow(
            row_number=row_num,
            original_name=name,
            original_price=price,
            original_unit=_safe_str(row.get(col_map["unit"])) if col_map["unit"] else None,
            quantity=_to_decimal(row.get(col_map["quantity"]) if col_map["quantity"] else None),
            total_sum=_to_decimal(row.get(col_map["total_sum"]) if col_map["total_sum"] else None),
            sku=_safe_str(row.get(col_map["sku"])) if col_map["sku"] else None,
            brand=_safe_str(row.get(col_map["brand"])) if col_map["brand"] else None,
            manufacturer=_safe_str(row.get(col_map["manufacturer"])) if col_map["manufacturer"] else None,
            raw_data={str(k): str(v) for k, v in row.items() if not pd.isna(v) and str(v).strip()},
        ))

    return rows, errors


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
            sheet_rows, sheet_errors = _df_to_parsed_rows(df, row_offset)
            rows.extend(sheet_rows)
            errors.extend([f"{sheet_name}: {error}" for error in sheet_errors])
            row_offset += len(df)
        except Exception as exc:
            errors.append(f"{sheet_name}: {exc}")

    return ParseResult(
        rows=rows,
        errors=errors,
        total_rows_found=len(rows),
        sheets_parsed=sheets_parsed,
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

    rows, errors = _df_to_parsed_rows(df)
    return ParseResult(rows=rows, errors=errors, total_rows_found=len(rows), sheets_parsed=1)


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
