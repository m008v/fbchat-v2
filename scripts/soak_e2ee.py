"""Run an opt-in, bounded live E2EE canary and collect private-free evidence.

The peer opts in by sending the exact challenge over E2EE. Only that peer may
trigger one text reply and one image/document round trip. No arbitrary thread
is selected and regular LightSpeed traffic is never counted as E2EE proof.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import ctypes
import hashlib
import json
import math
import os
import secrets
import signal
import sys
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fbchat_v2._core._console import configure_utf8_console, safe_print  # noqa: E402
from fbchat_v2._core._session import dataGetHome  # noqa: E402
from fbchat_v2._messaging._listening_e2ee import (  # noqa: E402
    BridgeError,
    listeningE2EEEvent,
)

MAX_MEDIA_BYTES = 2 * 1024 * 1024
MAX_SEEN_MESSAGES = 4096


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Thời gian phải là số hữu hạn lớn hơn 0.")
    return number


def process_rss(pid: int) -> int | None:
    """Read RSS without adding a runtime dependency or invoking a shell."""
    if sys.platform != "win32":
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
        except (OSError, ValueError):
            return None
        return None

    from ctypes import wintypes

    class MemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(MemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        return None
    try:
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return int(counters.WorkingSetSize)
    finally:
        kernel.CloseHandle(handle)


def device_identity(path: Path) -> bytes:
    """Compare identity in memory; never export device keys or their digest."""
    state = json.loads(path.read_text(encoding="utf-8"))
    fields = ("noise_key_priv", "identity_key_priv", "registration_id", "jid_user")
    if any(not state.get(field) for field in fields):
        raise RuntimeError("Persistent device chưa có đủ identity đã đăng ký.")
    payload = json.dumps(
        [state[field] for field in fields] + [state.get("jid_device", 0)]
    ).encode()
    return hashlib.sha256(payload).digest()


def validate_device_path(
    path: Path, *, output_dir: Path, config: Path, binary_path: Path
) -> None:
    reserved = {
        config.resolve(),
        binary_path.resolve(),
        output_dir.resolve(),
        *(
            output_dir.resolve() / name
            for name in ("report.json", "report.pending", "stop.request")
        ),
    }
    if path.resolve() in reserved or (path.exists() and not path.is_file()):
        raise ValueError(
            "Device path không được trùng config, binary hoặc evidence/control file."
        )


class Canary:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.output = args.output_dir.resolve()
        self.device_path = (
            args.device_path.resolve()
            if getattr(args, "device_path", None) is not None
            else self.output / "device.json"
        )
        self.events: Queue[dict[str, Any]] = Queue(maxsize=64)
        self.listener_failures: Queue[BaseException] = Queue(maxsize=2)
        self.observer_drops = 0
        self.stop_requested = threading.Event()
        self.listener: listeningE2EEEvent | None = None
        self.thread: threading.Thread | None = None
        self.session: dict[str, Any] = {}
        self.peer: tuple[str, str] | None = None
        self.seen: set[str] = set()
        self.seen_order: deque[str] = deque()
        self.echoed: set[str] = set()
        self.started_at = 0.0
        self.injected = False
        self.post_reconnect_sent = False
        self.text_reply_attempted = False
        self.text_ack = f"text-ok-{secrets.token_hex(4)}"
        self.media_ack = f"media-ok-{secrets.token_hex(4)}"
        self.media_ack_prompted = False
        self.regular_notice_attempted = False
        self.minimum_event_timestamp_ms = int(time.time() * 1000)
        self.bridge_error_events = 0
        self.final_bridge_drops = 0
        self.observed: Counter[str] = Counter()
        self.observed_lock = threading.Lock()
        self.report: dict[str, Any] = {
            "started_at": utc_now(),
            "status": "starting",
            "challenge": args.challenge,
            "requested_seconds": args.duration,
            "cold_restart_identity_reused": False,
            "text_reply_rpc_ok": False,
            "peer_confirmed_text": False,
            "peer_confirmed_media": False,
            "regular_notice_rpc_ok": False,
            "post_reconnect_text_rpc_ok": False,
            "watchdog_fault_injected": False,
            "shutdown_clean": False,
            "counts": Counter(),
            "media": [],
            "samples": [],
            "errors": [],
            "observed": {},
        }

    def save(self) -> None:
        with self.observed_lock:
            self.report["observed"] = dict(self.observed)
        self.report["bridge_error_events"] = self.bridge_error_events
        temporary = self.output / "report.pending"
        temporary.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.output / "report.json")

    def record_error(self, stage: str, error: BaseException) -> None:
        # Provider exception text can contain IDs/URLs. Keep only allowlisted
        # local stage and exception class in persistent evidence.
        self.report["errors"].append({"stage": stage, "type": type(error).__name__})
        safe_print(f"[canary] {stage}: {type(error).__name__}")
        self.save()

    def on_event(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if not isinstance(kind, str):
            self.observe("event_invalid_type")
            return
        known_kind = (
            kind
            if kind
            in {
                "message",
                "e2eeMessage",
                "error",
                "raw",
                "ready",
                "reconnected",
                "closed",
                "disconnected",
                "e2eeConnected",
                "e2eeReceipt",
                "typing",
                "reaction",
                "readReceipt",
                "deviceDataChanged",
            }
            else "other"
        )
        self.observe(f"event_{known_kind}")
        data = event.get("data")
        if kind in {"message", "e2eeMessage"} and isinstance(data, dict):
            if data.get("text") == self.args.challenge:
                self.observe(f"challenge_{kind}")
        if kind == "raw" and isinstance(data, dict):
            raw_type = data.get("type")
            if isinstance(raw_type, str) and raw_type in {
                "FBMessage",
                "Message",
                "UndecryptableMessage",
                "Receipt",
                "Connected",
                "Disconnected",
            }:
                self.observe(f"raw_{raw_type}")
        if kind == "error":
            self.bridge_error_events += 1
            return
        regular_challenge = (
            kind == "message"
            and isinstance(data, dict)
            and data.get("text") == self.args.challenge
            and getattr(self.args, "regular_notice", False)
        )
        if kind != "e2eeMessage" and not regular_challenge:
            return
        try:
            self.events.put_nowait(event)
        except Full:
            self.observer_drops += 1

    def observe(self, name: str) -> None:
        with self.observed_lock:
            self.observed[name] += 1

    def start_listener(self) -> None:
        if self.stop_requested.is_set():
            raise InterruptedError("Canary đã được yêu cầu dừng.")
        listener = listeningE2EEEvent(
            self.session,
            binary_path=str(self.args.binary_path.resolve()),
            device_path=str(self.device_path),
            e2ee_memory_only=False,
            enable_e2ee=True,
            log_level="warn",
            debug_errors=self.args.debug_errors,
        )
        self.listener = listener
        listener.on_message(self.on_event)

        def run() -> None:
            try:
                listener.connect_mqtt_blocking()
            except Exception as error:
                if not self.stop_requested.is_set():
                    try:
                        self.listener_failures.put_nowait(error)
                    except Full:
                        self.stop_requested.set()

        self.thread = threading.Thread(
            target=run, name="e2ee-soak-listener", daemon=True
        )
        self.thread.start()
        deadline = time.monotonic() + listener.startup_timeout
        while time.monotonic() < deadline:
            if self.stop_requested.is_set():
                listener.stop()
                raise InterruptedError("Canary dừng trong startup.")
            if listener.wait_until_connected(0.25, require_e2ee=True):
                return
        raise RuntimeError("E2EE listener không đạt readiness.")

    def stop_listener(self) -> bool:
        if self.listener is not None:
            if self.listener._bridge is not None:
                self.final_bridge_drops += self.listener._bridge.dropped_event_count
            self.listener.stop()
        if self.thread is not None:
            self.thread.join(timeout=15)
            return not self.thread.is_alive()
        return True

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        listener = self.listener
        if listener is None or listener._bridge is None:
            raise RuntimeError("Canary chưa có bridge.")
        result = listener._bridge.call_blocking(method, params, timeout=90.0)
        if result.get("deliveryStatus") == "unknown":
            raise BridgeError("Delivery chưa được xác nhận; không retry.")
        return result

    def send_text(self, text: str) -> None:
        if self.peer is None:
            raise RuntimeError("Chưa có peer E2EE opt-in.")
        self.call("sendE2EEMessage", {"chatJid": self.peer[0], "text": text})

    def handle_media(self, attachment: dict[str, Any]) -> None:
        kind = attachment.get("type")
        category = "image" if kind == "image" else "document"
        if kind not in {"image", "file", "document"} or category in self.echoed:
            return
        size = attachment.get("fileSize", 0)
        if type(size) is not int or not 0 < size <= MAX_MEDIA_BYTES:
            self.report["counts"]["media_rejected_size"] += 1
            return
        result = self.call(
            "downloadE2EEMedia",
            {
                "directPath": attachment.get("directPath", ""),
                "mediaKey": attachment.get("mediaKey", ""),
                "mediaSha256": attachment.get("mediaSha256", ""),
                "mediaEncSha256": attachment.get("mediaEncSha256", ""),
                "mediaType": category,
                "mimeType": attachment.get("mimeType", "application/octet-stream"),
                "fileSize": size,
            },
        )
        payload = base64.b64decode(result["data"], validate=True)
        expected = base64.b64decode(attachment["mediaSha256"], validate=True)
        if (
            len(payload) > MAX_MEDIA_BYTES
            or hashlib.sha256(payload).digest() != expected
        ):
            raise RuntimeError("Media plaintext không khớp digest trong E2EE event.")
        evidence = {"kind": category, "bytes": len(payload), "sha256_verified": True}
        self.report["media"].append(evidence)
        if self.peer is None:
            raise RuntimeError("Peer E2EE không tồn tại.")
        params = {
            "chatJid": self.peer[0],
            "data": base64.b64encode(payload).decode("ascii"),
            "mimeType": attachment.get("mimeType", "application/octet-stream"),
        }
        if category == "image":
            params.update(
                width=attachment.get("width", 0),
                height=attachment.get("height", 0),
                caption=f"{self.args.challenge}: image round trip",
            )
            method = "sendE2EEImage"
        else:
            params["filename"] = "canary-roundtrip.bin"
            method = "sendE2EEDocument"
        # Downloads are read-only; consume the one-shot only when sending.
        # Mark first so an uncertain send can never trigger a duplicate echo.
        self.echoed.add(category)
        self.call(method, params)
        evidence["echo_rpc_ok"] = True
        safe_print(
            f"[canary] E2EE {category}: download/digest/send OK ({len(payload)} bytes)"
        )

    def handle_event(self, event: dict[str, Any]) -> None:
        data = event.get("data")
        if not isinstance(data, dict):
            self.observe("reject_invalid_data")
            return
        timestamp = data.get("timestampMs")
        if (
            type(timestamp) is not int
            or timestamp < self.minimum_event_timestamp_ms
            or timestamp > int(time.time() * 1000) + 60_000
        ):
            self.observe("reject_timestamp")
            return
        if str(data.get("senderId")) == str(self.session.get("FacebookID")):
            self.observe("reject_self")
            return
        if event.get("type") == "message":
            self.handle_regular_notice(data)
            return
        chat, sender = data.get("chatJid"), data.get("senderJid")
        if (
            not isinstance(chat, str)
            or not isinstance(sender, str)
            or not chat
            or not sender
        ):
            self.observe("reject_jid_shape")
            return
        text = data.get("text", "")
        if self.peer is None:
            if text != self.args.challenge:
                self.observe("reject_not_challenge")
                return
            self.peer = (chat, sender)
        if self.peer != (chat, sender):
            self.observe("reject_other_peer")
            return
        message_id = data.get("id")
        if not isinstance(message_id, str) or not message_id:
            self.report["counts"]["missing_message_id"] += 1
            return
        if message_id in self.seen:
            self.report["counts"]["duplicate_e2ee_event"] += 1
            return
        self.seen.add(message_id)
        self.seen_order.append(message_id)
        if len(self.seen_order) > MAX_SEEN_MESSAGES:
            self.seen.discard(self.seen_order.popleft())
        self.report["counts"]["e2ee_received"] += 1
        if text == self.args.challenge and not self.text_reply_attempted:
            self.text_reply_attempted = True
            self.send_text(
                f"{self.args.challenge}: E2EE reply OK. "
                f"Sau khi thấy tin này, gửi lại: {self.text_ack}"
            )
            self.report["text_reply_rpc_ok"] = True
            safe_print(
                "[canary] E2EE text receive + reply RPC OK; peer identity hidden"
            )
        if text == self.text_ack and self.report["text_reply_rpc_ok"]:
            self.report["peer_confirmed_text"] = True
        if text == self.media_ack and all(
            any(
                item["kind"] == kind and item.get("echo_rpc_ok")
                for item in self.report["media"]
            )
            for kind in ("image", "document")
        ):
            self.report["peer_confirmed_media"] = True
        attachments = data.get("attachments", [])
        if isinstance(attachments, list):
            for attachment in attachments[:2]:
                if isinstance(attachment, dict):
                    self.handle_media(attachment)
        if not self.media_ack_prompted and all(
            any(
                item["kind"] == kind and item.get("echo_rpc_ok")
                for item in self.report["media"]
            )
            for kind in ("image", "document")
        ):
            self.media_ack_prompted = True
            self.send_text(
                "Đã echo ảnh và file E2EE. Sau khi nhận đủ cả hai, gửi lại: "
                f"{self.media_ack}"
            )
        self.save()

    def handle_regular_notice(self, data: dict[str, Any]) -> None:
        if (
            not getattr(self.args, "regular_notice", False)
            or data.get("text") != self.args.challenge
            or self.regular_notice_attempted
        ):
            return
        thread_id = data.get("threadId")
        if type(thread_id) is not int or thread_id <= 0:
            self.observe("reject_regular_thread_shape")
            return
        self.regular_notice_attempted = True
        self.call(
            "sendMessage",
            {
                "threadId": thread_id,
                "text": (
                    "Đã nhận mã canary qua Go LightSpeed regular. "
                    "Event này không phải e2eeMessage; kiểm thử E2EE chưa đạt."
                ),
            },
        )
        self.report["regular_notice_rpc_ok"] = True
        safe_print(
            "[canary] diagnostic notice sent via Go LightSpeed regular; E2EE proof unchanged"
        )
        self.save()

    def sample(self) -> None:
        if self.listener is None or self.listener._bridge is None:
            return
        bridge = self.listener._bridge
        healthy = self.call("isConnected", {})
        sample = {
            "elapsed_seconds": round(time.monotonic() - self.started_at, 2),
            "regular_connected": healthy.get("connected") is True,
            "e2ee_connected": healthy.get("e2eeConnected") is True,
            "generation": bridge._generation,
            "bridge_queue_size": bridge.events.qsize(),
            "bridge_queue_drops": bridge.dropped_event_count,
            "canary_queue_size": self.events.qsize(),
            "canary_queue_drops": self.observer_drops,
            "parent_rss_bytes": process_rss(os.getpid()),
            "bridge_rss_bytes": process_rss(bridge._proc.pid),
        }
        self.report["samples"].append(sample)
        self.save()

    def exercise_watchdog(self) -> None:
        if self.listener is None or self.listener._bridge is None:
            return
        bridge = self.listener._bridge
        previous = bridge._generation
        self.injected = True
        # Kill only the exact subprocess owned by this canary, never a process
        # name, system connection, unrelated bot or network interface.
        bridge._proc.kill()
        bridge._proc.wait(timeout=10)
        self.report["watchdog_fault_injected"] = True
        deadline = time.monotonic() + self.listener.startup_timeout
        while time.monotonic() < deadline and not self.stop_requested.wait(0.25):
            if bridge._generation > previous and self.listener.wait_until_connected(
                0.25, require_e2ee=True
            ):
                self.report["watchdog_recovered"] = True
                safe_print("[canary] watchdog respawn + E2EE reconnect OK")
                return
        raise RuntimeError("Watchdog không phục hồi trong startup deadline.")

    def run(self) -> int:
        self.output.mkdir(parents=True, exist_ok=False)
        self.save()
        try:
            cookie = os.getenv("FBCHAT_COOKIE", "").strip()
            if not cookie:
                config = json.loads(self.args.config.read_text(encoding="utf-8"))
                cookie = str(config.get("cookies") or "").strip()
            if not cookie:
                raise ValueError("Chưa cấu hình cookie clone.")
            session = asyncio.run(dataGetHome(cookie))
            if not isinstance(session, dict):
                raise RuntimeError("Không tạo được Facebook session.")
            self.session = session
            self.start_listener()
            if not self.stop_listener():
                raise RuntimeError("Listener đầu không dừng sạch.")
            identity = device_identity(self.device_path)
            self.start_listener()
            self.report["cold_restart_identity_reused"] = identity == device_identity(
                self.device_path
            )
            if not self.report["cold_restart_identity_reused"]:
                raise RuntimeError("Cold restart thay identity thiết bị.")
            self.started_at = time.monotonic()
            self.minimum_event_timestamp_ms = int(time.time() * 1000)
            self.report["ready_at"] = utc_now()
            self.report["status"] = "running"
            self.save()
            safe_print(
                f"[canary] READY; send {self.args.challenge}, image and file <=2 MiB via E2EE"
            )
            next_sample = 0.0
            while not self.stop_requested.is_set():
                if (self.output / "stop.request").exists():
                    self.stop_requested.set()
                    break
                try:
                    failure = self.listener_failures.get_nowait()
                except Empty:
                    pass
                else:
                    raise RuntimeError("Listener đã dừng ngoài dự kiến.") from failure
                elapsed = time.monotonic() - self.started_at
                if elapsed >= self.args.duration:
                    break
                try:
                    event = self.events.get(timeout=0.25)
                    self.handle_event(event)
                except Empty:
                    pass
                except Exception as error:
                    self.record_error("peer_roundtrip", error)
                if elapsed >= next_sample:
                    try:
                        self.sample()
                    except Exception as error:
                        self.record_error("health_sample", error)
                    next_sample = elapsed + self.args.sample_interval
                if elapsed >= self.args.fault_after and not self.injected:
                    self.exercise_watchdog()
                if (
                    self.report.get("watchdog_recovered")
                    and self.peer is not None
                    and not self.post_reconnect_sent
                ):
                    self.post_reconnect_sent = True
                    self.send_text(f"{self.args.challenge}: E2EE after reconnect OK")
                    self.report["post_reconnect_text_rpc_ok"] = True
                    self.save()
            self.report["status"] = (
                "cancelled" if self.stop_requested.is_set() else "completed"
            )
        except Exception as error:
            if self.stop_requested.is_set() and isinstance(error, InterruptedError):
                self.report["status"] = "cancelled"
            else:
                self.report["status"] = "failed"
                self.record_error("run", error)
        finally:
            self.stop_requested.set()
            shutdown_start = time.monotonic()
            self.report["shutdown_clean"] = self.stop_listener()
            self.report["shutdown_seconds"] = round(
                time.monotonic() - shutdown_start, 2
            )
            self.report["ended_at"] = utc_now()
            self.report["bridge_error_events"] = self.bridge_error_events
            self.report["final_bridge_queue_drops"] = self.final_bridge_drops
            if self.started_at:
                self.report["elapsed_seconds"] = round(
                    time.monotonic() - self.started_at, 2
                )
            samples = self.report["samples"]
            media = self.report["media"]
            self.report["checks"] = {
                "full_duration": self.report["status"] == "completed",
                "persistent_identity": self.report["cold_restart_identity_reused"],
                "text_roundtrip": self.report["text_reply_rpc_ok"]
                and self.report["peer_confirmed_text"],
                "media_roundtrip": self.report["peer_confirmed_media"]
                and all(
                    any(
                        item["kind"] == kind and item.get("echo_rpc_ok")
                        for item in media
                    )
                    for kind in ("image", "document")
                ),
                "watchdog_recovered": self.report.get("watchdog_recovered", False),
                "e2ee_send_after_reconnect": self.report["post_reconnect_text_rpc_ok"],
                "no_queue_drop": self.observer_drops == 0
                and self.final_bridge_drops == 0
                and all(sample["bridge_queue_drops"] == 0 for sample in samples),
                "health_samples_connected": bool(samples)
                and all(
                    sample["regular_connected"] and sample["e2ee_connected"]
                    for sample in samples
                ),
                "no_observed_errors": not self.report["errors"]
                and self.bridge_error_events == 0,
                "clean_shutdown": self.report["shutdown_clean"],
            }
            self.report["acceptance_passed"] = all(self.report["checks"].values())
            self.save()
        if self.report["status"] != "completed":
            return 1
        return 0 if self.report["acceptance_passed"] else 2


def main() -> int:
    configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=SRC / "config.json")
    parser.add_argument("--device-path", type=Path)
    parser.add_argument("--duration", type=positive_seconds, default=7200.0)
    parser.add_argument("--sample-interval", type=positive_seconds, default=60.0)
    parser.add_argument("--fault-after", type=positive_seconds, default=300.0)
    parser.add_argument(
        "--challenge", help="Mã chính xác; bỏ trống để tạo nonce từng run."
    )
    parser.add_argument("--regular-notice", action="store_true")
    parser.add_argument("--debug-errors", action="store_true")
    args = parser.parse_args()
    if args.challenge is None:
        args.challenge = f"canary-233-{secrets.token_hex(4)}"
    if not 1 <= len(args.challenge) <= 64 or not args.challenge.isascii():
        parser.error("Challenge phải có 1–64 ký tự ASCII.")
    if args.duration > 24 * 3600 or args.sample_interval < 5:
        parser.error("Duration tối đa 24 giờ; sample interval tối thiểu 5 giây.")
    if args.fault_after >= args.duration:
        parser.error("Fault injection phải xảy ra trước khi soak kết thúc.")
    if not args.binary_path.is_file():
        parser.error("Không tìm thấy bridge binary.")
    if args.output_dir.exists():
        parser.error("Output directory phải mới để không ghi đè device/evidence.")
    if args.device_path is not None:
        try:
            validate_device_path(
                args.device_path,
                output_dir=args.output_dir,
                config=args.config,
                binary_path=args.binary_path,
            )
        except ValueError as error:
            parser.error(str(error))
    canary = Canary(args)
    signal.signal(signal.SIGINT, lambda *_: canary.stop_requested.set())
    signal.signal(signal.SIGTERM, lambda *_: canary.stop_requested.set())
    return canary.run()


if __name__ == "__main__":
    raise SystemExit(main())
