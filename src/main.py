"""Bot mẫu async-first cho fbchat-v2."""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import time
import traceback
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from _core._permissions import create_private_json_file, set_private_file_permissions
from _core._session import dataGetHome
from _core._storage import FileSessionStorage
from _features._facebook import _search
from _messaging._bridge_actions import BridgeActions
from _messaging._listening_e2ee import (
    DELIVERY_STATUS_UNKNOWN,
    listeningE2EEEvent,
)

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
Handler = Callable[[dict[str, Any], str], Awaitable[None]]
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_E2EE_READY_TIMEOUT = 90.0
EVENT_QUEUE_MAXSIZE = 1000
RECENT_MESSAGE_IDS_MAXSIZE = 4096
SEARCH_QUERY_MIN_LENGTH = 2
SEARCH_QUERY_MAX_LENGTH = 100
SEARCH_RATE_WINDOW_SECONDS = 60.0
SEARCH_PER_SENDER_LIMIT = 3
SEARCH_GLOBAL_LIMIT = 20
MESSAGE_EVENT_TYPES = frozenset({"message", "e2eeMessage"})
CONTROL_EVENT_TYPES = frozenset(
    {
        "ready",
        "e2eeConnected",
        "reconnected",
        "disconnected",
        "closed",
        "error",
    }
)
FORWARDED_EVENT_TYPES = MESSAGE_EVENT_TYPES | CONTROL_EVENT_TYPES

_create_private_config = create_private_json_file
_set_private_file_permissions = set_private_file_permissions


