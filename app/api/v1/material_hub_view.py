from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.encoders import jsonable_encoder
from fastapi.templating import Jinja2Templates
from urllib.parse import urlparse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, require_admin
from app.config import settings
from app.models.catalog_product import CatalogProduct
from app.models.enums import (
    CatalogProductStatus,
    DocumentStatus,
    MatchCandidateStatus,
    MaterialStatus,
    SourceActionType,
    SourceStatus,
    SupplierStatus,
    TaskLogLevel,
    TaskResultType,
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
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.source_task_log import SourceTaskLog
from app.models.source_task_result import SourceTaskResult
from app.models.supplier import Supplier
from app.models.supplier_price import SupplierPrice
from app.models.unit_conversion_rule import UnitConversionRule
from app.models.unit import Unit
from app.services.module1_material_ui_write import MaterialUIWrite, save_material_ui
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
from app.services.module1_source_profile_registry import build_profile_readiness_report, get_extraction_profile, get_source_profile
from app.services.module1_ui_view_models import build_module1_ui_preview_context
from app.services.module1_provider_work_cost_offers import (
    build_provider_work_cost_market_sanity_map,
    list_work_catalog_options,
    provider_work_cost_offer_to_dict,
)
from app.services.source_document_refs import is_document_url
from app.services.supplier_price_standard import (
    TEMPLATE_BASENAME,
    build_supplier_price_template_csv,
    build_supplier_price_template_xlsx,
)


router = APIRouter(
    prefix="/admin/material-hub/view",
    tags=["material-hub-view"],
    dependencies=[require_admin()],
)
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
            "sources": sources,
            "source_groups": _group_sources_by_direction(sources),
            "source_category_options": _source_category_options(sources),
            "enum_label": _enum_label,
            "source_display_name": _source_display_name,
            "source_direction": _source_direction,
            "is_first_wave_blocked_source": is_first_wave_blocked_source,
            "scan_modes": [
                {"value": value, "label": label}
                for value, label in SCAN_MODE_LABELS.items()
            ],
            "data_source_kinds": [
                {"value": value, "label": label}
                for value, label in DATA_SOURCE_KIND_LABELS.items()
                if value != "FILE"
            ],
            "collection_objects": [
                {"value": value, "label": label}
                for value, label in COLLECTION_OBJECT_LABELS.items()
                if value != "WORK_RATES"
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
            "document_material_label": _document_material_label,
            "document_material_category_label": _document_material_category_label,
            "document_type_label": _document_type_label,
            "document_confirms_label": _document_confirms_label,
            "document_validity_label": _document_validity_label,
            "document_status_label": _document_status_label,
            "document_source_label": _document_source_label,
            "document_file_state_label": _document_file_state_label,
            "document_file_action_url": _document_file_action_url,
            "document_source_action_url": _document_source_action_url,
            "document_has_safe_action": _document_has_safe_action,
            "document_supporting_org_label": _document_supporting_org_label,
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
    preset: str | None = Query(None),
):
    material_table_preset = _material_table_preset(preset, default="all")
    return await _render_data_page(request, db, in_stock_only, "all", "Данные Material Hub", material_table_preset)


@router.get("/materials", response_class=HTMLResponse)
async def material_hub_materials(
    request: Request,
    db: DBSession,
    in_stock_only: bool = Query(False),
    preset: str | None = Query(None),
    q: str = "", category: str = "", subcategory: str = "", supplier: str = "", region: str | None = None,
    minimum: Decimal | None = Query(None, ge=0), maximum: Decimal | None = Query(None, ge=0),
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), material: str = "", sort: str = "name",
):
    compatibility = {"needs_price": "without_price", "estimate_ready": "all",
                     "needs_classification": "all", "needs_review": "all"}
    selected_preset = compatibility.get(preset, preset or "all")
    return await material_hub_materials_preview(
        request, db, q=q, category=category, subcategory=subcategory, supplier=supplier, region=region,
        minimum=minimum, maximum=maximum, preset=selected_preset, page=page, page_size=page_size,
        material=material, sort=sort,
    )


