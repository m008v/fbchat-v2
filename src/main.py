"""
Đường dẫn file:
  src/main.py

Mục đích:
  - Cung cấp module cho thư viện fbchat-v2 (phiên bản async).
  - Comment đầu file giúp developer dễ dàng theo dõi vị trí, luồng xử lý và dữ liệu của tính năng.

Cách hoạt động:
  - Nạp dependency/guard cần thiết, thực hiện các async HTTP requests tới API nội bộ hoặc GraphQL của Facebook.
  - Các thao tác request đều phải thông qua httpx.AsyncClient và module _core._utils để bảo đảm an toàn kết nối.
  - Payload gửi đi/nhận về được xử lý JSON cẩn thận, bắt lỗi try-except đầy đủ để tránh crash hệ thống.

File liên quan:
  - src/main.py và các entrypoint khác.
  - Phụ thuộc vào _core._session, _core._utils để khởi tạo và thao tác HTTP.

Author: @m008v (MinhHuyDev)
"""

"""Bot mẫu async-first cho fbchat-v2."""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import time
import traceback
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from _core._session import dataGetHome
from _core._storage import FileSessionStorage
from _features._facebook import _search
from _messaging._bridge_actions import BridgeActions
from _messaging._listening_e2ee import listeningE2EEEvent

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
Handler = Callable[[dict[str, Any], str], Awaitable[None]]
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_E2EE_READY_TIMEOUT = 90.0
EVENT_QUEUE_MAXSIZE = 1000


def load_config() -> dict[str, Any]:
    """Đọc config và tạo template an toàn nếu chưa tồn tại."""
    if not CONFIG_PATH.exists():
        template = {
            "cookies": "PASTE_YOUR_FACEBOOK_COOKIE_HERE",
            "prefix": "/",
            "admins": [],
        }
        CONFIG_PATH.write_text(
            json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        raise RuntimeError(
            f"Đã tạo template tại {CONFIG_PATH}. Điền cookies rồi chạy lại."
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as file_handle:
        config = json.load(file_handle)
    config.setdefault("prefix", "/")
    config.setdefault("admins", [])
    if not isinstance(config["prefix"], str) or not config["prefix"]:
        raise ValueError("config.prefix phải là chuỗi không rỗng.")
    if not isinstance(config["admins"], list):
        raise ValueError("config.admins phải là một danh sách ID.")
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
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.dataFB = dataFB
        self.prefix = prefix
        self.admins = {str(admin_id) for admin_id in admins or []}
        self.http_client = http_client
        self.listener = listeningE2EEEvent(dataFB)
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=EVENT_QUEUE_MAXSIZE
        )
        self._last_seen_message_id: str | None = None
        self._last_bot_message: dict[str, tuple[str, str]] = {}
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
            lambda event: loop.call_soon_threadsafe(self._queue_event, event)
        )
        listener_task = asyncio.create_task(
            self.listener.connect_mqtt(), name="fbchat-e2ee-listener"
        )
        ready = await asyncio.to_thread(
            self.listener.wait_until_connected,
            DEFAULT_E2EE_READY_TIMEOUT,
            require_e2ee=True,
        )
        if not ready:
            raise RuntimeError("E2EE listener chưa sẵn sàng trước timeout.")
        log("bot", "E2EE listener đã sẵn sàng. Nhấn Ctrl+C để thoát.")
        try:
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
        self.listener.stop()
        try:
            await asyncio.wait_for(listener_task, timeout=5)
        except asyncio.TimeoutError:
            listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener_task
        except asyncio.CancelledError:
            listener_task.cancel()
            raise

    def _queue_event(self, event: dict[str, Any]) -> None:
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self._event_queue.get_nowait()
            self._event_queue.put_nowait(event)

    async def _get_event(self, timeout: float | None = None) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._event_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    @staticmethod
    def _message_from_event(event: dict[str, Any]) -> dict[str, Any] | None:
        event_type = event.get("type")
        data = event.get("data") or {}

        if event_type in {
            "ready",
            "e2eeConnected",
            "reconnected",
            "disconnected",
            "closed",
        }:
            log("e2ee", f"{event_type}: {data}")
            return None
        if event_type == "error":
            log("e2ee", f"bridge error: {data}")
            return None
        if event_type == "raw":
            return None
        if event_type not in {"e2eeMessage", "message"}:
            log("e2ee", f"Bỏ qua event không phải message: {event_type}")
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
        message_id = message.get("messageID")
        body = message.get("body")
        if not message_id or message_id == self._last_seen_message_id:
            return
        self._last_seen_message_id = str(message_id)

        sender_id = str(message.get("userID") or "")
        if sender_id == str(self.dataFB.get("FacebookID")) or not body:
            return
        target = message.get("chatJid") or message.get("replyToID")
        log("recv", f"[{message.get('type')}] {sender_id}@{target}: {body!r}")
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
            log("cmd", f"Bỏ qua lệnh không tồn tại: {command}")
            return
        try:
            await handler(message, argument)
        except Exception as error:  # bot không được chết vì một lệnh lỗi
            log("err", f"Lỗi khi xử lý /{command}: {error}")
            traceback.print_exc()

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
            if message_id:
                self._last_bot_message[str(chat_jid)] = (str(chat_jid), str(message_id))
                log("send", f"E2EE -> {chat_jid}: {content!r}")
            else:
                log("send", f"E2EE FAIL -> {chat_jid}: {result}")
            return

        thread_id = message.get("replyToID")
        if not thread_id:
            log("send", f"Bỏ qua reply vì thiếu chatJid/threadID: {message}")
            return
        result = await self.listener.send_message(
            int(thread_id),
            content,
            reply_to_id=str(message.get("messageID") or ""),
        )
        message_id = result.get("messageId") or result.get("id")
        if message_id:
            log("send", f"regular -> {thread_id}: {content!r}")
        else:
            log("send", f"regular FAIL -> {thread_id}: {result}")

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
        if not argument:
            await self._reply(message, f"Cách dùng: {self.prefix}search <từ khóa>")
            return
        result = await _search.func(self.dataFB, argument, client=self.http_client)
        users = result.get("searchResultsDict") if isinstance(result, dict) else None
        if not users:
            await self._reply(message, f"🔍 Không tìm thấy kết quả cho: {argument}")
            return
        lines = [f"🔍 Kết quả cho “{argument}”:"]
        lines.extend(
            f"{index}. {user.get('name')} - {user.get('id')}"
            for index, user in enumerate(users[:5], 1)
        )
        await self._reply(message, "\n".join(lines))

    async def _cmd_unsend(self, message: dict[str, Any], argument: str) -> None:
        sender_id = str(message.get("userID") or "")
        if self.admins and sender_id not in self.admins:
            await self._reply(message, "⛔ Chỉ admin mới được dùng lệnh này.")
            return
        chat_jid = str(message.get("chatJid") or "")
        if not chat_jid:
            await self._reply(message, "Lệnh unsend E2EE cần chatJid, chat thường không dùng được.")
            return
        target = self._last_bot_message.get(chat_jid)
        if not target:
            await self._reply(message, "ℹ️ Chưa có tin E2EE nào để thu hồi trong chat này.")
            return
        target_chat_jid, target_message_id = target
        if self.listener._bridge is None:
            await self._reply(message, "Bridge E2EE chưa sẵn sàng để thu hồi.")
            return
        result = await BridgeActions(self.listener._bridge).unsend_e2ee_message(
            target_chat_jid, target_message_id
        )
        log("unsend", f"{target_message_id} -> {result}")
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
