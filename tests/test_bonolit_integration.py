from app.source_integrations.bonolit import (
    _category_from_url,
    _external_id,
    _is_document_url,
    _parse_page,
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
