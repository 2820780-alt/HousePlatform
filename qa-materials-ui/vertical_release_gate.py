"""Validate the release migration only on the explicitly named restored QA database."""
import asyncio
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy import inspect, select, func
from sqlalchemy.engine import make_url

QA_DATABASE = "houseplatform_vertical_release_20261114_01"
if os.environ.get("ATOM_RELEASE_QA_DB") != QA_DATABASE:
    raise RuntimeError("Refusing to run without the explicit release QA database guard")

original_init = BaseSettings.__init__


def no_env_file(self, *args, **kwargs):
    kwargs["_env_file"] = None
    return original_init(self, *args, **kwargs)


BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ:
        os.environ[key] = make_url(os.environ[key]).set(database=QA_DATABASE).render_as_string(hide_password=False)
os.environ["VERTICAL_CALCULATION_PREVIEW_ENABLED"] = "true"
os.environ["APP_DEBUG"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import async_session_factory, engine, init_db
from app.models.module1_offer_qualification import CalculationOfferQualification
from app.models.module1_work_item import ManualCalculationPriceRevision, WorkCatalogItem, WorkCatalogItemRevision
from app.models.module2_calculation_block import CalculationBlockTemplate, TechnologyCalculationBlock
from app.models.module5_estimate_snapshot import EstimatePreviewSnapshot
from app.models.module7_geometry import DigitalHouseObject, StripGeometryRevision
from app.services.module1_work_catalog import get_work_catalog_registry
from app.services.module1_work_catalog_store import seed_existing_work_catalog

if make_url(settings.DATABASE_URL).database != QA_DATABASE:
    raise RuntimeError("QA database URL does not match the guard")


def check_columns(connection):
    inspector = inspect(connection)
    models = (WorkCatalogItem, WorkCatalogItemRevision, ManualCalculationPriceRevision,
              CalculationOfferQualification, CalculationBlockTemplate, TechnologyCalculationBlock,
              DigitalHouseObject, StripGeometryRevision, EstimatePreviewSnapshot)
    for model in models:
        table = model.__table__
        actual = {column["name"]: column for column in inspector.get_columns(table.name)}
        if set(actual) != set(table.columns.keys()):
            raise RuntimeError(f"Column mismatch: {table.name}")
        for column in table.columns:
            if (actual[column.name]["nullable"] != column.nullable or
                    actual[column.name]["type"].compile(dialect=connection.dialect) !=
                    column.type.compile(dialect=connection.dialect)):
                raise RuntimeError(f"Column type or nullability mismatch: {table.name}.{column.name}")


async def main():
    await init_db(create_schema=False)
    async with engine.connect() as connection:
        await connection.run_sync(check_columns)
    async with async_session_factory() as db:
        first = await seed_existing_work_catalog(db)
        second = await seed_existing_work_catalog(db)
        expected = len(get_work_catalog_registry().works)
        count = await db.scalar(select(func.count()).select_from(WorkCatalogItem))
        revisions = await db.scalar(select(func.count()).select_from(WorkCatalogItemRevision))
        if (first["created"] != expected or first["reused"] != 0 or second["created"] != 0 or
                second["reused"] != expected or count != expected or revisions != expected):
            raise RuntimeError("Catalog seed is incomplete or not idempotent")
        await db.commit()
    print(f"Startup without create_all: PASS; ORM columns: PASS; work catalog: {count}; repeated seed: PASS")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
