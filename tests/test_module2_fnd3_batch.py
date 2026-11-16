import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.user import User
from app.services import module2_fnd3_batch


def qa_engine():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    return create_async_engine(configured_engine.url.set(database=dbname), echo=False)


@pytest.mark.asyncio
async def test_foundation_batch_is_idempotent_in_qa():
    engine = qa_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            actor = SimpleNamespace(id=await db.scalar(select(User.id).limit(1)), role="ADMIN")
            first = await module2_fnd3_batch.prepare_foundation_drafts(db, actor=actor)
            second = await module2_fnd3_batch.prepare_foundation_drafts(db, actor=actor)
            assert len({item["technology_id"] for item in first}) == 15
            assert all(not item["edited"] for item in first + second)
            assert all(item["created"] == 0 for item in second)
            await db.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_foundation_batch_rolls_back_on_conflict(monkeypatch):
    engine = qa_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            row = await db.scalar(select(TechnologyCalculationBlock).limit(1))
            original = row.name

            async def stage_change(db, *, actor):
                row.name = original + " QA"
                await db.flush()
                return {"edited": []}

            async def conflict(db, *, actor):
                return {"edited": ["changed"]}

            monkeypatch.setattr(module2_fnd3_batch, "_steps", lambda: [stage_change, conflict])
            with pytest.raises(ValueError, match="no batch changes applied"):
                await module2_fnd3_batch.prepare_foundation_drafts(db, actor=object())
            await db.refresh(row)
            assert row.name == original
            await db.rollback()
    finally:
        await engine.dispose()
