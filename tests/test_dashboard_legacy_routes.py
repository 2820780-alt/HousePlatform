from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app


def test_default_local_settings_use_host_ports_for_page_views(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_SYNC", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    local_settings = Settings(_env_file=None)

    assert "@localhost:5432/" in local_settings.DATABASE_URL
    assert local_settings.REDIS_URL == "redis://localhost:6379/0"


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


def test_legacy_digital_object_route_redirects_to_canonical_digital_house_route():
    client = TestClient(app)

    response = client.get("/modules/digital-object", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/modules/digital-house"


def test_canonical_digital_house_route_uses_safe_placeholder_until_module_is_active():
    client = TestClient(app)

    response = client.get("/modules/digital-house", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/admin/cabinet/view/modules/7"


def test_constructor_lite_route_uses_safe_placeholder_until_module_is_active():
    client = TestClient(app)

    response = client.get("/modules/constructor-lite", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/admin/cabinet/view"


def test_legacy_construction_groups_route_redirects_to_material_hub_feature():
    client = TestClient(app)

    response = client.get("/modules/construction-groups", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/admin/material-hub/view?feature=construction-applicability"
