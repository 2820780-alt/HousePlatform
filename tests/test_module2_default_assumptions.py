from __future__ import annotations

from contextlib import asynccontextmanager
import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import make_url

from app.api.deps import get_current_user
from app.api.v1.module2_workbench import router
from app.api.v1.module2_encyclopedia import router as encyclopedia_router
from app.config import settings
from app.core.exceptions import ForbiddenError
from app.database import Base, engine, get_db, init_db
from app.models.audit_event import AuditEvent
from app.models.enums import UserRole
from app.models.module2_technology import Technology, TechnologyDefaultAssumption, TechnologyMaterialRequirement
from app.models.user import User
from app.services.module2_default_assumptions import (
    DefaultAssumptionError, resolve_default_assumptions, revise_default_assumption,
)
from app.services.module2_technology_foundation import create_next_revision, read_technology


def _technology() -> Technology:
    technology = Technology(id=uuid4(), technology_code="TEST_DEFAULTS", revision=1, name="Тест")
    category_id = uuid4()
    requirement = TechnologyMaterialRequirement(
        id=uuid4(), code="CONCRETE", selector_kind="MATERIAL_CLASS",
        material_category_id=category_id,
    )
    technology.requirements.append(requirement)
    technology.default_assumptions.extend([
        TechnologyDefaultAssumption(
            id=uuid4(), assumption_code="DEPTH_MM", revision=1,
            parameter_code="DEPTH_MM", name_ru="Глубина", value_type="NUMBER", unit="мм",
            default_value={"value": 1200}, source_kind="PLATFORM_ASSUMPTION",
            applicability={"mode": "PRELIMINARY_ONLY"}, auto_fallback=True,
            warning_level="CRITICAL", warning_text="Предварительно",
            allowed_values_strategy="BOUNDED_NUMBER", allowed_values={"min": 100, "max": 10000},
            status="ACTIVE",
        ),
        TechnologyDefaultAssumption(
            id=uuid4(), assumption_code="MATERIAL_CONCRETE", revision=1,
            parameter_code="MATERIAL_CONCRETE", name_ru="Бетон", value_type="MATERIAL_CLASS",
            default_value={"value": str(category_id)}, source_kind="PLATFORM_ASSUMPTION",
            applicability={}, auto_fallback=True, warning_level="WARNING",
            allowed_values_strategy="M1_REQUIREMENT_CATEGORY",
            allowed_values={"category_ids": [str(category_id)]},
            material_requirement=requirement, status="ACTIVE",
        ),
    ])
    return technology


def test_priority_bounds_and_m1_material_scope() -> None:
    technology = _technology()
    fallback = {item["parameter_code"]: item for item in resolve_default_assumptions(technology)}
    assert fallback["DEPTH_MM"]["resolved_value"] == "1200"
    assert fallback["DEPTH_MM"]["source"] == "M2_DEFAULT"
    assert fallback["DEPTH_MM"]["assumption_revision"] == 1
    assert fallback["MATERIAL_CONCRETE"]["source_kind"] == "PLATFORM_ASSUMPTION"

    project = resolve_default_assumptions(technology, project_values={"DEPTH_MM": 1500})
    assert next(item for item in project if item["parameter_code"] == "DEPTH_MM")["source"] == "PROJECT_VALUE"
    override = resolve_default_assumptions(
        technology, project_values={"DEPTH_MM": 1500}, user_overrides={"DEPTH_MM": 1800}
    )
    assert next(item for item in override if item["parameter_code"] == "DEPTH_MM")["resolved_value"] == "1800"
    with pytest.raises(DefaultAssumptionError):
        resolve_default_assumptions(technology, user_overrides={"DEPTH_MM": 0})
    with pytest.raises(DefaultAssumptionError):
        resolve_default_assumptions(technology, user_overrides={"MATERIAL_CONCRETE": str(uuid4())})


@pytest.mark.asyncio(loop_scope="module")
async def test_clone_startup_does_not_call_create_all(monkeypatch) -> None:
    if make_url(settings.DATABASE_URL).database != "m2_a21_20261108_022108":
        pytest.skip("A2.1 startup test requires the isolated restored database")

    def forbidden_create_all(*_args, **_kwargs):
        raise AssertionError("startup must not call create_all")

    monkeypatch.setattr(Base.metadata, "create_all", forbidden_create_all)
    await init_db()


@pytest.mark.asyncio(loop_scope="module")
async def test_clone_schema_and_foundation_coverage() -> None:
    if make_url(settings.DATABASE_URL).database != "m2_a21_20261108_022108":
        pytest.skip("A2.1 coverage test requires the isolated restored database")
    async with engine.connect() as connection:
        columns = await connection.run_sync(lambda sync: {
            item["name"] for item in inspect(sync).get_columns("module2_technology_default_assumptions")
        })
        assert columns == set(TechnologyDefaultAssumption.__table__.columns.keys())
        count = await connection.scalar(select(func.count()).select_from(TechnologyDefaultAssumption))
        assert count == 90
    async with _clone_session() as session:
        technologies = (await session.scalars(select(Technology).where(
            Technology.status == "ACTIVE", Technology.technology_code.like("FND_%")
        ))).all()
        assert len(technologies) == 15
        for technology in technologies:
            loaded = await read_technology(session, technology.id)
            assert loaded is not None and loaded.default_assumptions
            assert all(item.source_kind == "PLATFORM_ASSUMPTION" for item in loaded.default_assumptions)
            assert all(item.warning_text for item in loaded.default_assumptions)
        source = await read_technology(session, next(
            item.id for item in technologies if item.technology_code == "FND_STRIP_MONOLITHIC_RC"
        ))
        revised = create_next_revision(source, actor_role_code="ADMIN")
        assert len(revised.default_assumptions) == len(source.default_assumptions)
        assert {item.id for item in revised.default_assumptions}.isdisjoint(
            {item.id for item in source.default_assumptions}
        )


