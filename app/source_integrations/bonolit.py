from __future__ import annotations

import hashlib
import asyncio
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

from app.models.enums import DocumentType, SourceActionType
from app.models.source import Source
from app.source_integrations.base import HealthCheckResult, SourceDocument, SourceIntegration, SourceProduct


PRODUCT_SITEMAP_URL = "https://bonolit.ru/sitemap-iblock-2.xml"
DOCUMENT_PAGES = {
    SourceActionType.UPDATE_CERTIFICATES: [
        ("https://bonolit.ru/tekhnicheskaya-podderzhka/sertifications/", DocumentType.CERTIFICATE.value),
    ],
    SourceActionType.UPDATE_TECH_DOCUMENTS: [
        ("https://bonolit.ru/tekhnicheskaya-podderzhka/dokumentatsiya/", DocumentType.TECH_CARD.value),
        ("https://bonolit.ru/klientam/bim/", DocumentType.BIM_MODEL.value),
        ("https://bonolit.ru/klientam/node/", DocumentType.TYPICAL_NODE.value),
    ],
}
MAX_PRODUCT_PAGES = 25
MAX_PRODUCT_ATTEMPTS = 60
MAX_DOCUMENT_LINKS_PER_PAGE = 50


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self._in_h1 = False
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "a":
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get("href")
            self._current_link_text = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "a" and self._current_href:
            text = _clean_text(" ".join(self._current_link_text))
            self.links.append((text, self._current_href))
            self._current_href = None
            self._current_link_text = []

    def handle_data(self, data):
        text = _clean_text(data)
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        if self._in_h1:
            self.h1_parts.append(text)
        if self._current_href:
            self._current_link_text.append(text)

    @property
    def title(self) -> str | None:
        return _clean_text(" ".join(self.title_parts)) or None

    @property
    def h1(self) -> str | None:
        return _clean_text(" ".join(self.h1_parts)) or None


class BonolitIntegration(SourceIntegration):
    supported_actions = {
        SourceActionType.CHECK_SOURCE_HEALTH,
        SourceActionType.INITIAL_MATERIAL_SCAN,
        SourceActionType.FIND_NEW_PRODUCTS,
        SourceActionType.UPDATE_SPECIFICATIONS,
        SourceActionType.UPDATE_CERTIFICATES,
        SourceActionType.UPDATE_TECH_DOCUMENTS,
    }

    def __init__(self, source: Source):
        self.source = source
        self.base_url = source.url or "https://bonolit.ru/"

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
        if action_type not in {
            SourceActionType.INITIAL_MATERIAL_SCAN,
            SourceActionType.FIND_NEW_PRODUCTS,
            SourceActionType.UPDATE_SPECIFICATIONS,
        }:
            return []

        import httpx

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            product_urls = await _fetch_product_urls(client)
            products: list[SourceProduct] = []
            for product_url in product_urls[:MAX_PRODUCT_ATTEMPTS]:
                if len(products) >= MAX_PRODUCT_PAGES:
                    break
                await asyncio.sleep(0.2)
                response = await client.get(product_url, headers=_headers())
                if response.status_code != 200:
                    continue
                parser = _parse_page(response.text)
                name = parser.h1 or _name_from_title(parser.title)
                if not name:
                    continue
                products.append(SourceProduct(
                    external_id=_external_id(product_url),
                    external_url=product_url,
                    raw_name=name,
                    normalized_name=_normalize_name(name),
                    raw_category=_category_from_url(product_url),
                    raw_brand="Bonolit",
                    raw_manufacturer="Bonolit",
                    price=None,
                    currency="RUB",
                    unit=None,
                    availability=None,
                    region=None,
                ))
        return products

    async def fetch_documents(self, action_type: SourceActionType) -> list[SourceDocument]:
        pages = DOCUMENT_PAGES.get(action_type)
        if not pages:
            return []

        import httpx

        documents: list[SourceDocument] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for page_url, document_type in pages:
                response = await client.get(page_url, headers=_headers())
                response.raise_for_status()
                parser = _parse_page(response.text)
                for title, href in parser.links:
                    absolute_url = urljoin(page_url, href)
                    if not _is_document_url(absolute_url) or absolute_url in seen:
                        continue
                    seen.add(absolute_url)
                    documents.append(SourceDocument(
                        title=title or _filename_from_url(absolute_url),
                        document_type=document_type,
                        file_url=absolute_url,
                        source_url=page_url,
                    ))
                    if len(documents) >= MAX_DOCUMENT_LINKS_PER_PAGE * len(pages):
                        return documents
        return documents


async def _fetch_product_urls(client) -> list[str]:
    response = await client.get(PRODUCT_SITEMAP_URL, headers=_headers())
    response.raise_for_status()
    root = ET.fromstring(response.content)
    urls: list[str] = []
    for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
        if loc.text and "/products/" in loc.text:
            urls.append(loc.text.strip())
    return urls


def _parse_page(html: str) -> _PageParser:
    parser = _PageParser()
    parser.feed(html)
    return parser


def _external_id(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = path.rsplit("/", 1)[-1] or path
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{slug}:{digest}"


def _category_from_url(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if len(parts) < 3 or parts[0] != "products":
        return None
    return parts[1].replace("-", " ")


def _name_from_title(title: str | None) -> str | None:
    if not title:
        return None
    return _clean_text(re.split(r"\s[|/-]\s| \| ", title, maxsplit=1)[0])


def _is_document_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith((".pdf", ".dwg", ".rvt", ".ifc", ".zip", ".rar"))


def _filename_from_url(url: str) -> str:
    filename = urlparse(url).path.rsplit("/", 1)[-1]
    return filename or url


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
