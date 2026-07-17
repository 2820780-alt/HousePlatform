from pathlib import Path

from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.services.module1_legacy_compatibility import get_module1_legacy_compatibility_map


MIGRATION_PATH = Path("database/migrations/20260717_module01_provider_work_cost_offers.sql")


def test_provider_work_cost_offer_model_is_separate_from_material_price_tables():
    table = ProviderWorkCostOffer.__table__

    assert table.name == "provider_work_cost_offers"
    assert "work_code" in table.c
    assert "owner_user_id" in table.c
    assert "pricing_mode" in table.c
    assert "fixed_amount" in table.c
    assert "minimum_amount" in table.c
    assert "maximum_amount" in table.c

    forbidden_columns = {
        "material_id",
        "catalog_product_id",
        "price_observation_id",
        "source_task_id",
        "source_adapter",
        "source_url",
        "raw_payload",
        "work_volume",
        "project_id",
        "house_id",
        "estimate_id",
        "ref_profile_id",
    }
    assert forbidden_columns.isdisjoint(table.c.keys())


def test_provider_work_cost_offer_constraints_and_indexes_are_declared():
    table = ProviderWorkCostOffer.__table__
    constraint_names = {constraint.name for constraint in table.constraints}
    index_names = {index.name for index in table.indexes}

    assert "ck_provider_work_cost_pricing_mode" in constraint_names
    assert "ck_provider_work_cost_status" in constraint_names
    assert "ck_provider_work_cost_fixed_positive" in constraint_names
    assert "ck_provider_work_cost_min_positive" in constraint_names
    assert "ck_provider_work_cost_max_positive" in constraint_names
    assert "ck_provider_work_cost_validity" in constraint_names
    assert "ck_provider_work_cost_amount_contract" in constraint_names
    assert "ix_provider_work_cost_owner_work_code" in index_names
    assert "ix_provider_work_cost_region_status" in index_names


def test_provider_work_cost_migration_creates_only_work_cost_table():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS provider_work_cost_offers" in sql
    assert "CREATE INDEX IF NOT EXISTS ix_provider_work_cost_offers_work_code" in sql
    assert "ALTER TABLE materials" not in sql
    assert "ALTER TABLE catalog_products" not in sql
    assert "ALTER TABLE supplier_prices" not in sql
    assert "ALTER TABLE price_history" not in sql
    assert "ALTER TABLE module08_works_costs_cabinet_links" not in sql
    assert "INSERT INTO provider_work_cost_offers" not in sql


def test_legacy_compatibility_marks_work_rate_boundary_as_separate_persistence_contract():
    mapping = {item.target_entity: item for item in get_module1_legacy_compatibility_map()}

    assert mapping["WorkRateObservation"].status == "separate_persistence_contract"
    assert mapping["WorkRateObservation"].legacy_entities == (
        "ProviderWorkCostOffer",
        "WorkRateObservation",
    )
    assert "never promote observations automatically" in mapping["WorkRateObservation"].adapt
