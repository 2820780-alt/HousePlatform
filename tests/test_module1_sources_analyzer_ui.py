from pathlib import Path


TEMPLATE = Path("templates/material_hub_sources_analyzer.html")
VIEW = Path("app/api/v1/material_hub_view.py")
DATA_TEMPLATE = Path("templates/material_hub_data.html")
OVERVIEW_TEMPLATE = Path("templates/material_hub_view.html")


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _view_text() -> str:
    return VIEW.read_text(encoding="utf-8")


def test_sources_analyzer_route_uses_dedicated_workspace_template() -> None:
    view = _view_text()

    assert '@router.get("/sources", response_class=HTMLResponse)' in view
    assert '"material_hub_sources_analyzer.html"' in view
    assert "_build_sources_analyzer_context" in view
    assert 'return await _render_data_page(request, db, False, "sources"' not in view


def test_workspace_has_four_internal_views_without_new_top_level_tabs() -> None:
    text = _template_text()

    for view in ["sources", "runs", "results", "errors"]:
        assert f'data-view-button="{view}"' in text
        assert f'data-view-panel="{view}"' in text
    for label in ["Источники", "Запуски", "Результаты", "Ошибки и предупреждения"]:
        assert label in text
    assert "view/material-hub/sources" not in text
    assert "data-main-tab" not in text


def test_sources_table_has_required_human_columns_and_read_only_settings() -> None:
    text = _template_text()

    expected = [
        "Источник",
        "Что получаем",
        "Регион",
        "Состояние",
        "Последняя проверка",
        "Последний результат",
        "Следующая проверка",
        "Действия",
        "Настройки",
    ]
    for label in expected:
        assert label in text
    assert "Открыть источник" in text
    assert "setSourceStatus" not in text
    assert "createSource" not in text
    assert "/api/v1/dev/material-hub" not in text


def test_run_results_and_error_tables_are_human_readable() -> None:
    text = _template_text() + _view_text()

    for label in [
        "Начало",
        "Завершение/длительность",
        "Обработано",
        "Ошибки/предупреждения",
        "Материалы и цены",
        "Документы/evidence",
        "Модерация/candidates",
        "Source health/logistics",
        "Цена не найдена; материал не готов",
    ]:
        assert label in text
    for link in [
        "/api/v1/admin/material-hub/view/materials?preset=all",
        "/api/v1/admin/material-hub/view/documents",
        "/api/v1/admin/material-hub/view/moderation",
    ]:
        assert link in text


def test_workspace_hides_raw_payload_ids_and_technical_details() -> None:
    text = _template_text()

    forbidden = [
        "source.id",
        "task.id",
        "entity_id",
        "UUID",
        "raw payload",
        "raw JSON",
        "parameters",
        "result_summary",
        "new_value",
        "stack trace",
        "traceback",
        "adapter class",
        "parser code",
        "technical enum",
        "source_code",
        "profile_code",
        "<code>",
        "Quick Actions",
        "Widgets",
        "WorkCost",
        "ATOM_REF",
        "reference_data",
    ]
    lowered = text.lower()
    for marker in forbidden:
        if marker.islower():
            assert marker not in lowered
        else:
            assert marker not in text


def test_workspace_has_required_filters_states_retry_and_pagination() -> None:
    text = _template_text()

    for marker in [
        "source-state-filter",
        "source-region-filter",
        "source-type-filter",
        "source-enabled-filter",
        "run-state-filter",
        "run-errors-filter",
        "result-type-filter",
        "result-price-filter",
        "error-type-filter",
        "error-state-filter",
        "resetWorkspaceFilters",
        "retryWorkspace",
        "changeWorkspacePage",
        "filtered-empty",
        "Загрузка источников...",
        "Не удалось загрузить источники.",
    ]:
        assert marker in text


def test_workspace_preferences_are_scoped_and_safe() -> None:
    text = _template_text()

    assert 'data-preference-namespace="module1.sources_analyzer"' in text
    assert 'workspacePreferenceKey = "atom:module1.sources_analyzer:v1"' in text
    for safe_key in ["selectedView", "density", "pageSize", "defaultSort", "wrapText", "filters"]:
        assert safe_key in text
    for unsafe_key in ["token", "password", "credential", "secret", "urlWithSecret", "taskPayload", "permissions"]:
        assert unsafe_key not in text


def test_price_gate_and_module_boundaries_are_not_reimplemented_in_template() -> None:
    text = _template_text()
    overview = OVERVIEW_TEMPLATE.read_text(encoding="utf-8")

    assert "Записи без положительной цены не считаются готовыми материалами." in text
    assert "price > 0" not in text
    assert "create_new_material" not in text
    assert "готовыми материалами" in text
    assert "work-cost-table" not in text
    assert "work_code" not in text
    assert "Запустить анализ" in overview
    assert "Запустить анализ" not in text


def test_old_data_template_keeps_legacy_sections_but_sources_route_no_longer_uses_them() -> None:
    data_text = DATA_TEMPLATE.read_text(encoding="utf-8")
    view = _view_text()

    assert 'id="source-table"' in data_text
    assert 'id="task-table"' in data_text
    assert 'view_mode in ["all", "sources"]' in data_text
    assert '"material_hub_sources_analyzer.html"' in view
    assert "_load_source_candidates" in view


def test_view_models_use_existing_loaders_and_safe_urls() -> None:
    view = _view_text()

    for function in [
        "def _build_sources_analyzer_context",
        "def _source_workspace_rows",
        "def _source_result_workspace_rows",
        "def _source_error_workspace_rows",
        "def _safe_external_url",
        "def _safe_domain",
    ]:
        assert function in view
    assert "selectinload(SourceTaskResult.task).selectinload(SourceTask.source)" in view
    assert "selectinload(SourceTaskLog.task).selectinload(SourceTask.source)" in view
    assert 'parsed.scheme not in {"http", "https"}' in view