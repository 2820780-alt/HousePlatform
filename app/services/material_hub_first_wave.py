from __future__ import annotations

from typing import Any

from app.models.enums import SourceStatus
from app.schemas.material_hub_contracts import ResultWriteMode, SourceTrustLevel


FIRST_WAVE_BLOCKED_NOTE = (
    "Источник блокирует автоматический анализ; не использовать в первой волне. "
    "История и адаптер сохранены, запуск доступен только через будущий безопасный feed/file workflow."
)

_BLOCKED_SOURCE_MARKERS = {
    "lemana",
    "lemanapro",
    "лемана",
    "vseinstrumenti",
    "vse-instrumenti",
    "всеинструменты",
    "vseinstrumenti.ru",
}


def is_first_wave_blocked_source(source_or_name: Any) -> bool:
    source_key = _source_key(source_or_name)
    return any(marker in source_key for marker in _BLOCKED_SOURCE_MARKERS)


def first_wave_source_policy(source_or_name: Any) -> dict[str, str]:
    if not is_first_wave_blocked_source(source_or_name):
        return {}
    return {
        "parserStatus": "BLOCKED",
        "updateMode": "disabled",
        "writeMode": "preview_only",
        "trustLevel": SourceTrustLevel.BLOCKED.value,
        "notes": FIRST_WAVE_BLOCKED_NOTE,
    }


def first_wave_safe_source_status(source_or_name: Any, default: SourceStatus = SourceStatus.ACTIVE) -> SourceStatus:
    return SourceStatus.PAUSED if is_first_wave_blocked_source(source_or_name) else default


def first_wave_source_status_label(source_or_name: Any) -> str | None:
    if not is_first_wave_blocked_source(source_or_name):
        return None
    return "Пауза: исключен из первой волны"


def first_wave_source_note(source_or_name: Any) -> str | None:
    return FIRST_WAVE_BLOCKED_NOTE if is_first_wave_blocked_source(source_or_name) else None


def apply_first_wave_policy_to_parameters(source_or_name: Any, parameters: dict | None) -> dict:
    payload = dict(parameters or {})
    policy = first_wave_source_policy(source_or_name)
    if not policy:
        return payload
    payload.update(
        {
            "parserStatus": policy["parserStatus"],
            "updateMode": policy["updateMode"],
            "writeMode": policy["writeMode"],
            "write_mode": ResultWriteMode.PREVIEW.value,
            "trustLevel": policy["trustLevel"],
            "first_wave_blocked": True,
            "notes": policy["notes"],
        }
    )
    return payload


def _source_key(source_or_name: Any) -> str:
    name = getattr(source_or_name, "name", source_or_name)
    url = getattr(source_or_name, "url", None)
    return f"{name or ''} {url or ''}".lower().replace(" ", "").replace("_", "-")


__all__ = [
    "FIRST_WAVE_BLOCKED_NOTE",
    "is_first_wave_blocked_source",
    "first_wave_source_policy",
    "first_wave_safe_source_status",
    "first_wave_source_status_label",
    "first_wave_source_note",
    "apply_first_wave_policy_to_parameters",
]
