from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.api.v1.module2_encyclopedia import router
from app.config import settings
from app.core.exceptions import ForbiddenError
from app.database import Base, get_db, init_db
from app.models.enums import UserRole
from app.models.module2_content_catalog import TechnologyCategory
from app.models.module2_technology import Technology
from app.services.module2_content_catalog import category_tree, list_categories


APPROVED_ROOTS = (
    ("PREPARATION", "Подготовка и демонтаж"),
    ("FOUNDATIONS", "Фундаменты и подземная часть"),
    ("WALLS", "Стены и несущий каркас"),
    ("PARTITIONS", "Перегородки"),
    ("FLOORS_AND_STAIRS", "Перекрытия, полы по грунту и лестницы"),
    ("ROOF", "Крыша, кровля и водосток"),
    ("FACADE_AND_OPENINGS", "Фасад, окна и наружные двери"),
    ("SITE_WORKS", "Работы вокруг дома"),
    ("INTERIOR_ROUGH", "Черновая внутренняя отделка"),
    ("INTERIOR_FINISH", "Чистовая отделка"),
    ("WATER_AND_SEWER", "Водоснабжение и канализация"),
    ("HEATING_AND_DHW", "Отопление и горячая вода"),
    ("VENTILATION_AND_AC", "Вентиляция и кондиционирование"),
    ("ELECTRICAL_AND_AUTOMATION", "Электрика, слаботочка и умный дом"),
    ("GAS_AND_COMBUSTION", "Газ, дымоходы, печи и камины"),
    ("FINAL_INSTALLATION", "Финальное оснащение"),
)
FOUNDATION_CHILDREN = (
    "STRIP_FOUNDATIONS", "SLAB_FOUNDATIONS", "PILE_FOUNDATIONS",
    "PILE_GRILLAGE_FOUNDATIONS", "COLUMN_FOUNDATIONS", "BASEMENT_AND_SUBSTRUCTURE",
)


def _isolated_engine():
    name = os.getenv("M2_APPROVED_CATALOG_TEST_DATABASE")
    if not name:
        pytest.skip("set M2_APPROVED_CATALOG_TEST_DATABASE to an isolated restored database")
    assert name != make_url(settings.DATABASE_URL).database
    return create_async_engine(make_url(settings.DATABASE_URL).set(database=name))


@pytest.mark.asyncio
async def test_approved_taxonomy_tree_and_no_technology_seed():
    engine = _isolated_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            categories = await list_categories(db)
            roots = sorted((item for item in categories if item.parent_id is None), key=lambda item: item.sort_order)
            assert len(categories) == 22
            assert tuple((item.code, item.name) for item in roots) == APPROVED_ROOTS
            assert [item.sort_order for item in roots] == list(range(10, 161, 10))
            assert all(item.status == "ACTIVE" and item.scope_code == "RESIDENTIAL" for item in categories)
            assert all(item.code.isascii() and item.code == item.code.upper() for item in categories)
            foundations = next(item for item in roots if item.code == "FOUNDATIONS")
            children = sorted(
                (item for item in categories if item.parent_id == foundations.id),
                key=lambda item: item.sort_order,
            )
            assert tuple(item.code for item in children) == FOUNDATION_CHILDREN
            assert [item.sort_order for item in children] == [10, 20, 30, 40, 50, 60]
            assert foundations.content_status == "IN_PROGRESS"
            assert all(item.content_status == "EMPTY" for item in categories if item.id != foundations.id)
            assert len(category_tree(categories, public=True)) == 22
            assert await db.scalar(select(func.count()).select_from(Technology)) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_foundations_navigation_and_reader_boundary():
    engine = _isolated_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")

            async def session_override():
                yield db

            app.dependency_overrides[get_db] = session_override
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                id=uuid4(), role=UserRole.ADMIN,
            )

            @app.exception_handler(ForbiddenError)
            async def forbidden_handler(_request, exc):
                return JSONResponse({"detail": str(exc)}, status_code=403)

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                index = await client.get("/api/v1/module2/encyclopedia")
                foundations = await client.get("/api/v1/module2/encyclopedia/categories/FOUNDATIONS")
                child = await client.get(
                    "/api/v1/module2/encyclopedia/categories/STRIP_FOUNDATIONS"
                )
                unpublished = await client.get(
                    "/api/v1/module2/encyclopedia/technologies/UNAPPROVED"
                )
                app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                    id=uuid4(), role=UserRole.SUPPLIER,
                )
                forbidden = await client.get("/api/v1/module2/encyclopedia")

            assert index.status_code == foundations.status_code == child.status_code == 200
            assert "FOUNDATIONS" in index.text
            assert "STRIP_FOUNDATIONS" in foundations.text
            assert "Наполнение: в работе" in foundations.text
            assert "Опубликованных технологий пока нет" in foundations.text
            assert unpublished.status_code == 404
            assert forbidden.status_code == 403
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_seeded_clone_starts_without_implicit_schema_creation(monkeypatch):
    engine = _isolated_engine()
    try:
        from app import database

        monkeypatch.setattr(database, "engine", engine)

        def forbidden_create_all(*_args, **_kwargs):
            raise AssertionError("normal startup must not create schema")

        monkeypatch.setattr(Base.metadata, "create_all", forbidden_create_all)
        await init_db()
    finally:
        await engine.dispose()
