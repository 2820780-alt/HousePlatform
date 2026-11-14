"""Opt-in forms for an owner-scoped M7/M5 calculation preview."""
from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.config import settings
from app.core.permission_guard import require_permission
from app.models.material import Material
from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import MODULE2_OWNER_CODE, Technology
from app.models.module7_geometry import DigitalHouseObject, StripGeometryRevision
from app.services.module2_calculation_blocks import decode_definition
from app.services.module5_estimate_snapshots import create_estimate_preview, read_estimate_preview
from app.services.module5_calculation_preview import PROTECTED_GEOMETRY_INPUTS
from app.services.module7_strip_geometry import create_object, save_strip_geometry
from app.services.module2_workbench import workbench_permissions

router = APIRouter(prefix="/admin/vertical-preview", tags=["vertical-preview"])
templates = Jinja2Templates(directory="templates")


def _display_number(value):
    try:
        number = Decimal(str(value))
        return format(number.normalize(), "f").replace(".", ",") if number.is_finite() else "—"
    except (InvalidOperation, ValueError):
        return "—"


def _guard(user):
    if not settings.VERTICAL_CALCULATION_PREVIEW_ENABLED:
        raise HTTPException(status_code=404)
    require_permission(user, "MODULE_01_MATERIAL_HUB", "VIEW")
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    require_permission(user, "MODULE_07_DIGITAL_HOUSE", "EDIT")
    require_permission(user, "MODULE_05_ESTIMATE_ENGINE", "CREATE")


@router.get("/{technology_id}", response_class=HTMLResponse)
async def preview_page(technology_id: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    _guard(user)
    tech = await db.get(Technology, technology_id)
    if tech is None or tech.status not in {"ACTIVE", "DRAFT"}:
        raise HTTPException(status_code=404)
    rows = (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == technology_id).order_by(TechnologyCalculationBlock.position))).all()
    blocks = [(row, decode_definition(row.definition, block_id=str(row.id), name=row.name,
                                      material_id=str(row.material_id) if row.material_id else None,
                                      work_code=row.work_code)) for row in rows]
    snapshot, geometry, obj = None, None, None
    if request.query_params.get("snapshot"):
        try:
            snapshot = await read_estimate_preview(db, actor=user, snapshot_id=uuid.UUID(request.query_params["snapshot"]))
        except ValueError:
            raise HTTPException(status_code=404) from None
        geometry = await db.get(StripGeometryRevision, snapshot.geometry_revision_id)
        if geometry.technology_id != technology_id:
            raise HTTPException(status_code=404)
        obj = await db.get(DigitalHouseObject, geometry.object_id)
    names = {}
    if snapshot:
        for line in snapshot.payload["result"]["materials"]:
            identifier = line["binding"]["resource_id"]
            material = await db.get(Material, uuid.UUID(identifier)) if identifier else None
            names["MATERIAL:" + (identifier or "")] = material.canonical_name if material else "Материал не выбран"
        for line in snapshot.payload["result"]["works"]:
            identifier = line["binding"]["resource_id"]
            work = await db.get(WorkCatalogItem, identifier) if identifier else None
            names["WORK:" + (identifier or "")] = work.work_name if work else "Работа не выбрана"
    return templates.TemplateResponse(request, "vertical_calculation_preview.html", {
        "technology": tech, "blocks": blocks, "snapshot": snapshot, "geometry": geometry,
        "object": obj, "names": names, "error": request.query_params.get("error"), "number": _display_number,
        "provided_parameters": {(item["block_id"], item["input_key"]): item["value"]
                                for item in snapshot.payload.get("parameters", [])} if snapshot else {},
        "protected_geometry_inputs": PROTECTED_GEOMETRY_INPUTS,
        "permissions": workbench_permissions(user), "atom_topbar_current_block": "Модуль №2: предварительный расчёт",
    })


@router.post("/{technology_id}")
async def calculate(technology_id: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    _guard(user)
    form = await request.form()
    try:
        if form.get("object_id"):
            object_id = uuid.UUID(str(form["object_id"]))
            expected_version = int(str(form["version"]))
        else:
            obj = await create_object(db, actor=user, name=str(form.get("name") or ""))
            object_id, expected_version = obj.id, 0
        geometry = await save_strip_geometry(db, actor=user, object_id=object_id, technology_id=technology_id,
            length_m=str(form.get("length_m") or "").replace(",", "."),
            width_m=str(form.get("width_m") or "").replace(",", "."),
            height_m=str(form.get("height_m") or "").replace(",", "."), expected_version=expected_version)
        rows = (await db.scalars(select(TechnologyCalculationBlock).where(
            TechnologyCalculationBlock.technology_id == technology_id))).all()
        keys = {(str(row.id), kind): str(form.get(f"scope.{row.id}.{kind}") or "")
                for row in rows for kind in ("MATERIAL", "WORK")}
        parameters = {}
        for row in rows:
            graph = decode_definition(row.definition, block_id=str(row.id), name=row.name)
            for parameter in graph.parameters:
                if parameter.input_key in PROTECTED_GEOMETRY_INPUTS:
                    continue
                raw = str(form.get(f"parameter.{row.id}.{parameter.input_key}") or "").strip()
                if raw:
                    parameters[(str(row.id), parameter.input_key)] = raw
        snapshot = await create_estimate_preview(db, actor=user, geometry_revision_id=geometry.id,
            region=str(form.get("region") or ""), terms=str(form.get("terms") or ""), accounting_keys=keys,
            parameter_values=parameters)
        await db.commit()
        query = urlencode({"snapshot": str(snapshot.id)})
    except (KeyError, ValueError):
        await db.rollback()
        query = urlencode({"error": "Не удалось выполнить расчёт. Проверьте размеры, связи и условия."})
    return RedirectResponse(f"/api/v1/admin/vertical-preview/{technology_id}?{query}", status_code=303)
