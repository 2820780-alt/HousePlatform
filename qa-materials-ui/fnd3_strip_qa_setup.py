"""Prepare the reviewed strip draft in the explicitly isolated QA database."""
import asyncio
from types import SimpleNamespace

import vertical_qa_server  # Enforces the isolated database and disables env-file loading.
from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User
from app.services.module2_fnd3_strip_blocks import add_strip_blocks


async def main():
    async with async_session_factory() as db:
        owner = await db.scalar(select(User.id).limit(1))
        if owner is None:
            raise RuntimeError("The restored QA database needs an existing user")
        actor = SimpleNamespace(id=owner, role="ADMIN")
        first = await add_strip_blocks(db, actor=actor)
        if first["edited"]:
            raise RuntimeError("QA strip blocks were edited; refusing to overwrite them")
        second = await add_strip_blocks(db, actor=actor)
        if second["created"] or second["reused"] != 5 or second["edited"]:
            raise RuntimeError("QA strip block setup is not idempotent")
        await db.commit()
        print(f"QA strip blocks: created={first['created']} reused={first['reused']} repeat_created=0")


if __name__ == "__main__":
    asyncio.run(main())
