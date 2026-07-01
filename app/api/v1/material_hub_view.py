from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.config import settings
from app.models.catalog_product import CatalogProduct
from app.models.enums import (
    CatalogProductStatus,
    DocumentStatus,
    MatchCandidateStatus,
    MaterialStatus,
    SourceActionType,
    TaskStatus,
)
from app.models.material import Material
from app.models.material_category import MaterialCategory
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.material_quality_issue import MaterialQualityIssue
from app.models.material_specification import MaterialSpecification
from app.models.material_type import MaterialType
from app.models.knowledge_resource import KnowledgeResource
from app.models.price_history import PriceHistory
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.source_task_log import SourceTaskLog
from app.models.source_task_result import SourceTaskResult
from app.models.unit_conversion_rule import UnitConversionRule
from app.services.material_construction_usage import get_material_construction_usage
from app.services.material_hub_supplier_workspaces import (
    load_supplier_cards,
    load_supplier_workspace_summary,
    load_work_rates_workspace_summary,
)
from app.services.material_hub_first_wave import (
    first_wave_source_note,
    first_wave_source_status_label,
    is_first_wave_blocked_source,
)
from app.services.supplier_price_standard import (
    TEMPLATE_BASENAME,
    build_supplier_price_template_csv,
    build_supplier_price_template_xlsx,
)


router = APIRouter(prefix="/admin/material-hub/view", tags=["material-hub-view"])
templates = Jinja2Templates(directory="templates")


ACTION_LABELS = {
    SourceActionType.INITIAL_MATERIAL_SCAN.value: "Первичное наполнение материалов",
    SourceActionType.UPDATE_PRICES.value: "Обновить цены",
    SourceActionType.FIND_NEW_PRODUCTS.value: "Найти новые товары",
    SourceActionType.UPDATE_SPECIFICATIONS.value: "Обновить характеристики",
    SourceActionType.UPDATE_CERTIFICATES.value: "Документы: сертификаты и декларации",
    SourceActionType.UPDATE_TECH_DOCUMENTS.value: "Документы: технические документы",
    SourceActionType.SCAN_TECHNOLOGIES.value: "Изучить технологии",
    SourceActionType.FULL_INITIAL_SCAN.value: "Первичное наполнение: полный сбор",
    SourceActionType.CHECK_SOURCE_HEALTH.value: "Проверить доступность источника",
    SourceActionType.UPLOAD_SUPPLIER_FILE.value: "Файл CSV/XLSX",
}

ENUM_LABELS = {
    "MANUFACTURER": "Производитель",
    "RETAIL": "Ритейл",
    "SUPPLIER": "Поставщик",
    "MANUAL_UPLOAD": "Ручная загрузка",
    "ACTIVE": "Активен",
    "PAUSED": "Пауза",
    "DISABLED": "Отключен",
    "ERROR": "Ошибка",
    "PENDING": "Ожидает",
    "RUNNING": "Выполняется",
    "COMPLETED": "Выполнена",
    "FAILED": "Ошибка",
    "CANCELLED": "Отменена",
    "NEEDS_REVIEW": "Требует проверки",
    "AUTO_CREATED": "Создан автоматически",
    "VERIFIED": "Проверен",
    "DRAFT": "Черновик",
    "REJECTED": "Отклонен",
    "ARCHIVED": "Архив",
    "UNAVAILABLE": "Недоступен",
    "NEW_PRODUCT_FOUND": "Новый товар",
    "CERTIFICATE": "Сертификат",
    "DECLARATION": "Декларация",
    "FIRE_CERTIFICATE": "Пожарный сертификат",
    "SANITARY_CERTIFICATE": "Санитарный сертификат",
    "QUALITY_PASSPORT": "Паспорт качества",
    "TECH_CARD": "Техническая карта",
    "INSTALLATION_GUIDE": "Инструкция по монтажу",
    "TYPICAL_NODE": "Типовой узел",
    "ALBUM_OF_SOLUTIONS": "Альбом решений",
    "BIM_MODEL": "BIM-модель",
    "VIDEO_GUIDE": "Видеоинструкция",
    "TEST_REPORT": "Протокол испытаний",
    "TECHNICAL_APPROVAL": "Техническое свидетельство",
    "CREATED": "Создано",
    "UPDATED": "Обновлено",
    "UNCHANGED": "Без изменений",
    "CONFLICT": "Конфликт",
    "OPEN": "Открыто",
    "DEBUG": "Отладка",
    "INFO": "Информация",
    "WARNING": "Предупреждение",
}

SOURCE_DISPLAY_NAMES = {
    "Baucenter": "Бауцентр",
    "VseInstrumenti": "ВсеИнструменты",
    "Saturn-Yug": "Сатурн Юг",
    "YugKabel": "Юг Кабель",
    "VKBlock": "ВКБлок",
    "Bonolit": "Bonolit",
    "Grand Line": "Grand Line",
    "Technonikol": "ТЕХНОНИКОЛЬ",
    "Tegola": "Tegola",
    "ETM": "ЭТМ",
    "Knauf": "КНАУФ",
    "Ручной ввод": "Ручной ввод",
}

SCAN_MODE_LABELS = {
    "TEST": "Тестовый запуск",
    "CATEGORY": "Одна категория",
    "FULL": "Полный сбор",
}

