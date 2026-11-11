"""Read-only check of the running HousePlatform material catalogue."""

import asyncio
import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["APP_DEBUG"] = "false"
original_init = BaseSettings.__init__


def no_env_file(self, *values, **kwargs):
    kwargs["_env_file"] = None
    original_init(self, *values, **kwargs)


BaseSettings.__init__ = no_env_file
from app.database import async_session_factory
from app.services.module1_material_ui_catalog import filter_material_ui_rows, load_material_ui_catalog, material_ui_rows


async def main():
    async with async_session_factory() as db:
        rows = material_ui_rows(await load_material_ui_catalog(db))
        filtered, counts = filter_material_ui_rows(rows, preset="without_price")
        print(f"catalog={len(rows)} without_price={len(filtered)} counts={counts}")


asyncio.run(main())
