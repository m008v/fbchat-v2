"""Kết nối dùng chung; không gửi tin hoặc đăng nhập khi import."""

import asyncio
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
import os
from typing import TypedDict

from fbchat_v2 import EnvSessionStorage, ReconnectPolicy, dataGetHome, listeningEvent


class Message(TypedDict):
    body: str
    userID: str
    replyToID: str
    messageID: str


class ConfigurationError(ValueError):
    """Lỗi cấu hình do ví dụ tạo, không chứa giá trị cookie/provider."""


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"Cần đặt biến môi trường {name} trước khi chạy.")
    return value


async def login() -> dict[str, object]:
    required_env("FB_COOKIES")
    session = await dataGetHome(storage=EnvSessionStorage("FB_COOKIES"))
    if session is None:
        raise ConfigurationError(
            "Không tạo được session; kiểm tra cookie và tài khoản."
        )
    return session


async def stop_listener(task: asyncio.Task[None]) -> None:
    # Wrapper connect_mqtt của thư viện nhận cancel, dừng và join worker.
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return
    except Exception as error:
        print(f"Listener kết thúc với {type(error).__name__}; không in chi tiết phiên.")


@asynccontextmanager
async def standard_messages() -> (
    AsyncIterator[tuple[dict[str, object], AsyncIterator[Message]]]
):
    thread_id = required_env("FB_THREAD_ID")
    if not thread_id.isdecimal():
        raise ConfigurationError("FB_THREAD_ID phải là ID nhóm dạng số.")
    session = await login()
    listener = listeningEvent(session, reconnect_policy=ReconnectPolicy(max_attempts=5))
    task = asyncio.create_task(listener.connect_mqtt())

    async def receive() -> AsyncIterator[Message]:
        while not task.done():
            event = await listener.get_message(timeout=1)
            if not event:
                continue
            body = event.get("body")
            sender = str(event.get("userID") or "")
            message_id = str(event.get("messageID") or "")
            if (
                str(event.get("replyToID")) == thread_id
                and sender
                and sender != str(session["FacebookID"])
                and message_id
                and isinstance(body, str)
                and body.strip()
                and len(body) <= 2000
            ):
                yield Message(
                    body=body, userID=sender, replyToID=thread_id, messageID=message_id
                )
        await task

    try:
        yield session, receive()
    finally:
        await stop_listener(task)


def run(coroutine: Coroutine[object, object, None]) -> None:
    try:
        asyncio.run(coroutine)
    except KeyboardInterrupt:
        print("Đã dừng bot.")
    except ConfigurationError as error:
        print(error)
        raise SystemExit(1) from None
    except Exception as error:
        print(f"Bot dừng: {type(error).__name__}. Không in cookie hoặc payload lỗi.")
        raise SystemExit(1) from None
