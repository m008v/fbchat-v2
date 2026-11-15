"""Chạy nhiều tài khoản trong một tiến trình Python.

File thuộc phần deploy của fork: chỉ dùng API sẵn có của ``src/main.py`` (kế
thừa ``SimpleBot``, bọc ``main.log``) để không phải sửa file upstream và tránh
conflict khi đồng bộ. ``deploy/tests`` kiểm tra các điểm bám này.

Mỗi tài khoản là một thư mục con của ``FBCHAT_ACCOUNTS_DIR`` (mặc định
``deploy/accounts``) chứa ``config.json`` cùng schema với ``src/config.json``.
Bridge E2EE vẫn là một tiến trình Go riêng cho mỗi tài khoản (bridge chỉ hỗ
trợ một client), nhưng interpreter Python, event loop và ``httpx.AsyncClient``
được dùng chung. Nếu bật lưu trạng thái E2EE ra file, mỗi tài khoản dùng
``<accounts>/<tên>/e2ee_device.json`` riêng.

Tài khoản lỗi được thử lại với backoff và không làm dừng tài khoản khác.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import gc
import json
import os
import re
import shutil
import tempfile
import time
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

import main as upstream_main
from _core._console import configure_utf8_console
from _core._permissions import set_private_file_permissions
from _core._session import dataGetHome
from _core._storage import FileSessionStorage
from _messaging._listening_e2ee import _format_exception_chain
from main import DEFAULT_HTTP_TIMEOUT, SimpleBot, is_valid_datafb

from connection_history import (
    HISTORY_FILE,
    SESSION_CAUSES,
    ConnectionHistory,
    DecryptFailureWatch,
    classify_bridge_error,
    classify_raw_event,
    decrypt_failure,
    decrypt_history_message,
    describe_run_error,
    diagnose_session,
    key_check_message,
    sender_key_message,
)
from gateway_link import (
    META_EVENT_TYPES,
    PRESENCE_EVENT_TYPES,
    GatewayLink,
    undecryptable_message,
)
from session_keeper import keep_session

ACCOUNTS_DIR = Path(
    os.environ.get("FBCHAT_ACCOUNTS_DIR", Path(__file__).resolve().parent / "accounts")
)
ACCOUNT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def only_account(value: str | None = None) -> str:
    """Chế độ một tài khoản (omi, D27: mỗi kênh một pod): BOT_ACCOUNT là tài khoản duy nhất bot
    chạy và nhận lệnh. Trống: mọi tài khoản trong thư mục."""
    name = (os.environ.get("BOT_ACCOUNT", "") if value is None else value).strip()
    if name and not ACCOUNT_NAME_PATTERN.match(name):
        raise ValueError(f"BOT_ACCOUNT không hợp lệ: {name!r}")
    return name


MAX_ATTEMPTS = 5
RETRY_BASE_SECONDS = 30.0
RETRY_MAX_SECONDS = 600.0
# Mất mạng / lỗi kết nối: không bao giờ bỏ tài khoản, thử lại tối đa mỗi 2 phút
# để có mạng lại là tự kết nối (chỉ phiên hết hạn thật mới dừng).
OFFLINE_RETRY_SECONDS = 120.0
FACEBOOK_PROBE_URL = "https://www.facebook.com/robots.txt"
STABLE_AFTER_SECONDS = 600.0
# File trạng thái cho Docker healthcheck; healthy khi mọi tài khoản là "running".
HEALTH_FILE = os.environ.get("FBCHAT_HEALTH_FILE")
BOT_HTTP_PORT = int(os.environ.get("BOT_HTTP_PORT", "7002"))
E2EE_PERSIST = os.environ.get("FBCHAT_E2EE_PERSIST", "1").lower() not in {
    "0",
    "false",
    "no",
}
# Có GATEWAY_URL: tin khách được chuyển tới omnichannel gateway và lệnh /ping...
# bị tắt (đặt BOT_COMMANDS=1 để bật lại).
COMMANDS_FLAG = os.environ.get("BOT_COMMANDS", "").lower() in {"1", "true", "yes"}
# Ghi mọi sự kiện thô của listener (cả loại bot đang bỏ qua, vd. cuộc gọi) để
# debug payload. Chỉ tài khoản thử: tệp có nội dung tin nhắn. Danh sách tên cách
# nhau bởi dấu phẩy; mỗi tài khoản một tệp JSON Lines trong /data/trace, quyền 600.
TRACE_ACCOUNTS = {
    name.strip()
    for name in os.environ.get("FBBOT_TRACE", "").split(",")
    if name.strip()
}
TRACE_DIR = ACCOUNTS_DIR.parent / "trace"
TRACE_MAX_BYTES = 20 << 20
# Tin không giải mã được thường tới lại ngay sau khi bridge xin gửi lại (tin
# nhóm khi bot chưa có khoá nhóm của người gửi): chờ rồi mới đăng tin báo lỗi,
# bỏ nếu tin thật cùng ID đã tới.
UNDECRYPTABLE_GRACE_SECONDS = 15.0
ARRIVED_IDS_MAX = 2048
_gateway: GatewayLink | None = None

_account_states: dict[str, str] = {}
# tên tài khoản -> {"uid", "displayName", "avatar"}: hiển thị ở trang "Tài khoản kênh".
_account_profiles: dict[str, dict[str, str]] = {}
# tên tài khoản -> {"kind", "message"}: lỗi gần nhất, để trang biết cần đăng nhập
# lại ("session_expired") hay chỉ là lỗi kết nối ("connection").
_account_errors: dict[str, dict[str, str]] = {}
# tên tài khoản -> lịch sử kết nối (rớt vì sao, nối lại lúc nào).
_account_history: dict[str, ConnectionHistory] = {}

SESSION_EXPIRED_ATTEMPTS = 2
SESSION_EXPIRED_MESSAGE = (
    "Phiên Facebook đã hết hạn hoặc bị đăng xuất: cần đăng nhập lại."
)


class SessionExpiredError(RuntimeError):
    """Cookie không còn cho ra dataFB: Facebook đã huỷ phiên."""

    def __init__(self, message: str, cause: str = "unknown") -> None:
        super().__init__(message)
        self.cause = cause  # khoá của SESSION_CAUSES


def account_history(name: str, account_dir: Path | None = None) -> ConnectionHistory:
    history = _account_history.get(name)
    if history is None:
        path = account_dir / HISTORY_FILE if account_dir is not None else None
        history = _account_history[name] = ConnectionHistory(path)
    return history


async def facebook_reachable(http_client: httpx.AsyncClient) -> bool:
    """True nếu tới được Facebook (không gửi cookie): phân biệt mất mạng với hết phiên."""
    try:
        await http_client.get(FACEBOOK_PROBE_URL, timeout=10)
    except httpx.HTTPError:
        return False
    return True


def describe_account_error(error: BaseException) -> dict[str, str]:
    if isinstance(error, SessionExpiredError):
        cause = SESSION_CAUSES.get(error.cause, SESSION_CAUSES["unknown"])
        return {
            "kind": "session_expired",
            "message": f"{SESSION_EXPIRED_MESSAGE} Nguyên nhân: {cause}",
            "cause": error.cause,
        }
    return {
        "kind": "connection",
        "message": f"Lỗi kết nối: {_format_exception_chain(error)}"[:200],
    }


# Tên tài khoản gắn vào log; task con và asyncio.to_thread kế thừa context.
LOG_LABEL: contextvars.ContextVar[str] = contextvars.ContextVar(
    "fbchat_log_label", default=""
)
_upstream_log = upstream_main.log


def log(tag: str, message: str) -> None:
    label = LOG_LABEL.get()
    # main.log in "[giờ] [tag] nội dung"; nhét nhãn vào tag để có "[acc] [tag]".
    _upstream_log(f"{label}] [{tag}" if label else tag, message)


class EventTrace:
    """Tệp JSON Lines của FBBOT_TRACE; ngừng ghi khi chạm TRACE_MAX_BYTES."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND | os.O_EXCL, 0o600)
        self._file = os.fdopen(fd, "a", encoding="utf-8")
        self._size = 0
        self.path = path

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()

    def write(self, event: Any) -> None:
        if self._file.closed:
            return
        line = json.dumps(
            {"t": int(time.time() * 1000), "event": event},
            ensure_ascii=False,
            default=str,
        )
        if self._size + len(line) + 1 > TRACE_MAX_BYTES:
            self._file.close()
            return
        self._file.write(line + "\n")
        self._file.flush()
        self._size += len(line) + 1


