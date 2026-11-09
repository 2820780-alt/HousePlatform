from __future__ import annotations

import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.module1_material_card import router as material_router
from app.api.v1.module2_encyclopedia import router as encyclopedia_router
from app.api.v1.module2_workbench import router as workbench_router
from app.core.exceptions import ForbiddenError
from app.database import Base, engine, get_db, init_db
from app.models.enums import MaterialStatus, TaskStatus, UserRole
from app.models.material import Material
from app.models.material_attribute import MaterialAttribute
from app.models.material_category import MaterialCategory
from app.models.module2_knowledge import CompatibilityRule
from app.models.module2_material_gap import Module2MaterialGap
from app.models.module2_technology import Technology, TechnologyMaterialRequirement
from app.models.source_task import SourceTask
from app.schemas.module2_knowledge import KnowledgeSelectorInput, KnowledgeSelectorKind
from app.services.module2_material_resolution import (
    MaterialResolutionError, change_gap_query, compatible_materials, ensure_gap,
    material_card_url, request_m1_search, resolve_existing,
)


@asynccontextmanager
async def _session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()
    await engine.dispose()


def _app(session: AsyncSession, role: UserRole = UserRole.ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(material_router, prefix="/api/v1")
    app.include_router(encyclopedia_router, prefix="/api/v1")
    app.include_router(workbench_router, prefix="/api/v1")

    async def session_override():
        yield session

    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=None, role=role)

    @app.exception_handler(ForbiddenError)
    async def denied(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    return app


@pytest.mark.asyncio(loop_scope="module")
async def test_verified_material_identity_and_scoped_candidates():
    async with _session() as db:
        suffix = uuid4().hex
        concrete = MaterialCategory(name="Бетон", slug=f"a22-concrete-{suffix}", status="ACTIVE")
        doors = MaterialCategory(name="Двери", slug=f"a22-doors-{suffix}", status="ACTIVE")
        db.add_all((concrete, doors))
        await db.flush()
        good = Material(canonical_name="Бетон B22,5", category_id=concrete.id,
                        status=MaterialStatus.VERIFIED)
        weaker = Material(canonical_name="Бетон B15", category_id=concrete.id,
                          status=MaterialStatus.VERIFIED)
        door = Material(canonical_name="Дверь", category_id=doors.id,
                        status=MaterialStatus.VERIFIED)
        good.attributes.append(MaterialAttribute(attribute_name="strength_class", attribute_value="B22.5"))
        weaker.attributes.append(MaterialAttribute(attribute_name="strength_class", attribute_value="B15"))
        db.add_all((good, weaker, door))
        first = Technology(technology_code=f"A22_1_{suffix}", revision=1, name="Лента", status="ACTIVE")
        second = Technology(technology_code=f"A22_2_{suffix}", revision=1, name="Плита", status="ACTIVE")
        for technology in (first, second):
            technology.requirements.append(TechnologyMaterialRequirement(
                code="CONCRETE", selector_kind="MATERIAL_CLASS",
                material_category_id=concrete.id, technical_constraints={"strength_class": "B22.5"},
            ))
        db.add_all((first, second))
        await db.flush()
        first_results = await compatible_materials(db, first.requirements[0])
        second_results = await compatible_materials(db, second.requirements[0])
        assert [item.id for item in first_results] == [good.id]
        assert [item.id for item in second_results] == [good.id]
        assert material_card_url(good.id).endswith(str(good.id))

        candidate_selector = KnowledgeSelectorInput(
            selector_kind=KnowledgeSelectorKind.CANONICAL_MATERIAL, canonical_material_id=good.id,
        )
        requirement_selector = KnowledgeSelectorInput(
            selector_kind=KnowledgeSelectorKind.MATERIAL_REQUIREMENT,
            material_requirement_id=first.requirements[0].id,
        )
        db.add(CompatibilityRule(
            technology_id=first.id, rule_code="NO_CONCRETE", revision=1,
            subject_kind="CANONICAL_MATERIAL",
            subject_selector=candidate_selector.model_dump(mode="json", exclude_none=True),
            object_kind="MATERIAL_REQUIREMENT",
            object_selector=requirement_selector.model_dump(mode="json", exclude_none=True),
            relation="INCOMPATIBLE", conditions=[], status="ACTIVE",
        ))
        await db.flush()
        assert await compatible_materials(db, first.requirements[0]) == ()
        assert [item.id for item in await compatible_materials(db, second.requirements[0])] == [good.id]

        transport = httpx.ASGITransport(app=_app(db))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            card = await client.get(material_card_url(good.id))
        assert card.status_code == 200
        assert "Бетон B22,5" in card.text
        assert "Карточка материала" in card.text


@pytest.mark.asyncio(loop_scope="module")
async def test_material_gap_to_m1_task_and_new_canonical_material():
    async with _session() as db:
        suffix = uuid4().hex
        category = MaterialCategory(name="Мембрана", slug=f"a22-membrane-{suffix}", status="ACTIVE")
        technology = Technology(technology_code=f"A22_GAP_{suffix}", revision=1,
                                name="Гидроизоляция", status="ACTIVE")
        requirement = TechnologyMaterialRequirement(code="MEMBRANE", selector_kind="MATERIAL_CLASS",
                                                    material_category_id=None)
        technology.requirements.append(requirement)
        db.add_all((category, technology))
        await db.flush()
        requirement.material_category_id = category.id
        gap = await ensure_gap(db, technology, requirement, search_phrase="Мембрана")
        assert gap.status == "OPEN"
        assert gap.evidence_context["evidence_reference_ids"] == []
        task = await db.get(SourceTask, gap.source_task_id)
        assert task.status == TaskStatus.NEEDS_REVIEW
        assert task.parameters["origin"] == "M2_MATERIAL_GAP"
        assert task.parameters["evidence_reference_ids"] == []

        await change_gap_query(db, gap, "Мембрана для подземной части", None)
        assert gap.status == "REVIEWING"
        assert (await db.get(SourceTask, gap.source_task_id)).parameters["search_phrase"] == gap.search_phrase
        await request_m1_search(db, gap, None)
        assert gap.status == "SEARCH_REQUESTED"
        assert (await db.get(SourceTask, gap.source_task_id)).parameters["search_requested"] is True

        material = Material(canonical_name="Мембрана M1", category_id=category.id,
                            status=MaterialStatus.VERIFIED)
        db.add(material)
        await db.flush()
        await resolve_existing(db, gap, requirement, material.id, None)
        assert gap.status == "RESOLVED_NEW_MATERIAL"
        assert gap.resolved_material_id == material.id
        with pytest.raises(MaterialResolutionError):
            await change_gap_query(db, gap, "Изменить снова", None)


@pytest.mark.asyncio(loop_scope="module")
async def test_customer_cannot_edit_material_gap():
    async with _session() as db:
        transport = httpx.ASGITransport(app=_app(db, UserRole.CUSTOMER))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/module2/workbench/{uuid4()}/material-gaps/{uuid4()}/query",
                data={"search_phrase": "Бетон"},
            )
        assert response.status_code == 403


