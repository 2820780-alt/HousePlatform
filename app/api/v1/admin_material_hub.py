from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.enums import SourceActionType, SourceStatus, SourceType, TaskStatus, UserRole
from app.models.material_document import MaterialDocument
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.source_task_log import SourceTaskLog
from app.models.source_task_result import SourceTaskResult
from app.schemas.common import PaginatedResponse
from app.schemas.material_hub import (
    SourceCreate,
    MaterialDocumentCreate,
    MaterialDocumentRead,
    SourceRead,
    SourceTaskCreate,
    SourceTaskLogRead,
    SourceTaskRead,
    SourceTaskResultRead,
    SourceUpdate,
)
from app.services.audit_service import log_event
from app.services.material_hub_first_wave import first_wave_yufo_source_create_payloads, is_first_wave_blocked_source
from app.services.module1_operational_widgets import (
    add_module1_widget_instance,
    build_module1_widget_instances,
    get_module1_widget_catalog,
    get_module1_widget_configuration_options,
    list_module1_widget_instances,
    remove_module1_widget_instance,
    reorder_module1_widget_instances,
    update_module1_widget_instance,
)
from app.services.source_profiles import attach_source_profile_snapshot
from app.services.source_task_runner import run_source_task

router = APIRouter(prefix="/admin/material-hub", tags=["admin-material-hub"])


class Module1WidgetCreateRequest(BaseModel):
    widgetCode: str
    placement: str = "MODULE_OVERVIEW"
    settings: dict[str, Any] = Field(default_factory=dict)
    activeRegionCode: str | None = None


class Module1WidgetUpdateRequest(BaseModel):
    placement: str | None = None
    settings: dict[str, Any] | None = None
    position: int | None = Field(default=None, ge=1)
    isVisible: bool | None = None


class Module1WidgetReorderRequest(BaseModel):
    instanceIds: list[str] = Field(default_factory=list)

class SourceTaskOverviewLaunchRequest(BaseModel):
    source_names: list[str] = Field(default_factory=list)
    all_sources: bool = False
    action_type: SourceActionType = SourceActionType.INITIAL_MATERIAL_SCAN
    settings: dict[str, Any] = Field(default_factory=dict)


class SourceTaskOverviewLaunchResponse(BaseModel):
    status: str
    launched: int
    failed: int
    redirect_url: str
    message: str


OVERVIEW_ALLOWED_SETTING_KEYS = {
    "scan_mode",
    "data_source_kind",
    "collection_object",
    "processing_scenario",
    "document_type_group",
    "write_mode",
    "source_category_label",
    "source_category_source",
    "category_url_contains",
    "max_pages",
    "max_documents",
}


def _check_admin(user):
    if user.role != UserRole.ADMIN:
        raise ForbiddenError()


