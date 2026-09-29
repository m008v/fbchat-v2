from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from pathlib import Path

import httpx
import pytest

from fbchat_v2.service_dispatcher import WebhookDispatcher, _is_ssrf_risk
from fbchat_v2.service_webhook import WebhookConfigStore


@pytest.fixture
def webhook_store(tmp_path: Path) -> WebhookConfigStore:
    return WebhookConfigStore(state_dir=tmp_path)


def test_ssrf_risk_detection() -> None:
    assert _is_ssrf_risk("127.0.0.1") is True
    assert _is_ssrf_risk("10.0.0.1") is True
    assert _is_ssrf_risk("192.168.1.50") is True
    assert _is_ssrf_risk("169.254.169.254") is True
    assert _is_ssrf_risk("localhost") is True


@pytest.mark.asyncio
async def test_dispatcher_enqueues_and_drops_when_full(
    webhook_store: WebhookConfigStore,
) -> None:
    dispatcher = WebhookDispatcher(webhook_store, max_queue_size=2)
    assert dispatcher.enqueue("message.received", {"text": "one"}) is True
    assert dispatcher.enqueue("message.received", {"text": "two"}) is True
    # Third item should be dropped due to bounded queue
    assert dispatcher.enqueue("message.received", {"text": "three"}) is False

    stats = dispatcher.stats()
    assert stats["droppedCount"] == 1
    assert stats["queueSize"] == 2
    assert stats["maxQueueSize"] == 2


@pytest.mark.asyncio
async def test_dispatcher_delivers_with_hmac_signature(
    webhook_store: WebhookConfigStore,
) -> None:
    await webhook_store.update(
        enabled=True,
        url="http://external-webhook.example.com/receiver",
        events=["message.sent", "session.status"],
        secret="test-signing-secret",
        clear_secret=False,
    )

    captured_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"received": True})

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    dispatcher = WebhookDispatcher(
        webhook_store, client=mock_client, allow_internal=True
    )
    await dispatcher.start()

    try:
        dispatcher.enqueue("message.sent", {"messageId": "msg-123", "text": "hello"})
        await asyncio.sleep(0.1)

        assert len(captured_requests) == 1
        request = captured_requests[0]
        assert request.url == "http://external-webhook.example.com/receiver"
        assert "X-Hub-Signature-256" in request.headers

        # Verify HMAC signature
        signature_header = request.headers["X-Hub-Signature-256"]
        expected_sig = (
            "sha256="
            + hmac.new(
                b"test-signing-secret", request.content, hashlib.sha256
            ).hexdigest()
        )
        assert signature_header == expected_sig

        body = json.loads(request.content)
        assert body["event"] == "message.sent"
        assert body["data"]["messageId"] == "msg-123"

        stats = dispatcher.stats()
        assert stats["deliveredCount"] == 1
        assert stats["lastStatus"] == "delivered"
    finally:
        await dispatcher.stop()
        await mock_client.aclose()


@pytest.mark.asyncio
async def test_dispatcher_skips_unsubscribed_events(
    webhook_store: WebhookConfigStore,
) -> None:
    await webhook_store.update(
        enabled=True,
        url="http://external-webhook.example.com/receiver",
        events=["session.status"],
        secret=None,
        clear_secret=True,
    )

    captured_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"received": True})

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    dispatcher = WebhookDispatcher(
        webhook_store, client=mock_client, allow_internal=True
    )
    await dispatcher.start()

    try:
        # message.deleted is not in the subscribed events list
        dispatcher.enqueue("message.deleted", {"messageId": "msg-999"})
        await asyncio.sleep(0.05)

        assert len(captured_requests) == 0
        assert dispatcher.stats()["deliveredCount"] == 0
    finally:
        await dispatcher.stop()
        await mock_client.aclose()


@pytest.mark.asyncio
async def test_dispatcher_blocks_ssrf_destinations(
    webhook_store: WebhookConfigStore,
) -> None:
    await webhook_store.update(
        enabled=True,
        url="http://127.0.0.1:8080/internal-endpoint",
        events=["message.sent"],
        secret=None,
        clear_secret=True,
    )

    mock_client = httpx.AsyncClient()
    dispatcher = WebhookDispatcher(
        webhook_store, client=mock_client, allow_internal=False
    )
    await dispatcher.start()

    try:
        dispatcher.enqueue("message.sent", {"test": True})
        await asyncio.sleep(0.05)

        stats = dispatcher.stats()
        assert stats["lastStatus"] == "ssrf_blocked"
        assert stats["failedCount"] == 1
        assert "SSRF blocked" in (stats["lastError"] or "")
    finally:
        await dispatcher.stop()
        await mock_client.aclose()


@pytest.mark.asyncio
async def test_dispatcher_test_probe_returns_telemetry(
    webhook_store: WebhookConfigStore,
) -> None:
    await webhook_store.update(
        enabled=True,
        url="http://probe-dest.example.com/webhook",
        events=["message.sent"],
        secret="probe-secret",
        clear_secret=False,
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"pong": True})

    transport = httpx.MockTransport(mock_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    dispatcher = WebhookDispatcher(
        webhook_store, client=mock_client, allow_internal=True
    )

    result = await dispatcher.test_probe()
    assert result["success"] is True
    assert result["statusCode"] == 200
    assert result["signatureIncluded"] is True
    assert result["error"] is None
    assert result["latencyMs"] >= 0

    await mock_client.aclose()
