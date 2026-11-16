"""Read-only inspection of temporary builder-smoke blocks in the QA database."""
import asyncio

import vertical_qa_server  # Forces the restored QA database.
from sqlalchemy import select

from app.database import async_session_factory
from app.models.module2_calculation_block import TechnologyCalculationBlock


async def main():
    async with async_session_factory() as db:
        rows = (await db.scalars(select(TechnologyCalculationBlock).where(
            TechnologyCalculationBlock.name.like("QA copy %")))).all()
        for item in rows:
            print(str(item.id), item.name, str(item.created_by_user_id))


if __name__ == "__main__":
    asyncio.run(main())
