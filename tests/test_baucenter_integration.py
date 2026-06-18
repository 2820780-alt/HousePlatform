from app.source_integrations.baucenter import _article_from_url, _extract_product


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
