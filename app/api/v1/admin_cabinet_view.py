from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.api.deps import DBSession
from app.models.catalog_product import CatalogProduct
from app.models.dashboard_profile import DashboardProfile
from app.models.dashboard_widget import DashboardWidget
from app.models.enums import (
    CatalogProductStatus,
    DocumentStatus,
    MatchCandidateStatus,
    MaterialStatus,
    RegionStatus,
    SourceStatus,
    TaskStatus,
)
from app.models.favorite_module import FavoriteModule
from app.models.material import Material
from app.models.material_category import MaterialCategory
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.platform_region import PlatformRegion
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.workspace import Workspace
from app.services.dashboard_auth_adapters import (
    can_access_module,
    can_access_widget,
    can_see_planned_modules,
    can_use_feature,
    get_dashboard_user_context,
)
from app.services.dashboard_cabinet_context import get_current_cabinet_context
from app.services.dashboard_module_registry import (
    get_canonical_module_code,
    get_dashboard_module_registry,
    get_dashboard_module_registry_item,
    get_dashboard_module_registry_item_by_number,
    get_planned_dashboard_modules,
    is_module_available_for_dashboard,
    resolve_module_route,
)
from app.services.dashboard_quick_actions import (
    ATOM_CARD_QUICK_ACTION_LIMIT,
    get_atom_card_quick_action_options,
    get_quick_actions_for_dashboard,
)
from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_CONTEXT, DASHBOARD_ADMIN_SOURCE_MODULE
from app.services.dashboard_widget_config import (
    BOTTOM_WIDGET_GRID,
    RIGHT_RAIL,
    SIZE_GRID_SPANS,
    TOP_WIDGET_GRID,
    dashboard_widget_config_from_model,
)
from app.services.dashboard_widget_payload import atom_widget_payload_from_admin_widget, build_atom_widget_payload
from app.services.dashboard_widget_registry import (
    get_dashboard_widget_registry,
)
from app.services.audit_log_service import record_view_as_role_entered


