from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from app.models.enums import SourceActionType
from app.models.source import Source
from app.source_integrations.base import HealthCheckResult, SourceIntegration, SourceProduct
from app.source_integrations.html_catalog import product_from_html


MAX_PRODUCT_PAGES = 30
MAX_PRODUCT_ATTEMPTS = 80
FULL_SCAN_MODE = "FULL"


@dataclass(frozen=True)
class SitemapCatalogConfig:
    brand: str | None
    manufacturer: str | None
    sitemap_urls: tuple[str, ...]
    category_marker: str
    default_url: str
    product_url_markers: tuple[str, ...] = ()
    blocked_message: str | None = None


class SitemapCatalogIntegration(SourceIntegration):
    supported_actions = {
        SourceActionType.CHECK_SOURCE_HEALTH,
        SourceActionType.INITIAL_MATERIAL_SCAN,
        SourceActionType.FIND_NEW_PRODUCTS,
        SourceActionType.UPDATE_PRICES,
        SourceActionType.UPDATE_SPECIFICATIONS,
    }

    def __init__(self, source: Source, config: SitemapCatalogConfig):
        self.source = source
        self.config = config
        self.base_url = source.url or config.default_url

    async def check_health(self) -> HealthCheckResult:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(self.base_url, headers=_headers())
            ok = 200 <= response.status_code < 400
            return HealthCheckResult(
                ok=ok,
                status_code=response.status_code,
                message=self.config.blocked_message if not ok and self.config.blocked_message else response.reason_phrase,
            )
        except Exception as exc:
            return HealthCheckResult(ok=False, message=str(exc))

    async def fetch_products(
        self,
        action_type: SourceActionType,
        parameters: dict | None = None,
    ) -> list[SourceProduct]:
        import httpx

        if self.config.blocked_message:
            raise RuntimeError(self.config.blocked_message)

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            urls = await _fetch_urls(client, self.config.sitemap_urls, self.config.product_url_markers)
            urls = _filter_urls(urls, parameters)
            max_pages, max_attempts = _resolve_limits(parameters)
            products: list[SourceProduct] = []
            for index, url in enumerate(urls):
                if max_attempts is not None and index >= max_attempts:
                    break
                if max_pages is not None and len(products) >= max_pages:
                    break
                response = await client.get(url, headers=_headers())
                if response.status_code != 200:
                    continue
                product = product_from_html(
                    response.text,
                    url,
                    brand=self.config.brand,
                    manufacturer=self.config.manufacturer,
                    category_marker=self.config.category_marker,
                )
                if product:
                    products.append(product)
            return products


async def _fetch_urls(client, sitemap_urls: tuple[str, ...], markers: tuple[str, ...]) -> list[str]:
    urls: list[str] = []
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    for sitemap_url in sitemap_urls:
        response = await client.get(sitemap_url, headers=_headers())
        if response.status_code != 200:
            continue
        root = ET.fromstring(response.content)
        for loc in root.findall(f".//{ns}loc"):
            if not loc.text:
                continue
            url = loc.text.strip()
            if markers and not any(marker in url.lower() for marker in markers):
                continue
            if url not in urls:
                urls.append(url)
    return urls


def _filter_urls(urls: list[str], parameters: dict | None) -> list[str]:
    filters = (parameters or {}).get("category_url_contains") or (parameters or {}).get("category_filters")
    if not filters:
        return urls
    if isinstance(filters, str):
        filters = [filters]
    values = [str(item).lower() for item in filters if str(item).strip()]
    filtered: list[str] = []
    for url in urls:
        path = urlparse(url).path.lower()
        if any(value in path for value in values):
            filtered.append(url)
    return filtered


def _resolve_limits(parameters: dict | None) -> tuple[int | None, int | None]:
    parameters = parameters or {}
    scan_mode = str(parameters.get("scan_mode") or "TEST").upper()
    if scan_mode == FULL_SCAN_MODE:
        return _positive_int_or_none(parameters.get("max_pages")), _positive_int_or_none(parameters.get("max_attempts"))
    return (
        _positive_int_or_default(parameters.get("max_pages"), MAX_PRODUCT_PAGES),
        _positive_int_or_default(parameters.get("max_attempts"), MAX_PRODUCT_ATTEMPTS),
    )


def _positive_int_or_default(value, default: int) -> int:
    parsed = _positive_int_or_none(value)
    return parsed if parsed is not None else default


def _positive_int_or_none(value) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (compatible; HousePlatformMaterialHub/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
