from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from fbchat_v2.service import create_app, readiness_report
from fbchat_v2.service_sessions import SessionRegistry
from fbchat_v2.service_webhook import WebhookConfigStore


def _configure_auth(monkeypatch) -> tuple[str, str]:
    username = "portal-user"
    password = "correct horse battery staple"
    monkeypatch.setenv("FBCHAT_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("FBCHAT_API_USERNAME", username)
    monkeypatch.setenv("FBCHAT_API_PASSWORD", password)
    return username, password


def test_health_endpoint_contains_no_runtime_configuration() -> None:
    response = TestClient(create_app()).get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert set(response.json()) == {"status", "service", "version"}


def test_readiness_allows_regular_only_mode(monkeypatch) -> None:
    _configure_auth(monkeypatch)
    monkeypatch.delenv("FBCHAT_E2EE_BIN", raising=False)
    monkeypatch.delenv("FBCHAT_E2EE_REQUIRED", raising=False)

    response = TestClient(create_app()).get("/readyz")

    assert response.status_code == 200
    assert response.json()["checks"]["e2ee_bridge"]["configured"] is False


def test_readiness_rejects_missing_required_bridge(monkeypatch, tmp_path: Path) -> None:
    _configure_auth(monkeypatch)
    missing = tmp_path / "missing-bridge"
    monkeypatch.setenv("FBCHAT_E2EE_BIN", str(missing))
    monkeypatch.setenv("FBCHAT_E2EE_REQUIRED", "true")

    report = readiness_report()

    assert report["status"] == "not_ready"
    assert report["checks"]["e2ee_bridge"]["executable"] is False


def test_readiness_accepts_executable_bridge(monkeypatch, tmp_path: Path) -> None:
    _configure_auth(monkeypatch)
    bridge = tmp_path / "bridge"
    bridge.write_text("bridge", encoding="utf-8")
    bridge.chmod(0o700)
    monkeypatch.setenv("FBCHAT_E2EE_BIN", str(bridge))
    monkeypatch.setenv("FBCHAT_E2EE_REQUIRED", "true")

    report = readiness_report()

    assert report["status"] == "ready"
    assert report["checks"]["e2ee_bridge"]["executable"] is True


def test_readiness_rejects_missing_required_api_credentials(monkeypatch) -> None:
    monkeypatch.setenv("FBCHAT_API_AUTH_REQUIRED", "true")
    monkeypatch.delenv("FBCHAT_API_USERNAME", raising=False)
    monkeypatch.delenv("FBCHAT_API_PASSWORD", raising=False)
    monkeypatch.delenv("FBCHAT_E2EE_BIN", raising=False)
    monkeypatch.delenv("FBCHAT_E2EE_REQUIRED", raising=False)

    report = readiness_report()

    assert report["status"] == "not_ready"
    assert report["checks"]["api_auth"] == {
        "ready": False,
        "required": True,
        "configured": False,
    }


def test_portal_and_api_require_basic_auth(monkeypatch) -> None:
    credentials = _configure_auth(monkeypatch)
    client = TestClient(create_app())

    unauthorized = client.get("/api/v1/app/info")
    authorized = client.get("/api/v1/app/info", auth=credentials)
    portal = client.get("/", auth=credentials)

    assert unauthorized.status_code == 401
    assert unauthorized.json()["code"] == "UNAUTHORIZED"
    assert authorized.status_code == 200
    assert authorized.json()["results"]["apiVersion"] == "v1"
    assert portal.status_code == 200
    assert "Provider Portal" in portal.text
    assert "Webhook global" in portal.text


def test_session_lifecycle_never_returns_cookie_or_provider_id(monkeypatch) -> None:
    credentials = _configure_auth(monkeypatch)
    secret_cookie = "session-secret-that-must-not-leak"

    async def authenticate(cookie_header: str) -> dict[str, Any] | None:
        assert secret_cookie in cookie_header
        return {
            "FacebookID": "123456789",
            "cookieFacebook": cookie_header,
            "fb_dtsg": "private-token",
        }

    registry = SessionRegistry(authenticate)
    client = TestClient(create_app(registry))
    response = client.post(
        "/api/v1/sessions",
        auth=credentials,
        json={
            "label": "Marketplace test",
            "cookies": [
                {"name": "c_user", "value": "123456789"},
                {"name": "xs", "value": secret_cookie},
            ],
        },
    )

    assert response.status_code == 201
    session = response.json()["results"]
    serialized = response.text
    assert set(session) == {
        "sessionId",
        "label",
        "status",
        "createdAt",
        "validatedAt",
    }
    assert secret_cookie not in serialized
    assert "123456789" not in serialized
    assert "private-token" not in serialized

    listed = client.get("/api/v1/sessions", auth=credentials)
    validated = client.post(
        f"/api/v1/sessions/{session['sessionId']}/validate", auth=credentials
    )
    deleted = client.delete(
        f"/api/v1/sessions/{session['sessionId']}", auth=credentials
    )
    after_delete = client.get("/api/v1/sessions", auth=credentials)

    assert listed.json()["results"][0]["sessionId"] == session["sessionId"]
    assert validated.status_code == 200
    assert deleted.status_code == 200
    assert after_delete.json()["results"] == []


def test_validation_error_redacts_cookie_input(monkeypatch) -> None:
    credentials = _configure_auth(monkeypatch)
    secret_cookie = "raw-secret-cookie"
    response = TestClient(create_app()).post(
        "/api/v1/sessions",
        auth=credentials,
        json={
            "label": "test",
            "cookies": [{"name": "xs", "value": secret_cookie, "unexpected": True}],
        },
    )

    assert response.status_code == 422
    assert secret_cookie not in response.text
    assert '"unexpected":true' not in response.text


def test_global_webhook_api_persists_and_redacts_secret(monkeypatch, tmp_path) -> None:
    credentials = _configure_auth(monkeypatch)
    secret = "webhook-secret-that-must-not-leak"
    store = WebhookConfigStore(tmp_path)
    client = TestClient(create_app(webhook_store=store))

    updated = client.put(
        "/api/v1/webhook",
        auth=credentials,
        json={
            "enabled": True,
            "url": "https://socialmanager.example.com/hooks/facebook",
            "events": ["message.received", "session.status"],
            "secret": secret,
        },
    )
    fetched = client.get("/api/v1/webhook", auth=credentials)

    assert updated.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["results"]["scope"] == "all-sessions"
    assert fetched.json()["results"]["secretConfigured"] is True
    assert secret not in updated.text
    assert secret not in fetched.text

    cleared = client.delete("/api/v1/webhook", auth=credentials)
    assert cleared.status_code == 200
    assert cleared.json()["results"]["enabled"] is False
