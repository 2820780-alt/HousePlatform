from decimal import Decimal
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import httpx
from fastapi import FastAPI
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.api.deps import get_current_user
from app.api.v1 import module2_workbench
from app.database import get_db
from app.models.enums import UserRole
from app.services import module2_encyclopedia
from app.services.module1_matching_dedup import build_match_candidate, compare_characteristics, compare_dimensions
from app.services.module1_material_normalizer import normalize_characteristics, normalize_raw_ingestion_item
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem
from app.services.module2_foundation_comparison import CRITERIA, SCENARIOS, foundation_comparison
from app.api.v1.module2_workbench import _perform_action


def _row(code, name, category_id=None):
    return {"technology": SimpleNamespace(id=uuid4(), technology_code=code, name=name,
                                           category_id=category_id or uuid4())}


@pytest.mark.parametrize("title", ["Бетон B25", "Бетон В25", "Бетон в 25"])
def test_existing_normalizer_recognizes_concrete_class_in_both_alphabets(title):
    result = normalize_characteristics("ready_mix_concrete", {}, title)
    assert result["concrete_class"] == "B25"
    assert result == normalize_characteristics("ready_mix_concrete", {}, title)


@pytest.mark.parametrize("title", ["Арматура А500С Ø12", "Арматура A500C ⌀ 12", "Арматура А500С 12 мм"])
def test_existing_normalizer_keeps_rebar_class_and_diameter(title):
    result = normalize_characteristics("rebar", {}, title)
    assert result["steel_class"] == "A500C"
    assert result["diameter_mm"] == Decimal("12")


def test_normalized_different_material_characteristics_are_conflicts():
    c25 = normalize_characteristics("ready_mix_concrete", {}, "Бетон В25")
    c30 = normalize_characteristics("ready_mix_concrete", {}, "Бетон B30")
    rebar12 = normalize_characteristics("rebar", {}, "Арматура A500C Ø12")
    rebar16 = normalize_characteristics("rebar", {}, "Арматура A500C Ø16")
    assert "concrete_class" in compare_characteristics(c25, c30).conflicting_fields
    assert "diameter_mm" in compare_dimensions(rebar12, rebar16).conflicting_fields


def test_m1_ingestion_normalization_is_idempotent_and_conflicts_are_not_exact():
    raw = Module1RawIngestionItem(legacy_source="raw_payload", raw_title="Арматура A500C Ø12",
                                  raw_category="арматура", raw_unit="кг")
    candidate = normalize_raw_ingestion_item(raw)
    assert candidate == normalize_raw_ingestion_item(raw)
    candidate = replace(candidate, suggested_group_code="rebar",
                        normalized_characteristics=normalize_characteristics("rebar", {}, raw.raw_title))
    existing = {"id": "other-diameter", "canonical_name": "Арматура A500C Ø16",
                "group_code": "rebar", "normalized_characteristics": {
                    "steel_class": "A500C", "diameter_mm": Decimal("16")}, "unit": candidate.normalized_unit}
    match = build_match_candidate(candidate, [existing])
    assert "diameter_mm" in match.conflicting_fields
    assert match.decision_hint not in {"exact_match", "strong_match"}


def test_foundation_compare_uses_only_available_public_rows_and_real_scenarios():
    strip = _row("FND_STRIP_MONOLITHIC_RC", "Монолитная лента")
    slab = _row("FND_SLAB_MONOLITHIC_RC", "Монолитная плита")
    insulation = _row("FND_SUBSTRUCTURE_INSULATION_XPS", "Утепление")
    rows = (strip, slab, insulation)
    result = foundation_comparison(rows, [], "basement")
    assert [item.name for item in result["options"]] == ["Монолитная лента", "Монолитная плита"]
    assert len(result["columns"]) == 2
    assert result["criteria"][0][0] == "basement"
    assert len(result["criteria"]) == len(CRITERIA)
    assert len(SCENARIOS) == 4
    for scenario, (_, priority) in SCENARIOS.items():
        assert foundation_comparison(rows, [], scenario)["criteria"][0][0] == priority[0]
    assert foundation_comparison(rows, [strip["technology"].technology_code] * 2, "")["error"]
    assert foundation_comparison(rows, [strip["technology"].technology_code, "NOT_PUBLIC"], "")["error"]
    assert foundation_comparison(rows, [strip["technology"].technology_code] * 4, "")["error"]


