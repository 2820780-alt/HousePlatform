from app.services.dashboard_module_registry import normalize_dashboard_layout
from app.services.dashboard_widget_config import (
    ATOM_CARD_ACTIONS,
    BOTTOM_WIDGET_GRID,
    RIGHT_RAIL,
    SIZE_GRID_SPANS,
    TOP_WIDGET_GRID,
    build_dashboard_widget_config,
    widget_config_from_dict,
)


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


def test_widget_config_supports_bottom_grid_and_right_rail_zones():
    bottom_config = build_dashboard_widget_config(
        widget_code="wide-widget",
        title="Широкий виджет",
        widget_type="LIST",
        source_module_code="MODULE_01_MATERIAL_HUB",
        size="W",
        zone_code="below",
    ).to_dict()
    right_config = widget_config_from_dict(
        {
            "widgetCode": "right-widget",
            "title": "Правая колонка",
            "type": "CHART",
            "sourceModuleCode": "MODULE_11_ANALYTICS",
            "size": "medium",
            "zone": "right",
        }
    ).to_dict()

    assert bottom_config["size"] == "wide"
    assert bottom_config["zoneCode"] == BOTTOM_WIDGET_GRID
    assert SIZE_GRID_SPANS[bottom_config["size"]] == 12
    assert right_config["zoneCode"] == RIGHT_RAIL

    top_config = widget_config_from_dict(
        {
            "widgetCode": "top-widget",
            "title": "Верхний KPI",
            "type": "KPI",
            "sourceModuleCode": "MODULE_01_MATERIAL_HUB",
            "zone": "top",
        }
    ).to_dict()

    assert top_config["zoneCode"] == TOP_WIDGET_GRID


def test_widget_config_supports_atom_card_action_zone_for_future_layout():
    config = widget_config_from_dict(
        {
            "widgetCode": "material-card-actions",
            "title": "Действия карточки",
            "type": "ACTIONS",
            "sourceModuleCode": "MODULE_01_MATERIAL_HUB",
            "zone": "atom_card",
        }
    ).to_dict()

    assert config["zoneCode"] == ATOM_CARD_ACTIONS
    assert config["sourceModuleCode"] == "MODULE_01_MATERIAL_HUB"
