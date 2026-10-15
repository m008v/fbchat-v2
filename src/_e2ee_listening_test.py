"""
fbchat-v2 :: tester.py
======================

Test driver cho `_listening_e2ee.py` (bridge Go subprocess).

Yêu cầu bắt buộc: build/cài Go E2EE bridge trước khi chạy. Script này fail
closed nếu E2EE không sẵn sàng và không fallback sang Python MQTT.

Cách dùng:
    1. Build bridge:
        git submodule update --init --recursive
        cd fbchat-v2/bridge-e2ee
        go mod download
        go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee.exe .

    2. Đặt cookie Facebook trong fbchat-v2/src/config.json (key "cookies")
       hoặc set env FBCHAT_COOKIE="c_user=...; xs=...; datr=...; fr=...;"

    3. Chạy:
        python src/_e2ee_listening_test.py

Bot này:
    - In ra mọi event nhận được từ bridge.
    - Nếu nhận "ping" E2EE thì trả bằng E2EE; nếu nhận từ group thường thì
      trả qua Go LightSpeed regular, không dùng Python MQTT.
    - Ctrl+C để thoát.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import asyncio
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Đảm bảo import được package src/
# ---------------------------------------------------------------------------
SRC = Path(__file__).resolve().parent
CONFIG_PATH = SRC / "config.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from _core._console import configure_utf8_console, safe_print  # noqa: E402
from _core._session import dataGetHome  # noqa: E402
from _messaging._listening_e2ee import (  # noqa: E402
    BridgeError,
    _redact_bridge_text,
    listeningE2EEEvent,
    _resolve_binary,
)

# ---------------------------------------------------------------------------
# Cookie loader
# ---------------------------------------------------------------------------


def load_cookie() -> str:
    cookie = os.getenv("FBCHAT_COOKIE", "").strip()
    if not cookie:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        cookie = str(config.get("cookies") or "").strip()
    if not cookie:
        raise ValueError(
            "Cookie Facebook không được cung cấp! Vui lòng set env "
            f"FBCHAT_COOKIE hoặc điền vào {CONFIG_PATH}."
        )
    return cookie


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def short(obj, n: int = 200) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "…"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    configure_utf8_console()
    safe_print(f"[{ts()}] tester.py bắt đầu")

    # 1. Kiểm tra binary tồn tại
    try:
        binary = _resolve_binary()
        safe_print(f"[{ts()}] bridge binary : {binary}")
    except FileNotFoundError as exc:
        sys.exit(str(exc))

    # 2. Lấy cookie + dataFB
    cookie = load_cookie()
    safe_print(f"[{ts()}] đang đăng nhập...")
    try:
        dataFB = asyncio.run(dataGetHome(cookie))
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"dataGetHome thất bại: {_redact_bridge_text(exc)}")

    fb_id = dataFB.get("FacebookID")
    safe_print(f"[{ts()}] đăng nhập thành công")

    # 3. Khởi tạo listener
    listener = listeningE2EEEvent(
        dataFB,
        log_level=os.getenv("FBCHAT_BRIDGE_LOG_LEVEL", "warn"),
        e2ee_memory_only=True,  # đổi False + device_path=... nếu muốn persist
        enable_e2ee=True,
        debug_errors=os.getenv("FBCHAT_DEBUG_ERRORS") == "1",
    )

    @listener.on_message
    def handler(evt: dict) -> None:
        etype = evt.get("type")
        data = evt.get("data") or {}
        safe_print(f"[{ts()}] <{etype}> {_redact_bridge_text(short(data))}")

        # Auto-reply "ping" -> "pong"
        text = (data.get("text") or "").strip().lower()
        if text != "ping":
            return

        sender_id = data.get("senderId")
        if str(sender_id) == str(fb_id):
            return  # bỏ qua tin của chính mình

        try:
            if etype == "e2eeMessage":
                listener.send_e2ee_message_blocking(
                    data["chatJid"],
                    "pong",
                    reply_to_id=data.get("id", ""),
                    reply_to_sender_jid=data.get("senderJid", ""),
                )
                safe_print(f"[{ts()}] -> đã gửi pong (E2EE)")
            elif etype == "message" and data.get("threadId"):
                # Đây vẫn là Go LightSpeed bridge; tuyệt đối không fallback sang
                # Python MQTT chỉ để bot group trông có vẻ đang chạy.
                listener.send_message_blocking(
                    int(data["threadId"]),
                    "pong",
                    reply_to_id=str(data.get("id") or ""),
                )
                safe_print(f"[{ts()}] -> đã gửi pong (Go LightSpeed regular)")
        except BridgeError as exc:
            safe_print(f"[{ts()}] gửi pong fail: {_redact_bridge_text(exc)}")

    # 4. Ctrl+C để thoát gọn
    def _sigint(_signum, _frame):
        safe_print(f"\n[{ts()}] nhận Ctrl+C, đang dừng...")
        listener.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)

    # 5. Blocking loop
    try:
        listener.connect_mqtt_blocking()
    except KeyboardInterrupt:
        listener.stop()
    except Exception as exc:  # noqa: BLE001
        safe_print(f"[{ts()}] lỗi nghiêm trọng: {_redact_bridge_text(exc)}")
        listener.stop()
        raise


if __name__ == "__main__":
    main()
