from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.module2_encyclopedia import router
from app.api.v1.module2_workbench import router as workbench_router
from app.core.exceptions import ForbiddenError
from app.database import engine, get_db
from app.models.enums import UserRole
from app.models.module2_technology import (
    Technology, TechnologyMaterialRequirement, TechnologyNode, TechnologyWorkStep,
)
from app.services.module1_work_catalog import list_work_items
from app.services.module2_content_catalog import (
    ContentCatalogError,
    category_tree,
    create_category,
    list_categories,
    start_content_package,
    transition_category,
    update_draft_category,
)


@asynccontextmanager
async def _session():
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            session = AsyncSession(bind=connection, expire_on_commit=False)
            try:
                yield session
            finally:
                await session.close()
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()


def _app(session: AsyncSession, role=UserRole.ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(workbench_router, prefix="/api/v1")

    async def session_override():
        yield session

    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4(), role=role)

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    return app


@pytest.mark.asyncio(loop_scope="module")
async def test_category_hierarchy_and_lifecycle_are_controlled():
    async with _session() as session:
        suffix = uuid4().hex[:10].upper()
        parent = await create_category(
            session, code=f"ROOT_{suffix}", name="Parent", parent_code=None
        )
        child = await create_category(
            session, code=f"CHILD_{suffix}", name="Child", parent_code=parent.code,
            sort_order=2,
        )
        fixture_ids = {parent.id, child.id}
        assert not any(
            row["category"].id in fixture_ids
            for row in category_tree(await list_categories(session), public=True)
        )
        with pytest.raises(ContentCatalogError, match="parent category"):
            await transition_category(session, child, "ACTIVE")
        with pytest.raises(ContentCatalogError, match="cycle"):
            await update_draft_category(
                session, parent, name="Parent", parent_code=child.code,
                sort_order=0, scope_code="RESIDENTIAL",
            )
        await transition_category(session, parent, "ACTIVE")
        await transition_category(session, child, "ACTIVE")
        await start_content_package(session, child)
        assert child.content_status == "IN_PROGRESS"
        assert [
            row["depth"] for row in category_tree(await list_categories(session), public=True)
            if row["category"].id in fixture_ids
        ] == [0, 1]
        with pytest.raises(ContentCatalogError, match="children"):
            await transition_category(session, parent, "ARCHIVED")


@pytest.mark.asyncio(loop_scope="module")
async def test_encyclopedia_is_empty_until_content_is_approved():
    async with _session() as session:
        suffix = uuid4().hex[:10].upper()
        draft = await create_category(
            session, code=f"DRAFT_{suffix}", name="Draft category", parent_code=None
        )
        technology = Technology(
            technology_code=f"DRAFT_TECH_{suffix}", revision=1,
            name="Draft technology", category_id=draft.id, status="DRAFT",
        )
        session.add(technology)
        await session.flush()
        transport = httpx.ASGITransport(app=_app(session))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            index = await client.get("/api/v1/module2/encyclopedia")
            category = await client.get(f"/api/v1/module2/encyclopedia/categories/{draft.code}")
            detail = await client.get(
                f"/api/v1/module2/encyclopedia/technologies/{technology.technology_code}"
            )
        assert index.status_code == 200
        assert "Draft category" not in index.text
        assert "Draft technology" not in index.text
        assert category.status_code == 404
        assert detail.status_code == 404


@pytest.mark.asyncio(loop_scope="module")
async def test_category_workbench_renders_with_existing_taxonomy():
    async with _session() as session:
        transport = httpx.ASGITransport(app=_app(session))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/module2/workbench/categories")
        assert response.status_code == 200
        assert "module2/workbench/categories/create" in response.text


@pytest.mark.asyncio(loop_scope="module")
async def test_published_technology_uses_stable_codes_and_m1_work_reference():
    async with _session() as session:
        suffix = uuid4().hex[:10].upper()
        category = await create_category(
            session, code=f"CAT_{suffix}", name="Assembly category", parent_code=None
        )
        await transition_category(session, category, "ACTIVE")
        work = list_work_items()[0]
        technology = Technology(
            technology_code=f"TECH_{suffix}", revision=1,
            name="Published assembly", category_id=category.id, status="ACTIVE",
        )
        technology.work_steps.append(TechnologyWorkStep(position=1, work_code=work.work_code))
        technology.requirements.append(
            TechnologyMaterialRequirement(
                code="PRIMARY", selector_kind="ROLE", material_role_code="FINISH",
            )
        )
        technology.nodes.append(TechnologyNode(code="EDGE", node_type="DETAIL", name="Edge node"))
        session.add(technology)
        await session.flush()
        transport = httpx.ASGITransport(app=_app(session))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            index = await client.get("/api/v1/module2/encyclopedia", params={"q": "Published"})
            category_page = await client.get(
                f"/api/v1/module2/encyclopedia/categories/{category.code}"
            )
            detail = await client.get(
                f"/api/v1/module2/encyclopedia/technologies/{technology.technology_code}"
            )
            work_page = await client.get(f"/api/v1/module2/encyclopedia/works/{work.work_code}")
            material_page = await client.get(
                f"/api/v1/module2/encyclopedia/technologies/{technology.technology_code}/materials/PRIMARY"
            )
            node_page = await client.get(
                f"/api/v1/module2/encyclopedia/technologies/{technology.technology_code}/nodes/EDGE"
            )
        assert all(response.status_code == 200 for response in (
            index, category_page, detail, work_page, material_page, node_page,
        ))
        assert technology.technology_code in index.text
        assert "Published assembly" in category_page.text
        assert work.work_name in detail.text
        assert technology.technology_code in work_page.text
        assert "FINISH" in material_page.text
        assert "Edge node" in node_page.text
        assert str(technology.id) not in detail.text
        assert "<pre" not in detail.text


@pytest.mark.asyncio(loop_scope="module")
async def test_supplier_cannot_read_encyclopedia_without_module2_view():
    async with _session() as session:
        transport = httpx.ASGITransport(app=_app(session, UserRole.SUPPLIER))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/module2/encyclopedia")
        assert response.status_code == 403
