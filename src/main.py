"""Bot mẫu async-first cho fbchat-v2."""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from _core._session import dataGetHome
from _core._storage import FileSessionStorage
from _features._facebook import _search
from _messaging._listening import listeningEvent
from _messaging._send import api as SendAPI
from _messaging._unsend import func as unsend_message

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
Handler = Callable[[dict[str, Any], str], Awaitable[None]]


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
    print(f"[{datetime.now():%H:%M:%S}] [{tag}] {message}")


class SimpleBot:
    def __init__(
        self, dataFB: dict[str, Any], prefix: str = "/", admins: list[Any] | None = None
    ) -> None:
        self.dataFB = dataFB
        self.prefix = prefix
        self.admins = {str(admin_id) for admin_id in admins or []}
        self.sender = SendAPI()
        self.listener = listeningEvent(dataFB)
        self._last_seen_message_id: str | None = None
        self._last_bot_message: dict[str, str] = {}
        self._handlers: dict[str, Handler] = {
            "ping": self._cmd_ping,
            "help": self._cmd_help,
            "id": self._cmd_id,
            "echo": self._cmd_echo,
            "search": self._cmd_search,
            "unsend": self._cmd_unsend,
        }

    async def run(self) -> None:
        log("bot", f"Đăng nhập với UID = {self.dataFB.get('FacebookID')}")
        await self.listener.get_last_seq_id()
        listener_task = asyncio.create_task(
            self.listener.connect_mqtt(), name="fbchat-listener"
        )
        log("bot", "Listener đã khởi động. Nhấn Ctrl+C để thoát.")
        try:
            while True:
                if listener_task.done():
                    listener_task.result()
                    raise RuntimeError("Listener MQTT đã dừng ngoài dự kiến.")
                message = await self.listener.get_message(timeout=1.0)
                if message is not None:
                    await self._dispatch(message)
        finally:
            await self.listener.disconnect()
            try:
                await asyncio.wait_for(listener_task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                listener_task.cancel()

    def run_blocking(self) -> None:
        """Wrapper CLI tương thích; trong ứng dụng async hãy await run()."""
        asyncio.run(self.run())

    async def _dispatch(self, message: dict[str, Any]) -> None:
        message_id = message.get("messageID")
        body = message.get("body")
        if not message_id or message_id == self._last_seen_message_id:
            return
        self._last_seen_message_id = str(message_id)

        sender_id = str(message.get("userID") or "")
        if sender_id == str(self.dataFB.get("FacebookID")) or not body:
            return
        log(
            "recv",
            f"[{message.get('type')}] {sender_id}@{message.get('replyToID')}: {body!r}",
        )
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
            return
        try:
            await handler(message, argument)
        except Exception as error:  # bot không được chết vì một lệnh lỗi
            log("err", f"Lỗi khi xử lý /{command}: {error}")
            traceback.print_exc()

    async def _reply(self, message: dict[str, Any], content: str) -> None:
        thread_id = message["replyToID"]
        type_chat = "user" if message.get("type") == "user" else None
        result = await self.sender.send(
            self.dataFB,
            content,
            thread_id,
            typeChat=type_chat,
            replyMessage=True,
            messageID=message.get("messageID"),
        )
        if isinstance(result, dict) and result.get("success") == 1:
            try:
                self._last_bot_message[str(thread_id)] = str(
                    result["payload"]["messageID"]
                )
            except (KeyError, TypeError):
                pass
            log("send", f"-> {thread_id}: {content!r}")
        else:
            log("send", f"FAIL -> {thread_id}: {result}")

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
            f"• {prefix}ping — kiểm tra độ trễ\n"
            f"• {prefix}help — hiển thị trợ giúp\n"
            f"• {prefix}id — xem threadID + userID\n"
            f"• {prefix}echo <text> — lặp lại nội dung\n"
            f"• {prefix}search <từ> — tìm người dùng Facebook\n"
            f"• {prefix}unsend — thu hồi tin nhắn cuối của bot",
        )

    async def _cmd_id(self, message: dict[str, Any], argument: str) -> None:
        await self._reply(
            message,
            f"🆔 type: {message.get('type')}\n"
            f"threadID: {message.get('replyToID')}\n"
            f"userID: {message.get('userID')}\n"
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
        result = await _search.func(self.dataFB, argument)
        users = result.get("searchResultsDict") if isinstance(result, dict) else None
        if not users:
            await self._reply(message, f"🔍 Không tìm thấy kết quả cho: {argument}")
            return
        lines = [f"🔍 Kết quả cho “{argument}”:"]
        lines.extend(
            f"{index}. {user.get('name')} — {user.get('id')}"
            for index, user in enumerate(users[:5], 1)
        )
        await self._reply(message, "\n".join(lines))

    async def _cmd_unsend(self, message: dict[str, Any], argument: str) -> None:
        sender_id = str(message.get("userID") or "")
        if self.admins and sender_id not in self.admins:
            await self._reply(message, "⛔ Chỉ admin mới được dùng lệnh này.")
            return
        thread_id = str(message["replyToID"])
        target = self._last_bot_message.get(thread_id)
        if not target:
            await self._reply(message, "ℹ️ Chưa có tin nào để thu hồi trong thread này.")
            return
        result = await unsend_message(target, self.dataFB)
        log("unsend", f"{target} -> {result}")
        self._last_bot_message.pop(thread_id, None)


async def main() -> None:
    config = load_config()
    log("boot", "Đang khởi tạo dataFB từ cookie…")
    dataFB = await dataGetHome(
        storage=FileSessionStorage(str(CONFIG_PATH), key="cookies")
    )
    if not is_valid_datafb(dataFB):
        raise RuntimeError(
            "Không lấy được dataFB hợp lệ; cookie đã hết hạn hoặc HTML token đã đổi."
        )
    bot = SimpleBot(dataFB, prefix=config["prefix"], admins=config["admins"])
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
