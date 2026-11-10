from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.models.catalog_product import CatalogProduct
from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.module2_material_gap import Module2MaterialGap
from app.models.price_history import PriceHistory
from app.models.source_task import SourceTask
from app.services.module1_foundation_target_package import (
    PACKAGE, _externally_referenced_material_ids, _normalized, _target_match,
    apply_foundation_target_package, material_inventory_fingerprint, targets,
)


def test_target_identities_use_existing_normalizer_and_are_distinct():
    items = targets()
    assert len(items) == 118
    assert len({item.key for item in items}) == 118
    assert all(_normalized(item).suggested_group_code == item.group for item in items
               if item.group != "unclassified")
    assert all(_normalized(item) is not None for item in items)
    assert all(item.missing for item in items)


def test_requested_variants_are_distinct_and_remain_review_candidates():
    items = {item.key: item for item in targets()}
    for code in ("bt-01", "bt-02", "bt-03", "bt-04", "rm-01", "rm-02", "fbs-11", "fl-22",
                 "xps-10", "base-05", "form-10", "arm-aux-07", "wpr-10", "drn-07",
                 "pen-04", "pile-s-06", "pile-rc-02"):
        assert code in items
    assert dict(items["rebar-a500c-12"].properties)["declared_theoretical_mass_kg_per_m"] == "0.888"
    assert items["bt-02"].expected["frost_type"] == "F1"
    assert items["bt-02"].expected != items["bt-03"].expected
    assert items["fl-11"].expected["load_group"] != items["fl-12"].expected["load_group"]
    assert items["xps-03"].expected != items["xps-06"].expected
    assert items["pile-rc-01"].missing


def test_owned_class_and_fully_specified_profiles_do_not_merge():
    items = {item.key: item for item in targets()}
    attrs = [SimpleNamespace(attribute_name="registry_origin", attribute_value=PACKAGE),
             SimpleNamespace(attribute_name="registry_key", attribute_value="bt-02")]
    profile = SimpleNamespace(canonical_name="БСТ B25 W6 F1 150 P4", attributes=attrs)
    assert _target_match(profile, items["bt-02"])
    assert not _target_match(profile, items["concrete-25"])


@pytest.mark.asyncio
async def test_cross_module_foreign_keys_are_protected_without_reading_m1_history():
    from unittest.mock import AsyncMock
    from uuid import uuid4

    knowledge_id, future_module_id = uuid4(), uuid4()
    rows = [("public", "catalog_products", "material_id"),
            ("public", "knowledge_resource_links", "material_id"),
            ("public", "future_module_items", "material_id")]
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)),
        scalars=AsyncMock(side_effect=[SimpleNamespace(all=lambda: [knowledge_id]),
                                      SimpleNamespace(all=lambda: [future_module_id])]),
    )
    assert await _externally_referenced_material_ids(db) == {knowledge_id, future_module_id}
    assert db.scalars.await_count == 2
    assert '"knowledge_resource_links"' in str(db.scalars.await_args_list[0].args[0])


@pytest.mark.asyncio
async def test_missing_fk_inventory_blocks_archival():
    from unittest.mock import AsyncMock
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))
    with pytest.raises(ValueError, match="FK inventory is empty"):
        await _externally_referenced_material_ids(db)


@pytest.mark.asyncio
async def test_mocked_package_archives_only_unprotected_and_is_idempotent(monkeypatch):
    from unittest.mock import AsyncMock
    from uuid import uuid4
    import app.services.module1_foundation_target_package as package

    old = Material(id=uuid4(), canonical_name="Старый тестовый материал", status=MaterialStatus.AUTO_CREATED)
    linked = Material(id=uuid4(), canonical_name="Материал со внешней связью", status=MaterialStatus.NEEDS_REVIEW)
    confirmed = Material(id=uuid4(), canonical_name="Подтверждённая карточка", status=MaterialStatus.VERIFIED)
    for material in (old, linked, confirmed):
        material.attributes = []
    categories = [SimpleNamespace(id=uuid4(), slug=slug) for slug in {
        item.category_slug for item in targets() if item.category_slug
    }]
    unit_ids = {name: uuid4() for name in ("m", "m2", "m3", "piece")}

    class MemorySession:
        def __init__(self):
            self.materials = [old, linked, confirmed]

        async def execute(self, statement):
            return None

        async def scalars(self, statement):
            sql = str(statement)
            if "FROM materials" in sql:
                values = self.materials
            elif "FROM material_categories" in sql:
                values = categories
            elif any(name in sql for name in (
                "FROM module2_technology_material_requirements", "FROM module2_material_gaps",
                "FROM module2_technology_default_assumptions",
            )):
                values = []
            else:
                raise AssertionError(f"unexpected query: {sql}")
            return SimpleNamespace(all=lambda: values)

        def add(self, value):
            if isinstance(value, Material):
                self.materials.append(value)

        async def flush(self):
            pass

    async def unit(_db, name, _kind):
        return SimpleNamespace(id=unit_ids[name])

    monkeypatch.setattr(package, "_unit", unit)
    monkeypatch.setattr(package, "_externally_referenced_material_ids", AsyncMock(return_value={linked.id}))
    monkeypatch.setattr(package, "material_inventory_fingerprint", AsyncMock(return_value="0" * 32))
    monkeypatch.setattr(package, "log_event", AsyncMock())
    db = MemorySession()

    result = await apply_foundation_target_package(db, expected_existing=3,
        expected_inventory_fingerprint="0" * 32, acknowledge_test_data=True)
    assert result["archived"] == 1 and result["created"] == len(targets())
    assert old.status == MaterialStatus.ARCHIVED
    assert linked.status == MaterialStatus.NEEDS_REVIEW
    assert confirmed.status == MaterialStatus.VERIFIED
    assert all(item.status == MaterialStatus.DRAFT for item in db.materials[3:])
    repeat = await apply_foundation_target_package(
        db, expected_existing=len(db.materials), expected_inventory_fingerprint="0" * 32, acknowledge_test_data=True)
    assert repeat["created"] == repeat["archived"] == repeat["enriched_attributes"] == 0
    assert repeat["reused"] == len(targets())


