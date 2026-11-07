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

from app.config import settings
from app.api.deps import get_current_user
from app.api.v1.module2_encyclopedia import router
from app.database import get_db
from app.models.enums import UserRole
from app.models.material_category import MaterialCategory
from app.models.module2_content_catalog import TechnologyCategory
from app.models.module2_technology import Technology
from app.services.module1_work_catalog import get_work_item
from app.services.module2_encyclopedia import (
    public_catalog,
    public_category,
    public_technology,
    technology_article,
)
from app.services.module2_technology_foundation import read_technology
from app.services.module2_estimation_export import build_module5_estimation_input_package


NEW_CODES = (
    "FND_STRIP_PRECAST_FBS_FL",
    "FND_SLAB_RIBBED_RC",
    "FND_SLAB_USHP",
    "FND_UFF",
    "FND_PILE_DRIVEN_RC",
    "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE",
)
FAMILIES = (
    "STRIP_FOUNDATIONS", "SLAB_FOUNDATIONS", "PILE_FOUNDATIONS",
    "PILE_GRILLAGE_FOUNDATIONS", "COLUMN_FOUNDATIONS", "BASEMENT_AND_SUBSTRUCTURE",
)


def _isolated_engine():
    name = os.getenv("M2_FOUNDATIONS_TEST_DATABASE")
    if not name:
        pytest.skip("set M2_FOUNDATIONS_TEST_DATABASE to an isolated restored database")
    assert name.startswith("houseplatform_m2_foundations_dryrun_")
    assert name != "buildplatform"
    return create_async_engine(make_url(settings.DATABASE_URL).set(database=name))


