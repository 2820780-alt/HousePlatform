from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.api.deps import get_current_user
from app.api.v1 import module2_encyclopedia, module2_workbench
from app.core.exceptions import ForbiddenError
from app.database import get_db
from app.models.enums import UserRole
from app.services.module2_workbench import _needs_material_selection, build_technology_list_view
from app.services.module2_operational_widgets import build_workbench_queue_widget


def test_material_selection_counts_open_gaps_not_resolved_or_dismissed():
    requirement = SimpleNamespace(id=uuid4(), canonical_material_id=None)
    assert _needs_material_selection(requirement, {})
    assert _needs_material_selection(requirement, {requirement.id: ("OPEN", None)})
    assert _needs_material_selection(requirement, {requirement.id: ("RESOLVED_EXISTING", None)})
    assert not _needs_material_selection(requirement, {requirement.id: ("RESOLVED_EXISTING", uuid4())})
    assert not _needs_material_selection(requirement, {requirement.id: ("DISMISSED", None)})
    requirement.canonical_material_id = uuid4()
    assert not _needs_material_selection(requirement, {})


@pytest.mark.asyncio
async def test_list_uses_actual_gap_resolutions_and_activation_blockers():
    open_req = SimpleNamespace(id=uuid4(), canonical_material_id=None)
    resolved_req = SimpleNamespace(id=uuid4(), canonical_material_id=None)
    technology = SimpleNamespace(
        id=uuid4(), name="Тест", technology_code="TEST", revision=1, status="DRAFT",
        system_code=None, category_id=None, updated_at=None,
        input_blockers=[], input_missing_fields=[], layers=[], requirements=[open_req, resolved_req],
    )
    technology_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [technology]))
    gap_result = SimpleNamespace(all=lambda: [
        (open_req.id, "OPEN", None),
        (resolved_req.id, "RESOLVED_EXISTING", uuid4()),
    ])
    db = SimpleNamespace(execute=AsyncMock(side_effect=[technology_result, gap_result]))

    rows = await build_technology_list_view(db)

    assert rows[0]["unresolved_material_count"] == 1
    assert rows[0]["blocker_count"] == 1
    assert rows[0]["open_gap_count"] == 1


def test_registered_workbench_widget_counts_real_queues():
    rows = [
        {"status": "REVIEW", "open_gap_count": 2, "blocker_count": 0},
        {"status": "ACTIVE", "open_gap_count": 1, "blocker_count": 1},
        {"status": "DRAFT", "open_gap_count": 0, "blocker_count": 1},
    ]
    payload = build_workbench_queue_widget(SimpleNamespace(id=uuid4(), role=UserRole.ADMIN), rows)
    assert payload["widgetCode"] == "MODULE_02_TECHNOLOGY_READINESS_WIDGET"
    assert [item["value"] for item in payload["items"]] == [1, 3, 1]
    assert payload["items"][0]["route"].endswith("?status=REVIEW")
    assert payload["items"][1]["route"].endswith("?materials=open_gap")
    assert payload["items"][2]["route"].endswith("?status=ACTIVE&blockers=yes")


def test_workbench_widget_rejects_view_only_user():
    with pytest.raises(ForbiddenError):
        build_workbench_queue_widget(SimpleNamespace(id=uuid4(), role=UserRole.SUPPLIER), [])


def test_material_requirement_forms_do_not_offer_unfiltered_catalog():
    template = (Path(__file__).resolve().parents[1] / "templates" / "module2_technology_detail.html").read_text(encoding="utf-8")
    section = template.split("{% if active_tab == 'materials' %}", 1)[1].split("{% if active_tab == 'works' %}", 1)[0]
    assert "for material in item.candidates" in section
    assert "in material_options" not in section


def test_selected_material_must_still_be_a_compatible_candidate():
    material = SimpleNamespace(id=uuid4(), canonical_name="Материал")
    requirement = SimpleNamespace(canonical_material_id=None)
    gap = SimpleNamespace(status="RESOLVED_EXISTING", resolved_material_id=material.id)
    assert module2_workbench._selected_material(requirement, gap, [material]) is material
    assert module2_workbench._selected_material(requirement, gap, []) is None
    gap.status = "OPEN"
    assert module2_workbench._selected_material(requirement, gap, [material]) is None
    requirement.canonical_material_id = material.id
    assert module2_workbench._selected_material(requirement, None, [material]) is material


def test_foundation_family_description_is_matched_by_code_not_position():
    env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape(("html",)))
    first = SimpleNamespace(code="STRIP_FOUNDATIONS", name="Ленточный")
    second = SimpleNamespace(code="SLAB_FOUNDATIONS", name="Плитный")
    intro = "Описание только плитного фундамента"
    comparison = [{"category": second, "article": {
        "intro": intro, "uses": ["Применение"], "advantages": ["Преимущество"], "limitations": ["Ограничение"],
    }}]
    overview = {"intro": "Введение", "principle": "Принцип", "steps": "Этапы", "project_checks": []}
    html = env.get_template("module2_encyclopedia.html").render(
        view="category", category=SimpleNamespace(code="FOUNDATIONS", name="Фундаменты"),
        overview=overview, breadcrumb=[], children=[{"category": first}, {"category": second}],
        comparison=comparison, technologies=[], related_technologies=[], materials=[], can_workbench=False,
    )
    first_item = html.split('/categories/STRIP_FOUNDATIONS', 1)[1].split('</li>', 1)[0]
    second_item = html.split('/categories/SLAB_FOUNDATIONS', 1)[1].split('</li>', 1)[0]
    assert intro not in first_item
    assert intro in second_item


