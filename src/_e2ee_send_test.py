"""
fbchat-v2 :: _e2ee_send_test.py
================================

Test driver cho `_messaging/_send_e2ee.py`.

Cach dung nhanh:
    # Chay interactive: script se hoi UID/JID va noi dung can gui
    python src/_e2ee_send_test.py

    # Chi test normalize Facebook ID -> Messenger E2EE JID, khong gui tin
    python src/_e2ee_send_test.py --dry-run

    # Gui that bang Facebook numeric ID
    python src/_e2ee_send_test.py 100012345678 "hello E2EE"

    # Gui that bang JID day du lay tu event listener
    python src/_e2ee_send_test.py 100012345678@msgr "hello E2EE"

Cookie doc tu env `FBCHAT_COOKIE` hoac `src/config.json` key `cookies`.
Bridge binary mac dinh: `build/fbchat-bridge-e2ee[.exe]`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _core._session import dataGetHome  # noqa: E402
from _messaging._listening_e2ee import _resolve_binary  # noqa: E402
from _messaging._send_e2ee import (  # noqa: E402
    api as E2EESender,
    normalize_chat_jid,
)


CONFIG_PATH = HERE / "config.json"
PROJECT_ROOT = HERE.parent


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(tag: str, message: str) -> None:
    print(f"[{ts()}] [{tag}] {message}")


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
            "Khong co cookie. Hay set env FBCHAT_COOKIE hoac dien key "
            f"'cookies' trong {CONFIG_PATH}."
        )
    return cookie


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test gui tin nhan Messenger E2EE qua _send_e2ee.py",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Facebook numeric ID hoac JID day du, vi du 100012345678 hoac 100012345678@msgr",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Noi dung tin nhan can gui",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chi in JID da normalize, khong dang nhap/khong gui tin",
    )
    parser.add_argument(
        "--log-level",
        default="warn",
        help="Log level truyen cho bridge Go: none, warn, info, debug",
    )
    parser.add_argument(
        "--binary-path",
        default=None,
        help="Duong dan bridge binary tuy chinh",
    )
    parser.add_argument(
        "--device-path",
        default=None,
        help="Noi luu Signal device/session neu dung --persist-device",
    )
    parser.add_argument(
        "--persist-device",
        action="store_true",
        help="Luu Signal keys xuong device-path de lan sau khong pair lai",
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
        help="Message ID can quote-reply, neu muon test reply",
    )
    parser.add_argument(
        "--reply-sender-jid",
        default="",
        help="Sender JID cua message goc khi quote-reply",
    )
    return parser


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def prompt_required(label: str) -> str:
    while True:
        value = input(label).strip()
        if value:
            return value
        print("Gia tri khong duoc de trong.")


def resolve_device_path(device_path: str | None) -> str | None:
    if not device_path:
        return None
    path = Path(device_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


def main() -> int:
    args = build_parser().parse_args()

    if not args.target:
        args.target = prompt_required("Nhap UID/JID nguoi nhan: ")
    if args.message is None:
        args.message = prompt_required("Nhap noi dung can gui: ")

    try:
        normalized_jid = normalize_chat_jid(args.target)
    except ValueError as exc:
        log("target", f"khong hop le: {exc}")
        return 2

    log("target", f"{args.target!r} -> {normalized_jid}")
    if args.dry_run:
        return 0

    try:
        binary = Path(args.binary_path) if args.binary_path else _resolve_binary()
        if not binary.exists():
            raise FileNotFoundError(binary)
        log("bridge", str(binary))
    except FileNotFoundError as exc:
        log("bridge", f"khong tim thay binary: {exc}")
        return 2

    try:
        cookie = load_cookie()
        log("login", "dang lay dataFB tu cookie...")
        dataFB = dataGetHome(cookie)
        log("login", f"FacebookID={dataFB.get('FacebookID')}")
    except Exception as exc:  # noqa: BLE001
        log("login", f"that bai: {exc}")
        return 2

    sender = E2EESender(
        dataFB=dataFB,
        log_level=args.log_level,
        device_path=resolve_device_path(args.device_path),
        e2ee_memory_only=not args.persist_device,
        binary_path=str(binary),
    )

    try:
        log("bridge", "dang connect + connectE2EE...")
        sender.connect(timeout=args.connect_timeout)
        log("send", f"dang gui toi {normalized_jid}...")
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
        log("error", str(exc))
        return 1
    finally:
        sender.close()


if __name__ == "__main__":
    raise SystemExit(main())