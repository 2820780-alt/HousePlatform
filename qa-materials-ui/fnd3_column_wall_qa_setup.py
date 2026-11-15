"""Prepare column and wall concrete only in the explicitly isolated QA database."""
import asyncio
from types import SimpleNamespace

import vertical_qa_server  # Enforces the isolated database and disables env-file loading.
from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User
from app.services.module2_fnd3_column_wall_blocks import (REBAR_ROLES, ROLES, add_column_wall_concrete,
                                                          add_column_wall_formwork, add_column_wall_reinforcement)


async def main():
    async with async_session_factory() as db:
        owner = await db.scalar(select(User.id).limit(1))
        if owner is None:
            raise RuntimeError("The restored QA database needs an existing user")
        actor = SimpleNamespace(id=owner, role="ADMIN")
        for code in ROLES:
            first = await add_column_wall_concrete(db, actor=actor, technology_code=code)
            second = await add_column_wall_concrete(db, actor=actor, technology_code=code)
            if first["edited"] or second["edited"] or second["created"] or second["reused"] != 1:
                raise RuntimeError("QA concrete blocks were edited or are not idempotent")
            first = await add_column_wall_reinforcement(db, actor=actor, technology_code=code)
            second = await add_column_wall_reinforcement(db, actor=actor, technology_code=code)
            if first["edited"] or second["edited"] or second["created"] or second["reused"] != len(REBAR_ROLES[code]):
                raise RuntimeError("QA reinforcement blocks were edited or are not idempotent")
            first = await add_column_wall_formwork(db, actor=actor, technology_code=code)
            second = await add_column_wall_formwork(db, actor=actor, technology_code=code)
            if first["edited"] or second["edited"] or second["created"] or second["reused"] != 1:
                raise RuntimeError("QA formwork blocks were edited or are not idempotent")
        await db.commit()
        print("QA column and wall concrete, reinforcement and formwork blocks prepared")


if __name__ == "__main__":
    asyncio.run(main())
