from fastapi.testclient import TestClient

from app.main import app


def test_legacy_price_history_route_redirects_to_price_dynamics_view():
    client = TestClient(app)

    response = client.get("/modules/price-history", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/admin/price-dynamics/view"


def test_legacy_analytics_price_dynamics_route_redirects_to_price_dynamics_view():
    client = TestClient(app)

    response = client.get("/modules/analytics?section=price-dynamics", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/admin/price-dynamics/view"


def test_legacy_analytics_route_without_section_redirects_to_analytics_module():
    client = TestClient(app)

    response = client.get("/modules/analytics", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/admin/cabinet/view/modules/11"
