from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DBSession
from app.core.permission_guard import can, require_permission
from app.models.enums import MaterialStatus, UserRole
from app.models.material import Material
from app.models.module2_technology import MODULE2_OWNER_CODE, Technology
from app.models.module2_content_catalog import TechnologyCategory
from app.schemas.module2_knowledge import (
    CompatibilityRuleDraftInput,
    ConsumptionNormDraftInput,
    KnowledgeRuleDraftInput,
)
from app.schemas.module2_technology import (
    TechnologyDraftInput,
    TechnologyDraftUpdate,
    TechnologyLayerInput,
    TechnologyLifecycle,
    TechnologyMaterialRequirementInput,
    TechnologyNodeInput,
    TechnologyWorkStepInput,
)
from app.services.module2_knowledge_foundation import (
    transition_compatibility_rule,
    transition_consumption_norm,
    transition_knowledge_rule,
    validate_technology_knowledge_publication,
    verify_evidence_references,
)
from app.services.module2_operational_widgets import build_technology_readiness_widget, build_workbench_queue_widget
from app.services.module2_default_assumptions import active_defaults, may_use_default, revise_default_assumption
from app.services.module2_encyclopedia_editorial import (
    MATERIAL_NAMES, effective_material_name, material_default_label,
)
from app.services.module2_material_resolution import (
    MaterialResolutionError, change_gap_query, compatible_materials, dismiss_gap, ensure_gap,
    gap_for_requirement, request_m1_search, resolve_existing,
)
from app.services.module2_content_catalog import (
    ContentCatalogError,
    category_tree,
    create_category,
    list_categories,
    resolve_category_id,
    start_content_package,
    transition_category,
    update_draft_category,
)
from app.services.module2_technology_foundation import (
    build_draft_technology,
    create_next_revision,
    persist_technology_draft,
    read_technology,
    transition_technology,
    update_draft_technology,
)
from app.services.module2_workbench import (
    REQUIREMENT_NAMES,
    add_evidence,
    build_technology_detail_view,
    build_technology_list_view,
    delete_draft_component,
    move_draft_ordered_item,
    upsert_compatibility_rule,
    upsert_consumption_norm,
    upsert_draft_layer,
    upsert_draft_node,
    upsert_draft_requirement,
    upsert_draft_work_step,
    upsert_knowledge_rule,
    workbench_permissions,
)


router = APIRouter(prefix="/admin/module2/workbench", tags=["module2-workbench"])
templates = Jinja2Templates(directory="templates")


def _admin_material_card_url(material_id: uuid.UUID) -> str:
    return f"/api/v1/admin/material-hub/view/materials/{material_id}"

TAB_BY_SECTION = {
    "general": "general", "validation": "general",
    "layers": "construction", "nodes": "construction", "construction": "construction",
    "materials": "materials", "defaults": "materials",
    "works": "works", "norms": "works",
    "rules": "rules", "compatibility": "rules",
    "evidence": "sources", "sources": "sources", "revisions": "revisions",
}
LAYER_DEFAULT_PARAMETERS = {
    "LOAD_BEARING_SLAB": "SLAB_THICKNESS_MM",
    "SLAB_AND_RIBS": "SLAB_THICKNESS_MM",
    "RIBBED_RC_FOUNDATION": "SLAB_THICKNESS_MM",
    "WALL_CONCRETE": "WALL_THICKNESS_MM",
    "XPS_LAYER": "INSULATION_THICKNESS_MM",
    "COATING_SYSTEM": "COATING_THICKNESS_MM",
    "MEMBRANE_SYSTEM": "MEMBRANE_THICKNESS_MM",
}


