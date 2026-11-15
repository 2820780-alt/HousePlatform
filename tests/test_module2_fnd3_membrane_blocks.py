import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.user import User
from app.services.module2_fnd3_membrane_blocks import TECHNOLOGY_CODE, _id, add_membrane_blocks
from app.services.module5_estimate_snapshots import create_estimate_preview
from app.services.module7_foundation_geometry import save_foundation_geometry
from app.services.module7_strip_geometry import create_object


@pytest.mark.asyncio
async def test_membrane_rolls_and_area_allocation_on_restored_qa():
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
            first, second = await add_membrane_blocks(db, actor=user), await add_membrane_blocks(db, actor=user)
            assert first["created"] + first["reused"] == 3 and not first["edited"]
            assert second["reused"] == 3 and not second["edited"]
            tech = await db.scalar(select(Technology).where(Technology.technology_code == TECHNOLOGY_CODE,
                                                             Technology.status == "DRAFT"))
            obj = await create_object(db, actor=user, name="QA membrane")
            geometry = await save_foundation_geometry(db, actor=user, object_id=obj.id, technology_id=tech.id,
                user_values={"geometry.area":"20"}, project_values={}, expected_version=0)
            roll, pvc, work = (_id(tech.id, name, "block") for name in ("roll", "pvc", "work"))
            keys = {(roll,"MATERIAL"):"roll-material", (pvc,"MATERIAL"):"pvc-material", (work,"WORK"):"membrane-work"}
            params = {(roll,"roll.coverage_area"):"20", (roll,"roll.overlap_area"):"2",
                      (roll,"roll.roll_length"):"10", (roll,"roll.roll_width"):"1", (pvc,"pvc.coverage_area"):"0"}
            result = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=params)
            materials, works = result.payload["result"]["materials"], result.payload["result"]["works"]
            roll_line = next(line for line in materials if line["binding"]["block_id"] == roll)
            pvc_line = next(line for line in materials if line["binding"]["block_id"] == pvc)
            assert roll_line["quantity"] == "30" and pvc_line["quantity"] == "0"
            assert not any(issue.startswith("MISSING_INPUT:") for issue in pvc_line["issues"])
            assert len(works) == 1 and works[0]["quantity"] == "20"
            assert not result.payload["result"]["complete"]
            split = {**params, (roll,"roll.coverage_area"):"12", (pvc,"pvc.coverage_area"):"8",
                     (pvc,"pvc.overlap_area"):"1", (pvc,"pvc.roll_length"):"10", (pvc,"pvc.roll_width"):"1"}
            unconfirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=split)
            assert all("COVERAGE_ALLOCATION_UNVERIFIED" in line["issues"] for line in
                       unconfirmed.payload["result"]["materials"] + unconfirmed.payload["result"]["works"])
            confirmed = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys, parameter_values=split,
                membrane_areas_disjoint_confirmed=True)
            assert all("COVERAGE_ALLOCATION_UNVERIFIED" not in line["issues"] for line in
                       confirmed.payload["result"]["materials"] + confirmed.payload["result"]["works"])
            invalid = await create_estimate_preview(db, actor=user, foundation_geometry_revision_id=geometry.id,
                region="qa", terms="qa", accounting_keys=keys,
                parameter_values={**split, (pvc,"pvc.coverage_area"):"9"}, membrane_areas_disjoint_confirmed=True)
            assert all("COVERAGE_ALLOCATION_UNVERIFIED" in line["issues"] for line in
                       invalid.payload["result"]["materials"] + invalid.payload["result"]["works"])
            await db.rollback()
    finally:
        await engine.dispose()
