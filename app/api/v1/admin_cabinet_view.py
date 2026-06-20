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
from app.models.enums import CatalogProductStatus, MatchCandidateStatus, MaterialStatus, SourceStatus, TaskStatus
from app.models.favorite_module import FavoriteModule
from app.models.material import Material
from app.models.material_category import MaterialCategory
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.workspace import Workspace


router = APIRouter(prefix="/admin/cabinet/view", tags=["admin-cabinet-view"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def admin_cabinet_view(request: Request, db: DBSession):
    cards = await _load_module_passports(db)
    center_card = next(card for card in cards if card["number"] == 16)
    satellite_cards = [card for card in cards if card["number"] != 16]
    dashboard_context = await _load_dashboard_context(db, cards)
    return templates.TemplateResponse(
        request,
        "admin_cabinet_view.html",
        {
            "cards": satellite_cards,
            "center_card": center_card,
            **dashboard_context,
        },
    )


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


async def _load_dashboard_context(db: DBSession, cards: list[dict]) -> dict:
    material_total = await _count_model(db, Material)
    pending_candidates = await _count_pending_candidates(db)
    active_tasks = await _count_active_tasks(db)
    active_sources = await _count_where(db, Source, Source.status == SourceStatus.ACTIVE)
    failed_tasks = await _count_where(db, SourceTask, SourceTask.status == TaskStatus.FAILED)
    new_materials = await _count_where(
        db,
        Material,
        Material.created_at >= datetime.utcnow() - timedelta(days=7),
    )
    price_summary = await _load_price_dynamics_summary(db)
    price_movers = await _load_price_movers(db)
    source_health = await _load_source_health(db)
    personalization = await _load_personalization_context(db, cards)

    market_label = price_summary["market"]
    market_is_real = market_label != "нужно больше данных"
    construction_cost = await _estimated_house_cost(db)

    return {
        "periods": ["Неделя", "Месяц", "Квартал", "Год"],
        "project_options": ["Дом 120 м2", "Дом 160 м2", "Текущий проект"],
        "side_nav": _side_nav(),
        "top_kpis": [
            {
                "label": "Стоимость строительства дома",
                "value": f"{construction_cost:,.0f} ₽".replace(",", " "),
                "delta": "+12,4% за месяц",
                "tone": "success",
                "spark": [18, 20, 19, 23, 22, 27, 25, 31, 29, 36, 33, 41],
                "is_mock": True,
            },
            {
                "label": "Изменение стоимости",
                "value": market_label if market_is_real else "нужно больше данных",
                "delta": "по PriceHistory" if market_is_real else "ожидаем историю",
                "tone": "success" if market_is_real and not str(market_label).startswith("-") else "muted",
                "spark": price_summary["spark"],
                "is_mock": not market_is_real,
            },
            {
                "label": "Новые материалы",
                "value": new_materials,
                "delta": f"всего: {material_total}",
                "tone": "info",
                "spark": [5, 8, 7, 11, 10, 14, 13, 16, 14, 18, 20, 22],
            },
            {
                "label": "Материалы на модерации",
                "value": pending_candidates,
                "delta": "требуют решения",
                "tone": "warn" if pending_candidates else "success",
                "spark": [2, 4, 3, 5, 7, 6, 8, 7, 9, 8, 10, 11],
            },
            {
                "label": "Активные источники",
                "value": active_sources,
                "delta": "готовы к сбору",
                "tone": "success",
                "spark": [7, 8, 9, 9, 10, 10, 11, 11, 12, 12, 12, active_sources],
            },
            {
                "label": "Ошибки сбора",
                "value": failed_tasks,
                "delta": "по задачам анализа",
                "tone": "danger" if failed_tasks else "success",
                "spark": [0, 1, 0, 2, 1, 0, 1, 2, 1, 1, 0, failed_tasks],
            },
            {
                "label": "Активные задачи",
                "value": active_tasks,
                "delta": "в очереди и работе",
                "tone": "info" if active_tasks else "success",
                "spark": [0, 1, 1, 2, 1, 3, 2, 2, 4, 3, 2, active_tasks],
            },
        ],
        "analytics": {
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
        },
        "sources_overview": source_health,
        "quick_actions": _quick_actions(),
        "system_events": _system_events(pending_candidates, failed_tasks, active_tasks, new_materials),
        "personalization": personalization,
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

    favorite_numbers: list[int] = []
    if profile and profile.workspace_id:
        favorite_result = await db.execute(
            select(FavoriteModule.module_number)
            .where(
                FavoriteModule.workspace_id == profile.workspace_id,
                FavoriteModule.status == "ACTIVE",
            )
            .order_by(FavoriteModule.sort_order.asc())
        )
        favorite_numbers = [int(number) for number in favorite_result.scalars().all()]
    if not favorite_numbers and profile and profile.favorite_modules:
        favorite_numbers = [int(number) for number in profile.favorite_modules]
    if not favorite_numbers:
        favorite_numbers = [1, 14, 16]

    widget_result = await db.execute(
        select(DashboardWidget)
        .where(DashboardWidget.status == "ACTIVE")
        .order_by(DashboardWidget.module_number.asc(), DashboardWidget.title.asc())
        .limit(12)
    )
    widgets = list(widget_result.scalars().all())
    module_by_number = {card["number"]: card for card in cards}

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
            module_by_number[number]
            for number in favorite_numbers
            if number in module_by_number
        ],
        "widgets": [
            {
                "title": widget.title,
                "description": widget.description or "",
                "module_number": widget.module_number,
                "type": widget.widget_type,
                "size": widget.default_size,
            }
            for widget in widgets
        ],
        "is_default_context": True,
    }


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
            "Запланирован",
            "#5b7cfa",
            None,
            "Ожидает реализации",
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
        {"label": "Пользователи", "href": "/api/v1/admin/cabinet/view/modules/3", "icon": "☻"},
        {"label": "Журнал событий", "href": "/api/v1/admin/cabinet/view/modules/13", "icon": "◷"},
    ]