@router.get("", response_class=HTMLResponse)
async def technology_workbench_list(request: Request, db: DBSession, user: CurrentUser):
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    rows = list(await build_technology_list_view(db))
    workbench_metrics = build_workbench_queue_widget(user, [row for row in rows if row["status"] != "ARCHIVED"])
    categories = await list_categories(db)
    category_names = {item.id: item.name for item in categories}
    for row in rows:
        row["category_name"] = category_names.get(row["category_id"], "Без категории")
    status_filter = str(request.query_params.get("status") or "").upper()
    category_filter = str(request.query_params.get("category") or "")
    material_filter = str(request.query_params.get("materials") or "")
    blocker_filter = str(request.query_params.get("blockers") or "")
    query = str(request.query_params.get("q") or "").strip().lower()
    if status_filter in {item.value for item in TechnologyLifecycle}:
        rows = [item for item in rows if item["status"] == status_filter]
    else:
        rows = [item for item in rows if item["status"] != "ARCHIVED"]
    if category_filter:
        rows = [item for item in rows if str(item["category_id"]) == category_filter]
    if material_filter == "needs_selection":
        rows = [item for item in rows if item["unresolved_material_count"]]
    elif material_filter == "open_gap":
        rows = [item for item in rows if item["open_gap_count"]]
    elif material_filter == "selected":
        rows = [item for item in rows if not item["unresolved_material_count"]]
    if blocker_filter == "yes":
        rows = [item for item in rows if item["blocker_count"]]
    elif blocker_filter == "no":
        rows = [item for item in rows if not item["blocker_count"]]
    if query:
        rows = [item for item in rows if query in f"{item['name']} {item['code']} {item['system_code']}".lower()]
    return templates.TemplateResponse(
        request,
        "module2_technology_workbench.html",
        {
            "technologies": rows,
            "workbench_metrics": workbench_metrics,
            "categories": tuple(item for item in categories if item.status != "ARCHIVED"),
            "permissions": workbench_permissions(user),
            "status_filter": status_filter,
            "category_filter": category_filter,
            "material_filter": material_filter,
            "blocker_filter": blocker_filter,
            "query": request.query_params.get("q", ""),
            "notice": request.query_params.get("notice"),
            "error": request.query_params.get("error"),
            "atom_topbar_current_block": "Модуль №2: Технологии",
        },
    )


@router.post("/create")
async def technology_workbench_create(request: Request, db: DBSession, user: CurrentUser):
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    form = await request.form()
    try:
        technology = build_draft_technology(
            TechnologyDraftInput(
                technology_code=_required(form, "technology_code").upper(),
                name=_required(form, "name"),
                description=_optional(form, "description"),
                system_code=_optional(form, "system_code"),
                category_id=await resolve_category_id(db, _optional(form, "category_code")),
            ),
            actor_role_code=user,
            created_by_user_id=_user_id(user),
        )
        await persist_technology_draft(db, technology)
    except (ValueError, PermissionError, ValidationError, IntegrityError) as exc:
        await db.rollback()
        return _redirect_list(error=_human_error(exc))
    return _redirect_detail(technology.id, notice="Черновик технологии создан.")


@router.get("/categories", response_class=HTMLResponse)
async def technology_categories(request: Request, db: DBSession, user: CurrentUser):
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    categories = await list_categories(db)
    return templates.TemplateResponse(
        request, "module2_technology_categories.html",
        {
            "category_rows": category_tree(categories),
            "parent_options": tuple(item for item in categories if item.status != "ARCHIVED"),
            "permissions": workbench_permissions(user),
            "notice": request.query_params.get("notice"),
            "error": request.query_params.get("error"),
            "atom_topbar_current_block": "Модуль №2: Категории технологий",
        },
    )


@router.post("/categories/create")
async def technology_category_create(request: Request, db: DBSession, user: CurrentUser):
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    form = await request.form()
    try:
        await create_category(
            db,
            code=_required(form, "code"),
            name=_required(form, "name"),
            parent_code=_optional(form, "parent_code"),
            scope_code=_optional(form, "scope_code") or "RESIDENTIAL",
            sort_order=int(form.get("sort_order") or 0),
            description=_optional(form, "description"),
        )
    except (ValueError, IntegrityError) as exc:
        await db.rollback()
        return _redirect_categories(error=str(exc))
    return _redirect_categories(notice="Черновик категории создан.")


