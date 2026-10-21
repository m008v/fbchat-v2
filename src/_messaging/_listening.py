"""
Đường dẫn file:
  src/_messaging/_listening.py

Mục đích:
  - Khởi tạo luồng lắng nghe tin nhắn (MQTT/WebSockets) thường.

Cách hoạt động:
  - Nạp dependency/guard cần thiết, thực hiện các async HTTP requests tới API nội bộ hoặc GraphQL của Facebook.
  - Các thao tác request đều phải thông qua httpx.AsyncClient và module _core._utils để bảo đảm an toàn kết nối.
  - Payload gửi đi/nhận về được xử lý JSON cẩn thận, bắt lỗi try-except đầy đủ để tránh crash hệ thống.

File liên quan:
  - src/main.py và các entrypoint khác.
  - Phụ thuộc vào _core._session, _core._utils để khởi tạo và thao tác HTTP.

Author: @m008v (MinhHuyDev)
"""

from __future__ import annotations

import asyncio
import datetime
import json
import ssl
import threading
import time
from collections import OrderedDict
from queue import Empty, Full, Queue
from typing import Any
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

from _core._console import safe_print as _safe_print
from _core._utils import generate_client_id, generate_session_id, json_minimal
from _features._thread import _all_thread_data
from _messaging._reconnect import (
    ConnectionCallback,
    ConnectionFailure,
    ConnectionStateTracker,
    ReconnectPolicy,
    classify_connection_error,
    finish_listener_worker,
)

DEFAULT_MESSAGE_QUEUE_MAXSIZE = 1000
_CONNECT_TIMEOUT_SECONDS = 5.0
_MESSAGE_DEDUPE_TTL_SECONDS = 600.0
_MESSAGE_DEDUPE_MAXSIZE = 4096


