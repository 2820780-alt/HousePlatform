from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.module2_workbench import router
from app.api.v1.module2_encyclopedia import router as encyclopedia_router
from app.api.v1.user_module_quick_actions import router as quick_action_router
from app.core.exceptions import ForbiddenError
from app.database import engine, get_db
from app.models.enums import UserRole
from app.models.module2_technology import TechnologyEvidenceReference
from app.models.user import User
from app.models.user_module_quick_action import UserModuleQuickAction
from app.schemas.module2_knowledge import ConsumptionNormDraftInput, KnowledgeSelectorInput
from app.schemas.module2_technology import (
    MaterialRequirementSelector,
    TechnologyDraftInput,
    TechnologyLayerInput,
    TechnologyLifecycle,
    TechnologyMaterialRequirementInput,
    TechnologyWorkStepInput,
)
from app.services.module1_work_catalog import list_work_items
from app.services.module2_technology_foundation import (
    Module2TechnologyError,
    build_draft_technology,
    create_next_revision,
    persist_technology_draft,
    read_technology,
    transition_technology,
    update_draft_technology,
    validate_technology_activation,
)
from app.services.module2_workbench import (
    build_technology_detail_view,
    delete_draft_component,
    format_condition,
    format_consumption_norm,
    move_draft_ordered_item,
    upsert_consumption_norm,
    upsert_draft_layer,
    upsert_draft_requirement,
    upsert_draft_work_step,
    workbench_permissions,
)


ROOT = Path(__file__).resolve().parents[1]
ADMIN = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)
VIEWER = SimpleNamespace(id=uuid4(), role="ANALYST")
SUPPLIER = SimpleNamespace(id=ADMIN.id, role=UserRole.SUPPLIER)


def _draft(*, with_layer: bool = True, with_work: bool = False):
    requirement = TechnologyMaterialRequirementInput(
        code="PRIMARY_MATERIAL",
        selector_kind=MaterialRequirementSelector.ROLE,
        material_role_code="PRIMARY_LAYER",
    )
    layers = [
        TechnologyLayerInput(
            position=1,
            functional_role="PRIMARY",
            requirement_code="PRIMARY_MATERIAL",
            thickness_expression="project_thickness_mm",
        )
    ] if with_layer else []
    work_steps = []
    if with_work:
        work_steps.append(
            TechnologyWorkStepInput(
                position=1,
                work_code=list_work_items()[0].work_code,
                instructions="Выполнить по технологической карте.",
            )
        )
    return build_draft_technology(
        TechnologyDraftInput(
            technology_code=f"WORKBENCH_{uuid4().hex[:10].upper()}",
            name="Тестовая технология",
            description="Изолированный fixture Workbench.",
            system_code="TEST_SYSTEM",
            requirements=[requirement],
            layers=layers,
            work_steps=work_steps,
        ),
        actor_role_code="ADMIN",
        created_by_user_id=ADMIN.id,
    )


@asynccontextmanager
async def _session():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            session.add(
                User(
                    id=ADMIN.id,
                    email="module2-workbench-admin@example.test",
                    password_hash="test-only",
                    role=ADMIN.role,
                )
            )
            await session.flush()
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()
    await engine.dispose()


