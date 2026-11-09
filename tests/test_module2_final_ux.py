from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.api.v1.module2_encyclopedia import router as encyclopedia_router
from app.api.v1.module2_workbench import router as workbench_router
from app.config import settings
from app.core.exceptions import ForbiddenError
from app.database import get_db
from app.models.enums import UserRole
from app.models.module2_technology import Technology
from app.services.module2_encyclopedia_editorial import (
    CATEGORY_ARTICLES, MATERIAL_NAMES, WORK_STEP_GUIDANCE,
    effective_material_name, material_default_label,
)


FAMILIES = (
    "STRIP_FOUNDATIONS", "SLAB_FOUNDATIONS", "PILE_FOUNDATIONS",
    "PILE_GRILLAGE_FOUNDATIONS", "COLUMN_FOUNDATIONS", "BASEMENT_AND_SUBSTRUCTURE",
)


@pytest.mark.parametrize("code", ("FOUNDATIONS", *FAMILIES))
def test_foundations_overview_has_article_structure(code):
    article = CATEGORY_ARTICLES[code]
    assert all(article[key] for key in (
        "intro", "principle", "uses", "advantages", "limitations", "steps", "project_checks",
    ))
    assert all(target in CATEGORY_ARTICLES for target, _ in article["comparison"])


def test_effective_material_names_are_not_internal_requirement_labels():
    concrete = SimpleNamespace(parameter_code="CONCRETE_CLASS", value_type="ENUM",
                               default_value={"value": "B25"})
    rebar_class = SimpleNamespace(parameter_code="REBAR_CLASS", value_type="ENUM",
                                  default_value={"value": "A500C"})
    diameter = SimpleNamespace(parameter_code="REBAR_DIAMETER_MM", value_type="NUMBER",
                               default_value={"value": 12})
    assert effective_material_name("CONCRETE", "Конструкционный бетон для фундаментов", (concrete,)) == "Бетон B25"
    assert effective_material_name("REBAR", "Арматура для фундаментов", (rebar_class, diameter)) == "Арматура A500C Ø12"
    assert material_default_label((rebar_class, diameter)) == "A500C Ø12"
    assert all(value and not value.isupper() for value in MATERIAL_NAMES.values())
    assert all(len(guidance) == 3 for guidance in WORK_STEP_GUIDANCE.values())


def test_public_article_keeps_m1_cards_and_gap_controls_separate():
    env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape(("html",)))
    candidate = SimpleNamespace(id=uuid4(), canonical_name="Бетон B25, вариант 1")
    another = SimpleNamespace(id=uuid4(), canonical_name="Бетон B25, вариант 2")
    technology = SimpleNamespace(name="Монолитная лента", technology_code="FND_STRIP_MONOLITHIC_RC",
                                 description="Лента передает нагрузку на грунт.", revision=1)
    category = SimpleNamespace(name="Ленточные фундаменты", code="STRIP_FOUNDATIONS")
    requirement = {"model": SimpleNamespace(code="CONCRETE", notes=None),
                   "base_name": "Бетон", "display_name": "Бетон B25", "default_label": "B25",
                   "candidates": (candidate, another), "gap": None, "sources": ()}
    article = {"technology": technology, "category": category, "editorial": {},
               "requirements": (requirement,), "layers": (), "steps": (), "defaults": (),
               "nodes": (), "norms": (), "compatibility": (), "warnings": (), "controls": (),
               "family_alternatives": (), "related_technologies": (), "related_categories": (),
               "evidence": (), "material_card_url": lambda item_id: f"/api/v1/module1/materials/{item_id}"}
    html = env.get_template("module2_encyclopedia.html").render(
        view="technology", article=article, can_workbench=False, m2_nav_active="technologies",
    )
    assert "Бетон B25" in html
    assert "Ещё 1 подходящий вариант" in html
    assert f"/api/v1/module1/materials/{candidate.id}" in html
    assert f"/api/v1/module1/materials/{another.id}" in html
    assert "material-gaps/" not in html
    assert 'aria-current="page"' in html


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith("/api/v1/module2/encyclopedia/"):
                self.links.add(href)


@pytest.mark.asyncio
async def test_live_a23_foundations_pages_read_only():
    if os.getenv("M2_A23_LIVE_SMOKE") != "1":
        pytest.skip("explicit read-only live smoke only")
    url = make_url(settings.DATABASE_URL)
    assert url.database == "buildplatform"
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            app = FastAPI()
            app.include_router(encyclopedia_router, prefix="/api/v1")
            app.include_router(workbench_router, prefix="/api/v1")

            async def session_override():
                yield db

            app.dependency_overrides[get_db] = session_override
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)

            @app.exception_handler(ForbiddenError)
            async def denied(_request, exc):
                return JSONResponse({"detail": str(exc)}, status_code=403)

            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                home = await client.get("/api/v1/module2/encyclopedia")
                categories = await client.get("/api/v1/module2/encyclopedia/categories")
                technologies = await client.get("/api/v1/module2/encyclopedia/technologies")
                assert all(response.status_code == 200 for response in (home, categories, technologies))
                foundation = await client.get("/api/v1/module2/encyclopedia/categories/FOUNDATIONS")
                assert foundation.status_code == 200
                assert "Сравнение видов" in foundation.text
                for code in FAMILIES:
                    family = await client.get(f"/api/v1/module2/encyclopedia/categories/{code}")
                    assert family.status_code == 200
                    assert all(label in family.text for label in ("Преимущества", "Ограничения", "Технологии семейства"))
                codes = (await db.scalars(select(Technology.technology_code).where(
                    Technology.status == "ACTIVE", Technology.technology_code.like("FND_%")
                ))).all()
                assert len(codes) == 15
                for code in codes:
                    page = await client.get(f"/api/v1/module2/encyclopedia/technologies/{code}")
                    assert page.status_code == 200
                    assert all(label in page.text for label in (
                        "Состав конструкции", "Материалы", "Порядок работ", "Для предварительной оценки",
                        "Контроль качества", "Что нужно уточнить", "Источники и нормативная база",
                    ))
                    assert "material-gaps/" not in page.text
                    assert 'id="source-1"' in page.text
                strip = await client.get("/api/v1/module2/encyclopedia/technologies/FND_STRIP_MONOLITHIC_RC")
                assert "Бетон B25" in strip.text and "Арматура A500C Ø12" in strip.text
                assert 'href="#source-1"' in strip.text
                material = await client.get("/api/v1/module2/encyclopedia/technologies/FND_STRIP_MONOLITHIC_RC/materials/CONCRETE")
                assert material.status_code == 200 and "Требования к бетону" in material.text
                workbench = await client.get("/api/v1/admin/module2/workbench")
                detail = await client.get("/api/v1/admin/module2/workbench/by-code/FND_STRIP_MONOLITHIC_RC", follow_redirects=True)
                assert workbench.status_code == 200 and detail.status_code == 200
                assert "Отправить в поиск M1" in detail.text and "Бетон B25" in detail.text
                parser = _Links()
                parser.feed(foundation.text + strip.text)
                for link in parser.links:
                    assert (await client.get(link)).status_code == 200, link
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4(), role=UserRole.SUPPLIER)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                assert (await client.get("/api/v1/module2/encyclopedia")).status_code == 403
    finally:
        await engine.dispose()