def open_trace(account: str) -> EventTrace | None:
    if account not in TRACE_ACCOUNTS:
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    try:
        trace = EventTrace(TRACE_DIR / f"{account}-{stamp}.jsonl")
    except OSError as error:
        log("trace", f"không mở được tệp trace: {error}")
        return None
    log("trace", f"ghi sự kiện thô vào {trace.path}")
    return trace


def remove_traces(account: str) -> None:
    """Xoá các tệp trace của một tài khoản vừa gỡ (tên tài khoản-giờ.jsonl)."""
    pattern = re.compile(rf"^{re.escape(account)}-\d{{8}}-\d{{6}}\.jsonl$")
    if not TRACE_DIR.is_dir():
        return
    for path in TRACE_DIR.iterdir():
        if pattern.match(path.name):
            path.unlink(missing_ok=True)


def install_labeled_log() -> None:
    """Cho SimpleBot dùng log có nhãn: hàm của nó tra ``log`` trong main lúc gọi."""
    upstream_main.log = log


def load_account_config(path: Path) -> dict[str, Any]:
    """Đọc config.json của một tài khoản; cùng quy tắc với main.load_config()."""
    set_private_file_permissions(path)
    with path.open("r", encoding="utf-8") as file_handle:
        config = json.load(file_handle)
    if not isinstance(config, dict):
        raise ValueError(f"{path.name} phải là một JSON object.")
    config.setdefault("prefix", "/")
    config.setdefault("admins", [])
    config.setdefault("log_message_content", False)
    config.setdefault("debug_errors", False)
    if not isinstance(config["prefix"], str) or not config["prefix"]:
        raise ValueError("config.prefix phải là chuỗi không rỗng.")
    if not isinstance(config["admins"], list):
        raise ValueError("config.admins phải là một danh sách ID.")
    for flag in ("log_message_content", "debug_errors"):
        if not isinstance(config[flag], bool):
            raise ValueError(f"config.{flag} phải là true hoặc false.")
    return config


