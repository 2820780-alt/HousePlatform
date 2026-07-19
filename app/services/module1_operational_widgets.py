from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.enums import DocumentStatus, DocumentType, MaterialStatus, TaskStatus
from app.models.material import Material
from app.models.material_document import MaterialDocument
from app.models.price_history import PriceHistory
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.user_dashboard_layout import UserDashboardLayout
from app.services.dashboard_widget_payload import build_atom_widget_payload
from app.services.dashboard_widget_registry import get_dashboard_widget_registry_item
from app.services.module1_provider_work_cost_offers import list_work_catalog_options
from app.services.platform_region_registry import PILOT_REGION_CODE
from app.services.role_dashboard_access_profiles import get_role_dashboard_access_profile
from app.services.user_dashboard_layout import (
    add_widget_to_layout,
    normalize_user_dashboard_layout,
    remove_widget_instance_from_layout,
    reorder_widget_instances_in_layout,
    update_widget_instance_in_layout,
)


MODULE1_CODE = "MODULE_01_MATERIAL_HUB"
MODULE1_WIDGET_CODES = (
    "MODULE_01_MATERIALS_REQUIRING_ATTENTION_WIDGET",
    "MODULE_01_MATERIAL_PRICE_RELEVANCE_WIDGET",
    "MODULE_01_DOCUMENTS_REQUIRING_REVIEW_WIDGET",
    "MODULE_01_ANALYZER_STATUS_WIDGET",
    "MODULE_01_WORK_COST_OFFERS_REQUIRING_ATTENTION_WIDGET",
)
WORK_COST_WIDGET_CODE = "MODULE_01_WORK_COST_OFFERS_REQUIRING_ATTENTION_WIDGET"
PLACEMENTS = {"DASHBOARD", "MODULE_OVERVIEW"}
MAX_INSTANCE_COUNT = 24
QUERY_LIMITS = {
    "materials": 500,
    "prices": 1000,
    "documents": 500,
    "tasks": 200,
    "work_costs": 500,
}
FORBIDDEN_SETTING_KEYS = {
    "permission",
    "permissions",
    "allowedRoles",
    "allowedUserIds",
    "ownerUserId",
    "raw",
    "rawData",
    "payload",
    "credentials",
    "password",
    "token",
    "secret",
}

DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    MODULE1_WIDGET_CODES[0]: {"reasons": ["open_quality_issue"], "limit": 5},
    MODULE1_WIDGET_CODES[1]: {"freshnessDays": 60, "mode": "stale", "limit": 5},
    MODULE1_WIDGET_CODES[2]: {"status": "needs_review", "expiryDays": 30, "limit": 5},
    MODULE1_WIDGET_CODES[3]: {"mode": "latest", "limit": 3},
    MODULE1_WIDGET_CODES[4]: {"status": "draft", "expiryDays": 30, "pricingMode": "all", "limit": 5},
}

SETTING_KEYS = {
    MODULE1_WIDGET_CODES[0]: {"region", "materialId", "reasons", "limit"},
    MODULE1_WIDGET_CODES[1]: {"region", "materialId", "freshnessDays", "mode", "limit"},
    MODULE1_WIDGET_CODES[2]: {"documentType", "status", "expiryDays", "limit"},
    MODULE1_WIDGET_CODES[3]: {"sourceId", "mode", "limit"},
    MODULE1_WIDGET_CODES[4]: {
        "workCode",
        "region",
        "status",
        "pricingMode",
        "expiryDays",
        "limit",
    },
}


async def get_module1_widget_layout(
    db: AsyncSession,
    user: Any,
    *,
    create: bool = False,
    active_region_code: str | None = None,
) -> UserDashboardLayout | None:
    result = await db.execute(
        select(UserDashboardLayout)
        .where(
            UserDashboardLayout.user_id == user.id,
            UserDashboardLayout.status == "ACTIVE",
        )
        .order_by(UserDashboardLayout.is_default.desc(), UserDashboardLayout.updated_at.desc())
        .limit(1)
    )
    layout = result.scalar_one_or_none()
    if layout is not None or not create:
        return layout
    layout = UserDashboardLayout(
        user_id=user.id,
        workspace_id=None,
        active_region_code=_clean_optional(active_region_code) or PILOT_REGION_CODE,
        favorite_modules=[],
        widgets=[],
        layout_settings={},
        is_default=True,
        status="ACTIVE",
    )
    db.add(layout)
    await db.flush()
    return layout


