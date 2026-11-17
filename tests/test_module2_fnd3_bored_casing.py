import os
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module1_manual_calculation_price import append_manual_price
from app.services.module2_fnd3_bored_casing import CASING_WORK, _id, add_bored_casing_block
from app.services.module2_fnd3_bored_pile_blocks import TECHNOLOGY_CODE
from app.services.module5_estimate_snapshots import create_estimate_preview, read_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_bored_casing_requires_scope_and_explicit_material_selection():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = await db.scalar(select(User.id).limit(1))
            actor = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                {"moduleCode": code, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
                for code in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                             "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE")])
            first = await add_bored_casing_block(db, actor=actor)
            second = await add_bored_casing_block(db, actor=actor)
            assert first["created"] + first["reused"] == 1 and not first["edited"]
            assert second["created"] == 0 and second["reused"] == 1 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=actor, name="QA bored casing")
            values = {"pile.diameter":"0.3", "pile.length":"4", "pile.count":"5", "pile.casing_length":"12.5"}
            geometry = await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=tech.id,
                user_values=values, project_values={}, expected_version=0)
            rows = (await db.scalars(select(TechnologyCalculationBlock).where(
                TechnologyCalculationBlock.technology_id == tech.id))).all()
            keys = {(str(row.id), kind): f"qa:{row.id}:{kind}" for row in rows for kind in ("MATERIAL", "WORK")}
            region = "qa-" + uuid.uuid4().hex
            await append_manual_price(db, work_code=CASING_WORK, amount=Decimal("20"), region=region, terms="qa",
                                      effective_from=date.today(), actor_id=owner)
            block_id = _id(tech.id, "block")
            blocked = await create_estimate_preview(db, actor=actor, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=keys)
            line = next(line for line in blocked.payload["result"]["works"] if line["binding"]["block_id"] == block_id)
            assert Decimal(line["quantity"]) == Decimal("12.5") and "BUNDLE_SCOPE_UNVERIFIED" in line["issues"]
            assert Decimal(line["amount_for_total"]) == 0
            approved = await create_estimate_preview(db, actor=actor, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=keys, pile_casing_scope_confirmed=True)
            line = next(line for line in approved.payload["result"]["works"] if line["binding"]["block_id"] == block_id)
            assert Decimal(line["amount_for_total"]) == Decimal("250")
            assert "Для обсадки выберите материал и уточните его расход" in approved.payload["missing_required_roles"]
            assert not approved.payload["result"]["complete"]
            resized = await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=tech.id,
                user_values={**values, "pile.casing_length":"15"}, project_values={}, expected_version=1)
            changed = await create_estimate_preview(db, actor=actor, foundation_geometry_revision_id=resized.id,
                region=region, terms="qa", accounting_keys=keys, pile_casing_scope_confirmed=True)
            line = next(line for line in changed.payload["result"]["works"] if line["binding"]["block_id"] == block_id)
            assert Decimal(line["quantity"]) == 15 and Decimal(line["amount_for_total"]) == 300
            saved = await read_estimate_preview(db, actor=actor, snapshot_id=approved.id)
            old = next(line for line in saved.payload["result"]["works"] if line["binding"]["block_id"] == block_id)
            assert Decimal(old["quantity"]) == Decimal("12.5") and saved.payload["pile_casing_scope_confirmed"]
            zero = await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=tech.id,
                user_values={**values, "pile.casing_length":"0"}, project_values={}, expected_version=2)
            unused = await create_estimate_preview(db, actor=actor, foundation_geometry_revision_id=zero.id,
                region=region, terms="qa", accounting_keys=keys)
            assert "Для обсадки выберите материал и уточните его расход" not in unused.payload["missing_required_roles"]
            missing = await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=tech.id,
                user_values={key: value for key, value in values.items() if key != "pile.casing_length"},
                project_values={}, expected_version=3)
            incomplete = await create_estimate_preview(db, actor=actor, foundation_geometry_revision_id=missing.id,
                region=region, terms="qa", accounting_keys=keys, pile_casing_scope_confirmed=True)
            line = next(line for line in incomplete.payload["result"]["works"] if line["binding"]["block_id"] == block_id)
            assert line["quantity"] is None and not incomplete.payload["result"]["complete"]
            await db.rollback()
    finally:
        await engine.dispose()
