"""Asynchronous Webhook Dispatcher with bounded queue, HMAC signing, retries and SSRF protection."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx

from .service_webhook import WebhookConfigStore

logger = logging.getLogger("fbchat_v2.dispatcher")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_ssrf_risk(hostname: str) -> bool:
    """Check if the target hostname resolves to a private, loopback or reserved IP."""
    try:
        # Check direct IP literals first
        ip = ipaddress.ip_address(hostname)
        return (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        )
    except ValueError:
        pass

    # Resolve hostname to IPs
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True  # If unresolvable, treat as unsafe

    for item in addr_info:
        ip_str = item[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
            ):
                return True
        except ValueError:
            return True
    return False


class WebhookDispatcher:
    """Bounded, retrying webhook event dispatcher with HMAC authentication."""

    def __init__(
        self,
        webhook_store: WebhookConfigStore,
        *,
        max_queue_size: int = 1000,
        max_retries: int = 3,
        allow_internal: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._webhook_store = webhook_store
        self._max_queue_size = max_queue_size
        self._max_retries = max_retries
        self._allow_internal = allow_internal or os.environ.get(
            "FBCHAT_ALLOW_INTERNAL_WEBHOOK", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._client = client
        self._queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._worker_task: asyncio.Task[None] | None = None
        self._dispatched_count = 0
        self._delivered_count = 0
        self._failed_count = 0
        self._dropped_count = 0
        self._last_status = "idle"
        self._last_error: str | None = None
        self._last_delivered_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._dispatch_loop())

    async def stop(self) -> None:
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    def enqueue(self, event_name: str, payload: dict[str, Any]) -> bool:
        """Enqueue an event for asynchronous delivery. Returns False if queue is full."""
        try:
            self._queue.put_nowait((event_name, payload))
            self._dispatched_count += 1
            return True
        except asyncio.QueueFull:
            self._dropped_count += 1
            self._last_status = "dropped"
            self._last_error = "Webhook dispatch queue overflow; event discarded."
            return False

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=10.0)

    async def _dispatch_loop(self) -> None:
        while True:
            event_name, payload = await self._queue.get()
            try:
                await self._deliver_event(event_name, payload)
            except asyncio.CancelledError:
                break
            except Exception as error:  # pragma: no cover - safety catch
                logger.exception("Unexpected error in webhook delivery: %s", error)
            finally:
                self._queue.task_done()

    async def _deliver_event(self, event_name: str, payload: dict[str, Any]) -> bool:
        # Read current webhook config
        config = self._webhook_store._read_unlocked()
        if not config.enabled or not config.url:
            return False
        if config.events and event_name not in config.events:
            return False

        # SSRF validation
        parsed_url = urlsplit(config.url)
        hostname = parsed_url.hostname or ""
        if not self._allow_internal and _is_ssrf_risk(hostname):
            self._failed_count += 1
            self._last_status = "ssrf_blocked"
            self._last_error = (
                f"SSRF blocked: {hostname} resolves to a private or restricted address."
            )
            return False

        body_dict = {
            "event": event_name,
            "timestamp": _utc_now().isoformat(),
            "data": payload,
        }
        body_bytes = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "fbchat-v2-dispatcher/1.0",
        }
        if config.secret:
            signature = hmac.new(
                config.secret.encode("utf-8"), body_bytes, hashlib.sha256
            ).hexdigest()
            headers["X-Hub-Signature-256"] = f"sha256={signature}"

        own_client = self._client is None
        client = await self._get_client()
        attempt = 0
        success = False

        try:
            while attempt < self._max_retries and not success:
                attempt += 1
                try:
                    self._last_status = "delivering"
                    response = await client.post(
                        config.url, content=body_bytes, headers=headers
                    )
                    if response.is_success:
                        success = True
                        self._delivered_count += 1
                        self._last_status = "delivered"
                        self._last_error = None
                        self._last_delivered_at = _utc_now()
                    elif 400 <= response.status_code < 500:
                        # Client error - not retryable
                        self._failed_count += 1
                        self._last_status = "failed"
                        self._last_error = f"Webhook endpoint returned client error {response.status_code}."
                        break
                    else:
                        # 5xx server error - retryable
                        if attempt >= self._max_retries:
                            self._failed_count += 1
                            self._last_status = "failed"
                            self._last_error = f"Webhook endpoint failed with status {response.status_code} after {attempt} attempts."
                        else:
                            await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                except (httpx.TransportError, httpx.TimeoutException) as exc:
                    if attempt >= self._max_retries:
                        self._failed_count += 1
                        self._last_status = "failed"
                        self._last_error = f"Webhook connection error: {exc}"
                    else:
                        await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
        finally:
            if own_client:
                await client.aclose()

        return success

    async def test_probe(
        self,
        target_url: str | None = None,
        target_secret: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch a test ping directly and synchronously, returning delivery telemetry."""
        config = self._webhook_store._read_unlocked()
        url = target_url or config.url
        secret = target_secret if target_secret is not None else config.secret

        if not url:
            return {
                "success": False,
                "statusCode": None,
                "latencyMs": 0.0,
                "error": "No webhook URL configured or provided.",
                "signatureIncluded": False,
            }

        parsed_url = urlsplit(url)
        hostname = parsed_url.hostname or ""
        if not self._allow_internal and _is_ssrf_risk(hostname):
            return {
                "success": False,
                "statusCode": None,
                "latencyMs": 0.0,
                "error": f"SSRF blocked: {hostname} resolves to a private or restricted address.",
                "signatureIncluded": bool(secret),
            }

        body_dict = {
            "event": "test.ping",
            "timestamp": _utc_now().isoformat(),
            "data": {"message": "Test ping from fbchat-v2 provider portal."},
        }
        body_bytes = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "fbchat-v2-dispatcher/1.0",
        }
        if secret:
            signature = hmac.new(
                secret.encode("utf-8"), body_bytes, hashlib.sha256
            ).hexdigest()
            headers["X-Hub-Signature-256"] = f"sha256={signature}"

        client = await self._get_client()
        own_client = self._client is None
        start_time = time.perf_counter()
        try:
            response = await client.post(url, content=body_bytes, headers=headers)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            is_ok = response.is_success
            return {
                "success": is_ok,
                "statusCode": response.status_code,
                "latencyMs": elapsed_ms,
                "error": None if is_ok else f"HTTP status {response.status_code}",
                "signatureIncluded": bool(secret),
            }
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "statusCode": None,
                "latencyMs": elapsed_ms,
                "error": str(exc),
                "signatureIncluded": bool(secret),
            }
        finally:
            if own_client:
                await client.aclose()

    def stats(self) -> dict[str, Any]:
        """Return operational dispatcher metrics for monitoring and health reporting."""
        return {
            "dispatchedCount": self._dispatched_count,
            "deliveredCount": self._delivered_count,
            "failedCount": self._failed_count,
            "droppedCount": self._dropped_count,
            "queueSize": self._queue.qsize(),
            "maxQueueSize": self._max_queue_size,
            "lastStatus": self._last_status,
            "lastError": self._last_error,
            "lastDeliveredAt": (
                self._last_delivered_at.isoformat() if self._last_delivered_at else None
            ),
        }