class AccountBot(SimpleBot):
    """SimpleBot cho một tài khoản trong tiến trình nhiều tài khoản."""

    def __init__(
        self, dataFB: dict[str, Any], *, account: str, device_path: str, **options: Any
    ) -> None:
        super().__init__(dataFB, **options)
        self.account = account
        # Listener chỉ đọc hai thuộc tính này khi connect. Upstream mặc định giữ
        # trạng thái E2EE trong RAM: mỗi lần restart là một thiết bị E2EE mới và
        # tin đến hay báo "could not be decrypted". Lưu ra file (0600) theo tài khoản.
        self.listener.device_path = device_path
        self.listener.e2ee_memory_only = not E2EE_PERSIST
        self._loop: asyncio.AbstractEventLoop | None = None
        self._reconnecting = False
        self._trace = open_trace(account)
        self._decrypt_watch = DecryptFailureWatch()
        # ID tin thật đã chuyển gateway (chỉ đọc/ghi trên event loop).
        self._arrived_ids: OrderedDict[str, None] = OrderedDict()
        # Tin báo lỗi giải mã đang chờ (chỉ trên event loop): huỷ khi tài khoản dừng,
        # kẻo tài khoản vừa gỡ còn gửi tin vào gateway.
        self._lost_tasks: set[asyncio.Task[None]] = set()
        self._stopped = False

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        try:
            await super().run()
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """Tài khoản dừng: bỏ tin báo lỗi giải mã đang chờ, đóng trace."""
        self._stopped = True
        for task in list(self._lost_tasks):
            task.cancel()
        if self._trace is not None:
            self._trace.close()

    def _spawn_undecryptable(self, lost: dict[str, Any]) -> None:
        """Hẹn đăng tin báo lỗi giải mã (chạy trên event loop)."""
        if self._stopped:
            return
        task = asyncio.create_task(self._forward_undecryptable(lost))
        self._lost_tasks.add(task)
        task.add_done_callback(self._lost_tasks.discard)

    def _log_connection_status(self, status: dict[str, Any]) -> None:
        """Trạng thái kết nối của thư viện (từ 2.3.4 tự nối lại; gọi từ listener thread)."""
        super()._log_connection_status(status)
        if self._loop is not None:
            with contextlib.suppress(RuntimeError):  # loop đã đóng khi đang tắt
                self._loop.call_soon_threadsafe(self._apply_connection_status, status)

    def _apply_connection_status(self, status: dict[str, Any]) -> None:
        # Thư viện tự nối lại thay vì ném lỗi, nên tài khoản phải tự chuyển
        # retrying/running ở đây; lỗi xác thực vẫn làm listener dừng và đi qua
        # supervise_account như trước.
        state = status.get("state")
        if state == "reconnecting" and not self._reconnecting:
            self._reconnecting = True
            set_account_state(self.account, "retrying")
            account_history(self.account).record(
                "network", "Mất kết nối, thư viện đang tự nối lại"
            )
        elif state == "connected" and self._reconnecting:
            self._reconnecting = False
            _mark_running(self.account)

    def _note_arrived(self, message_id: str) -> None:
        self._arrived_ids[message_id] = None
        self._arrived_ids.move_to_end(message_id)
        while len(self._arrived_ids) > ARRIVED_IDS_MAX:
            self._arrived_ids.popitem(last=False)

    async def _forward_undecryptable(self, lost: dict[str, Any]) -> None:
        """Đăng tin báo lỗi giải mã sau thời gian chờ, trừ khi tin thật đã tới."""
        original = str(lost["messageID"]).removeprefix("undecryptable-")
        await asyncio.sleep(UNDECRYPTABLE_GRACE_SECONDS)
        if original in self._arrived_ids or _gateway is None:
            return
        await _gateway.forward(self.account, self, lost)

    async def _dispatch(self, message: dict[str, Any]) -> None:
        if _gateway is not None:
            sender_id = str(message.get("userID") or "")
            if message.get("messageID"):
                self._note_arrived(str(message["messageID"]))
                if sender_id == str(self.dataFB.get("FacebookID")):
                    # Chủ tài khoản gửi từ thiết bị khác: ghi chú, không phải tin khách.
                    await _gateway.forward_owner(self.account, self, message)
                else:
                    await _gateway.forward(self.account, self, message)
            if not COMMANDS_FLAG:
                return
        await super()._dispatch(message)

    def _forward_listener_event(
        self, loop: asyncio.AbstractEventLoop, event: dict[str, Any]
    ) -> None:
        if self._trace is not None:
            self._trace.write(event)
        self._record_lifecycle(event)
        # SimpleBot chỉ chuyển tin nhắn/điều khiển; reaction, sửa, thu hồi thì
        # chuyển thẳng cho gateway (chạy trên event loop, gọi từ listener thread).
        if (
            _gateway is not None
            and isinstance(event, dict)
            and event.get("type") == "raw"
        ):
            # Bảng LightSpeed mang tên/ảnh/thành viên nhóm (tin E2EE thì không).
            changes = _gateway.observe_raw(self.account, event)
            lost = undecryptable_message(event)
            try:
                # Khách đang soạn tin trong chat E2EE (whatsmeow ChatPresence).
                if (event.get("data") or {}).get("type") == "ChatPresence":
                    asyncio.run_coroutine_threadsafe(
                        _gateway.post_presence(self.account, event), loop
                    )
                if changes:
                    asyncio.run_coroutine_threadsafe(
                        _gateway.post_group_changes(self.account, self, changes), loop
                    )
                if lost is not None:
                    loop.call_soon_threadsafe(self._spawn_undecryptable, lost)
            except RuntimeError:
                pass  # loop đã đóng khi đang tắt
        if (
            _gateway is not None
            and isinstance(event, dict)
            and event.get("type") in PRESENCE_EVENT_TYPES
        ):
            try:
                asyncio.run_coroutine_threadsafe(
                    _gateway.post_presence(self.account, event), loop
                )
            except RuntimeError:
                pass  # loop đã đóng khi đang tắt
            return
        if (
            _gateway is not None
            and isinstance(event, dict)
            and event.get("type") in META_EVENT_TYPES
        ):
            try:
                asyncio.run_coroutine_threadsafe(
                    _gateway.handle_meta(self.account, self, event), loop
                )
            except RuntimeError:
                pass  # loop đã đóng khi đang tắt
            return
        super()._forward_listener_event(loop, event)

    def _record_lifecycle(self, event: Any) -> None:
        """Ghi các mốc kết nối E2EE (gọi từ listener thread) vào lịch sử."""
        if not isinstance(event, dict):
            return
        kind = event.get("type")
        history = account_history(self.account)
        if kind == "disconnected":
            history.record("disconnected", "Messenger ngắt kết nối E2EE")
        elif kind == "reconnected":
            history.record("connected", "Đã nối lại Messenger")
        if kind in ("reconnected", "e2eeConnected") and self._loop is not None:
            # Có lần thư viện chỉ nối lại socket E2EE, không báo transport
            # "connected" (shop2 30/10/2026): coi đây là đã nối lại, nếu không
            # tài khoản kẹt "retrying" dù vẫn nhận gửi bình thường.
            with contextlib.suppress(RuntimeError):  # loop đã đóng khi đang tắt
                self._loop.call_soon_threadsafe(
                    self._apply_connection_status, {"state": "connected"}
                )
        elif kind == "e2eeKeyCheck":
            message = key_check_message(event.get("data"))
            if message:
                history.record("keycheck", message)
        elif kind == "e2eeSenderKey":
            result = sender_key_message(event.get("data"))
            if result is not None:
                message, alert = result
                # Listener thread không mang LOG_LABEL: gắn tên tài khoản tay.
                _upstream_log(f"{self.account}] [e2ee-key", message)
                if alert:
                    history.record("decrypt", message)
        elif kind == "error":
            label = classify_bridge_error(event.get("data"))
            if label:
                history.record("platform", label)
            failure = decrypt_failure(event.get("data"))
            if failure is not None:
                history.record("decrypt", decrypt_history_message(failure))
                count = self._decrypt_watch.observe(failure)
                if count and _gateway is not None and self._loop is not None:
                    with contextlib.suppress(RuntimeError):  # loop đã đóng khi đang tắt
                        asyncio.run_coroutine_threadsafe(
                            send_decrypt_alert(self.account, failure, count),
                            self._loop,
                        )
        elif kind == "raw":
            label = classify_raw_event(event)
            if label:
                history.record("platform", label)

    def _queue_event(self, event: dict[str, Any]) -> None:
        # call_soon_threadsafe chạy callback trong bản sao context của listener
        # thread, nên phải gắn lại nhãn; không ảnh hưởng task khác.
        LOG_LABEL.set(self.account)
        super()._queue_event(event)


