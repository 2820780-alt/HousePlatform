from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1 import module1_work_cost_offers as work_cost_api
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.services.module1_provider_work_cost_offers import (
    list_work_catalog_options,
    provider_work_cost_offer_to_dict,
)
from app.services.module1_work_catalog import list_work_items

TEMPLATE = Path("templates/material_hub_work_costs.html")
OVERVIEW_TEMPLATE = Path("templates/material_hub_view.html")
VIEW = Path("app/api/v1/material_hub_view.py")
SERVICE = Path("app/services/module1_provider_work_cost_offers.py")
API = Path("app/api/v1/module1_work_cost_offers.py")


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _offer(**overrides):
    work = list_work_items()[0]
    data = {
        "id": uuid4(),
        "work_code": work.work_code,
        "owner_user_id": uuid4(),
        "region": "Краснодарский край",
        "pricing_mode": "fixed",
        "fixed_amount": Decimal("25000.00"),
        "currency": "RUB",
        "pricing_unit": work.allowed_units[0],
        "valid_until": date.today() + timedelta(days=20),
        "status": "active",
        "created_at": datetime(2026, 7, 17, 10, 0),
        "updated_at": datetime(2026, 7, 17, 10, 0),
    }
    data.update(overrides)
    return ProviderWorkCostOffer(**data)


def _contractor(user_id):
    return {"id": user_id, "roleCode": "CONTRACTOR"}


def test_work_cost_workspace_route_and_overview_link_are_declared():
    view = VIEW.read_text(encoding="utf-8")
    overview = OVERVIEW_TEMPLATE.read_text(encoding="utf-8")

    assert '@router.get("/work-costs", response_class=HTMLResponse)' in view
    assert '"material_hub_work_costs.html"' in view
    assert "_load_provider_work_cost_offer_rows" in view
    assert "/api/v1/admin/material-hub/view/work-costs" in overview
    assert "Блок 5 · Стоимость работ" in overview
    assert "WorkRateObservation" not in overview


def test_workspace_has_required_columns_presets_states_and_form_fields():
    text = _template_text()

    for label in [
        "Стоимость работ",
        "Предложения стоимости работ",
        "Работа",
        "Раздел работ",
        "Исполнитель",
        "Регион",
        "Стоимость работы",
        "Единица расчёта",
        "Актуальность",
        "Состояние",
        "Действия",
        "Все доступные предложения",
        "Мои предложения",
        "Активные",
        "Черновики",
        "Неактивные",
        "С истёкшим сроком",
        "Добавить стоимость",
        "Тип стоимости",
        "Фиксированная стоимость",
        "Стоимость от",
        "Стоимость до",
        "Валюта",
        "Действует до",
        "Комментарий/условия",
        "Сохранить черновик",
        "Сохранить и активировать",
        "Загрузка предложений стоимости работ",
        "У вас пока нет предложений стоимости работ",
        "Предложения стоимости работ пока не добавлены",
        "По выбранным условиям ничего не найдено",
        "Повторить",
        "Страница 1",
    ]:
        assert label in text


def test_workspace_preferences_are_scoped_and_required_columns_are_protected():
    text = _template_text()

    assert 'data-preference-namespace="module1.work_costs_table"' in text
    assert 'workCostPreferenceKey = "atom:module1.work_costs_table:v1"' in text
    assert 'requiredWorkCostColumns = ["work", "cost", "state"]' in text
    assert "optionalWorkCostColumns.includes(id)" in text
    assert "sessionStorage" in text
    assert "unknownPreference" not in text


def test_workspace_isolated_from_material_prices_analyzer_and_raw_internals():
    text = _template_text()

    forbidden = [
        "WorkRateObservation",
        "PriceObservation",
        "CatalogProduct",
        "MaterialMatchCandidate",
        "materialId",
        "ownerUserId",
        "work_code",
        "rawPayload",
        "SourceTask",
        "adapter",
        "parsing",
        "extraction",
        "Запустить анализ",
        "Источники и анализатор",
        "/api/v1/dev/material-hub",
    ]
    for marker in forbidden:
        assert marker not in text


def test_form_payload_keeps_fixed_and_range_amounts_separate():
    text = _template_text()

    assert 'if (mode === "fixed") { payload.fixedAmount' in text
    assert 'payload.minimumAmount = document.getElementById("offer-minimum").value' in text
    assert 'payload.maximumAmount = document.getElementById("offer-maximum").value' in text
    assert "Стоимость от не может быть больше стоимости до" in text
    assert "owner_user_id" not in text
    assert "provider_id" not in text
    assert "company_id" not in text


def test_work_catalog_options_come_from_registry_without_hardcoded_209():
    options = list_work_catalog_options()
    text = _template_text()

    assert len(options) == len(list_work_items())
    assert options[0]["workCode"] == list_work_items()[0].work_code
    assert options[0]["workTitle"] == list_work_items()[0].work_name
    assert options[0]["allowedUnits"]
    assert "209" not in text


@pytest.mark.asyncio
async def test_work_catalog_api_returns_existing_contract():
    result = await work_cost_api.list_work_cost_catalog(SimpleNamespace(id=uuid4(), roleCode="PLATFORM_ADMIN"))

    assert len(result["items"]) == len(list_work_items())
    assert {"workCode", "workTitle", "workGroupTitle", "allowedUnits"}.issubset(result["items"][0])


def test_offer_serializer_adds_human_presentation_and_permissions():
    owner_id = uuid4()
    offer = _offer(owner_user_id=owner_id, pricing_mode="fixed", fixed_amount=Decimal("25000.00"))

    payload = provider_work_cost_offer_to_dict(offer, _contractor(owner_id))

    assert payload["ownerDisplayName"] == "Моё предложение"
    assert payload["pricingModeLabel"] == "Фиксированная"
    assert payload["priceLabel"] == "25 000 ₽"
    assert payload["statusLabel"] == "Активно"
    assert payload["canEdit"] is True
    assert payload["canDeactivate"] is True
    assert payload["canActivate"] is False
    assert payload["qualityFlags"] == []


def test_offer_serializer_formats_range_and_expired_quality_flag():
    work = next(item for item in list_work_items() if item.is_range_allowed)
    offer = _offer(
        work_code=work.work_code,
        pricing_mode="range",
        fixed_amount=None,
        minimum_amount=Decimal("20000.00"),
        maximum_amount=Decimal("30000.00"),
        pricing_unit=work.allowed_units[0],
        valid_until=date.today() - timedelta(days=1),
    )

    payload = provider_work_cost_offer_to_dict(offer)

    assert payload["pricingModeLabel"] == "Диапазон"
    assert payload["priceLabel"] == "от 20 000 до 30 000 ₽"
    assert payload["statusLabel"] == "Срок истёк"
    assert payload["qualityFlags"][0]["code"] == "expired"


def test_service_and_api_do_not_touch_foundation_boundaries():
    service_text = SERVICE.read_text(encoding="utf-8")
    api_text = API.read_text(encoding="utf-8")

    assert "ProviderWorkCostOffer(" in service_text
    assert "Material(" not in service_text
    assert "CatalogProduct(" not in service_text
    assert "PriceObservation" not in service_text
    assert "source_task" not in service_text
    assert "work-catalog" in api_text
    assert "owner_user_id=data" not in api_text
    assert "ownerUserId=data" not in api_text
