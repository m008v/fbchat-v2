from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from fbchat_v2.service import create_app, readiness_report
from fbchat_v2.service_sessions import SessionRegistry
from fbchat_v2.service_webhook import WebhookConfigStore
from fbchat_v2.service_provider import ProviderOperations


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


def test_threads_and_text_message_endpoints_use_private_session_data(
    monkeypatch,
) -> None:
    credentials = _configure_auth(monkeypatch)

    async def authenticate(cookie_header: str) -> dict[str, Any] | None:
        return {"cookieFacebook": cookie_header, "FacebookID": "private-account-id"}

    class FakeOperations:
        async def list_threads(
            self, provider_data: dict[str, Any]
        ) -> list[dict[str, Any]]:
            assert provider_data["FacebookID"] == "private-account-id"
            return [
                {
                    "threadId": "thread-1",
                    "type": "one_to_one",
                    "name": "Test",
                    "unreadCount": 0,
                    "updatedAt": None,
                    "archived": False,
                    "marketplace": False,
                }
            ]

        async def send_text(
            self, provider_data: dict[str, Any], **kwargs
        ) -> dict[str, Any]:
            assert provider_data["cookieFacebook"]
            assert kwargs == {
                "thread_id": "thread-1",
                "text": "Hello",
                "thread_type": "user",
                "reply_to_message_id": None,
            }
            return {
                "messageId": "message-1",
                "threadId": "thread-1",
                "status": "sent",
                "timestamp": "1",
            }

    registry = SessionRegistry(authenticate)
    client = TestClient(create_app(registry, provider_operations=FakeOperations()))
    connected = client.post(
        "/api/v1/sessions",
        auth=credentials,
        json={
            "label": "REST account",
            "cookies": [
                {"name": "c_user", "value": "1"},
                {"name": "xs", "value": "secret"},
            ],
        },
    )
    session_id = connected.json()["results"]["sessionId"]

    threads = client.get(f"/api/v1/sessions/{session_id}/threads", auth=credentials)
    message = client.post(
        f"/api/v1/sessions/{session_id}/messages/text",
        auth=credentials,
        json={"threadId": "thread-1", "text": "Hello", "threadType": "user"},
    )

    assert threads.status_code == 200
    assert threads.json()["results"]["count"] == 1
    assert message.status_code == 200
    assert message.json()["results"]["status"] == "sent"
    assert "private-account-id" not in threads.text + message.text
    assert "secret" not in threads.text + message.text


