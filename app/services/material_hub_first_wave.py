from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.enums import SourceStatus, SourceType
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


@dataclass(frozen=True)
class FirstWaveSourceSeed:
    source_code: str
    display_name: str
    base_url: str | None
    source_type: SourceType
    priority: int
    focus_region: str
    directions: tuple[str, ...]
    has_prices: bool = True
    has_availability: bool = True
    has_documents: bool = True
    has_certificates: bool = True
    has_characteristics: bool = True
    parser_status: str = "TEST"
    update_mode: str = "preview_only"
    write_mode: str = "preview_only"
    trust_level: SourceTrustLevel = SourceTrustLevel.TEST
    notes: str = (
        "Первая волна ЮФО. Источник доступен только для preview/test до проверки baseUrl, "
        "mapping, единиц, документов, региона и QualityReport."
    )

    def to_profile_parameters(self) -> dict[str, Any]:
        return {
            "sourceCode": self.source_code,
            "source_code": self.source_code,
            "source_name": self.display_name,
            "displayName": self.display_name,
            "baseUrl": self.base_url,
            "base_url": self.base_url,
            "sourceType": self.source_type.value,
            "priority": self.priority,
            "focusRegion": self.focus_region,
            "directions": list(self.directions),
            "parserStatus": self.parser_status,
            "updateMode": self.update_mode,
            "writeMode": self.write_mode,
            "write_mode": ResultWriteMode.PREVIEW.value,
            "trustLevel": self.trust_level.value,
            "hasPrices": self.has_prices,
            "hasAvailability": self.has_availability,
            "hasDocuments": self.has_documents,
            "hasCertificates": self.has_certificates,
            "hasCharacteristics": self.has_characteristics,
            "first_wave_yufo": True,
            "region_status": "needs_review",
            "needs_base_url_verification": self.base_url is None,
            "notes": self.notes,
        }


FIRST_WAVE_YUFO_FOCUS_REGION = "Краснодарский край / ЮФО"

