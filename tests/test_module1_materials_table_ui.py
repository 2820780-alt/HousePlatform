from pathlib import Path


TEMPLATE = Path("templates/material_hub_data.html")


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _materials_section() -> str:
    text = _template_text()
    start = text.index('<section id="materials"')
    end = text.index('<section id="category-editor"', start)
    return text[start:end]


def test_materials_table_uses_target_columns() -> None:
    section = _materials_section()

    expected_columns = [
        "Материал",
        "Категория",
        "Основные характеристики",
        "Единица и упаковка",
        "Текущая цена",
        "Поставщик и регион",
        "Состояние данных",
        "Обновлено",
        "Действия",
    ]
    expected_fields = [
        "material",
        "category",
        "characteristics",
        "unit_package",
        "price",
        "supplier_region",
        "data_state",
        "updated",
        "actions",
    ]

    for column in expected_columns:
        assert column in section
    for field in expected_fields:
        assert f'data-field="{field}"' in section


def test_materials_table_hides_raw_and_internal_details_from_main_row() -> None:
    section = _materials_section()

    forbidden_visible_markers = [
        "confidence:",
        "verified_by_moderator",
        "raw title",
        "raw category",
        "sourcecode",
        "supplier_account_id",
        "sync_status",
        "work_region_id",
        "module1_ref_projection",
        "ATOM_REF1",
        "ATOM_REF2",
        "ATOM_REF3",
        "reference_data",
    ]
    for marker in forbidden_visible_markers:
        assert marker not in section

    assert "<code>{{ material.id" not in section
    assert "Нет положительной цены" in section
    assert "Не готово для сметы" in section


def test_materials_table_has_loading_empty_and_error_states() -> None:
    section = _materials_section()

    assert "Загрузка материалов..." in section
    assert "Не удалось загрузить материалы" in section
    assert "По выбранным условиям ничего не найдено." in section
    assert "Материалов пока нет." in section


def test_materials_table_view_preferences_are_namespaced_and_user_isolated() -> None:
    text = _template_text()

    assert "module1.materials_table" in text
    assert "atom:${schema.namespace}:v1:${tablePreferenceUserScope()}:${tableId}" in text
    assert "tablePreferenceUserScope" in text
    assert "sessionStorage" in text
    assert "localStorage" in text
    assert "density" in text
    assert "page_size" in text
    assert "default_sort" in text
    assert "wrap_text" in text
    assert "column_order" in text


def test_required_columns_cannot_be_hidden_and_unknown_columns_are_ignored() -> None:
    text = _template_text()

    assert (
        'requiredColumns: ["material", "category", "characteristics", "price", '
        '"data_state", "updated", "actions"]'
    ) in text
    assert "schema.requiredColumns.includes(field)" in text
    assert "fields.has(field) && !schema.requiredColumns.includes(field)" in text
    assert "merged.column_order.filter((field) => fields.has(field))" in text
    assert "const field = table.tHead.rows[0].cells[columnIndex]?.dataset.field;" in text
    assert "if (field) {" in text


def test_materials_table_preferences_do_not_touch_rbac_or_ref_runtime() -> None:
    text = _template_text()

    assert "data-preference-namespace=\"module1.materials_table\"" in text
    assert "user_preference" not in text.lower()
    assert "role_matrix" not in text.lower()
    assert "module1.materials_table/rbac" not in text
    assert "ATOM_REF3" not in text
