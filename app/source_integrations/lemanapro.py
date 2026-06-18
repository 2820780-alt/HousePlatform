from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urljoin

from app.models.enums import SourceActionType
from app.models.source import Source
from app.source_integrations.base import HealthCheckResult, SourceIntegration, SourceProduct


class _TextAndLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_items: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get("href")
            self._current_text = []

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._current_href:
            text = _clean_text(" ".join(self._current_text))
            if text:
                self.links.append((text, self._current_href))
            self._current_href = None
            self._current_text = []

    def handle_data(self, data):
        text = _clean_text(data)
        if text:
            self.text_items.append(text)
            if self._current_href:
                self._current_text.append(text)


class LemanaProIntegration(SourceIntegration):
    supported_actions = {
        SourceActionType.CHECK_SOURCE_HEALTH,
        SourceActionType.INITIAL_MATERIAL_SCAN,
        SourceActionType.UPDATE_PRICES,
        SourceActionType.FIND_NEW_PRODUCTS,
    }

    def __init__(self, source: Source):
        self.source = source
        self.base_url = source.url or "https://lemanapro.ru/"

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
        import httpx

        if action_type not in self.supported_actions:
            return []
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(self.base_url, headers=_headers())
            response.raise_for_status()

        parser = _TextAndLinkParser()
        parser.feed(response.text)
        return _extract_products(parser.text_items, parser.links, self.base_url)


def _extract_products(
    text_items: list[str],
    links: list[tuple[str, str]],
    base_url: str,
) -> list[SourceProduct]:
    products: list[SourceProduct] = []
    seen: set[str] = set()

    link_by_text = {name.lower(): href for name, href in links if href}
    article_re = re.compile(r"арт\.?\s*(\d+)", re.IGNORECASE)

    for index, item in enumerate(text_items):
        match = article_re.search(item)
        if not match:
            continue

        external_id = match.group(1)
        if external_id in seen:
            continue

        window = text_items[index + 1:index + 18]
        name = _find_name(window)
        if not name:
            continue

        price, unit = _find_price(window)
        external_url = _find_url(name, links, link_by_text, base_url)

        products.append(SourceProduct(
            external_id=external_id,
            external_url=external_url,
            raw_name=name,
            normalized_name=_normalize_name(name),
            raw_brand=_guess_brand(name),
            raw_manufacturer=None,
            price=price,
            currency="RUB",
            unit=unit,
            availability=_find_availability(window),
            region=None,
        ))
        seen.add(external_id)

    return products


def _find_name(window: list[str]) -> str | None:
    skip_fragments = [
        "₽", "руб", "отзыв", "в корзину", "сравнить", "избранное", "доставка",
        "самовывоз", "скидка", "рейтинг", "арт.",
    ]
    for item in window:
        lower = item.lower()
        if any(fragment in lower for fragment in skip_fragments):
            continue
        if len(item) < 8:
            continue
        if re.fullmatch(r"[\d\s,.\-]+", item):
            continue
        return item
    return None


def _find_price(window: list[str]) -> tuple[Decimal | None, str | None]:
    price_re = re.compile(r"([\d\s]+(?:[,.]\d+)?)\s*₽(?:\s*/\s*([^\s]+))?")
    for item in window:
        match = price_re.search(item)
        if not match:
            continue
        raw = match.group(1).replace(" ", "").replace(",", ".")
        try:
            return Decimal(raw), match.group(2)
        except InvalidOperation:
            return None, match.group(2)
    return None, None


def _find_url(
    name: str,
    links: list[tuple[str, str]],
    link_by_text: dict[str, str],
    base_url: str,
) -> str | None:
    href = link_by_text.get(name.lower())
    if href:
        return urljoin(base_url, href)

    normalized = _normalize_name(name)
    for link_text, link_href in links:
        if _normalize_name(link_text) == normalized:
            return urljoin(base_url, link_href)
    return None


def _find_availability(window: list[str]) -> str | None:
    joined = " ".join(window).lower()
    if "нет в наличии" in joined:
        return "unavailable"
    if "в наличии" in joined or "в корзину" in joined:
        return "available"
    return None


def _guess_brand(name: str) -> str | None:
    tokens = [token.strip(",.;:()") for token in name.split()]
    for token in tokens:
        if len(token) >= 3 and (token.isupper() or any(ch.isdigit() for ch in token)):
            return token
    return None


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