async def send_decrypt_alert(account: str, failure: dict[str, Any], count: int) -> None:
    """Báo Telegram (qua gateway) khi một thiết bị gửi liên tục không giải mã được."""
    if _gateway is None:
        return
    where = "trong nhóm" if failure["group"] else "trong chat 1-1"
    text = (
        f"🟠 Facebook - {account}: {count} tin E2EE {where} từ thiết bị "
        f"{failure['device']} không giải mã được ({failure['label']}). Tin vào "
        "Libredesk thành dòng ⚠️, phải xem trên Messenger. Lỗi này thường không "
        "tự hết: nhờ người gửi đăng xuất rồi đăng nhập lại Messenger trên thiết "
        "bị đó (xem deploy/README.md, mục tin E2EE không giải mã được)."
    )
    try:
        await _gateway.post_alert(text)
    except httpx.HTTPError as error:
        log("gateway", f"Gửi cảnh báo giải mã thất bại: {type(error).__name__}")


def set_account_state(name: str, state: str | None) -> None:
    """Ghi nhận starting/running/retrying/dropped (None: xoá) và ghi file health."""
    if state is None:
        _account_states.pop(name, None)
    else:
        _account_states[name] = state
    if not HEALTH_FILE:
        return
    target = Path(HEALTH_FILE)
    try:
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(_account_states, handle)
        os.replace(tmp_name, target)
    except OSError as error:
        log("multi", f"Không ghi được file health: {error}")


