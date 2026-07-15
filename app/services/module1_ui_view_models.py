from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.module1_alternatives_analogs import build_alternative_readiness_report
from app.services.module1_canonical_material_store import MaterialCanonicalView, list_canonical_materials
from app.services.module1_compatibility_matrix import build_compatibility_readiness_report
from app.services.module1_data_quality_dashboard import (
    build_data_quality_dashboard_report,
    build_material_quality_snapshot,
)
from app.services.module1_documents_evidence import build_document_package
from app.services.module1_export_packages import build_export_readiness_report, build_material_export_bundle
from app.services.module1_extraction_workbench import build_extraction_workbench_report, build_workbench_input
from app.services.module1_golden_materials import (
    build_golden_canonical_view,
    build_golden_material_export_preview,
    list_golden_materials,
    validate_golden_material,
)
from app.services.module1_material_roles import build_material_role_readiness_report
from app.services.module1_participants_directory import build_participant_directory_package
from app.services.module1_price_work_observations import build_price_observation_package
from app.services.module1_technical_profile_packaging import build_material_technical_profile


STATUS_LABELS = {
    "active": "Активен",
    "approved": "Проверен",
    "auto_created": "Создан автоматически",
    "blocked": "Заблокировано",
    "draft": "Черновик",
    "fixture": "Эталон",
    "missing": "Не хватает данных",
    "mapped": "Сопоставлено",
    "ignored": "Не используется",
    "needs_more_data": "Не хватает данных",
    "needs_moderation": "Требует модерации",
    "needs_review": "Требует проверки",
    "ok": "В порядке",
    "pending": "Ожидает",
    "ready": "Готово",
    "ready_for_export": "Готов к предпросмотру",
    "ready_for_module2": "Готовность к расчетам",
    "verified": "Проверен",
    "unknown": "Не распознано",
}

READINESS_LABELS = {
    "blocked": "Есть блокирующие проблемы",
    "insufficient_quality": "Недостаточно качества данных",
    "missing_alternative_fields": "Не хватает данных для аналогов",
    "missing_compatibility_fields": "Не хватает данных совместимости",
    "missing_data": "Не хватает данных",
    "missing_positive_price": "Нет положительной цены",
    "missing_role_fields": "Не хватает данных для ролей",
    "needs_moderation": "Требует модерации",
    "needs_more_data": "Не хватает данных",
    "no_alternative_rules": "Правила аналогов не заданы",
    "no_compatibility_rules": "Правила совместимости не заданы",
    "no_documents": "Документы не привязаны",
    "no_participants": "Участники не указаны",
    "no_roles": "Роли применения не заданы",
    "ready": "Готово",
    "ready_for_alternative_evaluation": "Готово к оценке аналогов",
    "ready_for_compatibility_evaluation": "Готово к проверке совместимости",
    "ready_for_export": "Готов к предпросмотру",
    "ready_for_module2": "Готовность к расчетам",
    "roles_ready": "Роли определены",
}

ISSUE_LABELS = {
    "document_links_not_downloaded": "Документы не скачиваются автоматически",
    "invalid_unit": "Неизвестная единица измерения",
    "missing_brand": "Не указан бренд",
    "missing_category": "Не указана категория",
    "missing_characteristics": "Не указаны характеристики",
    "missing_document_link": "Не хватает ссылки на документ",
    "missing_manufacturer": "Не указан производитель",
    "missing_module2_field": "Не хватает поля для расчетов",
    "missing_packaging_field": "Не хватает данных упаковки",
    "missing_price": "Нет наблюдения цены",
    "missing_positive_price_observation": "Нет положительного наблюдения цены",
    "missing_region": "Не указан регион",
    "missing_required_characteristic": "Не хватает обязательной характеристики",
    "missing_required_document": "Не хватает обязательного документа",
    "missing_source_ref": "Нет источника подтверждения",
    "missing_supplier": "Не указан поставщик",
    "pending_moderation": "Требует модерации",
    "possible_duplicate": "Возможный дубль",
}

DIMENSION_LABELS = {
    "alternatives": "Альтернативы и аналоги",
    "characteristics": "Характеристики",
    "classification": "Классификация",
    "compatibility": "Совместимость",
    "documents": "Документы",
    "export_readiness": "Экспортные пакеты",
    "identity": "Основная информация",
    "moderation": "Модерация",
    "packaging": "Упаковка",
    "participants": "Участники",
    "price_observations": "Наблюдения цен",
    "roles": "Роли применения",
    "source_provenance": "Источники",
    "technical_profile": "Технический профиль",
}

