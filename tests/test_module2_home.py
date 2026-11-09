from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

import app.api.v1.module2_home as home_routes
from app.api.deps import get_current_user
from app.api.v1.module2_home import router as home_router
from app.api.v1.module2_workbench import router as workbench_router
from app.core.browser_auth import browser_auth_redirect_middleware
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.database import get_db
from app.models.module2_technology import MODULE2_OWNER_CODE
from app.services.module2_home import HOUSE_ZONES, ZONE_GROUPS, home_zones


def categories():
    return tuple(SimpleNamespace(id=uuid4(), parent_id=None, status="ACTIVE", sort_order=index,
                                 name=name, code=code)
                 for index, (_, code, name, _) in enumerate(HOUSE_ZONES))


def actor(level):
    return SimpleNamespace(id=uuid4(), role="SUPPLIER", moduleAccessRules=[{
        "moduleCode": MODULE2_OWNER_CODE, "accessLevel": level, "accessScope": "GLOBAL",
    }])


def make_app(user):
    app = FastAPI()
    app.middleware("http")(browser_auth_redirect_middleware)
    app.include_router(home_router, prefix="/api/v1")
    app.include_router(workbench_router, prefix="/api/v1")

    async def db_override():
        yield SimpleNamespace()

    def user_override():
        if user is None:
            raise UnauthorizedError()
        return user

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = user_override
    app.add_exception_handler(ForbiddenError, lambda _request, exc: JSONResponse({"detail": str(exc)}, status_code=403))
    app.add_exception_handler(UnauthorizedError, lambda _request, exc: JSONResponse({"detail": str(exc)}, status_code=401))
    return app


def test_zone_mapping_covers_approved_taxonomy_and_all_list_groups():
    expected = {
        "PREPARATION", "FOUNDATIONS", "WALLS", "PARTITIONS", "FLOORS_AND_STAIRS", "ROOF",
        "FACADE_AND_OPENINGS", "SITE_WORKS", "INTERIOR_ROUGH", "INTERIOR_FINISH",
        "WATER_AND_SEWER", "HEATING_AND_DHW", "VENTILATION_AND_AC",
        "ELECTRICAL_AND_AUTOMATION", "GAS_AND_COMBUSTION", "FINAL_INSTALLATION",
    }
    zones = home_zones(categories())
    assert {item["category_code"] for item in zones} == expected
    assert {part for _, parts in ZONE_GROUPS for part in parts} == {item["part"] for item in zones}
    assert all(item["url"] == f'/api/v1/module2/encyclopedia/categories/{item["category_code"]}' for item in zones)
    unavailable = home_zones(categories()[1:])[0]
    assert unavailable["url"] is None


@pytest.mark.asyncio
async def test_home_view_security_and_safe_query(monkeypatch):
    monkeypatch.setattr(home_routes, "list_categories", AsyncMock(return_value=categories()))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=make_app(actor("VIEW"))), base_url="http://test") as client:
        home = await client.get("/api/v1/module2")
        assert home.status_code == 200
        assert "Технологии строительства" in home.text
        assert 'href="/api/v1/module2/encyclopedia"' in home.text
        assert 'href="/api/v1/admin/module2/workbench">Технологии</a>' not in home.text
        assert "data-quick-action-hide-empty" in home.text
        assert 'data-widget-key="' not in home.text
        assert (await client.get("/api/v1/admin/module2/workbench")).status_code == 403
        selected = await client.get("/api/v1/module2?view=exterior&part=roof")
        assert 'data-selected="roof" data-view="exterior"' in selected.text
        unknown = await client.get("/api/v1/module2?view=unknown&part=unknown")
        assert unknown.status_code == 200 and 'data-selected="foundations" data-view="cutaway"' in unknown.text
        assert (await client.get("/api/v1/module2/home-assets/cutaway")).status_code == 200
        assert (await client.get("/api/v1/module2/home-assets/other")).status_code == 404
    for level in ("EDIT", "APPROVE", "ADMIN"):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=make_app(actor(level))), base_url="http://test") as client:
            home = await client.get("/api/v1/module2")
            assert home.status_code == 200
            assert 'href="/api/v1/admin/module2/workbench">Технологии</a>' in home.text
    for user in (actor("NO_ACCESS"), SimpleNamespace(id=uuid4(), role="SUPPLIER")):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=make_app(user)), base_url="http://test") as client:
            assert (await client.get("/api/v1/module2")).status_code == 403
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=make_app(None)), base_url="http://test") as client:
        response = await client.get("/api/v1/module2", headers={"Accept": "text/html"}, follow_redirects=False)
        assert response.status_code == 303 and "/auth/login/view" in response.headers["location"]


@pytest.mark.asyncio
async def test_explicit_deny_overrides_role(monkeypatch):
    monkeypatch.setattr(home_routes, "list_categories", AsyncMock(return_value=categories()))
    denied = actor("NO_ACCESS")
    denied.role = "ADMIN"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=make_app(denied)), base_url="http://test") as client:
        assert (await client.get("/api/v1/module2")).status_code == 403


@pytest.mark.asyncio
async def test_live_home_routes_are_read_only():
    if os.getenv("M2_HOME_LIVE_SMOKE") != "1":
        pytest.skip("explicit read-only live smoke only")
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.v1.module2_encyclopedia import router as encyclopedia_router
    from app.config import settings
    from app.services.module2_content_catalog import list_categories

    url = make_url(settings.DATABASE_URL)
    assert url.database == "buildplatform"
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            actual_zones = home_zones(await list_categories(session))
            assert len(actual_zones) == 16 and all(zone["url"] for zone in actual_zones)
            app = make_app(actor("ADMIN"))
            app.include_router(encyclopedia_router, prefix="/api/v1")

            async def live_db():
                yield session

            app.dependency_overrides[get_db] = live_db
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                for path in ("/api/v1/module2", "/api/v1/module2/encyclopedia",
                             "/api/v1/admin/module2/workbench", "/api/v1/module2/home-assets/cutaway",
                             "/api/v1/module2/home-assets/exterior"):
                    assert (await client.get(path)).status_code == 200, path
                for zone in actual_zones:
                    assert (await client.get(zone["url"])).status_code == 200, zone["part"]
    finally:
        await engine.dispose()
