"""Prepare bored-pile blocks only in the explicitly isolated QA database."""
import asyncio
from types import SimpleNamespace

import vertical_qa_server  # Enforces the isolated database and disables env-file loading.
from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User
from app.services.module2_fnd3_bored_pile_blocks import add_bored_pile_blocks, add_bored_pile_reinforcement_blocks
from app.services.module2_fnd3_bored_casing import add_bored_casing_block


async def main():
    async with async_session_factory() as db:
        owner = await db.scalar(select(User.id).limit(1))
        if owner is None:
            raise RuntimeError("The restored QA database needs an existing user")
        actor = SimpleNamespace(id=owner, role="ADMIN")
        for prepare in (add_bored_pile_blocks, add_bored_pile_reinforcement_blocks):
            first = await prepare(db, actor=actor)
            second = await prepare(db, actor=actor)
            if first["edited"] or second["edited"] or second["created"] or second["reused"] != 2:
                raise RuntimeError("QA bored-pile blocks were edited or are not idempotent")
        first, second = await add_bored_casing_block(db, actor=actor), await add_bored_casing_block(db, actor=actor)
        if first["edited"] or second["edited"] or second["created"] or second["reused"] != 1:
            raise RuntimeError("QA bored-pile casing block was edited or is not idempotent")
        await db.commit()
        print("QA bored-pile blocks prepared: concrete, drilling, pouring and two reinforcement groups")


if __name__ == "__main__":
    asyncio.run(main())