async def list_module1_widget_instances(
    db: AsyncSession,
    user: Any,
    *,
    placement: str | None = None,
) -> list[dict[str, Any]]:
    layout = await get_module1_widget_layout(db, user)
    if layout is None:
        return []
    normalized = normalize_user_dashboard_layout(layout, user=user, context=_layout_context(layout, user))
    requested = _validate_placement(placement) if placement else None
    return [
        item
        for item in normalized["widgets"]
        if item["widgetCode"] in MODULE1_WIDGET_CODES
        and item.get("isVisible", True)
        and (requested is None or item.get("placement", "DASHBOARD") == requested)
        and _is_widget_allowed(user, item["widgetCode"])
    ]


async def add_module1_widget_instance(
    db: AsyncSession,
    user: Any,
    *,
    widget_code: str,
    placement: str,
    settings: Mapping[str, Any] | None = None,
    active_region_code: str | None = None,
) -> dict[str, Any]:
    _require_widget_allowed(user, widget_code)
    normalized_settings = validate_module1_widget_settings(widget_code, settings)
    layout = await get_module1_widget_layout(
        db,
        user,
        create=True,
        active_region_code=active_region_code or normalized_settings.get("region"),
    )
    assert layout is not None
    current = normalize_user_dashboard_layout(layout, user=user, context=_layout_context(layout, user))
    module_instances = [item for item in current["widgets"] if item["widgetCode"] in MODULE1_WIDGET_CODES]
    if len(module_instances) >= MAX_INSTANCE_COUNT:
        raise ValidationError("Можно добавить не более 24 виджетов Module №1.")
    updated = add_widget_to_layout(
        current,
        widget_code,
        user=user,
        context=_layout_context(layout, user, action_code="VIEW"),
        placement=_validate_placement(placement),
        user_settings=normalized_settings,
    )
    layout.widgets = updated["widgets"]
    if active_region_code:
        layout.active_region_code = _clean_optional(active_region_code)
    db.add(layout)
    await db.flush()
    return _last_added_instance(current["widgets"], updated["widgets"])


async def update_module1_widget_instance(
    db: AsyncSession,
    user: Any,
    instance_id: str,
    *,
    placement: str | None = None,
    settings: Mapping[str, Any] | None = None,
    position: int | None = None,
    is_visible: bool | None = None,
) -> dict[str, Any]:
    layout = await _required_layout(db, user)
    current = normalize_user_dashboard_layout(layout, user=user, context=_layout_context(layout, user))
    existing = _find_owned_instance(current["widgets"], instance_id)
    _require_widget_allowed(user, existing["widgetCode"])
    normalized_settings = (
        validate_module1_widget_settings(existing["widgetCode"], settings)
        if settings is not None
        else None
    )
    updated = update_widget_instance_in_layout(
        current,
        instance_id,
        user=user,
        placement=_validate_placement(placement) if placement else None,
        user_settings=normalized_settings,
        position=position,
        is_visible=is_visible,
    )
    layout.widgets = updated["widgets"]
    db.add(layout)
    await db.flush()
    return _find_owned_instance(updated["widgets"], instance_id)


async def remove_module1_widget_instance(
    db: AsyncSession,
    user: Any,
    instance_id: str,
) -> None:
    layout = await _required_layout(db, user)
    current = normalize_user_dashboard_layout(layout, user=user, context=_layout_context(layout, user))
    _find_owned_instance(current["widgets"], instance_id)
    updated = remove_widget_instance_from_layout(current, instance_id, user=user)
    layout.widgets = updated["widgets"]
    db.add(layout)
    await db.flush()


