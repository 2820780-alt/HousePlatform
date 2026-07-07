from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_quick_action_context_menu_partial_declares_required_commands():
    html = read("templates/_atom_quick_action_menu.html")

    assert "data-quick-action-menu-command=\"add\"" in html
    assert "data-quick-action-menu-command=\"remove\"" in html
    assert "data-quick-action-menu-command=\"pin\"" in html
    assert "data-quick-action-menu-command=\"unpin\"" in html
    assert "data-quick-action-menu-command=\"rename\"" in html
    assert "Добавить в быстрые действия" in html
    assert "Убрать из быстрых действий" in html
    assert "Закрепить на карточке модуля" in html
    assert "Снять с карточки модуля" in html
    assert "Переименовать shortcut" in html


def test_quick_action_ui_commands_require_active_candidate_source():
    html = read("templates/_atom_quick_action_menu.html")

    assert 'root.querySelectorAll("[data-quick-action-candidate]")' in html
    assert "let activeCandidate = null" in html
    assert "if (!command || !activeCandidate || event.target.disabled) return;" in html
    assert "candidateFromElement(element)" in html
    assert "sourceModuleCode" in html
    assert "actionKey" in html
    assert "if (!sourceModuleCode || !actionKey || !title) return null;" in html

def test_quick_action_context_menu_partial_keeps_user_shortcut_limits_and_safe_payload_rules():
    html = read("templates/_atom_quick_action_menu.html")

    assert "MAX_MODULE_ACTIONS = 9" in html
    assert "MAX_PINNED_ACTIONS = 3" in html
    assert ".slice(0, MAX_MODULE_ACTIONS)" in html
    assert "businessPayload" in html
    assert "resultPayload" in html
    assert "rawData" in html
    assert "sourceRows" in html
    assert "atom:quick-action:add" in html
    assert "atom:quick-action:remove" in html
    assert "atom:quick-action:pin" in html
    assert "atom:quick-action:unpin" in html


def test_quick_action_module_bar_supports_empty_remove_order_and_disabled_states():
    html = read("templates/_atom_quick_action_menu.html")

    assert "data-quick-action-module-bar" in html
    assert "renderModuleQuickActionBar" in html
    assert "renderAllModuleQuickActionBars" in html
    assert "atom-module-quick-actions-empty" in html
    assert "В этом модуле еще нет быстрых действий" in html
    assert "item.isVisibleInModuleBar !== false" in html
    assert ".sort((a, b) => (a.order || 0) - (b.order || 0))" in html
    assert "removeStoredQuickAction" in html
    assert "BROKEN_CONFIG" in html
    assert "MODULE_DISABLED" in html
    assert "NO_LONGER_AVAILABLE" in html
    assert "LOADING" in html
    assert "ERROR" in html
    assert "Быстрое действие обновляется" in html
    assert "Не удалось подготовить быстрое действие" in html


def test_quick_action_module_bar_supports_reorder_reset_and_pinned_reset_controls():
    html = read("templates/_atom_quick_action_menu.html")

    assert "atom-module-quick-actions-tools" in html
    assert "dataset.quickActionResetPinned" in html
    assert "dataset.quickActionResetModule" in html
    assert "Сбросить карточку" in html
    assert "Сбросить все" in html
    assert "moveStoredQuickAction" in html
    assert "resetModuleQuickActions" in html
    assert "resetAtomCardPinnedQuickActions" in html
    assert "atom:quick-action:reorder" in html
    assert "atom:quick-action:reset-module" in html
    assert "atom:quick-action:reset-pinned" in html
    assert "Удалить все быстрые действия этого модуля?" in html
    assert "Снять все быстрые действия с карточки модуля?" in html


def test_atom_card_pinned_actions_contract_supports_zero_to_three_tooltips_and_disabled_state():
    html = read("templates/_atom_quick_action_menu.html")

    assert "data-quick-action-atom-card" in html
    assert "atom-card-pinned-actions" in html
    assert "atom-card-pinned-action" in html
    assert "renderAtomCardPinnedActions" in html
    assert "renderAllAtomCardPinnedActions" in html
    assert ".slice(0, MAX_PINNED_ACTIONS)" in html
    assert "item.isPinnedToAtomCard" in html
    assert "data-action-tooltip" in html
    assert "data-accent=\"blue\"" in html
    assert "data-accent=\"cyan\"" in html
    assert "data-accent=\"green\"" in html
    assert "data-accent=\"orange\"" in html
    assert "data-accent=\"red\"" in html
    assert "data-accent=\"purple\"" in html
    assert "className = \"atom-card-pinned-action\" + (item.status === \"ACTIVE\" ? \"\" : \" disabled\")" in html
    assert "renderAllAtomCardPinnedActions();" in html


