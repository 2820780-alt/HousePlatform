from pathlib import Path


SHELL = Path("templates/_module1_shell.html")
OVERVIEW = Path("templates/material_hub_view.html")
DATA = Path("templates/material_hub_data.html")
DOCUMENTS = Path("templates/material_hub_documents.html")
WORK_COSTS = Path("templates/material_hub_work_costs.html")
SOURCES = Path("templates/material_hub_sources_analyzer.html")
MODERATION = Path("templates/material_hub_moderation.html")
VIEW = Path("app/api/v1/material_hub_view.py")
ADMIN_API = Path("app/api/v1/admin_material_hub.py")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_shared_shell_has_fixed_six_tabs_in_order() -> None:
    text = read(SHELL)
    expected = [
        ("overview", "Обзор", "/api/v1/admin/material-hub/view"),
        ("materials", "Материалы", "/api/v1/admin/material-hub/view/materials"),
        ("documents", "Документы и технические данные", "/api/v1/admin/material-hub/view/documents"),
        ("work-costs", "Стоимость работ", "/api/v1/admin/material-hub/view/work-costs"),
        ("sources", "Источники и анализатор", "/api/v1/admin/material-hub/view/sources"),
        ("moderation", "Модерация и качество", "/api/v1/admin/material-hub/view/moderation"),
    ]
    positions = []
    for key, label, route in expected:
        marker = f'data-module1-tab="{key}"'
        assert marker in text
        assert label in text
        assert route in text
        positions.append(text.index(marker))
    assert positions == sorted(positions)
    assert text.count("data-module1-tab=") == 6
    assert "data-main-tab" not in text
    assert "data-quick-action" not in text


def test_all_six_workspaces_use_shared_shell_with_single_module_nav() -> None:
    workspaces = {
        DATA: "materials",
        DOCUMENTS: "documents",
        WORK_COSTS: "work-costs",
        SOURCES: "sources",
        MODERATION: "moderation",
        OVERVIEW: "overview",
    }
    for path, tab in workspaces.items():
        text = read(path)
        assert '{% from "_module1_shell.html" import module1_shell %}' in text
        assert f'module1_shell("{tab}"' in text
        assert text.count('module1_shell("') == 1


def test_overview_contains_only_launch_and_widgets_area() -> None:
    text = read(OVERVIEW)

    assert 'data-analyzer-launch' in text
    assert "Запустить анализ" in text
    assert 'data-module1-widgets' in text
    assert "Виджеты пока не добавлены" in text
    assert "Здесь появятся выбранные показатели Module №1" in text
    forbidden = [
        "dashboard_cards",
        "module1_ui_preview",
        "pending_candidates_total",
        "supplier_workspace_summary",
        "supplier_cards",
        "work_rates_workspace_summary",
        "atom-module-quick-actions",
        "data-quick-action",
        "_atom_quick_action_menu.html",
        "/api/v1/dev/material-hub/run-batch",
        "/api/v1/dev/material-hub/upload-supplier-file",
        "work-cost-table",
        "document-table",
        "moderation-table",
        "material-table",
        "SourceTaskResult",
        "ATOM_REF",
        "reference_data",
        "raw payload",
        "<code>",
    ]
    for marker in forbidden:
        assert marker not in text


def test_overview_settings_are_safe_and_not_credentials_or_adapter_details() -> None:
    text = read(OVERVIEW)
    view = read(VIEW)

    for marker in [
        "data-source-kind",
        "collection-object",
        "processing-scenario",
        "scan-mode",
        "write-mode",
        "source-direction",
        "source-category-filter",
        "max-pages",
        "max-documents",
    ]:
        assert marker in text
    assert 'if value != "FILE"' in view
    assert 'if value != "WORK_RATES"' in view
    for forbidden in ["password", "token", "cookie", "proxy", "adapter class", "CSS/XPath", "source.id"]:
        assert forbidden.lower() not in text.lower()


def test_overview_preferences_are_scoped_and_secret_free() -> None:
    text = read(OVERVIEW)

    assert 'module1.overview_analyzer_launch' in text
    assert 'overviewPreferenceKey = "atom:module1.overview_analyzer_launch:v1"' in text
    assert "localStorage" in text
    assert "sessionStorage" in text
    for safe_key in ["sourceNames", "dataSourceKind", "collectionObject", "processingScenario", "scanMode", "writeMode", "maxPages", "maxDocuments"]:
        assert safe_key in text
    for unsafe_key in ["credentials", "cookies", "tokens", "task results", "run history", "raw payload", "RBAC"]:
        assert unsafe_key not in text


def test_overview_launch_endpoint_uses_existing_service_and_rbac() -> None:
    api = read(ADMIN_API)

    assert '@router.post("/tasks/launch-overview"' in api
    assert "SourceTaskOverviewLaunchRequest" in api
    assert "_check_admin(user)" in api
    assert "run_source_task(db, task.id)" in api
    assert "attach_source_profile_snapshot" in api
    assert "OVERVIEW_ALLOWED_SETTING_KEYS" in api
    assert "is_first_wave_blocked_source" in api
    assert 'redirect_url="/api/v1/admin/material-hub/view/sources"' in api
    assert "password" not in api.lower()
    assert "token" not in api.lower()


def test_overview_does_not_show_run_ids_progress_or_history() -> None:
    text = read(OVERVIEW)

    forbidden = [
        "task.id",
        "run_id",
        "source_task_result_id",
        "progress",
        "processed count",
        "history",
        "traceback",
        "stack trace",
        "result_summary",
        "Ошибка запуска:",
    ]
    lowered = text.lower()
    for marker in forbidden:
        assert marker.lower() not in lowered
    assert "Перейти в Источники и анализатор" in text


def test_widget_area_is_separate_from_quick_actions_and_dashboard_cards() -> None:
    text = read(OVERVIEW)

    assert 'data-module1-widgets' in text
    assert 'data-module1-widgets-empty' in text
    assert "quick action" not in text.lower()
    assert "data-quick-action" not in text
    assert "dashboard" not in text.lower()
    assert "materials-kpi" not in text
    assert "classification-queue" not in text
    assert "source-health" not in text


def test_routes_for_six_tabs_are_preserved_without_redirect_loops() -> None:
    view = read(VIEW)

    for marker in [
        '@router.get("", response_class=HTMLResponse)',
        '@router.get("/materials", response_class=HTMLResponse)',
        '@router.get("/documents", response_class=HTMLResponse)',
        '@router.get("/work-costs", response_class=HTMLResponse)',
        '@router.get("/sources", response_class=HTMLResponse)',
        '@router.get("/moderation", response_class=HTMLResponse)',
    ]:
        assert marker in view
    assert "RedirectResponse" not in view