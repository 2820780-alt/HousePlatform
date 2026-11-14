"""Seed the approved M1 work catalog only in an explicitly guarded HousePlatform DB."""
import asyncio
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

mode = os.environ.get("ATOM_VERTICAL_SEED_MODE")
if mode not in {"release_qa", "houseplatform_live"}:
    raise RuntimeError("An explicit, supported seed mode is required")
target = "houseplatform_vertical_release_20261114_01" if mode == "release_qa" else "buildplatform"
if mode == "houseplatform_live" and os.environ.get("ATOM_LIVE_SEED_CONFIRM") != "houseplatform.buildplatform.work_catalog":
    raise RuntimeError("Live seed confirmation is missing")

original_init = BaseSettings.__init__


def no_env_file(self, *args, **kwargs):
    kwargs["_env_file"] = None
    return original_init(self, *args, **kwargs)


BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ and mode == "release_qa":
        os.environ[key] = make_url(os.environ[key]).set(database=target).render_as_string(hide_password=False)
os.environ["APP_DEBUG"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import async_session_factory, engine
from app.models.module1_work_item import WorkCatalogItem
from app.services.module1_work_catalog import get_work_catalog_registry
from app.services.module1_work_catalog_store import seed_existing_work_catalog

url = make_url(settings.DATABASE_URL)
if url.database != target or url.host != "db":
    raise RuntimeError("Database identity does not match the guarded HousePlatform target")


async def main():
    async with async_session_factory() as db:
        before = await db.scalar(select(func.count()).select_from(WorkCatalogItem))
        expected = len(get_work_catalog_registry().works)
        if mode == "houseplatform_live" and before != 0:
            raise RuntimeError("Live catalog is not empty; refusing automatic seed")
        first = await seed_existing_work_catalog(db)
        second = await seed_existing_work_catalog(db)
        after = await db.scalar(select(func.count()).select_from(WorkCatalogItem))
        if (after != expected or first["created"] + first["reused"] != expected or
                second["created"] != 0 or second["reused"] != expected or first["modified"]):
            raise RuntimeError("Catalog verification failed; transaction will not be committed")
        await db.commit()
        print(f"Work catalog: created {first['created']}, reused {first['reused']}; repeat: no duplicates")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