@router.get("/materials-ui-preview", response_class=HTMLResponse, include_in_schema=False)
async def material_hub_materials_preview(
    request: Request, db: DBSession,
    q: str = "", category: str = "", subcategory: str = "", supplier: str = "", region: str | None = None,
    minimum: Decimal | None = Query(None, ge=0), maximum: Decimal | None = Query(None, ge=0),
    preset: str = "all", page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
    material: str = "", sort: str = "name", detail_page: bool = False,
):
    """Render the materials workspace; retain the preview URL for QA."""
    from urllib.parse import urlencode
    from app.api.v1.admin_cabinet_view import _load_active_region_context
    from app.services.module1_material_ui_catalog import (
        MATERIAL_UI_CATEGORIES, filter_material_ui_rows, load_material_ui_catalog, material_ui_rows,
    )

    if preset not in {"all", "with_price", "without_price"}:
        raise HTTPException(status_code=400, detail="Unknown materials price filter")
    if sort not in {"name", "price_asc", "price_desc"}:
        raise HTTPException(status_code=400, detail="Unknown materials sorting")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise HTTPException(status_code=400, detail="Minimum price exceeds maximum price")
    active_region = await _load_active_region_context(db)
    default_region = active_region["name"] if active_region["is_configured"] else ""
    if region is None:
        region = default_region
    rules_by_material = {}
    for rule in (await db.scalars(select(UnitConversionRule).where(
            UnitConversionRule.material_id.is_not(None), UnitConversionRule.status == "ACTIVE"))).all():
        rules_by_material.setdefault(rule.material_id, []).append(rule)
    all_rows = material_ui_rows(await load_material_ui_catalog(db), conversion_rules=rules_by_material)
    rows, counts = filter_material_ui_rows(all_rows, search=q, category=category, subcategory=subcategory,
                                           supplier=supplier, region=region, minimum=minimum, maximum=maximum,
                                           preset=preset)
    if sort == "price_asc":
        rows.sort(key=lambda item: (item["price"] is None, item["price"] or Decimal(0), item["material"].canonical_name))
    elif sort == "price_desc":
        rows.sort(key=lambda item: (item["price"] is None, -(item["price"] or Decimal(0)), item["material"].canonical_name))
    page_count = max(1, (len(rows) + page_size - 1) // page_size)
    page = min(page, page_count)
    page_rows = rows[(page - 1) * page_size:page * page_size]
    selected = next((item for item in rows if str(item["material"].id) == material), None)
    if selected is None and material:
        selected = next((item for item in all_rows if str(item["material"].id) == material), None)
        if selected is not None:
            selected = {**selected, "visible_offers": selected["offers"]}
    if detail_page and selected is None:
        raise HTTPException(status_code=404, detail="Материал не найден.")
    selected_rules = []
    if selected:
        selected_rules = list((await db.scalars(select(UnitConversionRule).where(
            UnitConversionRule.material_id == selected["material"].id,
            UnitConversionRule.status != "ARCHIVED").order_by(UnitConversionRule.created_at))).all())
    units = (await db.scalars(select(Unit).order_by(Unit.name))).all()
    suppliers = {offer.supplier_id: offer.supplier for row in all_rows for offer in row["offers"] if offer.supplier_id}
    edit_data = None
    if selected:
        item = selected["material"]
        attrs = [attribute for attribute in item.attributes
                 if attribute.attribute_name != "ui_purpose"
                 and not attribute.attribute_name.startswith(("registry_", "declared_"))
                 and not attribute.attribute_name.endswith("_id")]
        edit_data = {
            "id": str(item.id), "name": item.canonical_name,
            "category_id": str(item.category_id or ""), "subcategory": item.subcategory.name if item.subcategory else "",
            "description": item.description or "", "base_unit_id": str(item.base_unit_id or ""),
            "purpose": next((a.attribute_value for a in item.attributes if a.attribute_name == "ui_purpose"), ""),
            "attributes": [{"name": a.attribute_name, "value": a.attribute_value,
                            "unit_id": str(a.unit_id or ""), "value_type": a.value_type} for a in attrs],
            "specifications": [{"id": str(spec.id), "label": _characteristic_label(spec),
                                "value": spec.value, "unit": spec.unit or ""} for spec in item.specifications],
            "conversions": [{"from_unit_id": str(unit.id), "coefficient": str(rule.coefficient), "source": rule.source}
                            for rule in selected_rules for unit in units
                            if rule.status == "NEEDS_REVIEW" and rule.formula_type == "LINEAR_COEFFICIENT"
                            and rule.coefficient is not None and rule.source and unit.abbreviation == rule.from_unit
                            and item.base_unit and rule.to_unit == item.base_unit.abbreviation],
            "analog_ids": [str(link.analog_material_id) for link in item.analog_links
                           if link.status not in {"ARCHIVED", "REJECTED"} and link.analog_material
                           and link.analog_material.status not in {MaterialStatus.ARCHIVED, MaterialStatus.REJECTED}],
        }

    def preview_url(**changes):
        params = dict(request.query_params)
        for key, value in changes.items():
            if value is None or value == "":
                params.pop(key, None)
            else:
                params[key] = str(value)
        encoded = urlencode(params)
        return "/api/v1/admin/material-hub/view/materials" + (f"?{encoded}" if encoded else "")

    def material_detail_url(material_id):
        params = dict(request.query_params)
        params.pop("material", None)
        encoded = urlencode(params)
        return f"/api/v1/admin/material-hub/view/materials/{material_id}" + (f"?{encoded}" if encoded else "")

    def preview_price(value):
        if value is None:
            return "Без цены"
        if Decimal(0) < value < Decimal("0.005"):
            return "< 0,01 ₽"
        return f"{value:.2f} ₽".replace(".", ",")

    categories = await _load_categories(db)
    by_name = {item.name: item for item in categories if not item.parent_id and item.status == "ACTIVE"}
    approved_categories = [by_name[name] for name in MATERIAL_UI_CATEGORIES if name in by_name]
    return templates.TemplateResponse(request, "material_hub_materials_preview.html", {
        "rows": page_rows, "all_rows": all_rows, "selected": selected, "selected_rules": selected_rules,
        "edit_data": edit_data, "counts": counts, "total": len(rows),
        "page": page, "page_count": page_count, "page_size": page_size,
        "categories": categories, "approved_categories": approved_categories,
        "units": units,
        "suppliers": sorted(suppliers.items(), key=lambda item: item[1]),
        "q": q, "category": category, "subcategory": subcategory, "supplier": supplier, "region": region,
        "default_region": default_region, "atom_topbar_region_name": active_region["name"],
        "atom_topbar_region_code": active_region["code"],
        "minimum": minimum, "maximum": maximum, "preset": preset, "sort": sort,
        "preview_url": preview_url, "material_detail_url": material_detail_url,
        "detail_page": detail_page or bool(material), "preview_price": preview_price,
        "material_attribute_rows": _material_ui_attribute_rows,
        "characteristic_label": _characteristic_label, "dt": _format_datetime,
    })


@router.post("/materials/save", include_in_schema=False)
@router.post("/materials-ui-preview/save", include_in_schema=False)
async def material_hub_materials_preview_save(
    payload: MaterialUIWrite, db: DBSession, user: CurrentUser, material_id: str | None = None,
):
    from uuid import UUID

    try:
        identifier = UUID(material_id) if material_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный идентификатор материала.")
    result = await save_material_ui(db, payload, actor_id=user.id, material_id=identifier)
    return {"id": str(result.id)}


@router.get("/materials/suppliers/{supplier_id}", response_class=HTMLResponse, include_in_schema=False)
@router.get("/materials-ui-preview/suppliers/{supplier_id}", response_class=HTMLResponse, include_in_schema=False)
async def material_hub_materials_preview_supplier(request: Request, db: DBSession, supplier_id: str):
    from uuid import UUID

    try:
        identifier = UUID(supplier_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Поставщик не найден.")
    supplier = await db.get(Supplier, identifier)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Поставщик не найден.")
    prices = (await db.scalars(select(SupplierPrice).where(SupplierPrice.supplier_id == identifier)
                              .options(selectinload(SupplierPrice.material))
                              .order_by(SupplierPrice.updated_at.desc()))).all()
    return templates.TemplateResponse(request, "material_hub_supplier_preview.html", {
        "supplier": supplier, "prices": prices, "dt": _format_datetime,
    })


@router.get("/materials/{material_id}", response_class=HTMLResponse)
async def material_hub_material_detail(
    request: Request, db: DBSession, material_id: str,
    q: str = "", category: str = "", subcategory: str = "", supplier: str = "", region: str | None = None,
    minimum: Decimal | None = Query(None, ge=0), maximum: Decimal | None = Query(None, ge=0),
    preset: str = "all", page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
    sort: str = "name",
):
    return await material_hub_materials_preview(
        request, db, q=q, category=category, subcategory=subcategory, supplier=supplier, region=region,
        minimum=minimum, maximum=maximum, preset=preset, page=page, page_size=page_size,
        material=material_id, sort=sort, detail_page=True,
    )


@router.get("/work-costs", response_class=HTMLResponse)
async def material_hub_work_costs(request: Request, db: DBSession):
    return templates.TemplateResponse(
        request,
        "material_hub_work_costs.html",
        {
            "offer_rows": jsonable_encoder(await _load_provider_work_cost_offer_rows(db)),
            "work_catalog_options": jsonable_encoder(list_work_catalog_options()),
        },
    )
@router.get("/sources", response_class=HTMLResponse)
async def material_hub_sources(request: Request, db: DBSession):
    sources = await _load_sources(db)
    tasks = await _load_tasks(db)
    products = await _load_catalog_products(db)
    documents = await _load_documents(db)
    results = await _load_results(db)
    logs = await _load_logs(db)
    candidates = await _load_source_candidates(db)
    return templates.TemplateResponse(
        request,
        "material_hub_sources_analyzer.html",
        _build_sources_analyzer_context(
            sources=sources,
            tasks=tasks,
            products=products,
            documents=documents,
            results=results,
            logs=logs,
            candidates=candidates,
        ),
    )

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
    material_table_preset: str = "all",
):
    materials = await _load_materials(db, without_price=material_table_preset == "needs_price")
    material_prices = ({} if material_table_preset == "needs_price"
                       else await _load_material_price_map(db, material_ids=[item.id for item in materials]))
    price_recommendations = await _load_price_recommendations(db, in_stock_only)
    estimate_ready_material_ids = {item["material_id"] for item in price_recommendations if item.get("material_id")}
    return templates.TemplateResponse(
        request,
        "material_hub_data.html",
        {
            "view_mode": view_mode,
            "page_title": page_title,
            "material_table_preset": material_table_preset,
            "material_table_presets": _material_table_presets(material_table_preset),
            "sources": await _load_sources(db),
            "tasks": await _load_tasks(db),
            "products": await _load_catalog_products(db),
            "materials": materials,
            "materials_total": await _count_active_materials(db),
            "categories": await _load_categories(db),
            "unclassified_materials": await _load_unclassified_materials(db),
            "material_prices": material_prices,
            "estimate_ready_material_ids": estimate_ready_material_ids,
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
            "material_attribute_rows": _material_attribute_rows,
            "is_consumption_characteristic": _is_consumption_characteristic,
            "characteristic_verified_by_moderator": _characteristic_verified_by_moderator,
            "characteristic_history_label": _characteristic_history_label,
            "construction_usage_for_material": get_material_construction_usage,
            "construction_usage_source_label": _construction_usage_source_label,
            "dt": _format_datetime,
            "in_stock_only": in_stock_only,
            "price_recommendations": price_recommendations,
        },
    )


def _build_sources_analyzer_context(
    *,
    sources: list[Source],
    tasks: list[SourceTask],
    products: list[CatalogProduct],
    documents: list[MaterialDocument],
    results: list[SourceTaskResult],
    logs: list[SourceTaskLog],
    candidates: list[MaterialMatchCandidate],
) -> dict[str, Any]:
    source_rows = _source_workspace_rows(sources, tasks, products, documents, results)
    run_rows = [_run_workspace_row(task) for task in tasks]
    result_rows = _source_result_workspace_rows(products, documents, candidates, results)
    error_rows = _source_error_workspace_rows(tasks, logs)
    source_states = sorted({row["state_key"] for row in source_rows})
    regions = sorted({row["region"] for row in source_rows if row["region"]})
    result_types = sorted({row["type_key"] for row in result_rows})
    error_types = sorted({row["type_key"] for row in error_rows})
    run_states = sorted({row["state_key"] for row in run_rows})
    return {
        "source_rows": source_rows,
        "run_rows": run_rows,
        "result_rows": result_rows,
        "error_rows": error_rows,
        "source_states": source_states,
        "regions": regions,
        "result_types": result_types,
        "error_types": error_types,
        "run_states": run_states,
        "summary": {
            "sources": len(source_rows),
            "enabled_sources": sum(1 for row in source_rows if row["enabled_key"] == "enabled"),
            "running": sum(1 for row in run_rows if row["state_key"] == "running"),
            "warnings": len(error_rows),
            "results": len(result_rows),
        },
        "dt": _format_datetime,
    }


def _source_workspace_rows(
    sources: list[Source],
    tasks: list[SourceTask],
    products: list[CatalogProduct],
    documents: list[MaterialDocument],
    results: list[SourceTaskResult],
) -> list[dict[str, Any]]:
    stats = _source_activity_stats(sources, tasks, products, documents, results)
    latest_tasks = _latest_tasks_by_source(tasks)
    rows: list[dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        key = str(source.id)
        row_stats = stats.get(key, {})
        latest_task = latest_tasks.get(key)
        profile = get_source_profile(source.name)
        extraction_profile = get_extraction_profile(source.name)
        readiness = build_profile_readiness_report(source.name)
        safe_url = _safe_external_url(source.url)
        status_label, state_key, state_tone = _human_source_state(source, latest_task)
        last_check = _latest_datetime(
            source.last_full_scan_at,
            source.last_price_update_at,
            source.last_document_update_at,
            source.last_knowledge_scan_at,
            getattr(latest_task, "finished_at", None),
            getattr(latest_task, "created_at", None),
        )
        rows.append({
            "index": index,
            "source_name": _source_display_name(source),
            "domain": _safe_domain(safe_url),
            "safe_url": safe_url,
            "scope": _source_scope_label(profile, row_stats),
            "region": _source_region_label(source, profile, row_stats),
            "state_label": status_label,
            "state_key": state_key,
            "state_tone": state_tone,
            "enabled_key": "disabled" if _enum_value(source.status) in {"DISABLED", "PAUSED"} else "enabled",
            "last_check": _format_datetime(last_check) or "Не проверялся",
            "last_result": _source_last_result_label(latest_task, row_stats),
            "next_check": _source_next_check_label(source),
            "settings": _source_settings_summary(source, profile, extraction_profile, readiness),
            "products_count": row_stats.get("products", 0),
            "documents_count": row_stats.get("documents", 0),
            "runs_count": row_stats.get("tasks", 0),
            "errors_count": row_stats.get("failed_tasks", 0) + row_stats.get("errors", 0),
        })
    return rows


def _source_activity_stats(
    sources: list[Source],
    tasks: list[SourceTask],
    products: list[CatalogProduct],
    documents: list[MaterialDocument],
    results: list[SourceTaskResult],
) -> dict[str, dict[str, Any]]:
    stats = {str(source.id): {"products": 0, "priced_products": 0, "documents": 0, "tasks": 0, "failed_tasks": 0, "errors": 0, "regions": set()} for source in sources}
    for product in products:
        key = str(product.source_id)
        if key in stats:
            stats[key]["products"] += 1
            if _has_positive_price(product.price):
                stats[key]["priced_products"] += 1
            if product.region:
                stats[key]["regions"].add(str(product.region))
    for document in documents:
        key = str(document.source_id) if document.source_id else ""
        if key in stats:
            stats[key]["documents"] += 1
    for task in tasks:
        key = str(task.source_id) if task.source_id else ""
        if key in stats:
            stats[key]["tasks"] += 1
            if task.status == TaskStatus.FAILED:
                stats[key]["failed_tasks"] += 1
    for result in results:
        task = getattr(result, "task", None)
        key = str(getattr(task, "source_id", "") or "")
        if key in stats and _enum_value(result.result_type) == "ERROR":
            stats[key]["errors"] += 1
    return stats


def _latest_tasks_by_source(tasks: list[SourceTask]) -> dict[str, SourceTask]:
    latest: dict[str, SourceTask] = {}
    for task in tasks:
        key = str(task.source_id) if task.source_id else ""
        if key and key not in latest:
            latest[key] = task
    return latest


def _run_workspace_row(task: SourceTask) -> dict[str, Any]:
    status_value = _enum_value(task.status)
    source_label = _source_display_name(task.source) if task.source else "Источник не указан"
    started = task.started_at or task.created_at
    finished = task.finished_at
    duration = _format_duration(started, finished)
    has_errors = task.status == TaskStatus.FAILED or bool(task.error_message)
    return {
        "source": source_label,
        "started_at": _format_datetime(started) or "Дата не указана",
        "finished_at": _format_datetime(finished) or ("Выполняется" if task.status == TaskStatus.RUNNING else "Не завершён"),
        "duration": duration,
        "action": ACTION_LABELS.get(_enum_value(task.action_type), _enum_label(task.action_type)),
        "state_label": _human_task_state(task.status),
        "state_key": _task_state_key(task.status),
        "state_tone": _task_state_tone(task.status),
        "processed": _task_processed_label(task.result_summary),
        "result": _task_result_label(task),
        "issues": _task_issue_label(task),
        "has_errors": "yes" if has_errors else "no",
        "has_results": "yes" if task.result_summary else "no",
        "status_value": status_value,
    }


def _source_result_workspace_rows(
    products: list[CatalogProduct],
    documents: list[MaterialDocument],
    candidates: list[MaterialMatchCandidate],
    results: list[SourceTaskResult],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product in products[:60]:
        has_price = _has_positive_price(product.price)
        rows.append({
            "type_label": "Материалы и цены" if has_price else "Source/evidence",
            "type_key": "materials_prices" if has_price else "source_evidence",
            "source": _source_display_name(product.source) if product.source else "Источник не указан",
            "created_at": _format_datetime(product.updated_at or product.created_at),
            "title": _safe_result_title(product.raw_name, fallback="Карточка источника"),
            "status": "Положительная цена найдена" if has_price else "Цена не найдена; материал не готов",
            "status_key": "positive_price" if has_price else "missing_price",
            "target": "/api/v1/admin/material-hub/view/materials?preset=all" if has_price else "#errors-view",
            "target_label": "Материалы" if has_price else "Ошибки и предупреждения",
            "tone": "ok" if has_price else "warn",
        })
    for document in documents[:40]:
        rows.append({
            "type_label": "Документы/evidence",
            "type_key": "documents",
            "source": _document_source_label(document),
            "created_at": _format_datetime(document.updated_at or document.created_at),
            "title": _safe_result_title(document.title, fallback="Документ"),
            "status": _document_status_label(document),
            "status_key": "document",
            "target": "/api/v1/admin/material-hub/view/documents",
            "target_label": "Документы",
            "tone": "ok" if document.status == DocumentStatus.ACTIVE else "warn",
        })
    for candidate in candidates[:40]:
        product = candidate.catalog_product
        rows.append({
            "type_label": "Модерация/candidates",
            "type_key": "moderation",
            "source": _source_display_name(product.source) if product and product.source else "Источник не указан",
            "created_at": _format_datetime(candidate.updated_at or candidate.created_at),
            "title": _safe_result_title(getattr(product, "raw_name", None), fallback="Кандидат на проверку"),
            "status": "Ожидает решения модератора",
            "status_key": "moderation",
            "target": "/api/v1/admin/material-hub/view/moderation",
            "target_label": "Очередь модерации",
            "tone": "warn",
        })
    for result in results[:40]:
        rows.append(_task_result_workspace_row(result))
    return rows[:140]


def _task_result_workspace_row(result: SourceTaskResult) -> dict[str, Any]:
    task = getattr(result, "task", None)
    source = getattr(task, "source", None)
    result_type = _enum_value(result.result_type)
    entity_type = str(result.entity_type or "").lower()
    if result_type == "ERROR":
        type_label, type_key, target, target_label, tone = "Source health/logistics", "source_health", "#errors-view", "Ошибки", "bad"
    elif "document" in entity_type or "evidence" in entity_type:
        type_label, type_key, target, target_label, tone = "Документы/evidence", "documents", "/api/v1/admin/material-hub/view/documents", "Документы", "ok"
    elif "candidate" in entity_type or result_type == "NEEDS_REVIEW":
        type_label, type_key, target, target_label, tone = "Модерация/candidates", "moderation", "/api/v1/admin/material-hub/view/moderation", "Очередь модерации", "warn"
    else:
        type_label, type_key, target, target_label, tone = "Материалы и цены", "materials_prices", "/api/v1/admin/material-hub/view/materials?preset=all", "Материалы", "ok"
    return {
        "type_label": type_label,
        "type_key": type_key,
        "source": _source_display_name(source) if source else "Источник не указан",
        "created_at": _format_datetime(result.created_at),
        "title": _safe_result_title(_result_display_value(result), fallback=_enum_label(result.result_type)),
        "status": _human_result_status(result),
        "status_key": "result",
        "target": target,
        "target_label": target_label,
        "tone": tone,
    }


def _source_error_workspace_rows(tasks: list[SourceTask], logs: list[SourceTaskLog]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        if task.status == TaskStatus.FAILED or task.error_message:
            error_type = _human_error_type(task.error_message)
            rows.append({
                "source": _source_display_name(task.source) if task.source else "Источник не указан",
                "created_at": _format_datetime(task.updated_at or task.created_at),
                "type_label": error_type[0],
                "type_key": error_type[1],
                "message": _human_error_message(task.error_message),
                "state": "Не решено",
                "resolved_key": "unresolved",
                "tone": "bad" if task.status == TaskStatus.FAILED else "warn",
            })
    for log in logs:
        if log.level not in {TaskLogLevel.WARNING, TaskLogLevel.ERROR}:
            continue
        task = getattr(log, "task", None)
        error_type = _human_error_type(log.message)
        rows.append({
            "source": _source_display_name(task.source) if task and task.source else "Источник не указан",
            "created_at": _format_datetime(log.created_at),
            "type_label": error_type[0],
            "type_key": error_type[1],
            "message": _human_error_message(log.message),
            "state": "Требует внимания",
            "resolved_key": "unresolved",
            "tone": "bad" if log.level == TaskLogLevel.ERROR else "warn",
        })
    return rows[:100]


def _human_source_state(source: Source, latest_task: SourceTask | None) -> tuple[str, str, str]:
    if latest_task and latest_task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
        return "Выполняется", "running", "warn"
    status = _enum_value(source.status)
    if status == "DISABLED":
        return "Отключён", "disabled", "muted"
    if status == "PAUSED":
        return "Требует настройки", "needs_setup", "warn"
    if status == "ERROR" or (latest_task and latest_task.status == TaskStatus.FAILED):
        return "Есть ошибки", "has_errors", "bad"
    if not _latest_datetime(source.last_full_scan_at, source.last_price_update_at, source.last_document_update_at, source.last_knowledge_scan_at, getattr(latest_task, "created_at", None)):
        return "Не проверялся", "not_checked", "muted"
    return "Работает", "working", "ok"


def _source_last_result_label(task: SourceTask | None, stats: dict[str, Any]) -> str:
    if task is None:
        return "Проверок пока нет"
    if task.status == TaskStatus.COMPLETED:
        products = stats.get("products", 0)
        documents = stats.get("documents", 0)
        if products or documents:
            return f"Найдено: материалы/цены {products}, документы {documents}"
        return "Завершено без новых записей"
    if task.status == TaskStatus.FAILED:
        return "Завершено с ошибкой"
    if task.status == TaskStatus.RUNNING:
        return "Идёт обработка"
    if task.status == TaskStatus.PENDING:
        return "Ожидает запуска"
    return _human_task_state(task.status)


def _source_scope_label(profile: Any | None, stats: dict[str, Any]) -> str:
    labels: list[str] = []
    allowed = tuple(getattr(profile, "allowed_objects", ()) or ()) if profile else tuple()
    for item in allowed:
        label = _collection_object_label(str(item))
        if label and label not in labels:
            labels.append(label)
    if stats.get("priced_products") and "цены" not in labels:
        labels.append("цены")
    if stats.get("products") and "материалы" not in labels:
        labels.append("материалы")
    if stats.get("documents") and "документы" not in labels:
        labels.append("документы")
    return ", ".join(labels) if labels else "Настроено в источнике"


def _collection_object_label(value: str) -> str:
    return {
        "MATERIALS": "материалы",
        "PRICES": "цены",
        "CHARACTERISTICS": "технические данные",
        "DOCUMENTS": "документы",
        "SOURCE_HEALTH": "доступность источника",
    }.get(value, "")


def _source_region_label(source: Source, profile: Any | None, stats: dict[str, Any]) -> str:
    profile_region = getattr(profile, "region", None) or getattr(profile, "city", None)
    if profile_region:
        return str(profile_region)
    regions = sorted(stats.get("regions") or [])
    if regions:
        return ", ".join(regions[:2])
    if source.source_type == getattr(source.source_type, "MANUAL_UPLOAD", None):
        return "Задаётся в файле"
    return _active_collection_region().get("label") or "Регион не указан"


def _source_next_check_label(_source: Source) -> str:
    return "Расписание не задано"


def _source_settings_summary(source: Source, profile: Any | None, extraction_profile: Any | None, readiness: Any | None) -> list[dict[str, str]]:
    target_group_count = len(getattr(extraction_profile, "target_material_groups", ()) or ())
    ready = bool(getattr(readiness, "ready", False))
    return [
        {"label": "Название", "value": _source_display_name(source)},
        {"label": "Тип источника", "value": _enum_label(source.source_type) or "Не указан"},
        {"label": "Регион", "value": _source_region_label(source, profile, {})},
        {"label": "Настройка извлечения", "value": "Готова" if ready else "Требует проверки"},
        {"label": "Группы материалов", "value": str(target_group_count) if target_group_count else "Не настроены"},
        {"label": "Частота проверки", "value": "Расписание не задано"},
        {"label": "Режим", "value": "Только чтение настроек в этой вкладке"},
    ]


def _human_task_state(status: Any) -> str:
    return {
        "PENDING": "Ожидает запуска",
        "RUNNING": "Выполняется",
        "COMPLETED": "Завершён",
        "FAILED": "Есть ошибки",
        "CANCELLED": "Отменён",
        "NEEDS_REVIEW": "Требует проверки",
    }.get(_enum_value(status), _enum_label(status) or "Неизвестно")


def _task_state_key(status: Any) -> str:
    return {
        "PENDING": "pending",
        "RUNNING": "running",
        "COMPLETED": "completed",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
        "NEEDS_REVIEW": "needs_review",
    }.get(_enum_value(status), "unknown")


def _task_state_tone(status: Any) -> str:
    if status == TaskStatus.COMPLETED:
        return "ok"
    if status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
        return "bad"
    if status in {TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.NEEDS_REVIEW}:
        return "warn"
    return "muted"


def _task_processed_label(summary: Any) -> str:
    if not isinstance(summary, dict):
        return "Итог не указан"
    parts: list[str] = []
    for key, label in (("processed", "обработано"), ("created", "создано"), ("updated", "обновлено"), ("documents", "документы"), ("errors", "ошибки"), ("skipped", "пропущено")):
        value = summary.get(key)
        if isinstance(value, (int, float)) and value:
            parts.append(f"{label}: {int(value)}")
    return ", ".join(parts) if parts else "Итог без чисел"


def _task_result_label(task: SourceTask) -> str:
    if task.status == TaskStatus.COMPLETED:
        return "Результат сохранён как данные источника/evidence"
    if task.status == TaskStatus.FAILED:
        return "Запуск завершился ошибкой"
    if task.status == TaskStatus.RUNNING:
        return "Обработка продолжается"
    if task.status == TaskStatus.PENDING:
        return "Ожидает обработки"
    return _human_task_state(task.status)


def _task_issue_label(task: SourceTask) -> str:
    if task.error_message:
        return _human_error_type(task.error_message)[0]
    if task.status == TaskStatus.COMPLETED:
        return "Критичных ошибок нет"
    return "Требует наблюдения"


def _human_result_status(result: SourceTaskResult) -> str:
    if result.result_type == TaskResultType.ERROR:
        return "Есть ошибка источника"
    status = str(result.status or "").strip()
    if status:
        return _human_status_text(status)
    return _enum_label(result.result_type) or "Результат зафиксирован"


def _human_status_text(value: str) -> str:
    normalized = value.lower().replace("_", " ").strip()
    return {
        "created": "Создано",
        "updated": "Обновлено",
        "unchanged": "Без изменений",
        "needs review": "Требует проверки",
        "error": "Есть ошибка",
        "active": "Активно",
        "pending": "Ожидает обработки",
    }.get(normalized, value[:80])


def _human_error_type(message: str | None) -> tuple[str, str]:
    text = (message or "").lower()
    if "price" in text or "цена" in text:
        return "Цена не найдена", "price_missing"
    if "document" in text or "pdf" in text or "file" in text or "документ" in text:
        return "Документ недоступен", "document_unavailable"
    if "timeout" in text or "connect" in text or "unavailable" in text or "недоступ" in text:
        return "Источник временно недоступен", "source_unavailable"
    if "parse" in text or "format" in text or "распозн" in text:
        return "Значение не распознано", "value_not_recognized"
    if "required" in text or "missing" in text or "настрой" in text:
        return "Требуется настройка источника", "setup_required"
    return "Временная ошибка обработки", "temporary_error"


def _human_error_message(message: str | None) -> str:
    label, key = _human_error_type(message)
    if key == "price_missing":
        return "Запись оставлена как source/evidence: положительная цена не найдена, материал не создаётся."
    if key == "source_unavailable":
        return "Источник не ответил или временно недоступен; данные не записаны как готовые материалы."
    if key == "document_unavailable":
        return "Документ или ссылка недоступны; запись требует проверки."
    if key == "value_not_recognized":
        return "Часть значений не удалось распознать безопасно."
    if key == "setup_required":
        return "Нужна проверка настроек источника перед следующим запуском."
    return f"{label}; подробности доступны в системных журналах администратора."


def _format_duration(started: datetime | None, finished: datetime | None) -> str:
    if not started or not finished:
        return "—"
    seconds = max(0, int((finished - started).total_seconds()))
    minutes, rest = divmod(seconds, 60)
    if minutes:
        return f"{minutes} мин {rest} сек"
    return f"{rest} сек"


def _latest_datetime(*values: datetime | None) -> datetime | None:
    valid = [value for value in values if isinstance(value, datetime)]
    return max(valid) if valid else None


def _safe_external_url(value: str | None) -> str:
    candidate = _safe_user_url(value)
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return ""
    return candidate


def _safe_domain(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    host = parsed.netloc.split("@")[-1].split(":")[0]
    return host.replace("www.", "")


def _has_positive_price(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _result_display_value(result: SourceTaskResult) -> str:
    value = result.new_value if isinstance(result.new_value, dict) else {}
    for key in ("title", "name", "material", "document", "message", "status"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return str(result.entity_type or "")


def _safe_result_title(value: str | None, *, fallback: str) -> str:
    text = (value or "").strip()
    if not text:
        return fallback
    if "{" in text or "}" in text or "traceback" in text.lower():
        return fallback
    return text[:140]


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


_MATERIAL_ATTRIBUTE_LABELS = {
    "mixture_type": ("Вид смеси", ""), "concrete_class": ("Класс бетона", ""),
    "water_resistance": ("Водонепроницаемость", ""), "frost_type": ("Тип морозостойкости", ""),
    "frost_cycles": ("Морозостойкость", "циклов"), "mobility_class": ("Подвижность", ""),
    "steel_class": ("Класс арматуры", ""), "diameter_mm": ("Диаметр", "мм"),
    "profile": ("Профиль", ""), "declared_theoretical_mass_kg_per_m": ("Масса погонного метра (заявлена)", "кг/м"),
    "thickness_mm": ("Толщина", "мм"), "cs_10_y_kpa": ("Прочность CS(10/Y)", "кПа"),
    "declared_mark": ("Марка (заявлена)", ""), "length_mm": ("Длина", "мм"),
    "width_mm": ("Ширина", "мм"), "height_mm": ("Высота", "мм"),
    "load_group": ("Группа несущей способности", ""), "concrete_type": ("Тип бетона", ""),
    "declared_standard": ("Стандарт (заявлен)", ""), "strength_mark": ("Марка прочности", ""),
    "mobility_mark": ("Подвижность", ""), "tube_diameter_mm": ("Диаметр трубы", "мм"),
    "wall_thickness_mm": ("Толщина стенки", "мм"), "blade_diameter_mm": ("Диаметр лопасти", "мм"),
    "section_width_mm": ("Ширина сечения", "мм"), "section_height_mm": ("Высота сечения", "мм"),
    "mass_kg": ("Масса", "кг"),
}
_MATERIAL_INTERNAL_ATTRIBUTES = frozenset({"registry_origin", "registry_key", "registry_code", "declared_source", "ui_purpose"})


def _material_attribute_rows(material: Material) -> list[dict[str, str]]:
    rows = []
    for attribute in material.attributes:
        name, value = attribute.attribute_name, attribute.attribute_value
        if name in _MATERIAL_INTERNAL_ATTRIBUTES or name.endswith("_id") or not value:
            continue
        label, unit = _MATERIAL_ATTRIBUTE_LABELS.get(name, (_humanize_material_field_key(name), ""))
        rows.append({"label": label, "value": value, "unit": unit})
    return rows


def _material_ui_attribute_rows(material: Material) -> list[dict[str, str]]:
    rows = []
    for attribute in material.attributes:
        name, value = attribute.attribute_name, attribute.attribute_value
        if name in _MATERIAL_INTERNAL_ATTRIBUTES or name.endswith("_id") or not value:
            continue
        label, fallback_unit = _MATERIAL_ATTRIBUTE_LABELS.get(name, (_humanize_material_field_key(name), ""))
        rows.append({"label": label, "value": value,
                     "unit": attribute.unit.abbreviation if attribute.unit else fallback_unit})
    return rows


MATERIAL_TABLE_PRESET_LABELS = {
    "all": ("Все материалы", "Единая каноническая таблица без preset-фильтра."),
    "estimate_ready": ("Готовы к смете", "Материалы из существующего серверного списка готовности для выбора в смете."),
    "needs_price": ("Без цены", "Материалы без действующего предложения с положительной ценой."),
    "needs_classification": ("Требуют классификации", "Материалы без назначенной категории."),
    "needs_review": ("Требуют проверки", "Материалы в статусе черновика или ручной проверки."),
}


def _material_table_preset(value: str | None, default: str = "all") -> str:
    normalized = (value or default or "all").strip().lower().replace("-", "_")
    return normalized if normalized in MATERIAL_TABLE_PRESET_LABELS else default


def _material_table_presets(active_preset: str) -> list[dict[str, str | bool]]:
    return [
        {
            "key": key,
            "label": label,
            "description": description,
            "href": f"/api/v1/admin/material-hub/view/materials?preset={key}",
            "active": key == active_preset,
        }
        for key, (label, description) in MATERIAL_TABLE_PRESET_LABELS.items()
    ]


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
        return _humanize_material_field_key(template.field_key)
    return "Характеристика"


def _humanize_material_field_key(value: str | None) -> str:
    if not value:
        return "Характеристика"
    known_labels = {
        "length_mm": "Длина, мм",
        "width_mm": "Ширина, мм",
        "height_mm": "Высота, мм",
        "thickness_mm": "Толщина, мм",
        "density_class": "Марка плотности",
        "strength_class": "Класс прочности",
        "frost_resistance": "Морозостойкость",
        "sheet_area_m2": "Площадь листа, м²",
        "board_type": "Тип листа",
        "edge_type": "Тип кромки",
        "weight_kg": "Вес, кг",
        "sheets_per_pack": "Листов в упаковке",
        "application": "Применение",
    }
    key = str(value).strip()
    if key in known_labels:
        return known_labels[key]
    return key.replace("_", " ").replace("-", " ")


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
            "key": direction,
            "label": direction,
            "sources": sorted(items, key=lambda item: (item.priority, item.name)),
        }
        for direction, items in sorted(grouped.items(), key=lambda item: item[0])
    ]


def _source_category_options(sources: list[Source]) -> dict[str, list[dict[str, Any]]]:
    options: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        if source.status != SourceStatus.ACTIVE or is_first_wave_blocked_source(source):
            continue
        profile = get_extraction_profile(source.name)
        if not profile:
            continue
        source_options: list[dict[str, Any]] = []
        for group_code, filters in sorted(profile.category_mapping_rules.items()):
            if not filters:
                continue
            source_options.append({
                "label": group_code.replace("_", " "),
                "filters": list(filters),
            })
        if source_options:
            options[source.name] = source_options
    return options


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
        .limit(100)
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


async def _load_provider_work_cost_offer_rows(db: DBSession) -> list[dict[str, Any]]:
    result = await db.execute(
        select(ProviderWorkCostOffer)
        .options(selectinload(ProviderWorkCostOffer.owner))
        .order_by(ProviderWorkCostOffer.updated_at.desc())
        .limit(50)
    )
    offers = tuple(result.scalars().all())
    market_sanity = await build_provider_work_cost_market_sanity_map(db, offers)
    return [
        provider_work_cost_offer_to_dict(
            offer,
            market_sanity=market_sanity.get(str(offer.id)),
        )
        for offer in offers
    ]

async def _load_materials(db: DBSession, *, without_price: bool = False) -> list[Material]:
    statement = (
        select(Material)
        .options(
            selectinload(Material.category),
            selectinload(Material.subcategory),
            selectinload(Material.base_unit),
            selectinload(Material.attributes),
            selectinload(Material.material_type).selectinload(MaterialType.construction_group),
            selectinload(Material.documents),
            selectinload(Material.specifications).selectinload(MaterialSpecification.template),
            selectinload(Material.specifications).selectinload(MaterialSpecification.source),
        )
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .order_by(Material.created_at.desc())
    )
    if without_price:
        product_price = select(CatalogProduct.id).where(
            CatalogProduct.material_id == Material.id,
            CatalogProduct.status == CatalogProductStatus.ACTIVE,
            CatalogProduct.price > 0,
        ).exists()
        supplier_price = select(SupplierPrice.id).join(Supplier).where(
            SupplierPrice.material_id == Material.id,
            SupplierPrice.price > 0,
            Supplier.status != SupplierStatus.BLOCKED,
            or_(SupplierPrice.valid_until.is_(None), SupplierPrice.valid_until >= date.today()),
            or_(SupplierPrice.catalog_product_id.is_(None),
                SupplierPrice.catalog_product.has(CatalogProduct.status == CatalogProductStatus.ACTIVE)),
        ).exists()
        statement = statement.where(~product_price, ~supplier_price)
    else:
        statement = statement.limit(500)
    result = await db.execute(statement)
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
    priced_material_ids = select(PriceHistory.material_id).where(PriceHistory.price > 0).distinct()
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
        select(SourceTaskLog)
        .options(selectinload(SourceTaskLog.task).selectinload(SourceTask.source))
        .order_by(SourceTaskLog.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


async def _load_results(db: DBSession) -> list[SourceTaskResult]:
    result = await db.execute(
        select(SourceTaskResult)
        .options(selectinload(SourceTaskResult.task).selectinload(SourceTask.source))
        .order_by(SourceTaskResult.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


async def _load_source_candidates(db: DBSession) -> list[MaterialMatchCandidate]:
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
        .limit(50)
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
        .where(CatalogProduct.price > 0)
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


async def _load_material_price_map(db: DBSession, *, material_ids: list | None = None) -> dict[str, dict]:
    if material_ids == []:
        return {}
    product_query = (
        select(CatalogProduct)
        .options(selectinload(CatalogProduct.source))
        .where(CatalogProduct.material_id.is_not(None))
        .where(CatalogProduct.price.is_not(None))
        .where(CatalogProduct.price > 0)
        .where(CatalogProduct.status == CatalogProductStatus.ACTIVE)
        .where(CatalogProduct.material.has(Material.status != MaterialStatus.ARCHIVED))
        .where(CatalogProduct.material.has(Material.status != MaterialStatus.REJECTED))
        .order_by(CatalogProduct.price.asc())
    )
    if material_ids is not None:
        product_query = product_query.where(CatalogProduct.material_id.in_(material_ids))
    result = await db.execute(product_query)
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
            "updated_at": product.updated_at,
        }
    supplier_query = (
        select(SupplierPrice)
        .join(Supplier)
        .options(selectinload(SupplierPrice.supplier))
        .where(SupplierPrice.price > 0, Supplier.status != SupplierStatus.BLOCKED)
        .where(or_(SupplierPrice.valid_until.is_(None), SupplierPrice.valid_until >= date.today()))
        .where(or_(SupplierPrice.catalog_product_id.is_(None),
                   SupplierPrice.catalog_product.has(CatalogProduct.status == CatalogProductStatus.ACTIVE)))
        .order_by(SupplierPrice.price.asc())
    )
    if material_ids is not None:
        supplier_query = supplier_query.where(SupplierPrice.material_id.in_(material_ids))
    supplier_result = await db.execute(supplier_query)
    for price in supplier_result.scalars().all():
        key = str(price.material_id)
        if key not in prices:
            prices[key] = {
                "price": price.price, "currency": price.currency, "unit": price.unit,
                "source": price.supplier.name if price.supplier else "", "availability": price.availability,
                "region": price.region, "updated_at": price.updated_at,
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


def _document_type_label(document: MaterialDocument) -> str:
    return DOCUMENT_GROUP_LABELS.get(document.document_type.value, "\u0414\u0440\u0443\u0433\u043e\u0439 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442")


def _safe_material_name(value: str | None) -> str:
    if not value:
        return "\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d"
    return "\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u0438\u0441\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f" if "???" in value else value


def _document_material_label(document: MaterialDocument) -> str:
    if document.material:
        return _safe_material_name(document.material.canonical_name)
    if document.manufacturer:
        return f"\u041f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0438\u0442\u0435\u043b\u044c: {document.manufacturer.name}"
    return "\u041d\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d \u043a \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u0443"


def _document_material_category_label(document: MaterialDocument) -> str:
    if document.material and document.material.category:
        return document.material.category.name
    if document.manufacturer:
        return "\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0438\u0442\u0435\u043b\u044f"
    return "\u0422\u0440\u0435\u0431\u0443\u0435\u0442 \u043f\u0440\u0438\u0432\u044f\u0437\u043a\u0438"


def _document_supporting_org_label(document: MaterialDocument) -> str:
    if document.manufacturer:
        return document.manufacturer.name
    if document.material and document.material.manufacturer:
        return document.material.manufacturer
    if document.source:
        return _source_display_name(document.source)
    return "\u041e\u0440\u0433\u0430\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d\u0430"


def _document_confirms_label(document: MaterialDocument) -> str:
    return {
        "CERTIFICATE": "\u0421\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0438\u0435 \u0438 \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u043e",
        "DECLARATION": "\u0421\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0438\u0435 \u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d\u0438\u044f\u043c",
        "FIRE_CERTIFICATE": "\u041f\u043e\u0436\u0430\u0440\u043d\u0443\u044e \u0431\u0435\u0437\u043e\u043f\u0430\u0441\u043d\u043e\u0441\u0442\u044c",
        "SANITARY_CERTIFICATE": "\u0421\u0430\u043d\u0438\u0442\u0430\u0440\u043d\u043e\u0435 \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0438\u0435",
        "QUALITY_PASSPORT": "\u041f\u0430\u0441\u043f\u043e\u0440\u0442 \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u0430 \u043f\u0430\u0440\u0442\u0438\u0438",
        "TECH_CARD": "\u0425\u0430\u0440\u0430\u043a\u0442\u0435\u0440\u0438\u0441\u0442\u0438\u043a\u0438 \u0438 \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u0438\u0435",
        "INSTALLATION_GUIDE": "\u041f\u0440\u0430\u0432\u0438\u043b\u0430 \u043c\u043e\u043d\u0442\u0430\u0436\u0430",
        "TYPICAL_NODE": "\u0422\u0438\u043f\u043e\u0432\u043e\u0439 \u0443\u0437\u0435\u043b \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u0438\u044f",
        "ALBUM_OF_SOLUTIONS": "\u0421\u0438\u0441\u0442\u0435\u043c\u043d\u044b\u0435 \u0440\u0435\u0448\u0435\u043d\u0438\u044f",
        "BIM_MODEL": "\u0426\u0438\u0444\u0440\u043e\u0432\u0443\u044e \u043c\u043e\u0434\u0435\u043b\u044c",
        "VIDEO_GUIDE": "\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044e \u043f\u043e \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u0438\u044e",
        "TEST_REPORT": "\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u0438\u0441\u043f\u044b\u0442\u0430\u043d\u0438\u0439",
        "TECHNICAL_APPROVAL": "\u0422\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u0441\u0432\u0438\u0434\u0435\u0442\u0435\u043b\u044c\u0441\u0442\u0432\u043e",
    }.get(document.document_type.value, "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435 \u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438")


def _document_validity_label(document: MaterialDocument) -> str:
    if document.status == DocumentStatus.EXPIRED:
        return "\u0421\u0440\u043e\u043a \u0438\u0441\u0442\u0435\u043a"
    if document.expiry_date:
        if document.expiry_date < date.today():
            return "\u0421\u0440\u043e\u043a \u0438\u0441\u0442\u0435\u043a"
        return f"\u0414\u0435\u0439\u0441\u0442\u0432\u0443\u0435\u0442 \u0434\u043e {_format_datetime(document.expiry_date)}"
    return "\u0421\u0440\u043e\u043a \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d"


def _document_status_label(document: MaterialDocument) -> str:
    if document.status == DocumentStatus.ACTIVE:
        return "\u0414\u043e\u0441\u0442\u0443\u043f\u0435\u043d" if _document_has_safe_action(document) else "\u0415\u0441\u0442\u044c \u0437\u0430\u043f\u0438\u0441\u044c, \u0444\u0430\u0439\u043b \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d"
    if document.status == DocumentStatus.NEEDS_REVIEW:
        return "\u0422\u0440\u0435\u0431\u0443\u0435\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438"
    if document.status == DocumentStatus.EXPIRED:
        return "\u0421\u0440\u043e\u043a \u0438\u0441\u0442\u0435\u043a"
    if document.status == DocumentStatus.REJECTED:
        return "\u0415\u0441\u0442\u044c \u0437\u0430\u043c\u0435\u0447\u0430\u043d\u0438\u044f"
    if document.status == DocumentStatus.ARCHIVED:
        return "\u0410\u0440\u0445\u0438\u0432"
    return "\u0422\u0440\u0435\u0431\u0443\u0435\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438"


def _document_source_label(document: MaterialDocument) -> str:
    if document.source:
        return _source_display_name(document.source)
    if document.manufacturer:
        return document.manufacturer.name
    return "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d"


def _document_file_state_label(document: MaterialDocument) -> str:
    if _document_file_action_url(document):
        return "\u0424\u0430\u0439\u043b \u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d"
    if _document_source_action_url(document):
        return "\u0424\u0430\u0439\u043b \u043d\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d, \u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a"
    return "\u0424\u0430\u0439\u043b \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d"


def _safe_user_url(value: str | None, *, require_document: bool = False) -> str:
    if not value:
        return ""
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.scheme and not candidate.startswith("/"):
        return ""
    if require_document and parsed.scheme in {"http", "https"} and not is_document_url(candidate):
        return ""
    return candidate


def _document_file_action_url(document: MaterialDocument) -> str:
    return _safe_user_url(document.file_url, require_document=True)


def _document_source_action_url(document: MaterialDocument) -> str:
    return _safe_user_url(document.source_url, require_document=False)


def _document_has_safe_action(document: MaterialDocument) -> bool:
    return bool(_document_file_action_url(document) or _document_source_action_url(document))


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