def _app(session: AsyncSession, user=ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(encyclopedia_router, prefix="/api/v1")
    app.include_router(quick_action_router, prefix="/api/v1")

    async def session_override():
        yield session

    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[get_current_user] = lambda: user

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    return app


@pytest.mark.asyncio(loop_scope="module")
async def test_technology_list_and_detail_open_without_http_500() -> None:
    async with _session() as session:
        technology = _draft(with_work=True)
        await persist_technology_draft(session, technology)
        await session.flush()
        app = _app(session)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            listing = await client.get("/api/v1/admin/module2/workbench")
            detail = await client.get(f"/api/v1/admin/module2/workbench/{technology.id}")
            materials = await client.get(f"/api/v1/admin/module2/workbench/{technology.id}?tab=materials")
            works = await client.get(f"/api/v1/admin/module2/workbench/{technology.id}?tab=works")

        assert listing.status_code == 200
        assert "Тестовая технология" in listing.text
        assert detail.status_code == 200
        assert "Технологии" in detail.text
        assert "Материалы и параметры" in materials.text
        assert "Работы" in detail.text
        assert list_work_items()[0].work_name in works.text
        assert "<pre" not in detail.text


@pytest.mark.asyncio(loop_scope="module")
async def test_structured_foundation_rule_is_named_and_not_offered_lossy_editor() -> None:
    from app.schemas.module2_knowledge import KnowledgeRuleDraftInput
    from app.services.module2_foundation_quantity_rules import describe_quantity_rule
    from app.services.module2_knowledge_foundation import create_knowledge_rule_draft

    async with _session() as session:
        technology = _draft()
        technology.technology_code = "FND_SLAB_USHP"
        technology.revision = 997701
        requirement = technology.requirements[0]
        requirement.code = "SLAB_CONCRETE"
        requirement.id = uuid4()
        payload = describe_quantity_rule("NET_AREA_VOLUME", role_code="SLAB_CONCRETE")
        rule = create_knowledge_rule_draft(
            technology,
            KnowledgeRuleDraftInput(rule_code=f"QA_{uuid4().hex.upper()}", scope_kind="MATERIAL_REQUIREMENT",
                                    scope_reference=str(requirement.id), outcome_type="INFORMATION",
                                    outcome_payload=payload, conditions=[{
                                        "source": "CONTEXT", "field": "thickness_m", "operator": "EXISTS",
                                    }]),
            actor_role_code="ADMIN",
        )
        await persist_technology_draft(session, technology)
        await session.flush()
        technology = await read_technology(session, technology.id)
        view = await build_technology_detail_view(session, technology)
        rendered_rule = next(item for item in view["rules"] if item["model"].id == rule.id)
        assert rendered_rule["display_text"] == "Объём по площади и толщине"
        assert rendered_rule["structured_role"] == "Бетон плиты"
        assert rendered_rule["structured_rule"] is True
        assert rendered_rule["structured_formula"] == "Площадь за вычетом проёмов × толщина."
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(session)), base_url="http://test") as client:
            response = await client.get(f"/api/v1/admin/module2/workbench/{technology.id}?tab=rules")
        assert response.status_code == 200
        assert "Объём по площади и толщине" in response.text
        assert "Предварительное правило" in response.text
        assert "Изменить инженерное правило" not in response.text
        assert rule.outcome_payload == payload


@pytest.mark.asyncio(loop_scope="module")
async def test_create_draft_and_general_edit_use_domain_services() -> None:
    async with _session() as session:
        app = _app(session)
        transport = httpx.ASGITransport(app=app)
        code = f"UI_CREATE_{uuid4().hex[:8].upper()}"
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            created = await client.post(
                "/api/v1/admin/module2/workbench/create",
                data={
                    "technology_code": code,
                    "name": "Новый черновик",
                    "system_code": "WALL",
                    "description": "Создан через Workbench.",
                },
            )
            assert created.status_code == 303
            technology_id = UUID(created.headers["location"].split("/")[-1].split("?")[0])
            edited = await client.post(
                f"/api/v1/admin/module2/workbench/{technology_id}/actions/update-general",
                data={"section": "general", "name": "Обновленный черновик", "system_code": "ROOF"},
            )

        assert edited.status_code == 303
        persisted = await read_technology(session, technology_id)
        assert persisted is not None
        assert persisted.name == "Обновленный черновик"
        assert persisted.status == "DRAFT"


@pytest.mark.asyncio(loop_scope="module")
async def test_viewer_cannot_open_admin_pages_or_create() -> None:
    async with _session() as session:
        technology = _draft()
        await persist_technology_draft(session, technology)
        app = _app(session, VIEWER)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            listing = await client.get("/api/v1/admin/module2/workbench")
            detail = await client.get(f"/api/v1/admin/module2/workbench/{technology.id}")
            create = await client.post(
                "/api/v1/admin/module2/workbench/create",
                data={"technology_code": "DENIED_CREATE", "name": "Запрещено"},
            )

        assert listing.status_code == 403
        assert detail.status_code == 403
        assert "update-general" not in detail.text
        assert create.status_code == 403
        assert workbench_permissions(VIEWER) == {
            "view": True,
            "edit": False,
            "approve": False,
            "admin": False,
        }


