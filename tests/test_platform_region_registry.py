from app.services.dashboard_module_registry import is_region_available_for_dashboard
from app.services.platform_region_registry import (
    PILOT_REGION_CODE,
    PILOT_REGION_NAME,
    REGION_CONTEXT_FIELD_NAMES,
    get_default_active_region,
    get_platform_region_registry_item,
    is_known_platform_region_code,
)


def test_pilot_region_is_registry_data_not_dashboard_condition():
    region = get_platform_region_registry_item(PILOT_REGION_CODE)

    assert region is not None
    assert region.code == PILOT_REGION_CODE
    assert region.name == PILOT_REGION_NAME
    assert region.isPilotRegion is True
    assert region.isActive is True
    assert is_known_platform_region_code(PILOT_REGION_CODE)
    assert is_region_available_for_dashboard(PILOT_REGION_CODE)
    assert not is_region_available_for_dashboard("UNKNOWN_REGION")


def test_region_context_field_names_cover_future_module_boundaries():
    expected_fields = {
        "activeRegionCode",
        "region_id",
        "city_id",
        "delivery_zone_id",
        "price_region_id",
        "supplier_region_id",
        "work_region_id",
        "object_region_id",
        "estimate_region_id",
        "audit_region_id",
        "procurement_region_id",
        "marketplace_region_id",
        "service_region_id",
        "delivery_region_id",
    }

    assert expected_fields.issubset(set(REGION_CONTEXT_FIELD_NAMES))
    assert get_default_active_region() == {
        "activeRegionCode": "KRASNODAR_KRAI",
        "activeRegionName": "Краснодарский край",
    }
