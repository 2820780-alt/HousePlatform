"""Prepare blocked M2 foundation revisions against a restored revision snapshot."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
REFERENCE = "houseplatform_fnd_final_restore_20261111"
parser = argparse.ArgumentParser()
parser.add_argument("--database", required=True, choices=("buildplatform", REFERENCE))
parser.add_argument("--commit", action="store_true")
args = parser.parse_args()
original_init = BaseSettings.__init__


def no_env_file(self, *values, **kwargs):
    kwargs["_env_file"] = None
    original_init(self, *values, **kwargs)


BaseSettings.__init__ = no_env_file
if "DATABASE_URL" not in os.environ:
    raise RuntimeError("No database connection configured")
base = make_url(os.environ["DATABASE_URL"])
os.environ["DATABASE_URL"] = base.set(database=args.database).render_as_string(hide_password=False)
if "DATABASE_URL_SYNC" in os.environ:
    os.environ["DATABASE_URL_SYNC"] = make_url(os.environ["DATABASE_URL_SYNC"]).set(database=args.database).render_as_string(hide_password=False)

from app.config import settings
from app.models.module2_technology import Technology
from app.services.module2_foundation_integration import prepare_partial_foundation_drafts
from app.services.module2_foundation_preliminary_profiles import PROFILES


async def main():
    if make_url(settings.DATABASE_URL).database != args.database:
        raise RuntimeError("Unexpected database")
    reference = create_async_engine(base.set(database=REFERENCE))
    destination = create_async_engine(settings.DATABASE_URL)
    try:
        codes = {profile.technology_code for profile in PROFILES}
        async with async_sessionmaker(reference, expire_on_commit=False)() as snapshot_db:
            active = (await snapshot_db.scalars(select(Technology).where(
                Technology.technology_code.in_(codes), Technology.status == "ACTIVE"))).all()
            snapshot = {item.technology_code: (item.id, item.revision) for item in active}
        async with async_sessionmaker(destination, expire_on_commit=False)() as db:
            result = await prepare_partial_foundation_drafts(
                db, expected_active_revisions=snapshot, actor_role_code="ENGINEER_DESIGNER")
            if args.commit:
                await db.commit()
            else:
                await db.rollback()
            print(json.dumps({"drafts": result["drafts"], "gaps": result["existing_gaps"],
                              "legacy_linked": sum(len(item["legacy_linked"]) for item in result["reports"]),
                              "legacy_unresolved": sum(len(item["legacy_unresolved"]) for item in result["reports"]),
                              "added_roles": sum(len(item["added_roles"]) for item in result["reports"]),
                              "unresolved_roles": sum(len(item["unresolved"]) for item in result["reports"]),
                              "committed": args.commit}, ensure_ascii=False))
    finally:
        await destination.dispose()
        await reference.dispose()


asyncio.run(main())
