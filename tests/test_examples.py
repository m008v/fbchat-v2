from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import importlib.util
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def samples(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "examples"))
    modules = []
    for filename in ("01_echo_bot", "02_group_manager", "03_e2ee_bot"):
        spec = importlib.util.spec_from_file_location(
            "sample_" + filename, ROOT / "examples" / (filename + ".py")
        )
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


def test_echo_example_is_under_twenty_lines_and_imports_are_idle(samples):
    assert len((ROOT / "examples/01_echo_bot.py").read_text().splitlines()) < 20
    assert len(samples) == 3


def test_runner_does_not_print_provider_secret(samples, capsys):
    import _common as common

    async def fail():
        raise RuntimeError("PRIVATE_COOKIE_DETAIL")

    with pytest.raises(SystemExit) as error:
        common.run(fail())
    assert error.value.code == 1
    output = capsys.readouterr()
    assert "RuntimeError" in output.out
    assert "PRIVATE_COOKIE_DETAIL" not in output.out + output.err


@pytest.mark.asyncio
async def test_echo_replies_once_without_real_session(samples, monkeypatch):
    echo = samples[0]
    message = {"body": "hello", "replyToID": "42"}

    async def messages():
        yield message

    @asynccontextmanager
    async def session():
        yield {"FacebookID": "1"}, messages()

    send = AsyncMock(return_value={"messageID": "reply"})
    monkeypatch.setattr(echo, "standard_messages", session)
    monkeypatch.setattr(echo, "SendAPI", lambda: type("Sender", (), {"send": send})())
    await echo.main()
    send.assert_awaited_once_with({"FacebookID": "1"}, "hello", "42")


@pytest.mark.parametrize("argument", ["", "Q | one", "Q | one |", "Q | one | one"])
def test_poll_rejects_invalid_options(samples, argument):
    with pytest.raises(ValueError):
        samples[1].Poll.parse(argument)


def test_poll_updates_vote_instead_of_duplicating_it(samples):
    poll = samples[1].Poll.parse("Ngày nào? | Thứ bảy | Chủ nhật")
    poll.vote("user", "1")
    poll.vote("user", "2")
    assert poll.votes == {"user": 2}
    assert "2. Chủ nhật: 1 phiếu" in poll.results()
    assert "không hợp lệ" in poll.vote("other", "99")
    assert len(poll.votes) == 1


@pytest.mark.asyncio
async def test_group_manager_denies_non_admin_without_provider_call(
    samples, monkeypatch
):
    group = samples[1]
    change = AsyncMock()
    monkeypatch.setattr(group._changeNickname, "func", change)
    manager = group.GroupManager("admin")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: None)
    ) as client:
        for command in ("/nick 123 Name", "/members", "/poll Q | a | b", "/close"):
            reply = await manager.handle(
                {"body": command, "userID": "other", "replyToID": "42"}, {}, client
            )
            assert "Chỉ admin" in reply
    change.assert_not_awaited()
    assert manager.poll is None


@pytest.mark.asyncio
async def test_group_manager_poll_and_nickname_flow(samples, monkeypatch):
    group = samples[1]
    change = AsyncMock(return_value={"status": "success", "message": "fixture"})
    monkeypatch.setattr(group._changeNickname, "func", change)
    manager = group.GroupManager("admin")
    async with httpx.AsyncClient() as client:

        async def command(text, sender="admin"):
            return await manager.handle(
                {"body": text, "userID": sender, "replyToID": "42"}, {}, client
            )

        assert "Đã đổi" in await command("/nick 123 Test")
        change.assert_awaited_once_with({}, "42", "123", "Test", client=client)
        change.return_value = {"status": "error", "message": "fixture"}
        assert "Không đổi được" in await command("/nick 123 Test")
        assert "Trả lời bằng số" in await command("/poll Q | a | b")
        await command("2", "voter")
        assert "2. b: 1 phiếu" in await command("/results", "voter")
        assert "2. b: 1 phiếu" in await command("/close")
        assert manager.poll is None