async def reorder_module1_widget_instances(
    db: AsyncSession,
    user: Any,
    ordered_instance_ids: list[str],
) -> list[dict[str, Any]]:
    layout = await _required_layout(db, user)
    current = normalize_user_dashboard_layout(layout, user=user, context=_layout_context(layout, user))
    owned = {
        item["instanceId"]
        for item in current["widgets"]
        if item["widgetCode"] in MODULE1_WIDGET_CODES and item.get("instanceId")
    }
    requested = list(dict.fromkeys(str(item) for item in ordered_instance_ids))
    if not set(requested).issubset(owned):
        raise ForbiddenError("Нельзя изменить порядок чужого или неизвестного виджета.")
    updated = reorder_widget_instances_in_layout(current, requested, user=user)
    layout.widgets = updated["widgets"]
    db.add(layout)
    await db.flush()
    return [
        item for item in updated["widgets"]
        if item["widgetCode"] in MODULE1_WIDGET_CODES and item.get("instanceId") in owned
    ]


def validate_module1_widget_settings(
    widget_code: str,
    settings: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if widget_code not in MODULE1_WIDGET_CODES:
        raise ValidationError("Неизвестный тип виджета Module №1.")
    raw = dict(settings or {})
    forbidden = FORBIDDEN_SETTING_KEYS.intersection(raw)
    if forbidden:
        raise ValidationError("Настройки виджета не могут содержать права доступа или технические данные.")
    unknown = set(raw).difference(SETTING_KEYS[widget_code])
    if unknown:
        raise ValidationError(f"Неизвестные параметры виджета: {', '.join(sorted(unknown))}.")
    data = {**DEFAULT_SETTINGS[widget_code], **raw}
    data["limit"] = _choice_int(data.get("limit"), {1, 3, 5, 10}, "limit")
    for key in ("freshnessDays", "expiryDays"):
        if key in data:
            data[key] = _choice_int(data[key], {7, 30, 60, 90}, key)
    for key in ("region", "materialId", "documentType", "sourceId", "workCode"):
        if key in data:
            data[key] = _clean_optional(data[key])
            if data[key] is None:
                data.pop(key)
    if "materialId" in data:
        _uuid(data["materialId"], "materialId")
    if "sourceId" in data:
        _uuid(data["sourceId"], "sourceId")
    if "reasons" in data:
        reasons = data["reasons"] if isinstance(data["reasons"], list) else []
        allowed = {
            "open_quality_issue",
            "no_positive_price",
            "requires_classification",
            "requires_moderation",
            "insufficient_data",
        }
        data["reasons"] = [str(reason) for reason in reasons if str(reason) in allowed] or ["open_quality_issue"]
    _validate_choice(data, "mode", {
        MODULE1_WIDGET_CODES[1]: {"missing", "stale", "current"},
        MODULE1_WIDGET_CODES[3]: {"latest", "source"},
    }.get(widget_code))
    _validate_choice(data, "status", {
        MODULE1_WIDGET_CODES[2]: {"needs_review", "expiring", "expired"},
        MODULE1_WIDGET_CODES[4]: {"draft", "expiring", "inactive"},
    }.get(widget_code))
    _validate_choice(data, "pricingMode", {"all", "fixed", "range"} if widget_code == WORK_COST_WIDGET_CODE else None)
    if "workCode" in data:
        known_work_codes = {str(item["workCode"]) for item in list_work_catalog_options()}
        if data["workCode"] not in known_work_codes:
            raise ValidationError("Выбранная работа отсутствует в нормализованном справочнике.")
    return data


def get_module1_widget_catalog(user: Any) -> list[dict[str, Any]]:
    result = []
    for code in MODULE1_WIDGET_CODES:
        if not _is_widget_allowed(user, code):
            continue
        item = get_dashboard_widget_registry_item(code)
        if not item:
            continue
        result.append({
            "widgetCode": code,
            "title": item.title,
            "description": item.description,
            "defaultSize": item.defaultSize,
            "allowsMultipleInstances": item.allowsMultipleInstances,
            "supportedPlacements": list(item.supportedPlacements),
            "defaultSettings": dict(DEFAULT_SETTINGS[code]),
            "availableSettings": dict(item.availableSettings),
        })
    return result


async def get_module1_widget_configuration_options(
    db: AsyncSession,
    user: Any,
) -> dict[str, Any]:
    catalog = get_module1_widget_catalog(user)
    allowed_codes = {item["widgetCode"] for item in catalog}
    options: dict[str, list[dict[str, str]]] = {
        "materials": [],
        "sources": [],
        "regions": [],
        "documentTypes": [],
        "works": [],
    }
    if not allowed_codes:
        return options

    regions: set[str] = set()
    if allowed_codes.intersection(MODULE1_WIDGET_CODES[:2]):
        materials_result = await db.execute(
            select(Material.id, Material.canonical_name)
            .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
            .order_by(Material.canonical_name.asc())
            .limit(100)
        )
        options["materials"] = [
            {"value": str(material_id), "label": name}
            for material_id, name in materials_result.all()
        ]
        price_regions_result = await db.execute(
            select(PriceHistory.region)
            .where(PriceHistory.region.is_not(None))
            .distinct()
            .order_by(PriceHistory.region.asc())
            .limit(100)
        )
        regions.update(str(value) for value in price_regions_result.scalars().all() if value)

    if MODULE1_WIDGET_CODES[3] in allowed_codes:
        sources_result = await db.execute(
            select(Source.id, Source.name).order_by(Source.name.asc()).limit(100)
        )
        options["sources"] = [
            {"value": str(source_id), "label": name}
            for source_id, name in sources_result.all()
        ]

    if MODULE1_WIDGET_CODES[2] in allowed_codes:
        options["documentTypes"] = [
            {"value": item.value, "label": _document_type_label(item)}
            for item in DocumentType
        ]

    if WORK_COST_WIDGET_CODE in allowed_codes:
        work_regions_statement = select(ProviderWorkCostOffer.region).where(
            ProviderWorkCostOffer.region.is_not(None)
        )
        if _role_code(user) != "ADMIN":
            work_regions_statement = work_regions_statement.where(
                ProviderWorkCostOffer.owner_user_id == user.id
            )
        work_regions_result = await db.execute(
            work_regions_statement.distinct().order_by(ProviderWorkCostOffer.region.asc()).limit(100)
        )
        regions.update(str(value) for value in work_regions_result.scalars().all() if value)
        options["works"] = [
            {"value": item["workCode"], "label": item["workTitle"]}
            for item in list_work_catalog_options()
        ]

    options["regions"] = [{"value": value, "label": value} for value in sorted(regions)]
    return options

async def build_module1_widget_instances(
    db: AsyncSession,
    user: Any,
    *,
    placement: str,
) -> list[dict[str, Any]]:
    instances = await list_module1_widget_instances(db, user, placement=placement)
    if not instances:
        return []
    data = await _load_widget_data(db, user, instances)
    result = []
    for instance in instances:
        code = instance["widgetCode"]
        try:
            settings = validate_module1_widget_settings(code, instance.get("userSettings"))
            payload = _build_payload(code, settings, data)
        except (ValidationError, ValueError, TypeError):
            payload = build_atom_widget_payload(
                widget_code=code,
                source_module_code=MODULE1_CODE,
                title=_widget_title(code),
                status="error",
                empty_state_label="Настройки устарели. Откройте меню виджета и сохраните их заново.",
                primary_value="—",
                primary_label="Требуется настройка",
                icon_key="alert",
            ).to_dict()
        result.append({
            **instance,
            "payload": payload,
            "route": get_dashboard_widget_registry_item(code).routeToSourceModule,
        })
    return result


async def _load_widget_data(
    db: AsyncSession,
    user: Any,
    instances: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    codes = {str(instance["widgetCode"]) for instance in instances}
    data: dict[str, Any] = {}
    if codes.intersection(MODULE1_WIDGET_CODES[:2]):
        result = await db.execute(
            select(Material)
            .options(
                selectinload(Material.quality_issues),
                selectinload(Material.catalog_products),
                selectinload(Material.category),
                selectinload(Material.material_type),
            )
            .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
            .order_by(Material.updated_at.desc())
            .limit(QUERY_LIMITS["materials"])
        )
        data["materials"] = list(result.scalars().unique().all())
    if MODULE1_WIDGET_CODES[1] in codes:
        result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.price > 0)
            .order_by(PriceHistory.collected_at.desc())
            .limit(QUERY_LIMITS["prices"])
        )
        data["prices"] = list(result.scalars().all())
    if MODULE1_WIDGET_CODES[2] in codes:
        result = await db.execute(
            select(MaterialDocument)
            .options(
                joinedload(MaterialDocument.material),
                joinedload(MaterialDocument.manufacturer),
                joinedload(MaterialDocument.source),
            )
            .order_by(MaterialDocument.updated_at.desc())
            .limit(QUERY_LIMITS["documents"])
        )
        data["documents"] = list(result.scalars().unique().all())
    if MODULE1_WIDGET_CODES[3] in codes:
        result = await db.execute(
            select(SourceTask)
            .options(joinedload(SourceTask.source))
            .order_by(SourceTask.created_at.desc())
            .limit(QUERY_LIMITS["tasks"])
        )
        data["tasks"] = list(result.scalars().unique().all())
    if MODULE1_WIDGET_CODES[4] in codes:
        statement = select(ProviderWorkCostOffer).order_by(ProviderWorkCostOffer.updated_at.desc())
        if _role_code(user) != "ADMIN":
            statement = statement.where(ProviderWorkCostOffer.owner_user_id == user.id)
        result = await db.execute(statement.limit(QUERY_LIMITS["work_costs"]))
        data["work_costs"] = list(result.scalars().all())
    return data


