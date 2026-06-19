"""
fbchat-v2 :: _listening_e2ee.py
================================

Lắng nghe tin nhắn Facebook Messenger có giải mã E2EE (Secret Conversations /
Labyrinth) bằng cách giao tiếp với binary Go `fbchat-bridge-e2ee` qua
stdin/stdout (line-delimited JSON-RPC).

Ưu điểm so với phiên bản ctypes/dll:
- Không cần thư mục `meta-messenger.js/` tồn tại trong workspace.
- Không cần load shared library bằng ctypes (an toàn hơn — bridge crash không
  kéo Python crash theo).
- Bridge có thể được phân phối dưới dạng .exe đơn lẻ.

Cách build binary (1 lần):
    cd fbchat-v2/bridge-e2ee
    git clone https://github.com/mautrix/meta.git ./meta
    go mod tidy
    go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee.exe .

Override đường dẫn binary bằng env: FBCHAT_E2EE_BIN=/path/to/binary

Tại sao không pure Python?
--------------------------
Giải mã E2EE Messenger cần Signal Protocol (Curve25519, Double Ratchet, Sender
Keys, AES-GCM, HKDF, Noise XX) + giao thức nội bộ Meta (Labyrinth /
Lightspeed). Tổng cộng ~100k LOC Go đã được audit, không có lib Python tương
đương. Tự re-implement = rủi ro bảo mật cao + bảo trì không nổi khi Meta đổi
giao thức.

Author: MinhHuyDev
"""

from __future__ import annotations

import datetime
import itertools
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Optional

from _core._utils import parse_cookie_string

# ---------------------------------------------------------------------------
# Binary discovery
# ---------------------------------------------------------------------------

def _default_binary_path() -> Path:
    name = "fbchat-bridge-e2ee.exe" if sys.platform.startswith("win") else "fbchat-bridge-e2ee"
    here = Path(__file__).resolve()
    # fbchat-v2/src/_messaging/_listening_e2ee.py -> fbchat-v2/build/<name>
    return here.parents[2] / "build" / name


def _resolve_binary() -> Path:
    override = os.environ.get("FBCHAT_E2EE_BIN")
    candidate = Path(override) if override else _default_binary_path()
    if not candidate.exists():
        raise FileNotFoundError(
            f"Không tìm thấy bridge binary tại {candidate}.\n"
            f"Chạy: cd fbchat-v2/bridge-e2ee && go build -o ../build/{candidate.name} .\n"
            f"Hoặc set env FBCHAT_E2EE_BIN."
        )
    return candidate


# ---------------------------------------------------------------------------
# Subprocess RPC client
# ---------------------------------------------------------------------------

class BridgeError(RuntimeError):
    """Bridge trả về `ok:false` hoặc lỗi truyền tải."""


