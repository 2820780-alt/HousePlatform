"""
FILE VALIDATOR
==============
MVP Module 01 / Material Hub accepts only CSV and XLSX manual uploads.

Readable PDF, invoices, commercial offers, and legacy XLS are future formats.
Scans and photos are outside MVP.
"""

from dataclasses import dataclass
from enum import Enum


class FileType(str, Enum):
    XLSX = "xlsx"
    CSV = "csv"


_MIME_MAP: dict[str, FileType] = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.XLSX,
    "text/csv": FileType.CSV,
    "application/csv": FileType.CSV,
    "text/plain": FileType.CSV,
}

_EXT_MAP: dict[str, FileType] = {
    ".xlsx": FileType.XLSX,
    ".csv": FileType.CSV,
}

_FUTURE_FORMATS: dict[str, str] = {
    ".pdf": "PDF will be added later. MVP accepts only CSV and XLSX.",
    ".xls": "Legacy XLS will be added later if needed. MVP accepts only CSV and XLSX.",
    ".doc": "DOC is not supported. MVP accepts only CSV and XLSX.",
    ".docx": "DOCX is not supported. MVP accepts only CSV and XLSX.",
    ".ods": "ODS is not supported. MVP accepts only CSV and XLSX.",
}

_FORBIDDEN_EXTENSIONS: dict[str, str] = {
    ".jpg": "Images are not supported. Upload CSV or XLSX.",
    ".jpeg": "Images are not supported. Upload CSV or XLSX.",
    ".png": "Images are not supported. Upload CSV or XLSX.",
    ".gif": "Images are not supported. Upload CSV or XLSX.",
    ".bmp": "Images are not supported. Upload CSV or XLSX.",
    ".tiff": "Scans are not supported. Upload CSV or XLSX.",
    ".tif": "Scans are not supported. Upload CSV or XLSX.",
    ".webp": "Images are not supported. Upload CSV or XLSX.",
    ".heic": "Images are not supported. Upload CSV or XLSX.",
    ".zip": "Archives are not supported. Upload CSV or XLSX.",
    ".rar": "Archives are not supported. Upload CSV or XLSX.",
    ".7z": "Archives are not supported. Upload CSV or XLSX.",
}

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


@dataclass
class ValidationResult:
    valid: bool
    file_type: FileType | None
    error: str | None = None


def validate_file(
    filename: str,
    content_type: str | None,
    file_size_bytes: int,
) -> ValidationResult:
    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        mb = file_size_bytes // (1024 * 1024)
        return ValidationResult(
            valid=False,
            file_type=None,
            error=f"File is too large: {mb} MB. Maximum size is 50 MB.",
        )

    if file_size_bytes == 0:
        return ValidationResult(
            valid=False,
            file_type=None,
            error="File is empty.",
        )

    lower_name = (filename or "").lower().strip()
    ext = ""
    if "." in lower_name:
        ext = "." + lower_name.rsplit(".", 1)[-1]

    if ext in _FUTURE_FORMATS:
        return ValidationResult(valid=False, file_type=None, error=_FUTURE_FORMATS[ext])

    if ext in _FORBIDDEN_EXTENSIONS:
        return ValidationResult(valid=False, file_type=None, error=_FORBIDDEN_EXTENSIONS[ext])

    file_type = _EXT_MAP.get(ext)
    if file_type is None and content_type:
        mime = content_type.lower().split(";")[0].strip()
        file_type = _MIME_MAP.get(mime)

    if file_type is None:
        return ValidationResult(
            valid=False,
            file_type=None,
            error=f"Unsupported file format: {ext or content_type}. MVP accepts only CSV and XLSX.",
        )

    return ValidationResult(valid=True, file_type=file_type)


def get_allowed_formats_description() -> str:
    return "CSV, XLSX"