def _build_payload(code: str, settings: Mapping[str, Any], data: Mapping[str, Any]) -> dict[str, Any]:
    if code == MODULE1_WIDGET_CODES[0]:
        return _materials_attention_payload(settings, data.get("materials", []))
    if code == MODULE1_WIDGET_CODES[1]:
        return _price_relevance_payload(settings, data.get("materials", []), data.get("prices", []))
    if code == MODULE1_WIDGET_CODES[2]:
        return _documents_payload(settings, data.get("documents", []))
    if code == MODULE1_WIDGET_CODES[3]:
        return _analyzer_payload(settings, data.get("tasks", []))
    return _work_cost_payload(settings, data.get("work_costs", []))


def _materials_attention_payload(settings: Mapping[str, Any], materials: list[Material]) -> dict[str, Any]:
    selected = []
    reasons = set(settings["reasons"])
    for material in materials:
        found = _material_attention_reasons(material, settings.get("region"))
        if settings.get("materialId") and str(material.id) != settings["materialId"]:
            continue
        matching = found.intersection(reasons)
        if matching:
            selected.append((material, matching))
    limit = int(settings["limit"])
    items = [
        {
            "label": material.canonical_name,
            "value": _attention_reason_label(next(iter(sorted(found)))),
            "status": "attention",
        }
        for material, found in selected[:limit]
    ]
    return _payload(
        MODULE1_WIDGET_CODES[0],
        len(selected),
        "Требуют действия",
        items,
        "Материалов, требующих действия, нет.",
        "attention" if selected else "ok",
        "alert",
    )


