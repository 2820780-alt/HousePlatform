from app.source_integrations.baucenter import (
    _article_from_url,
    _extract_product,
    _extract_product_from_api,
    _filter_product_urls,
    _resolve_product_limits,
)


def test_extract_product_from_next_data():
    html = """
        <html>
          <body>
            <h1>Коннектор трековый NEODECO черный</h1>
            <script id="__NEXT_DATA__" type="application/json">
            {
              "props": {
                "pageProps": {
                  "initialState": {
                    "product": {
                      "currentProductData": {
                        "product": {
                          "article": "816000046",
                          "brand": "NEODECO",
                          "categoryName": "Однофазные трековые светильники",
                          "availableType": "online",
                          "price": {
                            "main": {
                              "price": 0,
                              "currency": "RUB",
                              "unit": ""
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            </script>
          </body>
        </html>
    """

    product = _extract_product(html, "https://baucenter.ru/product/item-816000046/")

    assert product is not None
    assert product.external_id == "816000046"
    assert product.raw_name == "Коннектор трековый NEODECO черный"
    assert product.raw_brand == "NEODECO"
    assert product.raw_category == "Однофазные трековые светильники"
    assert product.availability == "online"
    assert product.price is None
    assert product.currency == "RUB"


def test_article_from_url():
    assert _article_from_url("https://baucenter.ru/product/example-705006436/") == "705006436"


def test_extract_product_from_api_uses_real_price_and_availability():
    product = _extract_product_from_api({
        "id": 288639,
        "article": "643000283",
        "title": "Плита ОСБ влагостойкая 2440х1220х12 мм",
        "url": "/product/plita-osb-643000283/",
        "categoryName": "Плиты OSB",
        "brand": "Ультраплай",
        "price": {
            "main": {
                "price": 105000,
                "currency": "RUB",
                "unit": "лст",
            }
        },
        "availability": [{
            "availabilityCount": {
                "amount": 1156.88,
                "unit": "лст",
                "text": "Доступно к заказу 1156.88 лст",
            }
        }],
    }, "https://baucenter.ru/product/example-643000283/")

    assert product is not None
    assert product.price == 1050
    assert product.unit == "лст"
    assert product.availability == "Доступно к заказу 1156.88 лст"


def test_scan_parameters_support_category_and_full_modes():
    urls = [
        "https://baucenter.ru/product/osb-ctg-stroymaterialy-643000283/",
        "https://baucenter.ru/product/lamp-ctg-svet-801010557/",
    ]

    filtered = _filter_product_urls(urls, {"category_url_contains": "stroymaterialy"})

    assert filtered == [urls[0]]
    assert _resolve_product_limits({}) == (30, 60)
    assert _resolve_product_limits({"scan_mode": "FULL"}) == (None, None)
    assert _resolve_product_limits({"scan_mode": "FULL", "max_pages": 1000}) == (1000, None)
