import os
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module1_manual_calculation_price import append_manual_price
from app.services.module2_fnd3_driven_pile_blocks import (TECHNOLOGY_CODE, _id, add_driven_pile_blocks,
    expected_blocks, add_driven_head_treatment_block, expected_head_treatment_block)
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_factory_pile_allocation_prevents_false_totals_on_restored_qa():
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
            first = await add_driven_pile_blocks(db, actor=user)
            second = await add_driven_pile_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 3 and not first["edited"]
            assert second["reused"] == 3 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            blocks = await expected_blocks(db, tech)
            detail = await add_driven_head_treatment_block(db, actor=user)
            repeated = await add_driven_head_treatment_block(db, actor=user)
            assert detail["created"] + detail["reused"] == 1 and not detail["edited"]
            assert repeated["reused"] == 1 and not repeated["edited"]
            head = await expected_head_treatment_block(db, tech)
            region = "qa-" + uuid.uuid4().hex
            for block in blocks[:2]:
                await append_manual_price(db, material_id=uuid.UUID(block.material_id), amount=Decimal("100"),
                    region=region, terms="qa", effective_from=date.today(), actor_id=owner)
            await append_manual_price(db, work_code=blocks[2].work_code, amount=Decimal("10"),
                region=region, terms="qa", effective_from=date.today(), actor_id=owner)
            obj = await create_object(db, actor=user, name="QA factory piles")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"pile.count":"5"}, project_values={}, expected_version=0)
            a, b, work = (_id(tech.id, name, "block") for name in ("pile_first", "pile_second", "work"))
            keys = {(a,"MATERIAL"):"factory-a", (b,"MATERIAL"):"factory-b", (work,"WORK"):"factory-install",
                    (head.id,"WORK"):"factory-head-treatment"}
            mismatch = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=keys,
                parameter_values={(a,"pile_first.count"):"3", (b,"pile_second.count"):"3",
                                  (head.id,"pile.head_treatment_count"):"0"})
            lines = mismatch.payload["result"]["materials"] + mismatch.payload["result"]["works"]
            assert all("PILE_ALLOCATION_UNVERIFIED" in line["issues"] for line in lines)
            assert all(Decimal(line["amount_for_total"]) == 0 for line in lines)
            assert "Распределение количества свай по исполнениям не подтверждено" in mismatch.payload["missing_required_roles"]
            correct = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=keys,
                parameter_values={(a,"pile_first.count"):"3", (b,"pile_second.count"):"2",
                                  (head.id,"pile.head_treatment_count"):"0"})
            assert sorted(line["quantity"] for line in correct.payload["result"]["materials"]) == ["2", "3"]
            assert correct.payload["result"]["works"][0]["quantity"] == "5"
            assert correct.payload["result"]["known_total"] == "550.00"
            assert not correct.payload["result"]["complete"]
            await append_manual_price(db, work_code=head.work_code, amount=Decimal("20"),
                region=region, terms="qa", effective_from=date.today(), actor_id=owner)
            head_keys = {**keys, (head.id, "WORK"): "factory-head-treatment"}
            parameters = {(a,"pile_first.count"):"3", (b,"pile_second.count"):"2",
                          (head.id,"pile.head_treatment_count"):"3"}
            unconfirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=head_keys, parameter_values=parameters)
            head_line = next(item for item in unconfirmed.payload["result"]["works"] if item["binding"]["block_id"] == head.id)
            assert "BUNDLE_SCOPE_UNVERIFIED" in head_line["issues"] and Decimal(head_line["amount_for_total"]) == 0
            confirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=head_keys, parameter_values=parameters,
                driven_head_scope_confirmed=True)
            head_line = next(item for item in confirmed.payload["result"]["works"] if item["binding"]["block_id"] == head.id)
            assert head_line["quantity"] == "3" and Decimal(head_line["amount_for_total"]) == 60
            assert Decimal(confirmed.payload["result"]["known_total"]) == 610
            too_many = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=head_keys,
                parameter_values={**parameters, (head.id,"pile.head_treatment_count"):"6"},
                driven_head_scope_confirmed=True)
            head_line = next(item for item in too_many.payload["result"]["works"] if item["binding"]["block_id"] == head.id)
            assert "PILE_ALLOCATION_UNVERIFIED" in head_line["issues"] and Decimal(head_line["amount_for_total"]) == 0
            zero = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region=region, terms="qa", accounting_keys=head_keys,
                parameter_values={**parameters, (head.id,"pile.head_treatment_count"):"0"})
            head_line = next(item for item in zero.payload["result"]["works"] if item["binding"]["block_id"] == head.id)
            assert head_line["quantity"] == "0" and "BUNDLE_SCOPE_UNVERIFIED" not in head_line["issues"]
            await db.rollback()
    finally:
        await engine.dispose()