def _price_relevance_payload(
    settings: Mapping[str, Any],
    materials: list[Material],
    observations: list[PriceHistory],
) -> dict[str, Any]:
    region = settings.get("region")
    filtered = [item for item in observations if not region or item.region == region]
    latest: dict[str, PriceHistory] = {}
    for item in filtered:
        latest.setdefault(str(item.material_id), item)
    cutoff = datetime.utcnow() - timedelta(days=int(settings["freshnessDays"]))
    mode = settings["mode"]
    selected = []
    for material in materials:
        if settings.get("materialId") and str(material.id) != settings["materialId"]:
            continue
        observation = latest.get(str(material.id))
        is_current = bool(observation and observation.collected_at >= cutoff and _positive(observation.price))
        if mode == "missing" and observation is None:
            selected.append((material, observation))
        elif mode == "stale" and observation is not None and not is_current:
            selected.append((material, observation))
        elif mode == "current" and is_current:
            selected.append((material, observation))
    limit = int(settings["limit"])
    items = [
        {
            "label": material.canonical_name,
            "value": _price_observation_label(observation),
            "status": "ok" if mode == "current" else "attention",
        }
        for material, observation in selected[:limit]
    ]
    labels = {"missing": "Без цены", "stale": "Цена устарела", "current": "Цена актуальна"}
    return _payload(
        MODULE1_WIDGET_CODES[1],
        len(selected),
        labels[mode],
        items,
        "Материалов по выбранному условию нет.",
        "ok" if mode == "current" and selected else ("attention" if selected else "info"),
        "price",
    )


