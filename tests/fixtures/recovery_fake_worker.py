"""Offline subprocess adapter: synthetic protocol, real proxied localhost bytes.

This executable never opens a Messenger connection or uses an actual bridge.
RecoveryCanary retains its real loop, event validation, ACK gates and reports;
only its provider/session and RPC adapter are replaced with deterministic data.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import recovery_e2ee as recovery  # noqa: E402

PRIVATE_PAYLOAD = b"offline-dummy-private-media-never-export"
PRIVATE_PEER = "offline-dummy-private-peer@msgr"
PRIVATE_CHAT = "offline-dummy-private-chat@msgr"
PRIVATE_COOKIE = "offline-dummy-private-cookie"


def wait_for(
    predicate: Callable[[], bool], stop: threading.Event, seconds: float = 6.0
) -> None:
    deadline = time.monotonic() + seconds
    while not predicate():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Offline protocol deadline.")
        if stop.wait(min(0.01, remaining)):
            raise InterruptedError("Offline worker stopped.")


class SocketAdapter:
    """Two independent opaque byte streams through the real CONNECT proxy."""

    def __init__(self, targets: list[tuple[str, int]]) -> None:
        proxy = urlsplit(os.environ["HTTPS_PROXY"])
        if proxy.scheme != "http" or proxy.hostname != "127.0.0.1" or not proxy.port:
            raise ValueError("Offline worker requires the child loopback proxy.")
        if any(not ipaddress.ip_address(host).is_loopback for host, _ in targets):
            raise ValueError("Offline endpoints must be literal loopback addresses.")
        self.proxy = (proxy.hostname, proxy.port)
        self.targets = targets
        self.streams: list[socket.socket] = []
        self.rejected = 0
        self.observed_cut = 0
        self.rpc_calls = 0
        self.lock = threading.RLock()

    def _open(self, target: tuple[str, int]) -> socket.socket:
        stream = socket.create_connection(self.proxy, timeout=0.4)
        try:
            stream.sendall(
                f"CONNECT {target[0]}:{target[1]} HTTP/1.1\r\n\r\n".encode("ascii")
            )
            header = bytearray()
            while b"\r\n\r\n" not in header:
                chunk = stream.recv(1024)
                if not chunk or len(header) + len(chunk) > 8192:
                    raise ConnectionError("Incomplete local CONNECT response.")
                header.extend(chunk)
            if not header.startswith(b"HTTP/1.1 200 "):
                if header.startswith(b"HTTP/1.1 503 "):
                    self.rejected += 1
                raise ConnectionError("Local CONNECT unavailable.")
            return stream
        except BaseException:
            stream.close()
            raise

    def connect(self) -> bool:
        with self.lock:
            return self._connect()

    def _connect(self) -> bool:
        if self.streams:
            return True
        try:
            for target in self.targets:
                self.streams.append(self._open(target))
            return True
        except OSError:
            self.close()
            return False

    @staticmethod
    def exchange(stream: socket.socket, payload: bytes) -> bytes:
        stream.sendall(payload)
        received = bytearray()
        while len(received) < len(payload):
            chunk = stream.recv(len(payload) - len(received))
            if not chunk:
                raise ConnectionError("Local echo stream closed.")
            received.extend(chunk)
        if received != payload:
            raise ValueError("Local echo bytes differ.")
        return bytes(received)

    def healthy(self) -> bool:
        with self.lock:
            return self._healthy()

    def _healthy(self) -> bool:
        if self.streams:
            broken = 0
            for stream in self.streams:
                try:
                    self.exchange(stream, b"offline-health-probe")
                except OSError:
                    broken += 1
            if broken:
                self.observed_cut += broken
                self.close()
        return self.connect()

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self._call(method, params)

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "isConnected":
            healthy = self.healthy()
            return {"connected": healthy, "e2eeConnected": healthy}
        if not self.streams:
            raise ConnectionError("Offline RPC has no local stream.")
        self.rpc_calls += 1
        if method == "downloadE2EEMedia":
            self.exchange(self.streams[1], PRIVATE_PAYLOAD)
            return {"data": base64.b64encode(PRIVATE_PAYLOAD).decode("ascii")}
        if method in {"sendE2EEImage", "sendE2EEDocument"}:
            payload = base64.b64decode(params["data"], validate=True)
        elif method == "sendE2EEMessage":
            payload = str(params["text"]).encode("utf-8")
        else:
            raise ValueError("Unexpected offline RPC method.")
        self.exchange(self.streams[1], payload)
        return {}

    def deliver(self, event: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if not self.streams:
                raise ConnectionError("Offline peer has no local stream.")
            payload = json.dumps(event).encode("utf-8")
            return json.loads(self.exchange(self.streams[0], payload))

    def close(self) -> None:
        with self.lock:
            self._close()

    def _close(self) -> None:
        for stream in self.streams:
            try:
                stream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            stream.close()
        self.streams.clear()


class OfflineCanary(recovery.RecoveryCanary):
    def __init__(self, args: argparse.Namespace, adapter: SocketAdapter) -> None:
        super().__init__(args)
        self.adapter = adapter
        self.mode = args.mode
        self.peer_thread: threading.Thread | None = None
        self.report.update(
            evidence_scope="offline_simulation", test="offline-controller-rehearsal"
        )

    def start_listener(self) -> None:
        if not self.adapter.connect():
            raise ConnectionError("Offline initial tunnel setup failed.")
        # Minimal fake bridge identity/state consumed by the real canary loop.
        self.listener = SimpleNamespace(
            _bridge=SimpleNamespace(
                _generation=1,
                _proc=SimpleNamespace(pid=os.getpid()),
                dropped_event_count=0,
                events=Queue(),
            )
        )
        if self.mode == "success":
            self.peer_thread = threading.Thread(
                target=self.peer_protocol, name="offline-peer-protocol", daemon=True
            )
            self.peer_thread.start()

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return self.adapter.call(method, params)

    def stop_listener(self) -> bool:
        if self.peer_thread is not None:
            self.peer_thread.join(timeout=1)
        self.adapter.close()
        clean = self.peer_thread is None or not self.peer_thread.is_alive()
        self.report["offline_transport"] = {
            "stream_cuts_observed": self.adapter.observed_cut,
            "connect_rejections_observed": self.adapter.rejected,
            "rpc_calls": self.adapter.rpc_calls,
            "closed_stream_count": 2,
            "peer_thread_clean": clean,
            "worker_pid": os.getpid(),
            "proxy_environment_consistent": all(
                os.environ.get(name) == os.environ["HTTPS_PROXY"]
                for name in ("HTTP_PROXY", "http_proxy", "https_proxy")
            )
            and os.environ.get("NO_PROXY") == os.environ.get("no_proxy") == "",
        }
        return clean

    def emit(
        self,
        number: int,
        text: str = "",
        media: str | None = None,
        timestamp_ms: int | None = None,
    ) -> None:
        data: dict[str, Any] = {
            "id": f"offline-event-{number}",
            "chatJid": PRIVATE_CHAT,
            "senderJid": PRIVATE_PEER,
            "senderId": "offline-peer",
            "text": text,
            "timestampMs": timestamp_ms or int(time.time() * 1000),
        }
        if media is not None:
            data["attachments"] = [
                {
                    "type": media,
                    "fileSize": len(PRIVATE_PAYLOAD),
                    "mediaSha256": base64.b64encode(
                        hashlib.sha256(PRIVATE_PAYLOAD).digest()
                    ).decode("ascii"),
                    "mediaKey": "offline-dummy-private-media-key",
                    "directPath": "/offline-dummy-private-path",
                    "filename": "offline-dummy-private-filename",
                }
            ]
        self.on_event(self.adapter.deliver({"type": "e2eeMessage", "data": data}))

    def peer_protocol(self) -> None:
        try:
            wait_for(
                lambda: self.report["status"] == "cold_restart_ready",
                self.stop_requested,
            )
            self.emit(1, self.args.challenge)
            wait_for(lambda: self.report["text_reply_rpc_ok"], self.stop_requested)
            self.emit(2, self.text_ack)
            self.emit(3, media="image")
            self.emit(4, media="file")
            wait_for(lambda: self.media_ack_prompted, self.stop_requested)
            self.emit(5, self.media_ack)
            wait_for(lambda: self.report["network_prompt_rpc_ok"], self.stop_requested)
            self.emit(6, self.network_ready)
            wait_for(
                lambda: self.report["both_transports_observed_down"],
                self.stop_requested,
            )
            # Simulate one peer message queued during outage, delivered only
            # after a real tunnel recovers. No event bypasses the local socket.
            queued_timestamp_ms = int(time.time() * 1000)
            wait_for(
                lambda: self.report["network_recovery_reply_rpc_ok"],
                self.stop_requested,
            )
            self.emit(7, f"{self.sequence_prefix}-1", timestamp_ms=queued_timestamp_ms)
            for number in range(2, 6):
                self.emit(6 + number, f"{self.sequence_prefix}-{number}")
            self.emit(12, self.network_ack)
        except InterruptedError:
            return
        except BaseException as error:
            self.listener_failures.put_nowait(error)


async def fake_session(cookie: str) -> dict[str, str]:
    if cookie != PRIVATE_COOKIE:
        raise ValueError("Offline worker did not isolate its synthetic credential.")
    return {"FacebookID": "offline-self"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "previous_report",
        "device_path",
        "binary_path",
        "config",
        "output_dir",
    ):
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    parser.add_argument("--target", action="append", type=int, required=True)
    parser.add_argument(
        "--mode", choices=("success", "incomplete", "cancel", "stalled"), required=True
    )
    args = parser.parse_args()
    args.duration = 6.0
    args.cold_timeout = 0.4 if args.mode == "incomplete" else 5.0
    args.network_timeout = 5.0
    args.sample_interval = 0.05
    args.debug_errors = False
    args.challenge = "offline-restart-synthetic-challenge"
    # Never consume an inherited live credential; the only config is test-owned.
    os.environ["FBCHAT_COOKIE"] = PRIVATE_COOKIE
    recovery.dataGetHome = fake_session
    adapter = SocketAdapter([("127.0.0.1", port) for port in args.target])
    worker = OfflineCanary(args, adapter)
    signal.signal(signal.SIGINT, lambda *_: worker.stop_requested.set())
    signal.signal(signal.SIGTERM, lambda *_: worker.stop_requested.set())
    if args.mode == "stalled":
        # Deliberately uncooperative test process: only the controller's bounded
        # owned-process cleanup may stop it. No thread or external process exists.
        worker.start_listener()
        worker.save()
        threading.Event().wait()
        return 99
    return worker.run()


if __name__ == "__main__":
    raise SystemExit(main())