@pytest.mark.asyncio
async def test_preparation_relationship_is_not_a_category_technology(monkeypatch):
    prep_id, pile_id = uuid4(), uuid4()
    prep = SimpleNamespace(id=prep_id, parent_id=None, code="PREPARATION", name="Подготовка", description=None)
    pile = SimpleNamespace(id=pile_id, parent_id=None, code="PILE_FOUNDATIONS", name="Сваи", description=None)
    driven = _row("FND_PILE_DRIVEN_RC", "Забивные сваи", pile_id)
    driven["category"] = pile
    rows = ({"category": prep}, {"category": pile})
    monkeypatch.setattr(module2_encyclopedia, "public_catalog", AsyncMock(return_value={
        "all_categories": rows, "technologies": (driven,),
    }))
    node = SimpleNamespace(technology_id=driven["technology"].id,
                           conditions={"category_code": "PREPARATION"},
                           name="Подготовка площадки", description="Подготовка относится к PREPARATION.")
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [node])))
    result = await module2_encyclopedia.public_category(db, "PREPARATION")
    assert result["technologies"] == ()
    assert result["related_technologies"][0]["relationship_name"] == "Подготовка площадки"
    assert result["related_technologies"][0]["relationship_description"] == "Подготовка относится к разделу «Подготовка»."
    env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape(("html",)))
    html = env.get_template("module2_encyclopedia.html").render(view="category", **result)
    assert "Связанные технологии из других разделов" in html
    assert "Связь: Подготовка площадки" in html
    assert "Иллюстрация раздела, не рабочая схема" not in html


def test_empty_compatibility_is_hidden_for_active_but_editable_in_draft():
    env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape(("html",)))
    template = env.get_template("module2_technology_detail.html")
    context = {"category_name": "Фундаменты", "category_code": None, "active_tab": "rules",
               "permissions": {"edit": True, "approve": True, "admin": True},
               "compatibility": [], "rules": [], "rule_groups": {}, "status_label": "Действует"}
    active = SimpleNamespace(id=uuid4(), name="Плита", revision=1, status="ACTIVE", description="")
    draft = SimpleNamespace(id=uuid4(), name="Плита", revision=2, status="DRAFT", description="")
    assert 'id="compatibility"' not in template.render(technology=active, **context)
    assert 'id="compatibility"' in template.render(technology=draft, **context)


@pytest.mark.asyncio
@pytest.mark.parametrize("component", ["norm", "compatibility", "rule"])
@pytest.mark.parametrize("status", ["ACTIVE", "REVIEW", "ARCHIVED"])
async def test_workbench_cannot_change_knowledge_in_a_non_draft_technology(component, status):
    technology = SimpleNamespace(status=status)
    db = SimpleNamespace()
    with pytest.raises(ValueError, match="черновой редакции"):
        await _perform_action("transition-knowledge", {"component": component, "target": "ARCHIVED",
                              "item_id": str(uuid4())}, technology=technology, db=db,
                              role_code="PLATFORM_ADMIN", user_id=None)


@pytest.mark.asyncio
async def test_direct_workbench_endpoint_rejects_active_child_transition(monkeypatch):
    tech_id, rule_id = uuid4(), uuid4()
    technology = SimpleNamespace(id=tech_id, status="ACTIVE")
    db = SimpleNamespace(rollback=AsyncMock(), flush=AsyncMock())
    monkeypatch.setattr(module2_workbench, "read_technology", AsyncMock(return_value=technology))
    app = FastAPI()
    app.include_router(module2_workbench.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)
    app.dependency_overrides[get_db] = lambda: db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/admin/module2/workbench/{tech_id}/actions/transition-knowledge",
                                     data={"component": "rule", "target": "ARCHIVED", "item_id": str(rule_id)})
    assert response.status_code == 303
    assert "error=" in response.headers["location"]
    db.rollback.assert_awaited_once()
    db.flush.assert_not_awaited()


def test_active_technology_hides_child_lifecycle_actions():
    env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape(("html",)))
    technology = SimpleNamespace(id=uuid4(), name="Плита", revision=1, status="ACTIVE", description="")
    rule = {"model": SimpleNamespace(id=uuid4(), status="ACTIVE"), "display_text": "Проверить основание",
            "phase_label": None, "status_label": "Действует", "conflicts": []}
    html = env.get_template("module2_technology_detail.html").render(
        technology=technology, category_name="Фундаменты", category_code=None, active_tab="rules",
        permissions={"edit": True, "approve": True, "admin": True}, compatibility=[],
        rules=[rule], rule_groups={"Применимость": [rule]}, status_label="Действует")
    assert "Проверить основание" in html
    assert "/actions/transition-knowledge" not in html