router = APIRouter(prefix="/admin/cabinet/view", tags=["admin-cabinet-view"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def admin_cabinet_view(request: Request, db: DBSession):
    cards = await _load_module_passports(db)
    center_card = next(card for card in cards if card["number"] == 16)
    preview_role_code = request.query_params.get("preview_role")
    if preview_role_code:
        record_view_as_role_entered(
            actor={"userId": "dev-admin-mock"},
            role_code=preview_role_code,
            reason="Dashboard preview-role mode entered from admin view.",
        )
    dashboard_context = await _load_dashboard_context(
        db,
        cards,
        preview_role_code=preview_role_code,
    )
    satellite_cards = _select_atom_map_cards(cards, dashboard_context["dashboard_user_context"])
    all_atom_cards = _select_all_atom_cards(cards, dashboard_context["dashboard_user_context"])
    selected_atom_module_codes = [card["module_code"] for card in satellite_cards]
    widget_registry = get_dashboard_widget_registry()
    return templates.TemplateResponse(
        request,
        "admin_cabinet_view.html",
        {
            "cards": satellite_cards,
            "all_atom_cards": all_atom_cards,
            "selected_atom_module_codes": selected_atom_module_codes,
            "all_modules_panel": _build_all_modules_panel(
                all_atom_cards,
                selected_atom_module_codes,
                dashboard_context["planned_modules"],
            ),
            "center_card": center_card,
            "module_registry": get_dashboard_module_registry(),
            "widget_registry": widget_registry,
            "widget_settings_groups": _build_widget_settings_groups(
                widget_registry,
                dashboard_context["dashboard_user_context"],
            ),
            **dashboard_context,
        },
    )


def _select_atom_map_cards(cards: list[dict], user_context) -> list[dict]:
    priority_module_codes = [
        "MODULE_12_AI_ASSISTANT",
        "MODULE_01_MATERIAL_HUB",
        "MODULE_02_KNOWLEDGE_BASE",
        "MODULE_05_ESTIMATES",
        "MODULE_04_WORKS_COSTS",
        "MODULE_09_TENDERS",
        "MODULE_08_PROCUREMENT",
        "MODULE_11_ANALYTICS",
    ]
    cards_by_code = {
        card["canonical_module_code"]: card
        for card in cards
        if _can_show_atom_card(card, user_context)
    }
    selected = [cards_by_code[module_code] for module_code in priority_module_codes if module_code in cards_by_code]
    if len(selected) < 6:
        selected_codes = {card["canonical_module_code"] for card in selected}
        selected.extend(
            card
            for card in sorted(cards, key=lambda item: item.get("display_order", item["number"]))
            if card["canonical_module_code"] not in selected_codes and _can_show_atom_card(card, user_context)
        )
    return selected[:8]


def _can_show_atom_card(card: dict, user_context) -> bool:
    if card["number"] == 16:
        return False
    if not card.get("is_visible_on_atom_map", True):
        return False
    if card.get("registry_status") in {"merged", "disabled", "archived", "deprecated"}:
        return False
    if card.get("atom_status") in {"disabled", "archived", "merged"}:
        return False
    if card.get("atom_status") in {"planned", "draft"} and not can_see_planned_modules(user_context):
        return False
    return can_access_module(user_context, card["canonical_module_code"])


def _select_all_atom_cards(cards: list[dict], user_context) -> list[dict]:
    return [
        card
        for card in sorted(cards, key=lambda item: item.get("display_order", item["number"]))
        if _can_show_atom_card(card, user_context)
    ]


def _build_all_modules_panel(
    atom_cards: list[dict],
    selected_module_codes: list[str],
    planned_modules: list[dict],
) -> dict:
    selected_codes = set(selected_module_codes)
    active_modules = [
        {
            "module_code": card["module_code"],
            "canonical_module_code": card["canonical_module_code"],
            "title": card["display_name"],
            "description": card["dashboard_description"],
            "status": card["atom_status"],
            "state": "selected" if card["module_code"] in selected_codes else "hidden",
            "is_selected": card["module_code"] in selected_codes,
            "route": card["route"],
            "passport_href": card["passport_href"],
            "accent": card["accent"],
            "dashboard_icon": card["dashboard_icon"],
            "visual_state": card["visual_state"],
            "state_tone": card["state_tone"],
            "atom_quick_action_options": card.get("atom_quick_action_options", []),
            "atom_quick_actions": card.get("atom_quick_actions", []),
            "display_order": card.get("display_order", card["number"]),
            "is_locked": False,
            "lock_reason": "",
        }
        for card in atom_cards
    ]
    planned_rows = [_module_manager_row_from_registry(module, state="planned") for module in planned_modules]
    system_rows = [
        _module_manager_row_from_registry(module, state="system")
        for module in get_dashboard_module_registry()
        if module["status"] in {"merged", "archived", "deprecated", "disabled"}
    ]
    on_atom_modules = [module for module in active_modules if module["is_selected"]]
    other_modules = [module for module in active_modules if not module["is_selected"]]
    other_modules.extend(planned_rows)
    other_modules.extend(system_rows)
    return {
        "limit": 8,
        "selected_count": len(selected_module_codes),
        "active_modules": active_modules,
        "on_atom_modules": on_atom_modules,
        "other_modules": sorted(other_modules, key=lambda module: (module["display_order"], module["title"])),
    }


def _module_manager_row_from_registry(module: dict, *, state: str) -> dict:
    status = module.get("status", "planned")
    visual_state = {
        "planned": "Планируется",
        "draft": "Проектируется",
        "merged": "Объединен",
        "archived": "Архив",
        "deprecated": "Устаревает",
        "disabled": "Выключен",
    }.get(status, status)
    return {
        "module_code": module["moduleCode"],
        "canonical_module_code": module.get("canonicalModuleCode") or module["moduleCode"],
        "title": module.get("title") or module["moduleCode"],
        "description": module.get("description") or module.get("plannedReason") or "",
        "status": status,
        "state": state,
        "is_selected": False,
        "route": module.get("route"),
        "passport_href": module.get("redirectRoute") or module.get("route") or "#",
        "accent": module.get("color") or "#64748b",
        "dashboard_icon": _module_registry_icon(module.get("icon")),
        "visual_state": visual_state,
        "state_tone": "muted" if status in {"planned", "draft"} else "disabled",
        "atom_quick_action_options": [],
        "atom_quick_actions": [],
        "display_order": module.get("displayOrder", 1000),
        "is_locked": True,
        "lock_reason": (
            "Будущий модуль пока нельзя добавить на атом"
            if status in {"planned", "draft"}
            else "Системная запись не добавляется как активная карточка"
        ),
    }


def _module_registry_icon(icon: str | None) -> str:
    return {
        "database": "▦",
        "file-text": "◇",
        "users": "☻",
        "hammer": "☑",
        "calculator": "≋",
        "check-square": "✓",
        "home": "⌂",
        "package": "⬡",
        "trophy": "♜",
        "store": "▤",
        "chart-no-axes-combined": "▥",
        "sparkles": "✦",
        "clock": "◷",
        "network": "◎",
        "settings": "⚙",
        "shield-check": "◇",
    }.get(icon or "", "◌")


def _build_widget_settings_groups(widget_registry: list[dict], user_context) -> list[dict]:
    module_items = get_dashboard_module_registry()
    modules_by_code = {
        module["moduleCode"]: module
        for module in module_items
    }
    modules_by_code.update({
        get_canonical_module_code(module["moduleCode"]): module
        for module in module_items
    })
    can_preview_future = can_see_planned_modules(user_context)
    groups: dict[str, dict] = {}
    for widget in widget_registry:
        source_code = widget.get("canonicalModuleCode") or widget.get("sourceModuleCode")
        module = modules_by_code.get(source_code) or {}
        status = widget.get("status", "disabled")
        is_future = status in {"planned", "requires_module"}
        is_disabled = status in {"disabled", "requires_permission"}
        if (is_future or is_disabled) and not can_preview_future:
            continue

        feature_code = widget.get("featureCode")
        module_allowed = can_access_module(user_context, source_code)
        feature_allowed = not feature_code or can_use_feature(user_context, feature_code)
        widget_allowed = can_access_widget(user_context, widget["widgetCode"])
        is_working_status = status in {"available", "mock_only"}
        is_allowed = is_working_status and module_allowed and feature_allowed and widget_allowed
        group = groups.setdefault(
            source_code,
            {
                "moduleCode": source_code,
                "title": module.get("title") or source_code,
                "shortTitle": module.get("shortTitle") or module.get("title") or source_code,
                "status": module.get("status", "unknown"),
                "color": module.get("color") or "#18d7f2",
                "displayOrder": module.get("displayOrder", 1000),
                "widgets": [],
            },
        )
        group["widgets"].append({
            **widget,
            "zoneCode": _default_widget_settings_zone(widget),
            "isAllowed": is_allowed,
            "isEnabled": is_allowed and widget.get("isEnabledByDefault", False),
            "canChooseZone": is_allowed and widget.get("type") != "ATOM_MAP",
            "policyNote": _widget_policy_note(
                widget,
                module_allowed=module_allowed,
                feature_allowed=feature_allowed,
                widget_allowed=widget_allowed,
            ),
            "previewPayload": _widget_settings_preview_payload(widget, is_allowed),
        })
    return sorted(
        groups.values(),
        key=lambda group: (group["displayOrder"], group["title"]),
    )


def _default_widget_settings_zone(widget: dict) -> str:
    if widget.get("type") == "KPI":
        return TOP_WIDGET_GRID
    return BOTTOM_WIDGET_GRID


def _widget_policy_note(
    widget: dict,
    *,
    module_allowed: bool,
    feature_allowed: bool,
    widget_allowed: bool,
) -> str:
    status = widget.get("status")
    if status == "planned":
        return "Будущий виджет. Видим администратору как preview, но не включаем в рабочий Dashboard."
    if status == "requires_module":
        return "Включится после активации модуля-источника."
    if status == "disabled":
        return "Системно отключен или заменен другой настройкой."
    if status == "requires_permission" or not widget_allowed:
        return "Недоступен по текущим widgetCode / permissions Module 03."
    if not module_allowed:
        return "Недоступен по moduleCode текущего пользователя."
    if not feature_allowed:
        return "Недоступен по featureCode текущего пользователя."
    if status == "mock_only":
        return "Работает на mock payload до подключения module-owned данных."
    return "Данные и варианты отображения задает модуль-источник."


def _widget_settings_preview_payload(widget: dict, is_allowed: bool) -> dict:
    widget_type = widget.get("type", "STATUS")
    status = "disabled" if not is_allowed else ("attention" if widget.get("status") == "mock_only" else "info")
    payload_kwargs = {
        "widget_code": widget["widgetCode"],
        "source_module_code": widget["sourceModuleCode"],
        "feature_code": widget.get("featureCode"),
        "title": widget["title"],
        "subtitle": widget.get("description") or widget_type,
        "status": status,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if widget_type == "KPI":
        payload_kwargs.update({
            "primary_value": "—" if not is_allowed else "mock",
            "primary_label": "значение",
            "secondary_value": "module payload",
            "secondary_label": "источник",
            "mini_chart": {"type": "sparkline", "points": [6, 9, 7, 11, 10, 14, 13, 16]},
        })
    elif widget_type == "CHART":
        payload_kwargs.update({
            "primary_value": "preview",
            "primary_label": "график",
            "mini_chart": {"type": "bar", "points": [8, 12, 9, 15, 13, 18, 17, 21]},
        })
    elif widget_type in {"LIST", "TASK_QUEUE", "ALERTS"}:
        payload_kwargs.update({
            "items": [
                {"label": "Module-owned payload", "value": widget.get("sourceModuleCode"), "status": status},
                {"label": "Настройки отдаст модуль", "value": widget.get("featureCode") or "summary", "status": "info"},
            ],
        })
    elif widget_type == "ACTIONS":
        payload_kwargs.update({
            "items": [
                {"label": "Действия задает модуль", "value": "0-3", "status": "info"},
            ],
        })
    else:
        payload_kwargs.update({
            "primary_value": widget_type,
            "primary_label": "тип",
            "secondary_value": widget.get("status"),
            "secondary_label": "статус",
        })
    return build_atom_widget_payload(**payload_kwargs).to_dict()


@router.get("/modules/{module_number}", response_class=HTMLResponse)
async def admin_module_passport_view(module_number: int, request: Request, db: DBSession):
    cards = await _load_module_passports(db)
    card = next((item for item in cards if item["number"] == module_number), None)
    if card is None:
        card = next(item for item in cards if item["number"] == 16)
    return templates.TemplateResponse(
        request,
        "admin_module_passport.html",
        {"card": card},
    )


async def _load_module_passports(db: DBSession) -> list[dict]:
    material_total = await _count_model(db, Material)
    document_total = await _count_model(db, MaterialDocument)
    pending_candidates = await _count_pending_candidates(db)
    active_tasks = await _count_active_tasks(db)
    price_points = await _count_model(db, PriceHistory)
    price_dynamics_summary = await _load_price_dynamics_summary(db)
    cards = _module_passports(
        material_total,
        document_total,
        pending_candidates,
        active_tasks,
        price_points,
        price_dynamics_summary,
    )
    return _apply_orbit_layout(cards)


async def _load_dashboard_context(db: DBSession, cards: list[dict], preview_role_code: str | None = None) -> dict:
    material_total = await _count_model(db, Material)
    document_total = await _count_model(db, MaterialDocument)
    pending_candidates = await _count_pending_candidates(db)
    active_tasks = await _count_active_tasks(db)
    active_sources = await _count_where(db, Source, Source.status == SourceStatus.ACTIVE)
    error_sources = await _count_where(db, Source, Source.status == SourceStatus.ERROR)
    failed_tasks = await _count_where(db, SourceTask, SourceTask.status == TaskStatus.FAILED)
    materials_without_category = await _count_where(db, Material, Material.category_id.is_(None))
    materials_on_moderation = await _count_where(db, Material, Material.status == MaterialStatus.NEEDS_REVIEW)
    materials_without_documents = await _count_materials_without_documents(db)
    documents_without_links = await _count_where(db, MaterialDocument, MaterialDocument.material_id.is_(None))
    documents_on_review = await _count_where(db, MaterialDocument, MaterialDocument.status == DocumentStatus.NEEDS_REVIEW)
    expired_documents = await _count_where(db, MaterialDocument, MaterialDocument.status == DocumentStatus.EXPIRED)
    new_documents = await _count_where(
        db,
        MaterialDocument,
        MaterialDocument.created_at >= datetime.utcnow() - timedelta(days=7),
    )
    last_successful_task_at = await _last_successful_source_task_at(db)
    new_materials = await _count_where(
        db,
        Material,
        Material.created_at >= datetime.utcnow() - timedelta(days=7),
    )
    price_summary = await _load_price_dynamics_summary(db)
    price_movers = await _load_price_movers(db)
    source_health = await _load_source_health(db)
    personalization = await _load_personalization_context(db, cards)
    active_region = await _load_active_region_context(db)
    dashboard_user_context = get_dashboard_user_context(
        personalization=personalization,
        active_region=active_region,
        cards=cards,
        preview_role_code=preview_role_code,
    )
    cabinet_context = get_current_cabinet_context(dashboard_user_context)
    current_user_profile_mock = dashboard_user_context.to_template_dict()
    current_cabinet_context_mock = cabinet_context.to_dict()
    _attach_atom_card_quick_actions(cards, dashboard_user_context, current_cabinet_context_mock)

    market_label = price_summary["market"]
    market_is_real = market_label != "нужно больше данных"
    construction_cost = await _estimated_house_cost(db)
    admin_widgets = _admin_widgets(
        material_total=material_total,
        materials_without_category=materials_without_category,
        materials_on_moderation=materials_on_moderation,
        materials_without_documents=materials_without_documents,
        pending_candidates=pending_candidates,
        active_sources=active_sources,
        error_sources=error_sources,
        active_tasks=active_tasks,
        failed_tasks=failed_tasks,
        last_successful_task_at=last_successful_task_at,
        document_total=document_total,
        documents_without_links=documents_without_links,
        documents_on_review=documents_on_review,
        expired_documents=expired_documents,
        new_documents=new_documents,
        price_summary=price_summary,
        price_movers=price_movers,
    )
    for widget in admin_widgets:
        widget["payload"] = atom_widget_payload_from_admin_widget(widget)
    analytics = {
        "construction_cost": f"{construction_cost:,.0f} ₽".replace(",", " "),
        "construction_delta_rub": "+187 432 ₽",
        "construction_delta_percent": "+12,4%",
        "is_mock": True,
        "chart": [12, 18, 25, 22, 29, 34, 31, 38, 45, 42, 51, 58],
        "category_index": [
            {"label": "Стены", "value": "+16,2%", "color": "#2563eb"},
            {"label": "Кровля", "value": "+12,4%", "color": "#f59e0b"},
            {"label": "Фундамент", "value": "+9,8%", "color": "#8b5cf6"},
            {"label": "Отделка", "value": "+8,7%", "color": "#22c55e"},
            {"label": "Инженерия", "value": "+6,3%", "color": "#06b6d4"},
        ],
        "price_growth": price_movers["growth"],
        "price_drop": price_movers["drop"],
    }
    right_rail_widgets = _analytics_right_rail_widgets(analytics)
    right_rail = {
        "zoneCode": RIGHT_RAIL,
        "title": "Правая аналитическая колонка",
        "isEnabled": _is_right_rail_enabled(current_user_profile_mock, current_cabinet_context_mock),
        "widgets": right_rail_widgets[:3],
    }
    bottom_widget_grid = _build_bottom_widget_grid(
        admin_widgets=admin_widgets,
        right_rail_widgets=right_rail_widgets,
        include_right_rail_widgets=False,
        user_context=dashboard_user_context,
    )
    top_kpis = _top_kpis(
        construction_cost=construction_cost,
        market_label=market_label,
        market_is_real=market_is_real,
        price_summary=price_summary,
        new_materials=new_materials,
        material_total=material_total,
        pending_candidates=pending_candidates,
        active_sources=active_sources,
        failed_tasks=failed_tasks,
        active_tasks=active_tasks,
    )
    top_widget_grid = _build_top_widget_grid(top_kpis, dashboard_user_context)

    return {
        "periods": ["Неделя", "Месяц", "Квартал", "Год"],
        "project_options": ["Дом 120 м2", "Дом 160 м2", "Текущий проект"],
        "side_nav": _side_nav(),
        "top_kpis": top_kpis,
        "top_widget_grid": top_widget_grid,
        "analytics": analytics,
        "right_rail": right_rail,
        "bottom_widget_grid": bottom_widget_grid,
        "sources_overview": source_health,
        "quick_actions": get_quick_actions_for_dashboard(dashboard_user_context, current_cabinet_context_mock),
        "atom_card_action_limit": ATOM_CARD_QUICK_ACTION_LIMIT,
        "system_events": _system_events(pending_candidates, failed_tasks, active_tasks, new_materials),
        "admin_widgets": admin_widgets,
        "personalization": personalization,
        "planned_modules": get_planned_dashboard_modules(dashboard_user_context),
        "active_region": active_region,
        "dashboard_user_context": dashboard_user_context,
        "currentCabinetContextMock": current_cabinet_context_mock,
        "cabinetDashboardPreset": current_cabinet_context_mock["cabinetDashboardPreset"],
        "userDashboardLayout": current_user_profile_mock["userDashboardLayout"],
        "currentUserProfileMock": current_user_profile_mock,
        "current_user_profile": current_user_profile_mock,
    }


def _attach_atom_card_quick_actions(cards: list[dict], user_context, cabinet_context: dict) -> None:
    module_action_settings = (
        (cabinet_context.get("cabinetDashboardPreset") or {})
        .get("atomCardActions", {})
        .get("moduleActionCodes", {})
    )
    for card in cards:
        module_code = card.get("canonical_module_code") or card.get("module_code")
        selected_codes = module_action_settings.get(module_code)
        options = get_atom_card_quick_action_options(
            user_context,
            cabinet_context,
            module_code,
            selected_action_codes=selected_codes,
        )
        card["atom_quick_action_options"] = options
        card["atom_quick_actions"] = [action for action in options if action["isSelected"]][:ATOM_CARD_QUICK_ACTION_LIMIT]
        card["atom_quick_action_limit"] = ATOM_CARD_QUICK_ACTION_LIMIT


async def _load_active_region_context(db: DBSession) -> dict:
    result = await db.execute(
        select(PlatformRegion)
        .where(
            PlatformRegion.status == RegionStatus.ACTIVE,
            PlatformRegion.is_active.is_(True),
        )
        .order_by(
            PlatformRegion.is_pilot_region.desc(),
            PlatformRegion.display_order.asc(),
            PlatformRegion.name.asc(),
        )
        .limit(1)
    )
    region = result.scalar_one_or_none()
    if region is None:
        return {
            "code": None,
            "name": "регион не выбран",
            "country": None,
            "is_pilot": False,
            "source": "PlatformRegionRegistry",
            "is_configured": False,
        }
    return {
        "code": region.code,
        "name": region.name,
        "country": region.country,
        "is_pilot": bool(region.is_pilot_region),
        "source": "PlatformRegionRegistry",
        "is_configured": True,
    }


async def _load_personalization_context(db: DBSession, cards: list[dict]) -> dict:
    workspace_result = await db.execute(
        select(Workspace)
        .where(Workspace.status == "ACTIVE")
        .order_by(Workspace.created_at.asc())
        .limit(12)
    )
    workspaces = list(workspace_result.scalars().all())

    profile_result = await db.execute(
        select(DashboardProfile)
        .where(DashboardProfile.status == "ACTIVE")
        .order_by(DashboardProfile.is_default.desc(), DashboardProfile.created_at.asc())
        .limit(1)
    )
    profile = profile_result.scalar_one_or_none()

    favorite_modules: list[str | int] = []
    if profile and profile.workspace_id:
        favorite_result = await db.execute(
            select(FavoriteModule.module_code, FavoriteModule.module_number)
            .where(
                FavoriteModule.workspace_id == profile.workspace_id,
                FavoriteModule.status == "ACTIVE",
            )
            .order_by(FavoriteModule.sort_order.asc())
        )
        favorite_modules = [module_code or int(module_number) for module_code, module_number in favorite_result.all()]
    if not favorite_modules and profile and profile.favorite_modules:
        favorite_modules = [int(number) for number in profile.favorite_modules]
    if not favorite_modules:
        favorite_modules = [1, 14, 16]

    widget_result = await db.execute(
        select(DashboardWidget)
        .where(DashboardWidget.status == "ACTIVE")
        .order_by(DashboardWidget.module_number.asc(), DashboardWidget.title.asc())
        .limit(12)
    )
    widgets = list(widget_result.scalars().all())
    module_by_number = {card["number"]: card for card in cards}
    module_by_code = {card["module_code"]: card for card in cards}
    module_by_canonical_code = {card["canonical_module_code"]: card for card in cards}

    return {
        "active_workspace": workspaces[0].name if workspaces else "Административное пространство",
        "workspaces": [workspace.name for workspace in workspaces] or ["Административное пространство"],
        "active_profile": profile.name if profile else "Администратор: обзор платформы",
        "role": "Администратор",
        "role_options": [
            "Администратор",
            "Модератор данных",
            "Менеджер поставщиков",
            "Аналитик",
        ],
        "favorite_modules": [
            card
            for card in _resolve_favorite_module_cards(
                favorite_modules,
                module_by_number,
                module_by_code,
                module_by_canonical_code,
            )
        ],
        "widgets": [
            _dashboard_widget_context(widget, position=index + 1)
            for index, widget in enumerate(widgets)
        ],
        "is_default_context": True,
    }


def _resolve_favorite_module_cards(
    favorite_modules: list[str | int],
    module_by_number: dict[int, dict],
    module_by_code: dict[str, dict],
    module_by_canonical_code: dict[str, dict],
) -> list[dict]:
    favorite_cards: list[dict] = []
    seen_codes: set[str] = set()
    for favorite in favorite_modules:
        registry_item = (
            get_dashboard_module_registry_item(favorite)
            if isinstance(favorite, str)
            else get_dashboard_module_registry_item_by_number(favorite)
        )
        canonical_code = get_canonical_module_code(
            registry_item.moduleCode if registry_item else favorite if isinstance(favorite, str) else None
        )
        card = None
        if canonical_code:
            card = module_by_canonical_code.get(canonical_code) or module_by_code.get(canonical_code)
        if card is None and isinstance(favorite, int):
            card = module_by_number.get(favorite)
        if card is None:
            continue
        card_code = card["canonical_module_code"]
        if card_code in seen_codes:
            continue
        seen_codes.add(card_code)
        favorite_cards.append(card)
    return favorite_cards


def _dashboard_widget_context(widget: DashboardWidget, position: int = 100) -> dict:
    return dashboard_widget_config_from_model(widget, position=position).to_dict()


def _module_passports(
    material_total: int,
    document_total: int,
    pending_candidates: int,
    active_tasks: int,
    price_points: int,
    price_dynamics_summary: dict,
) -> list[dict]:
    return [
        _passport(
            1,
            "Material Hub",
            "Сбор, обработка и хранение информации",
            "Материалы, источники, карточки товаров, документы, цены и фактический журнал истории цен.",
            "Реализуется",
            "#10d7e8",
            "/api/v1/admin/material-hub/view",
            "Открыть Модуль 1",
            "docs/Modules/Module_01_Materials_v1.2.md",
            "Сайты производителей, ритейл, поставщики, CSV/XLSX.",
            "Канонические материалы, карточки источников, источники, документы, цены и история цен.",
            "Передает данные в Модули 2, 5, 8, 10, 14.",
            [
                {"label": "Всего материалов", "value": material_total},
                {"label": "Всего документов", "value": document_total},
                {"label": "Спорные совпадения", "value": pending_candidates, "alert": pending_candidates > 0},
                {"label": "Активные задачи", "value": active_tasks, "alert": active_tasks > 0},
            ],
        ),
        _passport(
            2,
            "Knowledge Base",
            "Технологии, нормы и правила применения",
            "База знаний технологий строится поверх реальных материалов и документов.",
            "Запланирован",
            "#39d98a",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_02_KnowledgeBase_v1.0.md",
            "Материалы, документы, инструкции и технические карты из Модуля 1.",
            "Технологии, узлы, проверенные нормы расхода, совместимости.",
            "Используется Модулями 5, 6, 7, 12.",
        ),
        _passport(
            3,
            "Accounts",
            "Пользователи, роли и доступы",
            "Управляет учетными записями, ролями и правами доступа к модулям.",
            "Реализуется",
            "#5b7cfa",
            "/api/v1/admin/users-roles/view",
            "Управлять пользователями",
            "docs/Modules/Module_03_Accounts_v1.0.md",
            "Пользователи и роли.",
            "Права доступа, статусы пользователей, связи с кабинетами.",
            "Определяет доступ к Модулям 1, 8, 9, 10, 16.",
        ),
        _passport(
            4,
            "Labor Costs",
            "Трудозатраты и работы",
            "Хранит работы, нормы трудозатрат и параметры выполнения строительных операций.",
            "Запланирован",
            "#f59e0b",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_04_LaborCosts_v1.0.md",
            "Технологии из Модуля 2 и типовые работы.",
            "Нормы трудозатрат и состав работ.",
            "Используется Модулем 5 для смет.",
        ),
        _passport(
            5,
            "Estimates",
            "Формирование смет",
            "Собирает материалы, объемы, работы и цены в расчетную смету.",
            "Запланирован",
            "#22c55e",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_05_Estimates_v1.0.md",
            "Материалы, цены, нормы, объемы, трудозатраты.",
            "Сметы, позиции смет, расчетные стоимости.",
            "Связан с Модулями 1, 2, 4, 7, 8, 14.",
        ),
        _passport(
            6,
            "Estimate Audit",
            "Проверка смет",
            "Проверяет сметы на ошибки, дубли, завышения и несоответствия технологиям.",
            "Запланирован",
            "#ff3b7f",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_06_EstimateAudit_v1.0.md",
            "Сметы, материалы, нормы и цены.",
            "Замечания, риски, расхождения, рекомендации на проверку.",
            "Связан с Модулями 1, 2, 5, 14.",
        ),
        _passport(
            7,
            "Digital Object",
            "Цифровой объект строительства",
            "Хранит структуру дома, объемы, элементы объекта и связь со сметой.",
            "Запланирован",
            "#38bdf8",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_07_DigitalObject_v1.0.md",
            "Проектные данные, конструктивные элементы, объемы.",
            "Цифровую модель объекта и расчетные объемы.",
            "Передает объемы в Модули 5, 8, 11.",
        ),
        _passport(
            8,
            "Procurement",
            "Закупки",
            "Формирует закупочные потребности, сравнивает поставщиков и варианты поставки.",
            "Запланирован",
            "#f97316",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_08_Procurement_v1.0.md",
            "Сметы, материалы, цены, поставщики, наличие.",
            "Закупочные списки, варианты поставки, заявки.",
            "Связан с Модулями 1, 5, 9, 10, 14.",
        ),
        _passport(
            9,
            "Tenders",
            "Тендеры",
            "Позволяет собирать предложения поставщиков и подрядчиков по заданной потребности.",
            "Запланирован",
            "#a855f7",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_09_Tenders_v1.0.md",
            "Закупочные потребности, поставщики, подрядчики.",
            "Тендеры, предложения, сравнение условий.",
            "Связан с Модулями 8, 10, 16.",
        ),
        _passport(
            10,
            "Marketplace",
            "Маркетплейс",
            "Показывает материалы, предложения поставщиков, аналоги и альтернативы.",
            "Запланирован",
            "#14b8a6",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_10_Marketplace_v1.0.md",
            "База материалов, поставщики, цены, рейтинги и отзывы.",
            "Карточки предложений, витрины, подборки поставщиков.",
            "Связан с Модулями 1, 3, 8, 9, 14.",
        ),
        _passport(
            11,
            "Analytics",
            "Общая аналитика платформы",
            "Объединяет срезы по строительству, закупкам, рынку, поставщикам и объектам.",
            "Запланирован",
            "#6366f1",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_11_Analytics_v1.0.md",
            "Данные модулей 1, 5, 7, 8, 9, 10, 14.",
            "Отчеты, срезы, показатели эффективности.",
            "Использует агрегированные данные других модулей.",
        ),
        _passport(
            12,
            "AI Assistant",
            "AI-помощник",
            "Помогает искать, объяснять, классифицировать и предлагать варианты, но не является источником истины.",
            "Запланирован",
            "#ec4899",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_12_AI_Assistant_v1.0.md",
            "Проверенные данные модулей и пользовательские вопросы.",
            "Подсказки, объяснения, варианты действий.",
            "Работает поверх Модулей 1, 2, 5, 6, 11.",
        ),
        _passport(
            13,
            "Audit System",
            "Системный аудит",
            "Фиксирует действия пользователей и изменения важных данных.",
            "Запланирован",
            "#94a3b8",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_13_AuditSystem_v1.0.md",
            "Действия пользователей и системные события.",
            "Журнал аудита, события, след изменений.",
            "Поддерживает все модули платформы.",
        ),
        _passport(
            14,
            "Price Dynamics",
            "История и динамика цен",
            "Анализирует изменение цен по рынку, категориям, группам, материалам и источникам.",
            "Реализуется",
            "#8b5cf6",
            "/api/v1/admin/price-dynamics/view",
            "Открыть Модуль 14",
            "docs/Modules/Module_14_PriceDynamics_v1.0.md",
            "История цен, материалы и источники из Модуля 1.",
            "Аналитические графики и срезы динамики.",
            "Читает Модуль 1, помогает Модулям 5, 8, 11.",
            [
                {"label": "Точек истории", "value": price_points},
                {"label": "Динамика рынка", "value": price_dynamics_summary["market"]},
                {"label": "Категорий с динамикой", "value": price_dynamics_summary["categories"]},
                {"label": "Динамика по группам", "value": "черновая"},
            ],
        ),
        _passport(
            15,
            "Construction Groups",
            "Строительные группы",
            "Классификация поверх категорий материалов: фундамент, коробка, крыша, фасады и другие этапы.",
            "Запланирован",
            "#eab308",
            None,
            "Ожидает реализации",
            "docs/Modules/Module_15_ConstructionGroups_v1.0.md",
            "Категории и материалы из Модуля 1.",
            "Группы и подгруппы строительства.",
            "Используется Модулями 5, 8, 11, 14.",
        ),
        _passport(
            16,
            "Admin Cabinet",
            "Кабинет администратора и модератора",
            "Показывает уведомления, счетчики и переходы в рабочие контуры платформы.",
            "Реализуется",
            "#60a5fa",
            "/api/v1/admin/cabinet/view",
            "Текущий модуль",
            "docs/Modules/Module_16_PersonalCabinet_v1.1.md",
            "Сводные счетчики и публичные данные включенных модулей.",
            "Навигацию, карточки модулей, быстрые переходы.",
            "Не хранит доменные данные других модулей.",
            [
                {"label": "Активные модули", "value": 3},
                {"label": "Материалов", "value": material_total},
                {"label": "Спорные", "value": pending_candidates, "alert": pending_candidates > 0},
                {"label": "Задачи", "value": active_tasks, "alert": active_tasks > 0},
            ],
        ),
    ]


def _side_nav() -> list[dict]:
    return [
        {"label": "Главная", "href": "/api/v1/admin/cabinet/view", "icon": "⌂", "active": True},
        {"label": "База материалов", "href": "/api/v1/admin/material-hub/view", "icon": "▦"},
        {"label": "База знаний", "href": "/api/v1/admin/cabinet/view/modules/2", "icon": "◇"},
        {"label": "История цен", "href": "/api/v1/admin/price-dynamics/view", "icon": "⌁"},
        {"label": "Сметы", "href": "/api/v1/admin/cabinet/view/modules/5", "icon": "≋"},
        {"label": "Работы / проекты", "href": "/api/v1/admin/cabinet/view/modules/7", "icon": "▣"},
        {"label": "Тендеры", "href": "/api/v1/admin/cabinet/view/modules/9", "icon": "♜"},
        {"label": "Поставщики", "href": "/api/v1/admin/cabinet/view/modules/8", "icon": "♢"},
        {"label": "Маркетплейс", "href": "/api/v1/admin/cabinet/view/modules/10", "icon": "▤"},
        {"label": "Аналитика", "href": "/api/v1/admin/cabinet/view/modules/11", "icon": "▥"},
        {"label": "AI-помощник", "href": "/api/v1/admin/cabinet/view/modules/12", "icon": "✦"},
        {"label": "Настройки", "href": "/api/v1/admin/cabinet/view/modules/16", "icon": "⚙"},
        {"label": "Пользователи", "href": "/api/v1/admin/users-roles/view", "icon": "☻"},
        {"label": "Журнал событий", "href": "/api/v1/admin/cabinet/view/modules/13", "icon": "◷"},
    ]


def _admin_widgets(
    *,
    material_total: int,
    materials_without_category: int,
    materials_on_moderation: int,
    materials_without_documents: int,
    pending_candidates: int,
    active_sources: int,
    error_sources: int,
    active_tasks: int,
    failed_tasks: int,
    last_successful_task_at: datetime | None,
    document_total: int,
    documents_without_links: int,
    documents_on_review: int,
    expired_documents: int,
    new_documents: int,
    price_summary: dict,
    price_movers: dict,
) -> list[dict]:
    last_success = _format_datetime_minute(last_successful_task_at) if last_successful_task_at else "нет данных"
    growth_items = price_movers.get("growth", [])
    drop_items = price_movers.get("drop", [])
    return [
        {
            "title": "Material Hub",
            "module_code": "MODULE_01_MATERIAL_HUB",
            "type": "KPI",
            "items": [
                {"label": "Всего материалов", "value": material_total},
                {"label": "Без категории", "value": materials_without_category, "tone": "warn" if materials_without_category else "success"},
                {"label": "На модерации", "value": materials_on_moderation},
                {"label": "Без документов", "value": materials_without_documents},
                {"label": "Ошибки классификации", "value": pending_candidates},
                {"label": "Требуют конвертации", "value": "mock", "mock": True},
            ],
        },
        {
            "title": "Источники",
            "module_code": "MODULE_01_MATERIAL_HUB",
            "type": "STATUS",
            "items": [
                {"label": "Активные источники", "value": active_sources},
                {"label": "Источники с ошибками", "value": error_sources, "tone": "danger" if error_sources else "success"},
                {"label": "Последние задачи анализа", "value": active_tasks},
                {"label": "Ошибки сбора", "value": failed_tasks, "tone": "danger" if failed_tasks else "success"},
                {"label": "Последний успешный сбор", "value": last_success},
            ],
        },
        {
            "title": "Документы",
            "module_code": "MODULE_01_MATERIAL_HUB",
            "type": "LIST",
            "items": [
                {"label": "Всего ссылок / ресурсов", "value": document_total},
                {"label": "Без связей", "value": documents_without_links},
                {"label": "На проверке", "value": documents_on_review},
                {"label": "Просроченные сертификаты", "value": expired_documents},
                {"label": "Новые найденные документы", "value": new_documents},
            ],
        },
        {
            "title": "Analytics · Price Dynamics",
            "module_code": "MODULE_11_ANALYTICS",
            "feature_code": "PRICE_DYNAMICS",
            "legacy_module_code": "MODULE_14_PRICE_HISTORY",
            "type": "CHART",
            "items": [
                {"label": "Изменение типового дома", "value": price_summary.get("market", "нужно больше данных")},
                {"label": "Рост по категориям", "value": "mock", "mock": True},
                {"label": "Топ роста", "value": growth_items[0]["name"] if growth_items else "нет данных"},
                {"label": "Топ снижения", "value": drop_items[0]["name"] if drop_items else "нет данных"},
                {"label": "Аномалии цен", "value": "mock", "mock": True},
                {"label": "Устаревшие цены", "value": "mock", "mock": True},
            ],
        },
        {
            "title": "Пользователи и роли",
            "module_code": "MODULE_03_USERS_ROLES",
            "type": "STATUS",
            "mock": True,
            "items": [
                {"label": "Пользователей всего", "value": "mock", "mock": True},
                {"label": "Активных", "value": "mock", "mock": True},
                {"label": "Ожидают приглашения", "value": "mock", "mock": True},
                {"label": "Изменения прав", "value": "mock", "mock": True},
                {"label": "Последние входы", "value": "mock", "mock": True},
            ],
        },
        {
            "title": "Аудит",
            "module_code": "MODULE_13_AUDIT",
            "type": "ALERTS",
            "mock": True,
            "items": [
                {"label": "Последние действия", "value": "mock", "mock": True},
                {"label": "Критические изменения", "value": "mock", "mock": True},
                {"label": "Ошибки", "value": failed_tasks},
                {"label": "Импорт / экспорт", "value": "mock", "mock": True},
                {"label": "Изменение прав", "value": "mock", "mock": True},
            ],
        },
    ]


def _top_kpis(
    *,
    construction_cost: Decimal,
    market_label: str,
    market_is_real: bool,
    price_summary: dict,
    new_materials: int,
    material_total: int,
    pending_candidates: int,
    active_sources: int,
    failed_tasks: int,
    active_tasks: int,
) -> list[dict]:
    return [
        {
            "label": "Стоимость строительства дома",
            "value": f"{construction_cost:,.0f} ₽".replace(",", " "),
            "delta": "+12,4% за месяц",
            "tone": "success",
            "spark": [18, 20, 19, 23, 22, 27, 25, 31, 29, 36, 33, 41],
            "is_mock": True,
            "sourceModuleCode": "MODULE_11_ANALYTICS",
            "featureCode": "PRICE_DYNAMICS",
        },
        {
            "label": "Изменение стоимости",
            "value": market_label if market_is_real else "нужно больше данных",
            "delta": "по PriceHistory" if market_is_real else "ожидаем историю",
            "tone": "success" if market_is_real and not str(market_label).startswith("-") else "muted",
            "spark": price_summary["spark"],
            "is_mock": not market_is_real,
            "sourceModuleCode": "MODULE_11_ANALYTICS",
            "featureCode": "PRICE_DYNAMICS",
        },
        {
            "label": "Новые материалы",
            "value": new_materials,
            "delta": f"всего: {material_total}",
            "tone": "info",
            "spark": [5, 8, 7, 11, 10, 14, 13, 16, 14, 18, 20, 22],
            "sourceModuleCode": "MODULE_01_MATERIAL_HUB",
        },
        {
            "label": "Материалы на модерации",
            "value": pending_candidates,
            "delta": "требуют решения",
            "tone": "warn" if pending_candidates else "success",
            "spark": [2, 4, 3, 5, 7, 6, 8, 7, 9, 8, 10, 11],
            "sourceModuleCode": "MODULE_01_MATERIAL_HUB",
        },
        {
            "label": "Активные источники",
            "value": active_sources,
            "delta": "готовы к сбору",
            "tone": "success",
            "spark": [7, 8, 9, 9, 10, 10, 11, 11, 12, 12, 12, active_sources],
            "sourceModuleCode": "MODULE_01_MATERIAL_HUB",
        },
        {
            "label": "Ошибки сбора",
            "value": failed_tasks,
            "delta": "по задачам анализа",
            "tone": "danger" if failed_tasks else "success",
            "spark": [0, 1, 0, 2, 1, 0, 1, 2, 1, 1, 0, failed_tasks],
            "sourceModuleCode": "MODULE_01_MATERIAL_HUB",
        },
        {
            "label": "Активные задачи",
            "value": active_tasks,
            "delta": "в очереди и работе",
            "tone": "info" if active_tasks else "success",
            "spark": [0, 1, 1, 2, 1, 3, 2, 2, 4, 3, 2, active_tasks],
            "sourceModuleCode": "MODULE_01_MATERIAL_HUB",
        },
    ]


def _build_top_widget_grid(top_kpis: list[dict], user_context) -> dict:
    visible_kpis = [
        kpi
        for kpi in top_kpis
        if _can_show_widget_source(kpi.get("sourceModuleCode"), kpi.get("featureCode"), user_context)
    ][:6]
    widgets = [
        _widget_zone_item(
            build_atom_widget_payload(
                widget_code=f"{kpi.get('sourceModuleCode', 'DASHBOARD')}.KPI.{_slugify(kpi['label'])}",
                source_module_code=kpi.get("sourceModuleCode", DASHBOARD_ADMIN_SOURCE_MODULE),
                feature_code=kpi.get("featureCode"),
                title=kpi["label"],
                subtitle="KPI",
                status=_payload_status_from_tone(kpi.get("tone")),
                primary_value=kpi["value"],
                primary_label=kpi["label"],
                secondary_value=kpi.get("delta"),
                secondary_label="динамика",
                mini_chart={"type": "sparkline", "points": kpi.get("spark") or []},
            ).to_dict(),
            size="medium",
            zone_code=TOP_WIDGET_GRID,
            order=index + 1,
            grid_span=_equal_grid_span(len(visible_kpis)),
        )
        for index, kpi in enumerate(visible_kpis)
    ]
    return {
        "zoneCode": TOP_WIDGET_GRID,
        "title": "Верхние виджеты",
        "widgets": widgets,
        "hiddenCount": max(0, len(top_kpis) - len(widgets)),
        "maxVisibleWidgets": 6,
    }


def _analytics_right_rail_widgets(analytics: dict) -> list[dict]:
    construction_payload = build_atom_widget_payload(
        widget_code="MODULE_11_ANALYTICS.PRICE_DYNAMICS.construction-cost",
        source_module_code="MODULE_11_ANALYTICS",
        feature_code="PRICE_DYNAMICS",
        title="Изменение стоимости строительства",
        subtitle="Analytics mock adapter",
        status="info",
        primary_value=analytics["construction_delta_rub"],
        primary_label="изменение",
        secondary_value=analytics["construction_delta_percent"],
        secondary_label="за период",
        trend={"direction": "up", "value": analytics["construction_delta_percent"], "label": "за период"},
        mini_chart={"type": "bar", "points": analytics["chart"]},
        cta={
            "label": "Открыть аналитику",
            "route": "/modules/analytics?section=price-dynamics",
            "actionCode": "VIEW",
        },
    ).to_dict()
    category_payload = build_atom_widget_payload(
        widget_code="MODULE_11_ANALYTICS.PRICE_DYNAMICS.category-index",
        source_module_code="MODULE_11_ANALYTICS",
        feature_code="PRICE_DYNAMICS",
        title="Индекс стоимости по категориям",
        subtitle="Analytics mock adapter",
        status="info",
        items=[
            {"label": row["label"], "value": row["value"], "status": "info"}
            for row in analytics["category_index"]
        ],
    ).to_dict()
    movers_payload = build_atom_widget_payload(
        widget_code="MODULE_11_ANALYTICS.PRICE_DYNAMICS.price-movers",
        source_module_code="MODULE_11_ANALYTICS",
        feature_code="PRICE_DYNAMICS",
        title="Материалы с изменением цены",
        subtitle="Analytics mock adapter",
        status="attention",
        items=[
            {"label": item["name"], "value": item["label"], "status": "attention"}
            for item in analytics["price_growth"][:3]
        ] + [
            {"label": item["name"], "value": item["label"], "status": "ok"}
            for item in analytics["price_drop"][:2]
        ],
    ).to_dict()
    return [
        _widget_zone_item(construction_payload, size="large", zone_code=RIGHT_RAIL, order=1),
        _widget_zone_item(category_payload, size="medium", zone_code=RIGHT_RAIL, order=2),
        _widget_zone_item(movers_payload, size="medium", zone_code=RIGHT_RAIL, order=3),
    ]


def _build_bottom_widget_grid(
    *,
    admin_widgets: list[dict],
    right_rail_widgets: list[dict],
    include_right_rail_widgets: bool,
    user_context,
) -> dict:
    admin_zone_items = [
        _widget_zone_item(widget["payload"], size=_bottom_widget_size(index), zone_code=BOTTOM_WIDGET_GRID, order=index + 1)
        for index, widget in enumerate(admin_widgets)
    ]
    widgets = admin_zone_items
    if include_right_rail_widgets:
        widgets = right_rail_widgets + widgets
    widgets = [
        widget
        for widget in widgets
        if _can_show_widget_source(widget["sourceModuleCode"], widget.get("featureCode"), user_context)
    ]
    visible_widgets = widgets[:6]
    equal_span = _equal_grid_span(len(visible_widgets))
    visible_widgets = [dict(widget, gridSpan=equal_span) for widget in visible_widgets]
    return {
        "zoneCode": BOTTOM_WIDGET_GRID,
        "title": "Нижние виджеты",
        "widgets": visible_widgets,
        "hiddenCount": max(0, len(widgets) - len(visible_widgets)),
        "maxVisibleWidgets": 6,
    }


def _can_show_widget_source(source_module_code: str | None, feature_code: str | None, user_context) -> bool:
    if source_module_code and not can_access_module(user_context, source_module_code):
        return False
    if feature_code and not can_use_feature(user_context, feature_code):
        return False
    return True


def _widget_zone_item(payload: dict, *, size: str, zone_code: str, order: int, grid_span: int | None = None) -> dict:
    normalized_size = size if size in SIZE_GRID_SPANS else "medium"
    return {
        "widgetCode": payload["widgetCode"],
        "sourceModuleCode": payload["sourceModuleCode"],
        "featureCode": payload.get("featureCode"),
        "zoneCode": zone_code,
        "size": normalized_size,
        "gridSpan": grid_span or SIZE_GRID_SPANS[normalized_size],
        "order": order,
        "isVisible": True,
        "payload": payload,
    }


def _bottom_widget_size(index: int) -> str:
    if index < 4:
        return "small"
    if index < 6:
        return "medium"
    return "large"


def _equal_grid_span(widget_count: int) -> int:
    if widget_count <= 0:
        return 12
    return max(2, 12 // min(widget_count, 6))


def _payload_status_from_tone(tone: str | None) -> str:
    return {
        "success": "ok",
        "info": "info",
        "warn": "attention",
        "danger": "error",
        "muted": "disabled",
    }.get(tone, "info")


def _slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "widget"


def _is_right_rail_enabled(user_layout: dict, cabinet_context: dict) -> bool:
    zones = (user_layout.get("userDashboardLayout") or user_layout.get("dashboardLayout") or {}).get("zones") or {}
    user_zone = zones.get(RIGHT_RAIL)
    if isinstance(user_zone, dict) and "isEnabled" in user_zone:
        return bool(user_zone["isEnabled"])
    preset_zones = (cabinet_context.get("cabinetDashboardPreset") or {}).get("widgetZones") or {}
    role_code = _dashboard_effective_role_code(user_layout)
    allowed_role_codes = set(preset_zones.get("rightRailRoleCodes") or [])
    if role_code in allowed_role_codes:
        return True
    if "rightRailEnabled" in preset_zones:
        return bool(preset_zones["rightRailEnabled"])
    return preset_zones.get("analytics") == RIGHT_RAIL


def _dashboard_effective_role_code(user_layout: dict) -> str | None:
    layout = user_layout.get("userDashboardLayout") or user_layout.get("dashboardLayout") or {}
    zones = layout.get("zones") or {}
    right_rail_zone = zones.get(RIGHT_RAIL) if isinstance(zones, dict) else {}
    if isinstance(right_rail_zone, dict) and right_rail_zone.get("previewRoleCode"):
        return right_rail_zone["previewRoleCode"]
    return layout.get("previewRoleCode") or user_layout.get("previewRoleCode") or user_layout.get("roleCode")


def _system_events(pending_candidates: int, failed_tasks: int, active_tasks: int, new_materials: int) -> list[dict]:
    events = []
    if pending_candidates:
        events.append({"tone": "warn", "title": f"{pending_candidates} спорных совпадений", "note": "требуется решение модератора"})
    if failed_tasks:
        events.append({"tone": "danger", "title": f"{failed_tasks} ошибок сбора", "note": "проверь задачи анализа"})
    if active_tasks:
        events.append({"tone": "info", "title": f"{active_tasks} активных задач", "note": "сбор или импорт выполняется"})
    if new_materials:
        events.append({"tone": "success", "title": f"{new_materials} новых материалов", "note": "за последние 7 дней"})
    if not events:
        events.append({"tone": "success", "title": "Критичных уведомлений нет", "note": "система работает штатно"})
    return events[:4]


def _passport(
    number: int,
    name: str,
    subtitle: str,
    description: str,
    status: str,
    accent: str,
    href: str | None,
    action: str,
    document: str,
    reads: str,
    writes: str,
    connections: str,
    metrics: list[dict] | None = None,
) -> dict:
    display_names = {
        1: "База материалов",
        2: "База знаний",
        3: "Аккаунты",
        4: "Работы",
        5: "Сметы",
        6: "Проверка смет",
        7: "Объект",
        8: "Закупки",
        9: "Тендеры",
        10: "Маркетплейс",
        11: "Аналитика",
        12: "AI-помощник",
        13: "Аудит",
        14: "Динамика цен",
        15: "Группы стройки",
        16: "Кабинет",
    }
    dashboard_descriptions = {
        1: "Сбор и хранение данных",
        2: "Технологии, нормы и правила",
        3: "Пользователи и доступы",
        4: "Работы и трудозатраты",
        5: "Расчет стоимости работ",
        6: "Контроль ошибок в сметах",
        7: "Дом, объемы и элементы",
        8: "Поставки и комплектация",
        9: "Сбор предложений рынка",
        10: "Витрина материалов и цен",
        11: "Сводные показатели платформы",
        12: "Помощь в поиске и анализе",
        13: "История действий и изменений",
        14: "История и изменение стоимости",
        15: "Этапы и части строительства",
        16: "Административный контур",
    }
    dashboard_icons = {
        1: "▦",
        2: "◇",
        3: "☻",
        4: "⚒",
        5: "≋",
        6: "✓",
        7: "▣",
        8: "♢",
        9: "♜",
        10: "▤",
        11: "▥",
        12: "✦",
        13: "◷",
        14: "⌁",
        15: "◎",
        16: "⚙",
    }
    registry_item = get_dashboard_module_registry_item_by_number(number)
    dashboard_metrics = metrics or []
    events = _module_events(number, dashboard_metrics)
    registry_status = registry_item.status if registry_item else "active"
    implemented = bool(href) and registry_status not in {"planned", "draft", "disabled", "archived", "merged", "deprecated"}
    module_code = registry_item.moduleCode if registry_item else f"MODULE_{number:02d}"
    canonical_module_code = get_canonical_module_code(module_code) or module_code
    context_code = DASHBOARD_ADMIN_CONTEXT if number == 16 else None
    kpis = dashboard_metrics[:2]
    atom_status = registry_status if registry_status in {"merged", "deprecated"} else _mock_atom_status(number, implemented, events)
    atom_indicators = _module_indicators(number, dashboard_metrics, events, atom_status, status)
    resolved_route = resolve_module_route(module_code)
    is_available_for_dashboard = is_module_available_for_dashboard(module_code)
    visual_state_labels = {
        "normal": "Штатно",
        "active": "Работает",
        "planned": "Планируется",
        "draft": "Черновик",
        "disabled": "Отключен",
        "error": "Ошибка",
        "attention": "Требует внимания",
        "archived": "Архив",
        "merged": "Объединен",
        "deprecated": "Устаревает",
    }
    return {
        "number": number,
        "registry_id": registry_item.id if registry_item else None,
        "module_code": module_code,
        "canonical_module_code": canonical_module_code,
        "context_code": context_code,
        "feature_codes": registry_item.featureCodes if registry_item else [],
        "expected_feature_codes": registry_item.expectedFeatureCodes if registry_item else [],
        "legacy_codes": registry_item.legacyCodes if registry_item else [],
        "legacy_number": registry_item.legacyNumber if registry_item else number,
        "display_number": registry_item.displayNumber if registry_item else number,
        "visual_number": registry_item.visualNumber if registry_item else number,
        "display_order": registry_item.displayOrder if registry_item else number * 10,
        "registry_status": registry_status,
        "merged_into_module_code": registry_item.mergedIntoModuleCode if registry_item else None,
        "redirect_route": registry_item.redirectRoute if registry_item else None,
        "is_visible_in_sidebar": registry_item.isVisibleInSidebar if registry_item else True,
        "is_visible_on_atom_map": registry_item.isVisibleOnAtomMap if registry_item else True,
        "is_available_for_dashboard": is_available_for_dashboard,
        "title": f"Dashboard · {name}" if context_code else f"Модуль {number} · {name}",
        "module_name": name,
        "display_name": display_names.get(number, name),
        "dashboard_description": dashboard_descriptions.get(number, subtitle),
        "dashboard_icon": dashboard_icons.get(number, "◌"),
        "visual_state": visual_state_labels.get(atom_status, "Штатно"),
        "atom_status": atom_status,
        "state_tone": _atom_state_tone(atom_status),
        "atom_indicators": atom_indicators,
        "is_visible": True,
        "is_favorite": number in {1, 2, 3, 5, 8, 9, 11, 12},
        "kpi1": f"{kpis[0]['label']}: {kpis[0]['value']}" if len(kpis) > 0 else None,
        "kpi2": f"{kpis[1]['label']}: {kpis[1]['value']}" if len(kpis) > 1 else None,
        "subtitle": subtitle,
        "description": description,
        "status": status,
        "accent": accent,
        "color": accent,
        "href": href,
        "route": href or resolved_route or f"/api/v1/admin/cabinet/view/modules/{number}",
        "action": action,
        "document": document,
        "reads": reads,
        "writes": writes,
        "connections": connections,
        "metrics": metrics or [
            {"label": "Статус", "value": status},
            {"label": "Документ", "value": document.split("/")[-1]},
        ],
        "dashboard_metrics": dashboard_metrics[:4],
        "events": events,
        "implemented": implemented,
        "href": href or resolved_route or f"/api/v1/admin/cabinet/view/modules/{number}",
        "passport_href": f"/api/v1/admin/cabinet/view/modules/{number}",
    }


def _mock_atom_status(number: int, implemented: bool, events: list[dict]) -> str:
    if number == 14:
        return "merged"
    if any(event.get("kind") == "error" for event in events):
        return "error"
    if any(event.get("kind") in {"warning", "active"} for event in events):
        return "attention"
    if not implemented:
        return "planned"
    return "active"


def _atom_state_tone(status: str) -> str:
    if status == "error":
        return "danger"
    if status == "attention":
        return "warn"
    if status in {"planned", "draft", "merged", "deprecated"}:
        return "muted"
    if status in {"disabled", "archived"}:
        return "disabled"
    return "success"


def _module_indicators(
    number: int,
    metrics: list[dict],
    events: list[dict],
    atom_status: str,
    fallback_status: str,
) -> list[dict]:
    adapted = _atom_card_summary_indicators(number, metrics, events)
    if adapted:
        return adapted[:3]

    tone_by_event = {
        "error": "danger",
        "warning": "warn",
        "active": "info",
        "info": "info",
        "trend": "info",
    }
    icon_by_tone = {
        "danger": "✖",
        "warn": "⚠",
        "info": "•",
        "success": "✓",
        "future": "◇",
        "muted": "·",
    }
    indicators: list[dict] = []

    for event in events:
        tone = tone_by_event.get(event.get("kind"), "info")
        label = str(event.get("label", "событие"))
        value = event.get("value")
        text = f"{label}: {value}" if value not in (None, "") else label
        indicators.append({"tone": tone, "icon": icon_by_tone[tone], "text": text})

    for metric in metrics:
        if len(indicators) >= 3:
            break
        label = str(metric.get("label", "показатель"))
        value = metric.get("value")
        tone = "warn" if metric.get("alert") else "info"
        if number in {2, 7, 13} and not metric.get("alert"):
            tone = "success"
        indicators.append({
            "tone": tone,
            "icon": icon_by_tone[tone],
            "text": f"{label}: {value}" if value not in (None, "") else label,
        })

    if not indicators:
        tone = _atom_state_tone(atom_status)
        if tone == "disabled":
            tone = "muted"
        indicators.append({
            "tone": tone,
            "icon": icon_by_tone.get(tone, "·"),
            "text": fallback_status,
        })

    if atom_status in {"planned", "draft"}:
        indicators = [{"tone": "future", "icon": "◇", "text": "планируется"}] + indicators
    elif atom_status in {"disabled", "archived", "merged", "deprecated"}:
        indicators = [{"tone": "muted", "icon": "·", "text": atom_status}] + indicators

    return indicators[:3]


def _atom_card_summary_indicators(number: int, metrics: list[dict], events: list[dict]) -> list[dict]:
    metric_map = {str(metric.get("label", "")).lower(): metric.get("value") for metric in metrics}

    def metric(label_part: str, default=None):
        for label, value in metric_map.items():
            if label_part.lower() in label:
                return value
        return default

    def has_event(kind: str) -> bool:
        return any(event.get("kind") == kind for event in events)

    if number == 1:
        total = metric("всего материалов", metric("всего", 0))
        pending = metric("спорные", metric("без категории", 0))
        active = metric("активные", 0)
        error_event = next((event for event in events if event.get("kind") == "error"), None)
        return _compact_indicators([
            {"tone": "info", "icon": "•", "text": f"{total} материалов"},
            {"tone": "warn", "icon": "⚠", "text": f"{pending} на проверке"} if pending else None,
            {"tone": "danger", "icon": "✖", "text": f"{error_event.get('value')} ошибки"} if error_event else None,
            {"tone": "info", "icon": "•", "text": f"{active} задач сбора"} if active else None,
        ])

    if number == 5:
        return [
            {"tone": "future", "icon": "◇", "text": "сметы планируются"},
            {"tone": "info", "icon": "₽", "text": "расчет после Module 5"},
            {"tone": "muted", "icon": "·", "text": "данные не подключены"},
        ]

    if number == 7:
        return [
            {"tone": "future", "icon": "◇", "text": "образ объекта планируется"},
            {"tone": "success", "icon": "✓", "text": "структура готовится"},
            {"tone": "warn", "icon": "⚠", "text": "объемы не подключены"},
        ]

    if number == 8:
        return [
            {"tone": "future", "icon": "◇", "text": "закупки планируются"},
            {"tone": "info", "icon": "•", "text": "КП после Module 8"},
            {"tone": "muted", "icon": "·", "text": "заявок нет"},
        ]

    if number == 9:
        return [
            {"tone": "future", "icon": "◇", "text": "тендеры планируются"},
            {"tone": "info", "icon": "•", "text": "предложения позже"},
            {"tone": "muted", "icon": "·", "text": "нет активных торгов"},
        ]

    if number == 11:
        market = metric("динамика рынка", None)
        categories = metric("категорий", None)
        return _compact_indicators([
            {"tone": "info", "icon": "↗", "text": f"стоимость {market}"} if market else {"tone": "muted", "icon": "·", "text": "нет динамики"},
            {"tone": "info", "icon": "•", "text": f"{categories} категорий"} if categories else None,
            {"tone": "warn", "icon": "⚠", "text": "mock-аналитика"},
        ])

    if number == 12:
        return [
            {"tone": "future", "icon": "◇", "text": "AI планируется"},
            {"tone": "info", "icon": "•", "text": "рекомендации позже"},
            {"tone": "muted", "icon": "·", "text": "нет активных подсказок"},
        ]

    if number == 13:
        return [
            {"tone": "future", "icon": "◇", "text": "аудит планируется"},
            {"tone": "success", "icon": "✓", "text": "журнал готовится"},
            {"tone": "muted", "icon": "·", "text": "событий нет"},
        ]

    if number == 16:
        pending = metric("спорные", 0)
        tasks = metric("задачи", 0)
        return _compact_indicators([
            {"tone": "success", "icon": "✓", "text": "кабинет активен"},
            {"tone": "warn", "icon": "⚠", "text": f"{pending} на проверке"} if pending else None,
            {"tone": "info", "icon": "•", "text": f"{tasks} задач"} if tasks else None,
        ])

    if has_event("error"):
        return [{"tone": "danger", "icon": "✖", "text": "есть ошибки"}]
    return []


def _compact_indicators(items: list[dict | None]) -> list[dict]:
    return [item for item in items if item][:3]


def _module_events(number: int, metrics: list[dict]) -> list[dict]:
    by_label = {str(metric.get("label", "")).lower(): metric for metric in metrics}

    def metric_value(label_part: str, default=0):
        for label, metric in by_label.items():
            if label_part.lower() in label:
                return metric.get("value", default)
        return default

    if number == 1:
        pending = metric_value("спорные", 0)
        active = metric_value("активные", 0)
        events = []
        if pending:
            events.append({"kind": "warning", "label": "спорные", "value": pending})
        if active:
            events.append({"kind": "active", "label": "задачи", "value": active})
        return events

    if number == 14:
        points = metric_value("точек", 0)
        market = metric_value("рынка", "")
        events = []
        if points:
            events.append({"kind": "info", "label": "история", "value": points})
        if market:
            events.append({"kind": "trend", "label": "рынок", "value": market})
        return events

    if number == 16:
        pending = metric_value("спорные", 0)
        active_tasks = metric_value("задачи", 0)
        events = []
        if pending:
            events.append({"kind": "warning", "label": "спорные", "value": pending})
        if active_tasks:
            events.append({"kind": "active", "label": "задачи", "value": active_tasks})
        return events

    return []


def _apply_orbit_layout(cards: list[dict]) -> list[dict]:
    layout = {
        1: ("50%", "14%", "250px", "90deg", 1, 1),
        2: ("80%", "25%", "318px", "140deg", 2, 2),
        3: ("83%", "50%", "326px", "180deg", 2, 3),
        4: ("80%", "75%", "330px", "220deg", 3, 4),
        5: ("86%", "48%", "326px", "180deg", 2, 3),
        6: ("70%", "88%", "250px", "238deg", 3, 6),
        7: ("50%", "92%", "280px", "270deg", 3, 7),
        8: ("20%", "75%", "318px", "320deg", 2, 4),
        9: ("50%", "88%", "326px", "270deg", 2, 6),
        10: ("9%", "50%", "330px", "0deg", 3, 10),
        11: ("18%", "48%", "318px", "0deg", 2, 5),
        12: ("20%", "20%", "250px", "40deg", 1, 6),
        13: ("31%", "34%", "190px", "30deg", 1, 13),
        14: ("69%", "34%", "190px", "150deg", 1, 14),
        15: ("69%", "66%", "190px", "210deg", 1, 15),
    }
    link_map = {
        1: {
            "node": (50, 27),
            "inner_path": "M 50 27 L 50 14",
        },
        2: {
            "node": (69, 31),
            "inner_path": "M 69 31 L 80 25",
        },
        3: {
            "node": (86, 50),
            "inner_path": "M 86 50 L 83 50",
        },
        4: {
            "node": (69, 69),
            "inner_path": "M 69 69 L 80 75",
        },
        5: {
            "node": (86, 50),
            "inner_path": "M 86 50 L 86 48",
        },
        6: {
            "node": (60, 73),
            "inner_path": "M 60 73 L 70 88",
        },
        7: {
            "node": (50, 73),
            "inner_path": "M 50 73 L 50 92",
        },
        8: {
            "node": (31, 69),
            "inner_path": "M 31 69 L 20 75",
        },
        9: {
            "node": (50, 73),
            "inner_path": "M 50 73 L 50 88",
        },
        10: {
            "node": (14, 50),
            "inner_path": "M 14 50 L 9 50",
        },
        11: {
            "node": (14, 50),
            "inner_path": "M 14 50 L 18 48",
        },
        12: {
            "node": (31, 31),
            "inner_path": "M 31 31 L 20 20",
        },
        13: {
            "node": (32, 36),
            "inner_path": "M 32 36 L 31 34",
        },
        15: {
            "node": (68, 64),
            "inner_path": "M 68 64 L 69 66",
        },
    }
    for card in cards:
        x, y, link_width, link_angle, orbit_level, position = layout.get(
            card["number"],
            ("50%", "50%", "180px", "0deg", 1, card["number"]),
        )
        card["orbit"] = {
            "x": x,
            "y": y,
            "link_width": link_width,
            "link_angle": link_angle,
        }
        card["orbit_level"] = orbit_level
        card["position"] = position
        card["atom_link"] = link_map.get(
            card["number"],
            {
                "node": (50, 50),
                "inner_path": "M 50 50 C 50 50, 50 50, 50 50",
            },
        )
    return cards


async def _count_model(db: DBSession, model) -> int:
    result = await db.execute(select(func.count(model.id)))
    return result.scalar() or 0


async def _count_where(db: DBSession, model, condition) -> int:
    result = await db.execute(select(func.count(model.id)).where(condition))
    return result.scalar() or 0


async def _count_pending_candidates(db: DBSession) -> int:
    return await _count_where(
        db,
        MaterialMatchCandidate,
        MaterialMatchCandidate.status.in_([
            MatchCandidateStatus.OPEN,
            MatchCandidateStatus.NEEDS_REVIEW,
        ]),
    )


async def _count_active_tasks(db: DBSession) -> int:
    return await _count_where(
        db,
        SourceTask,
        SourceTask.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]),
    )


async def _count_materials_without_documents(db: DBSession) -> int:
    result = await db.execute(
        select(func.count(Material.id))
        .outerjoin(MaterialDocument, MaterialDocument.material_id == Material.id)
        .where(MaterialDocument.id.is_(None))
    )
    return result.scalar() or 0


async def _last_successful_source_task_at(db: DBSession) -> datetime | None:
    result = await db.execute(
        select(func.max(SourceTask.finished_at))
        .where(SourceTask.status == TaskStatus.COMPLETED)
    )
    return result.scalar_one_or_none()


def _format_datetime_minute(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


async def _load_price_dynamics_summary(db: DBSession) -> dict:
    result = await db.execute(
        select(PriceHistory.material_id, PriceHistory.price, PriceHistory.collected_at, Material.category_id)
        .join(Material, PriceHistory.material_id == Material.id)
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .order_by(PriceHistory.material_id.asc(), PriceHistory.collected_at.desc())
        .limit(2000)
    )
    rows = result.all()
    by_material: dict[str, list] = {}
    categories = set()
    for material_id, price, collected_at, category_id in rows:
        by_material.setdefault(str(material_id), []).append((price, collected_at, category_id))

    changes = []
    for material_rows in by_material.values():
        sorted_rows = sorted(material_rows, key=lambda item: item[1], reverse=True)
        if len(sorted_rows) < 2:
            continue
        latest, previous = sorted_rows[0], sorted_rows[1]
        if previous[0]:
            changes.append((latest[0] - previous[0]) / previous[0] * 100)
            if latest[2]:
                categories.add(str(latest[2]))

    spark = [12, 13, 12, 14, 16, 15, 17, 19, 18, 21, 23, 24]
    if not changes:
        market = "нужно больше данных"
    else:
        market = f"{sum(changes) / len(changes):.2f}%"
        average = float(sum(changes) / len(changes))
        spark = [max(2, int(14 + average + idx * 1.4)) for idx in range(12)]

    return {
        "market": market,
        "categories": len(categories),
        "spark": spark,
    }


async def _load_price_movers(db: DBSession) -> dict:
    result = await db.execute(
        select(Material.canonical_name, PriceHistory.price, PriceHistory.collected_at)
        .join(PriceHistory, PriceHistory.material_id == Material.id)
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .order_by(Material.id.asc(), PriceHistory.collected_at.desc())
        .limit(3000)
    )
    by_name: dict[str, list[tuple[Decimal, datetime]]] = {}
    for name, price, collected_at in result.all():
        by_name.setdefault(name, []).append((price, collected_at))

    changes = []
    for name, rows in by_name.items():
        sorted_rows = sorted(rows, key=lambda item: item[1], reverse=True)
        if len(sorted_rows) < 2 or not sorted_rows[1][0]:
            continue
        delta = (sorted_rows[0][0] - sorted_rows[1][0]) / sorted_rows[1][0] * Decimal("100")
        changes.append({"name": name, "delta": float(delta), "label": f"{delta:.1f}%"})

    growth = sorted((item for item in changes if item["delta"] > 0), key=lambda item: item["delta"], reverse=True)[:5]
    drop = sorted((item for item in changes if item["delta"] < 0), key=lambda item: item["delta"])[:5]
    if not growth:
        growth = [
            {"name": "Газобетонный блок D500", "delta": 25.4, "label": "+25,4%", "mock": True},
            {"name": "Арматура A500", "delta": 22.1, "label": "+22,1%", "mock": True},
            {"name": "Минеральная вата 50 мм", "delta": 18.7, "label": "+18,7%", "mock": True},
        ]
    if not drop:
        drop = [
            {"name": "OSB плита 12 мм", "delta": -12.4, "label": "-12,4%", "mock": True},
            {"name": "ГКЛ 12,5 мм", "delta": -7.3, "label": "-7,3%", "mock": True},
            {"name": "Саморезы по дереву", "delta": -6.1, "label": "-6,1%", "mock": True},
        ]
    return {"growth": growth, "drop": drop}


async def _load_source_health(db: DBSession) -> list[dict]:
    result = await db.execute(
        select(Source.name, Source.status, Source.source_type)
        .order_by(Source.priority.asc(), Source.name.asc())
        .limit(7)
    )
    rows = result.all()
    if not rows:
        return [{"name": "Источники не настроены", "status": "EMPTY", "type": "—"}]
    return [
        {
            "name": name,
            "status": getattr(status, "value", status),
            "type": getattr(source_type, "value", source_type),
        }
        for name, status, source_type in rows
    ]


async def _estimated_house_cost(db: DBSession) -> Decimal:
    result = await db.execute(
        select(func.sum(CatalogProduct.price))
        .where(CatalogProduct.status == CatalogProductStatus.ACTIVE)
        .where(CatalogProduct.price.is_not(None))
        .limit(1)
    )
    value = result.scalar()
    if value:
        return Decimal(value) * Decimal("8")
    return Decimal("4572861")
