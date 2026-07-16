from pathlib import Path


TEMPLATE = Path("templates/material_hub_moderation.html")


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_moderation_workspace_has_human_readable_title_and_columns() -> None:
    text = _template_text()

    assert "Модерация и качество" in text
    expected_columns = [
        "Материал",
        "Что требует внимания",
        "Категория",
        "Цена",
        "Источник",
        "Состояние данных",
        "Обновлено",
        "Действия",
    ]
    expected_fields = [
        "material",
        "issue",
        "category",
        "price",
        "source",
        "data_state",
        "updated",
        "actions",
    ]
    for column in expected_columns:
        assert column in text
    for field in expected_fields:
        assert f'data-field="{field}"' in text


def test_moderation_workspace_hides_raw_debug_and_ref_runtime_details() -> None:
    text = _template_text()

    forbidden = [
        "Оценка совпадения",
        "match_score",
        "confidence",
        "MaterialMatchCandidate",
        "candidate_id",
        "material_id",
        "supplier_account_id",
        "work_region_id",
        "verified_by_moderator",
        "raw JSON",
        "source payload",
        "stack trace",
        "ATOM_REF1",
        "ATOM_REF2",
        "ATOM_REF3",
        "REF-2B",
        "REF-3A",
        "REF-3B",
        "reference_data",
        "345",
    ]
    for marker in forbidden:
        assert marker not in text

    assert "candidate.id" in text
    assert "<th>Candidate" not in text
    assert "Material ID" not in text


def test_moderation_reasons_and_price_gate_are_human_readable() -> None:
    text = _template_text()

    assert "Нет положительной цены" in text
    assert "Требуется классификация" in text
    assert "Возможен дубль" in text
    assert "Требуется решение модератора" in text
    assert "Позицию нельзя считать готовой к смете." in text
    assert "has_positive_price" in text
    assert "Нужна положительная цена" in text
    assert "product.price is not none and product.price > 0" in text


def test_moderation_filters_states_and_retry_are_present() -> None:
    text = _template_text()

    expected = [
        "moderation-search",
        "moderation-issue-filter",
        "moderation-state-filter",
        "moderation-price-filter",
        "moderation-source-filter",
        "moderation-active-filters",
        "Сбросить фильтры",
        "Загрузка очереди...",
        "Сейчас нет материалов, требующих проверки.",
        "По выбранным условиям ничего не найдено.",
        "Не удалось загрузить очередь.",
        "Повторить",
        "applyModerationPagination",
        "sortModerationTable",
    ]
    for marker in expected:
        assert marker in text


def test_moderation_preferences_are_namespaced_user_scoped_and_safe() -> None:
    text = _template_text()

    assert 'data-preference-namespace="module1.moderation_queue"' in text
    assert 'namespace: "module1.moderation_queue"' in text
    assert "moderationUserScope" in text
    assert "sessionStorage" in text
    assert "localStorage" in text
    assert 'const MODERATION_REQUIRED_COLUMNS = ["material", "issue", "data_state", "actions"];' in text
    assert "fields.has(field) && !MODERATION_REQUIRED_COLUMNS.includes(field)" in text
    assert "merged.column_order.filter((field) => fields.has(field))" in text
    assert "materials" not in text.lower() or "moderation_queue" in text


def test_moderation_reuses_material_details_card_shell_and_focus_return() -> None:
    text = _template_text()

    assert "Открыть карточку" in text
    assert "openMaterialDetailsDialog('material-details-card-{{ loop.index }}', this)" in text
    assert '<div id="material-details-dialog" class="modal-backdrop" aria-hidden="true">' in text
    assert "material-details-loading" in text
    assert "material-details-error" in text
    assert "materialDetailsReturnFocus" in text
    assert "materialDetailsReturnFocus.focus()" in text
    assert 'event.key !== "Escape"' in text
    assert "closeMaterialDetailsDialog()" in text


def test_moderation_actions_use_admin_rbac_route_and_confirmations() -> None:
    text = _template_text()

    assert "/api/v1/admin/moderation/" in text
    assert "/api/v1/dev/material-hub/candidates" not in text
    assert "window.confirm" in text
    assert "Подтвердить" in text
    assert "Создать материал" in text
    assert "Отклонить" in text
    assert "Не удалось выполнить действие. Проверьте доступы и данные позиции." in text


def test_moderation_workspace_does_not_mention_other_modules_or_quick_actions() -> None:
    text = _template_text()

    forbidden = [
        "Quick Actions",
        "quick action",
        "Dashboard",
        "Widgets",
        "Module №2",
        "Module №3",
        "Module №5",
    ]
    for marker in forbidden:
        assert marker not in text