def test_active_technology_omits_empty_activation_panels():
    env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape(("html",)))
    technology = SimpleNamespace(id=uuid4(), name="Стена подвала", revision=1, status="ACTIVE", description="Описание")
    html = env.get_template("module2_technology_detail.html").render(
        technology=technology, category_name="Подвал", category_code=None, status_label="Действует",
        permissions={"edit": False, "approve": False, "admin": False},
        active_tab="general", activation_blockers=[], warnings=[],
    )
    assert "Описание" in html
    assert "Готовность к активации" not in html
    assert "Блокирующих причин нет" not in html
    assert "Предупреждений нет" not in html


@pytest.mark.asyncio
async def test_category_status_and_search_filters_are_combined(monkeypatch):
    first, second = uuid4(), uuid4()
    categories = [
        SimpleNamespace(id=first, name="Первый раздел", status="ACTIVE"),
        SimpleNamespace(id=second, name="Второй раздел", status="ACTIVE"),
    ]

    def row(name, category, status, code):
        return {
            "id": uuid4(), "name": name, "code": code, "revision": 1,
            "status": status, "status_label": status, "system_code": "SYSTEM",
            "category_id": category, "blocker_count": 1,
            "unresolved_material_count": 1, "open_gap_count": 1, "updated_at": None,
        }

    rows = [row("Нужная технология", first, "DRAFT", "MATCH"),
            row("Другой статус", first, "ACTIVE", "MATCH"),
            row("Другая категория", second, "DRAFT", "MATCH"),
            row("Архивная технология", first, "ARCHIVED", "MATCH")]
    monkeypatch.setattr(module2_workbench, "build_technology_list_view", AsyncMock(return_value=rows))
    monkeypatch.setattr(module2_workbench, "list_categories", AsyncMock(return_value=categories))
    app = FastAPI()
    app.include_router(module2_workbench.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)
    app.dependency_overrides[get_db] = lambda: None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/module2/workbench", params={
            "category": str(first), "status": "DRAFT", "q": "MATCH",
            "materials": "needs_selection", "blockers": "yes",
        })
        gaps = await client.get("/api/v1/admin/module2/workbench", params={"materials": "open_gap"})
        review = await client.get("/api/v1/admin/module2/workbench", params={"status": "REVIEW"})
        default = await client.get("/api/v1/admin/module2/workbench")
        archived = await client.get("/api/v1/admin/module2/workbench", params={"status": "ARCHIVED"})

    assert response.status_code == 200
    assert "Нужная технология" in response.text
    assert "Другой статус" not in response.text
    assert "Другая категория" not in response.text
    assert "<th>Редакция</th>" not in response.text
    assert "<th>Действия</th>" not in response.text
    assert "<th>Материалы</th>" not in response.text
    assert f'value="{first}" selected' in response.text
    assert "data-quick-action-hide-empty=\"true\"" in response.text
    assert 'href="/api/v1/admin/module2/workbench?materials=open_gap"' in response.text
    assert gaps.status_code == 200 and "Нужная технология" in gaps.text
    assert review.status_code == 200 and "Нужная технология" not in review.text
    assert "Архивная технология" not in default.text
    assert "Архивная технология" in archived.text


@pytest.mark.asyncio
async def test_encyclopedia_navigation_shows_only_public_root_categories(monkeypatch):
    root_id = uuid4()
    categories = [
        SimpleNamespace(id=root_id, parent_id=None, code="FOUNDATIONS", name="Фундаменты", status="ACTIVE", sort_order=2),
        SimpleNamespace(id=uuid4(), parent_id=root_id, code="STRIP", name="Лента", status="ACTIVE", sort_order=0),
        SimpleNamespace(id=uuid4(), parent_id=None, code="HIDDEN", name="Черновик", status="DRAFT", sort_order=0),
        SimpleNamespace(id=uuid4(), parent_id=None, code="ROOF", name="Крыша", status="ACTIVE", sort_order=1),
    ]
    monkeypatch.setattr(module2_encyclopedia, "list_categories", AsyncMock(return_value=categories))
    app = FastAPI()
    app.include_router(module2_encyclopedia.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)
    app.dependency_overrides[get_db] = lambda: None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/module2/encyclopedia/navigation")
        asset = await client.get("/api/v1/module2/encyclopedia/assets/categories")
    assert response.status_code == 200
    assert response.json() == {"categories": [
        {"code": "ROOF", "name": "Крыша"}, {"code": "FOUNDATIONS", "name": "Фундаменты"},
    ]}
    assert asset.status_code == 200
    assert asset.headers["content-type"].startswith("image/svg+xml")