DATA_SOURCE_KIND_LABELS = {
    "SUPPLIER_SITE": "Сайт поставщика",
    "API": "API",
    "FILE": "Файл CSV/XLSX",
    "OPEN_SOURCE": "Открытый источник",
    "PLATFORM_INTERNAL": "Внутренний источник платформы",
}

COLLECTION_OBJECT_LABELS = {
    "MATERIALS": "Материалы",
    "PRICES": "Цены",
    "CHARACTERISTICS": "Характеристики",
    "DOCUMENTS": "Документы",
    "WORK_RATES": "Работы и расценки",
    "SOURCE_HEALTH": "Доступность источника",
}

PROCESSING_SCENARIO_LABELS = {
    "INITIAL_FILL": "Первичное наполнение",
    "UPDATE_EXISTING": "Обновление существующих данных",
    "FIND_NEW_RECORDS": "Поиск новых записей",
    "CHECK_SOURCE": "Проверка источника",
    "EXTRACT_TECH_DATA": "Извлечение технологических данных",
}

WRITE_MODE_LABELS = {
    "PREVIEW": "Предпросмотр",
    "CREATE_CANDIDATES": "Создать кандидатов",
    "WRITE_CONFIRMED": "Записать подтвержденное",
}

DOCUMENT_TYPE_OPTIONS = {
    "ALL": "Все типы документов",
    "CERTIFICATES": "Сертификаты и декларации",
    "TECH_DOCUMENTS": "Технические документы",
}

DOCUMENT_GROUP_LABELS = {
    "CERTIFICATE": "Сертификаты",
    "DECLARATION": "Декларации",
    "FIRE_CERTIFICATE": "Пожарные сертификаты",
    "SANITARY_CERTIFICATE": "Санитарные сертификаты",
    "QUALITY_PASSPORT": "Паспорта качества",
    "TECH_CARD": "Технические карты и рекомендации",
    "INSTALLATION_GUIDE": "Инструкции по монтажу",
    "TYPICAL_NODE": "Типовые узлы",
    "ALBUM_OF_SOLUTIONS": "Альбомы решений",
    "BIM_MODEL": "BIM-модели",
    "VIDEO_GUIDE": "Видеоинструкции",
    "TEST_REPORT": "Протоколы испытаний",
    "TECHNICAL_APPROVAL": "Технические свидетельства",
}