@pytest.mark.asyncio
async def test_member_filter_does_not_expose_other_groups(samples, monkeypatch):
    group = samples[1]
    monkeypatch.setattr(
        group._all_thread_data, "func", AsyncMock(return_value={"dataGet": "fixture"})
    )
    export = AsyncMock(
        return_value=['{"123": {"nameFB": "An"}}', '{"456": {"nameFB": "Bình"}}']
    )
    monkeypatch.setattr(group._all_thread_data, "features", export)
    async with httpx.AsyncClient() as client:
        assert await group.find_members({}, "42", "AN", client) == "An: 123"
        export.assert_awaited_once_with("fixture", "42", "exportMemberListToJson")


@pytest.mark.asyncio
async def test_common_filters_self_other_thread_and_closes_worker(samples, monkeypatch):
    import _common as common

    monkeypatch.setenv("FB_THREAD_ID", "42")
    monkeypatch.setattr(common, "login", AsyncMock(return_value={"FacebookID": "1"}))
    events = [
        {"body": "self", "replyToID": "42", "userID": "1", "messageID": "a"},
        {"body": "other", "replyToID": "99", "userID": "2", "messageID": "b"},
        {"body": None, "replyToID": "42", "userID": "2", "messageID": "c"},
        {
            "body": " " * 2000 + "x",
            "replyToID": "42",
            "userID": "2",
            "messageID": "long",
        },
        {"body": "hello", "replyToID": "42", "userID": "2", "messageID": "d"},
    ]
    finished = asyncio.Event()
    closed = asyncio.Event()

    class Listener:
        async def connect_mqtt(self):
            try:
                await finished.wait()
            finally:
                closed.set()

        async def get_message(self, timeout):
            await asyncio.sleep(0)
            if events:
                return events.pop(0)
            finished.set()

    monkeypatch.setattr(common, "listeningEvent", lambda *a, **kw: Listener())
    async with common.standard_messages() as (_, messages):
        result = [message async for message in messages]
    assert [m["body"] for m in result] == ["hello"]
    assert closed.is_set()


@pytest.mark.asyncio
async def test_common_cancels_listener_when_consumer_fails(samples, monkeypatch):
    import _common as common

    monkeypatch.setenv("FB_THREAD_ID", "42")
    monkeypatch.setattr(common, "login", AsyncMock(return_value={"FacebookID": "1"}))
    closed = asyncio.Event()

    class Listener:
        async def connect_mqtt(self):
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()

        async def get_message(self, timeout):
            await asyncio.sleep(0)
            return {"body": "hello", "replyToID": "42", "userID": "2", "messageID": "a"}

    monkeypatch.setattr(common, "listeningEvent", lambda *a, **kw: Listener())
    with pytest.raises(ValueError, match="consumer"):
        async with common.standard_messages() as (_, messages):
            async for _ in messages:
                raise ValueError("consumer")
    assert closed.is_set()


@pytest.mark.asyncio
async def test_e2ee_only_replies_to_selected_encrypted_peer(
    samples, monkeypatch, capsys
):
    e2ee = samples[2]
    monkeypatch.setenv("FB_CHAT_JID", "selected@msgr")
    monkeypatch.setattr(e2ee, "login", AsyncMock(return_value={"FacebookID": "1"}))
    done = asyncio.Event()
    sent = []
    closed = asyncio.Event()

    class Listener:
        startup_timeout = 1
        connection_state = "connected"

        def on_message(self, callback):
            self.callback = callback

        def wait_until_connected(self, timeout, *, require_e2ee):
            assert require_e2ee
            return True

        async def connect_mqtt(self):
            try:
                for kind, chat, sender in (
                    ("message", "selected@msgr", "2"),
                    ("e2eeMessage", "other@msgr", "2"),
                    ("e2eeMessage", "selected@msgr", "1"),
                    ("e2eeMessage", "selected@msgr", "2"),
                ):
                    self.callback(
                        {
                            "type": kind,
                            "data": {
                                "chatJid": chat,
                                "senderId": sender,
                                "id": "mid",
                                "text": "/ping",
                            },
                        }
                    )
                await done.wait()
            finally:
                closed.set()

        async def send_e2ee_message(self, *args, **kwargs):
            sent.append((args, kwargs))
            done.set()
            await asyncio.sleep(0)
            return {"deliveryStatus": "unknown"}

    monkeypatch.setattr(e2ee, "listeningE2EEEvent", lambda *a, **kw: Listener())
    await e2ee.main()
    assert len(sent) == 1
    assert sent[0][0] == ("selected@msgr", "pong")
    assert closed.is_set()
    assert "unknown" in capsys.readouterr().out
