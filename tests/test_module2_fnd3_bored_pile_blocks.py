import os
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_bored_pile_blocks import TECHNOLOGY_CODE, _id, add_bored_pile_blocks
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_bored_pile_concrete_and_drilling_are_separate_on_restored_qa():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = await db.scalar(select(User.id).limit(1))
            user = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                {"moduleCode": code, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
                for code in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                             "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE")])
            first = await add_bored_pile_blocks(db, actor=user)
            second = await add_bored_pile_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 2 and not first["edited"]
            assert second["reused"] == 2 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA bored piles")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"pile.diameter":"0.4", "pile.length":"2", "pile.count":"5"},
                project_values={}, expected_version=0)
            first_id = _id(tech.id, "concrete-drilling", "block")
            second_id = _id(tech.id, "pouring", "block")
            snapshot = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys={(first_id,"MATERIAL"):"pile-concrete",
                    (first_id,"WORK"):"pile-drilling", (second_id,"WORK"):"pile-pouring"})
            material = snapshot.payload["result"]["materials"]
            work = snapshot.payload["result"]["works"]
            assert len(material) == 1 and abs(Decimal(material[0]["quantity"]) - Decimal("1.256637061435917")) < Decimal("0.000000000001")
            assert any(line["unit"] == "piece" and line["quantity"] == "5" for line in work)
            assert any(line["unit"] == "m3" and line["quantity"] == material[0]["quantity"] for line in work)
            assert not snapshot.payload["result"]["complete"] and snapshot.payload["missing_required_roles"]
            assert all("POTENTIAL_DOUBLE_COUNT" not in line["issues"] for line in work)
            await db.rollback()
    finally:
        await engine.dispose()
