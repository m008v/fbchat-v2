"""
fbchat-v2 — Minimal bot
=================================================

Bot này minh hoạ cách kết hợp 3 tầng `_core` / `_features` / `_messaging`
để tạo một con bot chat đơn giản phản hồi lệnh trong nhóm hoặc DM.

This bot demonstrates how to combine the three layers
(`_core` / `_features` / `_messaging`) into a small command-driven bot.

Lệnh hỗ trợ / Supported commands:
    /ping              -> trả lời "pong" (latency check)
    /help              -> hiển thị danh sách lệnh
    /id                -> in threadID + userID của người gửi
    /echo <text>       -> lặp lại nội dung
    /search <keyword>  -> tìm người dùng Facebook
    /unsend            -> thu hồi tin nhắn cuối của bot trong thread

Cấu hình / Configuration:
    Tạo file `config.json` cùng thư mục với main.py:
        {
            "cookies": "c_user=...; xs=...; fr=...; datr=...;",
            "prefix":  "/",
            "admins":  ["1000xxxxxxxxxx"]
        }

@MinhHuyDev (Claude Opus 4.7)
"""

from __future__ import annotations

import json
import os
import sys
import time
import threading
import traceback
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Bảo đảm `src/` nằm trong sys.path khi chạy file này trực tiếp
# Ensure `src/` is on sys.path when running this file directly
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _core._session import dataGetHome
from _features._facebook import _search
from _messaging._send import api as SendAPI
from _messaging._unsend import func as unsend_message
from _messaging._listening import listeningEvent


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

CONFIG_PATH = HERE / "config.json"