def discover_accounts(root: Path, only: str | None = None) -> list[tuple[str, Path]]:
    """Trả về (tên, thư mục) của mọi tài khoản có config.json, sắp theo tên (chỉ BOT_ACCOUNT nếu có)."""
    only = only_account() if only is None else only
    if not root.is_dir():
        return []
    accounts: list[tuple[str, Path]] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not (entry / "config.json").is_file():
            continue
        if only and entry.name != only:
            continue
        if not ACCOUNT_NAME_PATTERN.match(entry.name):
            log(
                "multi", f"Bỏ qua thư mục tài khoản có tên không hợp lệ: {entry.name!r}"
            )
            continue
        accounts.append((entry.name, entry))
    return accounts


async def run_account(
    name: str,
    account_dir: Path,
    http_client: httpx.AsyncClient,
    *,
    on_ready: Callable[[], None] | None = None,
) -> None:
    """Khởi tạo session và chạy bot cho một tài khoản tới khi lỗi hoặc bị hủy."""
    LOG_LABEL.set(name)
    config_path = account_dir / "config.json"
    config = load_account_config(config_path)
    log("boot", "Đang khởi tạo dataFB từ cookie...")
    dataFB = await dataGetHome(
        storage=FileSessionStorage(str(config_path), key="cookies")
    )
    # httpx.Response và stream của nó tham chiếu vòng nên HTML homepage (vài MB,
    # ~18 MiB sau khi decode) chỉ được giải phóng khi GC thế hệ cao nhất chạy;
    # bot rảnh có thể giữ nó rất lâu. Dọn ngay để không nhân lên theo số tài khoản.
    gc.collect()
    if dataFB is None or not is_valid_datafb(dataFB):
        # dataGetHome trả None cả khi mất mạng: chỉ coi là hết phiên khi vẫn
        # tới được Facebook.
        if not await facebook_reachable(http_client):
            raise ConnectionError("Không kết nối được Facebook (mất mạng?).")
        cause = await diagnose_session(http_client, str(config.get("cookies") or ""))
        raise SessionExpiredError(
            "Không lấy được dataFB hợp lệ; cookie đã hết hạn hoặc HTML token đã đổi.",
            cause,
        )
    bot = AccountBot(
        dataFB,
        account=name,
        device_path=str(account_dir / "e2ee_device.json"),
        prefix=config["prefix"],
        admins=config["admins"],
        log_message_content=config["log_message_content"],
        debug_errors=config["debug_errors"],
        http_client=http_client,
    )
    if _gateway is not None:
        await _gateway.register(name, bot)
    uid = str(dataFB.get("FacebookID") or "")
    _account_profiles[name] = {"uid": uid, "displayName": "", "avatar": ""}
    if _gateway is not None and uid:
        with contextlib.suppress(Exception):  # chỉ để hiển thị
            display_name, avatar = await _gateway.user_profile(bot, uid)
            _account_profiles[name].update(displayName=display_name, avatar=avatar)
    ready_task = asyncio.create_task(_notify_when_ready(bot, on_ready))
    # Lưu cookie Facebook cấp lại và mở trang chủ mỗi ngày (cùng danh tính với
    # bridge). Không dùng http_client chung: cookie jar của nó sẽ lẫn giữa tài khoản.
    keeper_task = asyncio.create_task(
        keep_session(config_path, bot.listener.get_cookies, log)
    )
    try:
        await bot.run()
    finally:
        ready_task.cancel()
        keeper_task.cancel()
        if _gateway is not None:
            _gateway.unregister(name, bot)


