"""
fbchat-v2 :: _send_e2ee.py
==========================

Gửi tin nhắn Facebook Messenger có **mã hoá đầu-cuối E2EE** (Secret
Conversations / Labyrinth) thông qua binary Go ``fbchat-bridge-e2ee``.

Module này dùng **chung** lớp ``_BridgeProcess`` và logic discovery binary
của ``_listening_e2ee.py`` — khuyến nghị **tái sử dụng bridge của listener**
thay vì spawn thêm process (mỗi process phải pair lại với Meta).

Hai chế độ dùng:

1. **Reuse** (khuyến nghị) — nhanh, không phải pair lại::

       from _messaging._listening_e2ee import listeningE2EEEvent
       from _messaging._send_e2ee import api as E2EESender

       listener = listeningE2EEEvent(dataFB)
       threading.Thread(target=listener.connect_mqtt, daemon=True).start()
       # ... đợi event "e2eeConnected" ...

       sender = E2EESender(listener=listener)
         sender.send(chat_jid="100012345678@msgr", contentSend="pong")
         sender.send_to_user("100012345678", "chủ động nhắn bằng Facebook ID")

2. **Standalone** — tự spawn bridge, tự ``connect()`` + ``connect_e2ee()``::

       sender = E2EESender(dataFB=dataFB, log_level="warn")
       sender.connect()           # blocking pairing handshake
         sender.send(chat_jid="100012345678", contentSend="hello")  # auto → 100012345678@msgr
       sender.close()

API ``send(...)`` mô phỏng style của ``_send.py`` — trả về dict với
``{"success": 1, ...}`` hoặc ``{"error": 1, ...}``.

Tham khảo: meta-messenger.js · ``Client.sendE2EEMessage()``.

Author: MinhHuyDev
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Optional

from _messaging._listening_e2ee import (
    BridgeError,
    _BridgeProcess,
    _resolve_binary,
    parse_cookie_string,
    listeningE2EEEvent,
    _REQUIRED_COOKIES,
)


E2EE_MESSENGER_SERVER = "msgr"


def _resolve_device_path(device_path: str | None) -> str | None:
    if not device_path:
        return None
    path = Path(device_path).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def normalize_chat_jid(target: str | int, *, default_server: str = E2EE_MESSENGER_SERVER) -> str:
    """Chuẩn hoá Facebook user ID hoặc JID thành Messenger E2EE chat JID.

    Messenger E2EE events trả về ``chatJid`` dạng ``<facebook_id>@msgr``.
    Khi chủ động gửi, caller thường chỉ có Facebook numeric ID; helper này
    chuyển ``"100012345678"`` thành ``"100012345678@msgr"``. Nếu caller đã
    truyền JID đầy đủ như ``"100012345678@msgr"`` thì giữ nguyên.
    """
    target_str = str(target or "").strip()
    if not target_str:
        raise ValueError("Thiếu chat_jid hoặc Facebook user ID để gửi E2EE.")

    if target_str.lower().startswith(("fbid:", "facebook:")):
        target_str = target_str.split(":", 1)[1].strip()

    if "@" in target_str:
        return target_str

    if not target_str.isdigit():
        raise ValueError(
            "chat_jid phải là JID đầy đủ (`<id>@msgr`) hoặc Facebook numeric ID. "
            f"Giá trị nhận được: {target!r}"
        )

    server = (default_server or E2EE_MESSENGER_SERVER).strip().lstrip("@")
    return f"{target_str}@{server}"


def chat_jid_from_user_id(user_id: str | int) -> str:
    """Alias rõ nghĩa cho ``normalize_chat_jid(user_id)``."""
    return normalize_chat_jid(user_id)


# ---------------------------------------------------------------------------
# Public sender
# ---------------------------------------------------------------------------

class api:
    """Sender E2EE — tương tự ``_send.api`` nhưng cho Secret Conversations.

    Khởi tạo:
        - ``api(listener=...)``  → reuse bridge của ``listeningE2EEEvent``
          (khuyến nghị; không tốn pairing).
        - ``api(dataFB=..., **opts)``  → spawn bridge riêng. Phải gọi
          ``connect()`` trước khi ``send()``.

    Ví dụ::

        sender = api(listener=listener)
        result = sender.send(
            chat_jid="100012345678",
            contentSend="pong",
            replyMessage="3EB0...",                      # tuỳ chọn
            replySenderJid="100087...@msgr",             # tuỳ chọn (nếu reply)
        )
        sender.send_to_user("100012345678", "chủ động nhắn")
        # → {"success": 1, "payload": {"messageID": "...", "timestamp": ...}}
        # hoặc {"error": 1, "payload": {"error-decription": "...", "error-code": "..."}}
    """

    # ------------------------------------------------------------------
    def __init__(self,
                 listener: Optional[listeningE2EEEvent] = None,
                 dataFB: Optional[dict] = None,
                 *,
                 log_level: str = "none",
                 device_path: Optional[str] = None,
                 e2ee_memory_only: bool = True,
                 binary_path: Optional[str] = None) -> None:

        if listener is None and dataFB is None:
            raise ValueError(
                "Phải truyền `listener=` (reuse) HOẶC `dataFB=` (standalone)."
            )
        if listener is not None and dataFB is not None:
            raise ValueError(
                "Truyền `listener=` HOẶC `dataFB=`, không được cả hai."
            )

        self._listener = listener
        self._owns_bridge = listener is None     # standalone → ta tự đóng

        # Standalone-only state
        self.dataFB = dataFB
        self.log_level = log_level
        self.device_path = device_path
        self.e2ee_memory_only = e2ee_memory_only
        self._binary_path_override = binary_path
        self._bridge: Optional[_BridgeProcess] = None
        self._connected = False

        # Compat fields giống _send.api
        self.results: dict[str, Any] = {}
        self.chat_jid = None
        self.content = None
        self.replyToId = None
        self.replyToSenderJid = None

    # ------------------------------------------------------------------
    @property
    def bridge(self) -> _BridgeProcess:
        """Lấy bridge đang dùng (của listener hoặc của chính sender)."""
        if self._listener is not None:
            br = self._listener._bridge
            if br is None:
                raise RuntimeError(
                    "Listener chưa connect — gọi listener.connect_mqtt() "
                    "(thường trong daemon thread) trước khi send."
                )
            return br
        if self._bridge is None:
            raise RuntimeError(
                "Standalone sender chưa connect — gọi sender.connect() trước."
            )
        return self._bridge

    # ------------------------------------------------------------------
    def connect(self, *, enable_e2ee: bool = True, timeout: float = 120.0) -> dict[str, Any]:
        """Standalone mode: spawn bridge + pair với Meta."""
        if self._listener is not None:
            raise RuntimeError("connect() chỉ dùng cho standalone mode.")
        if self._connected:
            return {"already": True}

        binary = (
            Path(self._binary_path_override)
            if self._binary_path_override else _resolve_binary()
        )
        self._bridge = _BridgeProcess(binary)

        cks = parse_cookie_string(self.dataFB["cookieFacebook"])
        missing = [c for c in _REQUIRED_COOKIES if c not in cks]
        if missing:
            self._bridge.close()
            self._bridge = None
            raise ValueError(f"Thiếu cookie bắt buộc cho E2EE: {missing}")
        keep = {"c_user", "xs", "datr", "fr", "sb", "wd", "presence"}
        cookies = {k: v for k, v in cks.items() if k in keep}

        cfg: dict[str, Any] = {
            "cookies": cookies,
            "platform": "facebook",
            "logLevel": self.log_level,
            "e2eeMemoryOnly": self.e2ee_memory_only,
        }
        device_path = _resolve_device_path(self.device_path)
        if device_path:
            cfg["devicePath"] = device_path

        self._bridge.call("newClient", cfg)
        info = self._bridge.call("connect", timeout=timeout)
        if enable_e2ee:
            self._bridge.call("connectE2EE", timeout=timeout)
        self._connected = True
        print(f"[{datetime.datetime.now()}] E2EE sender ready "
              f"(user={(info.get('user') or {}).get('id')})")
        return info

    # ------------------------------------------------------------------
    def send(self, chat_jid: str | int, contentSend: str,
             replyMessage: str = "",
             replySenderJid: str | int = "",
             timeout: float = 180.0) -> dict[str, Any]:
        """Gửi 1 tin nhắn E2EE text.

        :param chat_jid: JID đích, ví dụ Messenger JID
                 ``"100012345678@msgr"``.
                         Có thể truyền thẳng Facebook numeric ID
                         ``"100012345678"``; module sẽ tự đổi thành
                         ``"100012345678@msgr"``.
        :param contentSend: Nội dung text.
        :param replyMessage: ID message cần reply (tuỳ chọn).
        :param replySenderJid: JID người gửi message gốc (bắt buộc nếu reply).
        :return: Dict với cùng schema của ``_send.api.send``::

                    {"success": 1,
                     "payload": {"messageID": str, "timestamp": int}}

                 hoặc::

                    {"error": 1,
                     "payload": {"error-decription": str, "error-code": str}}
        """
        try:
            normalized_chat_jid = normalize_chat_jid(chat_jid)
            normalized_reply_sender_jid = (
                normalize_chat_jid(replySenderJid) if replySenderJid else ""
            )
        except ValueError as exc:
            self.results = {
                "error": 1,
                "payload": {
                    "error-decription": str(exc),
                    "error-code": "invalid_chat_jid",
                },
            }
            return self.results

        # Lưu vào instance để debug/log như _send.api
        self.chat_jid = normalized_chat_jid
        self.content = str(contentSend)
        self.replyToId = replyMessage or ""
        self.replyToSenderJid = normalized_reply_sender_jid

        try:
            data = self.bridge.call("sendE2EEMessage", {
                "chatJid": self.chat_jid,
                "text": self.content,
                "replyToId": self.replyToId,
                "replyToSenderJid": self.replyToSenderJid,
            }, timeout=timeout)
        except BridgeError as exc:
            self.results = {
                "error": 1,
                "payload": {
                    "error-decription": str(exc),
                    "error-code": "bridge_error",
                },
            }
            return self.results
        except RuntimeError as exc:
            self.results = {
                "error": 1,
                "payload": {
                    "error-decription": str(exc),
                    "error-code": "not_connected",
                },
            }
            return self.results

        # Bridge trả về SendMessageResult: {messageId, timestampMs, ...}
        self.results = {
            "success": 1,
            "payload": {
                "messageID": data.get("messageId") or data.get("id"),
                "timestamp": data.get("timestampMs") or data.get("timestamp") or 0,
            },
        }
        return self.results

    # ------------------------------------------------------------------
    def send_to_user(self, user_id: str | int, contentSend: str,
                     replyMessage: str = "",
                     replySenderJid: str | int = "",
                     timeout: float = 180.0) -> dict[str, Any]:
        """Gửi chủ động tới Facebook numeric ID.

        ``user_id="100012345678"`` sẽ được chuyển thành
        ``chat_jid="100012345678@msgr"`` trước khi gọi bridge.
        """
        return self.send(
            chat_jid=chat_jid_from_user_id(user_id),
            contentSend=contentSend,
            replyMessage=replyMessage,
            replySenderJid=replySenderJid,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    def reply(self, evt_data: dict, contentSend: str) -> dict[str, Any]:
        """Helper: reply trực tiếp từ ``data`` của event ``e2eeMessage``.

        ::

            @listener.on_message
            def handler(evt):
                if evt["type"] == "e2eeMessage" and evt["data"]["text"] == "ping":
                    sender.reply(evt["data"], "pong")
        """
        return self.send(
            chat_jid=evt_data.get("chatJid", ""),
            contentSend=contentSend,
            replyMessage=evt_data.get("id", ""),
            replySenderJid=evt_data.get("senderJid", ""),
        )

    # ------------------------------------------------------------------
    def close(self) -> None:
        """Đóng bridge nếu sender tự sở hữu (standalone mode)."""
        if self._owns_bridge and self._bridge is not None:
            self._bridge.close()
            self._bridge = None
            self._connected = False

    def __enter__(self) -> "api":
        if self._owns_bridge and not self._connected:
            self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
