from __future__ import annotations

from urllib.parse import urlparse

from app.models.enums import SourceActionType
from app.models.source import Source
from app.source_integrations.base import HealthCheckResult, SourceIntegration, SourceProduct
from app.source_integrations.html_catalog import (
    SimpleProductPageParser,
    absolute_url,
    product_from_html,
    same_host_or_child,
)


CATALOG_URL = "https://www.grandline.ru/katalog/"
MAX_PRODUCT_PAGES = 30
MAX_PRODUCT_ATTEMPTS = 80
FULL_SCAN_MODE = "FULL"
MAX_CATEGORY_PAGES = 50
PRIORITY_URL_MARKERS = [
    "krovel",
    "metallocherep",
    "profil",
    "falcev",
    "fasad",
    "saiding",
    "vodost",
    "zabor",
    "ograzh",
    "snegozader",
    "uteplit",
    "gidroizol",
]


class GrandLineIntegration(SourceIntegration):
    supported_actions = {
        SourceActionType.CHECK_SOURCE_HEALTH,
        SourceActionType.INITIAL_MATERIAL_SCAN,
        SourceActionType.FIND_NEW_PRODUCTS,
        SourceActionType.UPDATE_SPECIFICATIONS,
    }

    def __init__(self, source: Source):
        self.source = source
        self.base_url = source.url or CATALOG_URL

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

    async def fetch_products(
        self,
        action_type: SourceActionType,
        parameters: dict | None = None,
    ) -> list[SourceProduct]:
        import httpx

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            urls = await _fetch_catalogue_urls(client, self.base_url)
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
                    brand="Grand Line",
                    manufacturer="Grand Line",
                    category_marker="katalog",
                )
                if product and _is_product_url(url):
                    products.append(product)
            return products


async def _fetch_catalogue_urls(client, base_url: str) -> list[str]:
    response = await client.get(base_url or CATALOG_URL, headers=_headers())
    response.raise_for_status()
    base_host = urlparse(str(response.url)).netloc.lower()
    category_urls = _extract_catalog_urls(str(response.url), response.text, base_host)
    product_urls = [url for url in category_urls if _is_product_url(url)]
    category_urls = [url for url in category_urls if not _is_product_url(url)]

    for category_url in sorted(category_urls, key=_priority_key)[:MAX_CATEGORY_PAGES]:
        try:
            category_response = await client.get(category_url, headers=_headers())
        except Exception:
            continue
        if category_response.status_code != 200:
            continue
        for product_url in _extract_catalog_urls(str(category_response.url), category_response.text, base_host):
            if _is_product_url(product_url) and product_url not in product_urls:
                product_urls.append(product_url)
    return sorted(product_urls, key=_priority_key)


def _extract_catalog_urls(base_url: str, html: str, base_host: str) -> list[str]:
    parser = SimpleProductPageParser()
    parser.feed(html)
    urls: list[str] = []
    for href in parser.links:
        href = href.strip()
        if href.startswith("katalog/"):
            href = f"/{href}"
        url = absolute_url(base_url, href)
        if "#" in url:
            url = url.split("#", 1)[0]
        parsed = urlparse(url)
        if parsed.netloc.lower() != base_host:
            continue
        if "/katalog/" not in parsed.path:
            continue
        if url.rstrip("/") == "https://www.grandline.ru/katalog":
            continue
        if url not in urls:
            urls.append(url)
    return urls


def _is_product_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".html")


def _priority_key(url: str) -> tuple[int, str]:
    lowered = url.lower()
    if "/instrument/" in lowered:
        return (2, lowered)
    if any(marker in lowered for marker in PRIORITY_URL_MARKERS):
        return (0, lowered)
    return (1, lowered)


def _filter_urls(urls: list[str], parameters: dict | None) -> list[str]:
    filters = (parameters or {}).get("category_url_contains") or (parameters or {}).get("category_filters")
    if not filters:
        return urls
    if isinstance(filters, str):
        filters = [filters]
    values = [str(item).lower() for item in filters if str(item).strip()]
    return [url for url in urls if any(value in url.lower() for value in values)]


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