@pytest.mark.asyncio(loop_scope="module")
async def test_admin_gap_forms_update_m1_task_and_resolve_to_canonical_id():
    async with _session() as db:
        suffix = uuid4().hex
        category = MaterialCategory(name="Арматура", slug=f"a22-rebar-{suffix}", status="ACTIVE")
        technology = Technology(technology_code=f"A22_ADMIN_{suffix}", revision=1,
                                name="Тест армирования", status="ACTIVE")
        requirement = TechnologyMaterialRequirement(
            code="REBAR", selector_kind="MATERIAL_CLASS", material_category_id=None,
        )
        technology.requirements.append(requirement)
        db.add_all((category, technology))
        await db.flush()
        requirement.material_category_id = category.id
        gap = await ensure_gap(db, technology, requirement, search_phrase="Арматура")
        base = f"/api/v1/admin/module2/workbench/{technology.id}/material-gaps/{requirement.id}"
        transport = httpx.ASGITransport(app=_app(db))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            changed = await client.post(f"{base}/query", data={"search_phrase": "Арматура A500C"})
            assert changed.status_code == 303
            assert "notice=" in changed.headers["location"], changed.headers["location"]
            assert gap.search_phrase == "Арматура A500C"
            requested = await client.post(f"{base}/search")
            assert requested.status_code == 303
            assert "notice=" in requested.headers["location"], requested.headers["location"]
            assert gap.status == "SEARCH_REQUESTED"
            material = Material(canonical_name="Арматура A500C M1", category_id=category.id,
                                status=MaterialStatus.VERIFIED)
            db.add(material)
            await db.flush()
            resolved = await client.post(f"{base}/resolve", data={"material_id": str(material.id)})
            assert resolved.status_code == 303
            assert gap.resolved_material_id == material.id


@pytest.mark.asyncio(loop_scope="module")
async def test_gap_migration_matches_orm_and_startup_does_not_create_tables(monkeypatch):
    async with engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync: {item["name"] for item in inspect(sync).get_columns("module2_material_gaps")}
        )
    assert columns == set(Module2MaterialGap.__table__.columns.keys())

    def forbidden_create_all(*_args, **_kwargs):
        raise AssertionError("normal startup must not create tables")

    monkeypatch.setattr(Base.metadata, "create_all", forbidden_create_all)
    await init_db()
    await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_live_houseplatform_a22_pages_read_only():
    if os.getenv("M2_A22_LIVE_SMOKE") != "1":
        pytest.skip("run explicitly against the migrated live HousePlatform DB")
    async with _session() as db:
        material = await db.scalar(select(Material).where(Material.status == MaterialStatus.VERIFIED))
        assert material is not None
        technology_codes = (await db.scalars(
            select(Technology.technology_code)
            .where(Technology.status == "ACTIVE", Technology.technology_code.like("FND_%"))
        )).all()
        assert len(technology_codes) == 15
        transport = httpx.ASGITransport(app=_app(db))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            index = await client.get("/api/v1/module2/encyclopedia")
            assert index.status_code == 200
            for code in technology_codes:
                page = await client.get(f"/api/v1/module2/encyclopedia/technologies/{code}")
                assert page.status_code == 200
                assert "Предварительные допущения" in page.text
                assert "Материалы" in page.text
                assert "Порядок работ" in page.text
                assert "Источники и нормативная база" in page.text
            workbench = await client.get("/api/v1/admin/module2/workbench")
            assert workbench.status_code == 200
            assert "Паспорт модуля" not in workbench.text
            redirect = await client.get(
                "/api/v1/admin/module2/workbench/by-code/FND_STRIP_MONOLITHIC_RC",
                follow_redirects=False,
            )
            detail = await client.get(f'{redirect.headers["location"]}?tab=materials')
            assert detail.status_code == 200
            assert "Материал не найден в M1" in detail.text
            assert "Отправить в поиск M1" in detail.text
            card = await client.get(material_card_url(material.id))
            assert card.status_code == 200
            assert material.canonical_name in card.text
