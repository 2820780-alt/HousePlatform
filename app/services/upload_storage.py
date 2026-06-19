from __future__ import annotations

from pathlib import Path
from uuid import UUID
import re

from app.config import settings


def save_uploaded_file(content: bytes, filename: str, upload_id: UUID) -> str:
    upload_dir = Path(settings.TEMP_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename or "upload")
    target = upload_dir / f"{upload_id}-{safe_name}"
    target.write_bytes(content)
    return str(target)


def _safe_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = re.sub(r"[^A-Za-zА-Яа-яЁё0-9._-]+", "_", name)
    return name or "upload"