async def _notify_when_ready(
    bot: SimpleBot, on_ready: Callable[[], None] | None
) -> None:
    """Chờ cùng điều kiện ready với SimpleBot.run() rồi báo cho supervisor."""
    if on_ready is None:
        return
    while True:
        ready = await asyncio.to_thread(
            bot.listener.wait_until_connected,
            bot.listener.startup_timeout,
            require_e2ee=True,
        )
        if ready:
            on_ready()
            return
        # Từ 2.3.4 listener tự nối lại khi khởi động lúc mất mạng: chờ tiếp.
        if getattr(bot.listener, "connection_state", None) != "reconnecting":
            return


async def supervise_account(
    name: str,
    account_dir: Path,
    http_client: httpx.AsyncClient,
    *,
    max_attempts: int = MAX_ATTEMPTS,
    retry_base: float = RETRY_BASE_SECONDS,
    stable_after: float = STABLE_AFTER_SECONDS,
) -> bool:
    """Chạy lại tài khoản khi lỗi; trả về False khi bỏ cuộc sau max_attempts.

    Bộ đếm reset nếu lần chạy trước kéo dài quá ``stable_after`` giây, để bot
    chạy lâu ngày không bị bỏ chỉ vì thỉnh thoảng mất kết nối.
    """
    LOG_LABEL.set(name)
    loop = asyncio.get_running_loop()
    history = account_history(name, account_dir)
    attempt = 0
    while True:
        started = loop.time()
        set_account_state(name, "starting")
        try:
            await run_account(
                name,
                account_dir,
                http_client,
                on_ready=lambda: _mark_running(name),
            )
            return True
        except Exception as error:
            # Bắt rộng để lỗi của một tài khoản không làm dừng tài khoản khác;
            # CancelledError là BaseException nên vẫn được lan ra khi shutdown.
            _account_errors[name] = describe_account_error(error)
            if isinstance(error, SessionExpiredError):
                history.record("session_expired", _account_errors[name]["message"])
            else:
                history.record(*describe_run_error(error))
            attempt = 1 if loop.time() - started >= stable_after else attempt + 1
            # Phiên đã hết hạn: thử lại một lần (phòng lỗi thoáng qua) rồi dừng,
            # gọi Facebook liên tục bằng cookie hỏng dễ bị coi là bất thường.
            limit = (
                min(max_attempts, SESSION_EXPIRED_ATTEMPTS)
                if isinstance(error, SessionExpiredError)
                else max_attempts
            )
            expired = isinstance(error, SessionExpiredError)
            if expired and attempt >= limit:
                set_account_state(name, "dropped")
                log(
                    "multi",
                    f"❌ Bỏ tài khoản sau {attempt} lần lỗi liên tiếp: "
                    f"{_format_exception_chain(error)}",
                )
                return False
            set_account_state(name, "retrying")
            delay = min(retry_base * 2 ** (attempt - 1), RETRY_MAX_SECONDS)
            if not expired:
                delay = min(delay, OFFLINE_RETRY_SECONDS)
            counter = (
                f"{attempt}/{limit}" if expired or attempt < limit else f"lần {attempt}"
            )
            log(
                "multi",
                f"❌ {_format_exception_chain(error)}; thử lại sau {delay:.0f}s "
                f"({counter}).",
            )
            await asyncio.sleep(delay)


