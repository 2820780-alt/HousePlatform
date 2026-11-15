import os

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology, TechnologyWorkStep
from app.services.module2_fnd3_work_details import DETAILS, add_foundation_work_details, candidates


def test_fnd3_details_reference_reviewed_candidates():
    source = candidates()
    assert len(source) == 54 and len(DETAILS) == 4
    assert all(f"FND-WK-{number:03d}" in source for values in DETAILS.values() for number in values)


@pytest.mark.asyncio
async def test_fnd3_detailed_work_is_conditional_and_idempotent_on_restored_qa():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
                technologies = (await db.scalars(select(Technology).where(
                    Technology.status == "DRAFT", Technology.technology_code.in_(DETAILS)))).all()
                ids = {item.id for item in technologies}
                before = {(row.id, row.work_code, row.position) for row in (await db.scalars(
                    select(TechnologyWorkStep).where(TechnologyWorkStep.technology_id.in_(ids)))).all()}
                first = await add_foundation_work_details(db)
                after = (await db.scalars(select(TechnologyWorkStep).where(
                    TechnologyWorkStep.technology_id.in_(ids)))).all()
                assert before <= {(row.id, row.work_code, row.position) for row in after}
                assert set(first) == set(DETAILS) and all(value["bundle_retained"] for value in first.values())
                assert all(row.applicability_expression and "проектом" in row.applicability_expression
                           for row in after if row.id not in {item[0] for item in before})
                grillage = next(item for item in technologies if item.technology_code == "FND_PILE_GRILLAGE")
                earthwork = next(row for row in after if row.technology_id == grillage.id and
                                 row.work_code == "earthworks_razrabotka_grunta_tehnikoy")
                assert "свайно-ростверковый" in earthwork.instructions and "Плиты" in earthwork.instructions
                second = await add_foundation_work_details(db)
                assert all(value["created"] == 0 for value in second.values())
            await transaction.rollback()
    finally:
        await engine.dispose()
