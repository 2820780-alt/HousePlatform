"""Opt-in forms for an owner-scoped M7/M5 calculation preview."""
from __future__ import annotations

import uuid
import hashlib
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text

from app.api.deps import CurrentUser, DBSession
from app.config import settings
from app.core.permission_guard import require_permission
from app.models.material import Material
from app.models.module1_work_item import WorkCatalogItem
from app.models.module5_estimate_snapshot import EstimatePreviewSnapshot
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import MODULE2_OWNER_CODE, Technology
from app.models.module7_geometry import DigitalHouseObject, StripGeometryRevision
from app.services.module2_calculation_blocks import decode_definition
from app.services.module2_fnd3_work_policy import FOUNDATION_BUNDLED_WORK
from app.services.module5_estimate_snapshots import (FOUNDATION_INPUT_ALIASES, create_estimate_preview,
                                                      read_estimate_preview)
from app.services.module5_calculation_preview import PROTECTED_GEOMETRY_INPUTS
from app.services.module7_foundation_geometry import read_foundation_geometry
from app.services.module7_foundation_inputs import FOUNDATION_FIELDS
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


@router.get("/foundation/{revision_id}", response_class=HTMLResponse)
async def foundation_preview_page(revision_id: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    _guard(user)
    try:
        geometry = await read_foundation_geometry(db, actor=user, revision_id=revision_id)
        snapshot = None
        if request.query_params.get("snapshot"):
            snapshot = await read_estimate_preview(db, actor=user, snapshot_id=uuid.UUID(request.query_params["snapshot"]))
            if snapshot.foundation_geometry_revision_id != geometry.id:
                raise ValueError("snapshot geometry mismatch")
    except ValueError:
        raise HTTPException(status_code=404) from None
    technology = await db.get(Technology, geometry.technology_id)
    rows = (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == technology.id).order_by(TechnologyCalculationBlock.position))).all()
    blocks = [(row, decode_definition(row.definition, block_id=str(row.id), name=row.name,
                                      material_id=str(row.material_id) if row.material_id else None,
                                      work_code=row.work_code)) for row in rows]
    work_choices = []
    if technology.technology_code in FOUNDATION_BUNDLED_WORK:
        codes = {row.work_code for row, block in blocks if row.work_code and block.work_output_id}
        work_names = {item.work_code: item.work_name for item in (await db.scalars(
            select(WorkCatalogItem).where(WorkCatalogItem.work_code.in_(codes)))).all()}
        work_choices = [(str(row.id), block.name, work_names.get(row.work_code, "Работа не выбрана"))
                        for row, block in blocks if block.work_output_id]
    selected_work = snapshot.payload.get("selected_work_block_ids") if snapshot else None
    protected = set(PROTECTED_GEOMETRY_INPUTS) | {item.key for item in FOUNDATION_FIELDS[technology.technology_code]}
    protected.update(target for source, target in FOUNDATION_INPUT_ALIASES.items() if source in protected)
    names = {}
    if snapshot:
        captured = snapshot.payload.get("resource_names", {})
        for line in snapshot.payload["result"]["materials"]:
            identifier = line["binding"]["resource_id"]
            key = "MATERIAL:" + (identifier or "")
            material = await db.get(Material, uuid.UUID(identifier)) if identifier and key not in captured else None
            names[key] = captured.get(key, material.canonical_name if material else "Материал не выбран")
        for line in snapshot.payload["result"]["works"]:
            identifier = line["binding"]["resource_id"]
            key = "WORK:" + (identifier or "")
            work = await db.get(WorkCatalogItem, identifier) if identifier and key not in captured else None
            names[key] = captured.get(key, work.work_name if work else "Работа не выбрана")
    return templates.TemplateResponse(request, "vertical_foundation_preview.html", {
        "technology": technology, "geometry": geometry, "fields": FOUNDATION_FIELDS[technology.technology_code],
        "blocks": blocks, "protected": protected, "snapshot": snapshot, "names": names,
        "work_choices": work_choices, "selected_work": selected_work,
        "error": request.query_params.get("error"), "number": _display_number,
        "provided_parameters": {(item["block_id"], item["input_key"]): item["value"]
                                for item in snapshot.payload.get("parameters", [])} if snapshot else {},
        "idempotency_key": str(uuid.uuid4()), "permissions": workbench_permissions(user),
        "atom_topbar_current_block": "Модуль №5: предварительная смета",
    })


