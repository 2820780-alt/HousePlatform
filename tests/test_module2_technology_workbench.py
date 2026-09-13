from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.module2_workbench import router
from app.core.exceptions import ForbiddenError
from app.database import engine, get_db
from app.models.enums import UserRole
from app.models.module2_technology import TechnologyEvidenceReference
from app.models.user import User
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
    upsert_consumption_norm,
    upsert_draft_layer,
    upsert_draft_requirement,
    upsert_draft_work_step,
    workbench_permissions,
)


ROOT = Path(__file__).resolve().parents[1]
ADMIN = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN)
VIEWER = SimpleNamespace(id=uuid4(), role="ANALYST")


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

        assert listing.status_code == 200
        assert "Тестовая технология" in listing.text
        assert detail.status_code == 200
        assert "Technology Workbench" in detail.text
        assert "Материалы и требования" in detail.text
        assert "Работы" in detail.text
        assert list_work_items()[0].work_name in detail.text
        assert "<pre" not in detail.text


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
async def test_viewer_can_open_but_cannot_create_or_edit() -> None:
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

        assert listing.status_code == 200
        assert detail.status_code == 200
        assert "update-general" not in detail.text
        assert create.status_code == 403
        assert workbench_permissions(VIEWER) == {
            "view": True,
            "edit": False,
            "approve": False,
            "admin": False,
        }


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

    for section in (
        "general", "validation", "layers", "materials", "works", "norms",
        "nodes", "compatibility", "rules", "evidence", "revisions",
    ):
        assert f'id="{section}"' in detail
    assert "Новая технология" in listing
    assert "application/json" not in detail
    assert "JSON.stringify" not in detail
    assert "Итого на дом" not in detail
    assert "data-quick-action-candidate" not in detail
    assert "transition-knowledge" in detail
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