@router.get("/supplier-price-template/{file_type}")
async def supplier_price_template(file_type: str):
    normalized = file_type.lower().strip(".")
    if normalized == "csv":
        return Response(
            build_supplier_price_template_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{TEMPLATE_BASENAME}.csv"'},
        )
    if normalized == "xlsx":
        return Response(
            build_supplier_price_template_xlsx(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{TEMPLATE_BASENAME}.xlsx"'},
        )
    raise HTTPException(status_code=404, detail="Template format not found")


@router.get("", response_class=HTMLResponse)
async def material_hub_view(
    request: Request,
    db: DBSession,
    in_stock_only: bool = Query(False),
):
    sources = await _load_sources(db)

    return templates.TemplateResponse(
        request,
        "material_hub_view.html",
        {
            "dashboard_cards": await _load_dashboard_cards(db),
            "sources": sources,
            "source_groups": _group_sources_by_direction(sources),
            "pending_candidates_total": await _count_pending_candidates(db),
            "action_labels": ACTION_LABELS,
            "enum_label": _enum_label,
            "source_display_name": _source_display_name,
            "source_status_label": _source_status_label,
            "source_policy_note": first_wave_source_note,
            "is_first_wave_blocked_source": is_first_wave_blocked_source,
            "dt": _format_datetime,
            "scan_modes": [
                {"value": value, "label": label}
                for value, label in SCAN_MODE_LABELS.items()
            ],
            "data_source_kinds": [
                {"value": value, "label": label}
                for value, label in DATA_SOURCE_KIND_LABELS.items()
            ],
            "collection_objects": [
                {"value": value, "label": label}
                for value, label in COLLECTION_OBJECT_LABELS.items()
            ],
            "processing_scenarios": [
                {"value": value, "label": label}
                for value, label in PROCESSING_SCENARIO_LABELS.items()
            ],
            "write_modes": [
                {"value": value, "label": label}
                for value, label in WRITE_MODE_LABELS.items()
            ],
            "document_type_options": [
                {"value": value, "label": label}
                for value, label in DOCUMENT_TYPE_OPTIONS.items()
            ],
            "active_collection_region": _active_collection_region(),
            "supplier_workspace_summary": await load_supplier_workspace_summary(db),
            "supplier_cards": await load_supplier_cards(db),
            "work_rates_workspace_summary": await load_work_rates_workspace_summary(db),
            "in_stock_only": in_stock_only,
        },
    )


@router.get("/moderation", response_class=HTMLResponse)
async def material_hub_moderation(request: Request, db: DBSession):
    return templates.TemplateResponse(
        request,
        "material_hub_moderation.html",
        {
            "candidates": await _load_active_candidates(db),
            "pending_candidates_total": await _count_pending_candidates(db),
            "reviewed_candidates": await _load_recent_reviewed_candidates(db),
            "enum_label": _enum_label,
            "source_display_name": _source_display_name,
            "dt": _format_datetime,
        },
    )


@router.get("/documents", response_class=HTMLResponse)
async def material_hub_documents(request: Request, db: DBSession):
    documents = await _load_documents(db)
    return templates.TemplateResponse(
        request,
        "material_hub_documents.html",
        {
            "documents": documents,
            "document_groups": _group_documents(documents),
            "document_filter_options": _document_filter_options(documents),
            "document_filter_keys": _document_filter_keys,
            "document_tags": _document_tags,
            "document_file_type": _document_file_type,
            "document_mime_type": _document_mime_type,
            "document_origin": _document_origin,
            "document_text_suitability": _document_text_suitability,
            "document_parse_status": _document_parse_status,
            "document_file_name": _document_file_name,
            "document_summary": _document_summary,
            "document_change_history_label": _document_change_history_label,
            "document_region_status": _document_region_status,
            "enum_label": _enum_label,
            "source_display_name": _source_display_name,
            "dt": _format_datetime,
        },
    )


@router.get("/data", response_class=HTMLResponse)
async def material_hub_data(
    request: Request,
    db: DBSession,
    in_stock_only: bool = Query(False),
):
    return await _render_data_page(request, db, in_stock_only, "all", "Данные Material Hub")


@router.get("/materials", response_class=HTMLResponse)
async def material_hub_materials(
    request: Request,
    db: DBSession,
    in_stock_only: bool = Query(False),
):
    return await _render_data_page(request, db, in_stock_only, "materials", "Основная таблица материалов")


@router.get("/sources", response_class=HTMLResponse)
async def material_hub_sources(request: Request, db: DBSession):
    return await _render_data_page(request, db, False, "sources", "Источники")


@router.get("/products", response_class=HTMLResponse)
async def material_hub_products(request: Request, db: DBSession):
    return await _render_data_page(request, db, False, "products", "Карточки источников")


@router.get("/tasks", response_class=HTMLResponse)
async def material_hub_tasks(request: Request, db: DBSession):
    return await _render_data_page(request, db, False, "tasks", "Задачи анализа")


@router.get("/prices", response_class=HTMLResponse)
async def material_hub_prices(request: Request, db: DBSession):
    return await _render_data_page(request, db, False, "prices", "История цен")


@router.get("/categories", response_class=HTMLResponse)
async def material_hub_categories(request: Request, db: DBSession):
    return await _render_data_page(request, db, False, "categories", "Редактор категорий")


@router.get("/classification", response_class=HTMLResponse)
async def material_hub_classification(request: Request, db: DBSession):
    return await _render_data_page(request, db, False, "classification", "Требует классификации")


async def _render_data_page(
    request: Request,
    db: DBSession,
    in_stock_only: bool,
    view_mode: str,
    page_title: str,
):
    return templates.TemplateResponse(
        request,
        "material_hub_data.html",
        {
            "view_mode": view_mode,
            "page_title": page_title,
            "sources": await _load_sources(db),
            "tasks": await _load_tasks(db),
            "products": await _load_catalog_products(db),
            "materials": await _load_materials(db),
            "materials_total": await _count_active_materials(db),
            "categories": await _load_categories(db),
            "unclassified_materials": await _load_unclassified_materials(db),
            "material_prices": await _load_material_price_map(db),
            "prices": await _load_prices(db),
            "materials_without_price_history": await _load_materials_without_price_history(db),
            "logs": await _load_logs(db),
            "results": await _load_results(db),
            "action_labels": ACTION_LABELS,
            "enum_label": _enum_label,
            "source_display_name": _source_display_name,
            "source_status_label": _source_status_label,
            "source_policy_note": first_wave_source_note,
            "is_first_wave_blocked_source": is_first_wave_blocked_source,
            "characteristic_label": _characteristic_label,
            "is_consumption_characteristic": _is_consumption_characteristic,
            "characteristic_verified_by_moderator": _characteristic_verified_by_moderator,
            "characteristic_history_label": _characteristic_history_label,
            "construction_usage_for_material": get_material_construction_usage,
            "construction_usage_source_label": _construction_usage_source_label,
            "dt": _format_datetime,
            "in_stock_only": in_stock_only,
            "price_recommendations": await _load_price_recommendations(db, in_stock_only),
        },
    )


async def _load_stats(db: DBSession) -> dict[str, int]:
    models = {
        "Источники": Source,
        "Задачи": SourceTask,
        "Карточки источников": CatalogProduct,
        "Материалы": Material,
        "Спорные совпадения": MaterialMatchCandidate,
        "История цен": PriceHistory,
        "Документы": MaterialDocument,
    }
    stats: dict[str, int] = {}
    for key, model in models.items():
        result = await db.execute(select(func.count(model.id)))
        stats[key] = result.scalar() or 0
    return stats


SOURCE_DIRECTION_BY_NAME = {
    "Baucenter": "Ритейл: широкий ассортимент",
    "VseInstrumenti": "Ритейл: инструменты и материалы",
    "Saturn-Yug": "Ритейл: строительные материалы",
    "Grand Line": "Кровля и фасады",
    "Technonikol": "Кровля, гидроизоляция и теплоизоляция",
    "Tegola": "Кровля: гибкая черепица",
    "VKBlock": "Газоблок и стеновые материалы",
    "Bonolit": "Газоблок и сухие смеси",
    "Knauf": "Сухое строительство и сухие смеси",
    "YugKabel": "Электрика и кабель",
    "ETM": "Электрика и инженерные системы",
}


def _source_direction(source: Source) -> str:
    return SOURCE_DIRECTION_BY_NAME.get(source.name, "Прочие источники")


def _source_display_name(source_or_name) -> str:
    if not source_or_name:
        return ""
    name = getattr(source_or_name, "name", source_or_name)
    return SOURCE_DISPLAY_NAMES.get(str(name), str(name))


def _source_status_label(source: Source) -> str:
    return first_wave_source_status_label(source) or _enum_label(source.status)


def _enum_label(value) -> str:
    if value is None:
        return ""
    raw_value = getattr(value, "value", value)
    return ENUM_LABELS.get(str(raw_value), str(raw_value))


def _format_datetime(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        value = value.replace("T", " ")
        return value[:16]
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _active_collection_region() -> dict[str, str | None]:
    return {
        "label": settings.MATERIAL_HUB_ACTIVE_REGION_LABEL,
        "activeRegionCode": settings.MATERIAL_HUB_ACTIVE_REGION_CODE,
        "source_region_id": settings.MATERIAL_HUB_SOURCE_REGION_ID,
        "source_city_id": settings.MATERIAL_HUB_SOURCE_CITY_ID,
        "delivery_zone_id": settings.MATERIAL_HUB_DELIVERY_ZONE_ID,
    }


def _characteristic_label(specification: MaterialSpecification) -> str:
    template = getattr(specification, "template", None)
    if template and getattr(template, "name", None):
        return template.name
    if template and getattr(template, "field_key", None):
        return template.field_key
    return "Характеристика"


def _is_consumption_characteristic(specification: MaterialSpecification) -> bool:
    template = getattr(specification, "template", None)
    text = " ".join([
        str(getattr(template, "name", "") or ""),
        str(getattr(template, "field_key", "") or ""),
        str(getattr(specification, "value", "") or ""),
        str(getattr(specification, "unit", "") or ""),
    ]).lower()
    return any(marker in text for marker in ("расход", "consumption", "rashod"))


def _characteristic_verified_by_moderator(specification: MaterialSpecification) -> bool:
    raw_status = getattr(getattr(specification, "verified_status", None), "value", None)
    return raw_status == "VERIFIED"


def _characteristic_history_label(specification: MaterialSpecification) -> str:
    updated_at = _format_datetime(getattr(specification, "updated_at", None))
    created_at = _format_datetime(getattr(specification, "created_at", None))
    if updated_at:
        return f"обновлено {updated_at}"
    if created_at:
        return f"создано {created_at}"
    return "история пока не зафиксирована"


def _construction_usage_source_label(source_module: str | None) -> str:
    if source_module == "MODULE_02_KNOWLEDGE_BASE":
        return "Module №2 / База технологий"
    if source_module == "MODULE_01_MATERIAL_HUB":
        return "Module №1 / Material Hub"
    return source_module or "источник не указан"


def _group_sources_by_direction(sources: list[Source]) -> list[dict]:
    grouped: dict[str, list[Source]] = {}
    for source in sources:
        grouped.setdefault(_source_direction(source), []).append(source)
    return [
        {
            "direction": direction,
            "sources": sorted(items, key=lambda item: (item.priority, item.name)),
        }
        for direction, items in sorted(grouped.items(), key=lambda item: item[0])
    ]


async def _load_dashboard_cards(db: DBSession) -> list[dict]:
    pending_candidates = await _count_pending_candidates(db)
    total_documents = await _count_model(db, MaterialDocument)
    documents_needs_review = await _count_where(
        db,
        MaterialDocument,
        MaterialDocument.status == DocumentStatus.NEEDS_REVIEW,
    )
    active_tasks = await _count_where(
        db,
        SourceTask,
        SourceTask.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]),
    )
    failed_tasks = await _count_where(db, SourceTask, SourceTask.status == TaskStatus.FAILED)
    total_materials = await _count_model(db, Material)
    auto_materials = await _count_where(db, Material, Material.status == MaterialStatus.AUTO_CREATED)
    total_products = await _count_model(db, CatalogProduct)
    products_needs_review = await _count_where(
        db,
        CatalogProduct,
        CatalogProduct.status == CatalogProductStatus.NEEDS_REVIEW,
    )
    total_sources = await _count_model(db, Source)
    unclassified_materials = await _count_unclassified_materials(db)
    total_categories = await _count_model(db, MaterialCategory)
    total_knowledge_resources = await _count_model(db, KnowledgeResource)
    conversion_issues = await _count_quality_issue(db, "CONVERSION_DATA_REQUIRED")
    total_conversion_rules = await _count_model(db, UnitConversionRule)

    return [
        {
            "title": "Спорные совпадения",
            "value": pending_candidates,
            "note": "очередь ручного согласования",
            "href": "/api/v1/admin/material-hub/view/moderation",
            "action": "Открыть согласование",
            "tone": "warn" if pending_candidates else "ok",
        },
        {
            "title": "Документы",
            "value": total_documents,
            "note": (
                f"требуют проверки: {documents_needs_review}"
                if documents_needs_review
                else "сохраненные ссылки и привязки"
            ),
            "href": "/api/v1/admin/material-hub/view/documents",
            "action": "Смотреть документы",
            "tone": "warn" if documents_needs_review else "info",
        },
        {
            "title": "Задачи анализа",
            "value": active_tasks,
            "note": f"активных; ошибок всего: {failed_tasks}",
            "href": "/api/v1/admin/material-hub/view/tasks",
            "action": "Открыть задачи",
            "tone": "danger" if failed_tasks else "info",
        },
        {
            "title": "Основная таблица смет",
            "value": total_materials,
            "note": f"материалы, цены и поставщики; автосозданных: {auto_materials}",
            "href": "/api/v1/admin/material-hub/view/materials",
            "action": "Открыть таблицу",
            "tone": "ok",
        },
        {
            "title": "Карточки источников",
            "value": total_products,
            "note": f"требуют проверки: {products_needs_review}",
            "href": "/api/v1/admin/material-hub/view/products?status=NEEDS_REVIEW" if products_needs_review else "/api/v1/admin/material-hub/view/products",
            "action": "Проверить карточки" if products_needs_review else "Смотреть карточки",
            "tone": "warn" if products_needs_review else "info",
        },
        {
            "title": "Источники",
            "value": total_sources,
            "note": "сайты и загрузки для анализа",
            "href": "/api/v1/admin/material-hub/view/sources",
            "action": "Управлять источниками",
            "tone": "plain",
        },
        {
            "title": "Требует классификации",
            "value": unclassified_materials,
            "note": "без категории или с конфликтом классификации",
            "href": "/api/v1/admin/material-hub/view/classification",
            "action": "Разобрать материалы",
            "tone": "warn" if unclassified_materials else "ok",
        },
        {
            "title": "Категории",
            "value": total_categories,
            "note": "справочник категорий и подкатегорий",
            "href": "/api/v1/admin/material-hub/view/categories",
            "action": "Открыть редактор",
            "tone": "info",
        },
        {
            "title": "Ресурсы знаний",
            "value": total_knowledge_resources,
            "note": "ссылки, метаданные и связи документов v2.0",
            "href": "/api/v1/admin/material-hub/view/documents",
            "action": "Смотреть ресурсы",
            "tone": "info",
        },
        {
            "title": "Требует конвертации",
            "value": conversion_issues,
            "note": f"правил конвертации: {total_conversion_rules}",
            "href": "/api/v1/admin/material-hub/view/materials",
            "action": "Проверить материалы",
            "tone": "warn" if conversion_issues else "ok",
        },
    ]


