from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace as Obj
from uuid import uuid4

import pytest

from app.models.enums import CatalogProductStatus, SourceStatus, SupplierStatus, VerificationStatus
from app.services.module1_material_ui_catalog import _verified_conversion_profile, filter_material_ui_rows, material_ui_rows, supplier_offer_view


def offer(*, unit="т", price="58000", status=SupplierStatus.VERIFIED, valid_until=None,
          product=None, region="Краснодарский край"):
    supplier = Obj(id=uuid4(), name="Поставщик", status=status, region=region)
    return Obj(id=uuid4(), supplier=supplier, catalog_product=product, valid_until=valid_until,
               region=region, unit=unit, price=Decimal(price), currency="RUB", updated_at=None)


def material(name="Арматура А500С Ø12", unit="kg"):
    return Obj(id=uuid4(), canonical_name=name, base_unit=Obj(abbreviation=unit),
               category_id=None, subcategory_id=None, category=None, subcategory=None,
               attributes=[], specifications=[], catalog_products=[])


def test_valid_supplier_offer_converts_and_keeps_original_ids():
    item, item_material = offer(), material()
    view = supplier_offer_view(item, item_material, today=date.today())
    assert view.comparable_price == Decimal("58")
    assert view.id == str(item.id) and view.supplier_id == str(item.supplier.id)
    assert view.price == Decimal("58000") and view.unit == "т"


def test_unconvertible_offer_remains_visible_without_comparable_price():
    view = supplier_offer_view(offer(unit="pallet"), material(unit="piece"), today=date.today())
    assert view is not None and view.comparable_price is None
    rows, counts = filter_material_ui_rows([{"material": material(), "offers": [view]}], preset="without_price")
    assert counts["without_price"] == 1
    assert rows[0]["offer_count"] == 1 and rows[0]["price"] is None


def test_expired_blocked_or_unavailable_offers_are_excluded():
    today = date.today()
    assert supplier_offer_view(offer(valid_until=today - timedelta(days=1)), material(), today=today) is None
    assert supplier_offer_view(offer(status=SupplierStatus.BLOCKED), material(), today=today) is None
    product = Obj(status=CatalogProductStatus.UNAVAILABLE, external_url=None, raw_name="Товар")
    assert supplier_offer_view(offer(product=product), material(), today=today) is None


def test_only_verified_characteristics_with_explicit_units_support_conversion():
    item = material()
    item.specifications = [
        Obj(verified_status=VerificationStatus.VERIFIED, template=Obj(field_key="kg_per_meter"), unit="кг/м", value="0.888"),
        Obj(verified_status=VerificationStatus.NEEDS_REVIEW, template=Obj(field_key="length_mm"), unit="мм", value="600"),
        Obj(verified_status=VerificationStatus.VERIFIED, template=Obj(field_key="width_mm"), unit=None, value="400"),
    ]
    assert _verified_conversion_profile(item) == {"kg_per_meter": "0.888"}


def test_filters_use_whole_input_and_comparable_prices_only():
    today = date.today()
    first = material("Бетон B25")
    second = material("Арматура A500C")
    priced = supplier_offer_view(offer(), first, today=today)
    unpriced = supplier_offer_view(offer(unit="pallet"), second, today=today)
    rows = [{"material": first, "offers": [priced]}, {"material": second, "offers": [unpriced]}]
    result, counts = filter_material_ui_rows(rows, preset="without_price")
    assert counts == {"all": 2, "with_price": 1, "without_price": 1}
    assert [row["material"].id for row in result] == [second.id]
    result, _ = filter_material_ui_rows(rows, search="B25", minimum=Decimal("50"), maximum=Decimal("60"))
    assert [row["material"].id for row in result] == [first.id]
    assert not filter_material_ui_rows(rows, minimum=Decimal("59"))[0]


def test_search_can_match_separate_name_and_characteristic_tokens():
    item = material("Бетон B25")
    item.attributes = [Obj(attribute_name="water_resistance", attribute_value="W6")]
    rows, _ = filter_material_ui_rows([{"material": item, "offers": []}], search="W6 B25")
    assert [row["material"].id for row in rows] == [item.id]


def test_price_range_reports_minimum_inside_selected_range():
    item = material()
    cheap = supplier_offer_view(offer(price="58000"), item, today=date.today())
    dear = supplier_offer_view(offer(unit="kg", price="70"), item, today=date.today())
    result, _ = filter_material_ui_rows([{"material": item, "offers": [cheap, dear]}],
                                        minimum=Decimal("60"), maximum=Decimal("80"))
    assert result[0]["price"] == Decimal("70") and result[0]["offer_count"] == 1


def test_unlinked_source_price_is_visible_but_not_a_supplier_offer():
    item = material()
    product = Obj(id=uuid4(), status=CatalogProductStatus.ACTIVE,
                  source=Obj(name="Источник", status=SourceStatus.ACTIVE), raw_name="Товар",
                  external_url="https://example.test/item", region="Регион", price=Decimal("10"),
                  currency="RUB", unit="kg", updated_at=None)
    item.catalog_products = [product]
    item.supplier_prices = []
    rows = material_ui_rows([item])
    offer_view = rows[0]["offers"][0]
    assert offer_view.source_name == "Источник" and offer_view.supplier_id is None
    assert offer_view.price == Decimal("10") and offer_view.comparable_price is None
    assert filter_material_ui_rows(rows, preset="without_price")[1]["without_price"] == 1


@pytest.mark.asyncio
async def test_catalog_uses_the_full_isolated_database_without_writes():
    from sqlalchemy import func, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings
    from app.models.enums import MaterialStatus
    from app.models.material import Material
    from app.services.module1_material_ui_catalog import load_material_ui_catalog, material_ui_rows

    if make_url(settings.DATABASE_URL).database != "houseplatform_ui_clean_20261112":
        pytest.skip("requires the clean isolated materials UI database")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine)() as db:
        before = await db.scalar(select(func.count()).select_from(Material))
        assert before == 0
        db.add_all(Material(canonical_name=f"QA catalog material {index:03d}", status=MaterialStatus.DRAFT)
                   for index in range(55))
        await db.flush()
        expected = await db.scalar(select(func.count()).select_from(Material).where(
            Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED])))
        materials = await load_material_ui_catalog(db)
        rows = material_ui_rows(materials)
        assert len(rows) == expected == 55
        assert len({item["material"].id for item in rows}) == expected
        _, counts = filter_material_ui_rows(rows)
        assert counts["all"] == expected
        assert await db.scalar(select(func.count()).select_from(Material)) == expected
        await db.rollback()
        assert await db.scalar(select(func.count()).select_from(Material)) == before
    await engine.dispose()
