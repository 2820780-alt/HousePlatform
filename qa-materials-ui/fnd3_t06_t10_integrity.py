"""Compare the restored release backup with the live HousePlatform database."""
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
original_init = BaseSettings.__init__


def no_env_file(self, *args, **kwargs):
    kwargs["_env_file"] = None
    return original_init(self, *args, **kwargs)


BaseSettings.__init__ = no_env_file
os.environ["APP_DEBUG"] = "false"
from app.database import engine

BACKUP_DB = "houseplatform_fnd3_t06_t10_20261117"
LIVE_DB = "buildplatform"
CHANGED = {"module2_calculation_blocks": 4, "audit_events": 4}


async def main():
    if engine.url.host != "db" or engine.url.database != LIVE_DB:
        raise RuntimeError("Database connection is not the guarded HousePlatform source")
    restored = create_async_engine(engine.url.set(database=BACKUP_DB))
    try:
        async with restored.connect() as before, engine.connect() as after:
            names_query = text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            names = (await before.execute(names_query)).scalars().all()
            if names != (await after.execute(names_query)).scalars().all():
                raise RuntimeError("Table list changed")
            for name in names:
                quoted = '"' + name.replace('"', '""') + '"'
                if name in CHANGED:
                    query = text(f"SELECT row_to_json(t)::text FROM public.{quoted} AS t")
                    old_rows = Counter((await before.execute(query)).scalars())
                    new_rows = Counter((await after.execute(query)).scalars())
                    if old_rows - new_rows or sum(new_rows.values()) - sum(old_rows.values()) != CHANGED[name]:
                        raise RuntimeError(f"Unexpected change in {name}")
                else:
                    query = text(f"SELECT count(*), md5(coalesce(string_agg(md5(row_to_json(t)::text), '' "
                                 f"ORDER BY md5(row_to_json(t)::text)), '')) FROM public.{quoted} AS t")
                    if (await before.execute(query)).one() != (await after.execute(query)).one():
                        raise RuntimeError(f"Unexpected change in {name}")
            print(f"INTEGRITY: PASS; unchanged_tables={len(names) - len(CHANGED)}; "
                  "old_blocks_and_audit_preserved; new_blocks=4; new_audit_events=4")
    finally:
        await restored.dispose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