async def _count_model(db: DBSession, model) -> int:
    result = await db.execute(select(func.count(model.id)))
    return result.scalar() or 0


async def _count_where(db: DBSession, model, condition) -> int:
    result = await db.execute(select(func.count(model.id)).where(condition))
    return result.scalar() or 0


async def _count_quality_issue(db: DBSession, issue_type: str) -> int:
    result = await db.execute(
        select(func.count(MaterialQualityIssue.id)).where(
            MaterialQualityIssue.issue_type == issue_type,
            MaterialQualityIssue.status == "OPEN",
        )
    )
    return result.scalar() or 0


async def _count_active_materials(db: DBSession) -> int:
    result = await db.execute(
        select(func.count(Material.id)).where(
            Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED])
        )
    )
    return result.scalar() or 0


async def _count_unclassified_materials(db: DBSession) -> int:
    result = await db.execute(
        select(func.count(Material.id))
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .where(Material.category_id.is_(None))
    )
    return result.scalar() or 0


async def _load_sources(db: DBSession) -> list[Source]:
    result = await db.execute(
        select(Source).order_by(Source.priority.asc(), Source.name.asc()).limit(100)
    )
    return list(result.scalars().all())


async def _load_tasks(db: DBSession) -> list[SourceTask]:
    result = await db.execute(
        select(SourceTask)
        .options(selectinload(SourceTask.source))
        .order_by(SourceTask.created_at.desc())
        .limit(30)
    )
    return list(result.scalars().all())


