import re
from fastapi.testclient import TestClient
from app.main import app, get_service
from app.graph import DatabaseUnavailable


def test_database_outage_never_returns_empty_success():
    def unavailable():
        raise DatabaseUnavailable("Simulated unavailable database")

    app.dependency_overrides[get_service] = unavailable
    try:
        response = TestClient(app).post("/assess", json={"mode": "rehearsal"})
        assert response.status_code == 503
        assert response.json()["code"] == "database_unavailable"
        assert "assessments" not in response.json()
    finally:
        app.dependency_overrides.clear()


def test_home_and_assets_available_without_database():
    client = TestClient(app)
    for path in ("/", "/static/app.js", "/static/styles.css", "/setup"):
        assert client.get(path).status_code == 200
    home = client.get("/")
    scripts = re.findall(r"/static/(?:app\.js|styles\.css)\?v=[a-f0-9]{12}", home.text)
    assert len(scripts) == 2 and "{{ASSET_VERSION}}" not in home.text
    assert home.headers["cache-control"] == "no-cache"
    for path in scripts:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"


def test_cross_origin_write_rejected():
    r = TestClient(app).post(
        "/api/demo",
        headers={"Origin": "https://unrelated.example"},
        json={"mode": "rehearsal"},
    )
    assert r.status_code == 403
