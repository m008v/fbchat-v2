from __future__ import annotations

import json
import ssl
import asyncio
from threading import Event
from typing import Any
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

from _core._utils import generate_session_id, generate_client_id, gen_threading_id, json_minimal

APP_ID = "2220391788200892"
LS_TOPIC = "/ls_req"
MQTT_HOST = "edge-chat.facebook.com"
EDIT_MESSAGE_VERSION_ID = "6903494529735864"
_DEFAULT_TIMEOUT = 20
_MISSING = object()


def _json(data: Any) -> str:
     return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _rc_success(rc: Any) -> bool:
     try:
          return int(rc) == 0
     except (TypeError, ValueError):
          return str(rc).lower() in ("0", "success", "normal disconnection")


def _error_response(message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
     return {
          "error": 1,
          "messages": message,
          "payload": payload or {},
     }


def _build_ls_context(tasks: list[dict[str, Any]], request_id: int = 1, app_id: str = APP_ID, version_id: str = EDIT_MESSAGE_VERSION_ID, data_trace_id: Any = _MISSING) -> dict[str, Any]:
     payload = {
          "epoch_id": int(gen_threading_id()),
          "tasks": tasks,
          "version_id": str(version_id),
     }
     if data_trace_id is not _MISSING:
          payload["data_trace_id"] = data_trace_id

     return {
          "app_id": str(app_id),
          "payload": _json(payload),
          "request_id": int(request_id),
          "type": 3,
     }


def _make_mqtt_client(dataFB: dict[str, Any]) -> mqtt.Client:
     session_id = generate_session_id()
     chat_on = json_minimal(True)
     user = {
          "u": str(dataFB["FacebookID"]),
          "s": session_id,
          "chat_on": chat_on,
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

     host = f"wss://{MQTT_HOST}/chat?region=eag&sid={session_id}"
     parsed_host = urlparse(host)
     client = mqtt.Client(
          client_id="mqttwsclient",
          clean_session=True,
          protocol=mqtt.MQTTv31,
          transport="websockets",
     )
     client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
     client.tls_insecure_set(False)
     client.username_pw_set(username=json_minimal(user))
     client.ws_set_options(
          path=f"{parsed_host.path}?{parsed_host.query}",
          headers={
               "Cookie": dataFB["cookieFacebook"],
               "Origin": "https://www.facebook.com",
               "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0 Safari/537.36",
               "Referer": "https://www.facebook.com/",
               "Host": MQTT_HOST,
          },
     )
     return client


def _publish_ls_requests(dataFB: dict[str, Any], contexts: dict[str, Any] | list[dict[str, Any]], timeout: int = _DEFAULT_TIMEOUT) -> dict[str, Any]:
     if isinstance(contexts, dict):
          contexts = [contexts]
     if not contexts:
          return _error_response("No LS request context to publish.")

     connected = Event()
     published = Event()
     state = {
          "published": 0,
          "errors": [],
     }
     client = _make_mqtt_client(dataFB)

     def on_connect(client: mqtt.Client, userdata: Any, flags: Any, rc: Any, properties: Any = None) -> None:
          if not _rc_success(rc):
               state["errors"].append(f"MQTT connect failed: {rc}")
               connected.set()
               published.set()
               return

          connected.set()
          for context in contexts:
               info = client.publish(LS_TOPIC, _json(context), qos=1, retain=False)
               if getattr(info, "rc", 0) != mqtt.MQTT_ERR_SUCCESS:
                    state["errors"].append(f"MQTT publish failed: rc={getattr(info, 'rc', None)}")
          if state["errors"]:
               published.set()

     def on_publish(client: mqtt.Client, userdata: Any, mid: int, reason_code: Any = None, properties: Any = None) -> None:
          state["published"] += 1
          if state["published"] >= len(contexts):
               published.set()

     def on_disconnect(client: mqtt.Client, userdata: Any, rc: Any, *args: Any) -> None:
          reason = args[0] if args else rc
          if not _rc_success(reason) and not published.is_set():
               state["errors"].append(f"MQTT disconnected before publish: {reason}")
               connected.set()
               published.set()

     client.on_connect = on_connect
     client.on_publish = on_publish
     client.on_disconnect = on_disconnect

     try:
          client.connect(MQTT_HOST, port=443, keepalive=10)
          client.loop_start()

          if not connected.wait(timeout):
               return _error_response("MQTT connect timed out.", {"timeout": timeout})
          if state["errors"]:
               return _error_response("MQTT publish failed.", {"errors": state["errors"]})
          if not published.wait(timeout):
               return _error_response(
                    "MQTT LS publish timed out.",
                    {"timeout": timeout, "published": state["published"], "expected": len(contexts)},
               )
          if state["errors"]:
               return _error_response("MQTT publish failed.", {"errors": state["errors"]})

          return {
               "success": 1,
               "messages": "Đã publish LS task thành công.",
               "payload": {
                    "published": state["published"],
                    "expected": len(contexts),
               },
          }
     except Exception as exc:
          return _error_response("MQTT request failed.", {"exception": str(exc)})
     finally:
          try:
               client.disconnect()
          except Exception:
               pass
          try:
               client.loop_stop()
          except Exception:
               pass


def _build_edit_context(messageID: str, newText: str) -> dict[str, Any]:
     queryPayload = {
          "message_id": str(messageID),
          "text": str(newText),
     }
     query = {
          "failure_count": None,
          "label": "742",
          "payload": _json(queryPayload),
          "queue_name": "edit_message",
          "task_id": 1,
     }
     return _build_ls_context([query], request_id=1, version_id=EDIT_MESSAGE_VERSION_ID, data_trace_id=None)


def editMessage(dataFB: dict[str, Any], messageID: str, newText: str, timeout: int = _DEFAULT_TIMEOUT) -> dict[str, Any]:
     if not messageID:
          return _error_response("messageID is required.")
     if newText is None or str(newText) == "":
          return _error_response("newText is required.")

     context = _build_edit_context(messageID, newText)
     published = _publish_ls_requests(dataFB, context, timeout=timeout)
     if published.get("error"):
          return published

     return {
          "success": 1,
          "messages": "Gửi yêu cầu sửa tin nhắn thành công.",
          "data": {
               "messageID": str(messageID),
               "text": str(newText),
               "published": published.get("payload"),
          },
     }


def func(dataFB: dict[str, Any], messageID: str, newText: str, timeout: int = _DEFAULT_TIMEOUT) -> dict[str, Any]:
     return editMessage(dataFB, messageID, newText, timeout=timeout)


async def editMessage_async(dataFB: dict[str, Any], messageID: str, newText: str, timeout: int = _DEFAULT_TIMEOUT) -> dict[str, Any]:
     return await asyncio.to_thread(editMessage, dataFB, messageID, newText, timeout)


async def func_async(dataFB: dict[str, Any], messageID: str, newText: str, timeout: int = _DEFAULT_TIMEOUT) -> dict[str, Any]:
     return await editMessage_async(dataFB, messageID, newText, timeout=timeout)


""" Hướng dẫn sử dụng (Tutorial)

* Dữ liệu yêu cầu (args):

     - dataFB: lấy từ _core._session.dataGetHome(setCookies)
     - messageID: ID tin nhắn cần sửa (thường chỉ sửa được tin do chính tài khoản gửi)
     - newText: nội dung mới

* Ví dụ:

     from _core._session import dataGetHome
     from _messaging import _editMessage

     dataFB = dataGetHome("<cookie Facebook>")
     print(_editMessage.editMessage(dataFB, "mid.$...", "Nội dung đã sửa"))

* Kết quả trả về:

     - {"success": 1, "messages": "...", "data": {...}} khi publish LS task thành công
     - {"error": 1, "messages": "...", "payload": {...}} khi lỗi MQTT / thiếu dữ liệu

* Ghi chú:

     - Endpoint này dùng MQTT LS task queue_name="edit_message".
     - Facebook không trả response GraphQL trực tiếp; success ở đây nghĩa là task đã được publish lên /ls_req.
"""