@router.get("/sources", response_model=PaginatedResponse[SourceRead])
async def list_sources(
    db: DBSession,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    _check_admin(user)
    total_q = await db.execute(select(func.count(Source.id)))
    total = total_q.scalar()
    result = await db.execute(
        select(Source).order_by(Source.priority.asc(), Source.name.asc()).offset(offset).limit(limit)
    )
    return PaginatedResponse(items=result.scalars().all(), total=total, offset=offset, limit=limit)


@router.post("/sources", response_model=SourceRead, status_code=201)
async def create_source(data: SourceCreate, db: DBSession, user: CurrentUser):
    _check_admin(user)
    source = Source(**data.model_dump())
    db.add(source)
    await db.flush()
    await db.refresh(source)
    await log_event(db, "source_created", "Source", source.id, user.id)
    return source


@router.post("/sources/defaults", response_model=list[SourceRead], status_code=201)
async def create_default_sources(db: DBSession, user: CurrentUser):
    _check_admin(user)
    defaults = [
        SourceCreate(
            name="Бауцентр",
            source_type=SourceType.RETAIL,
            url="https://baucenter.ru/",
            priority=10,
        ),
        SourceCreate(
            name="Bonolit",
            source_type=SourceType.MANUFACTURER,
            url="https://bonolit.ru/",
            priority=20,
        ),
        SourceCreate(
            name="ТЕХНОНИКОЛЬ",
            source_type=SourceType.MANUFACTURER,
            url="https://www.tn.ru/",
            priority=30,
        ),
        *[SourceCreate(**payload) for payload in first_wave_yufo_source_create_payloads()],
    ]
    sources: list[Source] = []
    for source_data in defaults:
        existing_result = await db.execute(select(Source).where(Source.name == source_data.name))
        existing = existing_result.scalar_one_or_none()
        if existing:
            sources.append(existing)
            continue
        source = Source(**source_data.model_dump())
        db.add(source)
        await db.flush()
        await db.refresh(source)
        await log_event(db, "source_created", "Source", source.id, user.id, {"default": True})
        sources.append(source)
    return sources


@router.get("/sources/{source_id}", response_model=SourceRead)
async def get_source(source_id: UUID, db: DBSession, user: CurrentUser):
    _check_admin(user)
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise NotFoundError("Source not found")
    return source


@router.put("/sources/{source_id}", response_model=SourceRead)
async def update_source(source_id: UUID, data: SourceUpdate, db: DBSession, user: CurrentUser):
    _check_admin(user)
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise NotFoundError("Source not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.add(source)
    await db.flush()
    await db.refresh(source)
    await log_event(db, "source_updated", "Source", source.id, user.id)
    return source


@router.post("/sources/{source_id}/pause", response_model=SourceRead)
async def pause_source(source_id: UUID, db: DBSession, user: CurrentUser):
    return await _set_source_status(source_id, SourceStatus.PAUSED, db, user)


@router.post("/sources/{source_id}/enable", response_model=SourceRead)
async def enable_source(source_id: UUID, db: DBSession, user: CurrentUser):
    return await _set_source_status(source_id, SourceStatus.ACTIVE, db, user)


@router.post("/sources/{source_id}/disable", response_model=SourceRead)
async def disable_source(source_id: UUID, db: DBSession, user: CurrentUser):
    return await _set_source_status(source_id, SourceStatus.DISABLED, db, user)


async def _set_source_status(source_id: UUID, status: SourceStatus, db: DBSession, user) -> Source:
    _check_admin(user)
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise NotFoundError("Source not found")
    source.status = status
    db.add(source)
    await db.flush()
    await db.refresh(source)
    await log_event(db, "source_status_changed", "Source", source.id, user.id, {"status": status.value})
    return source


@router.post("/tasks", response_model=list[SourceTaskRead], status_code=201)
async def create_source_tasks(data: SourceTaskCreate, db: DBSession, user: CurrentUser):
    _check_admin(user)
    if data.all_sources:
        result = await db.execute(select(Source).where(Source.status == SourceStatus.ACTIVE))
        sources = list(result.scalars().all())
    else:
        source_ids = data.source_ids or []
        result = await db.execute(select(Source).where(Source.id.in_(source_ids))) if source_ids else None
        sources = list(result.scalars().all()) if result else []

    if not sources:
        raise ValidationError("Select at least one source or set all_sources=true")

    tasks: list[SourceTask] = []
    for source in sources:
        task = SourceTask(
            source_id=source.id,
            action_type=data.action_type,
            status=TaskStatus.PENDING,
            created_by=user.id,
            parameters=attach_source_profile_snapshot(source, data.action_type, data.parameters),
        )
        db.add(task)
        tasks.append(task)

    await db.flush()
    for task in tasks:
        await db.refresh(task)
        await log_event(db, "source_task_created", "SourceTask", task.id, user.id, {
            "source_id": str(task.source_id),
            "action_type": task.action_type.value,
        })
    return tasks


@router.post("/tasks/launch-overview", response_model=SourceTaskOverviewLaunchResponse, status_code=201)
async def launch_overview_source_tasks(data: SourceTaskOverviewLaunchRequest, db: DBSession, user: CurrentUser):
    _check_admin(user)
    sources = await _resolve_overview_launch_sources(db, data)
    if not sources:
        raise ValidationError("Select at least one available source")

    settings = _sanitize_overview_launch_settings(data.settings)
    launched = 0
    failed = 0
    for source in sources:
        task = SourceTask(
            source_id=source.id,
            action_type=data.action_type,
            status=TaskStatus.PENDING,
            created_by=user.id,
            parameters=attach_source_profile_snapshot(source, data.action_type, settings),
        )
        db.add(task)
        await db.flush()
        await db.refresh(task)
        await log_event(db, "source_task_created", "SourceTask", task.id, user.id, {
            "source_id": str(task.source_id),
            "action_type": task.action_type.value,
            "launch_surface": "module1_overview",
        })
        task = await run_source_task(db, task.id)
        await log_event(db, "source_task_run", "SourceTask", task.id, user.id, {
            "status": task.status.value,
            "action_type": task.action_type.value,
            "launch_surface": "module1_overview",
        })
        if task.status == TaskStatus.FAILED:
            failed += 1
        else:
            launched += 1

    status = "completed_with_warnings" if failed else "completed"
    return SourceTaskOverviewLaunchResponse(
        status=status,
        launched=launched,
        failed=failed,
        redirect_url="/api/v1/admin/material-hub/view/sources",
        message="?????? ???????" if launched else "?????? ?? ????????",
    )


@router.get("/tasks", response_model=PaginatedResponse[SourceTaskRead])
async def list_source_tasks(
    db: DBSession,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    _check_admin(user)
    total_q = await db.execute(select(func.count(SourceTask.id)))
    total = total_q.scalar()
    result = await db.execute(
        select(SourceTask).order_by(SourceTask.created_at.desc()).offset(offset).limit(limit)
    )
    return PaginatedResponse(items=result.scalars().all(), total=total, offset=offset, limit=limit)


@router.post("/tasks/{task_id}/run", response_model=SourceTaskRead)
async def run_task(task_id: UUID, db: DBSession, user: CurrentUser):
    _check_admin(user)
    task = await run_source_task(db, task_id)
    await log_event(db, "source_task_run", "SourceTask", task.id, user.id, {
        "status": task.status.value,
        "action_type": task.action_type.value,
    })
    return task


async def _resolve_overview_launch_sources(db: DBSession, data: SourceTaskOverviewLaunchRequest) -> list[Source]:
    if data.all_sources:
        result = await db.execute(select(Source).where(Source.status == SourceStatus.ACTIVE).order_by(Source.priority.asc(), Source.name.asc()))
    else:
        names = [name for name in data.source_names if isinstance(name, str) and name.strip()]
        result = await db.execute(select(Source).where(Source.name.in_(names)).where(Source.status == SourceStatus.ACTIVE).order_by(Source.priority.asc(), Source.name.asc())) if names else None
    sources = list(result.scalars().all()) if result else []
    return [source for source in sources if not is_first_wave_blocked_source(source)]


def _sanitize_overview_launch_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    source = settings if isinstance(settings, dict) else {}
    cleaned: dict[str, Any] = {}
    for key, value in source.items():
        if key not in OVERVIEW_ALLOWED_SETTING_KEYS:
            continue
        if key in {"max_pages", "max_documents"}:
            limit = 100 if key == "max_documents" else 150
            default = 10 if key == "max_documents" else 5
            cleaned[key] = min(max(_safe_int(value, default), 1), limit)
            continue
        if key == "category_url_contains":
            if isinstance(value, list):
                cleaned[key] = [str(item) for item in value if str(item).strip()][:20]
            elif isinstance(value, str) and value.strip():
                cleaned[key] = [value.strip()]
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[key] = value
    return cleaned


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@router.get("/widgets/catalog")
async def module1_widget_catalog(db: DBSession, user: CurrentUser):
    return {
        "items": get_module1_widget_catalog(user),
        "options": await get_module1_widget_configuration_options(db, user),
    }


@router.get("/widgets/instances")
async def module1_widget_instances(
    db: DBSession,
    user: CurrentUser,
    placement: str | None = None,
    includePayloads: bool = True,
):
    if placement and includePayloads:
        items = await build_module1_widget_instances(db, user, placement=placement)
    else:
        items = await list_module1_widget_instances(db, user, placement=placement)
    return {"items": items}


@router.post("/widgets/instances", status_code=201)
async def create_module1_widget_instance(
    data: Module1WidgetCreateRequest,
    db: DBSession,
    user: CurrentUser,
):
    item = await add_module1_widget_instance(
        db,
        user,
        widget_code=data.widgetCode,
        placement=data.placement,
        settings=data.settings,
        active_region_code=data.activeRegionCode,
    )
    return {"item": item}


@router.patch("/widgets/instances/{instance_id}")
async def edit_module1_widget_instance(
    instance_id: str,
    data: Module1WidgetUpdateRequest,
    db: DBSession,
    user: CurrentUser,
):
    item = await update_module1_widget_instance(
        db,
        user,
        instance_id,
        placement=data.placement,
        settings=data.settings,
        position=data.position,
        is_visible=data.isVisible,
    )
    return {"item": item}


@router.delete("/widgets/instances/{instance_id}", status_code=204)
async def delete_module1_widget_instance(
    instance_id: str,
    db: DBSession,
    user: CurrentUser,
):
    await remove_module1_widget_instance(db, user, instance_id)
    return None


@router.put("/widgets/instances-order")
async def reorder_module1_widgets(
    data: Module1WidgetReorderRequest,
    db: DBSession,
    user: CurrentUser,
):
    return {"items": await reorder_module1_widget_instances(db, user, data.instanceIds)}

@router.get("/tasks/{task_id}/logs", response_model=list[SourceTaskLogRead])
async def list_task_logs(task_id: UUID, db: DBSession, user: CurrentUser):
    _check_admin(user)
    result = await db.execute(
        select(SourceTaskLog).where(SourceTaskLog.task_id == task_id).order_by(SourceTaskLog.created_at.asc())
    )
    return result.scalars().all()


@router.get("/tasks/{task_id}/results", response_model=list[SourceTaskResultRead])
async def list_task_results(task_id: UUID, db: DBSession, user: CurrentUser):
    _check_admin(user)
    result = await db.execute(
        select(SourceTaskResult).where(SourceTaskResult.task_id == task_id).order_by(SourceTaskResult.created_at.asc())
    )
    return result.scalars().all()


@router.post("/documents", response_model=MaterialDocumentRead, status_code=201)
async def create_material_document(data: MaterialDocumentCreate, db: DBSession, user: CurrentUser):
    _check_admin(user)
    if not data.material_id and not data.manufacturer_id:
        raise ValidationError("material_id or manufacturer_id is required")
    document = MaterialDocument(**data.model_dump())
    db.add(document)
    await db.flush()
    await db.refresh(document)
    await log_event(db, "material_document_created", "MaterialDocument", document.id, user.id)
    return document
