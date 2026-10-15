"""
fbchat-v2 :: _e2ee_send_test.py
================================

Test driver cho `_messaging/_send_e2ee.py`.

Yêu cầu bắt buộc: build/cài Go E2EE bridge. Script fail closed nếu E2EE không
sẵn sàng và không fallback sang Python MQTT.

Cách dùng nhanh:
    # Chạy interactive: script sẽ hỏi UID/JID và nội dung cần gửi
    python src/_e2ee_send_test.py

    # Chỉ test normalize Facebook ID -> Messenger E2EE JID, không gửi tin
    python src/_e2ee_send_test.py --dry-run

    # Gửi thật bằng Facebook numeric ID
    python src/_e2ee_send_test.py 100012345678 "hello E2EE"

    # Gửi thật bằng JID đầy đủ lấy từ event listener
    python src/_e2ee_send_test.py 100012345678@msgr "hello E2EE"

Cookie đọc từ env `FBCHAT_COOKIE` hoặc `src/config.json` key `cookies`.
Bridge binary mặc định: `build/fbchat-bridge-e2ee[.exe]`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _core._console import configure_utf8_console, safe_print  # noqa: E402
from _core._session import dataGetHome  # noqa: E402
from _messaging._listening_e2ee import (  # noqa: E402
    _redact_bridge_text,
    _resolve_binary,
)
from _messaging._send_e2ee import (  # noqa: E402
    api as E2EESender,
    normalize_chat_jid,
)

CONFIG_PATH = HERE / "config.json"
PROJECT_ROOT = HERE.parent


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(tag: str, message: str) -> None:
    safe_print(f"[{ts()}] [{tag}] {message}")


def load_cookie() -> str:
    cookie = os.getenv("FBCHAT_COOKIE", "").strip()
    if cookie:
        return cookie

    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        cookie = str(config.get("cookies") or "").strip()

    if not cookie or "PASTE_YOUR" in cookie:
        raise ValueError(
            "Không có cookie. Hãy set env FBCHAT_COOKIE hoặc điền key "
            f"'cookies' trong {CONFIG_PATH}."
        )
    return cookie


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test gửi tin nhắn Messenger E2EE qua _send_e2ee.py",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Facebook numeric ID hoặc JID đầy đủ, ví dụ 100012345678 hoặc 100012345678@msgr",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Nội dung tin nhắn cần gửi",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ xác nhận JID đã normalize, không đăng nhập/không gửi tin",
    )
    parser.add_argument(
        "--log-level",
        default="warn",
        help="Log level truyền cho bridge Go: none, warn, info, debug",
    )
    parser.add_argument(
        "--binary-path",
        default=None,
        help="Đường dẫn bridge binary tùy chỉnh",
    )
    parser.add_argument(
        "--device-path",
        default=None,
        help="Nơi lưu Signal device/session nếu dùng --persist-device",
    )
    parser.add_argument(
        "--persist-device",
        action="store_true",
        help="Lưu Signal keys xuống device-path để lần sau không pair lại",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=120.0,
        help="Timeout cho connect/connectE2EE",
    )
    parser.add_argument(
        "--send-timeout",
        type=float,
        default=180.0,
        help="Timeout cho call sendE2EEMessage",
    )
    parser.add_argument(
        "--reply-message",
        default="",
        help="Message ID cần quote-reply, nếu muốn test reply",
    )
    parser.add_argument(
        "--reply-sender-jid",
        default="",
        help="Sender JID của message gốc khi quote-reply",
    )
    return parser


def print_json(data: dict[str, Any]) -> None:
    safe_print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def prompt_required(label: str) -> str:
    while True:
        value = input(label).strip()
        if value:
            return value
        safe_print("Giá trị không được để trống.")


def resolve_device_path(device_path: str | None) -> str | None:
    if not device_path:
        return None
    path = Path(device_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


def main() -> int:
    configure_utf8_console()
    args = build_parser().parse_args()

    if not args.target:
        args.target = prompt_required("Nhập UID/JID người nhận: ")
    if args.message is None:
        args.message = prompt_required("Nhập nội dung cần gửi: ")

    try:
        normalized_jid = normalize_chat_jid(args.target)
    except ValueError as exc:
        log("target", f"không hợp lệ: {_redact_bridge_text(exc)}")
        return 2

    log("target", "JID người nhận hợp lệ (giá trị đã ẩn).")
    if args.dry_run:
        return 0

    try:
        binary = Path(args.binary_path) if args.binary_path else _resolve_binary()
        if not binary.exists():
            raise FileNotFoundError(binary)
        log("bridge", str(binary))
    except FileNotFoundError as exc:
        log("bridge", f"không tìm thấy binary: {_redact_bridge_text(exc)}")
        return 2

    try:
        cookie = load_cookie()
        log("login", "đang lấy dataFB từ cookie...")
        dataFB = asyncio.run(dataGetHome(cookie))
        if not isinstance(dataFB, dict):
            raise RuntimeError("dataGetHome không trả về session hợp lệ")
        log("login", "đăng nhập thành công")
    except Exception as exc:  # noqa: BLE001
        log("login", f"thất bại: {_redact_bridge_text(exc)}")
        return 2

    sender = E2EESender(
        dataFB=dataFB,
        log_level=args.log_level,
        device_path=resolve_device_path(args.device_path),
        e2ee_memory_only=not args.persist_device,
        binary_path=str(binary),
    )

    try:
        log("bridge", "đang connect + connectE2EE...")
        sender.connect(timeout=args.connect_timeout)
        log("send", "đang gửi tới JID đã xác thực (giá trị đã ẩn)...")
        if "@" in str(args.target):
            result = sender.send(
                normalized_jid,
                args.message,
                replyMessage=args.reply_message,
                replySenderJid=args.reply_sender_jid,
                timeout=args.send_timeout,
            )
        else:
            result = sender.send_to_user(
                args.target,
                args.message,
                replyMessage=args.reply_message,
                replySenderJid=args.reply_sender_jid,
                timeout=args.send_timeout,
            )
        print_json(result)
        return 0 if result.get("success") == 1 else 1
    except Exception as exc:  # noqa: BLE001
        log("error", _redact_bridge_text(exc))
        return 1
    finally:
        sender.close()


if __name__ == "__main__":
    raise SystemExit(main())
