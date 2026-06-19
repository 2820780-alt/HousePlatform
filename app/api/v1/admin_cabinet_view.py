from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.api.deps import DBSession
from app.models.enums import MatchCandidateStatus, MaterialStatus, TaskStatus
from app.models.material import Material
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.source_task import SourceTask


router = APIRouter(prefix="/admin/cabinet/view", tags=["admin-cabinet-view"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def admin_cabinet_view(request: Request, db: DBSession):
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
    return templates.TemplateResponse(
        request,
        "admin_cabinet_view.html",
        {"cards": cards},
    )


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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Паспорт",
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
            "Показывает паспорта модулей, уведомления, счетчики и переходы в рабочие контуры.",
            "Реализуется",
            "#60a5fa",
            "/api/v1/admin/cabinet/view",
            "Текущий модуль",
            "docs/Modules/Module_16_PersonalCabinet_v1.1.md",
            "Сводные счетчики и публичные данные включенных модулей.",
            "Навигацию, карточки модулей, быстрые переходы.",
            "Не хранит доменные данные других модулей.",
        ),
    ]


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
    return {
        "number": number,
        "title": f"Модуль {number} · {name}",
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
        "enabled": bool(href),
    }


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

    if not changes:
        market = "нужно больше данных"
    else:
        market = f"{sum(changes) / len(changes):.2f}%"

    return {
        "market": market,
        "categories": len(categories),
    }