def _documents_payload(settings: Mapping[str, Any], documents: list[MaterialDocument]) -> dict[str, Any]:
    today = date.today()
    deadline = today + timedelta(days=int(settings["expiryDays"]))
    mode = settings["status"]
    selected = []
    for document in documents:
        if settings.get("documentType") and document.document_type.value != settings["documentType"]:
            continue
        expired = document.status == DocumentStatus.EXPIRED or bool(document.expiry_date and document.expiry_date < today)
        expiring = bool(document.expiry_date and today <= document.expiry_date <= deadline)
        needs_review = document.status == DocumentStatus.NEEDS_REVIEW
        if (mode == "expired" and expired) or (mode == "expiring" and expiring) or (mode == "needs_review" and needs_review):
            selected.append(document)
    limit = int(settings["limit"])
    items = [
        {
            "label": document.title,
            "value": _document_state_label(document, today),
            "status": "error" if document.status == DocumentStatus.EXPIRED else "attention",
        }
        for document in selected[:limit]
    ]
    return _payload(
        MODULE1_WIDGET_CODES[2],
        len(selected),
        "Требуют проверки",
        items,
        "Документов по выбранному условию нет.",
        "attention" if selected else "ok",
        "document",
    )


def _analyzer_payload(settings: Mapping[str, Any], tasks: list[SourceTask]) -> dict[str, Any]:
    source_id = settings.get("sourceId")
    selected = [task for task in tasks if not source_id or str(task.source_id) == source_id]
    selected = selected[: int(settings["limit"])]
    latest = selected[0] if selected else None
    status = "info"
    if latest and latest.status == TaskStatus.FAILED:
        status = "error"
    elif latest and latest.status in {TaskStatus.COMPLETED}:
        status = "ok"
    elif latest and latest.status in {TaskStatus.NEEDS_REVIEW}:
        status = "attention"
    items = [
        {
            "label": task.source.name if task.source else "Источник не указан",
            "value": _task_status_label(task.status),
            "caption": _format_datetime(task.finished_at or task.started_at or task.created_at),
            "status": "error" if task.status == TaskStatus.FAILED else ("attention" if task.status == TaskStatus.NEEDS_REVIEW else "info"),
        }
        for task in selected
    ]
    return _payload(
        MODULE1_WIDGET_CODES[3],
        _task_status_label(latest.status) if latest else "Нет запусков",
        "Последний запуск",
        items,
        "Запуски анализатора ещё не выполнялись.",
        status,
        "source",
    )


def _work_cost_payload(settings: Mapping[str, Any], offers: list[ProviderWorkCostOffer]) -> dict[str, Any]:
    today = date.today()
    deadline = today + timedelta(days=int(settings["expiryDays"]))
    mode = settings["status"]
    selected = []
    for offer in offers:
        if settings.get("workCode") and offer.work_code != settings["workCode"]:
            continue
        if settings.get("region") and offer.region != settings["region"]:
            continue
        if settings["pricingMode"] != "all" and offer.pricing_mode != settings["pricingMode"]:
            continue
        expiring = bool(offer.valid_until and today <= offer.valid_until <= deadline)
        matches = (
            (mode == "draft" and offer.status == "draft")
            or (mode == "inactive" and offer.status == "inactive")
            or (mode == "expiring" and expiring)
        )
        if matches:
            selected.append(offer)
    limit = int(settings["limit"])
    items = [
        {
            "label": offer.work_code,
            "value": _work_offer_label(offer),
            "caption": offer.region,
            "status": "attention",
        }
        for offer in selected[:limit]
    ]
    return _payload(
        MODULE1_WIDGET_CODES[4],
        len(selected),
        "Требуют внимания",
        items,
        "Предложений по выбранному условию нет.",
        "attention" if selected else "ok",
        "work",
    )


