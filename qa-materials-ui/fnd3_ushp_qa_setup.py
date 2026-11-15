"""Prepare USHP blocks only in the explicitly isolated QA database."""
import asyncio
from types import SimpleNamespace

import vertical_qa_server  # Enforces the isolated database and disables env-file loading.
from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User
from app.services.module2_fnd3_ribbed_slab_blocks import USHP_CODE, add_ribbed_slab_blocks
from app.services.module2_fnd3_ushp_blocks import add_ushp_blocks, add_ushp_geotextile_block, add_ushp_preparation_blocks


async def main():
    async with async_session_factory() as db:
        owner = await db.scalar(select(User.id).limit(1))
        if owner is None:
            raise RuntimeError("The restored QA database needs an existing user")
        actor = SimpleNamespace(id=owner, role="ADMIN")
        for prepare, expected in ((lambda: add_ribbed_slab_blocks(db, actor=actor, technology_code=USHP_CODE), 2),
                                  (lambda: add_ushp_blocks(db, actor=actor), 4),
                                  (lambda: add_ushp_preparation_blocks(db, actor=actor), 2),
                                  (lambda: add_ushp_geotextile_block(db, actor=actor), 1)):
            first, second = await prepare(), await prepare()
            if first["edited"] or second["edited"] or second["created"] or second["reused"] != expected:
                raise RuntimeError("QA USHP blocks were edited or are not idempotent")
        await db.commit()
        print("QA USHP concrete, insulation, preparation and aggregate reinforcement blocks prepared")


if __name__ == "__main__":
    asyncio.run(main())
