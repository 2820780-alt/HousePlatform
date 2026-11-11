from pathlib import Path


TEMPLATE = Path("templates/material_hub_data.html")
VIEW = Path("app/api/v1/material_hub_view.py")


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _view_text() -> str:
    return VIEW.read_text(encoding="utf-8")


def test_only_one_canonical_material_table_contract_remains() -> None:
    text = _template_text()

    assert '<table id="material-table" data-preference-namespace="module1.materials_table"' in text
    assert '<table id="price-table"' not in text
    assert "module1.price_table" not in text
    assert "\u041e\u0441\u043d\u043e\u0432\u043d\u0430\u044f \u0442\u0430\u0431\u043b\u0438\u0446\u0430 \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u043e\u0432 \u0434\u043b\u044f \u0441\u043c\u0435\u0442" not in text
    assert "\u0421\u0442\u043e\u043b\u0431\u0438\u043a\u0438" not in text
    assert "\u0418\u0441\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u043e" not in text


def test_material_table_presets_are_on_canonical_table() -> None:
    text = _template_text()
    view = _view_text()

    for preset in [
        "all",
        "estimate_ready",
        "needs_price",
        "needs_classification",
        "needs_review",
    ]:
        assert preset in text
        assert preset in view
    for label in [
        "\u0412\u0441\u0435 \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u044b",
        "\u0413\u043e\u0442\u043e\u0432\u044b \u043a \u0441\u043c\u0435\u0442\u0435",
        "\u0411\u0435\u0437 \u0446\u0435\u043d\u044b",
        "\u0422\u0440\u0435\u0431\u0443\u044e\u0442 \u043a\u043b\u0430\u0441\u0441\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u0438",
        "\u0422\u0440\u0435\u0431\u0443\u044e\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438",
    ]:
        assert label in view

    assert 'data-initial-preset="{{ material_table_preset }}"' in text
    assert "data-material-preset-link" in text
    assert "activeMaterialPreset" in text


def test_materials_route_uses_new_catalog_and_preserves_legacy_preset_urls() -> None:
    view = _view_text()

    assert '@router.get("/materials", response_class=HTMLResponse)' in view
    assert '"needs_price": "without_price"' in view
    assert '"estimate_ready": "all"' in view
    assert "return await material_hub_materials_preview(" in view
    assert '"/api/v1/admin/material-hub/view/materials?preset={key}"' in view
    assert '@router.get("/data", response_class=HTMLResponse)' in view
    assert '_material_table_preset(preset, default="all")' in view


def test_estimate_ready_uses_server_side_existing_readiness_source() -> None:
    text = _template_text()
    view = _view_text()

    assert "estimate_ready_material_ids" in view
    assert "price_recommendations = await _load_price_recommendations(db, in_stock_only)" in view
    assert 'data-estimate-ready="{{ \'yes\' if estimate_ready else \'no\' }}"' in text
    assert 'preset === "estimate_ready" && row.dataset.estimateReady === "yes"' in text
    assert 'preset === "estimate_ready" && row.dataset.hasPrice === "yes"' not in text


def test_unified_preferences_and_required_columns_are_preserved() -> None:
    text = _template_text()

    assert "module1.materials_table" in text
    assert "module1.price_table" not in text
    assert 'requiredColumns: ["material", "price", "data_state", "actions"]' in text
    assert "schema.requiredColumns.includes(field)" in text
    assert "fields.has(field) && !schema.requiredColumns.includes(field)" in text
    assert "resetMaterialFilters" in text
    assert "resetMaterialTableView" in text


def test_single_material_details_modal_and_safe_legacy_name_fallback() -> None:
    text = _template_text()

    assert text.count('id="material-details-dialog"') == 1
    assert "openMaterialDetailsDialog('material-details-card-{{ loop.index }}', this)" in text
    assert "materialDetailsReturnFocus" in text
    assert "\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u0438\u0441\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f" in text
    assert '"???" in material.canonical_name' in text
    assert "????????" not in text


def test_ref_dashboard_quick_actions_and_module5_are_not_touched_by_template() -> None:
    text = _template_text()

    forbidden = [
        "ATOM_REF1",
        "ATOM_REF2",
        "ATOM_REF3",
        "reference_data",
        "Quick Actions",
        "Dashboard",
        "Widget",
    ]
    for marker in forbidden:
        assert marker not in text
