from app.services.dashboard_module_registry import normalize_dashboard_layout
from app.services.dashboard_widget_config import build_dashboard_widget_config, widget_config_from_dict


def test_widget_config_uses_canonical_module_code_and_widget_code():
    config = build_dashboard_widget_config(
        widget_code="price-dynamics",
        title="Динамика цен",
        description="Изменение цен",
        widget_type="CHART",
        source_module_code="MODULE_14_PRICE_HISTORY",
        feature_code="PRICE_DYNAMICS",
        size="M",
        position=2,
        data_source="period",
    )

    assert config.widgetCode == "price-dynamics"
    assert config.type == "CHART"
    assert config.size == "medium"
    assert config.sourceModuleCode == "MODULE_11_ANALYTICS"
    assert config.canonicalModuleCode == "MODULE_11_ANALYTICS"
    assert config.legacyModuleCode == "MODULE_14_PRICE_HISTORY"
    assert config.featureCode == "PRICE_DYNAMICS"


def test_widget_config_from_legacy_dict_does_not_use_source_module_number():
    config = widget_config_from_dict(
        {
            "type": "KPI",
            "title": "Материалы",
            "size": "S",
            "module_number": 1,
            "enabled": True,
        }
    ).to_dict()

    assert config["size"] == "small"
    assert config["sourceModuleCode"] == "MODULE_01_MATERIAL_HUB"
    assert "sourceModuleNumber" not in config


def test_layout_normalization_removes_source_module_number():
    normalized = normalize_dashboard_layout(
        {
            "widgets": [
                {
                    "widgetCode": "legacy-widget",
                    "title": "Старый виджет",
                    "sourceModuleNumber": 14,
                    "moduleNumberLegacy": 14,
                }
            ]
        }
    )

    widget = normalized["widgets"][0]
    assert "sourceModuleNumber" not in widget
    assert widget["sourceModuleCode"] == "MODULE_11_ANALYTICS"
    assert widget["legacyModuleCode"] == "MODULE_14_PRICE_HISTORY"
