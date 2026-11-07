from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.api.v1.module2_encyclopedia import router
from app.config import settings
from app.database import get_db
from app.models.enums import UserRole
from app.models.material_category import MaterialCategory
from app.models.module2_content_catalog import TechnologyCategory
from app.models.module2_technology import Technology
from app.services.module1_work_catalog import get_work_item
from app.services.module2_encyclopedia import public_technology, technology_article
from app.services.module2_technology_foundation import read_technology


A2_CODES = (
    "FND_PILE_BORED_RC",
    "FND_PILE_SCREW",
    "FND_PILE_GRILLAGE",
    "FND_COLUMN_CONCRETE_RC",
    "FND_BASEMENT_WALL_MONOLITHIC",
    "FND_SUBSTRUCTURE_WATERPROOFING_COATING",
    "FND_SUBSTRUCTURE_INSULATION_XPS",
)


def _isolated_engine():
    name = os.getenv("M2_FOUNDATIONS_TEST_DATABASE")
    if not name:
        pytest.skip("set M2_FOUNDATIONS_TEST_DATABASE to an isolated restored database")
    assert name.startswith("houseplatform_m2_foundations_dryrun_")
    assert name != "buildplatform"
    return create_async_engine(make_url(settings.DATABASE_URL).set(database=name))


@pytest.mark.asyncio
async def test_a2_references_lifecycle_and_enrichment():
    engine = _isolated_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            categories = {item.code: item for item in (await db.scalars(select(TechnologyCategory))).all()}
            assert categories["FOUNDATIONS"].content_status == "IN_PROGRESS"
            for code in ("PILE_FOUNDATIONS", "PILE_GRILLAGE_FOUNDATIONS", "COLUMN_FOUNDATIONS",
                         "BASEMENT_AND_SUBSTRUCTURE"):
                assert categories[code].content_status == "IN_PROGRESS"

            rows = (await db.scalars(select(Technology).where(
                Technology.technology_code.in_(A2_CODES)
            ))).all()
            assert len(rows) == len(A2_CODES)
            for row in rows:
                assert row.status == "ACTIVE"
                tech = await read_technology(db, row.id)
                assert tech is not None
                assert tech.requirements and tech.layers and tech.work_steps and tech.nodes
                assert len(tech.knowledge_rules) == 7
                assert [step.position for step in tech.work_steps] == list(
                    range(1, len(tech.work_steps) + 1)
                )
                assert all(get_work_item(step.work_code) for step in tech.work_steps)
                targets = {(e.target_kind, e.target_reference) for e in tech.evidence_references}
                assert ("TECHNOLOGY", None) in targets
                for model, kind in (
                    (tech.requirements, "MATERIAL_REQUIREMENT"),
                    (tech.layers, "LAYER"),
                    (tech.work_steps, "WORK_STEP"),
                    (tech.nodes, "NODE"),
                    (tech.knowledge_rules, "KNOWLEDGE_RULE"),
                ):
                    assert all((kind, str(item.id)) in targets for item in model)
                for req in tech.requirements:
                    category = await db.get(MaterialCategory, req.material_category_id)
                    assert category is not None and category.status == "ACTIVE"
                article = await technology_article(db, tech)
                assert article["editorial"]["common_error"]
                assert article["editorial"]["project_dependent"]
                assert article["evidence"]

            assert await public_technology(db, "FND_PILE_DRIVEN_RC") is None
            assert await public_technology(db, "FND_BASEMENT_WALL_PRECAST") is None
            assert await public_technology(db, "FND_SLAB_RIBBED_RC") is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a2_encyclopedia_pages_and_nodes():
    engine = _isolated_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")

            async def session_override():
                yield db

            app.dependency_overrides[get_db] = session_override
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                id=uuid4(), role=UserRole.ADMIN
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                for code in A2_CODES:
                    tech = await public_technology(db, code)
                    assert tech is not None
                    detail = await client.get(f"/api/v1/module2/encyclopedia/technologies/{code}")
                    assert detail.status_code == 200
                    for label in ("Материалы", "Порядок работ", "Контроль качества",
                                  "Типичные ошибки", "Источники"):
                        assert label in detail.text
                    node = tech.nodes[0]
                    response = await client.get(
                        f"/api/v1/module2/encyclopedia/technologies/{code}/nodes/{node.code}"
                    )
                    assert response.status_code == 200
                    assert node.name in response.text
                for code in ("FND_PILE_DRIVEN_RC", "FND_BASEMENT_WALL_PRECAST",
                             "FND_SLAB_RIBBED_RC"):
                    assert (await client.get(
                        f"/api/v1/module2/encyclopedia/technologies/{code}"
                    )).status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a2_live_encyclopedia_smoke():
    if os.getenv("M2_FOUNDATIONS_LIVE_SMOKE") != "1":
        pytest.skip("explicit read-only live smoke only")
    url = make_url(settings.DATABASE_URL)
    assert url.database == "buildplatform"
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")

            async def session_override():
                yield db

            app.dependency_overrides[get_db] = session_override
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                id=uuid4(), role=UserRole.ADMIN
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                for code in A2_CODES:
                    response = await client.get(
                        f"/api/v1/module2/encyclopedia/technologies/{code}"
                    )
                    assert response.status_code == 200
                    assert code in response.text
                    assert "Источники" in response.text
                assert (await client.get(
                    "/api/v1/module2/encyclopedia/categories/FOUNDATIONS"
                )).status_code == 200
    finally:
        await engine.dispose()
