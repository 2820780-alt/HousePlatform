from pathlib import Path

TEMPLATE = Path("templates/material_hub_documents.html")
VIEW = Path("app/api/v1/material_hub_view.py")
DATA_TEMPLATE = Path("templates/material_hub_data.html")


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _view_text() -> str:
    return VIEW.read_text(encoding="utf-8")


def test_documents_workspace_has_human_readable_title_and_columns() -> None:
    text = _template_text()

    assert "Документы и технические данные" in text
    expected_columns = [
        "Документ",
        "Материал",
        "Тип документа",
        "Что подтверждает",
        "Срок действия",
        "Источник",
        "Состояние",
        "Обновлено",
        "Действия",
    ]
    expected_fields = [
        "document",
        "material",
        "document_type",
        "confirms",
        "validity",
        "source",
        "state",
        "updated",
        "actions",
    ]
    for column in expected_columns:
        assert column in text
    for field in expected_fields:
        assert f'data-field="{field}"' in text


def test_documents_workspace_hides_internal_ids_raw_urls_and_payloads() -> None:
    text = _template_text()

    forbidden = [
        "document.id",
        "document.material.id",
        "raw JSON",
        "raw evidence",
        "raw payload",
        "source task payload",
        "stack trace",
        "storage path",
        "checksum",
        "MIME",
        "Parse status",
        "{{ document.file_url }}</a>",
        "{{ document.source_url }}</a>",
        "<code>",
    ]
    for marker in forbidden:
        assert marker not in text


def test_documents_workspace_uses_safe_url_helpers_for_actions() -> None:
    text = _template_text()
    view = _view_text()

    assert "document_file_action_url(document)" in text
    assert "document_source_action_url(document)" in text
    assert "href=\"{{ file_action_url }}\"" in text
    assert "href=\"{{ source_action_url }}\"" in text
    assert 'rel="noopener noreferrer"' in text
    assert "def _safe_user_url" in view
    assert 'parsed.scheme not in {"http", "https"}' in view
    assert "is_document_url(candidate)" in view
    assert "javascript:" not in text.lower()
    assert "data:" not in text.lower()
    assert "file:" not in text.lower()


def test_documents_workspace_has_filters_preferences_pagination_and_states() -> None:
    text = _template_text()

    assert "document-search" in text
    assert "document-type-filter" in text
    assert "document-status-filter" in text
    assert "document-link-filter" in text
    assert "resetDocumentFilters" in text
    assert "module1.documents_table" in text
    assert "documentPreferenceUserScope" in text
    assert "requiredColumns" in text
    assert "documentTableSchema.optionalColumns.includes" in text
    assert "Загрузка документов..." in text
    assert "Документы и технические данные пока не добавлены." in text
    assert "По выбранным условиям ничего не найдено." in text
    assert "Не удалось загрузить документы." in text
    assert "retryDocuments" in text
    assert "document-page-size" in text
    assert "previousDocumentPage" in text
    assert "nextDocumentPage" in text


def test_documents_workspace_has_accessible_modal_and_material_integration() -> None:
    text = _template_text()

    assert 'id="document-details-dialog"' in text
    assert 'role="dialog"' in text
    assert 'aria-modal="true"' in text
    assert "openDocumentDialog('document-card-{{ loop.index }}', this)" in text
    assert "documentDialogReturnFocus" in text
    assert "event.key === \"Escape\"" in text
    assert "Открыть карточку материала" in text
    assert "/api/v1/admin/material-hub/view/materials?preset=all" in text
    assert "material_hub_data.html" not in text


def test_documents_labels_and_statuses_are_presented_by_view_helpers() -> None:
    text = _template_text()
    view = _view_text()

    for helper in [
        "document_material_label",
        "document_material_category_label",
        "document_type_label",
        "document_confirms_label",
        "document_validity_label",
        "document_status_label",
        "document_source_label",
        "document_file_state_label",
    ]:
        assert helper in text
        assert f'"{helper}": _{helper}' in view
    for function in [
        "def _document_type_label",
        "def _document_confirms_label",
        "def _document_validity_label",
        "def _document_status_label",
        "def _document_file_action_url",
        "def _document_source_action_url",
    ]:
        assert function in view


def test_documents_workspace_does_not_reimplement_price_gate_or_create_material_action() -> None:
    text = _template_text().lower()

    assert "готов" not in text or "готовность к смете" not in text
    assert "создать material" not in text
    assert "создать материал" not in text
    assert "price > 0" not in text
    assert "catalogproduct" not in text
    assert "materialmatchcandidate" not in text


def test_documents_workspace_does_not_touch_ref_dashboard_quick_actions_or_widgets() -> None:
    text = _template_text()

    for marker in [
        "ATOM_REF1",
        "ATOM_REF2",
        "ATOM_REF3",
        "reference_data",
        "Quick Actions",
        "Dashboard",
        "Widget",
    ]:
        assert marker not in text


def test_material_details_documents_section_stays_raw_free() -> None:
    details = DATA_TEMPLATE.read_text(encoding="utf-8")

    assert "Документы и технические данные" in details
    assert "{{ document.file_url }}</a>" not in details
    assert "{{ document.source_url }}</a>" not in details
    assert "raw JSON" not in details