def _payload(
    code: str,
    value: Any,
    label: str,
    items: list[dict[str, Any]],
    empty_label: str,
    status: str,
    icon: str,
) -> dict[str, Any]:
    item = get_dashboard_widget_registry_item(code)
    return build_atom_widget_payload(
        widget_code=code,
        source_module_code=MODULE1_CODE,
        title=item.title if item else code,
        status=status,
        style_variant="operational",
        icon_key=icon,
        empty_state_label=empty_label,
        primary_value=value,
        primary_label=label,
        items=items,
        cta={"label": "Открыть", "href": item.routeToSourceModule} if item and item.routeToSourceModule else None,
        updated_at=datetime.utcnow(),
    ).to_dict()


def _material_attention_reasons(material: Material, region: str | None) -> set[str]:
    reasons: set[str] = set()
    if any(issue.status == "OPEN" for issue in material.quality_issues):
        reasons.add("open_quality_issue")
    positive_products = [
        product for product in material.catalog_products
        if _positive(product.price) and (not region or product.region == region)
    ]
    if not positive_products:
        reasons.add("no_positive_price")
    if material.category_id is None or material.material_type_id is None:
        reasons.add("requires_classification")
    if material.status == MaterialStatus.NEEDS_REVIEW:
        reasons.add("requires_moderation")
    if not material.description or material.base_unit_id is None:
        reasons.add("insufficient_data")
    return reasons


def _is_widget_allowed(user: Any, widget_code: str) -> bool:
    profile = get_role_dashboard_access_profile(_role_code(user))
    if not profile:
        return False
    return (
        MODULE1_CODE in set(profile.get("allowedModuleCodes") or [])
        and "DASHBOARD_PERSONALIZE" in set(profile.get("allowedFeatureCodes") or [])
        and widget_code in set(profile.get("allowedWidgetCodes") or [])
    )


def _require_widget_allowed(user: Any, widget_code: str) -> None:
    if widget_code not in MODULE1_WIDGET_CODES:
        raise ValidationError("Неизвестный тип виджета Module №1.")
    if not _is_widget_allowed(user, widget_code):
        raise ForbiddenError("Виджет недоступен для текущей роли.")


def _layout_context(
    layout: UserDashboardLayout,
    user: Any,
    *,
    action_code: str | None = None,
) -> dict[str, Any]:
    role = _role_code(user)
    active_region_code = layout.active_region_code or PILOT_REGION_CODE
    return {
        "userId": str(user.id),
        "roleCode": role,
        "activeRegionCode": active_region_code,
        "actionCode": action_code,
        "userDashboardLayout": {
            "widgets": list(layout.widgets or []),
            "activeRegionCode": active_region_code,
        },
        "roleDashboardAccessProfile": get_role_dashboard_access_profile(role) or {},
    }

async def _required_layout(db: AsyncSession, user: Any) -> UserDashboardLayout:
    layout = await get_module1_widget_layout(db, user)
    if layout is None:
        raise NotFoundError("Настройки виджетов пользователя не найдены.")
    return layout


def _find_owned_instance(instances: list[dict[str, Any]], instance_id: str) -> dict[str, Any]:
    for item in instances:
        if item.get("instanceId") == instance_id and item["widgetCode"] in MODULE1_WIDGET_CODES:
            return item
    raise NotFoundError("Экземпляр виджета не найден.")


