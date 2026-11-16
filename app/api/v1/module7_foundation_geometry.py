"""Owner-scoped M7 foundation geometry revisions."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.config import settings
from app.core.permission_guard import can, require_permission
from app.models.module2_technology import MODULE2_OWNER_CODE, Technology
from app.models.module7_geometry import DigitalHouseObject, FoundationGeometryRevision
from app.services.module7_foundation_geometry import read_foundation_geometry, save_foundation_geometry
from app.services.module7_foundation_inputs import FOUNDATION_FIELDS
from app.services.module7_strip_geometry import MODULE7_CODE, _technology, create_object

router = APIRouter(prefix="/admin/module7/foundations", tags=["module7-foundation-geometry"])
templates = Jinja2Templates(directory="templates")


class ObjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)


class GeometryWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    technology_id: uuid.UUID
    expected_version: StrictInt = Field(ge=0)
    user_values: dict[str, StrictStr | StrictInt | None] = Field(default_factory=dict, max_length=80)
    project_values: dict[str, StrictStr | StrictInt | None] = Field(default_factory=dict, max_length=80)
    allow_preliminary: StrictBool = False


class ObjectGeometryCreate(GeometryWrite):
    name: str = Field(min_length=1, max_length=255)


def _guard(user, action: str):
    if not settings.VERTICAL_CALCULATION_PREVIEW_ENABLED:
        raise HTTPException(status_code=404)
    require_permission(user, MODULE7_CODE, action)


@router.get("/view", response_class=HTMLResponse)
async def geometry_view(request: Request, db: DBSession, user: CurrentUser):
    _guard(user, "VIEW")
    require_permission(user, MODULE2_OWNER_CODE, "VIEW")
    statuses = ["ACTIVE", "DRAFT"] if can(user, MODULE2_OWNER_CODE, "EDIT") else ["ACTIVE"]
    technologies = (await db.scalars(select(Technology).where(
        Technology.technology_code.in_(FOUNDATION_FIELDS), Technology.status.in_(statuses)
    ).order_by(Technology.name))).all()
    return templates.TemplateResponse(request, "module7_foundation_geometry.html", {
        "technologies": technologies, "can_create": can(user, MODULE7_CODE, "CREATE"),
        "can_edit": can(user, MODULE7_CODE, "EDIT"),
        "atom_topbar_current_block": "Модуль №7: геометрия фундамента",
    })


@router.get("/objects")
async def list_objects(db: DBSession, user: CurrentUser):
    _guard(user, "VIEW")
    require_permission(user, MODULE2_OWNER_CODE, "VIEW")
    latest = (select(FoundationGeometryRevision.object_id,
                     func.max(FoundationGeometryRevision.version).label("version"))
              .group_by(FoundationGeometryRevision.object_id).subquery())
    statuses = ["ACTIVE", "DRAFT"] if can(user, MODULE2_OWNER_CODE, "EDIT") else ["ACTIVE"]
    rows = (await db.execute(select(DigitalHouseObject, FoundationGeometryRevision, Technology)
        .join(latest, latest.c.object_id == DigitalHouseObject.id)
        .join(FoundationGeometryRevision, (FoundationGeometryRevision.object_id == latest.c.object_id) &
              (FoundationGeometryRevision.version == latest.c.version))
        .join(Technology, Technology.id == FoundationGeometryRevision.technology_id)
        .where(DigitalHouseObject.owner_user_id == user.id, Technology.status.in_(statuses))
        .order_by(DigitalHouseObject.name))).all()
    return [{"object_id": str(obj.id), "name": obj.name, "revision_id": str(revision.id),
             "version": revision.version, "technology": technology.name} for obj, revision, technology in rows]


@router.post("/objects/with-geometry", status_code=201)
async def new_object_with_geometry(data: ObjectGeometryCreate, db: DBSession, user: CurrentUser):
    _guard(user, "CREATE")
    _guard(user, "EDIT")
    if data.expected_version != 0:
        raise HTTPException(status_code=422, detail="Для нового объекта требуется первая версия")
    try:
        item = await create_object(db, actor=user, name=data.name)
        revision = await save_foundation_geometry(db, actor=user, object_id=item.id,
            technology_id=data.technology_id, user_values=data.user_values, project_values=data.project_values,
            expected_version=0, allow_preliminary=data.allow_preliminary)
        result = {"id": str(revision.id), "object_id": str(item.id), "version": revision.version,
                  "technology_id": str(revision.technology_id), "inputs": revision.inputs}
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/technologies/{technology_id}/fields")
async def fields(technology_id: uuid.UUID, db: DBSession, user: CurrentUser):
    _guard(user, "VIEW")
    try:
        technology = await _technology(db, technology_id, user)
        specs = FOUNDATION_FIELDS.get(technology.technology_code)
        if specs is None:
            raise ValueError("unsupported foundation technology")
        uff_labels = {"geometry.net_area": "Площадь пола без фундаментной части",
                      "geometry.slab_thickness": "Толщина пола по грунту"}
        return {"technology_id": str(technology.id), "technology_code": technology.technology_code,
                "fields": [{"key": item.key, "label": uff_labels.get(item.key, item.label)
                            if technology.technology_code == "FND_UFF" else item.label, "unit": item.unit,
                            "required": item.required, "allow_zero": item.allow_zero} for item in specs]}
    except ValueError:
        raise HTTPException(status_code=404, detail="Технология недоступна") from None


@router.post("/objects", status_code=201)
async def new_object(data: ObjectCreate, db: DBSession, user: CurrentUser):
    _guard(user, "CREATE")
    try:
        item = await create_object(db, actor=user, name=data.name)
        result = {"id": str(item.id), "name": item.name}
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/objects/{object_id}/revisions", status_code=201)
async def new_revision(object_id: uuid.UUID, data: GeometryWrite, db: DBSession, user: CurrentUser):
    _guard(user, "EDIT")
    try:
        revision = await save_foundation_geometry(db, actor=user, object_id=object_id,
            technology_id=data.technology_id, user_values=data.user_values, project_values=data.project_values,
            expected_version=data.expected_version, allow_preliminary=data.allow_preliminary)
        result = {"id": str(revision.id), "object_id": str(revision.object_id), "version": revision.version,
                  "technology_id": str(revision.technology_id), "inputs": revision.inputs}
        await db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/revisions/{revision_id}")
async def get_revision(revision_id: uuid.UUID, db: DBSession, user: CurrentUser):
    _guard(user, "VIEW")
    try:
        revision = await read_foundation_geometry(db, actor=user, revision_id=revision_id)
        obj = await db.get(DigitalHouseObject, revision.object_id)
        return {"id": str(revision.id), "object_id": str(revision.object_id), "version": revision.version,
                "object_name": obj.name, "technology_id": str(revision.technology_id), "inputs": revision.inputs}
    except ValueError:
        raise HTTPException(status_code=404, detail="Геометрия недоступна") from None