@router.post("/categories/{category_code}/update")
async def technology_category_update(
    category_code: str, request: Request, db: DBSession, user: CurrentUser
):
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    category = await db.scalar(
        select(TechnologyCategory).where(TechnologyCategory.code == category_code)
    )
    if not category:
        return _redirect_categories(error="Категория не найдена.")
    form = await request.form()
    try:
        await update_draft_category(
            db, category,
            name=_required(form, "name"),
            parent_code=_optional(form, "parent_code"),
            scope_code=_required(form, "scope_code"),
            sort_order=int(form.get("sort_order") or 0),
            description=_optional(form, "description"),
        )
    except (ValueError, IntegrityError) as exc:
        await db.rollback()
        return _redirect_categories(error=str(exc))
    return _redirect_categories(notice="Категория обновлена.")


@router.post("/categories/{category_code}/transition")
async def technology_category_transition(
    category_code: str, request: Request, db: DBSession, user: CurrentUser
):
    form = await request.form()
    target = _required(form, "target")
    require_permission(user, MODULE2_OWNER_CODE, "APPROVE" if target == "ACTIVE" else "ADMIN")
    category = await db.scalar(
        select(TechnologyCategory).where(TechnologyCategory.code == category_code)
    )
    if not category:
        return _redirect_categories(error="Категория не найдена.")
    try:
        await transition_category(db, category, target)
    except (ValueError, IntegrityError) as exc:
        await db.rollback()
        return _redirect_categories(error=str(exc))
    return _redirect_categories(notice="Статус категории обновлён.")


@router.post("/categories/{category_code}/start-content")
async def technology_category_start_content(
    category_code: str, db: DBSession, user: CurrentUser
):
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    category = await db.scalar(
        select(TechnologyCategory).where(TechnologyCategory.code == category_code)
    )
    if not category:
        return _redirect_categories(error="Категория не найдена.")
    try:
        await start_content_package(db, category)
    except ContentCatalogError as exc:
        await db.rollback()
        return _redirect_categories(error=str(exc))
    return _redirect_categories(notice="Контентный пакет начат.")


@router.get("/widgets/technology-readiness")
async def technology_readiness_widget(db: DBSession, user: CurrentUser):
    return await build_technology_readiness_widget(db, user)


@router.get("/by-code/{technology_code}")
async def technology_workbench_by_code(technology_code: str, db: DBSession, user: CurrentUser):
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    technology = await db.scalar(
        select(Technology)
        .where(Technology.technology_code == technology_code, Technology.status == "ACTIVE")
        .order_by(Technology.revision.desc())
    )
    if technology is None:
        return _redirect_list(error="Технология не найдена.")
    return _redirect_detail(technology.id)


def _selected_material(requirement, gap, candidates):
    selected_id = requirement.canonical_material_id
    if not selected_id and gap and gap.status in {"RESOLVED_EXISTING", "RESOLVED_NEW_MATERIAL"}:
        selected_id = gap.resolved_material_id
    return next((candidate for candidate in candidates if candidate.id == selected_id), None)


async def _technical_material_candidates(db, requirements):
    ids = {item.canonical_material_id for item in requirements
           if item.selector_kind == "CANONICAL_MATERIAL" and item.canonical_material_id}
    if not ids:
        return {}
    rows = (await db.scalars(select(Material).where(
        Material.id.in_(ids), Material.status.in_((
            MaterialStatus.DRAFT, MaterialStatus.AUTO_CREATED, MaterialStatus.NEEDS_REVIEW,
        )),
    ))).all()
    return {item.id: item for item in rows}