@pytest.mark.asyncio
async def test_closure_inventory_lifecycle_and_m1_references():
    engine = _isolated_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            categories = {row.code: row for row in (await db.scalars(
                select(TechnologyCategory)
            )).all()}
            assert all(categories[code].content_status == "CONTENT_COMPLETE"
                       for code in (*FAMILIES, "FOUNDATIONS"))
            catalog = await public_catalog(db)
            foundations = {row["technology"].technology_code: row["technology"]
                           for row in catalog["technologies"]
                           if row["category"].code in FAMILIES}
            assert len(foundations) == 15
            assert all(code in foundations for code in NEW_CODES)
            assert "FND_BASEMENT_WALL_PRECAST" not in foundations
            for code in NEW_CODES:
                current = await read_technology(db, foundations[code].id)
                assert current is not None and current.status == "ACTIVE"
                assert current.requirements and current.layers and current.work_steps
                assert current.nodes and current.knowledge_rules
                assert len(current.knowledge_rules) == 7
                assert [step.position for step in current.work_steps] == list(
                    range(1, len(current.work_steps) + 1)
                )
                assert all(get_work_item(step.work_code) for step in current.work_steps)
                targets = {(ref.target_kind, ref.target_reference)
                           for ref in current.evidence_references}
                assert ("TECHNOLOGY", None) in targets
                for items, kind in (
                    (current.requirements, "MATERIAL_REQUIREMENT"),
                    (current.layers, "LAYER"),
                    (current.work_steps, "WORK_STEP"),
                    (current.nodes, "NODE"),
                    (current.knowledge_rules, "KNOWLEDGE_RULE"),
                ):
                    assert all((kind, str(item.id)) in targets for item in items)
                for requirement in current.requirements:
                    material_class = await db.get(MaterialCategory,
                                                  requirement.material_category_id)
                    assert material_class is not None and material_class.status == "ACTIVE"
            rows = (await db.scalars(select(Technology).where(
                Technology.technology_code.in_(
                    ("FND_SLAB_RIBBED_RC", "FND_STRIP_PRECAST_FBS_FL")
                )
            ))).all()
            assert {(row.technology_code, row.revision, row.status) for row in rows} == {
                ("FND_SLAB_RIBBED_RC", 1, "ARCHIVED"),
                ("FND_SLAB_RIBBED_RC", 2, "ACTIVE"),
                ("FND_STRIP_PRECAST_FBS_FL", 1, "ARCHIVED"),
                ("FND_STRIP_PRECAST_FBS_FL", 2, "ACTIVE"),
            }
            for code in (
                "foundations_concrete_montazh_fundamentnyh_plit_fl",
                "foundations_concrete_montazh_blokov_fbs",
                "foundations_concrete_pogruzhenie_zhelezobetonnyh_svay",
            ):
                assert get_work_item(code) is not None
            for code in ("FND_STRIP_PRECAST_FBS_FL", "FND_PILE_DRIVEN_RC"):
                package = await build_module5_estimation_input_package(db, foundations[code].id)
                assert package.ready_for_estimation is False
                assert all(step.work_group == "foundations_concrete" for step in package.work_steps)
                assert all("unknown_m1_work_code" not in step.blockers for step in package.work_steps)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_closure_cross_category_and_reused_fbs_navigation():
    engine = _isolated_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            fbs = await public_technology(db, "FND_STRIP_PRECAST_FBS_FL")
            assert fbs is not None and fbs.revision == 2
            fbs_article = await technology_article(db, fbs)
            assert "BASEMENT_AND_SUBSTRUCTURE" in {
                category.code for category in fbs_article["related_categories"]
            }
            basement = await public_category(db, "BASEMENT_AND_SUBSTRUCTURE")
            assert basement is not None
            assert "FND_STRIP_PRECAST_FBS_FL" in {
                row["technology"].technology_code
                for row in basement["related_technologies"]
            }
            for code in ("FND_SLAB_USHP", "FND_UFF"):
                technology = await public_technology(db, code)
                assert technology is not None
                article = await technology_article(db, technology)
                assert {"FLOORS_AND_STAIRS", "HEATING_AND_DHW", "WATER_AND_SEWER"} <= {
                    category.code for category in article["related_categories"]
                }
                assert article["evidence"]
            assert await public_technology(db, "FND_BASEMENT_WALL_PRECAST") is None

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
                basement_page = await client.get(
                    "/api/v1/module2/encyclopedia/categories/BASEMENT_AND_SUBSTRUCTURE"
                )
                assert basement_page.status_code == 200
                assert "Связанные технологии" in basement_page.text
                assert "/technologies/FND_STRIP_PRECAST_FBS_FL" in basement_page.text
                for code in ("FND_SLAB_USHP", "FND_UFF"):
                    page = await client.get(f"/api/v1/module2/encyclopedia/technologies/{code}")
                    assert page.status_code == 200
                    assert "/categories/FLOORS_AND_STAIRS" in page.text
                    assert "/categories/HEATING_AND_DHW" in page.text
                for work_code in (
                    "foundations_concrete_montazh_fundamentnyh_plit_fl",
                    "foundations_concrete_montazh_blokov_fbs",
                    "foundations_concrete_pogruzhenie_zhelezobetonnyh_svay",
                ):
                    response = await client.get(f"/api/v1/module2/encyclopedia/works/{work_code}")
                    assert response.status_code == 200
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_closure_read_only_live_smoke():
    if os.getenv("M2_FOUNDATIONS_LIVE_SMOKE") != "1":
        pytest.skip("explicit read-only live smoke only")
    url = make_url(settings.DATABASE_URL)
    assert url.database == "buildplatform"
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            categories = {row.code: row for row in (await db.scalars(
                select(TechnologyCategory)
            )).all()}
            assert all(categories[code].content_status == "CONTENT_COMPLETE"
                       for code in (*FAMILIES, "FOUNDATIONS"))
            for code in NEW_CODES:
                technology = await public_technology(db, code)
                assert technology is not None and technology.status == "ACTIVE"
                article = await technology_article(db, technology)
                assert article["evidence"] and article["steps"]
            basement = await public_category(db, "BASEMENT_AND_SUBSTRUCTURE")
            assert basement is not None
            assert any(row["technology"].technology_code == "FND_STRIP_PRECAST_FBS_FL"
                       for row in basement["related_technologies"])
    finally:
        await engine.dispose()