CODE_LABELS = {
    "aerated_concrete_block": "Газоблок",
    "board": "Доска",
    "deep_penetration_primer": "Грунтовка глубокого проникновения",
    "flexible_shingle": "Гибкая черепица",
    "gypsum_board_moisture_resistant": "ГКЛ влагостойкий",
    "gypsum_plaster": "Гипсовая штукатурка",
    "metal_tile": "Металлочерепица",
    "mineral_wool_slab": "Минераловатный утеплитель",
    "porcelain_tile": "Керамогранит",
    "ready_mix_concrete": "Бетон",
    "rebar": "Арматура",
    "title": "Наименование",
    "category": "Категория",
    "price": "Цена",
    "unit": "Единица измерения",
    "manufacturer": "Производитель",
    "region": "Регион",
    "characteristics": "Характеристики",
    "length_mm": "Длина, мм",
    "width_mm": "Ширина, мм",
    "height_mm": "Высота, мм",
    "density_class": "Марка плотности",
    "strength_class": "Класс прочности",
    "frost_resistance": "Морозостойкость",
    "thermal_conductivity": "Теплопроводность",
    "pieces_per_m3": "Штук в м³",
    "volume_per_piece_m3": "Объем штуки, м³",
    "weight_per_piece_kg": "Вес штуки, кг",
    "pieces_per_pallet": "Штук на поддоне",
    "package_unit": "Единица упаковки",
}
SEVERITY_LABELS = {
    "critical": "Критично",
    "high": "Высокая",
    "medium": "Средняя",
    "low": "Низкая",
    "info": "Информация",
}


def build_material_list_item_view(canonical_material_view: MaterialCanonicalView) -> Mapping[str, Any]:
    quality = build_material_quality_snapshot(canonical_material_view)
    export_readiness = build_export_readiness_report(canonical_material_view)
    group_code = _group_code(canonical_material_view)
    return {
        "materialId": canonical_material_view.material_id,
        "title": canonical_material_view.canonical_name or "Материал без названия",
        "category": _label_from_mapping(canonical_material_view.category) or _humanize_code(group_code),
        "group": _humanize_code(group_code),
        "status": translate_module1_status(canonical_material_view.status or canonical_material_view.moderation_status),
        "moderationStatus": translate_module1_status(canonical_material_view.moderation_status),
        "qualityScore": quality.overall_quality_score,
        "qualityTone": _quality_tone(quality.overall_quality_score),
        "readiness": translate_module1_readiness(quality.readiness_status),
        "readyForModule2": bool(quality.module2_readiness.get("ready")),
        "readyForModule5": bool(quality.module5_readiness_hint.get("readyHint")),
        "warningCount": len(quality.issues) + len(canonical_material_view.warnings),
        "warnings": tuple(_trim_text(warning) for warning in canonical_material_view.warnings[:3]),
    }


def build_material_quality_view(canonical_material_view: MaterialCanonicalView) -> Mapping[str, Any]:
    snapshot = build_material_quality_snapshot(canonical_material_view)
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for issue in snapshot.issues:
        grouped.setdefault(issue.dimension, []).append(translate_module1_issue(issue))
    return {
        "materialId": snapshot.material_id,
        "title": snapshot.material_name,
        "score": snapshot.overall_quality_score,
        "status": translate_module1_readiness(snapshot.readiness_status),
        "readinessStatus": snapshot.readiness_status,
        "issues": tuple(translate_module1_issue(issue) for issue in snapshot.issues[:8]),
        "issuesByDimension": tuple(
            {
                "dimension": DIMENSION_LABELS.get(dimension, _humanize_code(dimension)),
                "issues": tuple(items),
            }
            for dimension, items in sorted(grouped.items(), key=lambda item: item[0])
        ),
        "actionHints": tuple(
            {
                "title": _trim_text(hint.title),
                "dimension": DIMENSION_LABELS.get(hint.dimension, _humanize_code(hint.dimension)),
                "safeToAutoApply": hint.safe_to_auto_apply,
            }
            for hint in snapshot.action_hints[:6]
        ),
        "module2Readiness": {
            "label": "Готовность к расчетам" if snapshot.module2_readiness.get("ready") else "Не хватает данных",
            "ready": bool(snapshot.module2_readiness.get("ready")),
            "missingFields": tuple(_humanize_code(item) for item in snapshot.module2_readiness.get("missingFields", tuple())),
            "calculationPerformed": False,
        },
        "module5Readiness": {
            "label": "Готово для выбора в смете" if snapshot.module5_readiness_hint.get("readyHint") else "Нужны цена или участник",
            "readyHint": bool(snapshot.module5_readiness_hint.get("readyHint")),
            "estimateCalculated": False,
        },
        "exportReadiness": {
            "label": "Готов к предпросмотру" if snapshot.export_readiness.get("ready") else "Не хватает данных",
            "ready": bool(snapshot.export_readiness.get("ready")),
            "blockingIssueCount": snapshot.export_readiness.get("blockingIssueCount", 0),
            "autoFixApplied": False,
        },
        "warnings": tuple(_trim_text(warning) for warning in snapshot.warnings[:6]),
    }


