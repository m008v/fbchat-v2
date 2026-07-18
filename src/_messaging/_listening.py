from __future__ import annotations

import asyncio
import datetime
import json
import ssl
import threading
from queue import Empty, Full, Queue
from typing import Any
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

from _core._utils import generate_client_id, generate_session_id, json_minimal
from _features._thread import _all_thread_data

DEFAULT_MESSAGE_QUEUE_MAXSIZE = 1000
_RECONNECT_DELAY_SECONDS = 10


class listeningEvent:
    """Listener MQTT có queue giới hạn và API async không chặn event loop."""

    def __init__(
        self,
        dataFB: dict[str, Any],
        message_queue_maxsize: int = DEFAULT_MESSAGE_QUEUE_MAXSIZE,
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

    async def get_message(
        self, timeout: float | None = None
    ) -> dict[str, Any] | None:
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
        print(
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

        thread_key = metadata.get("threadKey") or {}
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
        attachments = delta.get("attachments") or []
        if attachments and isinstance(attachments[0], dict):
            attachment = attachments[0]
            body["attachments"]["id"] = attachment.get("fbid", 0)
            body["attachments"]["url"] = (
                attachment.get("mercury", {})
                .get("blob_attachment", {})
                .get("preview", {})
                .get("uri")
            )
        return body

    @staticmethod
    def _coerce_seq_id(value: Any, source: str = "seq_id") -> int | None:
        try:
            seq_id = int(str(value).strip())
        except (TypeError, ValueError):
            print(f"[{datetime.datetime.now()}] Bỏ qua {source} không hợp lệ: {value}")
            return None
        if seq_id < 0:
            print(f"[{datetime.datetime.now()}] Bỏ qua {source} âm: {seq_id}")
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
            print(
                f"[{datetime.datetime.now()}] Bỏ qua {source} cũ: {seq_id} < {previous}"
            )
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
        try:
            self._apply_thread_data(_all_thread_data.func(self.dataFB), previous)
        except Exception as error:  # lỗi mạng cần giữ sequence cũ để phục hồi
            self.lastSeqID = previous
            print(f"[{datetime.datetime.now()}] Không thể làm mới last_seq_id: {error}")
        return self.lastSeqID

    async def get_last_seq_id(self) -> int | None:
        previous = self.lastSeqID
        try:
            result = await _all_thread_data.func(self.dataFB)
            self._apply_thread_data(result, previous)
        except Exception as error:  # lỗi mạng cần giữ sequence cũ để phục hồi
            self.lastSeqID = previous
            print(f"[{datetime.datetime.now()}] Không thể làm mới last_seq_id: {error}")
        return self.lastSeqID

    def _publish_pending_queue(self, client: mqtt.Client) -> None:
        if self.syncToken is None or self.lastSeqID is None:
            if self.syncToken is not None:
                self.syncToken = None
            self.get_last_seq_id()
        if self.lastSeqID is None:
            print(
                "Không có last_seq_id; hãy làm mới cookie Facebook rồi khởi động lại."
            )
            client.disconnect()
            return

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
        client.publish(topic, json_minimal(queue), qos=1, retain=False)

    def _on_connect(
        self, client: mqtt.Client, userdata: Any, flags: Any, rc: int
    ) -> None:
        if rc != 0:
            print(f"Kết nối MQTT thất bại với mã {rc}.")
            return
        self._publish_pending_queue(client)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: Any) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            print("Không thể giải mã dữ liệu MQTT trên /t_ms.")
            return

        for delta in payload.get("deltas") or []:
            body = self._body_from_delta(delta)
            if body is not None:
                self._publish_body_results(body)

        if "syncToken" in payload and "firstDeltaSeqId" in payload:
            self.syncToken = payload["syncToken"]
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
            self.get_last_seq_id()
            if self.lastSeqID is not None:
                self._publish_pending_queue(client)
                return

        print(f"MQTT lỗi {error}; yêu cầu tạo kết nối mới.")
        self.retry_count = 0
        self._reconnect_requested.set()
        client.disconnect()

    @staticmethod
    def _on_disconnect(client: mqtt.Client, userdata: Any, rc: int) -> None:
        print(f"MQTT đã ngắt kết nối với mã {rc}.")

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
        client = mqtt.Client(
            client_id="mqttwsclient",
            clean_session=True,
            protocol=mqtt.MQTTv31,
            transport="websockets",
        )
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
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        return client

    def connect_mqtt_blocking(self) -> None:
        """Chạy listener blocking; reconnect bằng vòng lặp, không đệ quy callback."""
        self._stop_event.clear()
        while not self._stop_event.is_set():
            self._reconnect_requested.clear()
            self.mqtt = self._build_client()
            self.mqtt.connect("edge-chat.facebook.com", port=443, keepalive=10)
            self.mqtt.loop_forever(retry_first_connection=True)
            if not self._reconnect_requested.is_set() or self._stop_event.is_set():
                break
            self._stop_event.wait(_RECONNECT_DELAY_SECONDS)

    async def connect_mqtt(self) -> None:
        """Chạy MQTT blocking trong worker thread dành riêng."""
        await asyncio.to_thread(self.connect_mqtt_blocking)

    def disconnect_blocking(self) -> None:
        self._stop_event.set()
        if self.mqtt is not None:
            self.mqtt.disconnect()

    async def disconnect(self) -> None:
        self.disconnect()