class listeningEvent:
    """Listener MQTT có queue giới hạn và API async không chặn event loop."""

    def __init__(
        self,
        dataFB: dict[str, Any],
        message_queue_maxsize: int = DEFAULT_MESSAGE_QUEUE_MAXSIZE,
        *,
        reconnect_policy: ReconnectPolicy | None = None,
        on_connection_state: ConnectionCallback | None = None,
    ) -> None:
        try:
            queue_size = int(message_queue_maxsize)
        except (TypeError, ValueError):
            queue_size = DEFAULT_MESSAGE_QUEUE_MAXSIZE
        if queue_size < 1:
            queue_size = DEFAULT_MESSAGE_QUEUE_MAXSIZE

        self.bodyResults = self._fresh_body_results()
        self.messageQueueMaxSize = queue_size
        self.messageQueue: Queue[dict[str, Any]] = Queue(maxsize=queue_size)
        self.droppedMessages = 0
        self.syncToken: str | None = None
        self.lastSeqID: int | None = None
        self.dataFB = dataFB
        self.fbt: dict[str, Any] = {}
        self.retry_count = 0
        self.max_retries = 3
        self.mqtt: mqtt.Client | None = None
        self._stop_event = threading.Event()
        self._reconnect_requested = threading.Event()
        if reconnect_policy is not None and not isinstance(
            reconnect_policy, ReconnectPolicy
        ):
            raise TypeError("reconnect_policy must be a ReconnectPolicy or None")
        self.reconnect_policy = reconnect_policy or ReconnectPolicy()
        self._connection_tracker = ConnectionStateTracker(on_connection_state)
        self._run_lock = threading.Lock()
        self._client_lock = threading.Lock()
        self._fatal_reason: str | None = None
        self._connected_since: float | None = None
        self._sequence_error: str | None = None
        self._dedupe_lock = threading.Lock()
        self._recent_messages: OrderedDict[tuple[str, str], float] = OrderedDict()

    @property
    def connection_state(self) -> str:
        return str(self._connection_tracker.snapshot()["state"])

    @property
    def connection_status(self) -> dict[str, Any]:
        return self._connection_tracker.snapshot()

    def set_connection_state_callback(
        self, callback: ConnectionCallback | None
    ) -> None:
        self._connection_tracker.set_callback(callback)

    def _is_current_client(self, client: mqtt.Client) -> bool:
        with self._client_lock:
            return self.mqtt is None or self.mqtt is client

    def _remember_message(self, body: dict[str, Any]) -> bool:
        message_id = body.get("messageID")
        if not isinstance(message_id, str) or not message_id or len(message_id) > 1024:
            return True
        thread_id = str(body.get("replyToID", ""))
        if len(thread_id) > 1024:
            return True
        key = (thread_id, message_id)
        now = time.monotonic()
        with self._dedupe_lock:
            while self._recent_messages:
                first = next(iter(self._recent_messages))
                if now - self._recent_messages[first] < _MESSAGE_DEDUPE_TTL_SECONDS:
                    break
                self._recent_messages.popitem(last=False)
            if key in self._recent_messages:
                return False
            self._recent_messages[key] = now
            while len(self._recent_messages) > _MESSAGE_DEDUPE_MAXSIZE:
                self._recent_messages.popitem(last=False)
        return True

    @staticmethod
    def _fresh_body_results() -> dict[str, Any]:
        return {
            "body": None,
            "timestamp": 0,
            "userID": 0,
            "messageID": None,
            "replyToID": 0,
            "type": None,
            "attachments": {"id": 0, "url": None},
        }

    def get_message_blocking(
        self, block: bool = False, timeout: float | None = None
    ) -> dict[str, Any] | None:
        try:
            return self.messageQueue.get(
                block=block, timeout=timeout if block else None
            )
        except Empty:
            return None

    async def get_message(self, timeout: float | None = None) -> dict[str, Any] | None:
        """Chờ một tin nhắn mà không chặn event loop."""
        return await asyncio.to_thread(self.get_message_blocking, True, timeout)

    def _publish_body_results(self, body: dict[str, Any]) -> None:
        self.bodyResults = body
        try:
            self.messageQueue.put_nowait(body)
            return
        except Full:
            try:
                self.messageQueue.get_nowait()
            except Empty:
                pass

        self.droppedMessages += 1
        _safe_print(
            f"[{datetime.datetime.now()}] Hàng đợi đầy "
            f"(max={self.messageQueueMaxSize}); đã bỏ tin cũ nhất; "
            f"tổng số tin bị bỏ={self.droppedMessages}"
        )
        try:
            self.messageQueue.put_nowait(body)
        except Full:
            self.droppedMessages += 1

    def _body_from_delta(self, delta: Any) -> dict[str, Any] | None:
        if not isinstance(delta, dict):
            return None
        metadata = delta.get("messageMetadata")
        if not isinstance(metadata, dict):
            return None

        thread_key = metadata.get("threadKey")
        if not isinstance(thread_key, dict):
            return None
        other_user_id = thread_key.get("otherUserFbId")
        body = self._fresh_body_results()
        body.update(
            {
                "body": delta.get("body"),
                "timestamp": metadata.get("timestamp", 0),
                "userID": metadata.get("actorFbId", 0),
                "messageID": metadata.get("messageId"),
                "replyToID": (
                    other_user_id
                    if other_user_id is not None
                    else thread_key.get("threadFbId", 0)
                ),
                "type": "user" if other_user_id is not None else "thread",
            }
        )
        attachments = delta.get("attachments")
        if (
            isinstance(attachments, list)
            and attachments
            and isinstance(attachments[0], dict)
        ):
            attachment = attachments[0]
            body["attachments"]["id"] = attachment.get("fbid", 0)
            mercury = attachment.get("mercury")
            blob = mercury.get("blob_attachment") if isinstance(mercury, dict) else None
            preview = blob.get("preview") if isinstance(blob, dict) else None
            if isinstance(preview, dict):
                body["attachments"]["url"] = preview.get("uri")
        return body

    @staticmethod
    def _coerce_seq_id(value: Any, source: str = "seq_id") -> int | None:
        try:
            seq_id = int(str(value).strip())
        except (TypeError, ValueError):
            _safe_print(f"[{datetime.datetime.now()}] Bỏ qua {source} không hợp lệ.")
            return None
        if seq_id < 0:
            _safe_print(f"[{datetime.datetime.now()}] Bỏ qua {source} âm.")
            return None
        return seq_id

    def _set_last_seq_id(
        self, value: Any, source: str = "seq_id", allow_reset: bool = False
    ) -> bool:
        seq_id = self._coerce_seq_id(value, source)
        if seq_id is None:
            return False
        previous = self.lastSeqID
        if previous is not None and seq_id < previous and not allow_reset:
            _safe_print(f"[{datetime.datetime.now()}] Bỏ qua {source} cũ.")
            return False
        self.lastSeqID = seq_id
        return True

    def _apply_thread_data(self, result: dict[str, Any], previous: int | None) -> None:
        self.fbt = result
        if not self._set_last_seq_id(
            result.get("last_seq_id"), "GraphQL sync_sequence_id", allow_reset=True
        ):
            self.lastSeqID = previous

    def get_last_seq_id_blocking(self) -> int | None:
        previous = self.lastSeqID
        self._sequence_error = None
        try:
            self._apply_thread_data(
                _all_thread_data.func_blocking(self.dataFB), previous
            )
        except Exception as error:  # lỗi mạng cần giữ sequence cũ để phục hồi
            self.lastSeqID = previous
            self._sequence_error = classify_connection_error(error)
            _safe_print(
                f"[{datetime.datetime.now()}] Không thể làm mới last_seq_id "
                f"({self._sequence_error})."
            )
        return self.lastSeqID

    async def get_last_seq_id(self) -> int | None:
        previous = self.lastSeqID
        self._sequence_error = None
        try:
            result = await _all_thread_data.func(self.dataFB)
            self._apply_thread_data(result, previous)
        except Exception as error:  # lỗi mạng cần giữ sequence cũ để phục hồi
            self.lastSeqID = previous
            self._sequence_error = classify_connection_error(error)
            _safe_print(
                f"[{datetime.datetime.now()}] Không thể làm mới last_seq_id "
                f"({self._sequence_error})."
            )
        return self.lastSeqID

    def _publish_pending_queue(self, client: mqtt.Client) -> bool:
        if self.syncToken is None or self.lastSeqID is None:
            if self.syncToken is not None:
                self.syncToken = None
            self.get_last_seq_id_blocking()
        if self._sequence_error is not None and self._sequence_error != "network":
            self._fatal_reason = self._sequence_error
            self._reconnect_requested.set()
            client.disconnect()
            return False
        if self.lastSeqID is None:
            reason = self._sequence_error or "unknown"
            if reason != "network":
                self._fatal_reason = reason
            self._reconnect_requested.set()
            client.disconnect()
            return False

        queue: dict[str, Any] = {
            "sync_api_version": 10,
            "max_deltas_able_to_process": 1000,
            "delta_batch_size": 500,
            "encoding": "JSON",
            "entity_fbid": self.dataFB["FacebookID"],
            "orca_version": "1.2.0",
        }
        if self.syncToken is None:
            topic = "/messenger_sync_create_queue"
            queue["initial_titan_sequence_id"] = self.lastSeqID
            queue["device_params"] = None
        else:
            topic = "/messenger_sync_get_diffs"
            queue["last_seq_id"] = self.lastSeqID
            queue["sync_token"] = self.syncToken
        result = client.publish(topic, json_minimal(queue), qos=1, retain=False)
        status = getattr(result, "rc", mqtt.MQTT_ERR_SUCCESS)
        if isinstance(status, int) and status != mqtt.MQTT_ERR_SUCCESS:
            self._reconnect_requested.set()
            client.disconnect()
            return False
        return True

    def _on_connect(
        self, client: mqtt.Client, userdata: Any, flags: Any, rc: int
    ) -> None:
        if not self._is_current_client(client):
            return
        if self._stop_event.is_set():
            client.disconnect()
            return
        if rc != 0:
            reason = (
                "auth_required"
                if rc in (4, 5)
                else "network" if rc == 3 else "protocol"
            )
            if reason != "network":
                self._fatal_reason = reason
                self._connection_tracker.update(
                    "auth_required" if reason == "auth_required" else "fatal", reason
                )
            else:
                self._connection_tracker.update("reconnecting", reason)
            self._reconnect_requested.set()
            client.disconnect()
            return
        if self._publish_pending_queue(client) is not False:
            self._connected_since = time.monotonic()
            self._connection_tracker.update("connected")

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: Any) -> None:
        if self._stop_event.is_set() or not self._is_current_client(client):
            return
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _safe_print("Không thể giải mã dữ liệu MQTT trên /t_ms.")
            return

        if not isinstance(payload, dict):
            _safe_print("Bỏ qua dữ liệu MQTT vì payload không phải JSON object.")
            return
        deltas = payload.get("deltas")
        if deltas is not None and not isinstance(deltas, list):
            _safe_print("Bỏ qua dữ liệu MQTT vì trường deltas không phải danh sách.")
            return
        if "syncToken" in payload and "firstDeltaSeqId" in payload:
            sync_token = payload.get("syncToken")
            if not isinstance(sync_token, str) or not sync_token:
                _safe_print("Bỏ qua dữ liệu MQTT vì syncToken không hợp lệ.")
                return

        for delta in deltas or []:
            body = self._body_from_delta(delta)
            if body is not None and self._remember_message(body):
                self._publish_body_results(body)

        if "syncToken" in payload and "firstDeltaSeqId" in payload:
            self.syncToken = sync_token
            self._set_last_seq_id(
                payload.get("lastIssuedSeqId") or payload.get("firstDeltaSeqId"),
                "MQTT first/last seq_id",
            )
            self.retry_count = 0
        elif "lastIssuedSeqId" in payload:
            self._set_last_seq_id(payload["lastIssuedSeqId"], "MQTT lastIssuedSeqId")

        if "errorCode" not in payload:
            return
        error = payload["errorCode"]
        is_overflow = error == 100 or str(error).upper() == "ERROR_QUEUE_OVERFLOW"
        if is_overflow and self.retry_count < self.max_retries:
            self.retry_count += 1
            self.syncToken = None
            self.get_last_seq_id_blocking()
            if self.lastSeqID is not None:
                self._publish_pending_queue(client)
                return

        reason = (
            "network"
            if is_overflow
            else classify_connection_error(RuntimeError(str(error)))
        )
        if reason != "network":
            self._fatal_reason = reason
            self._connection_tracker.update(
                "auth_required" if reason == "auth_required" else "fatal", reason
            )
        _safe_print(f"MQTT queue thất bại ({reason}); chi tiết đã được ẩn.")
        self.retry_count = 0
        self._reconnect_requested.set()
        client.disconnect()

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        if not self._is_current_client(client):
            return
        if not self._stop_event.is_set() and self._fatal_reason is None:
            self._connection_tracker.update("reconnecting", "network")

    def _build_client(self) -> mqtt.Client:
        session_id = generate_session_id()
        user = {
            "u": self.dataFB["FacebookID"],
            "s": session_id,
            "chat_on": json_minimal(True),
            "fg": False,
            "d": generate_client_id(),
            "ct": "websocket",
            "aid": 219994525426954,
            "mqtt_sid": "",
            "cp": 3,
            "ecp": 10,
            "st": "/t_ms",
            "pm": [],
            "dc": "",
            "no_auto_fg": True,
            "gas": None,
            "pack": [],
        }
        host = f"wss://edge-chat.facebook.com/chat?region=eag&sid={session_id}"
        parsed_host = urlparse(host)
        client_options: dict[str, Any] = dict(
            client_id="mqttwsclient",
            clean_session=True,
            protocol=mqtt.MQTTv31,
            transport="websockets",
        )
        # One supervisor owns retry timing. Paho 1.x has no constructor flag.
        try:
            client = mqtt.Client(**client_options, reconnect_on_failure=False)
        except TypeError:
            client = mqtt.Client(**client_options)
            client._reconnect_on_failure = False
        client._connect_timeout = _CONNECT_TIMEOUT_SECONDS
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        client.tls_insecure_set(False)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        client.username_pw_set(username=json_minimal(user))
        client.ws_set_options(
            path=f"{parsed_host.path}?{parsed_host.query}",
            headers={
                "Cookie": self.dataFB["cookieFacebook"],
                "Origin": "https://www.facebook.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137 Safari/537.36",
                "Referer": "https://www.facebook.com/",
                "Host": "edge-chat.facebook.com",
            },
        )
        return client

    def connect_mqtt_blocking(self) -> None:
        """Run one MQTT supervisor; startup and runtime share the retry policy."""
        self._run_listener()

    def _run_listener(
        self,
        cancelled: threading.Event | None = None,
        claimed: threading.Event | None = None,
    ) -> None:
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("MQTT listener is already running")
        if claimed is not None:
            claimed.set()
        attempts = 0
        try:
            if cancelled is not None and cancelled.is_set():
                return
            self._stop_event.clear()
            self._fatal_reason = None
            if cancelled is not None and cancelled.is_set():
                self._stop_event.set()
                return
            self._connection_tracker.update("starting")
            while not self._stop_event.is_set():
                self._reconnect_requested.clear()
                self._connected_since = None
                client: mqtt.Client | None = None
                reason = "network"
                try:
                    client = self._build_client()
                    with self._client_lock:
                        self.mqtt = client
                    if self._stop_event.is_set():
                        break
                    connect_result = client.connect(
                        "edge-chat.facebook.com", port=443, keepalive=10
                    )
                    if (
                        isinstance(connect_result, int)
                        and connect_result != mqtt.MQTT_ERR_SUCCESS
                    ):
                        raise ConnectionFailure("network")
                    if not self._stop_event.is_set():
                        client.loop_forever(retry_first_connection=False)
                    reason = self._fatal_reason or "network"
                except Exception as error:
                    reason = self._fatal_reason or classify_connection_error(error)
                finally:
                    if client is not None:
                        try:
                            client.disconnect()
                        except (OSError, ValueError):
                            _safe_print("MQTT cleanup failed (details hidden).")
                    with self._client_lock:
                        if self.mqtt is client:
                            self.mqtt = None
                if self._stop_event.is_set():
                    break
                if reason != "network":
                    self._connection_tracker.update(
                        "auth_required" if reason == "auth_required" else "fatal",
                        reason,
                    )
                    raise ConnectionFailure(reason) from None
                if (
                    self._connected_since is not None
                    and time.monotonic() - self._connected_since
                    >= self.reconnect_policy.stable_reset_after
                ):
                    attempts = 0
                attempts += 1
                if not self.reconnect_policy.allows(attempts):
                    reason = (
                        "retry_disabled"
                        if not self.reconnect_policy.enabled
                        else "retry_exhausted"
                    )
                    self._connection_tracker.update("fatal", reason, attempts)
                    raise ConnectionFailure(reason)
                delay = self.reconnect_policy.delay(attempts)
                self._connection_tracker.update(
                    "reconnecting", "network", attempts, delay
                )
                if self._stop_event.wait(delay):
                    break
        finally:
            if self.connection_state not in {"fatal", "auth_required"}:
                self._connection_tracker.update("stopped", "stopped")
            self._run_lock.release()

    async def connect_mqtt(self) -> None:
        """Run MQTT off-loop and reap its worker when the coroutine is cancelled."""
        cancelled = threading.Event()
        claimed = threading.Event()
        worker = asyncio.create_task(
            asyncio.to_thread(self._run_listener, cancelled, claimed)
        )
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            cancelled.set()
            await finish_listener_worker(
                worker, self.disconnect_blocking if claimed.is_set() else None
            )
            raise

    def disconnect_blocking(self) -> None:
        self._stop_event.set()
        with self._client_lock:
            client = self.mqtt
        if client is not None:
            try:
                client.disconnect()
            except (OSError, ValueError):
                _safe_print("MQTT disconnect failed (details hidden).")
        if self.connection_state not in {"fatal", "auth_required"}:
            self._connection_tracker.update("stopped", "stopped")

    async def disconnect(self) -> None:
        await asyncio.to_thread(self.disconnect_blocking)