def build_material_export_preview_view(canonical_material_view: MaterialCanonicalView) -> Mapping[str, Any]:
    bundle = build_material_export_bundle(canonical_material_view)
    return {
        "materialId": canonical_material_view.material_id,
        "title": canonical_material_view.canonical_name or "Материал без названия",
        "packages": (
            _package_row("clean_material", "Чистая карточка материала", bundle.clean_material.quality_score, bundle.clean_material.readiness_status),
            _package_row("technical_profile", "Технический профиль и упаковка", len(bundle.technical_profile.technical_characteristics), bundle.technical_profile.calculation_readiness.get("status")),
            _package_row("selector_package", "Данные для выбора материала", len(bundle.selector_package.allowed_roles), bundle.selector_package.quality_readiness.get("readinessStatus")),
            _package_row("module2_package", "Подсказка для Module №2", len(bundle.module2_package.missing_fields), "ready" if not bundle.module2_package.missing_fields else "missing_data"),
            _package_row("module5_package", "Подсказка для Module №5", len(bundle.module5_package.price_observation_refs), "ready" if bundle.module5_package.price_observation_refs else "missing_data"),
            _package_row("module11_signals", "Сигналы для аналитики", bundle.module11_signals.price_observation_count, bundle.module11_signals.readiness_status),
            _package_row("export_bundle", "Сводный пакет предпросмотра", int(bundle.validation_report.is_valid), "ready" if bundle.validation_report.is_valid else "blocked"),
        ),
        "readiness": {
            "module2": bundle.export_readiness_report.ready_for_module2,
            "module5": bundle.export_readiness_report.ready_for_module5_selection,
            "qualityReview": bundle.export_readiness_report.ready_for_quality_review,
            "label": "Готов к предпросмотру" if bundle.validation_report.is_valid else "Требует проверки",
        },
        "warnings": tuple(_trim_text(warning) for warning in bundle.export_readiness_report.warnings[:6]),
        "noFileGeneration": True,
        "noSideEffects": bundle.no_side_effects,
    }