def _mark_running(name: str) -> None:
    _account_errors.pop(name, None)
    set_account_state(name, "running")
    account_history(name).record("connected", "Đã kết nối")


class AccountManager:
    """Chạy/dừng từng tài khoản khi bot đang chạy (trang "Tài khoản kênh")."""

    def __init__(
        self, root: Path, http_client: httpx.AsyncClient, only: str | None = None
    ) -> None:
        self.root = root
        self.http_client = http_client
        self.tasks: dict[str, asyncio.Task[bool]] = {}
        self.only = only_account() if only is None else only

    def start(self, name: str) -> asyncio.Task[bool]:
        task = self.tasks.get(name)
        if task is not None and not task.done():
            return task
        task = asyncio.create_task(
            supervise_account(name, self.root / name, self.http_client),
            name=f"account-{name}",
        )
        self.tasks[name] = task
        return task

    async def stop(self, name: str) -> None:
        task = self.tasks.pop(name, None)
        if task is not None and not task.done():
            # Hủy task: SimpleBot.run() dừng bridge trong finally.
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        set_account_state(name, None)
        _account_profiles.pop(name, None)
        _account_errors.pop(name, None)
        _account_history.pop(name, None)

    async def restart(self, name: str) -> None:
        await self.stop(name)
        account_history(name, self.root / name).record(
            "manual", "Khởi động lại tài khoản (đăng nhập lại hoặc bấm Kết nối lại)"
        )
        self.start(name)

    def list(self) -> list[dict[str, Any]]:
        names = {n for n, _ in discover_accounts(self.root, self.only)} | set(
            _account_states
        )
        if self.only:
            # Tài khoản của pod luôn hiện, kể cả khi chưa đăng nhập; không hiện tài khoản khác.
            names = {self.only}
        # Tên/ảnh chưa tra được lúc khởi động: lấy từ danh bạ LightSpeed đã thấy.
        for profile in _account_profiles.values():
            if (
                _gateway is not None
                and profile.get("uid")
                and not profile.get("displayName")
            ):
                name, avatar = _gateway.cached_profile(profile["uid"])
                profile.update(displayName=name, avatar=profile.get("avatar") or avatar)
        return [
            {
                "name": n,
                "state": _account_states.get(n, "stopped"),
                "profile": _account_profiles.get(n),
                "error": _account_errors.get(n),
                "history": account_history(n, self.root / n).list(),
            }
            for n in sorted(names)
        ]

    async def set_cookie(self, name: str, cookie: str) -> tuple[int, str]:
        """Kiểm tra cookie với Facebook rồi lưu và chạy lại tài khoản."""
        names = {p.partition("=")[0].strip() for p in cookie.split(";") if "=" in p}
        if not {"c_user", "xs"} <= names:
            return 400, "Cookie phải có c_user và xs."
        data_fb = await dataGetHome(cookie)
        gc.collect()
        if data_fb is None or not is_valid_datafb(data_fb):
            return 422, "Facebook không chấp nhận cookie này (hết hạn hoặc sai)."
        account_dir = self.root / name
        account_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        config_path = account_dir / "config.json"
        FileSessionStorage(str(config_path), key="cookies").save(cookie.strip())
        set_private_file_permissions(config_path)
        log("multi", f"Đã lưu cookie mới cho tài khoản {name}.")
        await self.restart(name)
        return 200, "ok"

    async def remove(self, name: str) -> None:
        await self.stop(name)
        shutil.rmtree(self.root / name, ignore_errors=True)
        # Dữ liệu của tài khoản nằm ngoài thư mục của nó: tin đã nhớ của gateway, trace.
        if _gateway is not None:
            _gateway.forget_account(name)
        remove_traces(name)
        log("multi", f"Đã gỡ tài khoản {name}, xoá dữ liệu đăng nhập và tin đã nhớ.")

    async def handle(
        self, method: str, path: str, body: bytes
    ) -> tuple[int, Any] | None:
        """Route /accounts cho gateway; None nếu không phải route này."""
        parts = [p for p in path.split("?", 1)[0].split("/") if p]
        if not parts or parts[0] != "accounts":
            return None
        if len(parts) == 1 and method == "GET":
            return 200, self.list()
        name = parts[1] if len(parts) > 1 else ""
        if not ACCOUNT_NAME_PATTERN.match(name):
            return 400, {"error": "Tên tài khoản không hợp lệ."}
        if self.only and name != self.only:
            return 404, {"error": "unknown account"}
        action = parts[2] if len(parts) > 2 else ""
        if action == "cookie" and method == "POST":
            try:
                payload = json.loads(body or b"{}")
            except ValueError:
                return 400, {"error": "JSON không hợp lệ."}
            cookie = payload.get("cookie") if isinstance(payload, dict) else None
            if not isinstance(cookie, str) or not cookie.strip():
                return 400, {"error": "Thiếu cookie."}
            status, message = await self.set_cookie(name, cookie)
            return status, {"ok": status == 200, "message": message}
        if action == "restart" and method == "POST":
            if not (self.root / name / "config.json").is_file():
                return 404, {"error": "Chưa có tài khoản này."}
            await self.restart(name)
            return 202, {"ok": True}
        if action == "" and method == "DELETE":
            await self.remove(name)
            return 204, None
        return 404, {"error": "not found"}