def load_config() -> dict:
    """Đọc config.json. Tạo template nếu chưa tồn tại."""
    if not CONFIG_PATH.exists():
        template = {
            "cookies": "PASTE_YOUR_FACEBOOK_COOKIE_HERE",
            "prefix": "/",
            "admins": [],
        }
        CONFIG_PATH.write_text(
            json.dumps(template, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[config] Đã tạo template tại {CONFIG_PATH}. "
              "Hãy điền 'cookies' rồi chạy lại.")
        sys.exit(1)

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    if not cfg.get("cookies") or "PASTE_YOUR" in cfg["cookies"]:
        print("[config] Bạn chưa điền cookie Facebook trong config.json.")
        sys.exit(1)

    cfg.setdefault("prefix", "/")
    cfg.setdefault("admins", [])
    return cfg


def log(tag: str, msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] [{tag}] {msg}")


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

class SimpleBot:
    """Bot tối giản — poll `listener.bodyResults` và phản hồi theo lệnh."""

    def __init__(self, dataFB: dict, prefix: str = "/", admins: list | None = None):
        self.dataFB = dataFB
        self.prefix = prefix
        self.admins = set(map(str, admins or []))

        self.sender = SendAPI()
        self.listener = listeningEvent(dataFB)

        # Theo dõi messageID đã xử lý → tránh phản hồi 2 lần cùng 1 tin
        self._last_seen_message_id: str | None = None
        # Lưu messageID cuối cùng bot đã gửi vào mỗi thread (cho /unsend)
        self._last_bot_message: dict[str, str] = {}

        # Map prefix-less command -> handler
        self._handlers = {
            "ping":   self._cmd_ping,
            "help":   self._cmd_help,
            "id":     self._cmd_id,
            "echo":   self._cmd_echo,
            "search": self._cmd_search,
            "unsend": self._cmd_unsend,
        }

    # -- public ---------------------------------------------------------------

    def run(self) -> None:
        """Khởi động listener trong thread riêng và poll sự kiện."""
        log("bot", f"Đăng nhập với UID = {self.dataFB.get('FacebookID')}")
        self.listener.get_last_seq_id()

        # `connect_mqtt()` là blocking (loop_forever) → chạy trong thread daemon
        t = threading.Thread(
            target=self.listener.connect_mqtt,
            name="fbchat-listener",
            daemon=True,
        )
        t.start()
        log("bot", "Listener đã khởi động. Nhấn Ctrl+C để thoát.")

        try:
            while True:
                self._poll_once()
                time.sleep(0.3)
        except KeyboardInterrupt:
            log("bot", "Đã dừng theo yêu cầu người dùng.")

    # -- internal -------------------------------------------------------------

    def _poll_once(self) -> None:
        """Quét bodyResults; nếu có tin mới chưa xử lý → dispatch."""
        snap = self.listener.bodyResults
        mid = snap.get("messageID")
        body = snap.get("body")

        if not mid or mid == self._last_seen_message_id:
            return
        self._last_seen_message_id = mid

        # Bỏ qua tin do chính bot gửi
        sender_id = str(snap.get("userID") or "")
        if sender_id == str(self.dataFB.get("FacebookID")):
            return

        if not body:
            return

        log("recv", f"[{snap.get('type')}] {sender_id}@{snap.get('replyToID')}: {body!r}")

        if not body.startswith(self.prefix):
            return

        # Tách lệnh
        without_prefix = body[len(self.prefix):].strip()
        if not without_prefix:
            return
        parts = without_prefix.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        handler = self._handlers.get(cmd)
        if handler is None:
            return  # im lặng cho lệnh không biết

        try:
            handler(snap, arg)
        except Exception as exc:  # noqa: BLE001 - tránh crash listener thread
            log("err", f"Lỗi khi xử lý lệnh /{cmd}: {exc}")
            traceback.print_exc()

    # -- send wrapper ---------------------------------------------------------

    def _reply(self, snap: dict, content: str) -> None:
        thread_id = snap["replyToID"]
        type_chat = "user" if snap.get("type") == "user" else None

        result = self.sender.send(
            self.dataFB,
            content,
            thread_id,
            typeChat=type_chat,
            replyMessage=True,
            messageID=snap.get("messageID"),
        )

        if isinstance(result, dict) and result.get("success") == 1:
            try:
                self._last_bot_message[str(thread_id)] = (
                    result["payload"]["messageID"]
                )
            except (KeyError, TypeError):
                pass
            log("send", f"-> {thread_id}: {content!r}")
        else:
            log("send", f"FAIL -> {thread_id}: {result}")

    # -- commands -------------------------------------------------------------

    def _cmd_ping(self, snap: dict, arg: str) -> None:
        sent_ts = int(snap.get("timestamp") or 0)
        if sent_ts:
            latency_ms = max(0, int(time.time() * 1000) - sent_ts)
            self._reply(snap, f"🏓 pong! ({latency_ms} ms)")
        else:
            self._reply(snap, "🏓 pong!")

    def _cmd_help(self, snap: dict, arg: str) -> None:
        p = self.prefix
        self._reply(snap, (
            "📖 Lệnh hỗ trợ:\n"
            f"• {p}ping            — kiểm tra độ trễ\n"
            f"• {p}help            — hiển thị trợ giúp\n"
            f"• {p}id              — xem threadID + userID\n"
            f"• {p}echo <text>     — lặp lại nội dung\n"
            f"• {p}search <từ>     — tìm user Facebook\n"
            f"• {p}unsend          — thu hồi tin nhắn cuối của bot"
        ))

    def _cmd_id(self, snap: dict, arg: str) -> None:
        self._reply(snap, (
            f"🆔 type      : {snap.get('type')}\n"
            f"   threadID  : {snap.get('replyToID')}\n"
            f"   userID    : {snap.get('userID')}\n"
            f"   messageID : {snap.get('messageID')}"
        ))

    def _cmd_echo(self, snap: dict, arg: str) -> None:
        if not arg:
            self._reply(snap, f"Cách dùng: {self.prefix}echo <nội dung>")
            return
        self._reply(snap, arg)

    def _cmd_search(self, snap: dict, arg: str) -> None:
        if not arg:
            self._reply(snap, f"Cách dùng: {self.prefix}search <từ khoá>")
            return
        try:
            res = _search.func(self.dataFB, arg)
        except Exception as exc:  # noqa: BLE001
            self._reply(snap, f"❌ Lỗi tìm kiếm: {exc}")
            return

        users = res.get("searchResultsDict") if isinstance(res, dict) else None
        if not users:
            self._reply(snap, f"🔍 Không tìm thấy kết quả nào cho: {arg}")
            return

        lines = [f"🔍 Kết quả cho “{arg}”:"]
        for i, u in enumerate(users[:5], 1):
            lines.append(f"{i}. {u.get('name')} — {u.get('id')}")
        self._reply(snap, "\n".join(lines))

    def _cmd_unsend(self, snap: dict, arg: str) -> None:
        # Chỉ admin mới được dùng nếu có cấu hình admins
        sender_id = str(snap.get("userID") or "")
        if self.admins and sender_id not in self.admins:
            self._reply(snap, "⛔ Chỉ admin mới được dùng lệnh này.")
            return

        thread_id = str(snap["replyToID"])
        target = self._last_bot_message.get(thread_id)
        if not target:
            self._reply(snap, "ℹ️ Chưa có tin nào để thu hồi trong thread này.")
            return

        result = unsend_message(target, self.dataFB)
        log("unsend", f"{target} -> {result}")
        # Sau khi thu hồi → quên ID đó
        self._last_bot_message.pop(thread_id, None)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    cfg = load_config()

    log("boot", "Đang khởi tạo dataFB từ cookie…")
    dataFB = dataGetHome(cfg["cookies"])

    if not dataFB.get("FacebookID"):
        log("boot", "❌ Không lấy được FacebookID — cookie có thể đã hết hạn.")
        sys.exit(1)

    bot = SimpleBot(
        dataFB,
        prefix=cfg["prefix"],
        admins=cfg["admins"],
    )
    bot.run()


if __name__ == "__main__":
    main()
