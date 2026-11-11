"""Create identifiable test-only offer fixtures in the dedicated restored QA DB."""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
QA_DATABASE = "houseplatform_fnd_m1_m2_20261110"
original_init = BaseSettings.__init__


def no_env_file(self, *args, **kwargs):
    kwargs["_env_file"] = None
    return original_init(self, *args, **kwargs)


BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ:
        os.environ[key] = make_url(os.environ[key]).set(database=QA_DATABASE).render_as_string(hide_password=False)
os.environ["APP_DEBUG"] = "false"

from app.config import settings
from app.database import async_session_factory, engine
from app.models.catalog_product import CatalogProduct
from app.models.enums import CatalogProductStatus, MaterialStatus, SourceType, SupplierStatus, UnitType
from app.models.material import Material
from app.models.material_analog import MaterialAnalog
from app.models.material_category import MaterialCategory
from app.models.source import Source
from app.models.supplier import Supplier
from app.models.supplier_price import SupplierPrice
from app.models.unit import Unit


async def main():
    if make_url(settings.DATABASE_URL).database != QA_DATABASE:
        raise RuntimeError("Refusing fixture creation outside the QA database")
    async with async_session_factory() as db:
        if await db.scalar(select(Material.id).where(Material.canonical_name == "QA изолированный материал B25")):
            print("QA fixtures already exist")
            return
        category = await db.scalar(select(MaterialCategory).where(MaterialCategory.slug == "m1-ui-concrete-cement-mortar"))
        if not category:
            raise RuntimeError("Apply the QA-only category migration first")
        unit = await db.scalar(select(Unit).where(Unit.abbreviation == "kg"))
        if unit is None:
            unit = Unit(name="QA килограмм", abbreviation="kg", unit_type=UnitType.WEIGHT, is_base=True)
            db.add(unit)
            await db.flush()
        item = Material(canonical_name="QA изолированный материал B25", category_id=category.id,
                        base_unit_id=unit.id, status=MaterialStatus.DRAFT)
        analog = Material(canonical_name="QA изолированный аналог B20", category_id=category.id,
                          base_unit_id=unit.id, status=MaterialStatus.DRAFT)
        source = Source(name="QA тестовый источник", source_type=SourceType.SUPPLIER)
        suppliers = [Supplier(name=f"QA поставщик {number}", status=SupplierStatus.VERIFIED,
                              region="Краснодарский край") for number in (1, 2, 3)]
        db.add_all([item, analog, source, *suppliers])
        await db.flush()
        db.add(MaterialAnalog(material_id=item.id, analog_material_id=analog.id,
                              status="ACTIVE", reason="Только тестовый аналог"))
        for number, supplier in enumerate(suppliers, 1):
            product = CatalogProduct(source_id=source.id, material_id=item.id,
                                     raw_name=f"QA товар поставщика {number}",
                                     external_url=f"https://example.test/material-{number}",
                                     status=CatalogProductStatus.ACTIVE)
            db.add(product)
            await db.flush()
            prices = [("58000", "т"), ("70", "kg"), ("8300", "pallet")]
            value, sale_unit = prices[number - 1]
            db.add(SupplierPrice(supplier_id=supplier.id, material_id=item.id,
                                 catalog_product_id=product.id, price=Decimal(value),
                                 currency="RUB", unit=sale_unit, region="Краснодарский край"))
        await db.commit()
        print("QA-only material, suppliers, offers and analog created")
    await engine.dispose()


asyncio.run(main())
