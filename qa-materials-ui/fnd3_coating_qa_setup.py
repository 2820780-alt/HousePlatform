"""Prepare coating blocks only in the explicitly isolated QA database."""
import asyncio
from types import SimpleNamespace

import vertical_qa_server  # Enforces the isolated database and disables env-file loading.
from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User
from app.services.module2_fnd3_coating_blocks import add_coating_blocks, add_coating_primer_work
from app.services.module2_fnd3_work_details import add_foundation_work_details


async def main():
    async with async_session_factory() as db:
        owner = await db.scalar(select(User.id).limit(1))
        if owner is None:
            raise RuntimeError("The restored QA database needs an existing user")
        actor = SimpleNamespace(id=owner, role="ADMIN")
        first = await add_coating_blocks(db, actor=actor)
        second = await add_coating_blocks(db, actor=actor)
        if first["edited"] or second["edited"] or second["created"] or second["reused"] != 2:
            raise RuntimeError("QA coating blocks were edited or are not idempotent")
        await add_foundation_work_details(db)
        first, second = await add_coating_primer_work(db, actor=actor), await add_coating_primer_work(db, actor=actor)
        if first["edited"] or second["edited"] or second["created"] or second["reused"] != 1:
            raise RuntimeError("QA primer work was edited or is not idempotent")
        await db.commit()
        print("QA coating blocks prepared: primer, mastic, bundled and separate primer work")


if __name__ == "__main__":
    asyncio.run(main())
