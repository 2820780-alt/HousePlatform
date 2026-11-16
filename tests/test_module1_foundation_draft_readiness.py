from types import SimpleNamespace
import os
import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.enums import MaterialStatus
from app.services.module1_foundation_material_release import (
    PACKAGE, is_technically_identified_foundation_draft, releasable_foundation_targets,
)


def test_foundation_draft_readiness_requires_existing_technical_identity_not_price_or_documents():
    target = next(item for item in releasable_foundation_targets()[0] if item.key == "xps-04")
    values = {**target.expected, **dict(target.properties), "registry_key": target.key, "registry_origin": PACKAGE}
    material = SimpleNamespace(status=MaterialStatus.DRAFT, canonical_name=target.title,
        base_unit=SimpleNamespace(abbreviation=target.unit), quality_issues=[],
        attributes=[SimpleNamespace(attribute_name=key, attribute_value=value) for key, value in values.items()])
    assert is_technically_identified_foundation_draft(material)
    field = next(item for item in material.attributes if item.attribute_name == "thickness_mm")
    field.attribute_value = "100"
    assert not is_technically_identified_foundation_draft(material)
    field.attribute_value = values["thickness_mm"]
    material.base_unit.abbreviation = "kg"
    assert not is_technically_identified_foundation_draft(material)
    material.base_unit.abbreviation = target.unit
    material.quality_issues = [SimpleNamespace(status="OPEN", severity="CRITICAL", issue_type="identity_conflict")]
    assert not is_technically_identified_foundation_draft(material)
    material.quality_issues = [SimpleNamespace(status="OPEN", severity="HIGH", issue_type="missing_document_link")]
    assert is_technically_identified_foundation_draft(material)
    material.quality_issues = [SimpleNamespace(status="OPEN", severity="HIGH", issue_type="TECHNICAL_REVIEW_REQUIRED")]
    assert not is_technically_identified_foundation_draft(material)
    material.status = MaterialStatus.ARCHIVED
    assert not is_technically_identified_foundation_draft(material)


@pytest.mark.asyncio
async def test_reviewed_block_accepts_identified_draft_xps_without_price_on_qa(monkeypatch):
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.database import engine as configured_engine
    from app.models.material_attribute import MaterialAttribute
    from app.models.material import Material
    from sqlalchemy.orm import selectinload
    from app.models.module2_technology import Technology, TechnologyMaterialRequirement
    from app.models.user import User
    from app.services.module2_calculation_blocks import add_block, verify_block, require_verified_calculation_blocks
    from app.services.module2_fnd3_ushp_blocks import edge_material_block
    import app.services.module2_estimation_export as export

    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            owner = await db.scalar(select(User.id).limit(1))
            actor = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                {"moduleCode": "MODULE_02_KNOWLEDGE_BASE", "accessLevel": "ADMIN", "accessScope": "GLOBAL"}])
            xps_id = await db.scalar(select(MaterialAttribute.material_id).where(
                MaterialAttribute.attribute_name == "registry_code", MaterialAttribute.attribute_value == "XPS-04"))
            assert xps_id
            xps = await db.scalar(select(Material).where(Material.id == xps_id).options(
                selectinload(Material.attributes), selectinload(Material.base_unit), selectinload(Material.quality_issues)))
            attrs = {item.attribute_name: item.attribute_value for item in xps.attributes}
            assert attrs["registry_code"] == "XPS-04"
            assert not is_technically_identified_foundation_draft(xps)
            tech = Technology(id=uuid.uuid4(), technology_code="QA_READINESS_" + uuid.uuid4().hex,
                              revision=1, name="QA readiness", status="DRAFT")
            db.add(tech)
            await db.flush()
            role = TechnologyMaterialRequirement(id=uuid.uuid4(), technology_id=tech.id, code="EDGE_XPS",
                selector_kind="CANONICAL_MATERIAL", canonical_material_id=xps_id, technical_constraints={})
            db.add(role)
            await db.flush()
            graph = edge_material_block(tech.id, role)
            row = await add_block(db, technology_id=tech.id, block=graph, actor=actor, actor_id=owner)
            await verify_block(db, technology_id=tech.id, block_id=row.id, expected_version=1,
                               source="QA geometry rule", actor=actor, actor_id=owner)
            with pytest.raises(ValueError, match="технически определённый"):
                await require_verified_calculation_blocks(db, tech.id)
            for issue in xps.quality_issues:
                if issue.issue_type == "TECHNICAL_REVIEW_REQUIRED":
                    issue.status = "RESOLVED"
            await db.flush()
            await require_verified_calculation_blocks(db, tech.id)
            exported_tech = Technology(id=uuid.uuid4(), technology_code="QA_EXPORT_" + uuid.uuid4().hex,
                revision=1, status="ACTIVE", name="QA export", source_kind="HUMAN_CURATED",
                input_missing_fields=[], input_blockers=[])
            exported_tech.requirements.append(TechnologyMaterialRequirement(id=uuid.uuid4(), code="EDGE_XPS",
                selector_kind="CANONICAL_MATERIAL", canonical_material_id=xps_id, technical_constraints={}))
            monkeypatch.setattr(export, "read_technology", AsyncMock(return_value=exported_tech))
            monkeypatch.setattr(export, "verify_evidence_references", AsyncMock(return_value=frozenset()))
            package = await export.build_module5_estimation_input_package(db, exported_tech.id)
            assert "canonical_material_not_verified" not in package.material_requirements[0].blockers
            thickness = await db.scalar(select(MaterialAttribute).where(
                MaterialAttribute.material_id == xps_id, MaterialAttribute.attribute_name == "thickness_mm"))
            assert thickness is not None
            thickness.attribute_value = "999"
            await db.flush()
            with pytest.raises(ValueError, match="технически определённый"):
                await require_verified_calculation_blocks(db, tech.id)
            rejected_package = await export.build_module5_estimation_input_package(db, exported_tech.id)
            assert "canonical_material_not_verified" in rejected_package.material_requirements[0].blockers
            await db.rollback()
    finally:
        await engine.dispose()