def build_material_detail_view(canonical_material_view: MaterialCanonicalView) -> Mapping[str, Any]:
    technical_profile = build_material_technical_profile(canonical_material_view)
    role_report = build_material_role_readiness_report(technical_profile)
    alternative_report = build_alternative_readiness_report(technical_profile)
    compatibility_report = build_compatibility_readiness_report(technical_profile)
    document_package = build_document_package(canonical_material_view)
    participant_package = build_participant_directory_package(canonical_material_view)
    price_package = build_price_observation_package(canonical_material_view)
    return {
        "summary": build_material_list_item_view(canonical_material_view),
        "mainInfo": {
            "name": canonical_material_view.canonical_name or "Материал без названия",
            "category": _label_from_mapping(canonical_material_view.category),
            "subcategory": _label_from_mapping(canonical_material_view.subcategory),
            "group": _humanize_code(_group_code(canonical_material_view)),
            "baseUnit": technical_profile.base_unit or "не указана",
            "status": translate_module1_status(canonical_material_view.status),
        },
        "characteristics": tuple(
            {
                "name": _humanize_code(item.name),
                "value": _format_value(item.value),
                "unit": item.unit,
                "verificationStatus": translate_module1_status(item.verification_status),
            }
            for item in canonical_material_view.characteristics[:10]
        ),
        "technicalProfile": {
            "status": translate_module1_readiness(technical_profile.readiness.status),
            "readyForModule2": technical_profile.readiness.ready_for_module2,
            "readyForEstimateSelection": technical_profile.readiness.ready_for_estimate_selection,
            "missingFields": tuple(_humanize_code(item) for item in technical_profile.readiness.missing_required_fields[:8]),
            "module2MissingFields": tuple(_humanize_code(item) for item in technical_profile.missing_module2_fields[:8]),
        },
        "packaging": {
            "unit": technical_profile.packaging_profile.package_unit,
            "piecesPerPackage": technical_profile.packaging_profile.pieces_per_package,
            "piecesPerPallet": technical_profile.packaging_profile.pieces_per_pallet,
            "packageWeight": technical_profile.packaging_profile.package_weight,
            "packageVolume": technical_profile.packaging_profile.package_volume,
            "packageArea": technical_profile.packaging_profile.package_area,
            "missingFields": tuple(_humanize_code(item) for item in technical_profile.packaging_profile.missing_fields[:8]),
        },
        "roles": {
            "status": translate_module1_readiness(role_report.status),
            "primary": tuple(_humanize_code(item) for item in role_report.primary_roles[:5]),
            "conditional": tuple(_humanize_code(item) for item in role_report.conditional_roles[:5]),
            "missingFields": tuple(
                {"role": _humanize_code(role), "fields": tuple(_humanize_code(field) for field in fields)}
                for role, fields in list(role_report.missing_fields_by_role.items())[:5]
            ),
        },
        "alternatives": {
            "status": translate_module1_readiness(alternative_report.status),
            "allowedTargetGroups": tuple(_humanize_code(item) for item in alternative_report.allowed_target_groups[:6]),
            "forbiddenTargetGroups": tuple(_humanize_code(item) for item in alternative_report.forbidden_target_groups[:6]),
            "missingFields": tuple(_humanize_code(item) for item in alternative_report.missing_fields[:6]),
        },
        "compatibility": {
            "status": translate_module1_readiness(compatibility_report.status),
            "allowedContexts": tuple(_humanize_code(item) for item in compatibility_report.allowed_contexts[:6]),
            "forbiddenContexts": tuple(_humanize_code(item) for item in compatibility_report.forbidden_contexts[:6]),
            "missingFields": tuple(_humanize_code(item) for item in compatibility_report.missing_fields[:6]),
        },
        "documents": {
            "status": translate_module1_readiness(document_package.readiness.status),
            "count": len(document_package.documents),
            "items": tuple({"title": item.title, "type": _humanize_code(item.document_type), "status": translate_module1_status(item.status)} for item in document_package.documents[:5]),
            "missingHints": tuple(_humanize_code(item) for item in document_package.missing_document_hints[:5]),
        },
        "participants": {
            "status": translate_module1_readiness(participant_package.readiness.status),
            "count": len(participant_package.participants),
            "items": tuple({"name": item.display_name, "type": _humanize_code(item.participant_type)} for item in participant_package.participants[:5]),
        },
        "priceObservations": {
            "status": translate_module1_readiness(price_package.readiness.status),
            "count": len(price_package.observations),
            "items": tuple(
                {
                    "price": _format_value(item.price_value),
                    "currency": item.currency,
                    "unit": item.unit_info.normalized_unit or item.unit_info.raw_unit,
                    "region": _region_label(item.region),
                }
                for item in price_package.observations[:5]
            ),
        },
        "quality": build_material_quality_view(canonical_material_view),
        "exportPreview": build_material_export_preview_view(canonical_material_view),
    }


