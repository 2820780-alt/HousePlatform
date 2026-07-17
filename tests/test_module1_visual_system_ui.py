from pathlib import Path


SHELL = Path("templates/_module1_shell.html")
VISUAL = Path("templates/_module1_visual_system.html")
OVERVIEW = Path("templates/material_hub_view.html")
DATA = Path("templates/material_hub_data.html")
DOCUMENTS = Path("templates/material_hub_documents.html")
WORK_COSTS = Path("templates/material_hub_work_costs.html")
SOURCES = Path("templates/material_hub_sources_analyzer.html")
MODERATION = Path("templates/material_hub_moderation.html")
TOPBAR = Path("templates/_atom_platform_topbar.html")
QUICK_ACTION_MENU = Path("templates/_atom_quick_action_menu.html")

WORKSPACES = {
    OVERVIEW: "overview",
    DATA: "materials",
    DOCUMENTS: "documents",
    WORK_COSTS: "work-costs",
    SOURCES: "sources",
    MODERATION: "moderation",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_visual_layer_is_shared_and_platform_topbar_not_copied() -> None:
    visual = read(VISUAL)
    shell = read(SHELL)
    topbar = read(TOPBAR)

    assert "--module1-page-bg" in visual
    assert "--module1-panel" in visual
    assert "--module1-cyan" in visual
    assert "--module1-row-height" in visual
    assert "body[data-module1-visual-system] main" in visual
    assert "module1-quick-actions-rail" in visual
    assert "atom-platform-topbar" in topbar
    assert "atom-platform-topbar" not in shell
    assert "atom-platform-logo" not in shell

    for template in WORKSPACES:
        text = read(template)
        assert '{% include "_module1_visual_system.html" %}' in text
        assert "data-module1-visual-system" in text
        assert text.count('{% from "_module1_shell.html" import module1_shell %}') == 1


def test_shell_has_exact_six_tabs_once_and_no_duplicate_title_band() -> None:
    shell = read(SHELL)
    tabs = [
        ("overview", "Обзор"),
        ("materials", "Материалы"),
        ("documents", "Документы и технические данные"),
        ("work-costs", "Стоимость работ"),
        ("sources", "Источники и анализатор"),
        ("moderation", "Модерация и качество"),
    ]
    positions = []
    for key, label in tabs:
        marker = f'data-module1-tab="{key}"'
        assert marker in shell
        assert label in shell
        positions.append(shell.index(marker))
    assert positions == sorted(positions)
    assert shell.count("data-module1-tab=") == 6
    assert "module1-shell-title" not in shell
    assert "module1-shell-mark" not in shell
    assert "module1-shell-subtitle" not in shell


def test_quick_actions_rail_uses_existing_user_module_contract() -> None:
    shell = read(SHELL)
    visual = read(VISUAL)

    assert '{% include "_atom_quick_action_menu.html" %}' in shell
    assert 'data-quick-action-module-bar="MODULE_01_MATERIAL_HUB"' in shell
    assert "data-module1-quick-actions-rail" in shell
    assert "Быстрые действия не настроены" in shell
    assert 'const RAIL_KEY = "module1.quick_actions_rail"' in visual
    assert "ATOMQuickActionMenu.loadModuleQuickActions" in visual
    assert "JSON.stringify({ collapsed: Boolean(collapsed) })" in visual
    assert "aria-expanded" in shell
    assert "data-quick-action-candidate" not in shell
    for forbidden in ["quick-action-run-source-analysis", "UPLOAD_SUPPLIER_PRICE", "OPEN_MATERIAL_MODERATION", "CHECK_SOURCE_CARDS"]:
        assert forbidden not in shell


def test_overview_keeps_only_launch_widgets_and_after_launch_note() -> None:
    overview = read(OVERVIEW)

    assert "data-analyzer-launch" in overview
    assert "Запустить анализ" in overview
    assert "data-module1-widgets" in overview
    assert "Виджеты пока не добавлены" in overview
    assert "data-overview-after-launch-note" in overview
    assert "/api/v1/admin/material-hub/view/sources" in overview
    for forbidden in [
        "dashboard_cards",
        "pending_candidates_total",
        "work_rates_workspace_summary",
        "SourceTaskResult",
        "result_summary",
        "run history",
        "/api/v1/dev/material-hub",
        "ATOM_REF",
        "reference_data",
        "data-quick-action-candidate",
    ]:
        assert forbidden not in overview


def test_workspaces_preserve_routes_and_do_not_mix_widgets_with_quick_actions() -> None:
    for path, active_tab in WORKSPACES.items():
        text = read(path)
        assert f'module1_shell("{active_tab}"' in text
        if path == OVERVIEW:
            assert "data-module1-widgets" in text
            assert "data-module1-widgets-empty" in text
        else:
            assert "data-module1-widgets" not in text
            assert "data-module1-widgets-empty" not in text

    visual = read(VISUAL)
    assert "WidgetRegistry" not in visual
    assert "dashboard_widget_registry" not in visual
    assert "quickActionRegistry" not in visual


def test_visual_responsive_and_accessibility_contracts_exist() -> None:
    visual = read(VISUAL)
    shell = read(SHELL)

    assert "@media (max-width: 1180px)" in visual
    assert "@media (max-width: 720px)" in visual
    assert "overflow-x: hidden" in visual
    assert "overflow-x: auto" in visual
    assert "focus-visible" in visual
    assert "aria-label=\"Быстрые действия Module №1\"" in shell
    assert "aria-label=\"Навигация Module №1\"" in shell
    assert "aria-expanded=\"true\"" in shell

def test_collapsed_rail_is_compact_and_has_no_vertical_title_text() -> None:
    visual = read(VISUAL)
    shell = read(SHELL)

    assert "--module1-rail-collapsed-width: 62px" in visual
    assert "writing-mode: vertical-rl" not in visual
    assert ".module1-quick-actions-rail.is-collapsed .module1-rail-title" in visual
    assert "clip: rect(0 0 0 0)" in visual
    assert "aria-controls=\"module1-quick-actions-content\"" in shell
    assert "id=\"module1-quick-actions-content\"" in shell
    assert "aria-expanded" in shell


def test_action_menus_are_compact_keyboard_accessible_and_used_on_dense_rows() -> None:
    visual = read(VISUAL)
    documents = read(DOCUMENTS)
    sources = read(SOURCES)
    moderation = read(MODERATION)

    assert "data-module1-action-menu" in documents
    assert "data-module1-action-menu" in sources
    assert "data-module1-action-menu" in moderation
    assert "module1-action-menu-panel" in visual
    assert "aria-haspopup" in visual
    assert "event.key !== \"Escape\"" in visual
    assert "closeActionMenu(openMenu, true)" in visual
    assert "role=\"menu\"" in documents
    assert "role=\"menuitem\"" in documents
    assert "Дополнительные действия документа" in documents
    assert "Дополнительные действия источника" in sources
    assert "Решения по позиции модерации" in moderation


def test_materials_table_actions_nowrap_and_local_overflow() -> None:
    data = read(DATA)

    assert ".table-scroll { max-height:70vh; overflow:auto; max-width:100%;" in data
    assert "table { width:100%; border-collapse:collapse; min-width:1120px; table-layout:fixed; }" in data
    assert "min-width:144px; width:144px" in data
    assert "white-space:nowrap" in data
    assert 'actions: "144px"' in data
    assert 'supplier_region: "162px"' in data
    assert 'unit_package: "130px"' in data


def test_work_cost_states_are_mutually_exclusive_in_template_js() -> None:
    work_costs = read(WORK_COSTS)

    assert "function setWorkCostViewState(state)" in work_costs
    assert "document.body.dataset.module1WorkCostState = state" in work_costs
    assert "state !== \"table\"" in work_costs
    assert "setWorkCostViewState(\"error\")" in work_costs
    assert "setWorkCostViewState(\"empty\")" in work_costs
    assert "setWorkCostViewState(\"filteredEmpty\")" in work_costs
    assert "setWorkCostViewState(\"table\")" in work_costs
    assert "work-cost-table-wrap" in work_costs
    assert "work-cost-pagination" in work_costs


def test_moderation_table_keeps_source_date_compact_and_actions_accessible() -> None:
    moderation = read(MODERATION)

    assert "Источник / дата" in moderation
    assert "#moderation-table { width:100%; min-width:1080px;" in moderation
    assert '#moderation-table [data-field="issue"] { width:22%; }' in moderation
    assert '#moderation-table [data-field="actions"] { width:15%; min-width:150px; }' in moderation
    assert "module1-action-primary" in moderation
    assert "data-module1-action-menu" in moderation
    assert "Нет положительной цены" in moderation


def test_typography_tokens_and_text_wrapping_contract_are_centralized() -> None:
    visual = read(VISUAL)
    data = read(DATA)
    sources = read(SOURCES)
    moderation = read(MODERATION)

    for token in [
        "--module1-font-body",
        "--module1-font-secondary",
        "--module1-font-label",
        "--module1-font-table-header",
        "--module1-font-button",
        "--module1-font-badge",
        "--module1-font-section-title",
        "--module1-font-card-title",
        "--module1-font-metric",
        "--module1-line-body",
        "--module1-line-badge",
    ]:
        assert token in visual

    assert "body[data-module1-visual-system] main th" in visual
    assert "word-break: normal !important" in visual
    assert "overflow-wrap: break-word" in visual
    assert "word-break: break-all" not in visual
    assert "overflow-wrap:anywhere" not in data
    assert "overflow-wrap:anywhere" not in sources
    assert "overflow-wrap:anywhere" not in moderation


def test_button_badge_and_table_polish_contracts_exist() -> None:
    visual = read(VISUAL)
    documents = read(DOCUMENTS)
    sources = read(SOURCES)
    moderation = read(MODERATION)
    work_costs = read(WORK_COSTS)

    assert "body[data-module1-visual-system] main button," in visual
    assert "white-space: nowrap !important" in visual
    assert "body[data-module1-visual-system] main button.secondary" in visual
    assert "body[data-module1-visual-system] main button.danger" in visual
    assert "body[data-module1-visual-system] main button:disabled" in visual
    assert "box-shadow: 0 8px 18px rgba(24, 215, 242, 0.10)" in visual
    assert ".module1-action-primary" in visual
    assert "min-width: max-content" in visual

    assert "body[data-module1-visual-system] main .badge" in visual
    assert "max-width: 190px" in visual
    assert "body[data-module1-visual-system] main .reason-list" in visual
    assert "grid-template-columns: 1fr" in visual
    assert ".reason-list { display:grid; grid-template-columns:1fr;" in moderation

    assert "table-layout:fixed" in documents
    assert "min-width:1080px" in sources
    assert "min-width:1080px" in moderation
    assert "min-width:84px; white-space:nowrap" in work_costs


def test_document_and_moderation_dense_text_has_safe_widths() -> None:
    documents = read(DOCUMENTS)
    moderation = read(MODERATION)

    assert ".doc-title { font-weight:700; color:var(--text); line-height:1.32;" in documents
    assert "word-break:normal" in documents
    assert ".actions { display:flex; gap:6px; flex-wrap:nowrap; align-items:center; min-width:140px; }" in documents
    assert '#moderation-table [data-field="data_state"] { width:11%; }' in moderation
    assert '#moderation-table [data-field="actions"] { width:15%; min-width:150px; }' in moderation
    assert "Требуется решение модератора" in moderation

def test_resizable_column_helper_is_accessible_and_persists_widths() -> None:
    visual = read(VISUAL)

    assert "function initResizableTables()" in visual
    assert "data-module1-resizable-ready" in visual
    assert "module1-column-resize-handle" in visual
    assert 'role", "separator"' in visual
    assert 'aria-orientation", "vertical"' in visual
    assert 'tabindex", "0"' in visual
    assert "Изменить ширину столбца" in visual
    assert "ArrowLeft" in visual
    assert "ArrowRight" in visual
    assert "event.shiftKey ? 32 : 12" in visual
    assert "Home" in visual
    assert "clampColumnWidth" in visual
    assert "columnLimit(field, \"min\")" in visual
    assert "columnLimit(field, \"max\")" in visual
    assert "column_widths" in visual
    assert "saveColumnWidth(table, field" in visual
    assert "event.stopPropagation()" in visual


def test_main_module1_tables_are_resizable_with_existing_namespaces() -> None:
    data = read(DATA)
    documents = read(DOCUMENTS)
    work_costs = read(WORK_COSTS)
    sources = read(SOURCES)
    moderation = read(MODERATION)

    assert 'id="material-table" data-preference-namespace="module1.materials_table"' in data
    assert 'id="document-table" data-preference-namespace="module1.documents_table"' in documents
    assert 'id="work-cost-table" data-preference-namespace="module1.work_costs_table"' in work_costs
    assert 'id="moderation-table" data-preference-namespace="module1.moderation_queue"' in moderation

    for view in ["sources", "runs", "results", "errors"]:
        assert f'data-module1-width-view="{view}"' in sources
    assert sources.count('data-module1-resizable-table data-preference-namespace="module1.sources_analyzer"') == 4
    assert 'data-module1-preference-key="atom:module1.sources_analyzer:v1"' in sources


def test_column_width_preferences_survive_visibility_and_filter_changes() -> None:
    data = read(DATA)
    documents = read(DOCUMENTS)
    work_costs = read(WORK_COSTS)
    sources = read(SOURCES)
    moderation = read(MODERATION)

    assert "column_widths: {}" in data
    assert "merged.column_widths" in data
    assert "merged.widths || {}" in data
    assert "column_widths: {}" in moderation
    assert "merged.column_widths" in moderation
    assert "const next = { ...current, ...(preferences || {}) }" in documents
    assert "column_widths: patch.column_widths || current.column_widths || {}" in work_costs
    assert "column_widths: patch.column_widths || current.column_widths || {}" in sources

    assert "function resetMaterialTableView()" in data
    assert "tablePreferenceStorage().removeItem(tableLayoutKey(\"material-table\"))" in data
    assert "function resetWorkCostView()" in work_costs
    assert "workCostStorage().removeItem(workCostPreferenceKey)" in work_costs
    assert "function resetMaterialFilters()" in data
    reset_material_body = data.split("function resetMaterialFilters()", 1)[1].split("}", 1)[0]
    assert "removeItem" not in reset_material_body
    assert "tableLayoutKey" not in reset_material_body
    reset_document_body = documents.split("function resetDocumentFilters()", 1)[1].split("}", 1)[0]
    assert "removeItem" not in reset_document_body
    assert "documentPreferenceKey" not in reset_document_body


def test_visual_composition_depth_and_quiet_buttons() -> None:
    visual = read(VISUAL)
    work_costs = read(WORK_COSTS)
    documents = read(DOCUMENTS)

    assert "Page background" not in visual
    assert "rgba(8, 16, 38, 0.62)" in visual
    assert "main .table-panel" in visual
    assert "main .filters" in visual
    assert "main thead tr" in visual
    assert 'button[onclick*="reset"]' in visual
    assert "main .pagination button" in visual
    assert "box-shadow: none !important" in visual
    assert "resetWorkCostView" in work_costs
    assert "Настроить вид" in documents

def test_quick_action_fallback_toast_is_temporary_and_non_secret() -> None:
    quick_actions = read(QUICK_ACTION_MENU)
    toast_block = quick_actions.split("function showToast(message)", 1)[1].split("function initQuickActionMenus", 1)[0]

    assert "const previous = document.querySelector(\".atom-quick-action-toast\")" in toast_block
    assert "window.setTimeout(() => toast.remove(), 2800)" in toast_block
    assert "Backend быстрых действий недоступен" in quick_actions
    for forbidden in ["stack trace", "traceback", "secret", "access token", "password"]:
        assert forbidden not in toast_block.lower()