async def _load_catalog_products(db: DBSession) -> list[CatalogProduct]:
    result = await db.execute(
        select(CatalogProduct)
        .options(
            selectinload(CatalogProduct.source),
            selectinload(CatalogProduct.material),
        )
        .where(CatalogProduct.status != CatalogProductStatus.REJECTED)
        .order_by(CatalogProduct.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


async def _load_materials(db: DBSession) -> list[Material]:
    result = await db.execute(
        select(Material)
        .options(
            selectinload(Material.category),
            selectinload(Material.subcategory),
            selectinload(Material.material_type).selectinload(MaterialType.construction_group),
            selectinload(Material.documents),
            selectinload(Material.specifications).selectinload(MaterialSpecification.template),
            selectinload(Material.specifications).selectinload(MaterialSpecification.source),
        )
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .order_by(Material.created_at.desc())
        .limit(500)
    )
    return list(result.scalars().all())


async def _load_unclassified_materials(db: DBSession) -> list[Material]:
    result = await db.execute(
        select(Material)
        .options(
            selectinload(Material.category),
            selectinload(Material.subcategory),
            selectinload(Material.material_type).selectinload(MaterialType.construction_group),
            selectinload(Material.documents),
            selectinload(Material.specifications).selectinload(MaterialSpecification.template),
            selectinload(Material.specifications).selectinload(MaterialSpecification.source),
        )
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .where(Material.category_id.is_(None))
        .order_by(Material.updated_at.desc())
        .limit(300)
    )
    return list(result.scalars().all())


async def _load_categories(db: DBSession) -> list[MaterialCategory]:
    result = await db.execute(
        select(MaterialCategory)
        .options(selectinload(MaterialCategory.parent))
        .order_by(
            MaterialCategory.level.asc(),
            MaterialCategory.name.asc(),
        )
    )
    return list(result.scalars().all())


async def _load_active_candidates(db: DBSession) -> list[MaterialMatchCandidate]:
    result = await db.execute(
        select(MaterialMatchCandidate)
        .options(
            selectinload(MaterialMatchCandidate.catalog_product).selectinload(CatalogProduct.source),
            selectinload(MaterialMatchCandidate.candidate_material),
        )
        .where(MaterialMatchCandidate.status.in_([
            MatchCandidateStatus.OPEN,
            MatchCandidateStatus.NEEDS_REVIEW,
        ]))
        .order_by(MaterialMatchCandidate.created_at.asc())
        .limit(1)
    )
    return list(result.scalars().all())


async def _load_recent_reviewed_candidates(db: DBSession) -> list[MaterialMatchCandidate]:
    day_ago = datetime.utcnow() - timedelta(days=1)
    result = await db.execute(
        select(MaterialMatchCandidate)
        .options(
            selectinload(MaterialMatchCandidate.catalog_product).selectinload(CatalogProduct.source),
            selectinload(MaterialMatchCandidate.candidate_material),
        )
        .where(MaterialMatchCandidate.status.in_([
            MatchCandidateStatus.APPROVED,
            MatchCandidateStatus.REJECTED,
        ]))
        .where(MaterialMatchCandidate.updated_at >= day_ago)
        .order_by(MaterialMatchCandidate.updated_at.desc())
        .limit(25)
    )
    return list(result.scalars().all())


async def _count_pending_candidates(db: DBSession) -> int:
    result = await db.execute(
        select(func.count(MaterialMatchCandidate.id)).where(
            MaterialMatchCandidate.status.in_([
                MatchCandidateStatus.OPEN,
                MatchCandidateStatus.NEEDS_REVIEW,
            ])
        )
    )
    return result.scalar() or 0


async def _load_prices(db: DBSession) -> list[PriceHistory]:
    result = await db.execute(
        select(PriceHistory, Material, Source)
        .join(Material, PriceHistory.material_id == Material.id)
        .outerjoin(Source, PriceHistory.source_id == Source.id)
        .order_by(PriceHistory.collected_at.desc())
        .limit(200)
    )
    return [
        {
            "price": price,
            "material": material,
            "source": source,
        }
        for price, material, source in result.all()
    ]


async def _load_materials_without_price_history(db: DBSession) -> list[Material]:
    priced_material_ids = select(PriceHistory.material_id).distinct()
    result = await db.execute(
        select(Material)
        .options(selectinload(Material.category), selectinload(Material.subcategory))
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .where(Material.id.not_in(priced_material_ids))
        .order_by(Material.updated_at.desc())
        .limit(200)
    )
    return list(result.scalars().all())


async def _load_documents(db: DBSession) -> list[MaterialDocument]:
    result = await db.execute(
        select(MaterialDocument)
        .options(
            selectinload(MaterialDocument.source),
            selectinload(MaterialDocument.material).selectinload(Material.category),
            selectinload(MaterialDocument.manufacturer),
        )
        .order_by(MaterialDocument.created_at.desc())
        .limit(100)
    )
    return list(result.scalars().all())


async def _load_logs(db: DBSession) -> list[SourceTaskLog]:
    result = await db.execute(
        select(SourceTaskLog).order_by(SourceTaskLog.created_at.desc()).limit(50)
    )
    return list(result.scalars().all())


async def _load_results(db: DBSession) -> list[SourceTaskResult]:
    result = await db.execute(
        select(SourceTaskResult).order_by(SourceTaskResult.created_at.desc()).limit(50)
    )
    return list(result.scalars().all())


async def _load_price_recommendations(db: DBSession, in_stock_only: bool) -> list[dict]:
    # Alternative: same canonical Material from another source.
    # Analog: different Material in the same category with another brand/manufacturer.
    result = await db.execute(
        select(CatalogProduct)
        .options(
            selectinload(CatalogProduct.source),
            selectinload(CatalogProduct.material).selectinload(Material.category).selectinload(MaterialCategory.parent),
            selectinload(CatalogProduct.material).selectinload(Material.subcategory),
            selectinload(CatalogProduct.material).selectinload(Material.documents),
            selectinload(CatalogProduct.material).selectinload(Material.specifications).selectinload(MaterialSpecification.template),
        )
        .where(CatalogProduct.material_id.is_not(None))
        .where(CatalogProduct.price.is_not(None))
        .where(CatalogProduct.status == CatalogProductStatus.ACTIVE)
        .where(CatalogProduct.material.has(Material.status != MaterialStatus.ARCHIVED))
        .where(CatalogProduct.material.has(Material.status != MaterialStatus.REJECTED))
        .order_by(CatalogProduct.updated_at.desc())
        .limit(300)
    )
    by_material: dict[str, list[CatalogProduct]] = {}
    all_products: list[CatalogProduct] = []
    for product in result.scalars().all():
        if in_stock_only and not _looks_available(product.availability):
            continue
        all_products.append(product)
        by_material.setdefault(str(product.material_id), []).append(product)

    recommendations: list[dict] = []
    for _material_id, products in by_material.items():
        sorted_products = sorted(products, key=lambda item: (item.price is None, item.price))
        if not sorted_products:
            continue
        best = sorted_products[0]
        material = best.material
        recommendations.append({
            "category_name": _display_category_name(material),
            "subcategory_name": _display_subcategory_name(material),
            "material_id": str(material.id) if material else "",
            "category_id": str(material.category_id) if material and material.category_id else "",
            "subcategory_id": str(material.subcategory_id) if material and material.subcategory_id else "",
            "material_name": material.canonical_name if material else str(best.material_id),
            "brand": material.brand if material else "",
            "manufacturer": material.manufacturer if material else "",
            "documents": material.documents if material else [],
            "specifications": material.specifications if material else [],
            "best": best,
            "alternatives": _same_material_alternatives(best, sorted_products),
            "analogs": _find_price_analogs(best, all_products),
        })
    return recommendations[:50]


def _same_material_alternatives(best_product: CatalogProduct, products: list[CatalogProduct]) -> list[CatalogProduct]:
    alternatives: list[CatalogProduct] = []
    seen_sources = {best_product.source_id}
    for product in products:
        if product.id == best_product.id:
            continue
        if product.material_id != best_product.material_id:
            continue
        if product.source_id in seen_sources:
            continue
        alternatives.append(product)
        seen_sources.add(product.source_id)
        if len(alternatives) >= 3:
            break
    return alternatives


def _find_price_analogs(best_product: CatalogProduct, products: list[CatalogProduct]) -> list[CatalogProduct]:
    if not best_product.material:
        return []
    analogs: list[CatalogProduct] = []
    best_material = best_product.material
    best_brand = (best_material.brand or best_product.raw_brand or "").lower()
    best_manufacturer = (best_material.manufacturer or best_product.raw_manufacturer or "").lower()
    best_tokens = _name_tokens(best_material.canonical_name)

    for product in products:
        if not product.material or product.material_id == best_product.material_id:
            continue
        material = product.material
        same_category = (
            material.category_id
            and best_material.category_id
            and material.category_id == best_material.category_id
        )
        same_subcategory = (
            material.subcategory_id
            and best_material.subcategory_id
            and material.subcategory_id == best_material.subcategory_id
        )
        if not (same_category or same_subcategory):
            continue
        brand = (material.brand or product.raw_brand or "").lower()
        manufacturer = (material.manufacturer or product.raw_manufacturer or "").lower()
        different_brand = bool(best_brand or brand) and brand != best_brand
        different_manufacturer = bool(best_manufacturer or manufacturer) and manufacturer != best_manufacturer
        if not (different_brand or different_manufacturer):
            continue
        shared_tokens = best_tokens.intersection(_name_tokens(material.canonical_name))
        if best_tokens and len(shared_tokens) < min(2, len(best_tokens)):
            continue
        analogs.append(product)
        if len(analogs) >= 3:
            break
    return analogs


def _name_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token
        for token in value.lower().replace("*", " ").replace("x", " ").split()
        if len(token) > 2 and not token.isdigit()
    }


async def _load_material_price_map(db: DBSession) -> dict[str, dict]:
    result = await db.execute(
        select(CatalogProduct)
        .options(selectinload(CatalogProduct.source))
        .where(CatalogProduct.material_id.is_not(None))
        .where(CatalogProduct.price.is_not(None))
        .where(CatalogProduct.status == CatalogProductStatus.ACTIVE)
        .where(CatalogProduct.material.has(Material.status != MaterialStatus.ARCHIVED))
        .where(CatalogProduct.material.has(Material.status != MaterialStatus.REJECTED))
        .order_by(CatalogProduct.price.asc())
        .limit(5000)
    )
    prices: dict[str, dict] = {}
    for product in result.scalars().all():
        key = str(product.material_id)
        if key in prices:
            continue
        prices[key] = {
            "price": product.price,
            "currency": product.currency,
            "unit": product.unit,
            "source": product.source.name if product.source else "",
            "availability": product.availability,
            "region": product.region,
        }
    return prices


def _display_category_name(material: Material | None) -> str:
    if not material or not material.category:
        return ""
    if material.category.parent:
        return material.category.parent.name
    return material.category.name


def _display_subcategory_name(material: Material | None) -> str:
    if not material:
        return ""
    if material.subcategory:
        return material.subcategory.name
    if material.category and material.category.parent:
        return material.category.name
    return ""


def _group_documents(documents: list[MaterialDocument]) -> list[dict]:
    grouped: dict[str, list[MaterialDocument]] = {}
    for document in documents:
        key = document.document_type.value
        grouped.setdefault(key, []).append(document)
    return [
        {
            "key": key,
            "label": DOCUMENT_GROUP_LABELS.get(key, key),
            "documents": items,
        }
        for key, items in grouped.items()
    ]


def _group_documents_by_link(documents: list[MaterialDocument]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for document in documents:
        group_key, label, category_label = _document_link_key(document)
        if group_key not in grouped:
            grouped[group_key] = {
                "key": group_key,
                "label": label,
                "category_label": category_label,
                "documents": [],
            }
        grouped[group_key]["documents"].append(document)
    return list(grouped.values())


def _document_filter_options(documents: list[MaterialDocument]) -> list[dict]:
    options: dict[str, str] = {}
    for document in documents:
        for key, label in _document_filter_pairs(document):
            options[key] = label
    return [
        {"key": key, "label": label}
        for key, label in sorted(options.items(), key=lambda item: item[1].lower())
    ]


def _document_filter_keys(document: MaterialDocument) -> list[str]:
    return [key for key, _label in _document_filter_pairs(document)]


def _document_tags(document: MaterialDocument) -> list[str]:
    tags = [DOCUMENT_GROUP_LABELS.get(document.document_type.value, document.document_type.value)]
    tags.extend(label for _key, label in _document_filter_pairs(document))
    return tags


def _document_file_name(document: MaterialDocument) -> str:
    url = document.file_url or document.source_url or ""
    clean = url.split("?", 1)[0].rstrip("/")
    if not clean:
        return ""
    return clean.rsplit("/", 1)[-1] or clean


def _document_extension(document: MaterialDocument) -> str:
    name = _document_file_name(document).lower()
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1]


def _document_file_type(document: MaterialDocument) -> str:
    extension = _document_extension(document)
    if extension in {"jpg", "jpeg", "png"}:
        return extension.upper()
    if extension in {"pdf", "csv", "xlsx", "doc", "docx", "html"}:
        return extension.upper()
    if document.file_url:
        return "другой"
    return "не указан"


def _document_mime_type(document: MaterialDocument) -> str:
    extension = _document_extension(document)
    return {
        "pdf": "application/pdf",
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "html": "text/html",
    }.get(extension, "не определен")


def _document_origin(document: MaterialDocument) -> str:
    extension = _document_extension(document)
    if extension == "pdf":
        return "native_pdf"
    if extension in {"jpg", "jpeg", "png"}:
        return "photo"
    if extension == "html" and document.file_url:
        return "html_page"
    if document.file_url:
        return "uploaded_file" if "uploads" in document.file_url.lower() else "external_link"
    if document.source_url:
        return "external_link"
    return "external_link"


def _document_text_suitability(document: MaterialDocument) -> str:
    extension = _document_extension(document)
    if extension == "pdf":
        return "текстовый слой есть или требуется проверка"
    if extension in {"jpg", "jpeg", "png"}:
        return "нужен OCR"
    if extension in {"csv", "xlsx", "doc", "docx", "html"}:
        return "текстовый слой есть"
    if document.file_url or document.source_url:
        return "неизвестно"
    return "не поддерживается"


def _document_parse_status(document: MaterialDocument) -> str:
    if document.status == DocumentStatus.REJECTED:
        return "пропущен"
    if document.status == DocumentStatus.NEEDS_REVIEW:
        return "требует ручной проверки"
    return "не обработан"


def _document_summary(document: MaterialDocument) -> str:
    linked_to = []
    if document.material:
        linked_to.append(document.material.canonical_name)
    if document.manufacturer:
        linked_to.append(f"производитель: {document.manufacturer.name}")
    if document.source:
        linked_to.append(f"источник: {_source_display_name(document.source)}")
    base = ", ".join(linked_to) if linked_to else "связи пока не указаны"
    return f"{DOCUMENT_GROUP_LABELS.get(document.document_type.value, document.document_type.value)}; {base}"


def _document_change_history_label(document: MaterialDocument) -> str:
    updated_at = _format_datetime(document.updated_at)
    created_at = _format_datetime(document.created_at)
    if updated_at:
        return f"обновлено {updated_at}"
    if created_at:
        return f"получено {created_at}"
    return "история пока не зафиксирована"


def _document_region_status(_document: MaterialDocument) -> str:
    return "не региональный документ"


def _document_filter_pairs(document: MaterialDocument) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if document.material:
        pairs.append((f"material:{document.material.id}", document.material.canonical_name))
        if document.material.category:
            pairs.append((f"category:{document.material.category.id}", document.material.category.name))
        if document.material.manufacturer:
            pairs.append((f"manufacturer-text:{document.material.manufacturer}", document.material.manufacturer))
    if document.manufacturer:
        pairs.append((f"manufacturer:{document.manufacturer.id}", document.manufacturer.name))
    if document.source:
        pairs.append((f"source:{document.source.id}", document.source.name))
    if not pairs:
        pairs.append(("unlinked", "Без привязки"))
    return pairs


def _document_link_key(document: MaterialDocument) -> tuple[str, str, str]:
    if document.material:
        category = document.material.category.name if document.material.category else "Категория не указана"
        return (
            f"material:{document.material.id}",
            document.material.canonical_name,
            category,
        )
    if document.manufacturer:
        return (
            f"manufacturer:{document.manufacturer.id}",
            f"Производитель: {document.manufacturer.name}",
            "Документы производителя",
        )
    return ("unlinked", "Без привязки к материалу", "Требует модерации")


def _looks_available(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    unavailable_markers = ["нет", "недоступ", "out of stock", "unavailable", "0 "]
    if any(marker in lowered for marker in unavailable_markers):
        return False
    return any(marker in lowered for marker in ["доступ", "в наличии", "заказ", "шт", "лст", "л."])