class _BridgeProcess:
    """RPC client cho fbchat-bridge-e2ee.

    - Một luồng đọc stdout, phân phối response theo `id` về caller hoặc đẩy
      event vào `events` queue.
    - `call(method, params)` block tới khi nhận response.
    """

    def __init__(self, binary: Path, *, log_stderr: bool = True) -> None:
        self.events: "Queue[dict[str, Any]]" = Queue()
        self._next_id = itertools.count(1)
        self._pending: dict[int, Queue] = {}
        self._lock = threading.Lock()
        self._closed = False

        self._proc = subprocess.Popen(
            [str(binary)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

        if log_stderr:
            self._stderr_thread = threading.Thread(
                target=self._drain_stderr, daemon=True
            )
            self._stderr_thread.start()

    # ------------------------------------------------------------------
    def _drain_stderr(self) -> None:
        assert self._proc.stderr is not None
        for raw in self._proc.stderr:
            try:
                line = raw.decode("utf-8", errors="replace").rstrip()
            except Exception:  # noqa: BLE001
                continue
            print(f"[bridge stderr] {line}", file=sys.stderr)

    def _read_loop(self) -> None:
        assert self._proc.stdout is not None
        for raw in self._proc.stdout:
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"[bridge] bad json: {exc} :: {raw!r}", file=sys.stderr)
                continue

            if "event" in msg:
                self.events.put(msg["event"])
                continue

            mid = msg.get("id")
            with self._lock:
                q = self._pending.pop(mid, None)
            if q is not None:
                q.put(msg)

        self._closed = True
        with self._lock:
            for q in self._pending.values():
                q.put({"ok": False, "error": "bridge exited"})
            self._pending.clear()
        self.events.put({"type": "closed"})

    # ------------------------------------------------------------------
    def call(self, method: str, params: Optional[dict] = None,
             timeout: float = 60.0) -> dict[str, Any]:
        if self._closed or self._proc.poll() is not None:
            raise BridgeError("bridge process is not running")

        rid = next(self._next_id)
        q: Queue = Queue(maxsize=1)
        with self._lock:
            self._pending[rid] = q

        payload = {"id": rid, "method": method, "params": params or {}}
        line = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        assert self._proc.stdin is not None
        try:
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            with self._lock:
                self._pending.pop(rid, None)
            raise BridgeError(f"write failed: {exc}") from exc

        try:
            resp = q.get(timeout=timeout)
        except Empty:
            with self._lock:
                self._pending.pop(rid, None)
            raise BridgeError(f"{method} timed out after {timeout}s")

        if not resp.get("ok"):
            raise BridgeError(f"{method}: {resp.get('error', 'unknown')}")
        return resp.get("data") or {}

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self.call("disconnect", timeout=5)
            except BridgeError:
                pass
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._closed = True


# ---------------------------------------------------------------------------
# Cookie helper
# ---------------------------------------------------------------------------

_REQUIRED_COOKIES = ("c_user", "xs", "datr", "fr")

# ---------------------------------------------------------------------------
# Public listener — API tương thích với _listening.py
# ---------------------------------------------------------------------------

class listeningE2EEEvent:
    """Lắng nghe tin nhắn (regular + E2EE).

    Tương thích với `listeningEvent` của _listening.py:
        l = listeningE2EEEvent(dataFB)
        l.connect_mqtt()       # blocking, giữ tên cũ cho tương thích

    Bổ sung:
        @l.on_message
        def handler(evt: dict): ...

        l.send_e2ee_message(chat_jid, "pong",
                            reply_to_id=..., reply_to_sender_jid=...)
    """

    def __init__(self, dataFB: dict, *, log_level: str = "none",
                 device_path: Optional[str] = None,
                 e2ee_memory_only: bool = True,
                 enable_e2ee: bool = True,
                 binary_path: Optional[str] = None) -> None:
        self.dataFB = dataFB
        self.log_level = log_level
        self.device_path = device_path
        self.e2ee_memory_only = e2ee_memory_only
        self.enable_e2ee = enable_e2ee
        self._binary_path_override = binary_path

        self._on_message = None
        self._bridge: Optional[_BridgeProcess] = None
        self._stop = threading.Event()

        self.bodyResults = self._fresh_body()
        self.e2eeBodyResults: dict[str, Any] = {"chatJid": None, "senderJid": None}

        # Compat fields. Do not fetch the full inbox/thread list here: it can
        # block bridge startup for a long time and is not needed by the E2EE RPC listener.
        self.fbt: dict[str, Any] = {}
        self.lastSeqID = None
        self.syncToken = None

    # ------------------------------------------------------------------
    @staticmethod
    def _fresh_body() -> dict[str, Any]:
        return {
            "body": None,
            "timestamp": 0,
            "userID": 0,
            "messageID": None,
            "replyToID": 0,
            "type": None,
            "attachments": {"id": 0, "url": None},
            "mentions": [],
        }

    def on_message(self, fn: Callable[[dict], None]) -> Callable[[dict], None]:
        self._on_message = fn
        return fn

    def get_last_seq_id(self):
        self.lastSeqID = self.fbt.get("last_seq_id")
        print(f"[{datetime.datetime.now()}] last_seq_id: {self.lastSeqID}")
        return self.lastSeqID

    # ------------------------------------------------------------------
    def _build_cookie_dict(self) -> dict[str, str]:
        cks = parse_cookie_string(self.dataFB["cookieFacebook"])
        missing = [c for c in _REQUIRED_COOKIES if c not in cks]
        if missing:
            raise ValueError(
                f"Thiếu cookie bắt buộc cho E2EE bridge: {missing}. "
                f"Cookie hiện có: {list(cks)}"
            )
        keep = {"c_user", "xs", "datr", "fr", "sb", "wd", "presence"}
        return {k: v for k, v in cks.items() if k in keep}

    # ------------------------------------------------------------------
    def connect_mqtt(self) -> None:
        """Khởi động bridge subprocess + connect Messenger (blocking poll loop)."""
        binary = (
            Path(self._binary_path_override)
            if self._binary_path_override else _resolve_binary()
        )

        self._bridge = _BridgeProcess(binary)

        cfg: dict[str, Any] = {
            "cookies": self._build_cookie_dict(),
            "platform": "facebook",
            "logLevel": self.log_level,
            "e2eeMemoryOnly": self.e2ee_memory_only,
        }
        if self.device_path:
            cfg["devicePath"] = self.device_path

        self._bridge.call("newClient", cfg)
        info = self._bridge.call("connect", timeout=120)
        user = info.get("user", {})
        print(f"[{datetime.datetime.now()}] Logged in as "
              f"{user.get('name')} ({user.get('id')})")

        if self.enable_e2ee:
            try:
                self._bridge.call("connectE2EE", timeout=60)
                print(f"[{datetime.datetime.now()}] E2EE connected")
            except BridgeError as exc:
                print(f"[{datetime.datetime.now()}] E2EE connect failed: {exc}")

        self._poll_loop()

    def stop(self) -> None:
        self._stop.set()
        if self._bridge is not None:
            self._bridge.close()
            self._bridge = None

    # ------------------------------------------------------------------
    def _poll_loop(self) -> None:
        assert self._bridge is not None
        try:
            while not self._stop.is_set():
                try:
                    evt = self._bridge.events.get(timeout=1.0)
                except Empty:
                    continue
                if evt.get("type") == "closed":
                    print(f"[{datetime.datetime.now()}] bridge closed")
                    break
                self._dispatch(evt)
        finally:
            self.stop()

    # ------------------------------------------------------------------
    def _dispatch(self, evt: dict[str, Any]) -> None:
        etype = evt.get("type")
        data = evt.get("data") or {}

        if etype == "message":
            self._populate_regular(data)
        elif etype == "e2eeMessage":
            self._populate_e2ee(data)
        elif etype == "ready":
            print(f"[{datetime.datetime.now()}] ready: "
                  f"isNewSession={data.get('isNewSession')}")
        elif etype == "e2eeConnected":
            print(f"[{datetime.datetime.now()}] e2eeConnected")
        elif etype == "disconnected":
            print(f"[{datetime.datetime.now()}] disconnected: {data}")
        elif etype == "error":
            print(f"[{datetime.datetime.now()}] bridge error: {data}")

        if self._on_message:
            try:
                self._on_message(evt)
            except Exception as exc:  # noqa: BLE001
                print(f"[{datetime.datetime.now()}] handler raised: {exc}")

    def _populate_regular(self, msg: dict[str, Any]) -> None:
        body = self._fresh_body()
        body["body"] = msg.get("text")
        body["timestamp"] = msg.get("timestampMs", 0)
        body["userID"] = msg.get("senderId", 0)
        body["messageID"] = msg.get("id")
        body["replyToID"] = msg.get("threadId", 0)
        body["type"] = "thread"
        body["mentions"] = msg.get("mentions", [])

        atts = msg.get("attachments") or []
        if atts:
            first = atts[0]
            body["attachments"]["id"] = first.get("stickerId") or first.get("fileSize") or 0
            body["attachments"]["url"] = first.get("url") or first.get("previewUrl")

        self.bodyResults = body
        self.e2eeBodyResults = {"chatJid": None, "senderJid": None}

    def _populate_e2ee(self, msg: dict[str, Any]) -> None:
        body = self._fresh_body()
        body["body"] = msg.get("text")
        body["timestamp"] = msg.get("timestampMs", 0)
        body["userID"] = msg.get("senderId", 0)
        body["messageID"] = msg.get("id")
        body["replyToID"] = msg.get("threadId", 0)
        body["type"] = "e2ee"
        body["mentions"] = msg.get("mentions", [])

        atts = msg.get("attachments") or []
        if atts:
            first = atts[0]
            body["attachments"]["id"] = first.get("stickerId") or 0
            body["attachments"]["url"] = first.get("url") or first.get("previewUrl")

        self.bodyResults = body
        self.e2eeBodyResults = {
            "chatJid": msg.get("chatJid"),
            "senderJid": msg.get("senderJid"),
        }

    # ------------------------------------------------------------------
    # Helper sender APIs
    def send_message(self, thread_id: int, text: str,
                     reply_to_id: str = "") -> dict[str, Any]:
        if self._bridge is None:
            raise RuntimeError("Chưa kết nối — gọi connect_mqtt() trước.")
        opts: dict[str, Any] = {"threadId": thread_id, "text": text}
        if reply_to_id:
            opts["replyToId"] = reply_to_id
        return self._bridge.call("sendMessage", opts)

    def send_e2ee_message(self, chat_jid: str, text: str,
                          reply_to_id: str = "",
                          reply_to_sender_jid: str = "") -> dict[str, Any]:
        if self._bridge is None:
            raise RuntimeError("Chưa kết nối — gọi connect_mqtt() trước.")
        return self._bridge.call("sendE2EEMessage", {
            "chatJid": chat_jid,
            "text": text,
            "replyToId": reply_to_id,
            "replyToSenderJid": reply_to_sender_jid,
        })


