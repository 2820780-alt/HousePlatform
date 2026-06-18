from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

from app.models.enums import SourceActionType
from app.models.source import Source
from app.source_integrations.base import HealthCheckResult, SourceIntegration, SourceProduct


SITEMAP_URL = "https://baucenter.ru/sitemap.xml"
MAX_PRODUCT_PAGES = 30
MAX_PRODUCT_ATTEMPTS = 60


class _ProductPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1_parts: list[str] = []
        self.next_data_parts: list[str] = []
        self._in_h1 = False
        self._in_next_data = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag.lower() == "h1":
            self._in_h1 = True
        elif tag.lower() == "script" and attrs_dict.get("id") == "__NEXT_DATA__":
            self._in_next_data = True

    def handle_endtag(self, tag):
        if tag.lower() == "h1":
            self._in_h1 = False
        elif tag.lower() == "script" and self._in_next_data:
            self._in_next_data = False

    def handle_data(self, data):
        if self._in_h1:
            self.h1_parts.append(data)
        if self._in_next_data:
            self.next_data_parts.append(data)

    @property
    def h1(self) -> str | None:
        return _clean_text(" ".join(self.h1_parts)) or None

    @property
    def next_data(self) -> dict | None:
        if not self.next_data_parts:
            return None
        try:
            return json.loads("".join(self.next_data_parts))
        except json.JSONDecodeError:
            return None


class BaucenterIntegration(SourceIntegration):
    supported_actions = {
        SourceActionType.CHECK_SOURCE_HEALTH,
        SourceActionType.INITIAL_MATERIAL_SCAN,
        SourceActionType.UPDATE_PRICES,
        SourceActionType.FIND_NEW_PRODUCTS,
    }

    def __init__(self, source: Source):
        self.source = source
        self.base_url = source.url or "https://baucenter.ru/"

    async def check_health(self) -> HealthCheckResult:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(self.base_url, headers=_headers())
            return HealthCheckResult(
                ok=200 <= response.status_code < 400,
                status_code=response.status_code,
                message=response.reason_phrase,
            )
        except Exception as exc:
            return HealthCheckResult(ok=False, message=str(exc))

    async def fetch_products(self, action_type: SourceActionType) -> list[SourceProduct]:
        if action_type not in self.supported_actions:
            return []

        import httpx

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            product_urls = await _fetch_product_urls(client)
            products: list[SourceProduct] = []
            for product_url in product_urls[:MAX_PRODUCT_ATTEMPTS]:
                if len(products) >= MAX_PRODUCT_PAGES:
                    break
                response = await client.get(product_url, headers=_headers())
                if response.status_code != 200:
                    continue
                product = _extract_product(response.text, product_url)
                if product:
                    products.append(product)
            return products


async def _fetch_product_urls(client) -> list[str]:
    response = await client.get(SITEMAP_URL, headers=_headers())
    response.raise_for_status()
    root = ET.fromstring(response.content)
    sitemap_urls = [
        loc.text.strip()
        for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        if loc.text and "sitemap_iblock_2" in loc.text
    ]

    product_urls: list[str] = []
    for sitemap_url in sitemap_urls[:2]:
        response = await client.get(sitemap_url, headers=_headers())
        response.raise_for_status()
        sitemap_root = ET.fromstring(response.content)
        for loc in sitemap_root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            if loc.text and "/product/" in loc.text:
                product_urls.append(loc.text.strip())
    return product_urls


def _extract_product(html: str, url: str) -> SourceProduct | None:
    parser = _ProductPageParser()
    parser.feed(html)
    data = parser.next_data or {}
    raw_product = _find_current_product(data)
    name = parser.h1 or _clean_text(raw_product.get("title") or raw_product.get("name") or "")
    if not name:
        return None

    price, currency, unit = _extract_price(raw_product)
    article = raw_product.get("article") or _article_from_url(url)

    return SourceProduct(
        external_id=str(article) if article else url,
        external_url=url,
        raw_name=name,
        normalized_name=_normalize_name(name),
        raw_category=raw_product.get("categoryName"),
        raw_brand=raw_product.get("brand"),
        raw_manufacturer=None,
        price=price,
        currency=currency,
        unit=unit,
        availability=raw_product.get("availableType"),
        region=None,
    )


def _find_current_product(data: dict) -> dict:
    return (
        data.get("props", {})
        .get("pageProps", {})
        .get("initialState", {})
        .get("product", {})
        .get("currentProductData", {})
        .get("product", {})
    ) or {}


def _extract_price(product: dict) -> tuple[Decimal | None, str, str | None]:
    main_price = ((product.get("price") or {}).get("main") or {})
    raw_price = main_price.get("price")
    if raw_price in (None, "", 0, "0"):
        return None, main_price.get("currency") or "RUB", main_price.get("unit") or None
    try:
        return Decimal(str(raw_price)), main_price.get("currency") or "RUB", main_price.get("unit") or None
    except InvalidOperation:
        return None, main_price.get("currency") or "RUB", main_price.get("unit") or None


def _article_from_url(url: str) -> str | None:
    match = re.search(r"-(\d{6,})/?$", url)
    return match.group(1) if match else None


def _normalize_name(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.lower().replace("\xa0", " ").split())


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "HousePlatformBot/0.1 (+https://github.com/2820780-alt/HousePlatform)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
    }
