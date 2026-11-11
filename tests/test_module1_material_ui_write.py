from uuid import uuid4

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_ui_write_preserves_identity_and_refuses_unsafe_unit_change_on_isolated_db():
    from sqlalchemy import func, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings
    from app.models.enums import SupplierStatus, UserRole, UserStatus, VerificationStatus
    from app.models.material import Material
    from app.models.material_analog import MaterialAnalog
    from app.models.material_category import MaterialCategory
    from app.models.material_specification import MaterialSpecification
    from app.models.module2_technology import TechnologyMaterialRequirement
    from app.models.supplier import Supplier
    from app.models.supplier_price import SupplierPrice
    from app.models.specification_template import SpecificationTemplate
    from app.models.unit import Unit
    from app.models.user import User
    from app.models.unit_conversion_rule import UnitConversionRule
    from app.services.module1_material_ui_write import MaterialUIAttribute, MaterialUIConversion, MaterialUISpecification, MaterialUIWrite, save_material_ui

    if make_url(settings.DATABASE_URL).database != "houseplatform_fnd_m1_m2_20261110":
        pytest.skip("requires the isolated materials UI database")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        before = await db.scalar(select(func.count()).select_from(Material))
        actor = await db.scalar(select(User).where(User.role == UserRole.ADMIN, User.status == UserStatus.ACTIVE).limit(1))
        category = await db.scalar(select(MaterialCategory).where(MaterialCategory.name == "Крепёж и монтажные изделия"))
        units = list((await db.scalars(select(Unit).limit(2))).all())
        assert actor and category and len(units) == 2
        marker = f"QA identity {uuid4()}"
        payload = MaterialUIWrite(name=marker, category_id=category.id, base_unit_id=units[0].id,
                                  description="Первое описание", purpose="Назначение",
                                  attributes=[MaterialUIAttribute(name="QA параметр", value="125", value_type="number"),
                                              MaterialUIAttribute(name="diameter_mm", value="12")])
        created = await save_material_ui(db, payload, actor_id=actor.id)
        material_id = created.id
        analog = Material(canonical_name=f"QA analog {uuid4()}", category_id=category.id, base_unit_id=units[0].id)
        db.add(analog)
        await db.flush()
        with_analog = payload.model_copy(update={"analog_ids": [analog.id]})
        await save_material_ui(db, with_analog, actor_id=actor.id, material_id=material_id)
        await save_material_ui(db, with_analog, actor_id=actor.id, material_id=material_id)
        analogs = (await db.scalars(select(MaterialAnalog).where(MaterialAnalog.material_id == material_id))).all()
        assert len(analogs) == 1 and analogs[0].status == "NEEDS_REVIEW"
        await save_material_ui(db, payload.model_copy(update={"analog_ids": []}), actor_id=actor.id, material_id=material_id)
        assert analogs[0].status == "ARCHIVED"
        template = SpecificationTemplate(category_id=category.id, name="QA цвет", field_key=f"qa_color_{uuid4().hex}")
        db.add(template)
        await db.flush()
        spec = MaterialSpecification(material_id=material_id, template_id=template.id, value="Белый",
                                     verified_status=VerificationStatus.VERIFIED)
        db.add(spec)
        await db.flush()
        await db.refresh(created, attribute_names=["specifications"])
        supplier = Supplier(name=f"QA supplier {uuid4()}", status=SupplierStatus.VERIFIED)
        db.add(supplier)
        await db.flush()
        price = SupplierPrice(supplier_id=supplier.id, material_id=material_id, price=100, unit=units[0].abbreviation)
        db.add(price)
        requirement = await db.scalar(select(TechnologyMaterialRequirement).limit(1))
        assert requirement is not None
        requirement.canonical_material_id = material_id
        await db.flush()
        updated = await save_material_ui(db, payload.model_copy(update={"description": "Новое описание"}),
                                         actor_id=actor.id, material_id=material_id)
        assert updated.id == material_id and updated.description == "Новое описание"
        assert next(item for item in updated.attributes if item.attribute_name == "QA параметр").value_type == "number"
        assert requirement.canonical_material_id == material_id and price.material_id == material_id
        await save_material_ui(db, payload.model_copy(update={"specifications": [
            MaterialUISpecification(id=spec.id, value="Серый")]}), actor_id=actor.id, material_id=material_id)
        assert spec.value == "Серый" and spec.verified_status == VerificationStatus.NEEDS_REVIEW
        changed_identity = payload.model_copy(update={"attributes": [MaterialUIAttribute(name="diameter_mm", value="16")]})
        with pytest.raises(HTTPException) as changed:
            await save_material_ui(db, changed_identity, actor_id=actor.id, material_id=material_id)
        assert changed.value.status_code == 409
        invalid_dimension = payload.model_copy(update={"attributes": [
            MaterialUIAttribute(name="QA dimension", value="-1", value_type="dimension")]})
        with pytest.raises(HTTPException) as invalid:
            await save_material_ui(db, invalid_dimension, actor_id=actor.id, material_id=material_id)
        assert invalid.value.status_code == 400
        conversion = MaterialUIConversion(from_unit_id=units[1].id, coefficient="2", source="QA reference")
        with_conversion = payload.model_copy(update={"conversions": [conversion]})
        await save_material_ui(db, with_conversion, actor_id=actor.id, material_id=material_id)
        await save_material_ui(db, with_conversion, actor_id=actor.id, material_id=material_id)
        rules = (await db.scalars(select(UnitConversionRule).where(UnitConversionRule.material_id == material_id))).all()
        assert len(rules) == 1 and rules[0].status == "NEEDS_REVIEW" and rules[0].coefficient == 2
        modified = MaterialUIConversion(from_unit_id=units[1].id, coefficient="3", source="QA updated reference")
        await save_material_ui(db, payload.model_copy(update={"conversions": [modified]}),
                               actor_id=actor.id, material_id=material_id)
        assert rules[0].coefficient == 3 and rules[0].source == "QA updated reference"
        rules[0].status = "ACTIVE"
        with pytest.raises(HTTPException) as active_rule_error:
            await save_material_ui(db, with_conversion, actor_id=actor.id, material_id=material_id)
        assert active_rule_error.value.status_code == 409
        with pytest.raises(HTTPException) as error:
            await save_material_ui(db, payload.model_copy(update={"base_unit_id": units[1].id}),
                                   actor_id=actor.id, material_id=material_id)
        assert error.value.status_code == 409
        with pytest.raises(HTTPException) as duplicate:
            await save_material_ui(db, payload, actor_id=actor.id)
        assert duplicate.value.status_code == 409
        assert await db.scalar(select(func.count()).select_from(Material)) == before + 2
        await db.rollback()
        assert await db.scalar(select(func.count()).select_from(Material)) == before
    await engine.dispose()