def test_material_hub_real_actions_are_quick_action_candidates():
    html = read("templates/material_hub_view.html")

    assert "{% include \"_atom_quick_action_menu.html\" %}" in html
    assert "data-quick-action-module-bar=\"MODULE_01_MATERIAL_HUB\"" in html
    assert "id=\"quick-action-run-source-analysis\"" in html
    assert "id=\"quick-action-upload-supplier-price\"" in html
    assert "id=\"quick-action-open-material-moderation\"" in html
    assert "id=\"quick-action-check-source-cards\"" in html
    assert "data-quick-action-candidate" in html
    assert "data-quick-action-source-module-code=\"MODULE_01_MATERIAL_HUB\"" in html
    assert "data-quick-action-feature-code=\"SOURCE_ANALYSIS\"" in html
    assert "data-quick-action-key=\"RUN_SOURCE_ANALYSIS\"" in html
    assert "data-quick-action-feature-code=\"SUPPLIER_PRICE_UPLOAD\"" in html
    assert "data-quick-action-key=\"UPLOAD_SUPPLIER_PRICE\"" in html
    assert "data-quick-action-feature-code=\"MATERIAL_MODERATION\"" in html
    assert "data-quick-action-key=\"OPEN_MATERIAL_MODERATION\"" in html
    assert "data-quick-action-feature-code=\"SOURCE_PRODUCTS\"" in html
    assert "data-quick-action-key=\"CHECK_SOURCE_CARDS\"" in html
    assert "data-quick-action-menu-for=\"quick-action-run-source-analysis\"" in html
    assert "data-quick-action-menu-for=\"quick-action-upload-supplier-price\"" in html
    assert "data-quick-action-menu-for=\"quick-action-open-material-moderation\"" in html
    assert "data-quick-action-menu-for=\"quick-action-check-source-cards\"" in html


def test_material_hub_quick_action_config_providers_do_not_store_business_results():
    html = read("templates/material_hub_view.html")

    assert "function materialHubSourceAnalysisQuickActionConfig()" in html
    assert "function materialHubSupplierUploadQuickActionConfig()" in html
    assert "sourceMode:" in html
    assert "selectedSources:" in html
    assert "actionType:" in html
    assert "scanMode:" in html
    assert "categoryUrlContains:" in html
    assert "requiresFileSelection: true" in html
    assert "resultPayload" not in html
    assert "businessPayload" not in html


def test_material_hub_is_documented_as_reference_quick_action_example():
    doc = read("docs/Modules/ATOM_USER_QUICK_ACTIONS_v1.0.md")

    assert "Эталонный пример Module №1" in doc
    assert "sourceModuleCode = MODULE_01_MATERIAL_HUB" in doc
    assert "featureCode = SOURCE_ANALYSIS" in doc
    assert "actionKey = RUN_SOURCE_ANALYSIS" in doc
    assert "featureCode = SUPPLIER_PRICE_UPLOAD" in doc
    assert "actionKey = UPLOAD_SUPPLIER_PRICE" in doc
    assert "featureCode = MATERIAL_MODERATION" in doc
    assert "actionKey = OPEN_MATERIAL_MODERATION" in doc
    assert "featureCode = SOURCE_PRODUCTS" in doc
    assert "actionKey = CHECK_SOURCE_CARDS" in doc


def test_module_03_admin_ui_does_not_use_user_quick_action_pattern_as_admin_menu():
    html = read("templates/admin_users_roles.html")

    assert "{% include \"_atom_quick_action_menu.html\" %}" not in html
    assert "data-quick-action-module-bar=\"MODULE_03_USERS_ROLES\"" not in html
    assert "data-quick-action-source-module-code=\"MODULE_03_USERS_ROLES\"" not in html
    assert "data-quick-action-key=\"OPEN_USERS_ADMIN\"" not in html
    assert "data-quick-action-key=\"OPEN_MODULE_REGISTRY\"" not in html
    assert "data-quick-action-key=\"OPEN_AUDIT_LOG\"" not in html
    assert "id=\"quick-actions\" hidden data-system-section=\"quick-action-diagnostics\"" in html


def test_module_11_price_dynamics_uses_quick_action_pattern_without_result_payload():
    html = read("templates/price_dynamics_view.html")

    assert "{% include \"_atom_quick_action_menu.html\" %}" in html
    assert "data-quick-action-module-bar=\"MODULE_11_ANALYTICS\"" in html
    assert "id=\"quick-action-open-price-dynamics\"" in html
    assert "id=\"quick-action-current-price-dynamics-slice\"" in html
    assert "data-quick-action-source-module-code=\"MODULE_11_ANALYTICS\"" in html
    assert "data-quick-action-feature-code=\"PRICE_DYNAMICS\"" in html
    assert "data-quick-action-key=\"OPEN_PRICE_DYNAMICS\"" in html
    assert "data-quick-action-key=\"OPEN_CURRENT_PRICE_DYNAMICS_SLICE\"" in html
    assert "data-quick-action-config-provider=\"priceDynamicsCurrentSliceQuickActionConfig\"" in html
    assert "function priceDynamicsCurrentSliceQuickActionConfig()" in html
    assert "selectedTargets:" in html
    assert "analysisType:" in html
    assert "resultPayload" not in html
    assert "businessPayload" not in html