@pytest.mark.asyncio(loop_scope="module")
async def test_information_architecture_permissions_and_addressable_tabs() -> None:
    from app.models.module2_technology import MODULE2_OWNER_CODE, Technology
    from app.services.module2_content_catalog import create_category, transition_category

    async with _session() as session:
        suffix = uuid4().hex[:10].upper()
        category = await create_category(session, code=f"CAT_{suffix}", name="Раздел теста", parent_code=None)
        await transition_category(session, category, "ACTIVE")
        published = Technology(technology_code=f"TECH_{suffix}", revision=1,
                               name="Статья теста", category_id=category.id, status="ACTIVE")
        draft = _draft(with_work=True)
        session.add(published)
        await persist_technology_draft(session, draft)
        await session.flush()

        def granted(level):
            return SimpleNamespace(id=ADMIN.id, role=UserRole.SUPPLIER, moduleAccessRules=[{
                "moduleCode": MODULE2_OWNER_CODE, "accessLevel": level, "accessScope": "GLOBAL",
            }])

        viewer_app = _app(session, granted("VIEW"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=viewer_app), base_url="http://test") as client:
            for path in ("", f"/categories/{category.code}", f"/technologies/{published.technology_code}"):
                response = await client.get(f"/api/v1/module2/encyclopedia{path}")
                assert response.status_code == 200
                assert "Редактировать технологию" not in response.text
                assert "Рабочая область" not in response.text
                assert 'id="m2-encyclopedia-menu" hidden' in response.text
                assert 'id="m2-technologies-menu"' not in response.text
            entry = await client.get("/api/v1/module2/encyclopedia/entry")
            assert entry.headers["location"] == "/api/v1/module2/encyclopedia"
            for path in ("", "/categories", f"/{draft.id}", f"/by-code/{published.technology_code}"):
                assert (await client.get(f"/api/v1/admin/module2/workbench{path}")).status_code == 403
            assert (await client.post(f"/api/v1/admin/module2/workbench/{draft.id}/actions/update-general",
                                      data={"name": "Запрещено"})).status_code == 403

        tabs = {
            "general": ("general", "layers"), "construction": ("layers", "materials"),
            "materials": ("materials", "works"), "works": ("works", "layers"),
            "rules": ("rules", "evidence"), "sources": ("evidence", "rules"),
            "revisions": ("revisions", "general"),
        }
        for level in ("EDIT", "APPROVE", "ADMIN"):
            app = _app(session, granted(level))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                registry = await client.get("/api/v1/admin/module2/workbench")
                assert registry.status_code == 200
                assert 'href="/api/v1/module2/encyclopedia">Энциклопедия</a>' in registry.text
                assert 'id="m2-encyclopedia-menu" hidden' in registry.text
                assert 'id="m2-technologies-menu" hidden' in registry.text
                entry = await client.get("/api/v1/module2/encyclopedia/entry")
                assert entry.headers["location"] == "/api/v1/admin/module2/workbench"
                for tab, (visible, absent) in tabs.items():
                    detail = await client.get(f"/api/v1/admin/module2/workbench/{draft.id}?tab={tab}")
                    assert detail.status_code == 200
                    assert f'id="{visible}"' in detail.text
                    assert f'id="{absent}"' not in detail.text
                    assert f'href="?tab={tab}" class="active"' in detail.text
                invalid = await client.get(f"/api/v1/admin/module2/workbench/{draft.id}?tab=invalid")
                assert 'id="general"' in invalid.text and 'id="materials"' not in invalid.text
                if level == "EDIT":
                    edited = await client.post(f"/api/v1/admin/module2/workbench/{draft.id}/actions/update-general",
                                               data={"name": "Изменено редактором", "section": "general"})
                    assert edited.status_code == 303 and draft.name == "Изменено редактором"
                    reviewed = await client.post(f"/api/v1/admin/module2/workbench/{draft.id}/actions/transition",
                                                 data={"target": "REVIEW", "section": "general"})
                    assert reviewed.status_code == 303 and draft.status == "REVIEW"
                elif level == "APPROVE":
                    returned = await client.post(f"/api/v1/admin/module2/workbench/{draft.id}/actions/transition",
                                                 data={"target": "DRAFT", "section": "general"})
                    assert returned.status_code == 303 and draft.status == "DRAFT"
                else:
                    archived = await client.post(f"/api/v1/admin/module2/workbench/{published.id}/actions/transition",
                                                 data={"target": "ARCHIVED", "section": "general"})
                    assert archived.status_code == 303 and published.status == "ARCHIVED"

        denied = SimpleNamespace(id=ADMIN.id, role=UserRole.ADMIN, moduleAccessRules=[{
            "moduleCode": MODULE2_OWNER_CODE, "accessLevel": "NO_ACCESS", "accessScope": "NONE",
        }])
        for user in (denied, SimpleNamespace(id=ADMIN.id, role=UserRole.SUPPLIER)):
            app = _app(session, user)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                assert (await client.get("/api/v1/module2/encyclopedia")).status_code == 403
                assert (await client.get("/api/v1/admin/module2/workbench")).status_code == 403


