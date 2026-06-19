from decimal import Decimal

from app.processing.file_parser import parse_file
from app.processing.file_validator import FileType, validate_file


def test_xlsx_by_extension():
    r = validate_file(
        "price.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        2048,
    )
    assert r.valid is True
    assert r.file_type == FileType.XLSX


def test_csv_by_extension():
    r = validate_file("price.csv", "text/csv", 512)
    assert r.valid is True
    assert r.file_type == FileType.CSV


def test_pdf_rejected_for_mvp():
    r = validate_file("price.pdf", "application/pdf", 1024)
    assert r.valid is False
    assert "MVP accepts only CSV and XLSX" in r.error


def test_xls_rejected_for_mvp():
    r = validate_file("price.xls", "application/vnd.ms-excel", 2048)
    assert r.valid is False
    assert "MVP accepts only CSV and XLSX" in r.error


def test_jpg_rejected():
    r = validate_file("scan.jpg", "image/jpeg", 1024)
    assert r.valid is False
    assert "Images are not supported" in r.error


def test_tiff_rejected():
    r = validate_file("scan.tiff", "image/tiff", 1024)
    assert r.valid is False
    assert "Scans are not supported" in r.error


def test_unknown_extension_rejected():
    r = validate_file("file.xyz", "application/octet-stream", 1024)
    assert r.valid is False
    assert "Unsupported file format" in r.error


def test_empty_file_rejected():
    r = validate_file("price.csv", "text/csv", 0)
    assert r.valid is False
    assert "empty" in r.error.lower()


def test_oversized_file_rejected():
    size_51mb = 51 * 1024 * 1024
    r = validate_file(
        "price.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size_51mb,
    )
    assert r.valid is False
    assert "50 MB" in r.error


def test_max_allowed_size_passes():
    size_50mb = 50 * 1024 * 1024
    r = validate_file(
        "price.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size_50mb,
    )
    assert r.valid is True


def test_semicolon_csv_price_is_split_into_columns():
    content = "наименование;цена;единица\nOSB 2440x1220x12;1234.50;лист\n".encode("utf-8")

    result = parse_file(content, FileType.CSV)

    assert result.total_rows_found == 1
    assert result.rows[0].original_name == "OSB 2440x1220x12"
    assert result.rows[0].original_price == Decimal("1234.50")
    assert result.rows[0].original_unit == "лист"