class _SearchRateLimiter:
    """Sliding-window quota for the sample bot's authenticated search API."""

    def __init__(
        self,
        *,
        per_sender_limit: int,
        global_limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if per_sender_limit <= 0 or global_limit <= 0 or window_seconds <= 0:
            raise ValueError("Giới hạn /search phải lớn hơn 0.")
        self._per_sender_limit = per_sender_limit
        self._global_limit = global_limit
        self._window_seconds = window_seconds
        self._clock = clock
        self._global_requests: deque[float] = deque()
        self._sender_requests: dict[str, deque[float]] = {}

    @staticmethod
    def _prune(requests: deque[float], cutoff: float) -> None:
        while requests and requests[0] <= cutoff:
            requests.popleft()

    def check(self, sender_id: str) -> str | None:
        """Reserve one request, or return the quota scope that rejected it."""
        now = self._clock()
        cutoff = now - self._window_seconds
        self._prune(self._global_requests, cutoff)

        for known_sender, requests in list(self._sender_requests.items()):
            self._prune(requests, cutoff)
            if not requests:
                self._sender_requests.pop(known_sender, None)

        sender_requests = self._sender_requests.get(sender_id)
        if (
            sender_requests is not None
            and len(sender_requests) >= self._per_sender_limit
        ):
            return "sender"
        if len(self._global_requests) >= self._global_limit:
            return "global"

        if sender_requests is None:
            sender_requests = deque()
            self._sender_requests[sender_id] = sender_requests
        sender_requests.append(now)
        self._global_requests.append(now)
        return None


def load_config() -> dict[str, Any]:
    """Đọc config và tạo template an toàn nếu chưa tồn tại."""
    if not CONFIG_PATH.exists():
        template = {
            "cookies": "PASTE_YOUR_FACEBOOK_COOKIE_HERE",
            "prefix": "/",
            "admins": [],
            "log_message_content": False,
            "debug_errors": False,
        }
        if _create_private_config(CONFIG_PATH, template):
            raise RuntimeError(
                f"Đã tạo template riêng tư tại {CONFIG_PATH}. Điền cookies rồi chạy lại."
            )

    _set_private_file_permissions(CONFIG_PATH)
    with CONFIG_PATH.open("r", encoding="utf-8") as file_handle:
        config = json.load(file_handle)
    config.setdefault("prefix", "/")
    config.setdefault("admins", [])
    config.setdefault("log_message_content", False)
    config.setdefault("debug_errors", False)
    if not isinstance(config["prefix"], str) or not config["prefix"]:
        raise ValueError("config.prefix phải là chuỗi không rỗng.")
    if not isinstance(config["admins"], list):
        raise ValueError("config.admins phải là một danh sách ID.")
    if not isinstance(config["log_message_content"], bool):
        raise ValueError("config.log_message_content phải là true hoặc false.")
    if not isinstance(config["debug_errors"], bool):
        raise ValueError("config.debug_errors phải là true hoặc false.")
    return config


def is_valid_datafb(dataFB: object) -> bool:
    if not isinstance(dataFB, dict):
        return False
    facebook_id = str(dataFB.get("FacebookID") or "").strip()
    required = ("fb_dtsg", "jazoest", "sessionID", "clientRevision", "cookieFacebook")
    return facebook_id.isdigit() and all(
        str(dataFB.get(field) or "").strip() for field in required
    )


def log(tag: str, message: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] [{tag}] {message}"
    try:
        print(line)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe_line = line.encode(encoding, errors="backslashreplace").decode(
            encoding, errors="replace"
        )
        print(safe_line)


class SimpleBot:
    def __init__(
        self,
        dataFB: dict[str, Any],
        *,
        prefix: str = "/",
        admins: list[Any] | None = None,
        log_message_content: bool = False,
        debug_errors: bool = False,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.dataFB = dataFB
        self.prefix = prefix
        self.admins = {str(admin_id) for admin_id in admins or []}
        self.log_message_content = log_message_content
        self.debug_errors = debug_errors
        self.http_client = http_client
        self.listener = listeningE2EEEvent(dataFB, debug_errors=debug_errors)
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=EVENT_QUEUE_MAXSIZE
        )
        self._recent_message_ids: deque[str] = deque()
        self._recent_message_id_set: set[str] = set()
        self._dropped_message_events = 0
        self._last_bot_message: dict[str, tuple[str, str]] = {}
        self._search_rate_limiter = _SearchRateLimiter(
            per_sender_limit=SEARCH_PER_SENDER_LIMIT,
            global_limit=SEARCH_GLOBAL_LIMIT,
            window_seconds=SEARCH_RATE_WINDOW_SECONDS,
        )
        self._handlers: dict[str, Handler] = {
            "ping": self._cmd_ping,
            "help": self._cmd_help,
            "id": self._cmd_id,
            "echo": self._cmd_echo,
            "search": self._cmd_search,
            "unsend": self._cmd_unsend,
        }

    async def run(self) -> None:
        log("bot", f"Đăng nhập E2EE với UID = {self.dataFB.get('FacebookID')}")
        loop = asyncio.get_running_loop()
        self.listener.on_message(
            lambda event: self._forward_listener_event(loop, event)
        )
        listener_task = asyncio.create_task(
            self.listener.connect_mqtt(), name="fbchat-e2ee-listener"
        )
        try:
            ready = await asyncio.to_thread(
                self.listener.wait_until_connected,
                DEFAULT_E2EE_READY_TIMEOUT,
                require_e2ee=True,
            )
            if not ready:
                raise RuntimeError("E2EE listener chưa sẵn sàng trước timeout.")
            log("bot", "E2EE listener đã sẵn sàng. Nhấn Ctrl+C để thoát.")
            while True:
                if listener_task.done():
                    listener_task.result()
                    raise RuntimeError("E2EE listener đã dừng ngoài dự kiến.")
                event = await self._get_event(timeout=1.0)
                message = self._message_from_event(event) if event else None
                if message is not None:
                    await self._dispatch(message)
        finally:
            await self._shutdown_listener(listener_task)

    def run_blocking(self) -> None:
        """Wrapper CLI tương thích; trong ứng dụng async hãy await run()."""
        asyncio.run(self.run())

    async def _shutdown_listener(self, listener_task: asyncio.Task[None]) -> None:
        """Dừng bridge E2EE và chờ task listener thoát gọn."""
        await asyncio.to_thread(self.listener.stop)
        try:
            await asyncio.wait_for(asyncio.shield(listener_task), timeout=5)
        except asyncio.TimeoutError:
            listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener_task
        except asyncio.CancelledError:
            if listener_task.cancelled():
                return
            if not listener_task.done():
                listener_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await listener_task
            raise
        except Exception:
            # Cleanup không được che mất lỗi startup/runtime gốc của run().
            pass

    def _forward_listener_event(
        self, loop: asyncio.AbstractEventLoop, event: dict[str, Any]
    ) -> None:
        """Lọc event ngay trên listener thread trước khi chạm asyncio queue."""
        if not isinstance(event, dict):
            return
        if event.get("type") not in FORWARDED_EVENT_TYPES:
            return
        try:
            loop.call_soon_threadsafe(self._queue_event, event)
        except RuntimeError:
            if self.debug_errors:
                log("queue", "Bỏ qua event vì asyncio loop đã đóng.")

    def _queue_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type not in MESSAGE_EVENT_TYPES:
            # Control event được xử lý ngay trên event loop, còn
            # typing/receipt/reaction/raw bị loại trước queue message.
            if event_type in CONTROL_EVENT_TYPES:
                self._message_from_event(event)
            return
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self._event_queue.get_nowait()
            self._event_queue.put_nowait(event)
            self._dropped_message_events += 1
            # Log theo lũy thừa hai để có telemetry mà không tự tạo log storm.
            if self._dropped_message_events & (self._dropped_message_events - 1) == 0:
                log(
                    "queue",
                    "Queue message đầy; đã loại "
                    f"{self._dropped_message_events} event cũ (không log nội dung).",
                )

    def _remember_message_id(self, message_id: str) -> bool:
        """Ghi nhận ID hợp lệ; trả về False nếu event đã được xử lý."""
        if message_id in self._recent_message_id_set:
            return False
        if len(self._recent_message_ids) >= RECENT_MESSAGE_IDS_MAXSIZE:
            oldest = self._recent_message_ids.popleft()
            self._recent_message_id_set.discard(oldest)
        self._recent_message_ids.append(message_id)
        self._recent_message_id_set.add(message_id)
        return True

    async def _get_event(self, timeout: float | None = None) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._event_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def _message_from_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        event_type = event.get("type")
        raw_data = event.get("data")
        data = raw_data if isinstance(raw_data, dict) else {}

        if event_type in {
            "ready",
            "e2eeConnected",
            "reconnected",
            "disconnected",
            "closed",
        }:
            log("e2ee", str(event_type))
            return None
        if event_type == "error":
            if self.debug_errors:
                log("e2ee", f"bridge error: {data}")
            else:
                log("e2ee", "bridge error (chi tiết đã được ẩn)")
            return None
        if event_type not in MESSAGE_EVENT_TYPES:
            if self.debug_errors and event_type not in {"raw", None}:
                log("e2ee", f"Bỏ qua event phụ trợ: {event_type}")
            return None

        chat_jid = data.get("chatJid")
        sender_jid = data.get("senderJid")
        message_type = "e2ee" if event_type == "e2eeMessage" else "thread"
        return {
            "body": data.get("text"),
            "timestamp": data.get("timestampMs", 0),
            "userID": data.get("senderId", 0),
            "messageID": data.get("id"),
            "replyToID": data.get("threadId", 0),
            "type": message_type,
            "chatJid": chat_jid,
            "senderJid": sender_jid,
            "attachments": data.get("attachments") or [],
            "raw": data,
        }

    async def _dispatch(self, message: dict[str, Any]) -> None:
        message_id = str(message.get("messageID") or "").strip()
        body = message.get("body")
        sender_id = str(message.get("userID") or "").strip()
        if not message_id or not sender_id or not isinstance(body, str) or not body:
            if self.debug_errors:
                log(
                    "recv",
                    "Bỏ qua message thiếu ID, sender hoặc nội dung; "
                    f"keys={sorted(message)}",
                )
            return

        if sender_id == str(self.dataFB.get("FacebookID")):
            if self.debug_errors:
                log("recv", "Bỏ qua message do chính tài khoản bot gửi.")
            return
        target = message.get("chatJid") or message.get("replyToID")
        body_for_log = (
            repr(body)
            if self.log_message_content
            else f"<redacted length={len(str(body))}>"
        )
        log("recv", f"[{message.get('type')}] {sender_id}@{target}: {body_for_log}")
        if not str(body).startswith(self.prefix):
            return

        command_line = str(body)[len(self.prefix) :].strip()
        if not command_line:
            return
        parts = command_line.split(maxsplit=1)
        command = parts[0].lower()
        argument = parts[1] if len(parts) > 1 else ""
        handler = self._handlers.get(command)
        if handler is None:
            detail = command if self.log_message_content else "<redacted>"
            log("cmd", f"Bỏ qua lệnh không tồn tại: {detail}")
            return
        if not self._remember_message_id(message_id):
            return
        try:
            await handler(message, argument)
        except Exception as error:  # bot không được chết vì một lệnh lỗi
            if self.debug_errors:
                log("err", f"Lỗi khi xử lý /{command}: {error}")
                traceback.print_exc()
            else:
                log(
                    "err",
                    f"Lỗi {type(error).__name__} khi xử lý /{command}; "
                    "bật debug_errors để xem chi tiết.",
                )

    async def _reply(self, message: dict[str, Any], content: str) -> None:
        chat_jid = message.get("chatJid")
        if chat_jid:
            result = await self.listener.send_e2ee_message(
                str(chat_jid),
                content,
                reply_to_id=str(message.get("messageID") or ""),
                reply_to_sender_jid=str(message.get("senderJid") or ""),
            )
            message_id = result.get("messageId") or result.get("id")
            if result.get("deliveryStatus") == DELIVERY_STATUS_UNKNOWN:
                log(
                    "send",
                    f"E2EE UNKNOWN -> {chat_jid}; messageId={message_id or '<missing>'}; "
                    "không tự retry để tránh gửi trùng.",
                )
                return
            if message_id:
                self._last_bot_message[str(chat_jid)] = (str(chat_jid), str(message_id))
                content_for_log = (
                    repr(content)
                    if self.log_message_content
                    else f"<redacted length={len(content)}>"
                )
                log("send", f"E2EE -> {chat_jid}: {content_for_log}")
            else:
                log("send", f"E2EE FAIL -> {chat_jid}; keys={sorted(result)}")
            return

        thread_id = message.get("replyToID")
        if not thread_id:
            log(
                "send",
                "Bỏ qua reply vì thiếu chatJid/threadID "
                f"(messageID={message.get('messageID')!r}).",
            )
            return
        result = await self.listener.send_message(
            int(thread_id),
            content,
            reply_to_id=str(message.get("messageID") or ""),
        )
        message_id = result.get("messageId") or result.get("id")
        if message_id:
            content_for_log = (
                repr(content)
                if self.log_message_content
                else f"<redacted length={len(content)}>"
            )
            log("send", f"regular -> {thread_id}: {content_for_log}")
        else:
            log("send", f"regular FAIL -> {thread_id}; keys={sorted(result)}")

    async def _cmd_ping(self, message: dict[str, Any], argument: str) -> None:
        sent_ts = int(message.get("timestamp") or 0)
        latency = max(0, int(time.time() * 1000) - sent_ts) if sent_ts else None
        await self._reply(
            message, f"🏓 pong! ({latency} ms)" if latency is not None else "🏓 pong!"
        )

    async def _cmd_help(self, message: dict[str, Any], argument: str) -> None:
        prefix = self.prefix
        await self._reply(
            message,
            "📖 Lệnh hỗ trợ:\n"
            f"• {prefix}ping - kiểm tra độ trễ\n"
            f"• {prefix}help - hiển thị trợ giúp\n"
            f"• {prefix}id - xem chatJid/threadID + userID\n"
            f"• {prefix}echo <text> - lặp lại nội dung\n"
            f"• {prefix}search <từ> - tìm người dùng Facebook\n"
            f"• {prefix}unsend - thu hồi tin nhắn E2EE cuối của bot",
        )

    async def _cmd_id(self, message: dict[str, Any], argument: str) -> None:
        await self._reply(
            message,
            f"🆔 type: {message.get('type')}\n"
            f"chatJid: {message.get('chatJid')}\n"
            f"threadID: {message.get('replyToID')}\n"
            f"userID: {message.get('userID')}\n"
            f"senderJid: {message.get('senderJid')}\n"
            f"messageID: {message.get('messageID')}",
        )

    async def _cmd_echo(self, message: dict[str, Any], argument: str) -> None:
        await self._reply(
            message, argument or f"Cách dùng: {self.prefix}echo <nội dung>"
        )

    async def _cmd_search(self, message: dict[str, Any], argument: str) -> None:
        query = " ".join(argument.split())
        if not query:
            await self._reply(message, f"Cách dùng: {self.prefix}search <từ khóa>")
            return
        if len(query) < SEARCH_QUERY_MIN_LENGTH:
            await self._reply(
                message,
                f"🔍 Từ khóa phải có ít nhất {SEARCH_QUERY_MIN_LENGTH} ký tự.",
            )
            return
        if len(query) > SEARCH_QUERY_MAX_LENGTH:
            await self._reply(
                message,
                f"🔍 Từ khóa không được vượt quá {SEARCH_QUERY_MAX_LENGTH} ký tự.",
            )
            return

        limit_scope = self._search_rate_limiter.check(str(message.get("userID") or ""))
        if limit_scope is not None:
            log("rate", f"Từ chối /search do chạm quota {limit_scope}; query đã ẩn.")
            await self._reply(
                message,
                "⏳ /search đang được dùng quá nhanh. Vui lòng thử lại sau.",
            )
            return

        result = await _search.func(self.dataFB, query, client=self.http_client)
        users = result.get("searchResultsDict") if isinstance(result, dict) else None
        if not users:
            await self._reply(message, f"🔍 Không tìm thấy kết quả cho: {query}")
            return
        lines = [f"🔍 Kết quả cho “{query}”:"]
        lines.extend(
            f"{index}. {user.get('name')} - {user.get('id')}"
            for index, user in enumerate(users[:5], 1)
        )
        await self._reply(message, "\n".join(lines))

    async def _cmd_unsend(self, message: dict[str, Any], argument: str) -> None:
        sender_id = str(message.get("userID") or "")
        if not self.admins:
            await self._reply(message, "⛔ Lệnh này bị khóa vì chưa cấu hình admin.")
            return
        if sender_id not in self.admins:
            await self._reply(message, "⛔ Chỉ admin mới được dùng lệnh này.")
            return
        chat_jid = str(message.get("chatJid") or "")
        if not chat_jid:
            await self._reply(
                message, "Lệnh unsend E2EE cần chatJid, chat thường không dùng được."
            )
            return
        target = self._last_bot_message.get(chat_jid)
        if not target:
            await self._reply(
                message, "ℹ️ Chưa có tin E2EE nào để thu hồi trong chat này."
            )
            return
        target_chat_jid, target_message_id = target
        if self.listener._bridge is None:
            await self._reply(message, "Bridge E2EE chưa sẵn sàng để thu hồi.")
            return
        result = await BridgeActions(self.listener._bridge).unsend_e2ee_message(
            target_chat_jid, target_message_id
        )
        log("unsend", f"{target_message_id}; keys={sorted(result)}")
        self._last_bot_message.pop(chat_jid, None)


async def main() -> None:
    config = load_config()
    log("boot", "Đang khởi tạo dataFB từ cookie...")
    dataFB = await dataGetHome(
        storage=FileSessionStorage(str(CONFIG_PATH), key="cookies")
    )
    if not is_valid_datafb(dataFB):
        raise RuntimeError(
            "Không lấy được dataFB hợp lệ; cookie đã hết hạn hoặc HTML token đã đổi."
        )
    async with httpx.AsyncClient(timeout=DEFAULT_HTTP_TIMEOUT) as http_client:
        bot = SimpleBot(
            dataFB,
            prefix=config["prefix"],
            admins=config["admins"],
            log_message_content=config["log_message_content"],
            debug_errors=config["debug_errors"],
            http_client=http_client,
        )
        await bot.run()


def main_blocking() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("bot", "Đã dừng theo yêu cầu người dùng.")
    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
        log("boot", f"❌ {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main_blocking()
