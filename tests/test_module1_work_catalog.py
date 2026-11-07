import json
from pathlib import Path

import pytest

from app.services.module1_work_catalog import (
    ALLOWED_APPLIES_TO,
    WorkCatalogError,
    build_work_catalog_summary,
    get_allowed_units,
    get_work_item,
    is_range_allowed,
    list_work_by_applies_to,
    list_work_by_group,
    list_work_groups,
    list_work_items,
    load_work_catalog_seed,
    validate_work_catalog,
    validate_work_item,
)


SEED_PATH = Path("src/modules/module1/seeds/work_catalog_seed.json")


def test_work_catalog_seed_loads_from_repository():
    registry = load_work_catalog_seed(SEED_PATH)

    assert registry.version == "1.0"
    assert registry.module == "module1"
    assert registry.domain == "work_catalog"
    assert len(registry.groups) == 24
    assert len(registry.works) == 209
    assert len(registry.units) == 14


def test_work_catalog_top_level_api_returns_expected_data():
    items = list_work_items()
    groups = list_work_groups()
    summary = build_work_catalog_summary()

    assert len(items) == 212
    assert summary.version == "1.1"
    assert len(groups) == 24
    assert summary.work_count == len(items)
    assert summary.group_count == len(groups)
    assert summary.unit_count == 14
    assert set(summary.applies_to) == ALLOWED_APPLIES_TO
    assert summary.range_allowed_count == len(items)


def test_get_work_item_and_units():
    work_code = "preparation_vyezd_specialista_na_obekt"
    work = get_work_item(work_code)

    assert work is not None
    assert work.work_code == work_code
    assert work.work_group == "preparation"
    assert work.default_unit == "visit"
    assert get_allowed_units(work_code) == ("visit",)
    assert is_range_allowed(work_code) is True


def test_list_work_by_group_uses_seed_groups_without_inventing_works():
    preparation = list_work_by_group("preparation")
    demolition = list_work_by_group("demolition")

    assert preparation
    assert demolition
    assert all(work.work_group == "preparation" for work in preparation)
    assert all(work.work_group == "demolition" for work in demolition)
    assert list_work_by_group("unknown_group") == tuple()


def test_list_work_by_applies_to_covers_private_house_and_apartment():
    private_house = list_work_by_applies_to("private_house")
    apartment = list_work_by_applies_to("apartment")
    both = list_work_by_applies_to("both")

    assert private_house
    assert apartment
    assert both
    assert all(work.applies_to in {"private_house", "both"} for work in private_house)
    assert all(work.applies_to in {"apartment", "both"} for work in apartment)
    assert all(work.applies_to == "both" for work in both)
    assert list_work_by_applies_to("commercial") == tuple()


def test_work_codes_are_unique_and_default_units_are_allowed():
    registry = load_work_catalog_seed(SEED_PATH)
    work_codes = [work.work_code for work in registry.works]

    assert len(work_codes) == len(set(work_codes))
    for work in registry.works:
        assert work.default_unit in work.allowed_units
        assert work.applies_to in ALLOWED_APPLIES_TO


def test_validate_work_catalog_rejects_prices_providers_and_contacts():
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    raw["works"][0]["price"] = 1000
    raw["works"][1]["provider_id"] = "provider-1"
    raw["works"][2]["contact_phone"] = "+7"

    report = validate_work_catalog(raw)

    assert report.is_valid is False
    assert any("works[0] contains forbidden" in error and "price" in error for error in report.errors)
    assert any("works[1] contains forbidden" in error and "provider_id" in error for error in report.errors)
    assert any("works[2] contains forbidden" in error and "contact_phone" in error for error in report.errors)


def test_validate_work_catalog_rejects_invalid_units_and_applies_to():
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    raw["works"][0]["default_unit"] = "unknown_unit"
    raw["works"][0]["allowed_units"] = ["visit"]
    raw["works"][1]["applies_to"] = "commercial"

    report = validate_work_catalog(raw)

    assert report.is_valid is False
    assert "works[0].default_unit must be included in allowed_units" in report.errors
    assert any("works[1].applies_to must be one of" in error for error in report.errors)


def test_validate_work_item_returns_dataclass_or_raises_controlled_error():
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    item = validate_work_item(raw["works"][0])

    assert item.work_code == raw["works"][0]["work_code"]

    raw["works"][0].pop("work_code")
    with pytest.raises(WorkCatalogError, match="work_item.work_code must be a non-empty string"):
        validate_work_item(raw["works"][0])


def test_invalid_seed_file_raises_without_side_effects(tmp_path):
    invalid_seed = tmp_path / "work_catalog_seed.json"
    invalid_seed.write_text("{not-json", encoding="utf-8")

    with pytest.raises(WorkCatalogError, match="not valid JSON"):
        load_work_catalog_seed(invalid_seed)


def test_work_catalog_service_does_not_create_orm_or_prices():
    source = Path("app/services/module1_work_catalog.py").read_text(encoding="utf-8")

    assert "from app.models" not in source
    assert "Material(" not in source
    assert "SupplierPrice(" not in source
    assert "PriceObservation(" not in source
    assert "Session" not in source
