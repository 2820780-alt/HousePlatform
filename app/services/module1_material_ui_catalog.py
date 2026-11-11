"""Read-only catalogue projections for the M1 materials workspace."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import AnyHttpUrl, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.catalog_product import CatalogProduct
from app.models.enums import CatalogProductStatus, MaterialStatus, SourceStatus, SupplierStatus, VerificationStatus
from app.models.material import Material
from app.models.material_analog import MaterialAnalog
from app.models.material_attribute import MaterialAttribute
from app.models.material_specification import MaterialSpecification
from app.models.supplier_price import SupplierPrice
from app.services.module1_material_ui_prices import comparable_rule_price, comparable_unit_price
from app.services.module1_material_normalizer import normalize_raw_ingestion_item
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem

MATERIAL_UI_CATEGORIES = (
    "Сыпучие материалы", "Бетон, цемент и растворы", "Стеновые и сборные изделия",
    "Арматура и металлопрокат", "Пиломатериалы и листы", "Изоляционные материалы",
    "Кровельные материалы", "Облицовочные материалы", "Строительные смеси и химия",
    "Напольные покрытия", "Материалы для стен и потолков", "Окна и двери",
    "Трубы и водоотведение", "Крепёж и монтажные изделия",
)
_HTTP_URL = TypeAdapter(AnyHttpUrl)


def _safe_external_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = _HTTP_URL.validate_python(value)
    except ValidationError:
        return None
    if not parsed.host or parsed.username or parsed.password:
        return None
    return str(parsed)


@dataclass(frozen=True)
class SupplierOfferView:
    id: str
    supplier_id: str | None
    supplier: str
    name: str
    region: str | None
    price: Decimal | None
    currency: str | None
    unit: str | None
    comparable_price: Decimal | None
    updated_at: Any
    url: str | None
    source_name: str | None = None


def supplier_offer_view(offer: SupplierPrice, material: Material, *, today: date,
                        material_group: str | None = None, material_profile: dict | None = None,
                        conversion_rules: list | None = None) -> SupplierOfferView | None:
    """Exclude expired/blocked offers and never invent a sale unit or product URL."""
    supplier = offer.supplier
    product = offer.catalog_product
    if supplier is None or supplier.status == SupplierStatus.BLOCKED:
        return None
    if offer.valid_until is not None and offer.valid_until < today:
        return None
    if product is not None and product.status != CatalogProductStatus.ACTIVE:
        return None
    unit = material.base_unit.abbreviation if material.base_unit else None
    comparable = comparable_unit_price(offer.price, offer.unit, unit, currency=offer.currency,
                                       material_group=material_group, material_profile=material_profile)
    if comparable is None and conversion_rules:
        comparable = comparable_rule_price(offer.price, offer.unit, unit, conversion_rules, currency=offer.currency)
    url = _safe_external_url(product.external_url if product is not None else None)
    return SupplierOfferView(
        id=str(offer.id), supplier_id=str(supplier.id), supplier=supplier.name,
        name=product.raw_name if product else material.canonical_name,
        region=offer.region or supplier.region, price=offer.price, currency=offer.currency,
        unit=offer.unit, comparable_price=comparable, updated_at=offer.updated_at, url=url,
    )


async def load_material_ui_catalog(db) -> list[Material]:
    """Load the full canonical set; callers apply filters before pagination."""
    result = await db.scalars(
        select(Material)
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .options(
            selectinload(Material.category), selectinload(Material.subcategory),
            selectinload(Material.base_unit), selectinload(Material.attributes).selectinload(MaterialAttribute.unit),
            selectinload(Material.analog_links).selectinload(MaterialAnalog.analog_material),
            selectinload(Material.specifications).selectinload(MaterialSpecification.template),
            selectinload(Material.supplier_prices).selectinload(SupplierPrice.supplier),
            selectinload(Material.supplier_prices).selectinload(SupplierPrice.catalog_product),
            selectinload(Material.catalog_products).selectinload(CatalogProduct.source),
        )
        .order_by(Material.canonical_name, Material.id)
    )
    return list(result.all())


def _verified_conversion_profile(material: Material) -> dict[str, str]:
    expected_units = {"kg_per_meter": {"кг/м", "kg/m"},
                      "length_mm": {"мм", "mm"}, "width_mm": {"мм", "mm"},
                      "height_mm": {"мм", "mm"}, "thickness_mm": {"мм", "mm"}}
    profile = {}
    conflicts = set()
    for spec in material.specifications:
        if spec.verified_status != VerificationStatus.VERIFIED or spec.template is None:
            continue
        key = spec.template.field_key
        if key in expected_units and (spec.unit or "").strip().casefold() in expected_units[key]:
            if key in profile and profile[key] != spec.value:
                conflicts.add(key)
            else:
                profile[key] = spec.value
    for key in conflicts:
        profile.pop(key, None)
    return profile


def material_ui_rows(materials: list[Material], *, today: date | None = None,
                     conversion_rules: dict | None = None) -> list[dict[str, Any]]:
    """Keep original material/offer IDs and derive display-only price projections."""
    today = today or date.today()
    rows = []
    for material in materials:
        normalized = normalize_raw_ingestion_item(Module1RawIngestionItem(
            legacy_source="raw_payload", raw_title=material.canonical_name,
            raw_unit=material.base_unit.abbreviation if material.base_unit else None,
        ))
        profile = _verified_conversion_profile(material)
        offers = [view for offer in material.supplier_prices
                  if (view := supplier_offer_view(offer, material, today=today,
                                                   material_group=normalized.suggested_group_code,
                                                   material_profile=profile,
                                                   conversion_rules=(conversion_rules or {}).get(material.id))) is not None]
        displayed_offer_ids = {offer.id for offer in offers}
        linked_products = {offer.catalog_product_id for offer in material.supplier_prices
                           if offer.catalog_product_id and str(offer.id) in displayed_offer_ids}
        for product in material.catalog_products:
            if (product.id in linked_products or product.status != CatalogProductStatus.ACTIVE
                    or product.source is None or product.source.status != SourceStatus.ACTIVE):
                continue
            url = _safe_external_url(product.external_url)
            offers.append(SupplierOfferView(
                id=str(product.id), supplier_id=None, supplier="Поставщик не привязан",
                name=product.raw_name, region=product.region, price=product.price, currency=product.currency,
                unit=product.unit, comparable_price=None, updated_at=product.updated_at,
                url=url, source_name=product.source.name,
            ))
        rows.append({"material": material, "offers": offers})
    return rows


def filter_material_ui_rows(
    rows: list[dict[str, Any]], *, search: str = "", category: str = "", subcategory: str = "",
    supplier: str = "", region: str = "", minimum: Decimal | None = None,
    maximum: Decimal | None = None, preset: str = "all",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Filter the whole server-side set, then return counts before price preset."""
    if preset not in {"all", "with_price", "without_price"}:
        raise ValueError("Unknown materials price filter")
    term = search.strip().casefold()
    region = region.strip().casefold()
    matching = []
    for row in rows:
        material, offers = row["material"], row["offers"]
        if category and str(material.category_id or "") != category:
            continue
        if subcategory and str(material.subcategory_id or "") != subcategory:
            continue
        if term:
            fields = [material.canonical_name, material.category.name if material.category else "",
                      material.subcategory.name if material.subcategory else ""]
            fields.extend(f"{item.attribute_name} {item.attribute_value or ''}" for item in material.attributes
                          if not item.attribute_name.startswith("registry_"))
            fields.extend(f"{item.template.name if item.template else ''} {item.value or ''}" for item in material.specifications)
            fields.extend(item.name for item in offers)
            fields.extend(item.raw_name for item in material.catalog_products)
            haystack = " ".join(fields).casefold()
            if not all(token in haystack for token in term.split()):
                continue
        visible_offers = [offer for offer in offers
                          if (not supplier or offer.supplier_id == supplier)
                          and (not region or region in (offer.region or "").casefold())]
        prices = [offer.comparable_price for offer in visible_offers if offer.comparable_price is not None]
        if supplier and not visible_offers:
            continue
        prices = [price for price in prices if (minimum is None or price >= minimum)
                  and (maximum is None or price <= maximum)]
        if (minimum is not None or maximum is not None) and not prices:
            continue
        matching.append({**row, "visible_offers": visible_offers,
                         "price": min(prices) if prices else None, "offer_count": len(prices)})
    counts = {"all": len(matching), "with_price": sum(row["price"] is not None for row in matching)}
    counts["without_price"] = counts["all"] - counts["with_price"]
    return ([row for row in matching if preset == "all" or (row["price"] is not None) == (preset == "with_price")], counts)
