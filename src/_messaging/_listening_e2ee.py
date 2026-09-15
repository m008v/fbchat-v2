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

import asyncio
import datetime
import hashlib
import hmac
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any, Optional, TypeGuard
from urllib.parse import unquote, urlparse

import httpx

from _core import __version__ as _PACKAGE_VERSION
from _core._console import safe_print as _safe_print
from _core._utils import parse_cookie_string
from _messaging._bridge_checksums import BRIDGE_RELEASE_VERSION, BRIDGE_SHA256

# ---------------------------------------------------------------------------
# Binary discovery
# ---------------------------------------------------------------------------


_MAX_BRIDGE_SIZE = 200 * 1024 * 1024
_RELEASE_VERSION_PATTERN = re.compile(r"[0-9A-Za-z][0-9A-Za-z._+-]*")
_TRUSTED_DOWNLOAD_HOSTS = {
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
_SOURCE_BRIDGE_MODULE_FILES = (
    "go.mod",
    "go.sum",
    "meta/go.mod",
    "meta/go.sum",
)
_SOURCE_BRIDGE_EMBED_PATTERNS = (
    "meta/pkg/metadb/*.sql",
    "meta/pkg/connector/example-config.yaml",
    "meta/pkg/messagix/bloks/minify.json",
    "meta/pkg/messagix/bloks/debug_captcha.png",
    "meta/pkg/messagix/bloks/debug_captcha.ogg",
)
_BRIDGE_PROTOCOL_VERSION = 1
_BRIDGE_REQUIRED_CAPABILITIES = frozenset(
    {"newClient", "connect", "connectE2EE", "isConnected", "events"}
)
_BRIDGE_STATE_EVENT = "__bridge_state__"
DELIVERY_STATUS_UNKNOWN = "unknown"


def _is_valid_bridge_event(event: object) -> TypeGuard[dict[str, Any]]:
    """Validate the JSON event contract before it reaches user callbacks."""
    if not isinstance(event, dict):
        return False
    event_type = event.get("type")
    timestamp = event.get("timestamp")
    data = event.get("data")
    return (
        isinstance(event_type, str)
        and bool(event_type)
        and "data" in event
        and (data is None or isinstance(data, dict))
        and type(timestamp) is int
        and timestamp >= 0
    )


def _binary_name() -> str:
    name = (
        "fbchat-bridge-e2ee.exe"
        if sys.platform.startswith("win")
        else "fbchat-bridge-e2ee"
    )
    return name


def _default_binary_path() -> Path:
    name = _binary_name()
    here = Path(__file__).resolve()
    project_root = here.parents[2]
    if _is_source_checkout():
        return project_root / "build" / name

    if sys.platform.startswith("win"):
        cache_root = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    else:
        cache_root = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))
    return cache_root / "fbchat-v2" / "bridge" / f"v{_PACKAGE_VERSION}" / name


def _is_source_checkout() -> bool:
    return (Path(__file__).resolve().parents[2] / "pyproject.toml").is_file()


def _expected_package_version() -> str:
    """Resolve version from the checkout instead of stale installed metadata."""
    if _is_source_checkout():
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        match = re.search(
            r'^version\s*=\s*"([0-9A-Za-z][0-9A-Za-z._+-]*)"\s*$',
            pyproject.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        if match is None:
            raise RuntimeError("Không đọc được phiên bản bridge từ pyproject.toml.")
        return match.group(1)
    return _PACKAGE_VERSION


def _source_bridge_inputs() -> list[Path]:
    """Liệt kê source/asset có thể làm thay đổi bridge được build."""
    bridge_root = Path(__file__).resolve().parents[2] / "bridge-e2ee"
    inputs = {
        path
        for path in bridge_root.rglob("*.go")
        if path.is_file() and not path.name.endswith("_test.go")
    }
    for relative_path in _SOURCE_BRIDGE_MODULE_FILES:
        path = bridge_root / relative_path
        if path.is_file():
            inputs.add(path)
    for pattern in _SOURCE_BRIDGE_EMBED_PATTERNS:
        inputs.update(path for path in bridge_root.glob(pattern) if path.is_file())
    return sorted(inputs)


def _source_bridge_is_stale(binary: Path) -> bool:
    """So mtime để chặn source checkout vô tình chạy build cũ."""
    binary_mtime = binary.stat().st_mtime_ns
    source_inputs = _source_bridge_inputs()
    if not source_inputs:
        return True
    for source_path in source_inputs:
        try:
            if source_path.stat().st_mtime_ns > binary_mtime:
                return True
        except FileNotFoundError:
            # File bị đổi/xóa đồng thời; coi build là cũ để fail closed.
            return True
    return False


def _release_version_and_digest(binary_name: str) -> tuple[str, str]:
    package_version = (
        _PACKAGE_VERSION if BRIDGE_RELEASE_VERSION else _expected_package_version()
    )
    release_version = BRIDGE_RELEASE_VERSION or package_version
    if not _RELEASE_VERSION_PATTERN.fullmatch(release_version):
        raise RuntimeError("Phiên bản package không hợp lệ để tải bridge an toàn.")
    if BRIDGE_RELEASE_VERSION and BRIDGE_RELEASE_VERSION != package_version:
        raise RuntimeError(
            "Bảng checksum bridge không khớp phiên bản package đang cài đặt."
        )

    expected_sha256 = (
        (os.environ.get("FBCHAT_E2EE_SHA256") or BRIDGE_SHA256.get(binary_name) or "")
        .strip()
        .lower()
    )
    if expected_sha256.startswith("sha256:"):
        expected_sha256 = expected_sha256.partition(":")[2]
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise RuntimeError(
            "Thiếu checksum SHA-256 tin cậy cho bridge. Hãy tự build, đặt "
            "FBCHAT_E2EE_BIN hoặc cung cấp FBCHAT_E2EE_SHA256 từ nguồn độc lập."
        )
    return release_version, expected_sha256


def _validate_https_download_url(url: str) -> None:
    parsed_url = urlparse(url)
    hostname = (parsed_url.hostname or "").lower()
    try:
        port = parsed_url.port
    except ValueError as error:
        raise RuntimeError("Release trả về URL tải bridge không hợp lệ.") from error
    if (
        parsed_url.scheme != "https"
        or hostname not in _TRUSTED_DOWNLOAD_HOSTS
        or port not in (None, 443)
        or parsed_url.username is not None
        or parsed_url.password is not None
    ):
        raise RuntimeError("Release trả về URL tải bridge không hợp lệ.")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(64 * 1024), b""):
            total += len(chunk)
            if total > _MAX_BRIDGE_SIZE:
                raise RuntimeError("Bridge vượt quá giới hạn 200 MiB.")
            digest.update(chunk)
    if total == 0:
        raise RuntimeError("Bridge rỗng.")
    return digest.hexdigest()


