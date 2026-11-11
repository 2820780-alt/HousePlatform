"""Run the reviewed foundation material release in an explicitly named database."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
parser = argparse.ArgumentParser()
parser.add_argument("--database", required=True, choices=("buildplatform", "houseplatform_m1archive_check_20261111",
                                                        "houseplatform_fnd_final_restore_20261111"))
parser.add_argument("--fingerprint", required=True)
parser.add_argument("--commit", action="store_true")
args = parser.parse_args()
original_init = BaseSettings.__init__


def no_env_file(self, *values, **kwargs):
    kwargs["_env_file"] = None
    original_init(self, *values, **kwargs)


BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ:
        os.environ[key] = make_url(os.environ[key]).set(database=args.database).render_as_string(hide_password=False)
os.environ["MODULE1_REF_RUNTIME_MODE"] = "legacy"
os.environ["MODULE1_REF45_MODE"] = "legacy"
os.environ["MODULE1_REF6_MODE"] = "legacy"

from app.config import settings
from app.services.module1_foundation_material_release import release_foundation_materials


async def main():
    if make_url(settings.DATABASE_URL).database != args.database:
        raise RuntimeError("Unexpected database")
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            result = await release_foundation_materials(db, expected_inventory_fingerprint=args.fingerprint)
            result["committed"] = args.commit
            if args.commit:
                await db.commit()
            else:
                await db.rollback()
            print(json.dumps({"created": result["created"], "reused": result["reused"],
                              "blocked_count": len(result["blocked"]), "committed": args.commit}, ensure_ascii=False))
    finally:
        await engine.dispose()


asyncio.run(main())
