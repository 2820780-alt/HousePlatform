from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.enums import DocumentStatus, MaterialStatus, TaskStatus, UserRole
from app.services import user_dashboard_layout as layout_service
from app.services.dashboard_widget_registry import get_dashboard_widget_registry_item
from app.services.module1_operational_widgets import (
    MODULE1_WIDGET_CODES,
    WORK_COST_WIDGET_CODE,
    _analyzer_payload,
    _documents_payload,
    _load_widget_data,
    _materials_attention_payload,
    _price_relevance_payload,
    _work_cost_payload,
    get_module1_widget_catalog,
    get_module1_widget_configuration_options,
    get_module1_widget_layout,
    validate_module1_widget_settings,
)
from app.services.role_dashboard_access_profiles import get_role_dashboard_access_profile
from app.services.widget_registry import get_widget_registry_item


TEMPLATE = Path("templates/material_hub_view.html")
DASHBOARD_TEMPLATE = Path("templates/admin_cabinet_view.html")
QUICK_ACTIONS = Path("app/services/user_module_quick_actions.py")
API = Path("app/api/v1/admin_material_hub.py")


def _user(role: UserRole = UserRole.ADMIN):
    return SimpleNamespace(id=uuid4(), role=role)


def _layout_user():
    return {
        "userId": "admin-1",
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
    }


def test_module1_widgets_use_existing_registry_and_module_owned_payload_contract() -> None:
    assert len(MODULE1_WIDGET_CODES) == 5
    for code in MODULE1_WIDGET_CODES:
        dashboard_item = get_dashboard_widget_registry_item(code)
        authoritative_item = get_widget_registry_item(code)

        assert dashboard_item is not None
        assert authoritative_item is not None
        assert dashboard_item.sourceModuleCode == "MODULE_01_MATERIAL_HUB"
        assert dashboard_item.payloadSource == "module_owned"
        assert dashboard_item.allowsMultipleInstances is True
        assert dashboard_item.supportedPlacements == ["DASHBOARD", "MODULE_OVERVIEW"]
        assert authoritative_item.allowsMultipleInstances is True

    assert not Path("app/services/module1_widget_registry.py").exists()
    assert not Path("app/models/module1_widget_preference.py").exists()


def test_role_profiles_allow_but_do_not_auto_add_operational_widgets() -> None:
    admin = get_role_dashboard_access_profile("ADMIN")
    supplier = get_role_dashboard_access_profile("SUPPLIER")

    assert set(MODULE1_WIDGET_CODES).issubset(set(admin["allowedWidgetCodes"]))
    assert set(MODULE1_WIDGET_CODES).isdisjoint(set(admin["defaultWidgetCodes"]))
    assert WORK_COST_WIDGET_CODE in supplier["allowedWidgetCodes"]
    assert WORK_COST_WIDGET_CODE not in supplier["defaultWidgetCodes"]
    assert set(MODULE1_WIDGET_CODES[:-1]).isdisjoint(set(supplier["allowedWidgetCodes"]))


