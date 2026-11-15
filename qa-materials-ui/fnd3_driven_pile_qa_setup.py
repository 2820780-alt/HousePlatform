"""Prepare factory-pile blocks only in the explicitly isolated QA database."""
import asyncio
from types import SimpleNamespace

import vertical_qa_server  # Enforces the isolated database and disables env-file loading.
from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User
from app.services.module2_fnd3_driven_pile_blocks import add_driven_pile_blocks


async def main():
    async with async_session_factory() as db:
        owner = await db.scalar(select(User.id).limit(1))
        if owner is None:
            raise RuntimeError("The restored QA database needs an existing user")
        actor = SimpleNamespace(id=owner, role="ADMIN")
        first = await add_driven_pile_blocks(db, actor=actor)
        second = await add_driven_pile_blocks(db, actor=actor)
        if first["edited"] or second["edited"] or second["created"] or second["reused"] != 3:
            raise RuntimeError("QA factory-pile blocks were edited or are not idempotent")
        await db.commit()
        print("QA factory-pile blocks prepared: two variants and one installation work")


if __name__ == "__main__":
    asyncio.run(main())
