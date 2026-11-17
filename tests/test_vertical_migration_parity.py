"""Compare the vertical ORM to migrations only on the explicitly restored QA DB."""
import os

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import engine as configured_engine
from app.models.module1_offer_qualification import CalculationOfferQualification
from app.models.module1_work_item import ManualCalculationPriceRevision, WorkCatalogItem, WorkCatalogItemRevision
from app.models.module2_calculation_block import CalculationBlockTemplate, TechnologyCalculationBlock
from app.models.module5_estimate_snapshot import EstimatePreviewSnapshot
from app.models.module7_geometry import DigitalHouseObject, FoundationGeometryRevision, StripGeometryRevision


@pytest.mark.asyncio
async def test_vertical_migration_columns_match_orm_on_restored_database():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    models = (WorkCatalogItem, WorkCatalogItemRevision, ManualCalculationPriceRevision,
              CalculationOfferQualification, CalculationBlockTemplate, TechnologyCalculationBlock,
              DigitalHouseObject, StripGeometryRevision, EstimatePreviewSnapshot)

    def check(connection):
        inspector = inspect(connection)
        for model in models:
            table = model.__table__
            actual = {column["name"]: column for column in inspector.get_columns(table.name)}
            assert set(actual) == set(table.columns.keys()), table.name
            for expected in table.columns:
                reflected = actual[expected.name]
                assert reflected["nullable"] == expected.nullable, (table.name, expected.name, "nullable")
                assert reflected["type"].compile(dialect=connection.dialect) == expected.type.compile(
                    dialect=connection.dialect), (table.name, expected.name, "type")
    try:
        async with engine.connect() as connection:
            await connection.run_sync(check)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_fnd3_foundation_columns_match_fresh_restored_database(monkeypatch):
    dbname = "houseplatform_fnd3_release_20261117"
    if os.environ.get("ATOM_FND3_RELEASE_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored FND-3 release QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)

    def check(connection):
        inspector = inspect(connection)
        for model in (FoundationGeometryRevision, EstimatePreviewSnapshot):
            table = model.__table__
            actual = {column["name"]: column for column in inspector.get_columns(table.name)}
            assert set(actual) == set(table.columns.keys()), table.name
            for expected in table.columns:
                reflected = actual[expected.name]
                assert reflected["nullable"] == expected.nullable, (table.name, expected.name, "nullable")
                assert reflected["type"].compile(dialect=connection.dialect) == expected.type.compile(
                    dialect=connection.dialect), (table.name, expected.name, "type")

    try:
        async with engine.connect() as connection:
            await connection.run_sync(check)
        from app import database
        from app.config import settings

        monkeypatch.setattr(database, "engine", engine)
        monkeypatch.setattr(settings, "VERTICAL_CALCULATION_PREVIEW_ENABLED", True)
        await database.init_db(create_schema=False)
    finally:
        await engine.dispose()
