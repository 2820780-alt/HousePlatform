from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.material_hub_view import _material_attribute_rows, _material_table_presets, templates
from app.services.module1_foundation_target_package import targets


@pytest.mark.parametrize("key,expected", [
    ("bt-02", {"Вид смеси", "Класс бетона", "Водонепроницаемость", "Тип морозостойкости", "Морозостойкость", "Подвижность"}),
    ("rebar-a500c-12", {"Класс арматуры", "Диаметр", "Масса погонного метра (заявлена)"}),
    ("xps-06", {"Толщина", "Прочность CS(10/Y)"}),
    ("fbs-02", {"Марка (заявлена)", "Длина", "Ширина", "Высота", "Стандарт (заявлен)"}),
    ("fl-12", {"Марка (заявлена)", "Длина", "Ширина", "Группа несущей способности", "Стандарт (заявлен)"}),
])
def test_material_card_displays_only_stored_technical_attributes(key, expected):
    target = next(item for item in targets() if item.key == key)
    values = {**target.expected, **dict(target.properties), "registry_origin": "internal"}
    material = SimpleNamespace(attributes=[SimpleNamespace(attribute_name=k, attribute_value=v) for k, v in values.items()])
    rows = _material_attribute_rows(material)
    labels = {row["label"] for row in rows}
    assert expected <= labels
    assert "registry origin" not in labels and "registry code" not in labels
    if key.startswith(("fbs-", "fl-")):
        assert "Масса" not in labels
    if key.startswith("rebar-"):
        assert "Профиль" not in labels


def test_existing_without_price_preset_and_template_are_available():
    preset = next(item for item in _material_table_presets("needs_price") if item["key"] == "needs_price")
    assert preset["label"] == "Без цены" and preset["active"]
    templates.env.get_template("material_hub_data.html")


@pytest.mark.asyncio
async def test_without_price_query_is_server_side_and_not_limited_to_first_page():
    from sqlalchemy.dialects import postgresql
    from app.api.v1.material_hub_view import _load_materials

    class CaptureDB:
        async def execute(self, statement):
            self.statement = statement
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    db = CaptureDB()
    assert await _load_materials(db, without_price=True) == []
    sql = str(db.statement.compile(dialect=postgresql.dialect())).lower()
    assert " limit " not in sql
    assert sql.count("exists") >= 2
    assert "catalog_products.material_id = materials.id" in sql
    assert "supplier_prices.material_id = materials.id" in sql
    assert "supplier_prices.valid_until" in sql


@pytest.mark.asyncio
async def test_without_price_uses_all_server_rows_and_valid_prices_on_isolated_database():
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.api.v1.material_hub_view import _load_material_price_map, _load_materials
    from app.config import settings
    from app.models.catalog_product import CatalogProduct
    from app.models.enums import CatalogProductStatus, MaterialStatus, SourceType, SupplierStatus
    from app.models.material import Material
    from app.models.source import Source
    from app.models.supplier import Supplier
    from app.models.supplier_price import SupplierPrice

    if make_url(settings.DATABASE_URL).database != "houseplatform_fnd_m1_m2_20261110":
        pytest.skip("requires the dedicated restored foundation database")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        marker = str(uuid4())
        old = datetime(2000, 1, 1)
        target = Material(canonical_name=f"test without price {marker}", status=MaterialStatus.DRAFT, created_at=old)
        priced = Material(canonical_name=f"test priced {marker}", status=MaterialStatus.DRAFT)
        supplier_priced = Material(canonical_name=f"test supplier price {marker}", status=MaterialStatus.DRAFT)
        expired = Material(canonical_name=f"test expired price {marker}", status=MaterialStatus.DRAFT)
        inactive = Material(canonical_name=f"test inactive offer {marker}", status=MaterialStatus.DRAFT)
        source = Source(name=f"test {marker}", source_type=SourceType.RETAIL)
        supplier = Supplier(name=f"test {marker}", status=SupplierStatus.VERIFIED)
        db.add_all([target, priced, supplier_priced, expired, inactive, source, supplier])
        db.add_all([Material(canonical_name=f"test {marker} {i}", status=MaterialStatus.DRAFT)
                    for i in range(501)])
        await db.flush()
        db.add(CatalogProduct(source_id=source.id, material_id=priced.id, raw_name="test",
                              price=Decimal("1"), status=CatalogProductStatus.ACTIVE))
        inactive_product = CatalogProduct(source_id=source.id, material_id=inactive.id, raw_name="test",
                                          price=Decimal("3"), status=CatalogProductStatus.UNAVAILABLE)
        db.add(inactive_product)
        await db.flush()
        db.add_all([
            SupplierPrice(supplier_id=supplier.id, material_id=supplier_priced.id, price=Decimal("2")),
            SupplierPrice(supplier_id=supplier.id, material_id=expired.id, price=Decimal("2"),
                          valid_until=date.today() - timedelta(days=1)),
            SupplierPrice(supplier_id=supplier.id, material_id=inactive.id, catalog_product_id=inactive_product.id,
                          price=Decimal("3")),
        ])
        await db.flush()
        items = {item.id for item in await _load_materials(db, without_price=True)}
        assert target.id in items and expired.id in items and inactive.id in items
        assert priced.id not in items and supplier_priced.id not in items
        assert len(items) > 500
        prices = await _load_material_price_map(db)
        assert str(priced.id) in prices and str(supplier_priced.id) in prices
        assert str(target.id) not in prices and str(expired.id) not in prices and str(inactive.id) not in prices
        await db.rollback()
    await engine.dispose()
