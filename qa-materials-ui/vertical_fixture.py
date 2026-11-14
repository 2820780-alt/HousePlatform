"""Create only isolated QA data for browser smoke; never connects to the live DB."""
import asyncio
import uuid

import vertical_qa_server  # configures and verifies the exact isolated DB before app imports
from sqlalchemy import select
from app.database import async_session_factory
from app.models.module2_technology import Technology
from app.models.supplier import Supplier
from app.models.enums import SupplierStatus
from app.services.module1_work_catalog_store import seed_existing_work_catalog


async def main():
    async with async_session_factory() as db:
        await seed_existing_work_catalog(db)
        for name in ("QA vertical supplier 1", "QA vertical supplier 2"):
            if not await db.scalar(select(Supplier.id).where(Supplier.name == name)):
                db.add(Supplier(name=name, status=SupplierStatus.POTENTIAL))
        code = "QA_VERTICAL_BROWSER_" + uuid.uuid4().hex
        technology = Technology(id=uuid.uuid4(), technology_code=code, revision=1,
                                name="QA ленточный фундамент", status="DRAFT")
        second = Technology(id=uuid.uuid4(), technology_code="QA_VERTICAL_SLAB_" + uuid.uuid4().hex,
                            revision=1, name="QA монолитная плита", status="DRAFT")
        db.add_all([technology, second])
        await db.commit()
        print(str(technology.id), str(second.id))


asyncio.run(main())
