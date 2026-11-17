import os
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module1_manual_calculation_price import append_manual_price
from app.services.module2_fnd3_uff_blocks import TECHNOLOGY_CODE
from app.services.module2_fnd3_uff_sleeves import SLEEVE_WORK, _id, add_uff_sleeve_blocks, expected_sleeve_blocks
from app.services.module5_estimate_snapshots import create_estimate_preview, read_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_uff_sleeve_materials_and_work_share_saved_geometry():
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
            first = await add_uff_sleeve_blocks(db, actor=actor)
            second = await add_uff_sleeve_blocks(db, actor=actor)
            assert first["created"] + first["reused"] == 3 and not first["edited"]
            assert second["created"] == 0 and second["reused"] == 3 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            work_catalog_item = await db.get(WorkCatalogItem, SLEEVE_WORK)
            work_catalog_item.default_unit = "linear_meter"
            await db.flush()
            with pytest.raises(ValueError, match="must be measured in pieces"):
                await expected_sleeve_blocks(db, tech)
            work_catalog_item.default_unit = "piece"
            await db.flush()
            obj = await create_object(db, actor=actor, name="QA UFF sleeves")
            values = {"geometry.length":"12", "geometry.width":"0.4", "geometry.height":"0.8",
                      "strip.overlap_volume":"0.2", "geometry.net_area":"50", "geometry.slab_thickness":"0.1",
                      "uff.sleeves_dn110":"2", "uff.sleeves_dn160":"3"}
            geometry = await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=tech.id,
                user_values=values, project_values={}, expected_version=0)
            ids = {key: _id(tech.id, key, "block") for key in ("dn110", "dn160", "work")}
            rows = (await db.scalars(select(TechnologyCalculationBlock).where(
                TechnologyCalculationBlock.technology_id == tech.id))).all()
            keys = {(str(row.id), kind): f"qa:{row.id}:{kind}" for row in rows for kind in ("MATERIAL", "WORK")}
            region = "qa-" + uuid.uuid4().hex
            await append_manual_price(db, work_code=SLEEVE_WORK, amount=Decimal("100"), region=region, terms="qa",
                                      effective_from=date.today(), actor_id=owner)
            blocked = await create_estimate_preview(db, actor=actor, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=keys, uff_floor_disjoint_confirmed=True)
            work = next(line for line in blocked.payload["result"]["works"] if line["binding"]["block_id"] == ids["work"])
            assert Decimal(work["quantity"]) == 5 and "BUNDLE_SCOPE_UNVERIFIED" in work["issues"]
            assert Decimal(work["amount_for_total"]) == 0
            approved = await create_estimate_preview(db, actor=actor, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=keys, uff_floor_disjoint_confirmed=True,
                uff_sleeve_scope_confirmed=True)
            materials = {line["binding"]["block_id"]: line for line in approved.payload["result"]["materials"]}
            assert Decimal(materials[ids["dn110"]]["quantity"]) == 2
            assert Decimal(materials[ids["dn160"]]["quantity"]) == 3
            work = next(line for line in approved.payload["result"]["works"] if line["binding"]["block_id"] == ids["work"])
            assert Decimal(work["quantity"]) == 5 and Decimal(work["amount_for_total"]) == 500
            resized = await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=tech.id,
                user_values={**values, "uff.sleeves_dn110":"4"}, project_values={}, expected_version=1)
            changed = await create_estimate_preview(db, actor=actor, foundation_geometry_revision_id=resized.id,
                region=region, terms="qa", accounting_keys=keys, uff_floor_disjoint_confirmed=True,
                uff_sleeve_scope_confirmed=True)
            changed_work = next(line for line in changed.payload["result"]["works"] if line["binding"]["block_id"] == ids["work"])
            assert Decimal(changed_work["quantity"]) == 7 and Decimal(changed_work["amount_for_total"]) == 700
            saved = await read_estimate_preview(db, actor=actor, snapshot_id=approved.id)
            old_work = next(line for line in saved.payload["result"]["works"] if line["binding"]["block_id"] == ids["work"])
            assert Decimal(old_work["quantity"]) == 5 and saved.payload["uff_sleeve_scope_confirmed"]
            missing = await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=tech.id,
                user_values={key: value for key, value in values.items() if key != "uff.sleeves_dn160"},
                project_values={}, expected_version=2)
            incomplete = await create_estimate_preview(db, actor=actor, foundation_geometry_revision_id=missing.id,
                region=region, terms="qa", accounting_keys=keys, uff_floor_disjoint_confirmed=True,
                uff_sleeve_scope_confirmed=True)
            missing_work = next(line for line in incomplete.payload["result"]["works"] if line["binding"]["block_id"] == ids["work"])
            assert missing_work["quantity"] is None and not incomplete.payload["result"]["complete"]
            await db.rollback()
    finally:
        await engine.dispose()
