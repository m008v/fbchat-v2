from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from fbchat_v2.service_dispatcher import WebhookDispatcher
from fbchat_v2.service_events import RealtimeEventHub, SessionListenerManager
from fbchat_v2.service_webhook import WebhookConfigStore


@pytest.fixture
def webhook_store(tmp_path: Path) -> WebhookConfigStore:
    return WebhookConfigStore(state_dir=tmp_path)


@pytest.mark.asyncio
async def test_event_hub_broadcast_and_session_filtering(
    webhook_store: WebhookConfigStore,
) -> None:
    dispatcher = WebhookDispatcher(webhook_store)
    hub = RealtimeEventHub(dispatcher)

    ws_all = MagicMock()
    ws_all.send_text = AsyncMock()

    ws_session1 = MagicMock()
    ws_session1.send_text = AsyncMock()

    await hub.register(ws_all, session_id=None)
    await hub.register(ws_session1, session_id="sess-1")

    assert hub.client_count == 2

    # Broadcast event for sess-1
    await hub.broadcast(
        {"event": "message.received", "sessionId": "sess-1", "payload": {}}
    )

    assert ws_all.send_text.await_count == 1
    assert ws_session1.send_text.await_count == 1

    # Broadcast event for sess-2
    await hub.broadcast(
        {"event": "message.received", "sessionId": "sess-2", "payload": {}}
    )

    assert ws_all.send_text.await_count == 2
    # ws_session1 should NOT have received event for sess-2
    assert ws_session1.send_text.await_count == 1

    await hub.unregister(ws_all)
    await hub.unregister(ws_session1)
    assert hub.client_count == 0


@pytest.mark.asyncio
async def test_event_hub_removes_dead_clients() -> None:
    hub = RealtimeEventHub(None)

    dead_ws = MagicMock()
    dead_ws.send_text = AsyncMock(side_effect=RuntimeError("connection closed"))

    await hub.register(dead_ws, session_id=None)
    assert hub.client_count == 1

    await hub.broadcast({"event": "ping"})

    assert hub.client_count == 0
    assert hub.metrics["totalErrors"] == 1


@pytest.mark.asyncio
async def test_session_listener_manager_lifecycle() -> None:
    hub = RealtimeEventHub(None)
    manager = SessionListenerManager(hub)

    assert manager.get_status("session-abc") == "idle"
    assert not manager.is_listening("session-abc")

    # Start listening
    started = await manager.start_listening("session-abc")
    assert started is True
    assert manager.is_listening("session-abc")
    assert manager.get_status("session-abc") == "listening"

    # Stop listening
    stopped = await manager.stop_listening("session-abc")
    assert stopped is True
    assert not manager.is_listening("session-abc")
    assert manager.get_status("session-abc") == "idle"