def _last_added_instance(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    old_ids = {item.get("instanceId") for item in before}
    for item in reversed(after):
        if item.get("instanceId") not in old_ids:
            return item
    raise ValidationError("Экземпляр виджета не был добавлен.")


def _validate_placement(value: str | None) -> str:
    placement = str(value or "MODULE_OVERVIEW").upper()
    if placement not in PLACEMENTS:
        raise ValidationError("placement должен быть DASHBOARD или MODULE_OVERVIEW.")
    return placement


def _validate_choice(data: dict[str, Any], key: str, allowed: set[str] | None) -> None:
    if allowed is None or key not in data:
        return
    value = str(data[key])
    if value not in allowed:
        raise ValidationError(f"Недопустимое значение параметра {key}.")
    data[key] = value


def _choice_int(value: Any, allowed: set[int], key: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{key} должен быть числом.") from exc
    if parsed not in allowed:
        raise ValidationError(f"Недопустимое значение параметра {key}.")
    return parsed


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} имеет неверный формат.") from exc


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > 255:
        raise ValidationError("Значение настройки слишком длинное.")
    return text


def _role_code(user: Any) -> str:
    value = getattr(user, "role", None)
    return str(getattr(value, "value", value) or "").upper()


def _positive(value: Any) -> bool:
    try:
        return Decimal(str(value)) > 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def _attention_reason_label(code: str) -> str:
    return {
        "open_quality_issue": "Открыто замечание",
        "no_positive_price": "Нет положительной цены",
        "requires_classification": "Нужна классификация",
        "requires_moderation": "Нужно решение модератора",
        "insufficient_data": "Недостаточно данных",
    }.get(code, "Требуется действие")


def _price_observation_label(observation: PriceHistory | None) -> str:
    if observation is None:
        return "Цена отсутствует"
    return f"{observation.price:g} {observation.currency} · {_format_datetime(observation.collected_at)}"


def _document_type_label(document_type: DocumentType) -> str:
    return {
        DocumentType.CERTIFICATE: "Сертификат",
        DocumentType.DECLARATION: "Декларация",
        DocumentType.FIRE_CERTIFICATE: "Пожарный сертификат",
        DocumentType.SANITARY_CERTIFICATE: "Санитарный сертификат",
        DocumentType.QUALITY_PASSPORT: "Паспорт качества",
        DocumentType.TECH_CARD: "Техническая карта",
        DocumentType.INSTALLATION_GUIDE: "Инструкция по монтажу",
        DocumentType.TYPICAL_NODE: "Типовой узел",
        DocumentType.ALBUM_OF_SOLUTIONS: "Альбом решений",
        DocumentType.BIM_MODEL: "BIM-модель",
        DocumentType.VIDEO_GUIDE: "Видеоинструкция",
        DocumentType.TEST_REPORT: "Протокол испытаний",
        DocumentType.TECHNICAL_APPROVAL: "Техническое свидетельство",
    }[document_type]

def _document_state_label(document: MaterialDocument, today: date) -> str:
    if document.expiry_date and document.expiry_date < today:
        return "Срок истёк"
    if document.expiry_date:
        return f"До {document.expiry_date.strftime('%Y.%m.%d')}"
    return "Требует проверки"


def _task_status_label(status: Any) -> str:
    value = str(getattr(status, "value", status) or "")
    return {
        "PENDING": "В очереди",
        "RUNNING": "Выполняется",
        "COMPLETED": "Завершён",
        "FAILED": "Ошибка",
        "CANCELLED": "Отменён",
        "NEEDS_REVIEW": "Требует проверки",
    }.get(value, "Статус не указан")


def _work_offer_label(offer: ProviderWorkCostOffer) -> str:
    if offer.pricing_mode == "fixed":
        return f"{offer.fixed_amount:g} {offer.currency}/{offer.pricing_unit}"
    return f"{offer.minimum_amount:g}–{offer.maximum_amount:g} {offer.currency}/{offer.pricing_unit}"


def _format_datetime(value: datetime | None) -> str:
    return value.strftime("%Y.%m.%d %H:%M") if value else "не задано"


def _widget_title(code: str) -> str:
    item = get_dashboard_widget_registry_item(code)
    return item.title if item else "Виджет Module №1"
