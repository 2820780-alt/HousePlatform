from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.api.v1.module2_encyclopedia import router
from app.config import settings
from app.database import Base, get_db, init_db
from app.models.enums import UserRole
from app.models.knowledge_resource import KnowledgeResource
from app.models.knowledge_resource_link import KnowledgeResourceLink
from app.models.material_category import MaterialCategory
from app.models.module2_content_catalog import TechnologyCategory
from app.models.module2_knowledge import ConsumptionNorm
from app.models.module2_technology import Technology
from app.services.module1_work_catalog import get_work_item
from app.services.module2_encyclopedia import public_technology, technology_article
from app.services.module2_technology_foundation import read_technology


ACTIVE_CODES = (
    "FND_STRIP_MONOLITHIC_RC", "FND_STRIP_PRECAST_FBS_FL", "FND_SLAB_MONOLITHIC_RC",
)
RIBBED_CODE = "FND_SLAB_RIBBED_RC"


def _isolated_engine():
    name = os.getenv("M2_FOUNDATIONS_TEST_DATABASE")
    if not name:
        pytest.skip("set M2_FOUNDATIONS_TEST_DATABASE to an isolated restored database")
    assert name.startswith("houseplatform_m2_foundations_dryrun_")
    assert name != "buildplatform"
    return create_async_engine(make_url(settings.DATABASE_URL).set(database=name))


def test_foundation_work_codes_are_m1_owned():
    for code in ("foundations_concrete_ustroystvo_lentochnogo_fundamenta",):
        work = get_work_item(code)
        assert work is not None
        assert work.work_group == "foundations_concrete"
    assert get_work_item("foundations_concrete_montazh_fundamentnyh_plit_fl") is not None
    assert get_work_item("foundations_concrete_montazh_blokov_fbs") is not None


@pytest.mark.asyncio
async def test_foundation_content_integrity_and_lifecycle():
    engine = _isolated_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            categories = {
                row.code: row for row in (await db.scalars(select(TechnologyCategory))).all()
            }
            assert categories["FOUNDATIONS"].content_status == "CONTENT_COMPLETE"
            assert categories["STRIP_FOUNDATIONS"].content_status == "CONTENT_COMPLETE"
            assert categories["SLAB_FOUNDATIONS"].content_status == "CONTENT_COMPLETE"

            rows = (await db.scalars(select(Technology).where(
                Technology.technology_code.in_((*ACTIVE_CODES, RIBBED_CODE))
            ))).all()
            assert len(rows) == 6
            assert {row.technology_code for row in rows if row.status == "ACTIVE"} == {
                *ACTIVE_CODES, RIBBED_CODE,
            }
            historical = next(row for row in rows if row.technology_code == RIBBED_CODE
                              and row.revision == 1)
            assert historical.status == "ARCHIVED"
            assert historical.input_blockers
            assert next(row for row in rows if row.technology_code ==
                        "FND_STRIP_PRECAST_FBS_FL" and row.revision == 1).status == "ARCHIVED"
            assert (await public_technology(db, RIBBED_CODE)).revision == 2

            for row in rows:
                technology = await read_technology(db, row.id)
                assert technology is not None
                assert technology.category_id == categories[
                    "SLAB_FOUNDATIONS" if "SLAB" in technology.technology_code
                    else "STRIP_FOUNDATIONS"
                ].id
                assert technology.layers and technology.requirements and technology.work_steps
                positions = [step.position for step in technology.work_steps]
                assert positions == list(range(1, len(positions) + 1))
                assert all(get_work_item(step.work_code) for step in technology.work_steps)
                for req in technology.requirements:
                    category = await db.get(MaterialCategory, req.material_category_id)
                    assert req.selector_kind == "MATERIAL_CLASS"
                    assert category is not None and category.status == "ACTIVE"
                    assert any(e.target_kind == "MATERIAL_REQUIREMENT" and
                               e.target_reference == str(req.id)
                               for e in technology.evidence_references)
                for step in technology.work_steps:
                    assert any(e.target_kind == "WORK_STEP" and
                               e.target_reference == str(step.id)
                               for e in technology.evidence_references)
                for layer in technology.layers:
                    assert any(e.target_kind == "LAYER" and
                               e.target_reference == str(layer.id)
                               for e in technology.evidence_references)
                for node in technology.nodes:
                    assert any(e.target_kind == "NODE" and
                               e.target_reference == str(node.id)
                               for e in technology.evidence_references)
                if technology.status == "ACTIVE":
                    assert len(technology.knowledge_rules) == 7
                    assert all(rule.status == "ACTIVE" and rule.outcome_type == "INFORMATION"
                               for rule in technology.knowledge_rules)
                    assert all(any(e.target_kind == "KNOWLEDGE_RULE" and
                                   e.target_reference == str(rule.id)
                                   for e in technology.evidence_references)
                               for rule in technology.knowledge_rules)
                    article = await technology_article(db, technology)
                    assert article["evidence"]
                    assert article["editorial"]["quality_before"]
                    assert article["editorial"]["common_error"]
            assert await db.scalar(select(func.count()).select_from(ConsumptionNorm)) == 0
            assert await db.scalar(select(func.count()).select_from(KnowledgeResource).where(
                KnowledgeResource.resource_type == "STANDARD_REFERENCE"
            )) >= 11
            assert await db.scalar(select(func.count()).select_from(KnowledgeResourceLink).where(
                KnowledgeResourceLink.link_type == "APPLIES_TO"
            )) >= 8
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_foundation_encyclopedia_routes_and_links():
    engine = _isolated_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")

            async def session_override():
                yield db

            app.dependency_overrides[get_db] = session_override
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                id=uuid4(), role=UserRole.ADMIN,
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                for code in ACTIVE_CODES:
                    technology = await public_technology(db, code)
                    assert technology is not None
                    detail = await client.get(f"/api/v1/module2/encyclopedia/technologies/{code}")
                    assert detail.status_code == 200
                    assert all(label in detail.text for label in (
                        "Где применяется", "Когда не подходит", "Материалы", "Порядок работ",
                        "Контроль качества", "Типичные ошибки", "Источники",
                    ))
                    assert str(technology.id) not in detail.text
                    assert "protect.gost.ru" in detail.text
                    article = await technology_article(db, await read_technology(db, technology.id))
                    req = article["requirements"][0]["model"]
                    node = article["nodes"][0]
                    step = article["steps"][0]["model"]
                    for suffix in (
                        f"technologies/{code}/materials/{req.code}",
                        f"technologies/{code}/nodes/{node.code}",
                        f"works/{step.work_code}",
                    ):
                        assert (await client.get(f"/api/v1/module2/encyclopedia/{suffix}")).status_code == 200
                assert (await client.get(
                    f"/api/v1/module2/encyclopedia/technologies/{RIBBED_CODE}"
                )).status_code == 200
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_foundation_clone_startup_has_no_implicit_create_all(monkeypatch):
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