def _platform_bridge_asset() -> tuple[str, str]:
    import platform

    system = platform.system().lower()
    machine = platform.machine().lower()
    if system not in {"darwin", "linux", "windows"}:
        raise RuntimeError(f"Hệ điều hành không được hỗ trợ để tự động tải: {system}")
    architecture = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine)
    if architecture is None:
        raise RuntimeError(f"Kiến trúc không được hỗ trợ để tự động tải: {machine}")
    if system == "windows" and architecture == "arm64":
        raise RuntimeError("Windows ARM64 không có sẵn prebuilt binary. Hãy tự build.")

    goos = system
    goarch = architecture
    binary_name = f"fbchat-bridge-e2ee-{goos}-{goarch}"
    if goos == "windows":
        binary_name += ".exe"
    return binary_name, goos


def _verify_managed_binary(path: Path) -> None:
    import stat

    binary_name, _ = _platform_bridge_asset()
    _, expected_sha256 = _release_version_and_digest(binary_name)
    if not hmac.compare_digest(_sha256_file(path), expected_sha256):
        raise RuntimeError("Checksum SHA-256 của bridge cache không khớp package.")
    if os.name != "nt":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


def _download_bridge(target_path: Path) -> None:
    import logging
    import stat

    logger = logging.getLogger("fbchat")
    binary_name, goos = _platform_bridge_asset()
    release_version, expected_sha256 = _release_version_and_digest(binary_name)

    logger.info(
        "Đang tải bridge E2EE %s từ release v%s...",
        binary_name,
        release_version,
    )

    release_tag = f"v{release_version}"
    api_url = (
        f"https://api.github.com/repos/MinhHuyDev/fbchat-v2/releases/tags/{release_tag}"
    )
    temporary_path: Path | None = None
    try:
        resp = httpx.get(api_url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        for redirect in [*getattr(resp, "history", []), resp]:
            _validate_https_download_url(str(redirect.url))
        release_payload = resp.json()
        if release_payload.get("tag_name") != release_tag:
            raise RuntimeError("GitHub API trả về release tag không khớp package.")
        assets = release_payload.get("assets", [])
        download_url = None
        github_digest = None
        for asset in assets:
            if isinstance(asset, dict) and asset.get("name") == binary_name:
                download_url = asset.get("browser_download_url")
                github_digest = asset.get("digest")
                break

        if not download_url:
            raise RuntimeError(
                f"Không tìm thấy {binary_name} trên release {release_tag}."
            )

        parsed_url = urlparse(download_url)
        _validate_https_download_url(download_url)
        if (parsed_url.hostname or "").lower() != "github.com":
            raise RuntimeError("GitHub API trả về asset URL không chính thức.")
        expected_path = (
            f"/MinhHuyDev/fbchat-v2/releases/download/{release_tag}/{binary_name}"
        )
        if unquote(parsed_url.path) != expected_path:
            raise RuntimeError("GitHub API trả về asset ngoài release đã pin.")
        if github_digest:
            github_sha256 = str(github_digest).lower().removeprefix("sha256:")
            if not hmac.compare_digest(github_sha256, expected_sha256):
                raise RuntimeError(
                    "Digest trên GitHub Release không khớp checksum trong package."
                )

        target_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(target_path.parent, 0o700)

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target_path.name}.",
            suffix=".download",
            dir=target_path.parent,
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)

        digest = hashlib.sha256()
        downloaded = 0
        with httpx.stream(
            "GET", download_url, timeout=60, follow_redirects=True
        ) as response:
            response.raise_for_status()
            for redirect in [*response.history, response]:
                _validate_https_download_url(str(redirect.url))
            try:
                declared_size = int(response.headers.get("content-length", "0") or 0)
            except (TypeError, ValueError) as error:
                raise RuntimeError("Content-Length của bridge không hợp lệ.") from error
            if declared_size < 0 or declared_size > _MAX_BRIDGE_SIZE:
                raise RuntimeError("Bridge vượt quá giới hạn tải 200 MiB.")
            with temporary_path.open("wb") as file_handle:
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    downloaded += len(chunk)
                    if downloaded > _MAX_BRIDGE_SIZE:
                        raise RuntimeError("Bridge vượt quá giới hạn tải 200 MiB.")
                    digest.update(chunk)
                    file_handle.write(chunk)
                file_handle.flush()
                os.fsync(file_handle.fileno())

        if downloaded == 0:
            raise RuntimeError("Bridge tải về rỗng.")
        if declared_size and downloaded != declared_size:
            raise RuntimeError("Kích thước bridge tải về không khớp Content-Length.")
        if not hmac.compare_digest(digest.hexdigest(), expected_sha256):
            raise RuntimeError("Checksum SHA-256 của bridge không khớp package.")

        if goos != "windows":
            os.chmod(temporary_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        temporary_path.replace(target_path)
        if os.name != "nt":
            directory_fd = os.open(target_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

        logger.info(f"Đã tải thành công bridge E2EE vào {target_path}")
    except Exception as error:
        raise RuntimeError(f"Lỗi khi tải tự động bridge E2EE: {error}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _resolve_binary() -> Path:
    override = os.environ.get("FBCHAT_E2EE_BIN")
    candidate = Path(override) if override else _default_binary_path()
    source_checkout = _is_source_checkout()
    if (
        candidate.exists()
        and not override
        and source_checkout
        and _source_bridge_is_stale(candidate)
    ):
        raise RuntimeError(
            f"Bridge E2EE tại {candidate} cũ hơn mã nguồn. Dừng bot và build lại: "
            f"cd bridge-e2ee && go build -trimpath -o ../build/{candidate.name} ."
        )
    if candidate.exists() and not override and not source_checkout:
        try:
            _verify_managed_binary(candidate)
        except Exception as error:
            import logging

            logging.getLogger("fbchat").warning(
                "Bridge cache không hợp lệ, sẽ tải lại: %s", error
            )
            candidate.unlink()
    if not candidate.exists():
        if override:
            raise FileNotFoundError(
                f"Không tìm thấy bridge binary tại {candidate} (do FBCHAT_E2EE_BIN chỉ định)."
            )
        import logging

        logger = logging.getLogger("fbchat")
        logger.info(f"Không tìm thấy bridge tại {candidate}, tiến hành tải tự động...")
        try:
            _download_bridge(candidate)
        except Exception as e:
            raise FileNotFoundError(
                f"{e}\n"
                f"Vui lòng tự build: cd fbchat-v2/bridge-e2ee && go build -o ../build/{candidate.name} .\n"
                "Hoặc đặt FBCHAT_E2EE_BIN; source checkout chỉ tự tải khi có "
                "FBCHAT_E2EE_SHA256 tin cậy."
            ) from e
    return candidate


# ---------------------------------------------------------------------------
# Subprocess RPC client
# ---------------------------------------------------------------------------


class BridgeError(RuntimeError):
    """Bridge trả về `ok:false` hoặc lỗi truyền tải."""


@dataclass(slots=True)
class _WriteRequest:
    line: bytes
    result: Queue[BaseException | None]
    cancelled: threading.Event


class _BridgeProcess:
    """RPC client cho fbchat-bridge-e2ee.

    - Một luồng đọc stdout, phân phối response theo `id` về caller hoặc đẩy
      event vào `events` queue.
    - `call(method, params)` block tới khi nhận response.
    - Watchdog kiểm tra RPC và transport, rồi respawn theo generation khi bridge
      crash, treo hoặc mất kết nối quá lâu.
    """

    MAX_RETRIES: int = 5
    BASE_BACKOFF: float = 2.0
    HEALTH_INTERVAL: float = 5.0
    HEALTH_RPC_TIMEOUT: float = 5.0
    UNHEALTHY_CHECK_LIMIT: int = 3
    STABLE_UPTIME: float = 60.0
    REGULAR_READY_TIMEOUT: float = 90.0
    E2EE_READY_TIMEOUT: float = 60.0
    CONNECTION_POLL_INTERVAL: float = 0.25
    CLOSE_WRITE_LOCK_TIMEOUT: float = 0.1
    CLOSE_GRACEFUL_TIMEOUT: float = 1.0
    MAX_RPC_REQUEST_BYTES: int = 150 * 1024 * 1024
    MAX_EVENT_QUEUE_SIZE: int = 1000

    def __init__(
        self,
        binary: Path,
        *,
        log_stderr: bool = False,
        command: Sequence[str] | None = None,
    ) -> None:
        self.events: Queue[dict[str, Any]] = Queue(maxsize=self.MAX_EVENT_QUEUE_SIZE)
        self._event_queue_lock = threading.Lock()
        self._dropped_event_count = 0
        self._next_id = itertools.count(1)
        self._pending: dict[int, tuple[int, Queue[dict[str, Any]]]] = {}
        self._pending_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._rpc_condition = threading.Condition()
        self._active_rpc_calls = 0
        self._health_probe_active = False
        self._timed_out_generation: int | None = None
        self._recovery_owner: int | None = None
        self._recovery_depth = 0
        self._closed = False
        self._stop_event = threading.Event()
        self._binary = binary
        self._command = tuple(command) if command is not None else (str(binary),)
        if not self._command:
            raise ValueError("bridge command must not be empty")
        self._log_stderr = log_stderr
        self._generation = 0
        self._proc: subprocess.Popen[bytes]
        self._reader: threading.Thread
        self._stderr_thread: threading.Thread
        self._writer: threading.Thread
        self._writer_queue: Queue[_WriteRequest | None]
        self._watchdog_thread: threading.Thread | None = None
        self._connect_cfg: dict[str, Any] = {}
        self._enable_e2ee = True

        self._spawn()

    @property
    def dropped_event_count(self) -> int:
        """Số event cũ đã bị loại để giữ queue bridge có giới hạn."""
        with self._event_queue_lock:
            return self._dropped_event_count

    def _enqueue_event(self, event: dict[str, Any]) -> None:
        """Không block reader RPC; khi đầy, loại event cũ nhất.

        Drop-oldest giữ state/event mới nhất và tránh deadlock response RPC.
        Counter cùng log lũy thừa hai tạo telemetry mà không lộ payload hoặc
        tự biến một đợt event storm thành log storm.
        """
        dropped = False
        with self._event_queue_lock:
            while True:
                try:
                    self.events.put_nowait(event)
                    break
                except Full:
                    try:
                        self.events.get_nowait()
                    except Empty:
                        continue
                    self._dropped_event_count += 1
                    dropped = True
            dropped_count = self._dropped_event_count

        if dropped and dropped_count & (dropped_count - 1) == 0:
            _safe_print(
                "[bridge] event queue full; dropped "
                f"{dropped_count} oldest event(s) (payload hidden)",
                file=sys.stderr,
            )

    def _spawn(self) -> int:
        """Spawn một generation mới và gắn reader vào đúng process đó."""
        proc: subprocess.Popen[bytes] | None = None
        started_threads: list[threading.Thread] = []
        try:
            with self._state_lock:
                if self._closed or self._stop_event.is_set():
                    raise BridgeError("bridge process is closing")
                proc = subprocess.Popen(
                    list(self._command),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
                if self._stop_event.is_set():
                    raise BridgeError("bridge process is closing")

                self._generation += 1
                generation = self._generation
                with self._rpc_condition:
                    self._timed_out_generation = None
                self._proc = proc
                self._writer_queue = Queue()
                self._write_lock = threading.Lock()
                self._reader = threading.Thread(
                    target=self._read_loop,
                    args=(proc, generation, self._writer_queue),
                    daemon=True,
                    name=f"bridge-reader-{generation}",
                )
                self._stderr_thread = threading.Thread(
                    target=self._drain_stderr,
                    args=(proc,),
                    daemon=True,
                    name=f"bridge-stderr-{generation}",
                )
                self._writer = threading.Thread(
                    target=self._write_loop,
                    args=(proc, generation, self._writer_queue, self._write_lock),
                    daemon=True,
                    name=f"bridge-writer-{generation}",
                )
                self._reader.start()
                started_threads.append(self._reader)
                self._stderr_thread.start()
                started_threads.append(self._stderr_thread)
                self._writer.start()
                started_threads.append(self._writer)
                return generation
        except BaseException:
            # Popen đã thành công nhưng khởi tạo reader có thể vẫn lỗi (ví dụ
            # runtime từ chối tạo thread). Không được để subprocess mồ côi.
            if proc is not None:
                self._terminate_process(proc, graceful_timeout=0.0)
            for thread in started_threads:
                thread.join(timeout=1.0)
            raise

    # ------------------------------------------------------------------
    def _drain_stderr(self, proc: subprocess.Popen[bytes]) -> None:
        assert proc.stderr is not None
        for raw in proc.stderr:
            try:
                line = raw.decode("utf-8", errors="replace").rstrip()
            except Exception:  # noqa: BLE001
                continue
            if self._log_stderr:
                _safe_print(f"[bridge stderr] {line}", file=sys.stderr)

    @staticmethod
    def _fail_queued_writes(
        requests: Queue[_WriteRequest | None],
        error: BaseException,
    ) -> None:
        while True:
            try:
                queued = requests.get_nowait()
            except Empty:
                return
            if queued is not None and not queued.cancelled.is_set():
                queued.result.put(error)

    def _write_loop(
        self,
        proc: subprocess.Popen[bytes],
        generation: int,
        requests: Queue[_WriteRequest | None],
        write_lock: threading.Lock,
    ) -> None:
        assert proc.stdin is not None
        while True:
            request = requests.get()
            if request is None:
                self._fail_queued_writes(
                    requests, BridgeError("bridge writer is closing")
                )
                return
            if request.cancelled.is_set():
                error = BridgeError("request cancelled before bridge write")
                self._taint_generation(proc, generation)
                request.result.put(error)
                self._fail_queued_writes(requests, error)
                return
            if self._stop_event.is_set() or not self._is_current_generation(
                proc, generation
            ):
                error = BridgeError("bridge generation changed before request write")
                request.result.put(error)
                self._fail_queued_writes(requests, error)
                return
            try:
                with write_lock:
                    if request.cancelled.is_set():
                        raise BridgeError("request cancelled before bridge write")
                    if self._stop_event.is_set() or not self._is_current_generation(
                        proc, generation
                    ):
                        raise BridgeError(
                            "bridge generation changed before request write"
                        )
                    remaining = memoryview(request.line)
                    while remaining:
                        if request.cancelled.is_set():
                            raise BridgeError("request cancelled during bridge write")
                        if self._stop_event.is_set() or not self._is_current_generation(
                            proc, generation
                        ):
                            raise BridgeError(
                                "bridge generation changed during request write"
                            )
                        written = proc.stdin.write(remaining)
                        if written is None or written <= 0:
                            raise BridgeError("bridge pipe accepted zero bytes")
                        remaining = remaining[written:]
                    proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError, BridgeError) as exc:
                error = (
                    exc
                    if isinstance(exc, BridgeError)
                    else BridgeError(f"write failed: {exc}")
                )
                self._taint_generation(proc, generation)
                request.result.put(error)
                self._fail_queued_writes(requests, error)
                return
            request.result.put(None)

    def _is_current_generation(
        self, proc: subprocess.Popen[bytes], generation: int
    ) -> bool:
        with self._state_lock:
            return self._proc is proc and self._generation == generation

    def _taint_generation(self, proc: subprocess.Popen[bytes], generation: int) -> None:
        """Fail-fast new RPCs after an uncertain write/response outcome."""
        with self._state_lock:
            if (
                self._proc is not proc
                or self._generation != generation
                or self._stop_event.is_set()
            ):
                return
            with self._rpc_condition:
                self._timed_out_generation = generation
                self._rpc_condition.notify_all()

    def _read_loop(
        self,
        proc: subprocess.Popen[bytes],
        generation: int,
        writer_queue: Queue[_WriteRequest | None],
    ) -> None:
        assert proc.stdout is not None
        try:
            for raw in proc.stdout:
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    detail = (
                        f"{exc} :: {raw!r}" if self._log_stderr else "details hidden"
                    )
                    _safe_print(
                        f"[bridge] bad json ({len(raw)} bytes): {detail}",
                        file=sys.stderr,
                    )
                    continue

                if not isinstance(msg, dict):
                    detail = repr(msg) if self._log_stderr else "details hidden"
                    _safe_print(
                        f"[bridge] expected a JSON object: {detail}", file=sys.stderr
                    )
                    continue

                if "event" in msg:
                    event = msg.get("event")
                    if not _is_valid_bridge_event(event):
                        detail = repr(event) if self._log_stderr else "details hidden"
                        _safe_print(
                            f"[bridge] invalid event shape: {detail}", file=sys.stderr
                        )
                        continue
                    with self._state_lock:
                        if (
                            self._proc is proc
                            and self._generation == generation
                            and not self._stop_event.is_set()
                        ):
                            self._enqueue_event(event)
                    continue

                mid = msg.get("id")
                if type(mid) is not int:
                    continue
                with self._pending_lock:
                    pending = self._pending.get(mid)
                    if pending is not None and pending[0] == generation:
                        self._pending.pop(mid, None)
                    else:
                        pending = None
                if pending is not None:
                    pending[1].put(msg)
        except (OSError, ValueError) as exc:
            detail = str(exc) if self._log_stderr else "details hidden"
            _safe_print(f"[bridge] stdout read failed: {detail}", file=sys.stderr)
        finally:
            self._mark_generation_exited(proc, generation, writer_queue)

    def _mark_generation_exited(
        self,
        proc: subprocess.Popen[bytes],
        generation: int,
        writer_queue: Queue[_WriteRequest | None],
    ) -> None:
        # Mỗi reader giữ queue của chính generation đó. Reader cũ tuyệt đối
        # không được lấy queue global rồi vô tình dừng writer generation mới.
        self._taint_generation(proc, generation)
        writer_queue.put(None)
        self._fail_pending_generation(generation, "bridge exited")
        with self._state_lock:
            if (
                self._proc is proc
                and self._generation == generation
                and not self._stop_event.is_set()
            ):
                self._enqueue_event(
                    {"type": "closed", "data": {"generation": generation}}
                )

    def _fail_pending_generation(self, generation: int, error: str) -> None:
        failed: list[Queue[dict[str, Any]]] = []
        with self._pending_lock:
            for request_id, (request_generation, queue) in list(self._pending.items()):
                if request_generation == generation:
                    self._pending.pop(request_id, None)
                    failed.append(queue)
        for queue in failed:
            queue.put({"ok": False, "error": error})

    def _snapshot_process(self) -> tuple[subprocess.Popen[bytes], int]:
        with self._state_lock:
            if self._closed or self._stop_event.is_set():
                raise BridgeError("bridge process is closing")
            proc = self._proc
            generation = self._generation
            if proc.poll() is not None:
                raise BridgeError("bridge process is not running")
            return proc, generation

    def _begin_recovery_transaction(self) -> None:
        owner = threading.get_ident()
        with self._rpc_condition:
            while (
                (self._recovery_owner is not None and self._recovery_owner != owner)
                or self._health_probe_active
                or (self._recovery_owner is None and self._active_rpc_calls > 0)
            ) and not self._stop_event.is_set():
                self._rpc_condition.wait(timeout=0.1)
            if self._stop_event.is_set():
                raise BridgeError("bridge process is closing")
            self._recovery_owner = owner
            self._recovery_depth += 1

    def _end_recovery_transaction(self) -> None:
        owner = threading.get_ident()
        with self._rpc_condition:
            if self._recovery_owner != owner or self._recovery_depth <= 0:
                raise RuntimeError("bridge recovery transaction ownership mismatch")
            self._recovery_depth -= 1
            if self._recovery_depth == 0:
                self._recovery_owner = None
                self._rpc_condition.notify_all()

    # ------------------------------------------------------------------
    def call_blocking(
        self, method: str, params: Optional[dict] = None, timeout: float = 60.0
    ) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("RPC timeout must be greater than zero")
        deadline = time.monotonic() + timeout
        caller = threading.get_ident()
        with self._rpc_condition:
            while (
                self._health_probe_active
                or (self._recovery_owner is not None and self._recovery_owner != caller)
            ) and not self._stop_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BridgeError(
                        f"{method} timed out waiting for bridge availability"
                    )
                self._rpc_condition.wait(timeout=min(0.1, remaining))
            if self._stop_event.is_set():
                raise BridgeError("bridge process is closing")
            if self._timed_out_generation is not None:
                raise BridgeError(
                    "bridge generation is recovering after an RPC timeout"
                )
            self._active_rpc_calls += 1
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BridgeError(f"{method} timed out waiting for bridge availability")
            return self._call_blocking_impl(method, params, remaining)
        finally:
            with self._rpc_condition:
                self._active_rpc_calls -= 1
                self._rpc_condition.notify_all()

    def _call_blocking_impl(
        self, method: str, params: Optional[dict], timeout: float
    ) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("RPC timeout must be greater than zero")
        deadline = time.monotonic() + timeout
        proc, generation = self._snapshot_process()

        rid = next(self._next_id)
        q: Queue[dict[str, Any]] = Queue(maxsize=1)
        with self._pending_lock:
            self._pending[rid] = (generation, q)

        payload = {"id": rid, "method": method, "params": params or {}}
        try:
            line = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        except (TypeError, ValueError) as exc:
            with self._pending_lock:
                self._pending.pop(rid, None)
            raise BridgeError(f"{method}: request is not JSON serializable") from exc
        if len(line) > self.MAX_RPC_REQUEST_BYTES:
            with self._pending_lock:
                self._pending.pop(rid, None)
            raise BridgeError(f"{method}: request exceeds the 150 MiB JSON-RPC limit")
        write_request = _WriteRequest(
            line=line,
            result=Queue(maxsize=1),
            cancelled=threading.Event(),
        )
        with self._state_lock:
            if (
                self._closed
                or self._stop_event.is_set()
                or self._proc is not proc
                or self._generation != generation
            ):
                with self._pending_lock:
                    self._pending.pop(rid, None)
                raise BridgeError("bridge generation changed before request write")
            # Enqueue cùng critical section với generation validation. Vì Queue
            # không bounded, put không block; close() chỉ có thể xếp sentinel
            # sau mọi request đã được chấp nhận.
            self._writer_queue.put(write_request)
        try:
            write_error = write_request.result.get(
                timeout=max(0.0, deadline - time.monotonic())
            )
        except Empty:
            self._taint_generation(proc, generation)
            write_request.cancelled.set()
            with self._pending_lock:
                self._pending.pop(rid, None)
            raise BridgeError(f"{method} timed out after {timeout}s")
        if write_error is not None:
            with self._pending_lock:
                self._pending.pop(rid, None)
            if isinstance(write_error, BridgeError):
                raise write_error
            raise BridgeError(f"write failed: {write_error}") from write_error

        try:
            resp = q.get(timeout=max(0.0, deadline - time.monotonic()))
        except Empty:
            self._taint_generation(proc, generation)
            with self._pending_lock:
                self._pending.pop(rid, None)
            raise BridgeError(f"{method} timed out after {timeout}s")

        response_ok = resp.get("ok")
        if response_ok is False:
            error = resp.get("error")
            detail = error if isinstance(error, str) and error else "unknown"
            raise BridgeError(f"{method}: {detail}")
        if response_ok is not True:
            raise BridgeError(f"{method}: malformed bridge response status")
        data = resp.get("data")
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise BridgeError(f"{method}: malformed bridge response data")
        return data

    async def call(
        self,
        method: str,
        params: Optional[dict] = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """Chờ JSON-RPC trong worker thread để không chặn event loop."""
        return await asyncio.to_thread(self.call_blocking, method, params, timeout)

    def _validate_contract(self, *, health_probe: bool = False) -> dict[str, Any]:
        call = self._call_blocking_impl if health_probe else self.call_blocking
        hello = call("hello", None, self.HEALTH_RPC_TIMEOUT)
        protocol_version = hello.get("protocolVersion")
        if (
            type(protocol_version) is not int
            or protocol_version != _BRIDGE_PROTOCOL_VERSION
        ):
            raise BridgeError("bridge protocol version is incompatible")
        expected_version = BRIDGE_RELEASE_VERSION or _expected_package_version()
        bridge_version = hello.get("bridgeVersion")
        if not isinstance(bridge_version, str) or bridge_version != expected_version:
            raise BridgeError("bridge binary version does not match the Python package")
        raw_capabilities = hello.get("capabilities")
        if not isinstance(raw_capabilities, list) or not all(
            isinstance(item, str) for item in raw_capabilities
        ):
            raise BridgeError("bridge capabilities are invalid")
        missing = _BRIDGE_REQUIRED_CAPABILITIES.difference(raw_capabilities)
        if missing:
            raise BridgeError("bridge is missing required capabilities")
        return hello

    def _wait_for_connection(self, *, require_e2ee: bool, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        last_status: dict[str, Any] = {}
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                required = "E2EE" if require_e2ee else "regular"
                raise BridgeError(f"{required} connection did not become ready")
            last_status = self.call_blocking(
                "isConnected",
                timeout=min(self.HEALTH_RPC_TIMEOUT, max(0.1, remaining)),
            )
            regular_ready = last_status.get("connected") is True
            e2ee_ready = last_status.get("e2eeConnected") is True
            if regular_ready and (not require_e2ee or e2ee_ready):
                return
            self._stop_event.wait(min(self.CONNECTION_POLL_INTERVAL, remaining))
        raise BridgeError("bridge process is closing")

    def connect_client(
        self, connect_cfg: dict[str, Any], *, enable_e2ee: bool
    ) -> dict[str, Any]:
        """Validate contract and establish every requested transport."""
        self._begin_recovery_transaction()
        try:
            self._validate_contract()
            self.call_blocking("newClient", connect_cfg)
            info = self.call_blocking("connect", timeout=120)
            self._wait_for_connection(
                require_e2ee=False,
                timeout=self.REGULAR_READY_TIMEOUT,
            )
            if enable_e2ee:
                self.call_blocking("connectE2EE", timeout=self.E2EE_READY_TIMEOUT)
                self._wait_for_connection(
                    require_e2ee=True,
                    timeout=self.E2EE_READY_TIMEOUT,
                )
            return info
        finally:
            self._end_recovery_transaction()

    def _probe_health(self) -> bool | None:
        _, generation = self._snapshot_process()
        with self._rpc_condition:
            if self._timed_out_generation == generation:
                raise BridgeError("a bridge RPC timed out")
            if self._active_rpc_calls > 0 or self._recovery_owner is not None:
                return None
            self._health_probe_active = True
        try:
            self._validate_contract(health_probe=True)
            if not self._connect_cfg:
                return True
            status = self._call_blocking_impl(
                "isConnected",
                None,
                self.HEALTH_RPC_TIMEOUT,
            )
            return status.get("connected") is True and (
                not self._enable_e2ee or status.get("e2eeConnected") is True
            )
        finally:
            with self._rpc_condition:
                self._health_probe_active = False
                self._rpc_condition.notify_all()

    # ------------------------------------------------------------------
    # Watchdog — auto-respawn
    # ------------------------------------------------------------------
    def start_watchdog(
        self, connect_cfg: dict[str, Any] | None = None, enable_e2ee: bool = True
    ) -> threading.Thread:
        """Khởi động watchdog thread giám sát subprocess.

        Khi bridge crash, treo RPC hoặc mất kết nối quá lâu, watchdog sẽ:
        1. Dừng generation lỗi và đợi exponential backoff (2s→32s).
        2. Respawn subprocess rồi xác thực protocol/version.
        3. Replay `newClient` + `connect` + `connectE2EE` theo cấu hình.
        4. Chỉ reset retry sau khi generation mới chạy ổn định.
        5. Emit `bridge_fatal` nếu vượt quá MAX_RETRIES.
        """
        with self._state_lock:
            self._connect_cfg = dict(connect_cfg or {})
            if isinstance(self._connect_cfg.get("cookies"), dict):
                self._connect_cfg["cookies"] = dict(self._connect_cfg["cookies"])
            self._enable_e2ee = enable_e2ee
            if self._watchdog_thread is not None and self._watchdog_thread.is_alive():
                return self._watchdog_thread
            if self._closed or self._stop_event.is_set():
                raise BridgeError("cannot start watchdog after bridge close")
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                daemon=True,
                name="bridge-watchdog",
            )
            self._watchdog_thread.start()
            return self._watchdog_thread

    def _watchdog_loop(self) -> None:
        failures = 0
        healthy_since = time.monotonic()
        unhealthy_checks = 0
        while not self._stop_event.is_set():
            if self._stop_event.wait(self.HEALTH_INTERVAL):
                return
            try:
                proc, _ = self._snapshot_process()
                if proc.poll() is not None:
                    raise BridgeError("bridge process exited")
                health = self._probe_health()
                if health is None:
                    continue
                if health:
                    unhealthy_checks = 0
                    if time.monotonic() - healthy_since >= self.STABLE_UPTIME:
                        failures = 0
                    continue
                unhealthy_checks += 1
                if unhealthy_checks < self.UNHEALTHY_CHECK_LIMIT:
                    continue
                raise BridgeError("bridge connection remained unhealthy")
            except BridgeError:
                unhealthy_checks = 0

            recovered, failures = self._recover_process(failures)
            if not recovered:
                return
            healthy_since = time.monotonic()

    def _recover_process(self, failures: int) -> tuple[bool, int]:
        """Replace and replay a generation while external RPC calls are gated."""
        try:
            self._begin_recovery_transaction()
        except BridgeError:
            return False, failures
        try:
            try:
                failed_proc, _ = self._snapshot_process()
            except BridgeError:
                failed_proc = None
            if failed_proc is not None:
                self._terminate_process(failed_proc)
            self._enqueue_event(
                {
                    "type": _BRIDGE_STATE_EVENT,
                    "data": {"connected": False, "e2eeConnected": False},
                }
            )

            while not self._stop_event.is_set():
                failures += 1
                if failures > self.MAX_RETRIES:
                    _safe_print(
                        f"[{datetime.datetime.now()}] Bridge exceeded max retries "
                        f"({self.MAX_RETRIES}). Giving up."
                    )
                    self._enqueue_event(
                        {
                            "type": "bridge_fatal",
                            "error": f"max retries exceeded ({self.MAX_RETRIES})",
                            "retries": self.MAX_RETRIES,
                        }
                    )
                    return False, failures

                backoff = self.BASE_BACKOFF * (2 ** (failures - 1))
                _safe_print(
                    f"[{datetime.datetime.now()}] Bridge unavailable. "
                    f"Respawning in {backoff:.0f}s "
                    f"(attempt {failures}/{self.MAX_RETRIES})"
                )
                if self._stop_event.wait(backoff):
                    return False, failures

                spawned_proc: subprocess.Popen[bytes] | None = None
                try:
                    generation = self._spawn()
                    spawned_proc, _ = self._snapshot_process()
                    if self._connect_cfg:
                        self.connect_client(
                            self._connect_cfg,
                            enable_e2ee=self._enable_e2ee,
                        )
                    else:
                        self._validate_contract()
                    self._enqueue_event(
                        {
                            "type": _BRIDGE_STATE_EVENT,
                            "data": {
                                "connected": bool(self._connect_cfg),
                                "e2eeConnected": bool(
                                    self._connect_cfg and self._enable_e2ee
                                ),
                                "generation": generation,
                            },
                        }
                    )
                    _safe_print(
                        f"[{datetime.datetime.now()}] Respawn successful "
                        f"(attempt {failures})"
                    )
                    return True, failures
                except Exception as exc:  # noqa: BLE001
                    if spawned_proc is not None:
                        self._terminate_process(spawned_proc)
                    detail = str(exc) if self._log_stderr else type(exc).__name__
                    _safe_print(f"[{datetime.datetime.now()}] Respawn failed: {detail}")
            return False, failures
        finally:
            self._end_recovery_transaction()

    def _terminate_process(
        self, proc: subprocess.Popen[bytes], *, graceful_timeout: float = 1.0
    ) -> None:
        with self._state_lock:
            current_proc = getattr(self, "_proc", None)
            generation = self._generation if current_proc is proc else None
            writer_queue = self._writer_queue if current_proc is proc else None
        if writer_queue is not None:
            writer_queue.put(None)
        if proc.poll() is not None:
            if generation is not None:
                self._fail_pending_generation(generation, "bridge terminated")
            return
        try:
            proc.terminate()
            proc.wait(timeout=graceful_timeout)
        except (OSError, subprocess.TimeoutExpired):
            try:
                proc.kill()
            except OSError:
                return
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        finally:
            if generation is not None:
                self._fail_pending_generation(generation, "bridge terminated")

    # ------------------------------------------------------------------
    def close(self) -> None:
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            self._stop_event.set()
            proc = self._proc
            watchdog = self._watchdog_thread
        with self._rpc_condition:
            self._rpc_condition.notify_all()

        with self._state_lock:
            writer_queue = self._writer_queue
            write_lock = self._write_lock
        writer_queue.put(None)

        if proc.poll() is None:
            acquired_write_lock = write_lock.acquire(
                timeout=self.CLOSE_WRITE_LOCK_TIMEOUT
            )
            if acquired_write_lock:
                try:
                    if proc.stdin:
                        proc.stdin.close()
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    write_lock.release()
            else:
                self._terminate_process(proc, graceful_timeout=0.0)
            if proc.poll() is None:
                try:
                    proc.wait(timeout=self.CLOSE_GRACEFUL_TIMEOUT)
                except subprocess.TimeoutExpired:
                    self._terminate_process(proc, graceful_timeout=0.0)

        if watchdog is not None and watchdog is not threading.current_thread():
            watchdog.join(timeout=(2 * self.HEALTH_RPC_TIMEOUT) + 1.0)
        with self._state_lock:
            self._connect_cfg = {}

        failed: list[Queue[dict[str, Any]]] = []
        with self._pending_lock:
            for _, queue in self._pending.values():
                failed.append(queue)
            self._pending.clear()
        for queue in failed:
            queue.put({"ok": False, "error": "bridge closed"})


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

    def __init__(
        self,
        dataFB: dict,
        *,
        log_level: str = "none",
        device_path: Optional[str] = None,
        e2ee_memory_only: bool = True,
        enable_e2ee: bool = True,
        binary_path: Optional[str] = None,
        debug_errors: bool = False,
    ) -> None:
        self.dataFB = dataFB
        self.log_level = log_level
        self.device_path = device_path
        self.e2ee_memory_only = e2ee_memory_only
        self.enable_e2ee = enable_e2ee
        self.debug_errors = debug_errors
        self._binary_path_override = binary_path

        self._on_message: Callable[[dict[str, Any]], None] | None = None
        self._bridge: Optional[_BridgeProcess] = None
        self._lifecycle_lock = threading.Lock()
        self._run_started = False
        self._stop = threading.Event()
        self._startup_done = threading.Event()
        self._connected = threading.Event()
        self._e2ee_connected = threading.Event()
        self._startup_error: BaseException | None = None

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

    def on_message(
        self, fn: Callable[[dict[str, Any]], None]
    ) -> Callable[[dict[str, Any]], None]:
        self._on_message = fn
        return fn

    def get_last_seq_id(self):
        self.lastSeqID = self.fbt.get("last_seq_id")
        _safe_print(f"[{datetime.datetime.now()}] last_seq_id: {self.lastSeqID}")
        return self.lastSeqID

    def wait_until_connected(
        self, timeout: float = 60.0, *, require_e2ee: bool = False
    ) -> bool:
        """Đợi listener handshake xong trước khi gửi/đọc event.

        `connect_mqtt_blocking()` thường chạy trong daemon thread. Nếu caller
        gửi message ngay sau `Thread.start()` thì rất dễ đụng race: bridge mới
        spawn nhưng chưa `connect`/`connectE2EE`, poll loop cũng chưa chạy.
        """
        if timeout < 0:
            raise ValueError("timeout must not be negative")
        deadline = time.monotonic() + timeout
        if not self._startup_done.wait(timeout):
            return False
        if self._startup_error is not None:
            raise RuntimeError(
                "E2EE listener failed to start."
            ) from self._startup_error
        if not self._connected.is_set():
            return False
        if not require_e2ee or not self.enable_e2ee:
            return True
        remaining = max(0.0, deadline - time.monotonic())
        if not self._e2ee_connected.wait(remaining):
            if self._startup_error is not None:
                raise RuntimeError(
                    "E2EE listener failed during E2EE handshake."
                ) from self._startup_error
            return False
        return True

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
    def _claim_run(self) -> None:
        """Claim this single-use listener before mutating lifecycle state."""
        with self._lifecycle_lock:
            if self._run_started or self._stop.is_set():
                raise RuntimeError(
                    "E2EE listener instances are single-use; create a new instance."
                )
            self._run_started = True
            self._startup_error = None
            self._startup_done.clear()
            self._connected.clear()
            self._e2ee_connected.clear()

    def connect_mqtt_blocking(self) -> None:
        """Khởi động bridge subprocess + connect Messenger (blocking poll loop).

        Startup fail closed nếu protocol/version hoặc transport E2EE không sẵn
        sàng. Sau đó watchdog tự động respawn khi subprocess crash/treo/mất kết
        nối, với exponential backoff (2s→32s, tối đa 5 lần).
        """
        self._claim_run()
        bridge: _BridgeProcess | None = None
        try:
            binary = (
                Path(self._binary_path_override)
                if self._binary_path_override
                else _resolve_binary()
            )
            bridge = _BridgeProcess(binary, log_stderr=self.debug_errors)
            with self._lifecycle_lock:
                if self._stop.is_set():
                    raise BridgeError("listener stopped during bridge startup")
                self._bridge = bridge

            cfg: dict[str, Any] = {
                "cookies": self._build_cookie_dict(),
                "platform": "facebook",
                "logLevel": self.log_level,
                "e2eeMemoryOnly": self.e2ee_memory_only,
            }
            if self.device_path:
                cfg["devicePath"] = self.device_path

            info = bridge.connect_client(cfg, enable_e2ee=self.enable_e2ee)
            user = info.get("user", {})
            # Khởi động watchdog — auto-respawn khi bridge crash
            bridge.start_watchdog(connect_cfg=cfg, enable_e2ee=self.enable_e2ee)
            with self._lifecycle_lock:
                if self._bridge is not bridge or self._stop.is_set():
                    raise BridgeError("listener stopped during bridge startup")
                self._connected.set()
                if self.enable_e2ee:
                    self._e2ee_connected.set()
                self._startup_done.set()

            _safe_print(
                f"[{datetime.datetime.now()}] Logged in as "
                f"{user.get('name')} ({user.get('id')})"
            )
            if self.enable_e2ee:
                _safe_print(f"[{datetime.datetime.now()}] E2EE connected")

            self._poll_loop(bridge)
        except BaseException as exc:
            self._startup_error = exc
            self._connected.clear()
            self._e2ee_connected.clear()
            self._startup_done.set()
            self.stop()
            if bridge is not None:
                bridge.close()
            raise

    async def connect_mqtt(self) -> None:
        """Chạy poll loop của bridge ngoài event loop asyncio."""
        await asyncio.to_thread(self.connect_mqtt_blocking)

    def stop(self) -> None:
        self._stop.set()
        self._startup_done.set()
        self._connected.clear()
        self._e2ee_connected.clear()
        with self._lifecycle_lock:
            bridge = self._bridge
            self._bridge = None
        if bridge is not None:
            bridge.close()

    # ------------------------------------------------------------------
    def _poll_loop(self, bridge: _BridgeProcess | None = None) -> None:
        """Event dispatch loop — chỉ lắng nghe và dispatch events.

        Watchdog thread xử lý respawn độc lập, poll loop không cần
        quan tâm đến reconnect logic nữa.
        """
        if bridge is None:
            with self._lifecycle_lock:
                bridge = self._bridge
        if bridge is None:
            raise BridgeError("bridge process is not available")

        recovering = False
        try:
            while not self._stop.is_set():
                try:
                    evt = bridge.events.get(timeout=1.0)
                except Empty:
                    continue

                event_type = evt.get("type")
                if event_type == _BRIDGE_STATE_EVENT:
                    state = evt.get("data") or {}
                    if state.get("connected") is True:
                        self._connected.set()
                        recovering = False
                    else:
                        self._connected.clear()
                        recovering = True
                    if state.get("e2eeConnected") is True:
                        self._e2ee_connected.set()
                    else:
                        self._e2ee_connected.clear()
                    continue

                if event_type == "bridge_fatal":
                    self._connected.clear()
                    self._e2ee_connected.clear()
                    detail = evt.get("error") if self.debug_errors else "details hidden"
                    _safe_print(f"[{datetime.datetime.now()}] bridge_fatal: {detail}")
                    raise BridgeError("bridge watchdog exhausted its retry budget")

                if event_type == "closed":
                    self._connected.clear()
                    self._e2ee_connected.clear()
                    recovering = True
                elif event_type in {"ready", "reconnected"}:
                    if not recovering:
                        self._connected.set()
                elif event_type == "e2eeConnected":
                    if not recovering:
                        self._e2ee_connected.set()
                elif event_type == "disconnected":
                    data = evt.get("data") or {}
                    if data.get("isE2EE") is True:
                        self._e2ee_connected.clear()
                    else:
                        self._connected.clear()
                        self._e2ee_connected.clear()

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
            _safe_print(
                f"[{datetime.datetime.now()}] ready: "
                f"isNewSession={data.get('isNewSession')}"
            )
        elif etype == "e2eeConnected":
            _safe_print(f"[{datetime.datetime.now()}] e2eeConnected")
        elif etype == "disconnected":
            detail = f": {data}" if self.debug_errors else ""
            _safe_print(f"[{datetime.datetime.now()}] disconnected{detail}")
        elif etype == "error":
            detail = str(data) if self.debug_errors else "payload hidden"
            _safe_print(f"[{datetime.datetime.now()}] bridge error ({detail})")

        if self._on_message:
            try:
                self._on_message(evt)
            except Exception as exc:  # noqa: BLE001
                detail = str(exc) if self.debug_errors else "details hidden"
                _safe_print(
                    f"[{datetime.datetime.now()}] handler raised: "
                    f"{type(exc).__name__} ({detail})"
                )

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
            body["attachments"]["id"] = (
                first.get("stickerId") or first.get("fileSize") or 0
            )
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
    def _require_bridge(self) -> _BridgeProcess:
        with self._lifecycle_lock:
            bridge = self._bridge
            stopped = self._stop.is_set()
        if bridge is None or stopped:
            raise RuntimeError("Chưa kết nối — gọi connect_mqtt() trước.")
        return bridge

    def send_message_blocking(
        self, thread_id: int, text: str, reply_to_id: str = ""
    ) -> dict[str, Any]:
        bridge = self._require_bridge()
        opts: dict[str, Any] = {"threadId": thread_id, "text": text}
        if reply_to_id:
            opts["replyToId"] = reply_to_id
        return bridge.call_blocking("sendMessage", opts)

    async def send_message(
        self, thread_id: int, text: str, reply_to_id: str = ""
    ) -> dict[str, Any]:
        bridge = self._require_bridge()
        opts: dict[str, Any] = {"threadId": thread_id, "text": text}
        if reply_to_id:
            opts["replyToId"] = reply_to_id
        return await bridge.call("sendMessage", opts)

    def send_e2ee_message_blocking(
        self,
        chat_jid: str,
        text: str,
        reply_to_id: str = "",
        reply_to_sender_jid: str = "",
    ) -> dict[str, Any]:
        bridge = self._require_bridge()
        return bridge.call_blocking(
            "sendE2EEMessage",
            {
                "chatJid": chat_jid,
                "text": text,
                "replyToId": reply_to_id,
                "replyToSenderJid": reply_to_sender_jid,
            },
        )

    async def send_e2ee_message(
        self,
        chat_jid: str,
        text: str,
        reply_to_id: str = "",
        reply_to_sender_jid: str = "",
    ) -> dict[str, Any]:
        bridge = self._require_bridge()
        return await bridge.call(
            "sendE2EEMessage",
            {
                "chatJid": chat_jid,
                "text": text,
                "replyToId": reply_to_id,
                "replyToSenderJid": reply_to_sender_jid,
            },
        )
