from __future__ import annotations

import os

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.database import Base, init_db
from app.models.module2_content_catalog import TechnologyCategory


@pytest.mark.asyncio
async def test_content_catalog_migration_matches_orm_and_startup(monkeypatch) -> None:
    database_name = os.getenv("M2_CONTENT_SCHEMA_TEST_DATABASE")
    if not database_name:
        pytest.skip("set M2_CONTENT_SCHEMA_TEST_DATABASE to an isolated restored database")
    assert database_name != make_url(settings.DATABASE_URL).database

    url = make_url(settings.DATABASE_URL).set(database=database_name)
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            schema = await connection.run_sync(_read_schema)
        assert schema["category_columns"] == set(TechnologyCategory.__table__.columns.keys())
        assert schema["category_pk"] == {"id"}
        assert schema["category_checks"] == {
            "ck_module2_category_status",
            "ck_module2_category_content_status",
            "ck_module2_category_sort_order",
        }
        assert schema["category_indexes"] == {
            "ix_module2_technology_categories_code",
            "ix_module2_technology_categories_parent_id",
            "ix_module2_technology_categories_status",
        }
        assert schema["unique_code"]
        assert schema["category_self_fk"]
        assert schema["technology_fk"]
        assert schema["technology_category_nullable"]
        assert schema["category_count"] == 0
        assert schema["technology_count"] == 0
        assert schema["m1_m3_counts"] == (394, 31, 71, 20, 18, 5)

        from app import database

        monkeypatch.setattr(database, "engine", engine)

        def forbidden_create_all(*_args, **_kwargs):
            raise AssertionError("normal startup must not create schema")

        monkeypatch.setattr(Base.metadata, "create_all", forbidden_create_all)
        await init_db()
    finally:
        await engine.dispose()


def _read_schema(connection):
    inspector = inspect(connection)
    category = "module2_technology_categories"
    with connection.begin_nested():
        counts = connection.exec_driver_sql(
            "SELECT (SELECT count(*) FROM materials), "
            "(SELECT count(*) FROM material_documents), "
            "(SELECT count(*) FROM material_categories), "
            "(SELECT count(*) FROM users), "
            "(SELECT count(*) FROM roles), "
            "(SELECT count(*) FROM workspaces)"
        ).one()
        category_count = connection.exec_driver_sql(f"SELECT count(*) FROM {category}").scalar_one()
        technology_count = connection.exec_driver_sql(
            "SELECT count(*) FROM module2_technologies"
        ).scalar_one()
    technology_columns = {item["name"]: item for item in inspector.get_columns("module2_technologies")}
    return {
        "category_columns": {item["name"] for item in inspector.get_columns(category)},
        "category_pk": set(inspector.get_pk_constraint(category)["constrained_columns"]),
        "category_checks": {item["name"] for item in inspector.get_check_constraints(category)},
        "category_indexes": {item["name"] for item in inspector.get_indexes(category)},
        "unique_code": any(
            item["name"] == "ix_module2_technology_categories_code" and item["unique"]
            for item in inspector.get_indexes(category)
        ),
        "category_self_fk": any(
            item["referred_table"] == category and item["constrained_columns"] == ["parent_id"]
            for item in inspector.get_foreign_keys(category)
        ),
        "technology_fk": any(
            item["referred_table"] == category and item["constrained_columns"] == ["category_id"]
            for item in inspector.get_foreign_keys("module2_technologies")
        ),
        "technology_category_nullable": technology_columns["category_id"]["nullable"],
        "category_count": category_count,
        "technology_count": technology_count,
        "m1_m3_counts": tuple(counts),
    }