@pytest.mark.asyncio(loop_scope="module")
async def test_m2_browser_login_and_real_csrf_with_explicit_edit(monkeypatch) -> None:
    import app.api.deps as deps
    import app.api.v1.module2_workbench as routes
    from app.core.browser_auth import browser_auth_redirect_middleware
    from app.core.exceptions import UnauthorizedError
    from app.models.enums import UserStatus
    from app.models.module2_technology import MODULE2_OWNER_CODE

    actor = SimpleNamespace(id=uuid4(), role=UserRole.SUPPLIER, status=UserStatus.ACTIVE,
                            moduleAccessRules=[{"moduleCode": MODULE2_OWNER_CODE,
                                                "accessLevel": "EDIT", "accessScope": "GLOBAL"}])
    result = SimpleNamespace(scalar_one_or_none=lambda: actor)
    database = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock())
    app = FastAPI()
    app.middleware("http")(browser_auth_redirect_middleware)
    app.include_router(router, prefix="/api/v1")
    app.include_router(encyclopedia_router, prefix="/api/v1")

    async def fake_db():
        yield database

    app.dependency_overrides[get_db] = fake_db
    app.add_exception_handler(ForbiddenError, lambda _request, exc: JSONResponse({"detail": str(exc)}, status_code=403))
    app.add_exception_handler(UnauthorizedError, lambda _request, exc: JSONResponse({"detail": str(exc)}, status_code=401))
    monkeypatch.setattr(deps, "decode_token", lambda _token: {"type": "access", "sub": str(actor.id)})
    monkeypatch.setattr(routes, "read_technology", AsyncMock(return_value=SimpleNamespace()))
    perform = AsyncMock(return_value="Сохранено")
    monkeypatch.setattr(routes, "_perform_action", perform)
    path = f"/api/v1/admin/module2/workbench/{uuid4()}/actions/update-general"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for url in ("/api/v1/module2/encyclopedia", "/api/v1/admin/module2/workbench"):
            anonymous = await client.get(url, headers={"Accept": "text/html"}, follow_redirects=False)
            assert anonymous.status_code == 303 and "/auth/login/view" in anonymous.headers["location"]
        client.cookies.set("atom_access_token", "test-token")
        client.cookies.set("atom_csrf_token", "csrf-value")
        assert (await client.post(path, data={"name": "Тест"})).status_code == 403
        allowed = await client.post(path, data={"name": "Тест"}, headers={"X-CSRF-Token": "csrf-value"})
        assert allowed.status_code == 303
        assert perform.await_count == 1 and perform.await_args.kwargs["role_code"] is actor


