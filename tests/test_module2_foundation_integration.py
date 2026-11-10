from unittest.mock import AsyncMock

import pytest

from app.services.module2_foundation_integration import prepare_foundation_integration
from app.services.module2_technology_foundation import Module2TechnologyPermissionError


@pytest.mark.asyncio
async def test_package_requires_edit_permission_and_complete_reviewed_snapshot():
    db = AsyncMock()
    with pytest.raises(Module2TechnologyPermissionError):
        await prepare_foundation_integration(db, expected_existing_materials=0,
            expected_material_fingerprint="0" * 32, expected_active_revisions={},
            actor_role_code="CUSTOMER", acknowledge_test_data=True)
    with pytest.raises(ValueError, match="identify all foundation technologies"):
        await prepare_foundation_integration(db, expected_existing_materials=0,
            expected_material_fingerprint="0" * 32, expected_active_revisions={},
            actor_role_code="ENGINEER_DESIGNER", acknowledge_test_data=True)
    db.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_transactional_package_on_fresh_isolated_backup():
    from sqlalchemy import func, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.config import settings
    from app.models.material import Material
    from app.models.module2_technology import Technology
    from app.services.module1_foundation_target_package import material_inventory_fingerprint

    if make_url(settings.DATABASE_URL).database != "houseplatform_fnd_fresh_20261110_175041":
        pytest.skip("requires the dedicated fresh restored foundation database")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine)() as db:
        count = await db.scalar(select(func.count()).select_from(Material))
        fingerprint = await material_inventory_fingerprint(db)
        rows = (await db.execute(select(Technology.technology_code, Technology.id, Technology.revision).where(
            Technology.status == "ACTIVE", Technology.technology_code.like("FND_%")))).all()
        snapshot = {code: (ident, revision) for code, ident, revision in rows}
        wrong_snapshot = dict(snapshot)
        code = next(iter(wrong_snapshot))
        wrong_snapshot[code] = (wrong_snapshot[code][0], wrong_snapshot[code][1] + 1)
        with pytest.raises(ValueError, match="revisions changed"):
            await prepare_foundation_integration(db, expected_existing_materials=count,
                expected_material_fingerprint=fingerprint, expected_active_revisions=wrong_snapshot,
                actor_role_code="ENGINEER_DESIGNER", acknowledge_test_data=True)
        with pytest.raises(ValueError, match="inventory changed"):
            await prepare_foundation_integration(db, expected_existing_materials=count + 1,
                expected_material_fingerprint=fingerprint, expected_active_revisions=snapshot,
                actor_role_code="ENGINEER_DESIGNER", acknowledge_test_data=True)
        assert await material_inventory_fingerprint(db) == fingerprint
        result = await prepare_foundation_integration(db, expected_existing_materials=count,
            expected_material_fingerprint=fingerprint, expected_active_revisions=snapshot,
            actor_role_code="ENGINEER_DESIGNER", acknowledge_test_data=True)
        assert result["materials"]["created"] + result["materials"]["reused"] == 118
        assert result["technology_drafts"]["drafts"] == 15
        assert result["technology_drafts"]["direct_links"] > 0
        assert result["existing_gaps"] == 40
        with pytest.raises(ValueError, match="draft or review revision already exists"):
            await prepare_foundation_integration(db, expected_existing_materials=count,
                expected_material_fingerprint=fingerprint, expected_active_revisions=snapshot,
                actor_role_code="ENGINEER_DESIGNER", acknowledge_test_data=True)
        await db.rollback()
        assert await material_inventory_fingerprint(db) == fingerprint
    await engine.dispose()


@pytest.mark.asyncio
async def test_nested_material_reference_in_m2_json_is_found_in_postgres():
    from uuid import uuid4
    from sqlalchemy import select
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.config import settings
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.models.module2_technology import Technology, TechnologyDefaultAssumption
    from app.services.module1_foundation_target_package import _m2_json_referenced_material_ids

    if make_url(settings.DATABASE_URL).database != "houseplatform_fnd_fresh_20261110_175041":
        pytest.skip("requires the dedicated fresh restored foundation database")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine)() as db:
        technology_id = await db.scalar(select(Technology.id).where(Technology.status == "ACTIVE").limit(1))
        material = Material(id=uuid4(), canonical_name="Test JSON reference", status=MaterialStatus.DRAFT)
        db.add(material)
        db.add(TechnologyDefaultAssumption(technology_id=technology_id, assumption_code=f"TEST_{uuid4().hex}",
            revision=1, parameter_code="TEST_JSON_REFERENCE", name_ru="Test", value_type="MATERIAL_CLASS",
            default_value={"value": "category"}, source_kind="PLATFORM_ASSUMPTION", applicability={},
            auto_fallback=False, warning_level="INFO", allowed_values_strategy="EXPLICIT_M1_MATERIALS",
            allowed_values={"nested": [{"material_ids": [str(material.id)]}]}, status="ACTIVE"))
        await db.flush()
        assert material.id in await _m2_json_referenced_material_ids(db, {material.id})
        await db.rollback()
    await engine.dispose()