@router.get("/{technology_id}", response_class=HTMLResponse)
async def technology_workbench_detail(
    technology_id: uuid.UUID,
    request: Request,
    db: DBSession,
    user: CurrentUser,
):
    require_permission(user, MODULE2_OWNER_CODE, "EDIT")
    technology = await read_technology(db, technology_id)
    if technology is None:
        return _redirect_list(error="Технология не найдена.")
    context = await build_technology_detail_view(db, technology)
    technical_candidates = await _technical_material_candidates(db, technology.requirements)
    assumptions = active_defaults(technology)
    for layer in context["layers"]:
        model = layer["model"]
        expression = (model.thickness_expression or "").strip()
        named_parameter = LAYER_DEFAULT_PARAMETERS.get(model.functional_role)
        matches = [item for item in assumptions if may_use_default(technology, item) and (
            (expression and item.parameter_code.lower() == expression.lower()) or
            (not expression and named_parameter and item.parameter_code == named_parameter) or
            (not expression and model.material_requirement_id and
             item.material_requirement_id == model.material_requirement_id and
             "THICKNESS" in item.parameter_code.upper())
        )]
        if len(matches) == 1:
            value = matches[0].default_value.get("value")
            layer["thickness_label"] = f"Допущение платформы: {matches[0].name_ru} — {value} {matches[0].unit or ''}".strip()
        elif expression and any(char.isdigit() for char in expression):
            layer["thickness_label"] = expression
        else:
            layer["thickness_label"] = "Уточняется для объекта"
    for item in context["requirements"]:
        requirement = item["model"]
        linked_defaults = tuple(
            assumption for assumption in assumptions
            if assumption.material_requirement_id == requirement.id
        )
        item["effective_name"] = effective_material_name(
            requirement.code, item["display_name"], linked_defaults
        )
        item["default_label"] = material_default_label(linked_defaults)
        item["class_label"] = MATERIAL_NAMES.get(requirement.code, item["display_name"])
        item["candidates"] = await compatible_materials(db, requirement)
        item["gap"] = await gap_for_requirement(db, requirement.id)
        item["material_card_url"] = _admin_material_card_url
        item["selected_material"] = _selected_material(requirement, item["gap"], item["candidates"])
        item["technical_candidate"] = (technical_candidates.get(requirement.canonical_material_id)
                                       if requirement.selector_kind == "CANONICAL_MATERIAL" else None)
    for item in context["defaults"]:
        requirement = item["model"].material_requirement
        item["human_name"] = (
            MATERIAL_NAMES.get(requirement.code, item["model"].name_ru)
            if item["model"].value_type == "MATERIAL_CLASS" and requirement
            else item["model"].name_ru
        )
        item["human_requirement_name"] = (
            MATERIAL_NAMES.get(requirement.code, item["requirement_name"])
            if requirement else None
        )
    categories = await list_categories(db)
    context["technology_category_options"] = tuple(
        item for item in categories if item.status != "ARCHIVED"
    )
    context["category_code"] = next(
        (item.code for item in categories if item.id == technology.category_id), None
    )
    context["category_name"] = next(
        (item.name for item in categories if item.id == technology.category_id), "Без категории"
    )
    context.update(
        {
            "permissions": workbench_permissions(user),
            "can_view_m1_card": user.role == UserRole.ADMIN and can(user, "MODULE_01_MATERIAL_HUB", "VIEW"),
            "notice": request.query_params.get("notice"),
            "error": request.query_params.get("error"),
            "active_tab": TAB_BY_SECTION.get(request.query_params.get("tab", "general"), "general"),
            "atom_topbar_current_block": "Модуль №2: рабочая область технологий",
        }
    )
    return templates.TemplateResponse(request, "module2_technology_detail.html", context)


@router.post("/{technology_id}/material-gaps/{requirement_id}/{action}")
async def technology_material_gap_action(
    technology_id: uuid.UUID, requirement_id: uuid.UUID, action: str,
    request: Request, db: DBSession, user: CurrentUser,
):
    require_permission(user, MODULE2_OWNER_CODE, "ADMIN")
    technology = await read_technology(db, technology_id)
    if technology is None:
        return _redirect_list(error="Технология не найдена.")
    requirement = next((item for item in technology.requirements if item.id == requirement_id), None)
    gap = await gap_for_requirement(db, requirement_id) if requirement else None
    if requirement is None or gap is None or gap.technology_id != technology.id:
        return _redirect_detail(technology_id, error="Пробел материала не найден.", section="materials")
    form = await request.form()
    try:
        if action == "query":
            await change_gap_query(db, gap, str(form.get("search_phrase") or ""), _user_id(user))
            notice = "Поисковый запрос обновлен."
        elif action == "resolve":
            await resolve_existing(db, gap, requirement, _required_uuid(form, "material_id"), _user_id(user))
            notice = "Привязана каноническая карточка M1."
        elif action == "search":
            await request_m1_search(db, gap, _user_id(user))
            notice = "Запрос передан в очередь M1."
        elif action == "dismiss":
            await dismiss_gap(db, gap, str(form.get("rationale") or ""), _user_id(user))
            notice = "Пробел отклонен с обоснованием."
        else:
            raise MaterialResolutionError("Неизвестное действие с материалом.")
        await db.flush()
    except (ValueError, IntegrityError) as exc:
        await db.rollback()
        return _redirect_detail(technology_id, error=_human_error(exc), section="materials")
    return _redirect_detail(technology_id, notice=notice, section="materials")


