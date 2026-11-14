"""Opt-in preview of the M2 calculation block editor."""

from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.config import settings
from app.core.permission_guard import can, require_permission
from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_calculation_block import CalculationBlockTemplate, TechnologyCalculationBlock
from app.models.module2_technology import MODULE2_OWNER_CODE, Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.services.module2_calculation_blocks import (
    add_block, copy_from_technology, copy_from_template, decode_definition, remove_block, save_template, update_block,
    verify_block,
)
from app.services.module2_calculation_graph import Threshold
from app.services.module2_calculation_composer import ComposerStep, OPERATIONS, compose_block, composer_form_data, recompose_block
from app.services.module2_calculation_presets import area_consumption_block, rectangular_volume_block, reinforcement_block
from app.services.module2_workbench import REQUIREMENT_NAMES, workbench_permissions


router = APIRouter(prefix="/admin/module2/calculation-builder", tags=["module2-calculation-builder"])
templates = Jinja2Templates(directory="templates")


def _enabled() -> None:
    if not settings.VERTICAL_CALCULATION_PREVIEW_ENABLED:
        raise HTTPException(status_code=404)


def _block(row):
    return decode_definition(row.definition, block_id=str(row.id), name=row.name,
                             material_id=str(row.material_id) if row.material_id else None, work_code=row.work_code)


def _redirect(technology_id: uuid.UUID, *, error: bool = False) -> RedirectResponse:
    suffix = "?" + urlencode({"error": "Не удалось сохранить изменения. Проверьте данные и права."}) if error else ""
    return RedirectResponse(f"/api/v1/admin/module2/calculation-builder/{technology_id}{suffix}", status_code=303)


def _number(value):
    text = str(value or "").strip().replace(",", ".")
    return Decimal(text) if text else None


def _thresholds(form, prefix):
    result = []
    for index in range(4):
        lower = _number(form.get(f"{prefix}.{index}.lower"))
        upper = _number(form.get(f"{prefix}.{index}.upper"))
        count = _number(form.get(f"{prefix}.{index}.count"))
        if lower is None and upper is None and count is None:
            continue
        if lower is None or upper is None or count is None or count < 2 or count != count.to_integral_value():
            raise ValueError("complete ranges and integer counts are required")
        result.append(Threshold(lower, upper, count, bool(form.get(f"{prefix}.{index}.inclusive"))))
    return tuple(result)


@router.get("/{technology_id}", response_class=HTMLResponse)
async def builder(technology_id: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    _enabled()
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    require_permission(user, "MODULE_01_MATERIAL_HUB", "VIEW")
    technology = await db.get(Technology, technology_id)
    if technology is None:
        raise HTTPException(status_code=404)
    rows = (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == technology_id).order_by(TechnologyCalculationBlock.position))).all()
    library = (await db.scalars(select(CalculationBlockTemplate).order_by(
        CalculationBlockTemplate.name, CalculationBlockTemplate.version.desc()))).all()
    usage = (await db.execute(select(CalculationBlockTemplate.template_key, Technology).join(
        TechnologyCalculationBlock, TechnologyCalculationBlock.template_id == CalculationBlockTemplate.id
    ).join(Technology, Technology.id == TechnologyCalculationBlock.technology_id).order_by(
        Technology.name, Technology.revision))).all()
    template_usage = {}
    for key, revision in usage:
        entries = template_usage.setdefault(key, {})
        entries[revision.id] = revision
    sources = (await db.execute(select(TechnologyCalculationBlock, Technology).join(
        Technology, Technology.id == TechnologyCalculationBlock.technology_id).where(
        Technology.id != technology_id).order_by(Technology.name, TechnologyCalculationBlock.position))).all()
    materials = (await db.scalars(select(Material).where(Material.status.notin_(
        [MaterialStatus.ARCHIVED, MaterialStatus.REJECTED])).order_by(Material.canonical_name))).all()
    works = (await db.scalars(select(WorkCatalogItem).where(
        WorkCatalogItem.status != "ARCHIVED").order_by(WorkCatalogItem.work_name))).all()
    requirements = (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology_id).order_by(TechnologyMaterialRequirement.code))).all()
    work_steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology_id).order_by(TechnologyWorkStep.position))).all()
    material_names = {item.id: item.canonical_name for item in materials}
    work_names = {item.work_code: item.work_name for item in works}
    block_views = [(row, _block(row)) for row in rows]
    return templates.TemplateResponse(request, "module2_calculation_builder.html", {
        "technology": technology, "blocks": block_views,
        "composer_data": {str(row.id): composer_form_data(graph) for row, graph in block_views},
        "library": [(row, _block(row)) for row in library],
        "template_usage": {key: list(items.values()) for key, items in template_usage.items()},
        "sources": [(row, source, _block(row)) for row, source in sources],
        "materials": materials, "works": works,
        "material_roles": [(item.id, REQUIREMENT_NAMES.get(item.code) or material_names.get(item.canonical_material_id)
                            or f"Материальная роль {index + 1}") for index, item in enumerate(requirements)],
        "work_steps": [(item.id, f"{item.position}. {work_names.get(item.work_code, 'Работа M1')}")
                       for item in work_steps],
        "may_template": can(user, MODULE2_OWNER_CODE, "ADMIN"),
        "may_approve": can(user, MODULE2_OWNER_CODE, "APPROVE"),
        "error": request.query_params.get("error"),
        "permissions": workbench_permissions(user), "atom_topbar_current_block": "Модуль №2: расчётные блоки",
    })


