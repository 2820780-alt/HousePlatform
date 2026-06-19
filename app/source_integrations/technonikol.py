from __future__ import annotations

from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from app.models.enums import SourceActionType
from app.models.source import Source
from app.source_integrations.base import HealthCheckResult, SourceIntegration, SourceProduct
from app.source_integrations.html_catalog import product_from_html


SITEMAP_URL = "https://www.tn.ru/sitemap.xml"
CATALOGUE_SITEMAP_URL = "https://www.tn.ru/sitemap-main.xml"
MAX_PRODUCT_PAGES = 30
MAX_PRODUCT_ATTEMPTS = 80
FULL_SCAN_MODE = "FULL"


class TechnonikolIntegration(SourceIntegration):
    supported_actions = {
        SourceActionType.CHECK_SOURCE_HEALTH,
        SourceActionType.INITIAL_MATERIAL_SCAN,
        SourceActionType.FIND_NEW_PRODUCTS,
        SourceActionType.UPDATE_SPECIFICATIONS,
    }

    def __init__(self, source: Source):
        self.source = source
        self.base_url = source.url or "https://www.tn.ru/"

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
            urls = await _fetch_catalogue_urls(client)
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
                    brand="ТЕХНОНИКОЛЬ",
                    manufacturer="ТЕХНОНИКОЛЬ",
                    category_marker="catalogue",
                )
                if product:
                    products.append(product)
            return products


async def _fetch_catalogue_urls(client) -> list[str]:
    response = await client.get(CATALOGUE_SITEMAP_URL, headers=_headers())
    response.raise_for_status()
    root = ET.fromstring(response.content)
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    urls = [
        loc.text.strip()
        for loc in root.findall(f".//{ns}loc")
        if loc.text and "/catalogue/" in loc.text
    ]
    return [
        url for url in urls
        if url.rstrip("/") != "https://www.tn.ru/catalogue" and _catalogue_depth(url) >= 2
    ]


def _catalogue_depth(url: str) -> int:
    parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if "catalogue" not in parts:
        return 0
    return len(parts) - parts.index("catalogue") - 1


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