def build_golden_materials_view(*, limit: int | None = None) -> Mapping[str, Any]:
    records = list_golden_materials()
    if limit is not None:
        records = records[:limit]
    rows = []
    for record in records:
        validation = validate_golden_material(record)
        canonical_view = build_golden_canonical_view(record.golden_material_code)
        quality = build_material_quality_snapshot(canonical_view)
        export_preview = build_golden_material_export_preview(record.golden_material_code)
        rows.append(
            {
                "code": record.golden_material_code,
                "title": record.display_name,
                "group": _humanize_code(record.group_code),
                "baseUnit": record.base_unit,
                "validationStatus": "Проверен" if validation.is_valid else "Требует проверки",
                "qualityScore": quality.overall_quality_score,
                "exportPreviewReady": validation.export_preview_available and export_preview.no_side_effects,
                "warnings": tuple(_trim_text(warning) for warning in validation.warnings[:3]),
            }
        )
    reports = tuple(validate_golden_material(record) for record in records)
    return {
        "title": "Эталонные материалы",
        "total": len(records),
        "valid": sum(1 for report in reports if report.is_valid),
        "items": tuple(rows),
        "readOnly": True,
        "noDatabaseWrites": True,
    }


def build_workbench_preview_view(
    raw_payload: Mapping[str, Any] | None = None,
    *,
    source_profile_code: str | None = "YUFO_VKBLOCK",
    extraction_profile_code: str | None = "yufo_vkblock_extraction_profile",
    material_group: str | None = "aerated_concrete_block",
    canonical_material_view: MaterialCanonicalView | None = None,
) -> Mapping[str, Any]:
    payload = raw_payload or {
        "sourceCode": source_profile_code,
        "title": "Газоблок D500 B2.5 600x300x200",
        "category": "Газобетон",
        "price": "4200",
        "unit": "м3",
        "manufacturer": "VKBlock",
        "region": "Краснодарский край",
        "characteristics": {
            "length_mm": 600,
            "width_mm": 300,
            "height_mm": 200,
            "density_class": "D500",
            "strength_class": "B2.5",
        },
        "documentLinks": ["https://example.test/certificate.pdf"],
    }
    workbench_input = build_workbench_input(
        payload,
        source_profile_code=source_profile_code,
        extraction_profile_code=extraction_profile_code,
        material_group=material_group,
    )
    report = build_extraction_workbench_report(workbench_input, canonical_material_view=canonical_material_view)
    return {
        "title": "Лаборатория извлечения",
        "sampleTitle": _trim_text(payload.get("title") or "Сырой пример без названия"),
        "source": _trim_text(source_profile_code or payload.get("sourceCode") or "источник не указан"),
        "materialGroup": _humanize_code(material_group or payload.get("materialGroup")),
        "fieldTrace": tuple(
            {
                "field": _humanize_code(trace.raw_field),
                "mappedTo": _humanize_code(trace.mapped_field) if trace.mapped_field else "не распознано",
                "status": translate_module1_status(trace.status),
            }
            for trace in report.field_traces[:8]
        ),
        "validationIssues": tuple(translate_module1_issue(issue) for issue in report.validation_issues[:6]),
        "normalization": {
            "status": translate_module1_status(report.pipeline_preview.normalized_candidate_preview.get("status")),
            "suggestedGroup": _humanize_code(
                _nested_get(report.pipeline_preview.normalized_candidate_preview, "candidate", "suggested_group_code")
                or _nested_get(report.pipeline_preview.normalized_candidate_preview, "candidate", "suggestedGroupCode")
            ),
        },
        "matching": {
            "createsLink": bool((report.pipeline_preview.matching_preview or {}).get("createsLink")),
            "mergesDuplicate": bool((report.pipeline_preview.matching_preview or {}).get("mergesDuplicate")),
            "label": "Предпросмотр совпадений без объединения",
        },
        "moderation": {
            "decisionApplied": bool((report.pipeline_preview.moderation_preview or {}).get("decisionApplied")),
            "label": "Решение модерации не применяется",
        },
        "actionHints": tuple(
            {
                "title": _trim_text(hint.title),
                "safeToAutoApply": hint.safe_to_auto_apply,
            }
            for hint in report.action_hints[:5]
        ),
        "noHttp": True,
        "noParsing": True,
        "noOcr": True,
        "noSideEffects": report.no_side_effects,
    }