def test_layout_supports_multiple_instances_with_independent_settings(monkeypatch) -> None:
    monkeypatch.setattr(layout_service, "can_add_widget", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(layout_service, "record_dashboard_layout_change", lambda **_kwargs: None)
    layout = {
        "userId": "admin-1",
        "activeRegionCode": "KRASNODAR_KRAI",
        "widgets": [],
    }

    first = layout_service.add_widget_to_layout(
        layout,
        MODULE1_WIDGET_CODES[1],
        user=_layout_user(),
        placement="MODULE_OVERVIEW",
        user_settings={"materialId": "material-a", "freshnessDays": 30},
    )
    second = layout_service.add_widget_to_layout(
        first,
        MODULE1_WIDGET_CODES[1],
        user=_layout_user(),
        placement="DASHBOARD",
        user_settings={"materialId": "material-b", "freshnessDays": 90},
    )

    assert len(second["widgets"]) == 2
    assert second["widgets"][0]["instanceId"] != second["widgets"][1]["instanceId"]
    assert second["widgets"][0]["userSettings"]["materialId"] == "material-a"
    assert second["widgets"][1]["userSettings"]["materialId"] == "material-b"
    assert {item["placement"] for item in second["widgets"]} == {"MODULE_OVERVIEW", "DASHBOARD"}

    changed = layout_service.update_widget_instance_in_layout(
        second,
        second["widgets"][0]["instanceId"],
        user=_layout_user(),
        user_settings={"materialId": "material-c", "freshnessDays": 60},
    )
    assert changed["widgets"][0]["userSettings"]["materialId"] == "material-c"
    assert changed["widgets"][1]["userSettings"]["materialId"] == "material-b"

    removed = layout_service.remove_widget_instance_from_layout(
        changed,
        changed["widgets"][0]["instanceId"],
        user=_layout_user(),
    )
    assert [item["instanceId"] for item in removed["widgets"]] == [changed["widgets"][1]["instanceId"]]


def test_layout_reorder_and_unknown_widget_are_safe(monkeypatch) -> None:
    monkeypatch.setattr(layout_service, "can_add_widget", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(layout_service, "record_dashboard_layout_change", lambda **_kwargs: None)
    layout = {"userId": "admin-1", "activeRegionCode": "KRASNODAR_KRAI", "widgets": []}
    for code in MODULE1_WIDGET_CODES[:2]:
        layout = layout_service.add_widget_to_layout(
            layout,
            code,
            user=_layout_user(),
            placement="MODULE_OVERVIEW",
            user_settings={},
        )
    reversed_ids = [layout["widgets"][1]["instanceId"], layout["widgets"][0]["instanceId"]]
    reordered = layout_service.reorder_widget_instances_in_layout(
        layout,
        reversed_ids,
        user=_layout_user(),
    )

    assert [item["instanceId"] for item in reordered["widgets"]] == reversed_ids
    normalized = layout_service.normalize_user_dashboard_layout(
        {
            **layout,
            "widgets": [
                *layout["widgets"],
                {"widgetCode": "MODULE_01_REMOVED_WIDGET", "instanceId": "stale"},
            ],
        },
        user=_layout_user(),
    )
    assert all(item["widgetCode"] != "MODULE_01_REMOVED_WIDGET" for item in normalized["widgets"])


def test_reorder_preserves_unrelated_dashboard_widget_slot(monkeypatch) -> None:
    monkeypatch.setattr(layout_service, "can_add_widget", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(layout_service, "record_dashboard_layout_change", lambda **_kwargs: None)
    layout = {"userId": "admin-1", "activeRegionCode": "KRASNODAR_KRAI", "widgets": []}
    layout = layout_service.add_widget_to_layout(
        layout,
        MODULE1_WIDGET_CODES[0],
        user=_layout_user(),
        placement="MODULE_OVERVIEW",
        user_settings={},
    )
    layout = layout_service.add_widget_to_layout(layout, "materials-kpi", user=_layout_user())
    layout = layout_service.add_widget_to_layout(
        layout,
        MODULE1_WIDGET_CODES[1],
        user=_layout_user(),
        placement="MODULE_OVERVIEW",
        user_settings={},
    )
    first_id = layout["widgets"][0]["instanceId"]
    second_id = layout["widgets"][2]["instanceId"]

    reordered = layout_service.reorder_widget_instances_in_layout(
        layout,
        [second_id, first_id],
        user=_layout_user(),
    )

    assert reordered["widgets"][1]["widgetCode"] == "materials-kpi"
    assert [reordered["widgets"][index]["instanceId"] for index in (0, 2)] == [second_id, first_id]

@pytest.mark.parametrize("code", MODULE1_WIDGET_CODES)
def test_widget_settings_have_safe_defaults_and_reject_permission_payload(code: str) -> None:
    validated = validate_module1_widget_settings(code, {})
    assert validated["limit"] in {1, 3, 5, 10}

    with pytest.raises(Exception):
        validate_module1_widget_settings(code, {"permissions": ["ADMIN"]})
    with pytest.raises(Exception):
        validate_module1_widget_settings(code, {"rawData": {"secret": True}})
    with pytest.raises(Exception):
        validate_module1_widget_settings(code, {"unknownSetting": "x"})


def test_widget_catalog_is_role_scoped() -> None:
    admin_codes = {item["widgetCode"] for item in get_module1_widget_catalog(_user())}
    supplier_codes = {item["widgetCode"] for item in get_module1_widget_catalog(_user(UserRole.SUPPLIER))}
    customer_codes = {item["widgetCode"] for item in get_module1_widget_catalog(_user(UserRole.CUSTOMER))}

    assert admin_codes == set(MODULE1_WIDGET_CODES)
    assert supplier_codes == {WORK_COST_WIDGET_CODE}
    assert customer_codes == set()


def test_materials_attention_widget_uses_legacy_material_quality_and_price() -> None:
    material = SimpleNamespace(
        id=uuid4(),
        canonical_name="Газобетонный блок",
        quality_issues=[SimpleNamespace(status="OPEN")],
        catalog_products=[SimpleNamespace(price=None, region="Краснодарский край")],
        category_id=None,
        material_type_id=None,
        status=MaterialStatus.NEEDS_REVIEW,
        description=None,
        base_unit_id=None,
    )
    payload = _materials_attention_payload(
        {"reasons": ["open_quality_issue", "no_positive_price"], "region": "Краснодарский край", "limit": 5},
        [material],
    )

    assert payload["primaryValue"] == 1
    assert payload["status"] == "attention"
    assert payload["items"][0]["label"] == "Газобетонный блок"
    assert "ATOM_REF" not in str(payload)


def test_price_relevance_widget_uses_real_positive_observation_without_chart() -> None:
    material = SimpleNamespace(id=uuid4(), canonical_name="Арматура")
    observation = SimpleNamespace(
        material_id=material.id,
        price=Decimal("125.50"),
        currency="RUB",
        region="Краснодарский край",
        collected_at=datetime.utcnow() - timedelta(days=5),
    )
    payload = _price_relevance_payload(
        {"mode": "current", "freshnessDays": 30, "region": "Краснодарский край", "limit": 5},
        [material],
        [observation],
    )

    assert payload["primaryValue"] == 1
    assert payload["status"] == "ok"
    assert payload["miniChart"] is None
    assert "125.50 RUB" in payload["items"][0]["value"]


def test_documents_widget_filters_review_and_expiry_states() -> None:
    review = SimpleNamespace(
        title="Сертификат соответствия",
        document_type=SimpleNamespace(value="CERTIFICATE"),
        status=DocumentStatus.NEEDS_REVIEW,
        expiry_date=None,
    )
    payload = _documents_payload(
        {"status": "needs_review", "expiryDays": 30, "limit": 5},
        [review],
    )

    assert payload["primaryValue"] == 1
    assert payload["items"][0]["label"] == "Сертификат соответствия"
    assert payload["status"] == "attention"


def test_analyzer_widget_hides_raw_error_and_result_payload() -> None:
    task = SimpleNamespace(
        source=SimpleNamespace(name="Проверенный источник"),
        source_id=uuid4(),
        status=TaskStatus.FAILED,
        finished_at=datetime(2026, 7, 19, 12, 30),
        started_at=None,
        created_at=datetime(2026, 7, 19, 12, 0),
        error_message="password=secret stack trace",
        result_summary={"raw": "private"},
    )
    payload = _analyzer_payload({"mode": "latest", "limit": 3}, [task])
    serialized = str(payload)

    assert payload["primaryValue"] == "Ошибка"
    assert "password=secret" not in serialized
    assert "stack trace" not in serialized
    assert "private" not in serialized


def test_work_cost_widget_is_separate_from_material_price() -> None:
    offer = SimpleNamespace(
        work_code="foundation.concrete",
        region="Краснодарский край",
        pricing_mode="range",
        minimum_amount=Decimal("1000"),
        maximum_amount=Decimal("1500"),
        fixed_amount=None,
        currency="RUB",
        pricing_unit="м2",
        valid_until=date.today() + timedelta(days=10),
        status="active",
    )
    payload = _work_cost_payload(
        {
            "status": "expiring",
            "expiryDays": 30,
            "pricingMode": "range",
            "region": "Краснодарский край",
            "limit": 5,
        },
        [offer],
    )

    assert payload["primaryValue"] == 1
    assert "1000–1500 RUB/м2" in payload["items"][0]["value"]
    assert "price_history" not in str(payload).lower()
    assert "priceObservations" not in payload
    assert "PriceHistory" not in str(payload)


class _FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)

    def unique(self):
        return self


class _FakeResult:
    def __init__(self, values=()):
        self.values = values

    def scalars(self):
        return _FakeScalars(self.values)

    def scalar_one_or_none(self):
        return self.values[0] if self.values else None


class _FakeDB:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_layout_lookup_is_scoped_to_current_user() -> None:
    user = _user()
    db = _FakeDB([_FakeResult([])])

    assert await get_module1_widget_layout(db, user) is None

    assert len(db.statements) == 1
    sql = str(db.statements[0])
    assert "user_dashboard_layouts.user_id" in sql
    assert "user_dashboard_layouts.status" in sql

@pytest.mark.asyncio
async def test_multiple_instances_are_batched_by_widget_type() -> None:
    db = _FakeDB([_FakeResult([]), _FakeResult([])])
    instances = [
        {"widgetCode": MODULE1_WIDGET_CODES[1]},
        {"widgetCode": MODULE1_WIDGET_CODES[1]},
    ]

    await _load_widget_data(db, _user(), instances)

    assert len(db.statements) == 2
    assert "LIMIT" in str(db.statements[0]).upper()
    assert "LIMIT" in str(db.statements[1]).upper()


@pytest.mark.asyncio
async def test_provider_work_cost_query_is_owner_scoped() -> None:
    supplier = _user(UserRole.SUPPLIER)
    db = _FakeDB([_FakeResult([])])

    await _load_widget_data(db, supplier, [{"widgetCode": WORK_COST_WIDGET_CODE}])

    sql = str(db.statements[0])
    assert "provider_work_cost_offers.owner_user_id" in sql
    assert "price_history" not in sql.lower()


@pytest.mark.asyncio
async def test_configuration_options_follow_role_and_owner_scope() -> None:
    supplier = _user(UserRole.SUPPLIER)
    db = _FakeDB([_FakeResult(["Краснодарский край"])])

    options = await get_module1_widget_configuration_options(db, supplier)

    assert options["materials"] == []
    assert options["sources"] == []
    assert options["documentTypes"] == []
    assert options["regions"] == [
        {"value": "Краснодарский край", "label": "Краснодарский край"}
    ]
    assert options["works"]
    assert len(db.statements) == 1
    sql = str(db.statements[0])
    assert "provider_work_cost_offers.owner_user_id" in sql
    assert "price_history" not in sql.lower()


def test_widget_api_models_import_with_runtime_annotations() -> None:
    from app.api.v1.admin_material_hub import Module1WidgetCreateRequest

    request = Module1WidgetCreateRequest(widgetCode=MODULE1_WIDGET_CODES[0])
    assert request.placement == "MODULE_OVERVIEW"


def test_overview_ui_has_empty_loading_error_and_instance_controls() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")

    assert "data-module1-widgets-empty" in html
    assert "Загружаю виджеты" in html
    assert "Настройки виджетов сейчас недоступны" in html
    assert "data-module1-widget-add" in html
    assert "data-module1-widget-form" in html
    assert "Настроить" in html
    assert "Удалить" in html
    assert "raw payload" not in html.lower()

def test_api_is_user_scoped_and_dashboard_uses_existing_payload_renderer() -> None:
    api = API.read_text(encoding="utf-8")
    dashboard = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")

    assert "user: CurrentUser" in api
    assert '@router.post("/widgets/instances"' in api
    assert '@router.patch("/widgets/instances/{instance_id}")' in api
    assert '@router.delete("/widgets/instances/{instance_id}"' in api
    assert "admin-widget-card" in dashboard
    assert "data-dashboard-widget-card" in dashboard
    assert "Module01" not in dashboard


def test_quick_action_contract_was_not_mixed_with_widgets() -> None:
    quick_actions = QUICK_ACTIONS.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")

    assert "module1_operational_widgets" not in quick_actions
    assert "quickAction" not in template
    assert "data-quick-action" not in template