@pytest.mark.asyncio
async def test_inventory_mismatch_fails_before_any_material_changes():
    from unittest.mock import AsyncMock
    material = Material(canonical_name="Тест", status=MaterialStatus.NEEDS_REVIEW)
    db = SimpleNamespace(execute=AsyncMock(), scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [material])))
    with pytest.raises(ValueError, match="inventory changed"):
        await apply_foundation_target_package(db, expected_existing=2,
            expected_inventory_fingerprint="0" * 32, acknowledge_test_data=True)
    assert material.status == MaterialStatus.NEEDS_REVIEW


def test_rebar_diameter_and_class_are_not_interchangeable(monkeypatch):
    from app.services.module1_material_normalizer import settings

    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "disabled")
    candidates = {item.key: item for item in targets()}
    steel = SimpleNamespace(canonical_name="Арматура А500С Ø12 мм", attributes=[])
    assert _target_match(steel, candidates["rebar-a500c-12"])
    assert not _target_match(steel, candidates["rebar-a500c-16"])
    assert not _target_match(steel, candidates["rebar-a240-10"])


def test_ambiguous_normalizer_result_does_not_match_a_target(monkeypatch):
    import app.services.module1_foundation_target_package as package

    monkeypatch.setattr(package, "normalize_raw_ingestion_item", lambda _: SimpleNamespace(
        suggested_group_code=None, normalized_characteristics={}))
    target = next(item for item in targets() if item.key == "rebar-a500c-12")
    steel = SimpleNamespace(canonical_name="Арматура А500С Ø12 мм", attributes=[])
    assert not _target_match(steel, target)


@pytest.mark.asyncio
async def test_target_package_is_idempotent_and_preserves_linked_tables():
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.config import settings

    if make_url(settings.DATABASE_URL).database != "houseplatform_fnd_m1_m2_20261110":
        pytest.skip("requires the dedicated restored foundation database")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine)() as db:
        async def count(model):
            return await db.scalar(select(func.count()).select_from(model))
        before = {model.__tablename__: await count(model)
                  for model in (Material, CatalogProduct, PriceHistory, SourceTask, Module2MaterialGap)}
        fingerprint = await material_inventory_fingerprint(db)
        with pytest.raises(ValueError, match="explicit acknowledgement"):
            await apply_foundation_target_package(db, expected_existing=before["materials"],
                                                  expected_inventory_fingerprint=fingerprint)
        result = await apply_foundation_target_package(
            db, expected_existing=before["materials"], expected_inventory_fingerprint=fingerprint,
            acknowledge_test_data=True)
        assert result["created"] + result["reused"] == len(targets())
        again = await apply_foundation_target_package(
            db, expected_existing=before["materials"] + result["created"],
            expected_inventory_fingerprint=await material_inventory_fingerprint(db), acknowledge_test_data=True)
        assert again["created"] == again["archived"] == again["enriched_attributes"] == 0
        assert again["target_ids"] == result["target_ids"]
        assert await count(Material) == before["materials"] + result["created"]
        for model in (CatalogProduct, PriceHistory, SourceTask, Module2MaterialGap):
            assert await count(model) == before[model.__tablename__]
        selected = (await db.scalars(select(Material).where(Material.id.in_(result["target_ids"].values())))).all()
        assert len(selected) == len(targets()) and all(item.status == MaterialStatus.DRAFT for item in selected)
        await db.rollback()
    await engine.dispose()
