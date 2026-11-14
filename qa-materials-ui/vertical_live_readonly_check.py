"""Read-only release checks for the explicitly identified HousePlatform live DB."""
import asyncio
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
import httpx

if os.environ.get("ATOM_VERTICAL_READONLY_CHECK") != "houseplatform.buildplatform":
    raise RuntimeError("Explicit HousePlatform read-only guard required")

original_init = BaseSettings.__init__


def no_env_file(self, *args, **kwargs):
    kwargs["_env_file"] = None
    return original_init(self, *args, **kwargs)


BaseSettings.__init__ = no_env_file
os.environ["APP_DEBUG"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import async_session_factory, engine, init_db
from app.main import app
from app.models.module1_work_item import WorkCatalogItem
from app.services.module1_work_catalog import get_work_catalog_registry

url = make_url(settings.DATABASE_URL)
if url.database != "buildplatform" or url.host != "db":
    raise RuntimeError("Database identity is not the guarded HousePlatform target")
if not settings.VERTICAL_CALCULATION_PREVIEW_ENABLED:
    raise RuntimeError("Vertical routes are disabled")


async def main():
    await init_db(create_schema=False)
    identifier = "00000000-0000-0000-0000-000000000000"
    required = ("/api/v1/admin/vertical-m1/works", f"/api/v1/admin/module2/calculation-builder/{identifier}",
                f"/api/v1/admin/vertical-preview/{identifier}")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        for path in required:
            response = await client.get(path, follow_redirects=False)
            if response.status_code not in {401, 403, 302, 303, 307}:
                raise RuntimeError(f"Unexpected unauthenticated route status: {response.status_code}")
    async with async_session_factory() as db:
        count = await db.scalar(select(func.count()).select_from(WorkCatalogItem))
    if count != len(get_work_catalog_registry().works):
        raise RuntimeError("Work catalog does not match the initial seed count")
    print(f"Startup schema: PASS; vertical routes: PASS; M1 work cards: {count}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
