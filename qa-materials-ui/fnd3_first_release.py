"""Apply reviewed FND-3 draft blocks only to the explicitly guarded database."""
import argparse
import asyncio
import hashlib
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent
QA_DATABASE = "houseplatform_fnd3_release_20261117"
LIVE_DATABASE = "buildplatform"
BACKUP = ROOT / "backup/fnd3-first-release-20261117/buildplatform.dump"
BACKUP_SHA256 = "a6a82c7668d9e772648c1f708bbc4865add3c3bb71fa09ffb9fb27e2464d7b8e"

parser = argparse.ArgumentParser()
parser.add_argument("--database", required=True, choices=(QA_DATABASE, LIVE_DATABASE))
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
if args.database == LIVE_DATABASE and (
    not args.apply or os.environ.get("ATOM_FND3_FIRST_RELEASE") != "houseplatform.buildplatform"
):
    raise SystemExit("Live release requires the explicit HousePlatform release guard")
if args.database == QA_DATABASE and args.apply:
    raise SystemExit("The fresh QA run must roll back")
if not BACKUP.is_file() or hashlib.sha256(BACKUP.read_bytes()).hexdigest() != BACKUP_SHA256:
    raise SystemExit("Verified release backup is missing or has changed")

original_init = BaseSettings.__init__


def no_env_file(self, *args, **kwargs):
    kwargs["_env_file"] = None
    return original_init(self, *args, **kwargs)


BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ:
        url = make_url(os.environ[key])
        if url.host != "db" or url.database != LIVE_DATABASE:
            raise SystemExit("Database connection is not the guarded HousePlatform source")
        os.environ[key] = url.set(database=args.database).render_as_string(hide_password=False)
os.environ["APP_DEBUG"] = "false"
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text
from app.database import async_session_factory, engine
from app.models.enums import UserRole, UserStatus
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_batch import prepare_foundation_drafts


async def main():
    if engine.url.host != "db" or engine.url.database != args.database:
        raise RuntimeError("Database identity mismatch")
    async with async_session_factory() as db:
        if await db.scalar(text("SELECT current_database()")) != args.database:
            raise RuntimeError("Connected database identity mismatch")
        actor = await db.scalar(select(User).where(User.role == UserRole.ADMIN,
                                                    User.status == UserStatus.ACTIVE).order_by(User.created_at))
        if actor is None:
            raise RuntimeError("An active administrator is required")
        active_query = select(Technology.id, Technology.technology_code, Technology.revision).where(
            Technology.status == "ACTIVE").order_by(Technology.id)
        active_before = (await db.execute(active_query)).all()
        first = await prepare_foundation_drafts(db, actor=actor)
        second = await prepare_foundation_drafts(db, actor=actor)
        if len({item["technology_id"] for item in first}) != 15:
            raise RuntimeError("Expected exactly 15 draft technologies")
        if any(item["edited"] for item in first + second) or any(item["created"] for item in second):
            raise RuntimeError("Draft preparation is not conflict-free and idempotent")
        if (await db.execute(active_query)).all() != active_before:
            raise RuntimeError("Active technology revisions changed")
        created = sum(item["created"] for item in first)
        if args.apply:
            await db.commit()
        else:
            await db.rollback()
        print(f"{'APPLY' if args.apply else 'DRY_RUN'}: PASS; drafts=15; "
              f"created_blocks={created}; active_preserved={len(active_before)}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