@router.post("/{technology_id}/actions/{action}")
async def technology_workbench_action(
    technology_id: uuid.UUID,
    action: str,
    request: Request,
    db: DBSession,
    user: CurrentUser,
):
    form = await request.form()
    required_action = _required_permission(action, form)
    require_permission(user, MODULE2_OWNER_CODE, required_action)
    technology = await read_technology(db, technology_id)
    if technology is None:
        return _redirect_list(error="Технология не найдена.")

    role_code = user
    section = str(form.get("section") or "general")
    try:
        result = await _perform_action(
            action,
            form,
            technology=technology,
            db=db,
            role_code=role_code,
            user_id=_user_id(user),
        )
        await db.flush()
    except (ValueError, PermissionError, ValidationError, IntegrityError) as exc:
        await db.rollback()
        return _redirect_detail(technology_id, error=_human_error(exc), section=section)
    if isinstance(result, tuple):
        notice, destination_id = result
    else:
        notice, destination_id = result, technology_id
    return _redirect_detail(destination_id, notice=notice, section=section)


async def _perform_action(
    action: str,
    form,
    *,
    technology: Technology,
    db: DBSession,
    role_code: object,
    user_id: uuid.UUID | None,
) -> str | tuple[str, uuid.UUID]:
    item_id = _optional_uuid(form, "item_id")
    if action == "save-default":
        await revise_default_assumption(
            db, technology, assumption_code=_required(form, "assumption_code"),
            value=_required(form, "value"), actor_user_id=user_id,
        )
        return "Значение по умолчанию сохранено в новой редакции."
    if action == "update-general":
        update_draft_technology(
            technology,
            TechnologyDraftUpdate(
                name=_required(form, "name"),
                description=_optional(form, "description"),
                system_code=_optional(form, "system_code"),
                category_id=await resolve_category_id(db, _optional(form, "category_code")),
            ),
            actor_role_code=role_code,
        )
        return "Основные сведения сохранены."
    if action == "create-revision":
        revision = create_next_revision(
            technology,
            actor_role_code=role_code,
            created_by_user_id=user_id,
        )
        await persist_technology_draft(db, revision)
        return "Новая черновая редакция создана.", revision.id
    if action == "transition":
        target = TechnologyLifecycle(_required(form, "target"))
        if target == TechnologyLifecycle.ACTIVE:
            verified = await verify_evidence_references(db, technology.evidence_references)
            blockers = validate_technology_knowledge_publication(
                technology, verified_evidence_reference_ids=verified,
            )
            if blockers:
                raise ValueError("У инженерных записей отсутствуют связанные источники или необходимые данные.")
        transition_technology(technology, target, actor_role_code=role_code)
        if target == TechnologyLifecycle.ACTIVE:
            await db.flush()
            for requirement in technology.requirements:
                await ensure_gap(
                    db, technology, requirement,
                    search_phrase=REQUIREMENT_NAMES.get(requirement.code, requirement.code),
                    actor_id=user_id,
                )
        return f"Статус изменен: {target.value}."
    if action == "save-requirement":
        command = _requirement_input(form)
        if item_id:
            existing = next((item for item in technology.requirements if item.id == item_id), None)
            if existing is not None:
                command = command.model_copy(update={"technical_constraints": {
                    **(existing.technical_constraints or {}), **command.technical_constraints,
                }})
        upsert_draft_requirement(
            technology,
            command,
            actor_role_code=role_code,
            item_id=item_id,
        )
        return "Требование к материалу сохранено."
    if action == "save-layer":
        upsert_draft_layer(
            technology,
            TechnologyLayerInput(
                position=_positive_int(form, "position"),
                functional_role=_required(form, "functional_role").upper(),
                requirement_code=_optional(form, "requirement_code"),
                thickness_expression=_optional(form, "thickness_expression"),
                is_mandatory=_checked(form, "is_mandatory"),
                notes=_optional(form, "notes"),
                restrictions=_single_mapping(form, "restriction_field", "restriction_value"),
            ),
            actor_role_code=role_code,
            item_id=item_id,
        )
        return "Слой сохранен."
    if action == "save-node":
        upsert_draft_node(
            technology,
            TechnologyNodeInput(
                code=_required(form, "code").upper(),
                node_type=_required(form, "node_type").upper(),
                name=_required(form, "name"),
                description=_optional(form, "description"),
                conditions=_single_mapping(form, "condition_field", "condition_value"),
            ),
            actor_role_code=role_code,
            item_id=item_id,
        )
        return "Узел сохранен."
    if action == "save-work-step":
        upsert_draft_work_step(
            technology,
            TechnologyWorkStepInput(
                position=_positive_int(form, "position"),
                work_code=_required(form, "work_code"),
                applicability_expression=_optional(form, "applicability_expression"),
                dependency_step_codes=_csv(form.get("dependency_step_codes")),
                instructions=_optional(form, "instructions"),
            ),
            actor_role_code=role_code,
            item_id=item_id,
        )
        return "Работа сохранена."
    if action == "save-norm":
        upsert_consumption_norm(
            technology,
            ConsumptionNormDraftInput(
                norm_code=_required(form, "norm_code").upper(),
                scope_layer_id=_optional_uuid(form, "scope_layer_id"),
                scope_requirement_id=_optional_uuid(form, "scope_requirement_id"),
                scope_work_step_id=_optional_uuid(form, "scope_work_step_id"),
                resource=_selector_input(form, "resource"),
                basis_quantity=_positive_decimal(form, "basis_quantity"),
                basis_unit=_required(form, "basis_unit"),
                consumption_quantity=_positive_decimal(form, "consumption_quantity"),
                consumption_unit=_required(form, "consumption_unit"),
                conditions=_condition_input(form),
                blockers=_csv(form.get("blockers")),
            ),
            actor_role_code=role_code,
            created_by_user_id=user_id,
            item_id=item_id,
        )
        return "Норма расхода сохранена."
    if action == "save-compatibility":
        upsert_compatibility_rule(
            technology,
            CompatibilityRuleDraftInput(
                rule_code=_required(form, "rule_code").upper(),
                subject=_selector_input(form, "subject"),
                object=_selector_input(form, "object"),
                relation=_required(form, "relation"),
                conditions=_condition_input(form),
                reason=_optional(form, "reason"),
                is_symmetric=_checked(form, "is_symmetric"),
                blockers=_csv(form.get("blockers")),
            ),
            actor_role_code=role_code,
            created_by_user_id=user_id,
            item_id=item_id,
        )
        return "Правило совместимости сохранено."
    if action == "save-rule":
        upsert_knowledge_rule(
            technology,
            KnowledgeRuleDraftInput(
                rule_code=_required(form, "rule_code").upper(),
                scope_kind=_required(form, "scope_kind"),
                scope_reference=_optional(form, "scope_reference"),
                conditions=_condition_input(form, required=True),
                outcome_type=_required(form, "outcome_type"),
                outcome_payload=_single_mapping(form, "outcome_field", "outcome_value"),
                blockers=_csv(form.get("blockers")),
            ),
            actor_role_code=role_code,
            created_by_user_id=user_id,
            item_id=item_id,
        )
        return "Инженерное правило сохранено."
    if action == "add-evidence":
        source_kind, source_id = _evidence_source(form)
        add_evidence(
            technology,
            {
                "document_id": source_id if source_kind == "document" else None,
                "knowledge_resource_id": source_id if source_kind == "resource" else None,
                "target_kind": _required(form, "target_kind"),
                "target_reference": _optional(form, "target_reference"),
                "interpretation": _optional(form, "interpretation"),
            },
            actor_role_code=role_code,
        )
        return "Подтверждение M1 добавлено."
    if action == "delete":
        delete_draft_component(
            technology,
            _required(form, "component"),
            _required_uuid(form, "item_id"),
            actor_role_code=role_code,
        )
        return "Черновая запись удалена."
    if action == "move":
        await move_draft_ordered_item(
            db,
            technology,
            _required(form, "component"),
            _required_uuid(form, "item_id"),
            _required(form, "direction"),
            actor_role_code=role_code,
        )
        return "Порядок обновлен."
    if action == "transition-knowledge":
        if technology.status != TechnologyLifecycle.DRAFT.value:
            raise ValueError("Изменять инженерные записи можно только в черновой редакции технологии.")
        component = _required(form, "component")
        entity = _knowledge_entity(technology, component, _required_uuid(form, "item_id"))
        target = TechnologyLifecycle(_required(form, "target"))
        verified = await verify_evidence_references(db, technology.evidence_references)
        common = {
            "technology": technology,
            "evidence_references": technology.evidence_references,
            "actor_role_code": role_code,
            "verified_evidence_reference_ids": verified,
            "allow_draft_technology": True,
        }
        if component == "norm":
            transition_consumption_norm(entity, target, **common)
        elif component == "compatibility":
            transition_compatibility_rule(entity, target, peer_rules=technology.compatibility_rules, **common)
        elif component == "rule":
            transition_knowledge_rule(entity, target, peer_rules=technology.knowledge_rules, **common)
        else:
            raise ValueError("Неизвестный тип инженерной записи.")
        return f"Статус инженерной записи изменен: {target.value}."
    raise ValueError("Неизвестное действие Workbench.")