@pytest.mark.asyncio(loop_scope="module")
async def test_readiness_widget_uses_real_data_and_enforces_module_rbac() -> None:
    async with _session() as session:
        technology = _draft()
        await persist_technology_draft(session, technology)
        await session.flush()

        admin_app = _app(session)
        admin_transport = httpx.ASGITransport(app=admin_app)
        async with httpx.AsyncClient(transport=admin_transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/admin/module2/workbench/widgets/technology-readiness"
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["widgetCode"] == "MODULE_02_TECHNOLOGY_READINESS_WIDGET"
        assert payload["sourceModuleCode"] == "MODULE_02_KNOWLEDGE_BASE"
        assert payload["primaryValue"] >= 1
        assert next(item for item in payload["items"] if item["label"] == "DRAFT")["value"] >= 1

        supplier_app = _app(session, SUPPLIER)
        supplier_transport = httpx.ASGITransport(app=supplier_app)
        async with httpx.AsyncClient(transport=supplier_transport, base_url="http://test") as client:
            denied = await client.get(
                "/api/v1/admin/module2/workbench/widgets/technology-readiness"
            )
        assert denied.status_code == 403


@pytest.mark.asyncio(loop_scope="module")
async def test_module2_quick_action_is_user_owned_persisted_and_rechecked_on_run() -> None:
    async with _session() as session:
        technology = _draft()
        await persist_technology_draft(session, technology)
        await session.flush()
        before = await session.scalar(select(func.count()).select_from(UserModuleQuickAction))

        admin_app = _app(session)
        admin_transport = httpx.ASGITransport(app=admin_app)
        async with httpx.AsyncClient(transport=admin_transport, base_url="http://test") as client:
            listing = await client.get("/api/v1/admin/module2/workbench")
            detail = await client.get(f"/api/v1/admin/module2/workbench/{technology.id}")
            created = await client.post(
                "/api/v1/quick-actions/user-module",
                json={
                    "sourceModuleCode": "MODULE_02_KNOWLEDGE_BASE",
                    "featureCode": "TECHNOLOGY_CONSTRUCTION_GROUPS",
                    "actionKey": "EDIT",
                    "title": "Новая технология",
                    "route": "/api/v1/admin/module2/workbench?create=1",
                    "configSnapshot": {"permissionKey": "EDIT"},
                    "atomCardAccent": "green",
                },
            )
            assert created.status_code == 201
            action_id = created.json()["quickActionId"]
            pinned = await client.post(
                f"/api/v1/quick-actions/user-module/{action_id}/pin-atom-card"
                "?sourceModuleCode=MODULE_02_KNOWLEDGE_BASE",
                json={"atomCardAccent": "green"},
            )
            run = await client.post(
                f"/api/v1/quick-actions/user-module/{action_id}/run",
                json={
                    "sourceModuleCode": "MODULE_02_KNOWLEDGE_BASE",
                    "actionKey": "EDIT",
                },
            )

        assert before == 0
        assert "data-quick-action-module-bar=\"MODULE_02_KNOWLEDGE_BASE\"" in listing.text
        assert f"data-quick-action-route=\"/api/v1/admin/module2/workbench/{technology.id}\"" in listing.text
        assert "data-quick-action-title=\"Открыть реестр технологий\"" in detail.text
        assert pinned.status_code == 200
        assert pinned.json()["isPinnedToAtomCard"] is True
        assert pinned.json()["route"] == "/api/v1/admin/module2/workbench?create=1"
        assert run.status_code == 200
        assert run.json()["status"] == "OPEN_MODULE_HANDLER"
        assert run.json()["route"] == "/api/v1/admin/module2/workbench?create=1"

        persisted = await session.get(UserModuleQuickAction, UUID(action_id))
        assert persisted is not None
        assert persisted.user_id == ADMIN.id
        assert persisted.source_module_code == "MODULE_02_KNOWLEDGE_BASE"
        assert persisted.is_pinned_to_atom_card is True

        supplier_app = _app(session, SUPPLIER)
        supplier_transport = httpx.ASGITransport(app=supplier_app)
        async with httpx.AsyncClient(transport=supplier_transport, base_url="http://test") as client:
            denied = await client.post(
                f"/api/v1/quick-actions/user-module/{action_id}/run",
                json={
                    "sourceModuleCode": "MODULE_02_KNOWLEDGE_BASE",
                    "actionKey": "EDIT",
                },
            )
        assert denied.status_code == 403


def test_draft_structure_mutations_validate_order_and_m1_work_catalog() -> None:
    technology = _draft(with_layer=False)
    requirement = upsert_draft_requirement(
        technology,
        TechnologyMaterialRequirementInput(
            code="FINISH",
            selector_kind=MaterialRequirementSelector.TECHNICAL_CONSTRAINTS,
            technical_constraints={"frost_resistance": "F50"},
        ),
        actor_role_code="ADMIN",
    )
    layer = upsert_draft_layer(
        technology,
        TechnologyLayerInput(position=1, functional_role="FINISH", requirement_code="FINISH"),
        actor_role_code="ADMIN",
    )
    step = upsert_draft_work_step(
        technology,
        TechnologyWorkStepInput(position=1, work_code=list_work_items()[0].work_code),
        actor_role_code="ADMIN",
    )

    assert layer.material_requirement is requirement
    assert step.work_code == list_work_items()[0].work_code
    with pytest.raises(ValueError, match="позиция"):
        upsert_draft_layer(
            technology,
            TechnologyLayerInput(position=1, functional_role="DUPLICATE"),
            actor_role_code="ADMIN",
        )
    with pytest.raises(ValueError, match="каталоге работ M1"):
        upsert_draft_work_step(
            technology,
            TechnologyWorkStepInput(position=2, work_code="FREE_TEXT_WORK"),
            actor_role_code="ADMIN",
        )


@pytest.mark.asyncio
async def test_draft_work_steps_can_be_reordered_without_copying_m1_catalog_data() -> None:
    technology = _draft(with_layer=False)
    work_catalog = list_work_items()
    first = upsert_draft_work_step(
        technology,
        TechnologyWorkStepInput(position=1, work_code=work_catalog[0].work_code),
        actor_role_code="ADMIN",
    )
    second = upsert_draft_work_step(
        technology,
        TechnologyWorkStepInput(position=2, work_code=work_catalog[1].work_code),
        actor_role_code="ADMIN",
    )
    db = SimpleNamespace(flush=AsyncMock())

    await move_draft_ordered_item(
        db,
        technology,
        "work-step",
        second.id,
        "up",
        actor_role_code="ADMIN",
    )

    assert (second.position, first.position) == (1, 2)
    assert second.work_code == work_catalog[1].work_code
    assert not hasattr(second, "work_name")
    assert db.flush.await_count == 3


def test_consumption_norm_is_human_readable_and_not_an_object_total() -> None:
    technology = _draft()
    requirement = technology.requirements[0]
    norm = upsert_consumption_norm(
        technology,
        ConsumptionNormDraftInput(
            norm_code="ADHESIVE_RATE",
            scope_requirement_id=requirement.id,
            resource=KnowledgeSelectorInput(
                selector_kind="MATERIAL_REQUIREMENT",
                material_requirement_id=requirement.id,
            ),
            basis_quantity="1",
            basis_unit="m2",
            consumption_quantity="5",
            consumption_unit="kg",
        ),
        actor_role_code="ADMIN",
    )

    assert format_consumption_norm(norm) == "5 kg / 1 m2"
    assert not hasattr(norm, "object_total")
    assert not hasattr(norm, "estimate_total")


def test_structured_condition_renderer_uses_human_language() -> None:
    rendered = format_condition(
        {
            "source": "CONTEXT",
            "field": "temperature_c",
            "operator": "GTE",
            "value": -5,
            "required_for_activation": True,
        }
    )

    assert rendered == "Температура не ниже -5 °C"
    assert "GTE" not in rendered
    assert "{" not in rendered


def test_material_constraints_hide_unknown_keys_and_uuids() -> None:
    from app.services.module2_workbench import _material_constraints_display

    result = _material_constraints_display({"diameter_mm": 12, "unknown_internal_key": str(uuid4()),
                                            "steel_class": "А500С"})
    assert "Диаметр, мм: 12" in result and "Класс арматуры: А500С" in result
    assert "Другие условия требуют уточнения" in result
    assert "unknown" not in result and "{" not in result
    assert _material_constraints_display({"steel_class": str(uuid4())}) == "Другие условия требуют уточнения"


@pytest.mark.asyncio(loop_scope="module")
async def test_invalid_draft_shows_blocker_and_activation_stays_guarded() -> None:
    async with _session() as session:
        technology = _draft(with_layer=False)
        await persist_technology_draft(session, technology)
        transition_technology(technology, TechnologyLifecycle.REVIEW, actor_role_code="ADMIN")
        await session.flush()
        technology = await read_technology(session, technology.id)
        assert technology is not None
        context = await build_technology_detail_view(session, technology)

        assert "Не добавлен ни один слой." in context["activation_blockers"]
        with pytest.raises(Module2TechnologyError, match="requires at least one layer"):
            transition_technology(technology, TechnologyLifecycle.ACTIVE, actor_role_code="ADMIN")


def test_active_is_immutable_and_creates_separate_draft_revision() -> None:
    technology = _draft()
    transition_technology(technology, TechnologyLifecycle.REVIEW, actor_role_code="ADMIN")
    transition_technology(technology, TechnologyLifecycle.ACTIVE, actor_role_code="ADMIN")

    with pytest.raises(Module2TechnologyError, match="only a DRAFT"):
        update_draft_technology(technology, {"name": "Перезапись"}, actor_role_code="ADMIN")
    revision = create_next_revision(technology, actor_role_code="ADMIN")

    assert technology.status == "ACTIVE"
    assert revision.status == "DRAFT"
    assert revision.revision == technology.revision + 1
    assert revision.id != technology.id


@pytest.mark.asyncio(loop_scope="module")
async def test_broken_evidence_reference_is_presented_safely() -> None:
    async with _session() as session:
        technology = _draft()
        await persist_technology_draft(session, technology)
        technology = await read_technology(session, technology.id)
        assert technology is not None
        technology.evidence_references.append(
            TechnologyEvidenceReference(
                id=uuid4(),
                technology_id=technology.id,
                document_id=uuid4(),
                target_kind="TECHNOLOGY",
            )
        )
        with session.no_autoflush:
            context = await build_technology_detail_view(session, technology)

        assert context["evidence"][0]["title"] == "Источник M1 недоступен"
        assert context["evidence"][0]["verified"] is False
        assert context["warnings"] == ["Недоступных или неподтвержденных ссылок M1: 1."]


def test_draft_component_delete_respects_references() -> None:
    technology = _draft()
    requirement = technology.requirements[0]
    with pytest.raises(ValueError, match="используется слоем"):
        delete_draft_component(
            technology,
            "requirement",
            requirement.id,
            actor_role_code="ADMIN",
        )


def test_templates_cover_workbench_sections_without_raw_json_editor() -> None:
    detail = (ROOT / "templates" / "module2_technology_detail.html").read_text(encoding="utf-8")
    listing = (ROOT / "templates" / "module2_technology_workbench.html").read_text(encoding="utf-8")
    scripts = (ROOT / "templates" / "_module2_workbench_scripts.html").read_text(encoding="utf-8")

    for section in (
        "general", "validation", "layers", "materials", "works", "norms",
        "nodes", "compatibility", "rules", "evidence", "revisions",
    ):
        assert f'id="{section}"' in detail
    assert "Новая технология" in listing
    assert "application/json" not in detail
    assert "JSON.stringify" not in detail
    assert "Итого на дом" not in detail
    assert "data-quick-action-candidate" in detail
    assert "data-quick-action-candidate" in listing
    assert "_atom_quick_action_menu.html" in detail
    assert "_atom_quick_action_menu.html" in listing
    assert 'data-quick-action-key="EDIT"' in listing
    assert 'data-quick-action-key="EDIT"' in detail
    assert "data-quick-action-config-snapshot" in listing
    assert "new URLSearchParams(window.location.search)" in scripts
    quick_action_menu = (ROOT / "templates" / "_atom_quick_action_menu.html").read_text(encoding="utf-8")
    assert 'document.createElement(item.status === "ACTIVE" && (item.deepLink || item.route) ? "a" : "button")' in quick_action_menu
    assert "transition-knowledge" in detail
    assert "Готовность к активации" in detail
    assert '<select name="materials"' in listing
    assert '<select name="blockers"' in listing
    assert "<th>Материалы</th>" not in listing
    assert "<th>Редакция</th>" not in listing
    assert "<th>Действия</th>" not in listing
    assert detail.count("/actions/move") == 2
    assert 'name="component" value="work-step"' in detail
    assert 'data-m2-confirm="Удалить эту запись?"' in detail
    assert 'data-m2-confirm="Архивировать эту технологию?"' in detail
    assert "window.confirm" in scripts
    for editor_label in (
        "Изменить узел",
        "Изменить норму",
        "Изменить правило совместимости",
        "Изменить инженерное правило",
    ):
        assert editor_label in detail


def test_workbench_does_not_change_module1_or_create_module_specific_infra() -> None:
    source = (ROOT / "app" / "services" / "module2_workbench.py").read_text(encoding="utf-8")
    route_source = (ROOT / "app" / "api" / "v1" / "module2_workbench.py").read_text(encoding="utf-8")

    for forbidden in (
        "docker compose", "atom-module2", "ProviderWorkCostOffer", "SupplierPrice",
        "estimate_total", "procurement", "Material(", "MaterialDocument(",
    ):
        assert forbidden not in source + route_source
    assert "db.add(" not in route_source
    assert "db.delete(" not in route_source
    conflict_warning = 'warnings.append(f"Обнаружено конфликтующих правил: {conflict_count}.")'
    assert conflict_warning in source
    assert conflict_warning.replace("warnings", "activation_blockers") not in source


def test_public_activation_validation_is_shared_with_ui() -> None:
    technology = _draft(with_layer=False)
    technology.input_missing_fields = ["frost_resistance"]
    technology.input_blockers = ["missing_technical_fields"]

    assert validate_technology_activation(technology) == (
        "missing_m1_field:frost_resistance",
        "m1_blocker:missing_technical_fields",
        "missing_layer",
    )
