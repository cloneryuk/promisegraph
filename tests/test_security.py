import asyncio
import base64
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security import DemoLimits, DemoSecurityMiddleware, SecuritySettings
from app import security


PASSWORD = "test-only-password-with-32-characters"
SETTINGS = SecuritySettings(required=True, username="judge", password=PASSWORD)
AUTH = ("judge", PASSWORD)


def protected_app(settings=SETTINGS):
    app = FastAPI()
    app.state.calls = 0

    @app.get("/")
    @app.get("/api/export")
    @app.get("/api/health")
    @app.get("/static/app.js")
    def read():
        app.state.calls += 1
        return {"private": True}

    @app.post("/documents")
    @app.post("/assess")
    @app.post("/api/demo")
    @app.post("/facts/example/review")
    def write(payload: dict):
        app.state.calls += 1
        return payload

    app.add_middleware(DemoSecurityMiddleware, settings=settings)
    return app


@pytest.mark.parametrize("path", ["/", "/api/export", "/api/health", "/docs", "/redoc", "/openapi.json", "/static/app.js", "/unknown"])
def test_every_private_route_requires_login(path):
    app = protected_app()
    client = TestClient(app)
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic ")
    assert app.state.calls == 0


@pytest.mark.parametrize("header", ["Bearer secret", "Basic !!!", "Basic " + base64.b64encode(b"no-colon").decode(), "Basic " + base64.b64encode(b"judge:wrong").decode()])
def test_invalid_credentials_never_reach_handler(header):
    app = protected_app()
    assert TestClient(app).post("/documents", json={}, headers={"Authorization": header}).status_code == 401
    assert app.state.calls == 0


def test_login_covers_reads_writes_and_private_caching():
    client = TestClient(protected_app())
    for path in ["/", "/api/export", "/openapi.json", "/static/app.js"]:
        response = client.get(path, auth=AUTH)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
    assert client.post("/documents", json={"text": "note"}, auth=AUTH).json() == {"text": "note"}


def test_liveness_exposes_no_configuration_and_does_not_bypass_other_routes():
    client = TestClient(protected_app())
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.head("/healthz").status_code == 200
    assert client.post("/healthz", json={}).status_code == 401
    assert client.get("/healthz/").status_code == 401


def test_login_throttle_does_not_lock_out_valid_login():
    client = TestClient(protected_app())
    for _ in range(30):
        assert client.get("/").status_code == 401
    response = client.get("/")
    assert response.status_code == 429 and int(response.headers["retry-after"]) > 0
    assert client.get("/", auth=AUTH).status_code == 200


def test_ai_limit_is_shared_across_endpoints_modes_and_forwarded_ips():
    app = protected_app(replace(SETTINGS, ai_per_minute=2))
    client = TestClient(app)
    assert client.post("/documents", json={}, auth=AUTH).status_code == 200
    assert client.post("/assess", json={"mode": "rehearsal"}, auth=AUTH).status_code == 200
    response = client.post("/api/demo", json={}, auth=AUTH, headers={"X-Forwarded-For": "1.2.3.4"})
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    assert app.state.calls == 2
    assert client.get("/", auth=AUTH).status_code == 200
    assert client.post("/facts/example/review", json={}, auth=AUTH).status_code == 200


def test_write_limit_applies_to_reviews():
    client = TestClient(protected_app(replace(SETTINGS, writes_per_minute=1)))
    assert client.post("/facts/example/review", json={}, auth=AUTH).status_code == 200
    assert client.post("/facts/example/review", json={}, auth=AUTH).status_code == 429


def test_sliding_windows_expire_and_hour_limit_survives_minute_reset():
    now = [0.0]
    limiter = DemoLimits(SETTINGS, clock=lambda: now[0])
    buckets = [("ai_minute", 1, 60), ("ai_hour", 2, 3600)]
    assert limiter.reserve(buckets) == 0
    assert limiter.reserve(buckets) == 60
    now[0] = 60
    assert limiter.reserve(buckets) == 0
    now[0] = 120
    assert limiter.reserve(buckets) == 3480
    now[0] = 3600
    assert limiter.reserve(buckets) == 0