@router.post("/{technology_id}/{action}")
async def builder_action(technology_id: uuid.UUID, action: str, request: Request, db: DBSession, user: CurrentUser):
    _enabled()
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    require_permission(user, "MODULE_01_MATERIAL_HUB", "VIEW")
    form = await request.form()
    actor_id = getattr(user, "id", None)
    try:
        if action in {"compose", "compose-update"}:
            steps = []
            for index in range(1, 13):
                operation = str(form.get(f"step.{index}.operation") or "").strip()
                if not operation:
                    if any(str(form.get(f"step.{later}.operation") or "").strip() for later in range(index + 1, 13)):
                        raise ValueError("steps must be consecutive")
                    break
                if operation not in OPERATIONS:
                    raise ValueError("unknown operation")
                refs = tuple(int(str(form[f"step.{index}.ref.{n}"])) for n in range(1, OPERATIONS[operation] + 1))
                steps.append(ComposerStep(
                    label=str(form.get(f"step.{index}.label") or ""), operation=operation,
                    unit=str(form.get(f"step.{index}.unit") or ""), references=refs,
                    source=str(form.get(f"step.{index}.source") or ""),
                    constant=_number(form.get(f"step.{index}.constant")) if operation == "CONSTANT" else None,
                ))
            material_step = int(str(form["material_step"])) if form.get("material_step") else None
            work_step = int(str(form["work_step"])) if form.get("work_step") else None
            graph = compose_block(str(form.get("name") or ""), tuple(steps), material_step=material_step,
                                  work_step=work_step, rule_source=str(form.get("rule_source") or ""))
            material = uuid.UUID(str(form["material_id"])) if form.get("material_id") else None
            work_code = str(form["work_code"]) if form.get("work_code") else None
            if (material and material_step is None) or (work_code and work_step is None):
                raise ValueError("a linked resource requires an output")
            graph = replace(graph, material_id=str(material) if material else None, work_code=work_code,
                            material_requirement_id=str(form.get("material_requirement_id") or "") or None,
                            work_step_id=str(form.get("work_step_id") or "") or None)
            if action == "compose-update":
                block_id = uuid.UUID(str(form["block_id"]))
                original = await db.get(TechnologyCalculationBlock, block_id)
                if original is None or original.technology_id != technology_id or composer_form_data(_block(original)) is None:
                    raise ValueError("block cannot be edited with this composer")
                graph = recompose_block(_block(original), graph)
                await update_block(db, technology_id=technology_id, block_id=block_id, block=graph,
                                   expected_version=int(str(form["version"])), actor=user, actor_id=actor_id)
            else:
                await add_block(db, technology_id=technology_id, block=graph, actor=user, actor_id=actor_id)
        elif action == "add":
            preset = form.get("preset")
            if preset not in {"volume", "surface", "reinforcement"}:
                raise ValueError("unknown preset")
            if preset == "reinforcement":
                graph = reinforcement_block(thresholds=_thresholds(form, "range"),
                                            source=str(form.get("rule_source") or ""))
            else:
                graph = rectangular_volume_block() if preset == "volume" else area_consumption_block()
            material = uuid.UUID(str(form["material_id"])) if form.get("material_id") else None
            graph = replace(graph, material_id=str(material) if material else None,
                            work_code=str(form["work_code"]) if form.get("work_code") else None,
                            material_requirement_id=str(form.get("material_requirement_id") or "") or None,
                            work_step_id=str(form.get("work_step_id") or "") or None)
            await add_block(db, technology_id=technology_id, block=graph, actor=user, actor_id=actor_id)
        elif action in {"copy-template", "copy-technology"}:
            source_id = uuid.UUID(str(form["source_id"]))
            source = await db.get(CalculationBlockTemplate if action == "copy-template" else TechnologyCalculationBlock,
                                  source_id)
            if source is None:
                raise ValueError("source missing")
            graph = _block(source)
            keys = {node.input_key for node in graph.nodes if node.operation == "INPUT"}
            mapping = {key: str(form.get(f"mapping.{key}") or "").strip() for key in keys}
            material = uuid.UUID(str(form["material_id"])) if form.get("material_id") else None
            common = dict(technology_id=technology_id, input_mapping=mapping, material_id=material,
                          work_code=str(form["work_code"]) if form.get("work_code") else None,
                          material_requirement_id=str(form.get("material_requirement_id") or "") or None,
                          work_step_id=str(form.get("work_step_id") or "") or None,
                          actor=user, actor_id=actor_id)
            if action == "copy-template":
                await copy_from_template(db, template_id=source_id, **common)
            else:
                await copy_from_technology(db, source_block_id=source_id, **common)
        elif action in {"update", "delete", "save-template", "verify"}:
            block_id = uuid.UUID(str(form["block_id"]))
            row = await db.get(TechnologyCalculationBlock, block_id)
            if row is None or row.technology_id != technology_id:
                raise ValueError("block missing")
            if action == "verify":
                require_permission(user, MODULE2_OWNER_CODE, "APPROVE")
                await verify_block(db, technology_id=technology_id, block_id=block_id,
                    expected_version=int(str(form["version"])), source=str(form.get("rule_source") or ""),
                    actor=user, actor_id=actor_id)
            elif action == "save-template":
                require_permission(user, MODULE2_OWNER_CODE, "ADMIN")
                await save_template(db, block_id=block_id, template_key=str(form.get("template_key") or uuid.uuid4().hex),
                                    name=str(form.get("template_name") or ""), description=None,
                                    actor=user, actor_id=actor_id)
            elif action == "delete":
                await remove_block(db, technology_id=technology_id, block_id=block_id,
                                   expected_version=int(str(form["version"])), actor=user, actor_id=actor_id)
            else:
                graph = _block(row)
                parameters = []
                for parameter in graph.parameters:
                    raw = str(form.get(f"default.{parameter.input_key}") or "").strip()
                    source = str(form.get(f"source.{parameter.input_key}") or "").strip()
                    if raw and not source:
                        raise ValueError("parameter source required")
                    value = _number(raw)
                    minimum, maximum = _number(form.get(f"min.{parameter.input_key}")), _number(form.get(f"max.{parameter.input_key}"))
                    if (value == parameter.default and (source or None) == parameter.source and
                            minimum == parameter.minimum and maximum == parameter.maximum):
                        parameters.append(parameter)
                    else:
                        parameters.append(replace(parameter, default=value, minimum=minimum, maximum=maximum, source=source or None,
                                                  status="PRELIMINARY" if raw else "UNCONFIRMED", auto_apply=bool(raw)))
                if any(node.operation == "PIECEWISE" and len(node.thresholds) > 4 for node in graph.nodes):
                    raise ValueError("this editor cannot modify more than four ranges")
                nodes = tuple(replace(node, thresholds=_thresholds(form, f"range.{node.id}"))
                              if node.operation == "PIECEWISE" else node for node in graph.nodes)
                changed_rule = nodes != graph.nodes or str(form.get("rule_source") or "").strip() != (graph.rule_source or "")
                rule_source = str(form.get("rule_source") or "").strip() or None
                material = uuid.UUID(str(form["material_id"])) if form.get("material_id") else None
                graph = replace(graph, name=str(form.get("name") or "").strip(), parameters=tuple(parameters),
                                nodes=nodes, rule_source=rule_source,
                                rule_status=("PRELIMINARY" if rule_source else "UNCONFIRMED") if changed_rule else graph.rule_status,
                                material_id=str(material) if material else None,
                                work_code=str(form["work_code"]) if form.get("work_code") else None,
                                material_requirement_id=str(form.get("material_requirement_id") or "") or None,
                                work_step_id=str(form.get("work_step_id") or "") or None)
                await update_block(db, technology_id=technology_id, block_id=block_id, block=graph,
                                   expected_version=int(str(form["version"])), actor=user, actor_id=actor_id)
        else:
            raise HTTPException(status_code=404)
        await db.commit()
    except (KeyError, ValueError, InvalidOperation):
        await db.rollback()
        return _redirect(technology_id, error=True)
    return _redirect(technology_id)
