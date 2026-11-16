from types import SimpleNamespace
from dataclasses import replace
import asyncio
import os
from uuid import uuid4

import pytest

from app.services.module2_calculation_blocks import encode_definition
from app.services.module2_calculation_package_v2 import build_calculation_package_v2
from app.services.module2_calculation_presets import rectangular_volume_block
from app.services.module2_calculation_blocks import add_block


def test_calculation_package_is_versioned_deterministic_and_revision_scoped():
    technology = SimpleNamespace(id=uuid4(), technology_code="QA", revision=2, status="DRAFT")
    graph = rectangular_volume_block()
    row = SimpleNamespace(id=uuid4(), technology_id=technology.id, version=1, position=1, name="QA block",
                          material_id=uuid4(), work_code="qa_work", definition=encode_definition(graph))
    package, digest = build_calculation_package_v2(technology, [row])
    same, same_digest = build_calculation_package_v2(technology, [row])
    assert package.contract_version == "2" and package.technology_revision == 2
    assert package.blocks[0].material_id == row.material_id and package.blocks[0].work_code == "qa_work"
    assert package == same and digest == same_digest
    row.version = 2
    assert build_calculation_package_v2(technology, [row])[1] != digest
    assert package.blocks[0].version == 1
    with pytest.raises(ValueError, match="duplicate"):
        build_calculation_package_v2(technology, [row, row])
    row.technology_id = uuid4()
    with pytest.raises(ValueError, match="different technology"):
        build_calculation_package_v2(technology, [row])


@pytest.mark.asyncio
async def test_package_revision_lock_serializes_draft_block_edits():
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.database import engine as configured_engine
    from app.models.module2_technology import Technology
    from app.models.user import User

    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as reader, sessions() as editor:
            technology_id = await reader.scalar(select(Technology.id).where(
                Technology.technology_code == "FND_SLAB_USHP", Technology.status == "DRAFT"))
            owner = await reader.scalar(select(User.id).limit(1))
            assert technology_id and owner
            actor = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                {"moduleCode": "MODULE_02_KNOWLEDGE_BASE", "accessLevel": "ADMIN", "accessScope": "GLOBAL"}])
            await reader.scalar(select(Technology).where(Technology.id == technology_id).with_for_update())
            block = replace(rectangular_volume_block(), material_output_id=None, work_output_id=None)
            pending = asyncio.create_task(add_block(editor, technology_id=technology_id, block=block,
                                                     actor=actor, actor_id=owner))
            try:
                done, _ = await asyncio.wait({pending}, timeout=0.5)
                assert not done, "draft edit must wait for the revision lock"
                await reader.rollback()
                assert await asyncio.wait_for(pending, timeout=10)
            finally:
                if not pending.done():
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                await editor.rollback()
    finally:
        await engine.dispose()