def test_cross_origin_and_form_posts_blocked_even_with_correct_password():
    app = protected_app()
    client = TestClient(app)
    assert client.post("/documents", json={}, auth=AUTH, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/documents", content='{}', auth=AUTH, headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.post("/documents", json={}, auth=AUTH, headers={"Origin": "http://testserver"}).status_code == 200
    assert app.state.calls == 1


def test_chunked_oversized_body_rejected_before_handler():
    app = protected_app(replace(SETTINGS, body_bytes=32))
    response = TestClient(app).post("/documents", content=iter([b"x" * 20, b"x" * 20]), headers={"Content-Type": "application/json"}, auth=AUTH)
    assert response.status_code == 413
    assert app.state.calls == 0


def test_concurrent_limit_and_exception_release():
    async def scenario():
        app = protected_app(replace(SETTINGS, ai_concurrency=1))
        started, finish = asyncio.Event(), asyncio.Event()

        @app.post("/documents/slow")
        async def unused():
            return {}

        # Substitute the assessed route with a controllable upstream operation.
        for route in app.router.routes:
            if getattr(route, "path", None) == "/assess":
                app.router.routes.remove(route)
                break

        @app.post("/assess")
        async def wait_then_fail():
            started.set()
            await finish.wait()
            raise RuntimeError("upstream failure")

        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test", auth=AUTH) as client:
            first = asyncio.create_task(client.post("/assess", json={}))
            await asyncio.wait_for(started.wait(), timeout=2)
            assert (await client.post("/documents", json={})).status_code == 429
            finish.set()
            assert (await first).status_code == 500
            assert (await client.post("/documents", json={})).status_code == 200

    asyncio.run(scenario())


@pytest.fixture
def clean_config(monkeypatch):
    monkeypatch.setattr(security, "dotenv_values", lambda _: {})
    for key in ["RENDER", "APP_ENV", "AUTH_REQUIRED", "DEMO_USERNAME", "DEMO_PASSWORD", "PUBLIC_DEMO_UNTIL", "AI_REQUESTS_PER_MINUTE", "AI_REQUESTS_PER_HOUR", "WRITE_REQUESTS_PER_MINUTE", "AI_MAX_CONCURRENT"]:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.mark.parametrize("key,value", [("RENDER", "true"), ("APP_ENV", "production"), ("AUTH_REQUIRED", "true")])
def test_hosted_mode_fails_closed_without_credentials(clean_config, key, value):
    clean_config.setenv(key, value)
    clean_config.setenv("AUTH_REQUIRED", "true" if key == "AUTH_REQUIRED" else "false")
    with pytest.raises(ValueError, match="Protected hosting requires"):
        SecuritySettings.load()


def test_local_default_and_valid_hosted_configuration(clean_config):
    assert SecuritySettings.load().required is False
    clean_config.setenv("RENDER", "true")
    clean_config.setenv("DEMO_USERNAME", "judge")
    clean_config.setenv("DEMO_PASSWORD", PASSWORD)
    assert SecuritySettings.load().required is True
    clean_config.setenv("AI_REQUESTS_PER_HOUR", "0")
    with pytest.raises(ValueError, match="positive integer"):
        SecuritySettings.load()


def test_typo_and_partial_credentials_fail_closed(clean_config):
    clean_config.setenv("AUTH_REQUIRED", "tru")
    with pytest.raises(ValueError):
        SecuritySettings.load()
    clean_config.setenv("AUTH_REQUIRED", "false")
    clean_config.setenv("DEMO_USERNAME", "judge")
    with pytest.raises(ValueError):
        SecuritySettings.load()


def test_real_app_routes_and_existing_middleware_work_behind_login():
    from app.main import app, get_service
    from app.graph import DatabaseUnavailable

    called = []

    def offline():
        called.append(True)
        raise DatabaseUnavailable("Test database unavailable")

    app.dependency_overrides[get_service] = offline
    try:
        client = TestClient(DemoSecurityMiddleware(app, SETTINGS))
        for path in ["/", "/api/export", "/docs", "/api/health", "/facts"]:
            assert client.get(path).status_code == 401
        for path in ["/documents", "/assess", "/api/demo", "/facts/example/review"]:
            assert client.post(path, json={}).status_code == 401
        assert called == []
        for path in ["/", "/docs", "/static/app.js", "/setup"]:
            assert client.get(path, auth=AUTH).status_code == 200
        response = client.post("/assess", auth=AUTH, json={"mode": "rehearsal"})
        assert response.status_code == 503
        assert response.json()["code"] == "database_unavailable"
        assert called == [True]
    finally:
        app.dependency_overrides.clear()


def test_public_window_expires_without_restart_and_limits_continue(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(security.time, "time", lambda: now[0])
    app = protected_app(replace(SETTINGS, public_until=1100, ai_per_minute=1))
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/api/export").status_code == 200
    assert client.get("/").headers["cache-control"] == "no-store"
    assert client.post("/documents", json={}).status_code == 200
    assert client.post("/assess", json={}).status_code == 429
    now[0] = 1100
    assert client.get("/").status_code == 401
    assert client.get("/api/export").status_code == 401
    assert client.post("/facts/example/review", json={}).status_code == 401
    assert client.get("/", auth=AUTH).status_code == 200
    # The expiry must not reset usage counters.
    assert client.post("/assess", json={}, auth=AUTH).status_code == 429
    # Restarting with the same absolute deadline must not reopen public access.
    assert TestClient(protected_app(replace(SETTINGS, public_until=1100))).get("/").status_code == 401


@pytest.mark.parametrize("deadline", ["tomorrow", "2026-11-07T08:50:19", "2026-99-07T08:50:19Z"])
def test_invalid_public_deadline_stops_startup(clean_config, deadline):
    clean_config.setenv("PUBLIC_DEMO_UNTIL", deadline)
    with pytest.raises(ValueError, match="ISO timestamp"):
        SecuritySettings.load()


def test_public_window_still_requires_credentials_and_uses_absolute_time(clean_config):
    clean_config.setenv("PUBLIC_DEMO_UNTIL", "2026-11-07T14:20:19+05:30")
    with pytest.raises(ValueError, match="Protected hosting requires"):
        SecuritySettings.load()
    clean_config.setenv("DEMO_USERNAME", "judge")
    clean_config.setenv("DEMO_PASSWORD", PASSWORD)
    configured = SecuritySettings.load()
    assert configured.required
    clean_config.setenv("PUBLIC_DEMO_UNTIL", "2026-11-07T08:50:19Z")
    assert configured.public_until == SecuritySettings.load().public_until