@router.post("/foundation/{revision_id}")
async def calculate_foundation(revision_id: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    _guard(user)
    form = await request.form()
    try:
        geometry = await read_foundation_geometry(db, actor=user, revision_id=revision_id)
        technology = await db.get(Technology, geometry.technology_id)
        raw_key = str(form.get("idempotency_key") or "")
        request_key = str(uuid.UUID(raw_key)) if raw_key else None
        fingerprint = None
        if request_key:
            if db.bind.dialect.name != "postgresql":
                raise ValueError("idempotent requests require PostgreSQL transaction locking")
            payload = sorted((str(key), str(value)) for key, value in form.multi_items()
                             if key not in {"idempotency_key", "csrf_token"})
            fingerprint = hashlib.sha256(json.dumps([str(revision_id), payload], ensure_ascii=True,
                                                    separators=(",", ":")).encode()).hexdigest()
            await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                             {"key": f"atom.m5.preview:{user.id}:{request_key}"})
            existing = await db.scalar(select(EstimatePreviewSnapshot).where(
                EstimatePreviewSnapshot.owner_user_id == user.id,
                EstimatePreviewSnapshot.payload["idempotency_key"].as_string() == request_key))
            if existing is not None:
                if existing.payload.get("request_fingerprint") != fingerprint:
                    raise ValueError("idempotency key cannot be reused for different inputs")
                await read_estimate_preview(db, actor=user, snapshot_id=existing.id)
                return RedirectResponse(f"/api/v1/admin/vertical-preview/foundation/{revision_id}?" +
                                        urlencode({"snapshot": str(existing.id)}), status_code=303)
        rows = (await db.scalars(select(TechnologyCalculationBlock).where(
            TechnologyCalculationBlock.technology_id == technology.id))).all()
        protected = set(PROTECTED_GEOMETRY_INPUTS) | {item.key for item in FOUNDATION_FIELDS[technology.technology_code]}
        protected.update(target for source, target in FOUNDATION_INPUT_ALIASES.items() if source in protected)
        keys, parameters = {}, {}
        for row in rows:
            block = decode_definition(row.definition, block_id=str(row.id), name=row.name)
            for kind in ("MATERIAL", "WORK"):
                role = block.material_requirement_id or str(row.id)
                keys[(str(row.id), kind)] = f"{kind}:{role}:{block.work_step_id or row.id}"
            for parameter in block.parameters:
                if parameter.input_key not in protected:
                    raw = str(form.get(f"parameter.{row.id}.{parameter.input_key}") or "").strip()
                    if raw:
                        parameters[(str(row.id), parameter.input_key)] = raw
        snapshot = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=revision_id,
            region=str(form.get("region") or ""), terms=str(form.get("terms") or ""), accounting_keys=keys,
            parameter_values=parameters, strip_roles_confirmed=form.get("strip_roles_confirmed") == "yes",
            slab_roles_confirmed=form.get("slab_roles_confirmed") == "yes",
            pile_roles_confirmed=form.get("pile_roles_confirmed") == "yes",
            pile_casing_scope_confirmed=form.get("pile_casing_scope_confirmed") == "yes",
            screw_head_match_confirmed=form.get("screw_head_match_confirmed") == "yes",
            screw_head_work_scope_confirmed=form.get("screw_head_work_scope_confirmed") == "yes",
            screw_weld_scope_confirmed=form.get("screw_weld_scope_confirmed") == "yes",
            screw_corrosion_scope_confirmed=form.get("screw_corrosion_scope_confirmed") == "yes",
            membrane_areas_disjoint_confirmed=form.get("membrane_areas_disjoint_confirmed") == "yes",
            ribbed_concrete_disjoint_confirmed=form.get("ribbed_concrete_disjoint_confirmed") == "yes",
            column_wall_rebar_disjoint_confirmed=form.get("column_wall_rebar_disjoint_confirmed") == "yes",
            uff_floor_disjoint_confirmed=form.get("uff_floor_disjoint_confirmed") == "yes",
            uff_sleeve_scope_confirmed=form.get("uff_sleeve_scope_confirmed") == "yes",
            grillage_rebar_disjoint_confirmed=form.get("grillage_rebar_disjoint_confirmed") == "yes",
            grillage_bundle_scope_confirmed=form.get("grillage_bundle_scope_confirmed") == "yes",
            ribbed_rebar_disjoint_confirmed=form.get("ribbed_rebar_disjoint_confirmed") == "yes",
            coating_work_scope_confirmed=form.get("coating_work_scope_confirmed") == "yes",
            driven_head_scope_confirmed=form.get("driven_head_scope_confirmed") == "yes",
            selected_work_block_ids=frozenset(str(value) for value in form.getlist("work_block_id"))
                if form.get("work_selection_present") == "yes" else None)
        if request_key:
            snapshot.payload = {**snapshot.payload, "idempotency_key": request_key,
                                "request_fingerprint": fingerprint}
        await db.commit()
        query = urlencode({"snapshot": str(snapshot.id)})
    except (KeyError, ValueError):
        await db.rollback()
        query = urlencode({"error": "Не удалось выполнить расчёт. Проверьте параметры и условия."})
    return RedirectResponse(f"/api/v1/admin/vertical-preview/foundation/{revision_id}?{query}", status_code=303)