async def main() -> None:
    install_labeled_log()
    accounts = discover_accounts(ACCOUNTS_DIR)
    log(
        "multi",
        f"Chạy {len(accounts)} tài khoản: "
        f"{', '.join(n for n, _ in accounts) or '(chưa có)'}",
    )
    global _gateway
    async with httpx.AsyncClient(timeout=DEFAULT_HTTP_TIMEOUT) as http_client:
        _gateway = GatewayLink.from_env(http_client, log)
        if _gateway is None and not accounts:
            raise RuntimeError(
                f"Không có tài khoản nào trong {ACCOUNTS_DIR} (cần <tên>/config.json)."
            )
        manager = AccountManager(ACCOUNTS_DIR, http_client)
        set_account_state("", None)  # ghi file health ngay cả khi chưa có tài khoản
        if _gateway is not None:
            _gateway.routes = manager.handle
            await _gateway.serve(BOT_HTTP_PORT)
        tasks = [manager.start(n) for n, _ in accounts]
        if _gateway is None:
            await asyncio.gather(*tasks)
            return
        # Không await các task: trang "Tài khoản kênh" có thể dừng/chạy lại
        # (hủy task) bất cứ lúc nào. Tài khoản bị bỏ vẫn giữ tiến trình sống để
        # healthcheck báo unhealthy thay vì Docker restart với cookie hỏng mãi mãi.
        await asyncio.Event().wait()


def main_blocking() -> None:
    configure_utf8_console()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("multi", "Đã dừng theo yêu cầu người dùng.")
    except RuntimeError as error:
        log("multi", f"❌ {_format_exception_chain(error)}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main_blocking()