def test_extended_service_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    credentials = ("provider", "secret")
    monkeypatch.setenv("FBCHAT_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("FBCHAT_API_USERNAME", credentials[0])
    monkeypatch.setenv("FBCHAT_API_PASSWORD", credentials[1])

    async def authenticate(_: str) -> dict[str, Any] | None:
        return {"FacebookID": "test-fb-id", "cookieFacebook": "c_user=1; xs=secret"}

    class FullMockOperations(ProviderOperations):
        async def react_message(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "messageId": kwargs.get("message_id"),
                "emoji": kwargs.get("emoji"),
                "status": "confirmed",
            }

        async def unsend_message(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"messageId": kwargs.get("message_id"), "status": "revoked"}

        async def get_user_info(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "userId": kwargs.get("user_id"),
                "name": "Jane Doe",
                "username": "janedoe",
            }

        async def search_users(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            return [
                {
                    "userId": "user-2",
                    "name": "Target",
                    "url": "https://facebook.com/target",
                }
            ]

        async def block_user(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "userId": kwargs.get("user_id"),
                "action": kwargs.get("action"),
                "status": "confirmed",
            }

        async def get_marketplace_item(
            self, *args: Any, **kwargs: Any
        ) -> dict[str, Any]:
            return {
                "itemId": kwargs.get("item_id"),
                "name": "Vintage Camera",
                "price": "200",
                "status": "experimental",
            }

    registry = SessionRegistry(authenticate)
    app = create_app(registry, provider_operations=FullMockOperations())
    client = TestClient(app)

    # 1. Connect session
    created = client.post(
        "/api/v1/sessions",
        auth=credentials,
        json={
            "label": "Op Account",
            "cookies": [
                {"name": "c_user", "value": "1"},
                {"name": "xs", "value": "secret"},
            ],
        },
    )
    assert created.status_code == 201
    sid = created.json()["results"]["sessionId"]

    # 2. App Status & Diagnostics
    status_resp = client.get("/api/v1/app/status", auth=credentials)
    assert status_resp.status_code == 200
    assert status_resp.json()["results"]["activeSessions"] == 1

    diag_resp = client.get("/api/v1/diagnostics", auth=credentials)
    assert diag_resp.status_code == 200
    assert "auditLogs" in diag_resp.json()["results"]

    # 3. Session Status
    sess_status = client.get(f"/api/v1/sessions/{sid}/status", auth=credentials)
    assert sess_status.status_code == 200
    assert sess_status.json()["results"]["status"] == "connected"

    # 4. Reaction
    react_resp = client.post(
        f"/api/v1/sessions/{sid}/messages/reaction",
        auth=credentials,
        json={"messageId": "msg-123", "emoji": "❤️", "action": "add"},
    )
    assert react_resp.status_code == 200
    assert react_resp.json()["results"]["status"] == "confirmed"

    # 5. Unsend
    unsend_resp = client.post(
        f"/api/v1/sessions/{sid}/messages/unsend",
        auth=credentials,
        json={"messageId": "msg-123"},
    )
    assert unsend_resp.status_code == 200
    assert unsend_resp.json()["results"]["status"] == "revoked"

    # 6. User Info
    user_resp = client.get(f"/api/v1/sessions/{sid}/users/usr-456", auth=credentials)
    assert user_resp.status_code == 200
    assert user_resp.json()["results"]["name"] == "Jane Doe"

    # 7. Search
    search_resp = client.get(
        f"/api/v1/sessions/{sid}/search?q=Target", auth=credentials
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["results"]["count"] == 1

    # 8. Block
    block_resp = client.post(
        f"/api/v1/sessions/{sid}/privacy/block",
        auth=credentials,
        json={"userId": "usr-456", "action": "block"},
    )
    assert block_resp.status_code == 200
    assert block_resp.json()["results"]["action"] == "block"

    # 9. Marketplace
    market_resp = client.get(
        f"/api/v1/sessions/{sid}/marketplace/item-123", auth=credentials
    )
    assert market_resp.status_code == 200
    assert market_resp.json()["results"]["name"] == "Vintage Camera"

    # 10. Webhook probe test
    probe_resp = client.post("/api/v1/webhook/test", auth=credentials)
    assert probe_resp.status_code == 200
    assert "success" in probe_resp.json()["results"]

    # Verify no leaked secrets
    all_responses_text = "".join(
        [
            status_resp.text,
            diag_resp.text,
            sess_status.text,
            react_resp.text,
            unsend_resp.text,
            user_resp.text,
            search_resp.text,
            block_resp.text,
            market_resp.text,
        ]
    )
    assert "test-fb-id" not in all_responses_text
    assert "secret" not in all_responses_text


def test_media_and_websocket_endpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import base64
    from starlette.websockets import WebSocketDisconnect
    from fbchat_v2.service_media import MediaStorage

    credentials = ("provider", "secret")
    monkeypatch.setenv("FBCHAT_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("FBCHAT_API_USERNAME", credentials[0])
    monkeypatch.setenv("FBCHAT_API_PASSWORD", credentials[1])

    async def authenticate(_: str) -> dict[str, Any] | None:
        return {"FacebookID": "test-fb-id", "cookieFacebook": "c_user=1; xs=secret"}

    class MediaMockOperations(ProviderOperations):
        async def send_attachment(
            self,
            data_fb: dict[str, Any],
            thread_id: str,
            thread_type: str,
            file_paths: list[str],
            text: str | None = None,
        ) -> dict[str, Any]:
            return {
                "messageId": "mid.media_test_123",
                "threadId": thread_id,
                "status": "sent",
            }

    media_storage = MediaStorage(state_dir=tmp_path)
    registry = SessionRegistry(authenticator=authenticate)
    app = create_app(
        registry=registry,
        provider_operations=MediaMockOperations(),
        media_store=media_storage,
    )
    client = TestClient(app)

    # 1. Create session
    create_resp = client.post(
        "/api/v1/sessions",
        auth=credentials,
        json={
            "label": "Media Account",
            "cookies": [{"name": "c_user", "value": "1"}, {"name": "xs", "value": "2"}],
        },
    )
    assert create_resp.status_code == 201
    sid = create_resp.json()["results"]["sessionId"]

    # 2. Session listener start / status / stop
    listen_start = client.post(f"/api/v1/sessions/{sid}/listen/start", auth=credentials)
    assert listen_start.status_code == 200
    assert listen_start.json()["results"]["status"] == "listening"

    listen_status = client.get(
        f"/api/v1/sessions/{sid}/listen/status", auth=credentials
    )
    assert listen_status.status_code == 200
    assert listen_status.json()["results"]["status"] == "listening"

    listen_stop = client.post(f"/api/v1/sessions/{sid}/listen/stop", auth=credentials)
    assert listen_stop.status_code == 200
    assert listen_stop.json()["results"]["status"] == "idle"

    # 3. Media upload via JSON base64
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    b64_data = base64.b64encode(fake_png).decode("utf-8")
    upload_resp = client.post(
        "/api/v1/media/upload",
        auth=credentials,
        json={
            "fileName": "test_image.png",
            "mimeType": "image/png",
            "contentBase64": b64_data,
        },
    )
    assert upload_resp.status_code == 201
    media_res = upload_resp.json()["results"]
    media_id = media_res["mediaId"]
    assert media_id.startswith("med_")
    assert media_res["fileName"] == "test_image.png"

    # 4. Media upload via raw binary body
    binary_resp = client.post(
        "/api/v1/media/upload",
        auth=credentials,
        content=b"%PDF-1.4 dummy",
        headers={"Content-Type": "application/pdf", "X-File-Name": "report.pdf"},
    )
    assert binary_resp.status_code == 201
    pdf_media_id = binary_resp.json()["results"]["mediaId"]

    # 5. Media list & info
    list_resp = client.get("/api/v1/media", auth=credentials)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["results"]) >= 2

    info_resp = client.get(f"/api/v1/media/{media_id}/info", auth=credentials)
    assert info_resp.status_code == 200
    assert info_resp.json()["results"]["fileName"] == "test_image.png"

    # 6. Download media file
    file_resp = client.get(f"/api/v1/media/{media_id}", auth=credentials)
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "image/png"
    assert file_resp.content == fake_png

    # 7. Send media message
    media_msg_resp = client.post(
        f"/api/v1/sessions/{sid}/messages/media",
        auth=credentials,
        json={
            "threadId": "1234567890",
            "mediaIds": [media_id, pdf_media_id],
            "text": "Check out these documents",
        },
    )
    assert media_msg_resp.status_code == 200
    assert media_msg_resp.json()["results"]["status"] == "sent"
    assert media_msg_resp.json()["results"]["messageId"] == "mid.media_test_123"

    # 8. Delete media
    del_resp = client.delete(f"/api/v1/media/{media_id}", auth=credentials)
    assert del_resp.status_code == 200
    assert del_resp.json()["results"]["deleted"] is True

    # 9. WebSocket /ws authentication and ping/pong
    with client.websocket_connect("/ws?token=secret") as ws:
        greeting = ws.receive_json()
        assert greeting["event"] == "system.connected"
        ws.send_text("ping")
        assert ws.receive_text() == "pong"

    # 10. WebSocket rejection on invalid token
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws?token=wrong_secret") as ws:
            pass