@router.get("/{technology_id}", response_class=HTMLResponse)
async def preview_page(technology_id: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    _guard(user)
    tech = await db.get(Technology, technology_id)
    if tech is None or tech.status not in {"ACTIVE", "DRAFT"}:
        raise HTTPException(status_code=404)
    if (tech.technology_code in FOUNDATION_FIELDS and tech.technology_code != "FND_STRIP_MONOLITHIC_RC"
            and not request.query_params.get("snapshot")):
        return RedirectResponse("/api/v1/admin/module7/foundations/view?" + urlencode({"technology": str(tech.id)}), status_code=303)
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
        if snapshot.geometry_revision_id is None:
            raise HTTPException(status_code=404)
        geometry = await db.get(StripGeometryRevision, snapshot.geometry_revision_id)
        if geometry is None or geometry.technology_id != technology_id:
            raise HTTPException(status_code=404)
        obj = await db.get(DigitalHouseObject, geometry.object_id)
    names = {}
    if snapshot:
        captured = snapshot.payload.get("resource_names", {})
        for line in snapshot.payload["result"]["materials"]:
            identifier = line["binding"]["resource_id"]
            key = "MATERIAL:" + (identifier or "")
            material = await db.get(Material, uuid.UUID(identifier)) if identifier and key not in captured else None
            names[key] = captured.get(key, material.canonical_name if material else "Материал не выбран")
        for line in snapshot.payload["result"]["works"]:
            identifier = line["binding"]["resource_id"]
            key = "WORK:" + (identifier or "")
            work = await db.get(WorkCatalogItem, identifier) if identifier and key not in captured else None
            names[key] = captured.get(key, work.work_name if work else "Работа не выбрана")
    return templates.TemplateResponse(request, "vertical_calculation_preview.html", {
        "technology": tech, "blocks": blocks, "snapshot": snapshot, "geometry": geometry,
        "object": obj, "names": names, "error": request.query_params.get("error"), "number": _display_number,
        "provided_parameters": {(item["block_id"], item["input_key"]): item["value"]
                                for item in snapshot.payload.get("parameters", [])} if snapshot else {},
        "protected_geometry_inputs": PROTECTED_GEOMETRY_INPUTS,
        "legacy_snapshot_only": tech.technology_code in FOUNDATION_FIELDS and tech.technology_code != "FND_STRIP_MONOLITHIC_RC",
        "idempotency_key": str(uuid.uuid4()),
        "permissions": workbench_permissions(user), "atom_topbar_current_block": "Модуль №2: предварительный расчёт",
    })


@router.post("/{technology_id}")
async def calculate(technology_id: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    _guard(user)
    technology = await db.get(Technology, technology_id)
    if technology is None:
        raise HTTPException(status_code=404)
    if technology.technology_code in FOUNDATION_FIELDS and technology.technology_code != "FND_STRIP_MONOLITHIC_RC":
        raise HTTPException(status_code=400, detail="Используйте геометрию выбранной технологии")
    form = await request.form()
    try:
        raw_key = str(form.get("idempotency_key") or "")
        request_key = str(uuid.UUID(raw_key)) if raw_key else None
        fingerprint = None
        if request_key:
            if db.bind.dialect.name != "postgresql":
                raise ValueError("idempotent requests require PostgreSQL transaction locking")
            payload = sorted((str(key), str(value)) for key, value in form.multi_items()
                             if key not in {"idempotency_key", "csrf_token"})
            fingerprint = hashlib.sha256(json.dumps([str(technology_id), payload], ensure_ascii=True,
                                                    separators=(",", ":")).encode()).hexdigest()
            await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                             {"key": f"atom.m5.preview:{user.id}:{request_key}"})
            existing = await db.scalar(select(EstimatePreviewSnapshot).where(
                EstimatePreviewSnapshot.owner_user_id == user.id,
                EstimatePreviewSnapshot.payload["idempotency_key"].as_string() == request_key))
            if existing is not None:
                if existing.payload.get("request_fingerprint") != fingerprint:
                    raise ValueError("idempotency key cannot be reused for different inputs")
                await read_estimate_preview(db, actor=user, snapshot_id=existing.id)
                return RedirectResponse(f"/api/v1/admin/vertical-preview/{technology_id}?" +
                                        urlencode({"snapshot": str(existing.id)}), status_code=303)
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
        keys = {}
        for row in rows:
            block = decode_definition(row.definition, block_id=str(row.id), name=row.name)
            for kind in ("MATERIAL", "WORK"):
                role = block.material_requirement_id or str(row.id)
                default = f"{kind}:{role}:{block.work_step_id or row.id}"
                keys[(str(row.id), kind)] = str(form.get(f"scope.{row.id}.{kind}") or default)
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
            parameter_values=parameters, strip_roles_confirmed=form.get("strip_roles_confirmed") == "yes")
        if request_key:
            snapshot.payload = {**snapshot.payload, "idempotency_key": request_key,
                                "request_fingerprint": fingerprint}
        await db.commit()
        query = urlencode({"snapshot": str(snapshot.id)})
    except (KeyError, ValueError):
        await db.rollback()
        query = urlencode({"error": "Не удалось выполнить расчёт. Проверьте размеры, связи и условия."})
    return RedirectResponse(f"/api/v1/admin/vertical-preview/{technology_id}?{query}", status_code=303)