@asynccontextmanager
async def _clone_session():
    clone_name = "m2_a21_20261108_022108"
    if make_url(settings.DATABASE_URL).database != clone_name:
        pytest.skip("A2.1 integration tests require the isolated restored database")
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


def _app(session: AsyncSession, user) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def db_override():
        yield session

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = lambda: user

    @app.exception_handler(ForbiddenError)
    async def forbidden(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    return app


@pytest.mark.asyncio(loop_scope="module")
async def test_revision_audit_and_admin_only_workbench() -> None:
    async with _clone_session() as session:
        user = User(id=uuid4(), email=f"a21-{uuid4().hex}@example.test", password_hash="test-only", role=UserRole.ADMIN)
        session.add(user)
        await session.flush()
        technology = await session.scalar(select(Technology).where(
            Technology.technology_code == "FND_STRIP_MONOLITHIC_RC", Technology.status == "ACTIVE"
        ))
        assert technology is not None
        loaded = await read_technology(session, technology.id)
        assert loaded is not None
        assert len(loaded.default_assumptions) >= 5
        view = _app(session, SimpleNamespace(id=user.id, role=UserRole.ADMIN))
        transport = httpx.ASGITransport(app=view)
        url = f"/api/v1/admin/module2/workbench/{technology.id}"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            page = await client.get(url)
            assert page.status_code == 200
            assert "Значения по умолчанию" in page.text
            assert "Глубина заложения" in page.text
            assert "Предположение платформы" in page.text
            result = await client.post(
                url + "/actions/save-default",
                data={"assumption_code": "FOUNDATION_DEPTH_MM", "value": "1300", "section": "defaults"},
                follow_redirects=False,
            )
            assert result.status_code == 303
            assert "section=defaults" in result.headers["location"]
        revised = await session.scalars(select(TechnologyDefaultAssumption).where(
            TechnologyDefaultAssumption.technology_id == technology.id,
            TechnologyDefaultAssumption.assumption_code == "FOUNDATION_DEPTH_MM",
        ))
        history = sorted(revised.all(), key=lambda item: item.revision)
        assert [(item.revision, item.status) for item in history] == [(1, "SUPERSEDED"), (2, "ACTIVE")]
        assert history[0].default_value["value"] == 1200
        assert history[1].default_value["value"] == "1300"
        assert history[1].source_kind == "PLATFORM_ASSUMPTION"
        assert await session.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.event_type == "MODULE2_DEFAULT_REVISED", AuditEvent.entity_id == history[1].id
        )) == 1
        viewer = _app(session, SimpleNamespace(id=uuid4(), role="ANALYST"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=viewer), base_url="http://test") as client:
            denied = await client.post(url + "/actions/save-default", data={
                "assumption_code": "FOUNDATION_DEPTH_MM", "value": "1400", "section": "defaults"
            })
            assert denied.status_code == 403


@pytest.mark.asyncio(loop_scope="module")
async def test_noop_does_not_create_revision() -> None:
    async with _clone_session() as session:
        user = await session.scalar(select(User).limit(1))
        technology = await session.scalar(select(Technology).where(
            Technology.technology_code == "FND_SLAB_MONOLITHIC_RC", Technology.status == "ACTIVE"
        ))
        assert user is not None and technology is not None
        loaded = await read_technology(session, technology.id)
        before = await session.scalar(select(func.count()).select_from(TechnologyDefaultAssumption).where(
            TechnologyDefaultAssumption.technology_id == technology.id,
            TechnologyDefaultAssumption.assumption_code == "SLAB_THICKNESS_MM",
        ))
        await revise_default_assumption(
            session, loaded, assumption_code="SLAB_THICKNESS_MM", value="250", actor_user_id=user.id
        )
        after = await session.scalar(select(func.count()).select_from(TechnologyDefaultAssumption).where(
            TechnologyDefaultAssumption.technology_id == technology.id,
            TechnologyDefaultAssumption.assumption_code == "SLAB_THICKNESS_MM",
        ))
        assert after == before


@pytest.mark.asyncio(loop_scope="module")
async def test_live_read_only_workbench_and_encyclopedia_smoke() -> None:
    if os.getenv("M2_A21_LIVE_SMOKE") != "1":
        pytest.skip("opt-in read-only live smoke")
    assert make_url(settings.DATABASE_URL).database == "buildplatform"
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            technology = await session.scalar(select(Technology).where(
                Technology.technology_code == "FND_STRIP_MONOLITHIC_RC", Technology.status == "ACTIVE"
            ))
            assert technology is not None
            app = _app(session, SimpleNamespace(id=uuid4(), role=UserRole.ADMIN))
            app.include_router(encyclopedia_router, prefix="/api/v1")
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                workbench = await client.get(f"/api/v1/admin/module2/workbench/{technology.id}")
                encyclopedia = await client.get(
                    "/api/v1/module2/encyclopedia/technologies/FND_STRIP_MONOLITHIC_RC"
                )
            assert workbench.status_code == 200
            assert "Значения по умолчанию" in workbench.text
            assert "Глубина заложения" in workbench.text
            assert "Предположение платформы" in workbench.text
            assert encyclopedia.status_code == 200
        finally:
            await session.close()
            await transaction.rollback()
