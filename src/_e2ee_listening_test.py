"""
fbchat-v2 :: tester.py
======================

Test driver cho `_listening_e2ee.py` (bridge Go subprocess).

Cách dùng:
    1. Build bridge:
        cd fbchat-v2/bridge-e2ee
        git clone https://github.com/mautrix/meta.git ./meta
        go mod tidy
        go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee.exe .

    2. Đặt cookie Facebook trong fbchat-v2/src/config.json (key "cookies")
       hoặc set env FBCHAT_COOKIE="c_user=...; xs=...; datr=...; fr=...;"

    3. Chạy:
        python tester.py

Bot này:
    - In ra mọi event nhận được từ bridge.
    - Nếu nhận tin "ping" thì trả "pong" (regular hoặc E2EE tuỳ nguồn).
    - Ctrl+C để thoát.
"""

from __future__ import annotations

import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Đảm bảo import được package src/
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from _core._session import dataGetHome  # noqa: E402
from _messaging._listening_e2ee import (  # noqa: E402
    BridgeError,
    listeningE2EEEvent,
    _resolve_binary,
)


# ---------------------------------------------------------------------------
# Cookie loader
# ---------------------------------------------------------------------------

def load_cookie() -> str:
    _ = json.loads(open("config.json", "r", encoding="utf-8").read())
    cookie = os.getenv("FBCHAT_COOKIE") or _["cookies"]
    if not cookie:
        raise ValueError("Cookie Facebook không được cung cấp! Vui lòng set env FBCHAT_COOKIE hoặc điền vào config.json")
    return cookie;


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
    print(f"[{ts()}] tester.py bắt đầu")

    # 1. Kiểm tra binary tồn tại
    try:
        binary = _resolve_binary()
        print(f"[{ts()}] bridge binary : {binary}")
    except FileNotFoundError as exc:
        sys.exit(str(exc))

    # 2. Lấy cookie + dataFB
    cookie = load_cookie()
    print(f"[{ts()}] đang đăng nhập...")
    try:
        dataFB = dataGetHome(cookie)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"dataGetHome thất bại: {exc}")

    fb_id = dataFB.get("FacebookID")
    print(f"[{ts()}] FacebookID = {fb_id}")

    # 3. Khởi tạo listener
    listener = listeningE2EEEvent(
        dataFB,
        log_level="warn",
        e2ee_memory_only=True,   # đổi False + device_path=... nếu muốn persist
        enable_e2ee=True,
    )

    @listener.on_message
    def handler(evt: dict) -> None:
        etype = evt.get("type")
        data = evt.get("data") or {}
        print(f"[{ts()}] <{etype}> {short(data)}")

        # Auto-reply "ping" -> "pong"
        text = (data.get("text") or "").strip().lower()
        if text != "ping":
            return

        sender_id = data.get("senderId")
        if str(sender_id) == str(fb_id):
            return  # bỏ qua tin của chính mình

        try:
            if etype == "e2eeMessage":
                listener.send_e2ee_message(
                    data["chatJid"], "pong",
                    reply_to_id=data.get("id", ""),
                    reply_to_sender_jid=data.get("senderJid", ""),
                )
                print(f"[{ts()}] -> đã gửi pong (E2EE)")
            elif etype == "message":
                listener.send_message(
                    int(data["threadId"]), "pong",
                    reply_to_id=data.get("id", ""),
                )
                print(f"[{ts()}] -> đã gửi pong (regular)")
        except BridgeError as exc:
            print(f"[{ts()}] gửi pong fail: {exc}")

    # 4. Ctrl+C để thoát gọn
    def _sigint(_signum, _frame):
        print(f"\n[{ts()}] nhận Ctrl+C, đang dừng...")
        listener.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)

    # 5. Blocking loop
    try:
        listener.connect_mqtt()
    except KeyboardInterrupt:
        listener.stop()
    except Exception as exc:  # noqa: BLE001
        print(f"[{ts()}] lỗi nghiêm trọng: {exc}")
        listener.stop()
        raise


if __name__ == "__main__":
    main()
