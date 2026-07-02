import pytest

from app.models.enums import SourceActionType, SourceStatus, SourceType
from app.models.source import Source
from app.schemas.material_hub_contracts import ResultWriteMode
from app.services.material_hub_first_wave import (
    FIRST_WAVE_YUFO_SOURCES,
    apply_first_wave_policy_to_parameters,
    first_wave_yufo_source_create_payloads,
    first_wave_yufo_source_policy,
    first_wave_safe_source_status,
    first_wave_source_policy,
    is_first_wave_yufo_source,
    is_first_wave_blocked_source,
)
from app.services.source_profiles import attach_source_profile_snapshot
from app.source_integrations.lemanapro import LemanaProIntegration
from app.source_integrations.vseinstrumenti import VseInstrumentiIntegration


def test_first_wave_policy_blocks_lemana_and_vseinstrumenti_without_deleting_sources():
    lemana = Source(name="LemanaPro", source_type=SourceType.RETAIL, url="https://lemanapro.ru/")
    vse = Source(name="VseInstrumenti", source_type=SourceType.RETAIL, url="https://www.vseinstrumenti.ru/")
    active = Source(name="Bonolit", source_type=SourceType.MANUFACTURER, url="https://bonolit.ru/")

    assert is_first_wave_blocked_source(lemana) is True
    assert is_first_wave_blocked_source(vse) is True
    assert is_first_wave_blocked_source(active) is False
    assert first_wave_safe_source_status(vse) == SourceStatus.PAUSED
    assert first_wave_safe_source_status(active) == SourceStatus.ACTIVE


def test_first_wave_policy_metadata_matches_safe_status_contract():
    policy = first_wave_source_policy("VseInstrumenti")

    assert policy["parserStatus"] == "BLOCKED"
    assert policy["updateMode"] == "disabled"
    assert policy["writeMode"] == "preview_only"
    assert policy["trustLevel"] == "BLOCKED"
    assert "не использовать в первой волне" in policy["notes"]


def test_blocked_source_profile_snapshot_is_preview_only():
    source = Source(
        name="VseInstrumenti",
        source_type=SourceType.RETAIL,
        url="https://www.vseinstrumenti.ru/",
        status=SourceStatus.ACTIVE,
    )

    payload = attach_source_profile_snapshot(
        source,
        SourceActionType.UPDATE_PRICES,
        {"write_mode": ResultWriteMode.CREATE_CANDIDATES.value},
        adapter_code="VseInstrumentiIntegration",
        supported_actions={SourceActionType.UPDATE_PRICES},
        force=True,
    )

    profile = payload["source_profile_snapshot"]["source_profile"]
    assert profile["parser_status"] == "BLOCKED"
    assert profile["update_mode"] == "disabled"
    assert profile["write_mode"] == "preview_only"
    assert profile["trust_level"] == "BLOCKED"
    assert payload["write_mode"] == "PREVIEW"
    assert payload["first_wave_blocked"] is True


def test_apply_first_wave_policy_keeps_non_blocked_parameters_unchanged():
    payload = apply_first_wave_policy_to_parameters("Bonolit", {"write_mode": "CREATE_CANDIDATES"})

    assert payload == {"write_mode": "CREATE_CANDIDATES"}


def test_first_wave_yufo_registry_is_preview_only_seed_config():
    assert len(FIRST_WAVE_YUFO_SOURCES) == 15
    assert is_first_wave_yufo_source("ЮгКабель") is True
    assert first_wave_safe_source_status("ЮгКабель") == SourceStatus.PAUSED

    policy = first_wave_yufo_source_policy("ЮгКабель")

    assert policy["sourceCode"] == "YUFO_YUGKABEL"
    assert policy["displayName"] == "ЮгКабель"
    assert policy["baseUrl"] == "https://yugkabel.ru/"
    assert policy["parserStatus"] == "TEST"
    assert policy["writeMode"] == "preview_only"
    assert policy["write_mode"] == "PREVIEW"
    assert policy["trustLevel"] == "TEST"
    assert policy["first_wave_yufo"] is True
    assert policy["hasPrices"] is True
    assert policy["hasDocuments"] is True


def test_first_wave_yufo_seed_sources_are_paused_for_default_creation():
    payloads = first_wave_yufo_source_create_payloads()

    assert len(payloads) == 15
    assert all(payload["status"] == SourceStatus.PAUSED for payload in payloads)
    assert {payload["name"] for payload in payloads} >= {"Строй-С", "ЮгКабель", "Экватор"}


def test_first_wave_source_profile_snapshot_is_test_preview_only():
    source = Source(
        name="ЮгКабель",
        source_type=SourceType.SUPPLIER,
        url="https://yugkabel.ru/",
        status=SourceStatus.PAUSED,
    )

    payload = attach_source_profile_snapshot(
        source,
        SourceActionType.INITIAL_MATERIAL_SCAN,
        {"write_mode": "CREATE_CANDIDATES"},
        adapter_code=None,
        supported_actions={SourceActionType.INITIAL_MATERIAL_SCAN},
        force=True,
    )

    profile = payload["source_profile_snapshot"]["source_profile"]
    quality = profile["quality_report"]
    assert payload["write_mode"] == "PREVIEW"
    assert profile["source_code"] == "YUFO_YUGKABEL"
    assert profile["parser_status"] == "TEST"
    assert profile["write_mode"] == "preview_only"
    assert profile["trust_level"] == "TEST"
    assert profile["has_documents"] is True
    assert quality["recommended_next_action"] == "keep_preview_only"


@pytest.mark.asyncio
async def test_blocked_adapters_do_not_fetch_products_directly():
    lemana = LemanaProIntegration(Source(name="LemanaPro", source_type=SourceType.RETAIL))
    vse = VseInstrumentiIntegration(Source(name="VseInstrumenti", source_type=SourceType.RETAIL))

    assert lemana.supported_actions == {SourceActionType.CHECK_SOURCE_HEALTH}
    assert vse.supported_actions == {SourceActionType.CHECK_SOURCE_HEALTH}

    lemana_health = await lemana.check_health()
    vse_health = await vse.check_health()
    assert lemana_health.ok is False
    assert vse_health.ok is False
    assert "excluded from the first wave" in lemana_health.message
    assert "excluded from the first wave" in vse_health.message

    with pytest.raises(RuntimeError, match="excluded from the first wave"):
        await lemana.fetch_products(SourceActionType.UPDATE_PRICES)
    with pytest.raises(RuntimeError, match="excluded from the first wave"):
        await vse.fetch_products(SourceActionType.UPDATE_PRICES)