def _required_permission(action: str, form) -> str:
    if action == "save-default":
        return "ADMIN"
    if action in {"transition", "transition-knowledge"}:
        target = str(form.get("target") or "").upper()
        if target in {"ACTIVE", "DRAFT"}:
            return "APPROVE"
        if target == "ARCHIVED":
            return "ADMIN"
    return "EDIT"


def _requirement_input(form) -> TechnologyMaterialRequirementInput:
    kind = _required(form, "selector_kind")
    return TechnologyMaterialRequirementInput(
        code=_required(form, "code").upper(),
        selector_kind=kind,
        material_role_code=_optional(form, "material_role_code"),
        canonical_material_id=_optional_uuid(form, "canonical_material_id"),
        material_category_id=_optional_uuid(form, "material_category_id"),
        material_type_id=_optional_uuid(form, "material_type_id"),
        technical_constraints=_single_mapping(form, "constraint_field", "constraint_value"),
        notes=_optional(form, "notes"),
    )


def _selector_input(form, prefix: str) -> dict:
    return {
        "selector_kind": _required(form, f"{prefix}_kind"),
        "canonical_material_id": _optional_uuid(form, f"{prefix}_canonical_material_id"),
        "material_category_id": _optional_uuid(form, f"{prefix}_material_category_id"),
        "material_type_id": _optional_uuid(form, f"{prefix}_material_type_id"),
        "material_requirement_id": _optional_uuid(form, f"{prefix}_material_requirement_id"),
        "material_role_code": _optional(form, f"{prefix}_material_role_code"),
        "technical_constraints": _single_mapping(
            form,
            f"{prefix}_constraint_field",
            f"{prefix}_constraint_value",
        ),
    }


