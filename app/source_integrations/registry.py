from app.models.source import Source
from app.source_integrations.base import SourceIntegration
from app.source_integrations.baucenter import BaucenterIntegration
from app.source_integrations.bonolit import BonolitIntegration
from app.source_integrations.grandline import GrandLineIntegration
from app.source_integrations.lemanapro import LemanaProIntegration
from app.source_integrations.sitemap_catalog import SitemapCatalogConfig, SitemapCatalogIntegration
from app.source_integrations.technonikol import TechnonikolIntegration
from app.source_integrations.vseinstrumenti import VseInstrumentiIntegration


SOURCE_CONFIGS = {
    "yugkabel": SitemapCatalogConfig(
        brand=None,
        manufacturer=None,
        sitemap_urls=("https://yugkabel.ru/products.xml",),
        category_marker="products",
        default_url="https://yugkabel.ru/",
        product_url_markers=("/products/",),
    ),
    "tegola": SitemapCatalogConfig(
        brand="Tegola",
        manufacturer="Tegola",
        sitemap_urls=("https://www.tegola.ru/sitemap_iblock_23.xml", "https://www.tegola.ru/sitemap_iblock_26.xml"),
        category_marker="catalog",
        default_url="https://www.tegola.ru/",
        blocked_message="Tegola nested sitemaps currently return 404; direct product scan is not available.",
    ),
    "vkblock": SitemapCatalogConfig(
        brand="ВКБлок",
        manufacturer="ВКБлок",
        sitemap_urls=("https://vkblock.ru/catalog-sitemap.xml",),
        category_marker="catalog",
        default_url="https://vkblock.ru/",
        product_url_markers=("/catalog/",),
    ),
    "knauf": SitemapCatalogConfig(
        brand="Knauf",
        manufacturer="Knauf",
        sitemap_urls=("https://www.knauf.ru/sitemap-iblock-27.xml",),
        category_marker="catalog",
        default_url="https://www.knauf.ru/",
        product_url_markers=("/catalog/",),
    ),
    "etm": SitemapCatalogConfig(
        brand=None,
        manufacturer=None,
        sitemap_urls=("https://www.etm.ru/sitemap.xml",),
        category_marker="catalog",
        default_url="https://www.etm.ru/",
        blocked_message="ETM returns 444 for direct scan from this environment.",
    ),
    "saturn-yug": SitemapCatalogConfig(
        brand=None,
        manufacturer=None,
        sitemap_urls=("https://saturn-yug.ru/sitemap.xml",),
        category_marker="catalog",
        default_url="https://saturn-yug.ru/",
        blocked_message="Saturn-Yug connection is closed by the remote server from this environment.",
    ),
}


def get_integration(source: Source) -> SourceIntegration | None:
    name = (source.name or "").lower()
    url = (source.url or "").lower()
    source_key = f"{name} {url}"

    if "baucenter" in source_key:
        return BaucenterIntegration(source)
    if "lemana" in source_key or "lemanapro" in source_key:
        return LemanaProIntegration(source)
    if "bonolit" in source_key:
        return BonolitIntegration(source)
    if "vseinstrumenti" in source_key:
        return VseInstrumentiIntegration(source)
    if "technonikol" in source_key or "tn.ru" in source_key:
        return TechnonikolIntegration(source)
    if "grandline" in source_key or "grand line" in source_key:
        return GrandLineIntegration(source)
    for marker, config in SOURCE_CONFIGS.items():
        if marker in source_key:
            return SitemapCatalogIntegration(source, config)
    return None
