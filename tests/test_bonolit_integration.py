from app.source_integrations.bonolit import (
    _category_from_url,
    _external_id,
    _filter_product_urls,
    _is_document_url,
    _parse_page,
    _resolve_document_limit,
    _resolve_product_limits,
    _should_keep_document,
)


def test_parse_page_extracts_h1_and_pdf_links():
    parser = _parse_page("""
        <html>
          <head><title>Fallback title | Bonolit</title></head>
          <body>
            <h1>Stenovoy blok Bonolit D500</h1>
            <a href="/upload/spec.pdf">Technical card</a>
          </body>
        </html>
    """)

    assert parser.h1 == "Stenovoy blok Bonolit D500"
    assert parser.title == "Fallback title | Bonolit"
    assert parser.links == [("Technical card", "/upload/spec.pdf")]
    assert _is_document_url("https://bonolit.ru/upload/spec.pdf")


def test_product_url_helpers_are_stable():
    url = "https://bonolit.ru/products/stenovye-bloki/d500/stenovoy-blok-d500-300mm-/"

    assert _category_from_url(url) == "stenovye bloki"
    assert _external_id(url).startswith("stenovoy-blok-d500-300mm-:")


def test_scan_parameters_support_category_and_full_modes():
    urls = [
        "https://bonolit.ru/products/stenovye-bloki/d500/block/",
        "https://bonolit.ru/products/p-obraznye-bloki/d500/u-block/",
    ]

    filtered = _filter_product_urls(urls, {"category_url_contains": "stenovye-bloki"})

    assert filtered == [urls[0]]
    assert _resolve_product_limits({}) == (25, 60)
    assert _resolve_product_limits({"scan_mode": "FULL"}) == (None, None)
    assert _resolve_document_limit({}, 2) == 100
    assert _resolve_document_limit({"scan_mode": "FULL"}, 2) is None


def test_document_filter_rejects_hr_documents_and_keeps_technical_documents():
    assert not _should_keep_document(
        "Сводная ведомость СОУТ 2026",
        "TECH_CARD",
        "https://bonolit.ru/upload/sout.pdf",
    )
    assert _should_keep_document(
        "Альбом технических решений",
        "TECH_CARD",
        "https://bonolit.ru/upload/album.pdf",
    )
    assert _should_keep_document(
        "Сертификат соответствия",
        "CERTIFICATE",
        "https://bonolit.ru/upload/cert.pdf",
    )