def _condition_input(form, *, required: bool = False) -> list[dict]:
    field = _optional(form, "condition_field")
    if not field:
        if required:
            raise ValueError("Укажите условие правила.")
        return []
    operator = _required(form, "condition_operator")
    raw_value = _optional(form, "condition_value")
    if operator == "EXISTS":
        value = None if raw_value is None else raw_value.lower() not in {"false", "0", "нет"}
    elif operator in {"IN", "NOT_IN", "BETWEEN"}:
        value = [_scalar(item) for item in _csv(raw_value)]
    else:
        if raw_value is None:
            raise ValueError("Укажите значение условия.")
        value = _scalar(raw_value)
    return [
        {
            "source": _required(form, "condition_source"),
            "field": field,
            "operator": operator,
            "value": value,
            "required_for_activation": _checked(form, "condition_required"),
        }
    ]


def _knowledge_entity(technology: Technology, component: str, item_id: uuid.UUID):
    collection = {
        "norm": technology.consumption_norms,
        "compatibility": technology.compatibility_rules,
        "rule": technology.knowledge_rules,
    }.get(component)
    if collection is None:
        raise ValueError("Неизвестный тип инженерной записи.")
    entity = next((item for item in collection if item.id == item_id), None)
    if entity is None:
        raise ValueError("Инженерная запись не найдена.")
    return entity