def build_module1_ui_preview_context(
    *,
    materials: Iterable[Any] | None = None,
    golden_limit: int = 4,
) -> Mapping[str, Any]:
    material_views = list_canonical_materials(materials=materials or ())
    if not material_views:
        material_views = tuple(
            build_golden_canonical_view(record.golden_material_code)
            for record in list_golden_materials()[:golden_limit]
        )
    material_views = material_views[:golden_limit]
    quality_report = build_data_quality_dashboard_report(material_views)
    first_view = material_views[0] if material_views else None
    return {
        "sections": (
            "Материалы",
            "Качество данных",
            "Документы",
            "Участники",
            "Наблюдения цен",
            "Лаборатория извлечения",
            "Эталонные материалы",
            "Экспортные пакеты",
        ),
        "materials": tuple(build_material_list_item_view(view) for view in material_views),
        "selectedMaterial": build_material_detail_view(first_view) if first_view else None,
        "quality": {
            "total": quality_report.total_materials_checked,
            "readiness": tuple(
                {
                    "label": translate_module1_readiness(status),
                    "count": count,
                }
                for status, count in quality_report.count_by_readiness_status.items()
            ),
            "severity": tuple(
                {
                    "label": SEVERITY_LABELS.get(severity, _humanize_code(severity)),
                    "count": count,
                }
                for severity, count in quality_report.count_by_severity.items()
            ),
            "topIssues": tuple(translate_module1_issue(issue) for issue in quality_report.top_blocking_issues[:5]),
            "autoFixApplied": False,
        },
        "workbench": build_workbench_preview_view(canonical_material_view=first_view),
        "goldenMaterials": build_golden_materials_view(limit=golden_limit),
        "exportPreview": build_material_export_preview_view(first_view) if first_view else None,
        "readOnly": True,
        "noDatabaseWrites": True,
    }


def translate_module1_status(status: Any) -> str:
    raw = _normalized_code(status)
    if not raw:
        return "не указано"
    return STATUS_LABELS.get(raw, _humanize_code(raw))


def translate_module1_issue(issue: Any) -> Mapping[str, Any]:
    issue_type = _normalized_code(_read(issue, "issue_type", "issueType")) or "issue"
    severity = _normalized_code(_read(issue, "severity")) or "info"
    dimension = _normalized_code(_read(issue, "dimension")) or "quality"
    message = _trim_text(_read(issue, "message") or "")
    return {
        "title": ISSUE_LABELS.get(issue_type, _humanize_code(issue_type)),
        "severity": SEVERITY_LABELS.get(severity, _humanize_code(severity)),
        "severityCode": severity,
        "dimension": DIMENSION_LABELS.get(dimension, _humanize_code(dimension)),
        "field": _humanize_code(_read(issue, "field")) if _read(issue, "field") else None,
        "message": message or ISSUE_LABELS.get(issue_type, _humanize_code(issue_type)),
    }


def translate_module1_readiness(readiness: Any) -> str:
    raw = _normalized_code(readiness)
    if not raw:
        return "не указано"
    return READINESS_LABELS.get(raw, STATUS_LABELS.get(raw, _humanize_code(raw)))


def _package_row(code: str, title: str, value: Any, readiness: Any) -> Mapping[str, Any]:
    return {
        "code": code,
        "title": title,
        "value": value,
        "readiness": translate_module1_readiness(readiness),
        "noFileGeneration": True,
    }


def _group_code(canonical_material_view: MaterialCanonicalView) -> str | None:
    group = canonical_material_view.group or {}
    return _read(group, "code", "slug", "name")


def _label_from_mapping(value: Mapping[str, Any] | None) -> str | None:
    if not value:
        return None
    return _trim_text(value.get("displayName") or value.get("name") or value.get("title") or value.get("slug") or value.get("code"))


def _quality_tone(score: int) -> str:
    if score >= 80:
        return "ok"
    if score >= 55:
        return "warn"
    return "danger"


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return _trim_text(value)


def _region_label(value: Any) -> str:
    parts = tuple(
        part
        for part in (
            _read(value, "region"),
            _read(value, "city"),
            _read(value, "country"),
        )
        if part
    )
    return ", ".join(str(part) for part in parts)

def _read(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    for name in names:
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _nested_get(mapping: Mapping[str, Any], *names: str) -> Any:
    value: Any = mapping
    for name in names:
        if not isinstance(value, Mapping):
            return None
        value = value.get(name)
    return value


def _trim_text(value: Any, *, max_length: int = 140) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _normalized_code(value: Any) -> str:
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw).strip().replace("-", "_").lower()


def _humanize_code(value: Any) -> str:
    raw = _normalized_code(value)
    if not raw:
        return ""
    return CODE_LABELS.get(raw, " ".join(part for part in raw.replace("/", "_").split("_") if part))
