from pathlib import Path


TEMPLATE = Path("templates/material_hub_data.html")
VIEW = Path("app/api/v1/material_hub_view.py")


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _details_area() -> str:
    return _template_text()

def test_material_details_opens_from_admin_table_with_keyboard_safe_modal() -> None:
    text = _template_text()
    details = _details_area()

    assert "Открыть карточку материала" in text
    assert "openMaterialDetailsDialog('material-details-card-{{ loop.index }}', this)" in text
    assert '<div id="material-details-dialog" class="modal-backdrop" aria-hidden="true">' in details
    assert 'role="dialog"' in details
    assert "materialDetailsReturnFocus" in text
    assert 'event.key !== "Escape"' in text
    assert "closeMaterialDetailsDialog()" in text
    assert "material-details-loading" in details
    assert "material-details-error" in details


def test_material_details_contains_human_readable_sections() -> None:
    details = _details_area()

    expected_sections = [
        "Основная информация",
        "Характеристики",
        "Единица и упаковка",
        "Цена",
        "Поставщик и регион",
        "Документы и технические данные",
        "Источники и evidence",
        "Состояние данных",
        "Роли и применимость",
        "Действия",
    ]
    for section in expected_sections:
        assert section in details


def test_material_details_hides_internal_ids_and_raw_debug_fields() -> None:
    details = _details_area()
    text = _template_text()

    assert "Material ID" not in text
    assert '<input id="edit-material-id" type="hidden">' in text
    forbidden = [
        "supplier_account_id",
        "work_region_id",
        "sync_status",
        "debug payload",
        "raw JSON",
        "stack trace",
        "field_code",
        "schema_id",
        "profile_id",
        "confidence:",
        "verified_by_moderator",
    ]
    for marker in forbidden:
        assert marker not in details
    assert "<code>{{ material.id" not in details


def test_material_details_shows_price_gate_without_frontend_reimplementation() -> None:
    details = _details_area()
    view_source = VIEW.read_text(encoding="utf-8")

    assert "Нет положительной цены" in details
    assert "Не готово для сметы" in details
    assert "Можно использовать при выполнении остальных условий" in details
    assert ".where(CatalogProduct.price > 0)" in view_source
    assert "updated_at" in view_source and "product.updated_at" in view_source
    assert "price_info.price <= 0" not in details


def test_material_details_separates_characteristics_packaging_documents_and_evidence() -> None:
    details = _details_area()

    assert "{{ specification.value }}" in details
    assert "Данные об упаковке не указаны" in details
    assert "Открыть документ" in details
    assert "Открыть источник" in details
    assert "Источник цены доступен в системе" in details
    assert "{{ document.file_url }}</a>" not in details
    assert "{{ document.source_url }}</a>" not in details


def test_material_details_uses_human_labels_for_fallback_characteristics() -> None:
    view_source = VIEW.read_text(encoding="utf-8")

    assert "def _humanize_material_field_key" in view_source
    assert "return template.field_key" not in view_source
    assert '"length_mm": "Длина, мм"' in view_source
    assert 'return key.replace("_", " ").replace("-", " ")' in view_source


def test_material_details_is_responsive_and_does_not_import_ref_or_other_modules() -> None:
    text = _template_text()

    assert "@media (max-width: 860px)" in text
    assert ".material-detail-grid { grid-template-columns:1fr; }" in text
    assert "module1.material_details" not in text or "tablePreferenceStorage" in text
    assert "ATOM_REF1" not in text
    assert "ATOM_REF2" not in text
    assert "ATOM_REF3" not in text
    assert "reference_data" not in text