FIRST_WAVE_YUFO_SOURCES: tuple[FirstWaveSourceSeed, ...] = (
    FirstWaveSourceSeed(
        source_code="YUFO_STROY_S",
        display_name="Строй-С",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=110,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("универсальные строительные базы", "сухие смеси и химия", "стеновые материалы"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_TD_MURAVEY",
        display_name="ТД Муравей",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=120,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("универсальные строительные базы", "крепеж и метизы", "сухие смеси и химия"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_VKBLOCK",
        display_name="ВКБлок",
        base_url="https://vkblock.ru/",
        source_type=SourceType.MANUFACTURER,
        priority=130,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("стеновые материалы", "документы и сертификаты"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_KSMK_GAZOBETON_KRASNODAR",
        display_name="КСМК Газобетон Краснодар",
        base_url=None,
        source_type=SourceType.MANUFACTURER,
        priority=140,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("стеновые материалы", "документы и сертификаты"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_KIRPICHNY_DVOR",
        display_name="Кирпичный Двор",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=150,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("стеновые материалы", "кирпич"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_KROVLYA_IZOLYACIYA",
        display_name="Кровля и Изоляция",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=160,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("кровля и водосток", "утеплители и мембраны"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_ROOF_MATERIALS",
        display_name="Roof Materials",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=170,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("кровля и водосток", "документы и сертификаты"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_SST_KVIK",
        display_name="ССТ КВИК",
        base_url=None,
        source_type=SourceType.MANUFACTURER,
        priority=180,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("сухие смеси и химия", "стеновые материалы"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_DOSKA_BRUS",
        display_name="Доска-Брус",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=190,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("пиломатериалы и листовые материалы",),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_PROFI_LES",
        display_name="Профи Лес",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=200,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("пиломатериалы и листовые материалы",),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_1METALLOBAZA_KRASNODAR",
        display_name="1Металлобаза Краснодар",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=210,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("металлопрокат",),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_SPK_KRASNODAR",
        display_name="СПК Краснодар",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=220,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("металлопрокат", "кровля и водосток"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_YUGKABEL",
        display_name="ЮгКабель",
        base_url="https://yugkabel.ru/",
        source_type=SourceType.SUPPLIER,
        priority=230,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("электрика и освещение",),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_PROMMETIZ",
        display_name="Промметиз",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=240,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("крепеж и метизы", "металлопрокат"),
    ),
    FirstWaveSourceSeed(
        source_code="YUFO_EKVATOR",
        display_name="Экватор",
        base_url=None,
        source_type=SourceType.SUPPLIER,
        priority=250,
        focus_region=FIRST_WAVE_YUFO_FOCUS_REGION,
        directions=("инженерная сантехника / отопление / вентиляция",),
    ),
)

_FIRST_WAVE_SEED_BY_KEY = {
    seed.display_name.lower().replace(" ", "").replace("_", "-"): seed
    for seed in FIRST_WAVE_YUFO_SOURCES
}


def is_first_wave_blocked_source(source_or_name: Any) -> bool:
    source_key = _source_key(source_or_name)
    return any(marker in source_key for marker in _BLOCKED_SOURCE_MARKERS)


def is_first_wave_yufo_source(source_or_name: Any) -> bool:
    return first_wave_yufo_source_seed(source_or_name) is not None


def first_wave_yufo_source_seed(source_or_name: Any) -> FirstWaveSourceSeed | None:
    source_key = _source_key(source_or_name)
    for seed_key, seed in _FIRST_WAVE_SEED_BY_KEY.items():
        if seed_key and seed_key in source_key:
            return seed
    return None


def first_wave_yufo_source_policy(source_or_name: Any) -> dict[str, Any]:
    seed = first_wave_yufo_source_seed(source_or_name)
    return seed.to_profile_parameters() if seed else {}


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
    return SourceStatus.PAUSED if (
        is_first_wave_blocked_source(source_or_name) or is_first_wave_yufo_source(source_or_name)
    ) else default


def first_wave_source_status_label(source_or_name: Any) -> str | None:
    if not is_first_wave_blocked_source(source_or_name):
        if is_first_wave_yufo_source(source_or_name):
            return "Preview/test: первая волна ЮФО"
        return None
    return "Пауза: исключен из первой волны"


def first_wave_source_note(source_or_name: Any) -> str | None:
    if is_first_wave_blocked_source(source_or_name):
        return FIRST_WAVE_BLOCKED_NOTE
    seed = first_wave_yufo_source_seed(source_or_name)
    return seed.notes if seed else None


def apply_first_wave_policy_to_parameters(source_or_name: Any, parameters: dict | None) -> dict:
    payload = dict(parameters or {})
    policy = first_wave_source_policy(source_or_name)
    yufo_policy = first_wave_yufo_source_policy(source_or_name)
    if yufo_policy:
        payload.update(yufo_policy)
    if policy:
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


def first_wave_yufo_source_create_payloads() -> list[dict[str, Any]]:
    return [
        {
            "name": seed.display_name,
            "source_type": seed.source_type,
            "url": seed.base_url,
            "priority": seed.priority,
            "status": SourceStatus.PAUSED,
        }
        for seed in FIRST_WAVE_YUFO_SOURCES
    ]


def _source_key(source_or_name: Any) -> str:
    name = getattr(source_or_name, "name", source_or_name)
    url = getattr(source_or_name, "url", None)
    return f"{name or ''} {url or ''}".lower().replace(" ", "").replace("_", "-")


__all__ = [
    "FIRST_WAVE_BLOCKED_NOTE",
    "FIRST_WAVE_YUFO_SOURCES",
    "FirstWaveSourceSeed",
    "is_first_wave_blocked_source",
    "is_first_wave_yufo_source",
    "first_wave_source_policy",
    "first_wave_yufo_source_seed",
    "first_wave_yufo_source_policy",
    "first_wave_yufo_source_create_payloads",
    "first_wave_safe_source_status",
    "first_wave_source_status_label",
    "first_wave_source_note",
    "apply_first_wave_policy_to_parameters",
]
