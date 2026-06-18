from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.enums import SourceStatus, TaskStatus, UserRole
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.source_task_log import SourceTaskLog
from app.models.source_task_result import SourceTaskResult
from app.schemas.common import PaginatedResponse
from app.schemas.material_hub import (
    SourceCreate,
    SourceRead,
    SourceTaskCreate,
    SourceTaskLogRead,
    SourceTaskRead,
    SourceTaskResultRead,
    SourceUpdate,
)
from app.services.audit_service import log_event

router = APIRouter(prefix="/admin/material-hub", tags=["admin-material-hub"])


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
        result = await db.execute(select(Source.id).where(Source.status == SourceStatus.ACTIVE))
        source_ids = list(result.scalars().all())
    else:
        source_ids = data.source_ids or []

    if not source_ids:
        raise ValidationError("Select at least one source or set all_sources=true")

    tasks: list[SourceTask] = []
    for source_id in source_ids:
        task = SourceTask(
            source_id=source_id,
            action_type=data.action_type,
            status=TaskStatus.PENDING,
            created_by=user.id,
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