def _evidence_source(form) -> tuple[str, uuid.UUID]:
    raw = _required(form, "source_reference")
    try:
        kind, value = raw.split(":", 1)
    except ValueError as exc:
        raise ValueError("Выберите источник M1.") from exc
    if kind not in {"document", "resource"}:
        raise ValueError("Неизвестный тип источника M1.")
    return kind, uuid.UUID(value)


def _single_mapping(form, key_name: str, value_name: str) -> dict:
    key = _optional(form, key_name)
    value = _optional(form, value_name)
    return {key: _scalar(value)} if key and value is not None else {}


def _required(form, name: str) -> str:
    value = str(form.get(name) or "").strip()
    if not value:
        raise ValueError(f"Заполните поле: {name.replace('_', ' ')}.")
    return value


def _optional(form, name: str) -> str | None:
    value = str(form.get(name) or "").strip()
    return value or None


def _required_uuid(form, name: str) -> uuid.UUID:
    value = _optional_uuid(form, name)
    if value is None:
        raise ValueError("Не выбрана запись Workbench.")
    return value


def _optional_uuid(form, name: str) -> uuid.UUID | None:
    value = _optional(form, name)
    return uuid.UUID(value) if value else None


def _positive_int(form, name: str) -> int:
    value = int(_required(form, name))
    if value < 1:
        raise ValueError("Позиция должна быть положительной.")
    return value


def _positive_decimal(form, name: str) -> Decimal:
    try:
        value = Decimal(_required(form, name).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Количество должно быть числом.") from exc
    if value <= 0:
        raise ValueError("Количество должно быть больше нуля.")
    return value


def _checked(form, name: str) -> bool:
    return str(form.get(name) or "").lower() in {"1", "true", "on", "yes"}


def _csv(value) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _scalar(value: str | None):
    if value is None:
        return None
    text = str(value).strip()
    try:
        number = Decimal(text.replace(",", "."))
        return int(number) if number == number.to_integral_value() else float(number)
    except InvalidOperation:
        return text


def _user_id(user) -> uuid.UUID | None:
    value = getattr(user, "id", None)
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _human_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        details = exc.errors()
        if details:
            return str(details[0].get("msg") or "Проверьте заполненные поля.")
    message = str(getattr(exc, "orig", None) or exc)
    translations = {
        "technology activation blocked": "Активация технологии запрещена",
        "a new revision can only supersede ACTIVE technology": "Новую редакцию можно создать только из действующей технологии.",
        "unsupported technology lifecycle transition": "Недопустимый переход статуса технологии",
        "only a DRAFT technology can be updated in place": "Изменять можно только черновую редакцию технологии.",
        "knowledge activation blocked": "Активация инженерной записи запрещена",
    }
    for source, target in translations.items():
        if source in message:
            return message.replace(source, target)
    return message or "Действие не выполнено."


def _redirect_list(*, notice: str | None = None, error: str | None = None):
    query = urlencode({key: value for key, value in {"notice": notice, "error": error}.items() if value})
    return RedirectResponse(f"/api/v1/admin/module2/workbench{'?' + query if query else ''}", status_code=303)


def _redirect_categories(*, notice: str | None = None, error: str | None = None):
    query = urlencode({key: value for key, value in {"notice": notice, "error": error}.items() if value})
    return RedirectResponse(
        f"/api/v1/admin/module2/workbench/categories{'?' + query if query else ''}",
        status_code=303,
    )


def _redirect_detail(
    technology_id: uuid.UUID,
    *,
    notice: str | None = None,
    error: str | None = None,
    section: str | None = None,
):
    query = urlencode({key: value for key, value in {"notice": notice, "error": error, "tab": TAB_BY_SECTION.get(section, "general") if section else None}.items() if value})
    return RedirectResponse(
        f"/api/v1/admin/module2/workbench/{technology_id}{'?' + query if query else ''}",
        status_code=303,
    )
