from __future__ import annotations

import os
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import MODULE2_OWNER_CODE, Technology
from app.models.user import User
from app.services.module7_strip_geometry import MODULE7_CODE, _length, create_object, read_strip_geometry, save_strip_geometry


def actor(user_id):
    return SimpleNamespace(id=user_id, role="SUPPLIER", moduleAccessRules=[
        {"moduleCode": MODULE7_CODE, "accessLevel": "EDIT", "accessScope": "GLOBAL"},
        {"moduleCode": MODULE2_OWNER_CODE, "accessLevel": "EDIT", "accessScope": "GLOBAL"},
    ])


@pytest.mark.parametrize("invalid", [0, "-1", "NaN", "Infinity", "0.0000001", 0.4, True, "10000000000"])
def test_geometry_rejects_invalid_dimensions(invalid):
    with pytest.raises(ValueError):
        _length(invalid)


@pytest.mark.asyncio
async def test_geometry_versions_are_owned_and_preserve_previous_values_on_restored_qa():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner_id = await db.scalar(select(User.id).limit(1))
            assert owner_id
            user = actor(owner_id)
            tech = Technology(id=uuid.uuid4(), technology_code="QA_STRIP_" + uuid.uuid4().hex,
                              revision=1, name="QA strip", status="DRAFT")
            db.add(tech)
            await db.flush()
            obj = await create_object(db, actor=user, name="QA object")
            first = await save_strip_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                                              length_m="10", width_m="0.4", height_m="1", expected_version=0)
            second = await save_strip_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                                               length_m="10", width_m="0.5", height_m="1", expected_version=1)
            assert first.version == 1 and first.width_m == Decimal("0.4")
            assert second.version == 2 and second.width_m == Decimal("0.5")
            assert (await read_strip_geometry(db, actor=user, revision_id=first.id)).width_m == Decimal("0.4")
            with pytest.raises(ValueError, match="geometry changed"):
                await save_strip_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                                          length_m="1", width_m="1", height_m="1", expected_version=1)
            with pytest.raises(ValueError, match="not found"):
                await read_strip_geometry(db, actor=actor(uuid.uuid4()), revision_id=first.id)
            await db.rollback()
    finally:
        await engine.dispose()
