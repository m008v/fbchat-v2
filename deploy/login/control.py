"""Dịch vụ trình duyệt đăng nhập Facebook theo yêu cầu (trang "Tài khoản kênh").

Chạy thường trực nhưng chỉ bật Chromium/noVNC khi gateway yêu cầu:
  POST   /session  {"account": "<tên>", "target": "facebook" | "fbweb"}
                                          -> chạy extract_cookie.py (FORCE_LOGIN=1)
  GET    /session                         -> {"account", "target", "status", "message"}
  DELETE /session                         -> dừng phiên đang chạy
noVNC (cổng 6080) chỉ tồn tại khi có phiên; gateway proxy nó sau khi kiểm tra quyền
admin Libredesk. Mỗi lúc một phiên (một màn hình ảo), hồ sơ Chromium được xoá trước
mỗi phiên để tài khoản sau không nhận nhầm cookie của tài khoản trước.
target "facebook" (mặc định) ghi cookie cho fb-bot (/data/accounts/<tên>), "fbweb"
ghi cho agent Fanpage Web (FBWEB_LOGINS_DIR/<tên>, volume riêng; omnichannel D18).
Không bao giờ in cookie ra log.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PORT = int(os.environ.get("CONTROL_PORT", "6079"))
TOKEN = os.environ.get("GATEWAY_TOKEN", "")
SCRIPT = Path(__file__).with_name("extract_cookie.py")
PROFILE_DIR = Path(os.environ.get("CHROMIUM_PROFILE", "/tmp/chromium-profile"))
ACCOUNT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
MAX_BODY = 4096
VNC_PORT = 6080
FBWEB_LOGINS_DIR = Path(os.environ.get("FBWEB_LOGINS_DIR", "/fbweb"))
TARGETS = ("facebook", "fbweb")

_lock = threading.Lock()
_proc: subprocess.Popen[bytes] | None = None
_state: dict[str, Any] = {
    "account": "",
    "target": "facebook",
    "status": "idle",
    "message": "",
    "at": 0.0,
}


def log(message: str) -> None:
    print(f"[control] {message}", flush=True)


def _set(
    status: str, message: str, account: str | None = None, target: str | None = None
) -> None:
    if account is not None:
        _state["account"] = account
    if target is not None:
        _state["target"] = target
    _state.update(status=status, message=message, at=time.time())


# extract_cookie.py in dòng này khi thấy c_user/xs và đóng Chromium để ghi cookie
# (~30 giây, noVNC hiện "Aw, Snap!"): giao diện ẩn trình duyệt và báo đang lưu.
LOGIN_DETECTED_MARKER = "Đã phát hiện đăng nhập"


def _watch(proc: subprocess.Popen[bytes], account: str) -> None:
    assert proc.stdout is not None
    for raw in proc.stdout:  # log của extract_cookie.py (không chứa cookie)
        line = raw.decode("utf-8", "replace").rstrip()
        print(line, flush=True)
        if LOGIN_DETECTED_MARKER in line:
            with _lock:
                if _proc is proc and _state["status"] == "running":
                    _set("saving", "Đã đăng nhập, đang lưu cookie (khoảng 30 giây)...")
    code = proc.wait()
    with _lock:
        if _proc is not proc:
            return  # đã bị dừng/thay bằng phiên khác
        if code == 0:
            _set("success", "Đã lấy được cookie, tài khoản đang kết nối.")
            log(f"Phiên {account}: đăng nhập thành công.")
        elif _state["status"] != "cancelled":
            _set(
                "error",
                f"Phiên đăng nhập kết thúc (mã {code}), có thể đã hết thời gian.",
            )
            log(f"Phiên {account}: kết thúc với mã {code}.")
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)


def _vnc_ready() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", VNC_PORT), timeout=0.5):
            return True
    except OSError:
        return False


def snapshot() -> dict[str, Any]:
    """Trạng thái hiện tại; "starting" tới khi noVNC nhận kết nối (iframe tải
    trước lúc đó sẽ nhận trang lỗi và không tự tải lại)."""
    with _lock:
        state = dict(_state)
    if state["status"] == "running" and not _vnc_ready():
        state.update(status="starting", message="Đang mở trình duyệt...")
    return state


def start(account: str, target: str = "facebook") -> tuple[int, dict[str, Any]]:
    global _proc
    with _lock:
        running = _proc is not None and _proc.poll() is None
        if running and (_state["account"], _state["target"]) != (account, target):
            return 409, {"error": f"Đang có phiên đăng nhập cho {_state['account']}."}
        if not running:
            shutil.rmtree(PROFILE_DIR, ignore_errors=True)
            env = {**os.environ, "ACCOUNT": account, "FORCE_LOGIN": "1"}
            if target == "fbweb":
                if not FBWEB_LOGINS_DIR.is_dir():
                    return 501, {
                        "error": "Chưa gắn volume phiên Fanpage Web cho fb-login-ui."
                    }
                env["CONFIG_PATH"] = str(FBWEB_LOGINS_DIR / account / "config.json")
            _proc = subprocess.Popen(
                [sys.executable, str(SCRIPT)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            _set(
                "running",
                "Đăng nhập Facebook trong khung trình duyệt.",
                account,
                target,
            )
            threading.Thread(target=_watch, args=(_proc, account), daemon=True).start()
            log(f"Bắt đầu phiên đăng nhập cho {account}.")
    # Ngoài khóa: snapshot() tự lấy khóa.
    return (200 if running else 202), snapshot()


def stop() -> dict[str, Any]:
    with _lock:
        if _proc is not None and _proc.poll() is None:
            _set("cancelled", "Đã huỷ phiên đăng nhập.")
            _proc.send_signal(signal.SIGTERM)
            try:
                _proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                _proc.kill()
            log(f"Đã huỷ phiên của {_state['account']}.")
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)
        return dict(_state)


class Handler(BaseHTTPRequestHandler):
    server_version = "fb-login-control"

    def log_message(self, *_: Any) -> None:  # không log URL/header
        pass

    def _reply(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        ok = len(TOKEN) >= 32 and hmac.compare_digest(
            self.headers.get("Authorization", ""), f"Bearer {TOKEN}"
        )
        if not ok:
            self._reply(401, {"error": "unauthorized"})
        return ok

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/session":
            return self._reply(404, {"error": "not found"})
        if self._authorized():
            self._reply(200, snapshot())

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/session":
            return self._reply(404, {"error": "not found"})
        if not self._authorized():
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._reply(413, {"error": "too large"})
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._reply(400, {"error": "invalid json"})
        account = payload.get("account") if isinstance(payload, dict) else None
        if not isinstance(account, str) or not ACCOUNT_PATTERN.match(account):
            return self._reply(400, {"error": "Tên tài khoản không hợp lệ."})
        target = payload.get("target") or "facebook"
        if target not in TARGETS:
            return self._reply(400, {"error": "target không hợp lệ."})
        self._reply(*start(account, target))

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path != "/session":
            return self._reply(404, {"error": "not found"})
        if self._authorized():
            self._reply(200, stop())


def main() -> int:
    if len(TOKEN) < 32:
        log("GATEWAY_TOKEN phải dài ít nhất 32 ký tự.")
        return 1
    signal.signal(signal.SIGTERM, lambda *_: (stop(), sys.exit(0)))
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log(f"Chờ yêu cầu đăng nhập tại :{PORT}/session")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