def _quick_actions() -> list[dict]:
    return [
        {"label": "Добавить материал", "href": "/api/v1/admin/material-hub/view/materials", "icon": "+"},
        {"label": "Загрузить прайс", "href": "/api/v1/admin/material-hub/view", "icon": "⇧"},
        {"label": "Импорт документов", "href": "/api/v1/admin/material-hub/view/documents", "icon": "↥"},
        {"label": "Создать смету", "href": "/api/v1/admin/cabinet/view/modules/5", "icon": "≋", "mock": True},
        {"label": "Создать тендер", "href": "/api/v1/admin/cabinet/view/modules/9", "icon": "♜", "mock": True},
        {"label": "Анализ источников", "href": "/api/v1/admin/material-hub/view", "icon": "⌁"},
    ]


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
    dashboard_metrics = metrics or []
    events = _module_events(number, dashboard_metrics)
    return {
        "number": number,
        "title": f"Модуль {number} · {name}",
        "module_name": name,
        "display_name": display_names.get(number, name),
        "dashboard_description": dashboard_descriptions.get(number, subtitle),
        "subtitle": subtitle,
        "description": description,
        "status": status,
        "accent": accent,
        "href": href,
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
        "implemented": bool(href),
        "href": href or f"/api/v1/admin/cabinet/view/modules/{number}",
        "passport_href": f"/api/v1/admin/cabinet/view/modules/{number}",
    }


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
        1: ("50%", "9%", "265px", "90deg"),
        2: ("70%", "13%", "250px", "122deg"),
        3: ("86%", "27%", "300px", "150deg"),
        4: ("91%", "50%", "330px", "180deg"),
        5: ("86%", "73%", "300px", "210deg"),
        6: ("70%", "88%", "250px", "238deg"),
        7: ("50%", "92%", "280px", "270deg"),
        8: ("30%", "88%", "250px", "302deg"),
        9: ("14%", "73%", "300px", "330deg"),
        10: ("9%", "50%", "330px", "0deg"),
        11: ("14%", "27%", "300px", "30deg"),
        12: ("30%", "13%", "250px", "58deg"),
        13: ("38%", "30%", "135px", "32deg"),
        14: ("62%", "30%", "135px", "148deg"),
        15: ("62%", "70%", "135px", "212deg"),
    }
    for card in cards:
        x, y, link_width, link_angle = layout.get(card["number"], ("50%", "50%", "180px", "0deg"))
        card["orbit"] = {
            "x": x,
            "y": y,
            "link_width": link_width,
            "link_angle": link_angle,
        }
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
