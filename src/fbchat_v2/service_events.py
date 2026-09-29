"""
Realtime Event Hub and WebSocket broadcasting for fbchat-v2.

Provides:
- Realtime WebSocket event streaming (/ws) with query/header authentication.
- Unified dual delivery: broadcasts to connected WebSockets and WebhookDispatcher.
- Session listener management to monitor inbound events and status changes.
- Sanitized event envelopes following GOWA event model.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from fastapi import WebSocket

from fbchat_v2.service_dispatcher import WebhookDispatcher

logger = logging.getLogger("fbchat_v2.events")


class RealtimeEventHub:
    """Central event broadcaster managing WebSocket clients and webhook forwarding."""

    def __init__(self, dispatcher: WebhookDispatcher | None = None) -> None:
        self._dispatcher = dispatcher
        self._clients: dict[WebSocket, str | None] = {}  # ws -> session_filter
        self._lock = asyncio.Lock()
        self._total_broadcast = 0
        self._total_errors = 0

    @property
    def dispatcher(self) -> WebhookDispatcher | None:
        return self._dispatcher

    @dispatcher.setter
    def dispatcher(self, d: WebhookDispatcher | None) -> None:
        self._dispatcher = d

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def metrics(self) -> dict[str, Any]:
        return {
            "connectedClients": len(self._clients),
            "totalBroadcast": self._total_broadcast,
            "totalErrors": self._total_errors,
        }

    async def register(
        self, websocket: WebSocket, session_id: str | None = None
    ) -> None:
        async with self._lock:
            self._clients[websocket] = session_id
        logger.info(
            "WebSocket client registered (session filter: %s)", session_id or "all"
        )

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(websocket, None)
        logger.info("WebSocket client unregistered")

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Broadcasts an event to all matching WebSockets and forwards to webhook dispatcher."""
        self._total_broadcast += 1
        event_session_id = event.get("sessionId")
        payload_text = json.dumps(event)

        # 1. Forward to connected WebSockets
        dead_clients: list[WebSocket] = []
        async with self._lock:
            clients_snapshot = list(self._clients.items())

        for ws, session_filter in clients_snapshot:
            # If client specified a session filter, skip events from other sessions (except global events)
            if (
                session_filter
                and event_session_id
                and session_filter != event_session_id
            ):
                continue
            try:
                await ws.send_text(payload_text)
            except Exception:
                self._total_errors += 1
                dead_clients.append(ws)

        if dead_clients:
            async with self._lock:
                for ws in dead_clients:
                    self._clients.pop(ws, None)

        # 2. Forward to Webhook Dispatcher
        if self._dispatcher:
            try:
                await self._dispatcher.enqueue(event)
            except Exception as exc:
                logger.error("Failed to forward event to webhook dispatcher: %s", exc)

    async def emit_session_status(
        self,
        session_id: str,
        status: str,
        tenant_id: str = "default",
        error: str | None = None,
    ) -> None:
        event = {
            "event": "session.status",
            "sessionId": session_id,
            "tenantId": tenant_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "status": status,
                "error": error,
            },
        }
        await self.broadcast(event)

    async def emit_message_received(
        self,
        session_id: str,
        thread_id: str,
        thread_type: str,
        message_id: str,
        sender_id: str,
        text: str | None,
        attachments: list[dict[str, Any]] | None = None,
        reply_to_id: str | None = None,
    ) -> None:
        event = {
            "event": "message.received",
            "sessionId": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "threadId": thread_id,
                "threadType": thread_type,
                "messageId": message_id,
                "senderId": sender_id,
                "text": text,
                "attachments": attachments or [],
                "replyToMessageId": reply_to_id,
            },
        }
        await self.broadcast(event)


class SessionListenerManager:
    """Controls background listeners for active sessions."""

    def __init__(self, event_hub: RealtimeEventHub) -> None:
        self._event_hub = event_hub
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._statuses: dict[str, str] = (
            {}
        )  # session_id -> "idle" | "listening" | "error"

    def get_status(self, session_id: str) -> str:
        return self._statuses.get(session_id, "idle")

    def is_listening(self, session_id: str) -> bool:
        return self.get_status(session_id) == "listening"

    async def start_listening(
        self,
        session_id: str,
        worker_coro: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> bool:
        if self.is_listening(session_id):
            return True

        self._statuses[session_id] = "listening"
        await self._event_hub.emit_session_status(session_id, "listening")

        if worker_coro:

            async def _runner() -> None:
                try:
                    await worker_coro()
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.error("Session listener error for %s: %s", session_id, exc)
                    self._statuses[session_id] = "error"
                    await self._event_hub.emit_session_status(
                        session_id,
                        "error",
                        error="Listener encountered unexpected error",
                    )

            task = asyncio.create_task(_runner())
            self._tasks[session_id] = task

        return True

    async def stop_listening(self, session_id: str) -> bool:
        task = self._tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        was_listening = self._statuses.get(session_id) == "listening"
        self._statuses[session_id] = "idle"
        if was_listening:
            await self._event_hub.emit_session_status(session_id, "idle")
        return True

    async def stop_all(self) -> None:
        for session_id in list(self._tasks.keys()):
            await self.stop_listening(session_id)
