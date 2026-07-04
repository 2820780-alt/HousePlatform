from fastapi.testclient import TestClient

from app.main import app


def test_partner_portal_settings_ui_is_cabinet_settings_not_second_dashboard():
    client = TestClient(app)
    response = client.get("/api/v1/partner-portal/settings")

    assert response.status_code == 200
    html = response.text
    assert "Кабинеты участников" in html
    assert "Профиль кабинета" in html
    assert "Создание / переключение кабинета" in html
    assert "Сотрудники" in html
    assert "Контакты" in html
    assert "Филиалы" in html
    assert "Регионы" in html
    assert "Документы" in html
    assert "Связанные объекты" in html
    assert "Настройки видимости" in html
    assert "Настройки предложений" in html
    assert "Настройки рабочего экрана" in html
    assert "PARTICIPANT_CABINET_CONTEXT" in html
    assert "legacy source: MODULE_08_PARTNER_PORTAL" in html
    assert "без Dashboard-дубля" in html
    assert "atom-map" not in html
    assert "dashboard-grid" not in html
