from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

import main as sample_main


class _FakeListener:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str, str]] = []
        self.send_result: dict[str, str] = {"messageId": "mid.reply"}

    async def send_e2ee_message(
        self,
        chat_jid: str,
        content: str,
        *,
        reply_to_id: str,
        reply_to_sender_jid: str,
    ) -> dict[str, str]:
        self.sent.append((chat_jid, content, reply_to_id, reply_to_sender_jid))
        return dict(self.send_result)


class _RecordingLoop:
    def __init__(self) -> None:
        self.calls: list[tuple[Callable[..., Any], tuple[Any, ...]]] = []

    def call_soon_threadsafe(self, callback: Callable[..., Any], *args: Any) -> None:
        self.calls.append((callback, args))


def _make_bot(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any], **kwargs: Any
) -> sample_main.SimpleBot:
    monkeypatch.setattr(
        sample_main, "listeningE2EEEvent", lambda data, **options: object()
    )
    return sample_main.SimpleBot(mock_dataFB, **kwargs)


@pytest.mark.asyncio
async def test_e2ee_ping_flows_from_listener_event_to_reply(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    listener = _FakeListener()
    monkeypatch.setattr(
        sample_main, "listeningE2EEEvent", lambda data, **options: listener
    )
    bot = sample_main.SimpleBot(mock_dataFB)
    bot._queue_event(
        {
            "type": "e2eeMessage",
            "data": {
                "id": "mid.incoming",
                "text": "/ping",
                "timestampMs": 0,
                "senderId": 2000,
                "chatJid": "2000@msgr",
                "senderJid": "2000:1@msgr",
            },
        }
    )

    event = await bot._get_event(timeout=0.1)
    assert event is not None
    message = bot._message_from_event(event)
    assert message is not None
    await bot._dispatch(message)

    assert len(listener.sent) == 1
    chat_jid, content, reply_to_id, sender_jid = listener.sent[0]
    assert chat_jid == "2000@msgr"
    assert content == "🏓 pong!"
    assert reply_to_id == "mid.incoming"
    assert sender_jid == "2000:1@msgr"


def test_auxiliary_event_storm_cannot_evict_message(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    bot = _make_bot(monkeypatch, mock_dataFB)

    for index in range(sample_main.EVENT_QUEUE_MAXSIZE * 2):
        bot._queue_event(
            {
                "type": ("typing", "readReceipt", "reaction")[index % 3],
                "data": {"sequence": index},
            }
        )

    assert bot._event_queue.empty()

    message_event = {
        "type": "e2eeMessage",
        "data": {"id": "mid.command", "senderId": 2000, "text": "/ping"},
    }
    bot._queue_event(message_event)

    assert bot._event_queue.get_nowait() == message_event
    assert bot._event_queue.empty()


def test_listener_thread_filters_noise_before_scheduling_asyncio_callback(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    bot = _make_bot(monkeypatch, mock_dataFB)
    loop = _RecordingLoop()

    for index in range(sample_main.EVENT_QUEUE_MAXSIZE * 2):
        bot._forward_listener_event(
            loop,  # type: ignore[arg-type]
            {"type": "typing", "data": {"sequence": index}},
        )
    message = {"type": "message", "data": {"id": "mid.live"}}
    bot._forward_listener_event(loop, message)  # type: ignore[arg-type]

    assert loop.calls == [(bot._queue_event, (message,))]


def test_control_event_is_logged_without_using_message_queue(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    output: list[str] = []
    monkeypatch.setattr(sample_main, "log", lambda tag, message: output.append(message))
    bot = _make_bot(monkeypatch, mock_dataFB)

    bot._queue_event({"type": "reconnected", "data": {}})

    assert bot._event_queue.empty()
    assert output == ["reconnected"]


def test_message_queue_overflow_is_redacted_and_counted(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    output: list[str] = []
    monkeypatch.setattr(sample_main, "log", lambda tag, message: output.append(message))
    bot = _make_bot(monkeypatch, mock_dataFB)
    bot._event_queue = asyncio.Queue(maxsize=1)
    first = {
        "type": "message",
        "data": {"id": "mid.private-1", "text": "FIRST_SECRET"},
    }
    second = {
        "type": "message",
        "data": {"id": "mid.private-2", "text": "SECOND_SECRET"},
    }

    bot._queue_event(first)
    bot._queue_event(second)

    assert bot._event_queue.get_nowait() == second
    assert bot._dropped_message_events == 1
    assert "FIRST_SECRET" not in "\n".join(output)
    assert "SECOND_SECRET" not in "\n".join(output)
    assert "đã loại 1 event" in "\n".join(output)


@pytest.mark.asyncio
async def test_empty_event_does_not_poison_populated_event_with_same_id(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    bot = _make_bot(monkeypatch, mock_dataFB)
    handled: list[str] = []

    async def handle_ping(message: dict[str, Any], argument: str) -> None:
        handled.append(str(message["messageID"]))

    bot._handlers["ping"] = handle_ping
    base_message = {
        "messageID": "mid.same",
        "userID": "2000",
        "replyToID": "3000",
        "type": "thread",
    }

    await bot._dispatch({**base_message, "body": None})
    await bot._dispatch({**base_message, "body": "/ping"})

    assert handled == ["mid.same"]


@pytest.mark.asyncio
async def test_placeholder_does_not_poison_decrypted_command_with_same_id(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    bot = _make_bot(monkeypatch, mock_dataFB)
    handled: list[str] = []

    async def handle_ping(message: dict[str, Any], argument: str) -> None:
        handled.append(str(message["messageID"]))

    bot._handlers["ping"] = handle_ping
    base_message = {
        "messageID": "mid.placeholder",
        "userID": "2000",
        "replyToID": "3000",
        "type": "thread",
    }

    await bot._dispatch({**base_message, "body": "Encrypted placeholder"})
    await bot._dispatch({**base_message, "body": "/ping"})

    assert handled == ["mid.placeholder"]


@pytest.mark.asyncio
async def test_message_ids_are_deduplicated_out_of_order(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    bot = _make_bot(monkeypatch, mock_dataFB)
    handled: list[str] = []

    async def handle_ping(message: dict[str, Any], argument: str) -> None:
        handled.append(str(message["messageID"]))

    handler: Callable[[dict[str, Any], str], Awaitable[None]] = handle_ping
    bot._handlers["ping"] = handler

    for message_id in ("mid.1", "mid.2", "mid.1"):
        await bot._dispatch(
            {
                "messageID": message_id,
                "body": "/ping",
                "userID": "2000",
                "replyToID": "3000",
                "type": "thread",
            }
        )

    assert handled == ["mid.1", "mid.2"]


@pytest.mark.asyncio
async def test_plain_text_is_ignored_but_prefixed_command_runs(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    bot = _make_bot(monkeypatch, mock_dataFB)
    handled: list[str] = []

    async def handle_ping(message: dict[str, Any], argument: str) -> None:
        handled.append(argument)

    bot._handlers["ping"] = handle_ping
    for message_id, body in (("mid.plain", "ping"), ("mid.command", "/ping")):
        await bot._dispatch(
            {
                "messageID": message_id,
                "body": body,
                "userID": "2000",
                "replyToID": "3000",
                "type": "thread",
            }
        )

    assert handled == [""]


@pytest.mark.asyncio
async def test_unsend_is_denied_when_admin_list_is_empty(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    bot = _make_bot(monkeypatch, mock_dataFB, admins=[])
    replies: list[str] = []

    async def record_reply(message: dict[str, Any], text: str) -> None:
        replies.append(text)

    monkeypatch.setattr(bot, "_reply", record_reply)

    await bot._cmd_unsend(
        {"userID": "2000", "chatJid": "2000@msgr"},
        "",
    )

    assert replies == ["⛔ Lệnh này bị khóa vì chưa cấu hình admin."]


@pytest.mark.asyncio
async def test_unknown_e2ee_delivery_is_not_cached_or_logged_as_success(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    listener = _FakeListener()
    listener.send_result = {
        "messageId": "mid-timeout",
        "deliveryStatus": sample_main.DELIVERY_STATUS_UNKNOWN,
    }
    monkeypatch.setattr(
        sample_main, "listeningE2EEEvent", lambda data, **options: listener
    )
    output: list[str] = []
    monkeypatch.setattr(sample_main, "log", lambda tag, message: output.append(message))
    bot = sample_main.SimpleBot(mock_dataFB)

    await bot._reply(
        {
            "chatJid": "2000@msgr",
            "messageID": "mid.incoming",
            "senderJid": "2000:1@msgr",
        },
        "PRIVATE_REPLY",
    )

    assert bot._last_bot_message == {}
    assert len(output) == 1
    assert any("E2EE UNKNOWN" in line for line in output)
    assert any("mid-timeout" in line for line in output)
    assert all("E2EE ->" not in line for line in output)
    assert all("PRIVATE_REPLY" not in line for line in output)


def test_search_rate_limiter_enforces_sender_and_global_sliding_windows() -> None:
    now = [100.0]
    limiter = sample_main._SearchRateLimiter(
        per_sender_limit=2,
        global_limit=3,
        window_seconds=10.0,
        clock=lambda: now[0],
    )

    assert limiter.check("sender-a") is None
    assert limiter.check("sender-a") is None
    assert limiter.check("sender-a") == "sender"
    assert limiter.check("sender-b") is None
    assert limiter.check("sender-c") == "global"

    now[0] = 110.0
    assert limiter.check("sender-c") is None


@pytest.mark.asyncio
async def test_search_validates_and_normalizes_query_before_provider(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    bot = _make_bot(monkeypatch, mock_dataFB)
    queries: list[str] = []
    replies: list[str] = []

    async def fake_search(
        dataFB: dict[str, Any], query: str, **kwargs: Any
    ) -> dict[str, list[Any]]:
        queries.append(query)
        return {"searchResultsDict": []}

    async def record_reply(message: dict[str, Any], text: str) -> None:
        replies.append(text)

    monkeypatch.setattr(sample_main._search, "func", fake_search)
    monkeypatch.setattr(bot, "_reply", record_reply)
    message = {"userID": "sender-a"}

    await bot._cmd_search(message, "x")
    await bot._cmd_search(message, "x" * (sample_main.SEARCH_QUERY_MAX_LENGTH + 1))
    await bot._cmd_search(message, "  Alice\n  Bob  ")

    assert queries == ["Alice Bob"]
    assert "ít nhất 2 ký tự" in replies[0]
    assert "không được vượt quá 100 ký tự" in replies[1]


@pytest.mark.asyncio
async def test_search_rate_limit_blocks_provider_and_redacts_telemetry(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    bot = _make_bot(monkeypatch, mock_dataFB)
    bot._search_rate_limiter = sample_main._SearchRateLimiter(
        per_sender_limit=1,
        global_limit=2,
        window_seconds=60.0,
        clock=lambda: 100.0,
    )
    queries: list[str] = []
    replies: list[str] = []
    logs: list[str] = []

    async def fake_search(
        dataFB: dict[str, Any], query: str, **kwargs: Any
    ) -> dict[str, list[Any]]:
        queries.append(query)
        return {"searchResultsDict": []}

    async def record_reply(message: dict[str, Any], text: str) -> None:
        replies.append(text)

    monkeypatch.setattr(sample_main._search, "func", fake_search)
    monkeypatch.setattr(bot, "_reply", record_reply)
    monkeypatch.setattr(sample_main, "log", lambda tag, text: logs.append(text))
    message = {"userID": "sender-a"}

    await bot._cmd_search(message, "PRIVATE_QUERY")
    await bot._cmd_search(message, "PRIVATE_QUERY")

    assert queries == ["PRIVATE_QUERY"]
    assert any("thử lại sau" in reply for reply in replies)
    assert logs == ["Từ chối /search do chạm quota sender; query đã ẩn."]
    assert all("PRIVATE_QUERY" not in line for line in logs)