def test_quick_action_documentation_lists_active_module_pattern_readiness():
    doc = read("docs/Modules/ATOM_USER_QUICK_ACTIONS_v1.0.md")

    assert "Sprint 8: единый pattern для активных модулей" in doc
    assert "app/services/active_module_quick_action_patterns.py" in doc
    assert "MODULE_02_KNOWLEDGE_BASE" in doc
    assert "MODULE_03_USERS_ROLES" in doc
    assert "MODULE_04_WORKS_COSTS" in doc
    assert "MODULE_05_ESTIMATE_ENGINE" in doc
    assert "MODULE_06_ESTIMATE_AUDIT" in doc
    assert "MODULE_07_DIGITAL_HOUSE" in doc
    assert "MODULE_09_PROCUREMENT" in doc
    assert "MODULE_10_MARKETPLACE" in doc
    assert "MODULE_11_ANALYTICS" in doc
    assert "UI_READY" in doc
    assert "PATTERN_READY_NO_UI" in doc


def test_quick_action_documentation_lists_planned_module_compatibility_rules():
    doc = read("docs/Modules/ATOM_USER_QUICK_ACTIONS_v1.0.md")

    assert "Sprint 9: planned / future modules compatibility" in doc
    assert "PLANNED_DOCUMENTATION_ONLY" in doc
    assert "PLANNED_NO_ACTIVE_ACTIONS" in doc
    assert "isVisibleToOrdinaryUsers = false" in doc
    assert "isExecutable = false" in doc
    assert "canPinToAtomCard = false" in doc
    assert "MODULE_12_AI_ASSISTANT" in doc
    assert "MODULE_13_PROJECT_COLLABORATION" in doc
    assert "MODULE_15_CONTRACTS" in doc
    assert "MODULE_16_LOGISTICS_DELIVERY" in doc
    assert "MODULE_17_FINANCE_PAYMENTS" in doc
    assert "MODULE_18_QUALITY_CONTROL" in doc
    assert "MODULE_19_CONSTRUCTOR_LITE" in doc
    assert "MODULE_20_SITE_SUPERVISION" in doc
    assert "MODULE_21_WARRANTY_SERVICE" in doc


def test_quick_action_documentation_lists_user_management_operations():
    doc = read("docs/Modules/ATOM_USER_QUICK_ACTIONS_v1.0.md")

    assert "Sprint 10: удаление, сброс и восстановление порядка" in doc
    assert "resetModuleQuickActions()" in doc
    assert "resetAtomCardPinnedQuickActions()" in doc
    assert "removeUserModuleQuickAction()" in doc
    assert "reorderUserModuleQuickActions()" in doc
    assert "resetUserModuleQuickActions()" in doc
    assert "atom:quick-action:reorder" in doc
    assert "atom:quick-action:reset-module" in doc
    assert "atom:quick-action:reset-pinned" in doc


def test_quick_action_documentation_lists_stale_action_states():
    doc = read("docs/Modules/ATOM_USER_QUICK_ACTIONS_v1.0.md")

    assert "Sprint 11: states и защита от устаревших действий" in doc
    assert "ACTIVE" in doc
    assert "DISABLED" in doc
    assert "BROKEN_CONFIG" in doc
    assert "MODULE_DISABLED" in doc
    assert "NO_LONGER_AVAILABLE" in doc
    assert "LOADING" in doc
    assert "ERROR" in doc
    assert "интерфейс не должен падать" in doc


def test_quick_action_menu_uses_backend_api_as_primary_storage():
    html = read("templates/_atom_quick_action_menu.html")

    assert 'QUICK_ACTION_API_BASE = "/api/v1/quick-actions/user-module"' in html
    assert 'FALLBACK_STORAGE_KEY = "atom:userModuleQuickActions:v1"' in html
    assert "async function apiRequest" in html
    assert "await apiRequest(`?${moduleQuery(sourceModuleCode)}`)" in html
    assert "method: \"POST\", body: JSON.stringify(createPayloadFromCandidate" in html
    assert "method: \"DELETE\"" in html
    assert "pin-atom-card" in html
    assert "unpin-atom-card" in html
    assert "/rename?${moduleQuery" in html
    assert "await apiRequest(\"/reorder\"" in html
    assert "}/run`" in html
    assert "function readFallbackStore()" in html
    assert "function writeFallbackStore(items)" in html
    assert "quickActionCache.map(normalizeAction)" in html
    assert "localStorage.setItem(FALLBACK_STORAGE_KEY" in html
