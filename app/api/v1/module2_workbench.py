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
from app.core.permission_guard import require_permission
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
    verify_evidence_references,
)
from app.services.module2_operational_widgets import build_technology_readiness_widget
from app.services.module2_default_assumptions import revise_default_assumption
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
    actor_role_code,
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


@router.get("", response_class=HTMLResponse)
async def technology_workbench_list(request: Request, db: DBSession, user: CurrentUser):
    require_permission(user, MODULE2_OWNER_CODE, "VIEW")
    rows = list(await build_technology_list_view(db))
    categories = await list_categories(db)
    category_names = {item.id: item.name for item in categories}
    for row in rows:
        row["category_name"] = category_names.get(row["category_id"], "Без категории")
    status_filter = str(request.query_params.get("status") or "").upper()
    query = str(request.query_params.get("q") or "").strip().lower()
    if status_filter in {item.value for item in TechnologyLifecycle}:
        rows = [item for item in rows if item["status"] == status_filter]
    if query:
        rows = [item for item in rows if query in f"{item['name']} {item['code']} {item['system_code']}".lower()]
    return templates.TemplateResponse(
        request,
        "module2_technology_workbench.html",
        {
            "technologies": rows,
            "categories": tuple(item for item in categories if item.status != "ARCHIVED"),
            "permissions": workbench_permissions(user),
            "status_filter": status_filter,
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
            actor_role_code=actor_role_code(user),
            created_by_user_id=_user_id(user),
        )
        await persist_technology_draft(db, technology)
    except (ValueError, PermissionError, ValidationError, IntegrityError) as exc:
        await db.rollback()
        return _redirect_list(error=_human_error(exc))
    return _redirect_detail(technology.id, notice="Черновик технологии создан.")


@router.get("/categories", response_class=HTMLResponse)
async def technology_categories(request: Request, db: DBSession, user: CurrentUser):
    require_permission(user, MODULE2_OWNER_CODE, "VIEW")
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


@router.get("/{technology_id}", response_class=HTMLResponse)
async def technology_workbench_detail(
    technology_id: uuid.UUID,
    request: Request,
    db: DBSession,
    user: CurrentUser,
):
    require_permission(user, MODULE2_OWNER_CODE, "VIEW")
    technology = await read_technology(db, technology_id)
    if technology is None:
        return _redirect_list(error="Технология не найдена.")
    context = await build_technology_detail_view(db, technology)
    categories = await list_categories(db)
    context["technology_category_options"] = tuple(
        item for item in categories if item.status != "ARCHIVED"
    )
    context["category_code"] = next(
        (item.code for item in categories if item.id == technology.category_id), None
    )
    context.update(
        {
            "permissions": workbench_permissions(user),
            "notice": request.query_params.get("notice"),
            "error": request.query_params.get("error"),
            "active_section": request.query_params.get("section", "general"),
            "atom_topbar_current_block": "Модуль №2: рабочая область технологий",
        }
    )
    return templates.TemplateResponse(request, "module2_technology_detail.html", context)


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

    role_code = actor_role_code(user)
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
    role_code: str,
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
        transition_technology(technology, target, actor_role_code=role_code)
        return f"Статус изменен: {target.value}."
    if action == "save-requirement":
        upsert_draft_requirement(
            technology,
            _requirement_input(form),
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
        component = _required(form, "component")
        entity = _knowledge_entity(technology, component, _required_uuid(form, "item_id"))
        target = TechnologyLifecycle(_required(form, "target"))
        verified = await verify_evidence_references(db, technology.evidence_references)
        common = {
            "technology": technology,
            "evidence_references": technology.evidence_references,
            "actor_role_code": role_code,
            "verified_evidence_reference_ids": verified,
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
    query = urlencode({key: value for key, value in {"notice": notice, "error": error, "section": section}.items() if value})
    return RedirectResponse(
        f"/api/v1/admin/module2/workbench/{technology_id}{'?' + query if query else ''}",
        status_code=303,
    )
