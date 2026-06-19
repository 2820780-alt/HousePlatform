from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.source_integrations.base import SourceProduct


class SimpleProductPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1_parts: list[str] = []
        self.title_parts: list[str] = []
        self.links: list[str] = []
        self._in_h1 = False
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag = tag.lower()
        if tag == "h1":
            self._in_h1 = True
        elif tag == "title":
            self._in_title = True
        elif tag == "a" and attrs_dict.get("href"):
            self.links.append(attrs_dict["href"])

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "h1":
            self._in_h1 = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_h1:
            self.h1_parts.append(data)
        if self._in_title:
            self.title_parts.append(data)

    @property
    def h1(self) -> str | None:
        return clean_text(" ".join(self.h1_parts)) or None

    @property
    def title(self) -> str | None:
        return clean_text(" ".join(self.title_parts)) or None


def clean_text(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def normalize_name(value: str | None) -> str | None:
    cleaned = clean_text(value)
    return cleaned.lower() if cleaned else None


def absolute_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def same_host_or_child(url: str, expected_host: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == expected_host or host.endswith(f".{expected_host}")


def category_from_url(url: str, marker: str) -> str | None:
    path = urlparse(url).path.strip("/")
    if not path:
        return None
    parts = [part for part in path.split("/") if part]
    if marker in parts:
        index = parts.index(marker)
        if index + 1 < len(parts):
            return parts[index + 1].replace("-", " ")
    return None


def extract_decimal_price(text: str) -> Decimal | None:
    patterns = [
        r'"price"\s*:\s*"?([0-9]+(?:[.,][0-9]+)?)"?',
        r"([0-9][0-9\s]{2,}(?:[.,][0-9]+)?)\s*(?:₽|руб|RUB)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1).replace(" ", "").replace(",", ".")
        try:
            return Decimal(raw)
        except InvalidOperation:
            continue
    return None


def product_from_html(
    html: str,
    url: str,
    *,
    brand: str | None = None,
    manufacturer: str | None = None,
    category_marker: str = "catalogue",
) -> SourceProduct | None:
    parser = SimpleProductPageParser()
    parser.feed(html)
    name = parser.h1 or parser.title
    if not name:
        return None
    price = extract_decimal_price(html)
    return SourceProduct(
        external_id=url,
        external_url=url,
        raw_name=name,
        normalized_name=normalize_name(name),
        raw_category=category_from_url(url, category_marker),
        raw_brand=brand,
        raw_manufacturer=manufacturer,
        price=price,
        currency="RUB",
        unit=None,
        availability=None,
        region=None,
    )
