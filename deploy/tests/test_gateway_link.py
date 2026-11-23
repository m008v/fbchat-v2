from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx
import pytest

import gateway_link
import main as upstream_main
import multi_main
from gateway_link import (
    audio_seconds,
    GatewayLink,
    describe_attachment,
    summarize,
    describe_message,
    fetch_attachment,
    file_name,
    media_rpc,
    thread_ref,
)

TOKEN = "0123456789abcdef0123456789abcdef"


class _Listener:
    startup_timeout = 1.0
    device_path: str | None = None

    def __init__(self) -> None:
        self.e2ee: list[tuple[str, str]] = []
        self.regular: list[tuple[int, str]] = []
        self.reply_args: list[tuple[Any, ...]] = []
        self.fail = False
        self.result: dict[str, Any] = {"messageId": "mid.out"}

    def on_message(self, callback: Any) -> None:
        pass

    async def send_e2ee_message(
        self, chat_jid: str, text: str, *args: Any
    ) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("bridge down")
        self.e2ee.append((chat_jid, text))
        self.reply_args.append(args)
        return self.result

    async def send_message(
        self, thread_id: int, text: str, *args: Any
    ) -> dict[str, Any]:
        self.regular.append((thread_id, text))
        self.reply_args.append(args)
        return self.result


class _FakeBridge:
    def __init__(self, data: bytes = b"FILEDATA") -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.data = base64.b64encode(data).decode()

    async def call(
        self, method: str, params: dict[str, Any] | None = None, timeout: float = 60.0
    ) -> dict[str, Any]:
        self.calls.append((method, params or {}))
        if method.startswith("download"):
            return {"data": self.data, "mimeType": "image/jpeg"}
        return {"messageId": "mid.media"}


class _Bot:
    def __init__(self) -> None:
        self.dataFB = {"FacebookID": "100"}
        self.listener = _Listener()
        self.listener._bridge = _FakeBridge()  # type: ignore[attr-defined]


def _link(handler: Any) -> GatewayLink:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GatewayLink("http://gateway:8080", TOKEN, client, lambda tag, msg: None)


def test_thread_ref_distinguishes_e2ee_one_to_one_and_group() -> None:
    assert thread_ref({"chatJid": "123@msgr"}) == ("e2ee:123@msgr", False)
    assert thread_ref({"chatJid": "3858@g.us"}) == ("e2ee:3858@g.us", True)
    assert thread_ref({"raw": {"threadId": 55, "threadType": 1}}) == (
        "thread:55",
        False,
    )
    assert thread_ref({"raw": {"threadId": 56, "threadType": 2}}) == ("thread:56", True)
    assert thread_ref({"raw": {}}) is None


def test_describe_message_includes_attachments() -> None:
    message = {
        "body": "xem ảnh",
        "attachments": [{"type": "image", "url": "https://x/y.jpg"}],
    }
    assert describe_message(message) == "xem ảnh\n🖼️ Ảnh\nhttps://x/y.jpg"
    assert describe_message({"body": "", "attachments": []}) == ""


def test_media_labels_and_summary_without_urls() -> None:
    video = {"type": "video", "fileName": "clip.mp4", "url": "https://cdn/v.mp4"}
    assert describe_attachment(video) == "🎬 Video: clip.mp4\nhttps://cdn/v.mp4"
    assert (
        describe_attachment({"type": "file", "fileName": "FIP.pdf"})
        == "📎 Tệp: FIP.pdf"
    )
    assert describe_attachment({"type": "voice"}) == "🎤 Tin thoại"
    assert describe_attachment({"type": "poll"}) == "[poll]"
    message = {"body": "", "attachments": [{"type": "image", "url": "https://x/y.jpg"}]}
    assert summarize(message) == "🖼️ Ảnh"


@pytest.mark.asyncio
async def test_forward_posts_inbound_with_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={})

    async def fake_user_info(
        dataFB: dict[str, Any], user_id: str, **_: Any
    ) -> dict[str, Any]:
        return {"nameUser": f"User {user_id}", "thumbSrc": f"https://cdn/{user_id}.jpg"}

    monkeypatch.setattr(gateway_link._get_user_info, "func", fake_user_info)
    link = _link(handler)
    group = {
        "messageID": "m1",
        "userID": "7",
        "body": "chào",
        "raw": {"threadId": 9, "threadType": 2, "threadName": "Nhóm A"},
    }
    await link.forward("acc1", _Bot(), group)
    direct = {"messageID": "m2", "userID": "8", "body": "hi", "chatJid": "8@msgr"}
    await link.forward("acc1", _Bot(), direct)

    assert sent[0] == {
        "channel": "facebook",
        "account": "acc1",
        "thread_id": "thread:9",
        "is_group": True,
        "thread_name": "Nhóm A",
        "sender_name": "User 7",
        "text": "chào",
        "message_id": "m1",
        "attachments": [],
        "quote": "",
        "thread_avatar": "",
        "sender_avatar": "https://cdn/7.jpg",
    }
    assert sent[1]["thread_id"] == "e2ee:8@msgr" and sent[1]["thread_name"] == "User 8"
    # 1-1: ảnh đại diện của người nhắn; nhóm thì chưa có.
    assert sent[1]["thread_avatar"] == "https://cdn/8.jpg"


@pytest.mark.asyncio
async def test_send_reply_routes_by_thread_prefix_and_dedupes() -> None:
    link = _link(lambda r: httpx.Response(200))
    bot = _Bot()
    link.bots["acc1"] = bot  # type: ignore[assignment]

    status, _ = await link.send_reply(
        {"account": "acc1", "thread_id": "e2ee:8@msgr", "text": "a", "message_id": "r1"}
    )
    assert status == 200
    assert await link.send_reply(
        {"account": "acc1", "thread_id": "e2ee:8@msgr", "text": "a", "message_id": "r1"}
    ) == (200, "duplicate")
    status, _ = await link.send_reply(
        {"account": "acc1", "thread_id": "thread:9", "text": "b", "message_id": "r2"}
    )
    assert status == 200
    assert (
        await link.send_reply(
            {
                "account": "acc1",
                "thread_id": "thread:abc",
                "text": "c",
                "message_id": "r3",
            }
        )
    )[0] == 400
    assert (
        await link.send_reply({"account": "nope", "thread_id": "thread:9", "text": "c"})
    )[0] == 404
    assert bot.listener.e2ee == [("8@msgr", "a")]
    assert bot.listener.regular == [(9, "b")]


@pytest.mark.asyncio
async def test_send_reply_bridge_error_allows_retry() -> None:
    link = _link(lambda r: httpx.Response(200))
    bot = _Bot()
    link.bots["acc1"] = bot  # type: ignore[assignment]
    bot.listener.fail = True
    payload = {
        "account": "acc1",
        "thread_id": "e2ee:8@msgr",
        "text": "a",
        "message_id": "r1",
    }
    assert (await link.send_reply(payload))[0] == 502
    bot.listener.fail = False
    assert (await link.send_reply(payload))[0] == 200


@pytest.mark.asyncio
async def test_http_server_requires_token_and_sends() -> None:
    link = _link(lambda r: httpx.Response(200))
    bot = _Bot()
    link.bots["acc1"] = bot  # type: ignore[assignment]
    server = await asyncio.start_server(link._handle_connection, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            body = {
                "account": "acc1",
                "thread_id": "thread:9",
                "text": "xin chào",
                "message_id": "r9",
            }
            bad = await client.post(
                "/send", json=body, headers={"Authorization": "Bearer wrong"}
            )
            good = await client.post(
                "/send", json=body, headers={"Authorization": f"Bearer {TOKEN}"}
            )
            missing = await client.post(
                "/other", json=body, headers={"Authorization": f"Bearer {TOKEN}"}
            )
            react = await client.post(
                "/react",
                json={
                    "account": "acc1",
                    "thread_id": "thread:9",
                    "message_id": "m1",
                    "emoji": "👍",
                },
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
    finally:
        server.close()
        await server.wait_closed()
    assert (bad.status_code, good.status_code, missing.status_code) == (401, 200, 404)
    assert react.status_code == 200  # /react phải qua được bộ lọc route HTTP
    assert bot.listener.regular == [(9, "xin chào")]


@pytest.mark.asyncio
async def test_account_bot_forwards_to_gateway_instead_of_commands(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    listener = _Listener()
    monkeypatch.setattr(
        upstream_main, "listeningE2EEEvent", lambda data, **options: listener
    )
    forwarded: list[str] = []

    owner: list[str] = []

    class _FakeGateway:
        async def forward(
            self, account: str, bot: Any, message: dict[str, Any]
        ) -> None:
            forwarded.append(message["body"])

        async def forward_owner(
            self, account: str, bot: Any, message: dict[str, Any]
        ) -> None:
            owner.append(message["body"])

    monkeypatch.setattr(multi_main, "_gateway", _FakeGateway())
    monkeypatch.setattr(multi_main, "COMMANDS_FLAG", False)
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")

    await bot._dispatch(
        {"messageID": "m1", "userID": "555", "body": "/ping", "chatJid": "555@msgr"}
    )
    await bot._dispatch(
        {
            "messageID": "m2",
            "userID": mock_dataFB["FacebookID"],
            "body": "own",
            "chatJid": "x",
        }
    )

    assert forwarded == ["/ping"]  # chuyển nguyên văn, không chạy lệnh
    assert owner == ["own"]  # tin của chính tài khoản đi nhánh ghi chú
    assert listener.e2ee == []


@pytest.mark.asyncio
async def test_fetch_attachment_uses_e2ee_or_regular_download() -> None:
    bridge = _FakeBridge(b"IMG")
    e2ee = {
        "type": "image",
        "directPath": "/v/t62",
        "mediaKey": "a2V5",
        "mediaSha256": "c2hh",
        "mediaEncSha256": "ZW5j",
        "mimeType": "image/jpeg",
        "fileSize": 3,
    }
    file = await fetch_attachment(bridge, e2ee)  # type: ignore[arg-type]
    assert file == {
        "name": "image.jpg",
        "content_type": "image/jpeg",
        "data": base64.b64encode(b"IMG").decode(),
    }
    assert (
        bridge.calls[0][0] == "downloadE2EEMedia"
        and bridge.calls[0][1]["mediaType"] == "image"
    )

    regular = {
        "type": "file",
        "url": "https://cdn.fb/x.pdf",
        "fileName": "x.pdf",
        "mimeType": "application/pdf",
    }
    assert (await fetch_attachment(bridge, regular))["name"] == "x.pdf"  # type: ignore[arg-type,index]
    assert bridge.calls[1] == ("downloadMedia", {"url": "https://cdn.fb/x.pdf"})

    assert await fetch_attachment(bridge, {"type": "location", "latitude": 1, "longitude": 2}) is None  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await fetch_attachment(bridge, {"type": "video", "url": "https://x", "fileSize": 999 << 20})  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_fetch_attachment_sniffs_mime_when_missing() -> None:
    # Sticker Messenger tải qua URL CDN không có mimeType: đoán từ chữ ký tệp.
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    sticker = {"type": "sticker", "url": "https://cdn.fb/s"}
    file = await fetch_attachment(_FakeBridge(png), sticker)  # type: ignore[arg-type]
    assert file is not None
    assert (file["name"], file["content_type"]) == ("sticker.png", "image/png")

    webp = b"RIFF\x10\x00\x00\x00WEBPVP8 "
    file = await fetch_attachment(_FakeBridge(webp), sticker)  # type: ignore[arg-type]
    assert file is not None and file["name"] == "sticker.webp"

    # Không nhận ra thì giữ như cũ; MIME đã khai thì không đoán đè.
    file = await fetch_attachment(_FakeBridge(b"???"), sticker)  # type: ignore[arg-type]
    assert file is not None and file["name"] == "sticker.bin"
    declared = {**sticker, "type": "file", "mimeType": "application/pdf"}
    file = await fetch_attachment(_FakeBridge(png), declared)  # type: ignore[arg-type]
    assert file is not None and file["content_type"] == "application/pdf"


def test_file_name_audio_and_mime_family() -> None:
    # Tin thoại Messenger (opus) và audio aac từng thành "audio.bin"/"voice.bin" (omi 24/11/2026).
    assert file_name("", "audio/opus", "audio") == "audio.opus"
    assert file_name(None, "audio/aac", "voice") == "voice.aac"
    # GIF Messenger tới với type "video" nhưng là webp: tên theo loại thật.
    assert file_name("", "image/webp", "video") == "image.webp"
    assert file_name("", "video/mp4", "video") == "video.mp4"
    # Tên có sẵn và loại khác (sticker, file) giữ nguyên.
    assert file_name("bao-gia.pdf", "application/pdf", "file") == "bao-gia.pdf"
    assert file_name("", "image/png", "sticker") == "sticker.png"


def test_media_rpc_picks_method_by_chat_and_mime() -> None:
    img = {"name": "a", "content_type": "image/png", "data": "QQ=="}
    doc = {"name": "bao-gia.pdf", "content_type": "application/pdf", "data": "QQ=="}
    assert media_rpc("e2ee", "8@msgr", img)[0] == "sendE2EEImage"
    method, params = media_rpc("e2ee", "8@msgr", doc)
    assert (
        method == "sendE2EEDocument"
        and params["filename"] == "bao-gia.pdf"
        and params["chatJid"] == "8@msgr"
    )
    assert (
        media_rpc("e2ee", "8@msgr", {**img, "content_type": "video/mp4"})[0]
        == "sendE2EEVideo"
    )
    method, params = media_rpc("e2ee", "8@msgr", {**img, "content_type": "audio/mpeg"})
    # Audio đi thành tin thoại (ptt); mp3 không đọc được thời lượng thì 0.
    assert method == "sendE2EEAudio" and params["ptt"] is True
    assert params["duration"] == 0
    method, params = media_rpc("thread", "9", img)
    assert (
        method == "sendImage"
        and params["threadId"] == 9
        and params["filename"] == "a.png"
    )
    assert media_rpc("thread", "9", doc)[0] == "sendFile"


@pytest.mark.asyncio
async def test_send_reply_sends_text_then_files() -> None:
    link = _link(lambda r: httpx.Response(200))
    bot = _Bot()
    link.bots["acc1"] = bot  # type: ignore[assignment]
    payload = {
        "account": "acc1",
        "thread_id": "e2ee:8@msgr",
        "text": "gửi bạn file",
        "message_id": "r1",
        "attachments": [
            {"name": "a.pdf", "content_type": "application/pdf", "data": "UERG"}
        ],
    }
    assert (await link.send_reply(payload))[0] == 200
    assert bot.listener.e2ee == [("8@msgr", "gửi bạn file")]
    assert [c[0] for c in bot.listener._bridge.calls] == ["sendE2EEDocument"]  # type: ignore[attr-defined]

    only_file = {
        "account": "acc1",
        "thread_id": "thread:9",
        "text": "",
        "message_id": "r2",
        "attachments": [
            {"name": "p.jpg", "content_type": "image/jpeg", "data": "SlBH"}
        ],
    }
    assert (await link.send_reply(only_file))[0] == 200
    assert bot.listener.regular == []
    bad = {
        **only_file,
        "message_id": "r3",
        "attachments": [{"name": "x", "data": "@@@"}],
    }
    assert (await link.send_reply(bad))[0] == 400


@pytest.mark.asyncio
async def test_forward_includes_downloaded_attachments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={})

    async def fake_user_info(
        dataFB: dict[str, Any], user_id: str, **_: Any
    ) -> dict[str, Any]:
        return {"nameUser": "Khách"}

    monkeypatch.setattr(gateway_link._get_user_info, "func", fake_user_info)
    link = _link(handler)
    message = {
        "messageID": "m9",
        "userID": "7",
        "body": "",
        "chatJid": "7@msgr",
        "attachments": [
            {
                "type": "image",
                "directPath": "/p",
                "mediaKey": "aw==",
                "mimeType": "image/jpeg",
                "fileSize": 8,
            },
            {"type": "location", "latitude": 10.7, "longitude": 106.6},
        ],
    }
    await link.forward("acc1", _Bot(), message)
    assert sent[0]["text"] == "📍 Vị trí\nhttps://maps.google.com/?q=10.7,106.6"
    assert [a["name"] for a in sent[0]["attachments"]] == ["image.jpg"]


@pytest.mark.asyncio
async def test_forward_logs_sticker_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []
    logs: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={})

    async def fake_user_info(
        dataFB: dict[str, Any], user_id: str, **_: Any
    ) -> dict[str, Any]:
        return {"nameUser": "Khách"}

    monkeypatch.setattr(gateway_link._get_user_info, "func", fake_user_info)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    link = GatewayLink(
        "http://gateway:8080", TOKEN, client, lambda tag, msg: logs.append(msg)
    )
    message = {
        "messageID": "m10",
        "userID": "7",
        "body": "",
        "chatJid": "7@msgr",
        "attachments": [
            {"type": "sticker", "fetchError": "receiver fetch returned HTTP 401"}
        ],
    }
    await link.forward("acc1", _Bot(), message)
    assert sent[0]["text"] == "🧩 Sticker"
    assert "Không lấy được sticker: receiver fetch returned HTTP 401" in logs


def _recording_link() -> tuple[GatewayLink, list[tuple[str, dict[str, Any]]]]:
    calls: list[tuple[str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={})

    return _link(handler), calls


async def _names(dataFB: dict[str, Any], user_id: str, **_: Any) -> dict[str, Any]:
    return {"nameUser": f"User {user_id}"}


def test_describe_attachment_location_link_sticker() -> None:
    loc = {
        "type": "location",
        "latitude": 10.77,
        "longitude": 106.7,
        "description": "Quán",
    }
    assert (
        describe_attachment(loc)
        == "📍 Vị trí: Quán\nhttps://maps.google.com/?q=10.77,106.7"
    )
    link = {
        "type": "link",
        "url": "https://shop.vn/a",
        "description": "Áo thun",
        "sourceText": "shop.vn",
    }
    assert describe_attachment(link) == "🔗 Áo thun\nhttps://shop.vn/a\nshop.vn"
    sticker = {"type": "sticker", "url": "https://cdn/s.png", "fileName": "s"}
    assert describe_attachment({"type": "sticker"}) == "🧩 Sticker"
    assert describe_attachment(sticker) == "🧩 Sticker"


@pytest.mark.asyncio
async def test_quote_uses_cached_text_for_e2ee_replies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    link, calls = _recording_link()
    first = {
        "messageID": "m1",
        "userID": "7",
        "body": "giá bao nhiêu?",
        "chatJid": "7@msgr",
    }
    await link.forward("acc1", _Bot(), first)
    reply = {
        "messageID": "m2",
        "userID": "7",
        "body": "còn hàng không?",
        "chatJid": "7@msgr",
        "raw": {"replyTo": {"messageId": "m1"}},
    }
    await link.forward("acc1", _Bot(), reply)
    regular = {
        "messageID": "m3",
        "userID": "8",
        "body": "ok",
        "raw": {
            "threadId": 5,
            "threadType": 1,
            "replyTo": {"messageId": "zz", "text": "tin cũ"},
        },
    }
    await link.forward("acc1", _Bot(), regular)
    assert calls[0][1]["quote"] == ""
    assert calls[1][1]["quote"] == "User 7: giá bao nhiêu?"
    assert calls[2][1]["quote"] == "tin cũ"


@pytest.mark.asyncio
async def test_owner_message_note_skips_bot_echoes() -> None:
    link, calls = _recording_link()
    bot = _Bot()
    link.bots["acc1"] = bot  # type: ignore[assignment]
    # Bot gửi trả lời nhân viên: tin này có thể quay về như tin của chính tài khoản.
    await link.send_reply(
        {
            "account": "acc1",
            "thread_id": "e2ee:8@msgr",
            "text": "nhân viên trả lời",
            "message_id": "r1",
        }
    )
    echo = {
        "messageID": "mid.other",
        "userID": "100",
        "body": "nhân viên trả lời",
        "chatJid": "8@msgr",
    }
    await link.forward_owner("acc1", bot, echo)
    by_id = {
        "messageID": "mid.out",
        "userID": "100",
        "body": "khác",
        "chatJid": "8@msgr",
    }  # id trả về từ send
    await link.forward_owner("acc1", bot, by_id)
    phone = {
        "messageID": "m9",
        "userID": "100",
        "body": "chủ shop trả lời từ điện thoại",
        "chatJid": "8@msgr",
    }
    await link.forward_owner("acc1", bot, phone)
    events = [c[1] for c in calls if c[0] == "/v1/event"]
    assert len(events) == 1
    assert (
        events[0]["kind"] == "owner_message" and events[0]["thread_id"] == "e2ee:8@msgr"
    )
    assert events[0]["text"] == "chủ shop trả lời từ điện thoại"


@pytest.mark.asyncio
async def test_meta_events_become_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    link, calls = _recording_link()
    bot = _Bot()
    await link.forward(
        "acc1",
        bot,
        {"messageID": "m1", "userID": "7", "body": "giá 5 triệu", "chatJid": "7@msgr"},
    )
    await link.handle_meta(
        "acc1",
        bot,
        {
            "type": "e2eeReaction",
            "data": {
                "chatJid": "7@msgr",
                "messageId": "m1",
                "reaction": "❤️",
                "senderId": 7,
            },
        },
    )
    await link.handle_meta(
        "acc1",
        bot,
        {
            "type": "messageEdit",
            "data": {"messageId": "m1", "newText": "giá 4 triệu", "editCount": 1},
        },
    )
    await link.handle_meta(
        "acc1",
        bot,
        {"type": "messageEdit", "data": {"messageId": "unknown", "newText": "x"}},
    )
    await link.handle_meta(
        "acc1",
        bot,
        {
            "type": "messageUnsend",
            "data": {"isE2EE": True, "messageId": "m1", "threadId": "7@msgr"},
        },
    )
    events = [c[1] for c in calls if c[0] == "/v1/event"]
    assert [(e["kind"], e["thread_id"]) for e in events] == [
        ("reaction", "e2ee:7@msgr"),
        ("edit", "e2ee:7@msgr"),
        ("recall", "e2ee:7@msgr"),
    ]
    assert (
        events[0]["text"] == "❤️ vào tin «giá 5 triệu»"
        and events[0]["sender_name"] == "User 7"
    )
    # Gateway dùng mấy trường này để hiện huy hiệu trên đúng tin.
    assert events[0]["target_ids"] == ["m1"]
    assert events[0]["reactor_id"] == "7"
    assert events[0]["reaction"] == "❤️"
    assert events[1]["text"] == "«giá 5 triệu» → «giá 4 triệu»"
    assert events[2]["text"] == "«giá 4 triệu»"


@pytest.mark.asyncio
async def test_account_bot_routes_meta_events_to_gateway(
    monkeypatch: pytest.MonkeyPatch, mock_dataFB: dict[str, Any]
) -> None:
    monkeypatch.setattr(
        upstream_main, "listeningE2EEEvent", lambda data, **options: _Listener()
    )
    handled: list[str] = []

    class _FakeGateway:
        async def handle_meta(
            self, account: str, bot: Any, event: dict[str, Any]
        ) -> None:
            handled.append(event["type"])

        async def post_presence(self, account: str, event: dict[str, Any]) -> None:
            handled.append("presence:" + event["type"])

    monkeypatch.setattr(multi_main, "_gateway", _FakeGateway())
    bot = multi_main.AccountBot(mock_dataFB, account="acc1", device_path="/d.json")
    loop = asyncio.get_running_loop()
    bot._forward_listener_event(loop, {"type": "messageUnsend", "data": {}})
    bot._forward_listener_event(loop, {"type": "typing", "data": {}})
    await asyncio.sleep(0.05)
    assert handled == ["messageUnsend", "presence:typing"]


@pytest.mark.asyncio
async def test_cache_is_per_account(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cùng một tin được hai tài khoản nhìn thấy: mỗi bên giữ ngữ cảnh riêng."""
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    link, calls = _recording_link()
    bot = _Bot()
    msg = {"messageID": "m1", "userID": "7", "body": "giá 5 triệu", "chatJid": "7@msgr"}
    await link.forward("shop", bot, msg)  # shop nhận tin của khách 7
    owner_bot = _Bot()
    owner_bot.dataFB = {"FacebookID": "7"}
    await link.forward_owner(
        "khach", owner_bot, {**msg, "chatJid": "100@msgr"}
    )  # khách 7 thấy tin của chính mình
    await link.handle_meta(
        "shop",
        bot,
        {
            "type": "messageUnsend",
            "data": {"isE2EE": True, "messageId": "m1", "threadId": "7@msgr"},
        },
    )
    reply = {
        "messageID": "m2",
        "userID": "7",
        "body": "?",
        "chatJid": "7@msgr",
        "raw": {"replyTo": {"messageId": "m1"}},
    }
    await link.forward("shop", bot, reply)
    events = [c[1] for c in calls if c[0] == "/v1/event" and c[1]["account"] == "shop"]
    assert events[0]["kind"] == "recall" and events[0]["thread_id"] == "e2ee:7@msgr"
    assert events[0]["sender_name"] == "User 7"
    inbound = [c[1] for c in calls if c[0] == "/v1/inbound"]
    assert inbound[-1]["quote"] == "User 7: giá 5 triệu"


@pytest.mark.asyncio
async def test_unknown_name_falls_back_to_readable_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_name(dataFB: dict[str, Any], user_id: str, **_: Any) -> dict[str, Any]:
        return {"error": 1}

    monkeypatch.setattr(gateway_link._get_user_info, "func", no_name)
    link, calls = _recording_link()
    await link.forward(
        "shop",
        _Bot(),
        {"messageID": "m1", "userID": "42", "body": "hi", "chatJid": "42@msgr"},
    )
    assert (
        calls[0][1]["thread_name"] == "Facebook 42"
        and calls[0][1]["sender_name"] == "Facebook 42"
    )


@pytest.mark.asyncio
async def test_stranger_name_from_messenger_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 09/11/2026: người lạ nhắn `default`, /chat/user_info không trả hồ sơ nên
    # hội thoại mang tên "Facebook <id>", không ảnh. Bridge hỏi danh bạ Messenger.
    async def no_name(dataFB: dict[str, Any], user_id: str, **_: Any) -> dict[str, Any]:
        return {"error": 1}

    class _ContactBridge(_FakeBridge):
        async def call(
            self,
            method: str,
            params: dict[str, Any] | None = None,
            timeout: float = 60.0,
        ) -> dict[str, Any]:
            self.calls.append((method, params or {}))
            if (params or {}).get("userId") == 42:
                return {
                    "id": 42,
                    "name": " Người Lạ ",
                    "profilePictureUrl": "https://cdn/p.jpg",
                }
            raise RuntimeError("user not found")

    monkeypatch.setattr(gateway_link._get_user_info, "func", no_name)
    link, calls = _recording_link()
    bot = _Bot()
    bridge = _ContactBridge()
    bot.listener._bridge = bridge  # type: ignore[attr-defined]
    await link.forward(
        "shop",
        bot,
        {"messageID": "m1", "userID": "42", "body": "hi", "chatJid": "42@msgr"},
    )
    assert bridge.calls == [("getUserInfo", {"userId": 42})]
    inbound = calls[0][1]
    assert inbound["thread_name"] == "Người Lạ" and inbound["sender_name"] == "Người Lạ"
    assert inbound["thread_avatar"] == "https://cdn/p.jpg"

    # Danh bạ cũng không có: vẫn nhãn dễ đọc, không lỗi.
    await link.forward(
        "shop",
        bot,
        {"messageID": "m2", "userID": "43", "body": "hi", "chatJid": "43@msgr"},
    )
    assert calls[-1][1]["sender_name"] == "Facebook 43"


@pytest.mark.asyncio
async def test_unknown_e2ee_group_name_asked_from_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 09/11/2026: sau khi fb-bot khởi động lại, nhóm của `default` mất tên vì
    # bảng LightSpeed không nhắc lại nhóm đó; bot hỏi server qua bridge.
    async def fake_user_info(
        dataFB: dict[str, Any], user_id: str, **_: Any
    ) -> dict[str, Any]:
        return {"nameUser": "Đoàn Duy Nhất"}

    class _GroupBridge(_FakeBridge):
        def __init__(self) -> None:
            super().__init__()
            self.fail = True

        async def call(
            self,
            method: str,
            params: dict[str, Any] | None = None,
            timeout: float = 60.0,
        ) -> dict[str, Any]:
            self.calls.append((method, params or {}))
            if self.fail:
                raise RuntimeError("timeout")
            return {"name": "Nhóm VetGo", "participantCount": 4}

    monkeypatch.setattr(gateway_link._get_user_info, "func", fake_user_info)
    link, calls = _recording_link()
    bot = _Bot()
    bridge = _GroupBridge()
    bot.listener._bridge = bridge  # type: ignore[attr-defined]

    def message(n: int) -> dict[str, Any]:
        return {
            "messageID": f"m{n}",
            "userID": "7",
            "body": "hi",
            "chatJid": "3858@g.us",
        }

    # Lỗi: vẫn chuyển tin, không tên; không hỏi lại ngay ở tin sau.
    await link.forward("acc1", bot, message(1))
    await link.forward("acc1", bot, message(2))
    assert [c[1]["thread_name"] for c in calls] == ["", ""]
    assert bridge.calls == [("getE2EEGroupInfo", {"chatJid": "3858@g.us"})]

    # Hết giờ chờ: hỏi lại, lần này có tên và nhớ luôn.
    link._group_lookups.clear()
    bridge.fail = False
    await link.forward("acc1", bot, message(3))
    await link.forward("acc1", bot, message(4))
    assert [c[1]["thread_name"] for c in calls[2:]] == ["Nhóm VetGo", "Nhóm VetGo"]
    assert len(bridge.calls) == 2


@pytest.mark.asyncio
async def test_e2ee_group_name_and_picture_from_raw_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={})

    async def fake_user_info(
        dataFB: dict[str, Any], user_id: str, **_: Any
    ) -> dict[str, Any]:
        return {"nameUser": "Đoàn Duy Nhất", "thumbSrc": "https://cdn/u.jpg"}

    monkeypatch.setattr(gateway_link._get_user_info, "func", fake_user_info)
    link = _link(handler)
    message = {"messageID": "m1", "userID": "7", "body": "chào", "chatJid": "3858@g.us"}
    # Chưa biết tên nhóm: không lấy tên người gửi làm tên hội thoại.
    await link.forward("acc1", _Bot(), message)
    assert sent[0]["is_group"] is True and sent[0]["thread_name"] == ""
    assert sent[0]["sender_name"] == "Đoàn Duy Nhất"

    def raw(table: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "raw",
            "data": {"from": "lightspeed", "type": "LSTable", "data": table},
        }

    link.observe_raw(
        "acc1",
        raw(
            {
                "LSDeleteThenInsertThread": [
                    {
                        "ThreadKey": 3858,
                        "ThreadName": "Nhóm VetGo",
                        "ThreadPictureUrl": "https://cdn/g.jpg",
                    }
                ]
            }
        ),
    )
    link.observe_raw(
        "acc2",
        raw({"LSSyncUpdateThreadName": [{"ThreadKey": 3858, "ThreadName": "Khác"}]}),
    )
    link.observe_raw(
        "acc1", {"type": "raw", "data": {"type": "ReadyEvent", "data": None}}
    )
    await link.forward("acc1", _Bot(), {**message, "messageID": "m2"})
    assert sent[1]["thread_name"] == "Nhóm VetGo"
    assert sent[1]["thread_avatar"] == "https://cdn/g.jpg"
    assert sent[1]["sender_avatar"] == "https://cdn/u.jpg"

    # Đổi tên nhóm và ảnh nhóm sau đó.
    link.observe_raw(
        "acc1",
        raw(
            {"LSSyncUpdateThreadName": [{"ThreadKey": 3858, "ThreadName": "VetGo mới"}]}
        ),
    )
    link.observe_raw(
        "acc1",
        raw(
            {
                "LSSetThreadImageURL": [
                    {"ThreadKey": 3858, "ImageURL": "https://cdn/g2.jpg"}
                ]
            }
        ),
    )
    assert link.group_info("acc1", "e2ee:3858@g.us") == {
        "name": "VetGo mới",
        "picture": "https://cdn/g2.jpg",
    }
    assert link.group_info("acc2", "e2ee:3858@g.us") == {"name": "Khác"}


@pytest.mark.asyncio
async def test_unsupported_e2ee_content_becomes_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_name(dataFB: dict[str, Any], user_id: str, **_: Any) -> dict[str, Any]:
        return {"error": 1}

    monkeypatch.setattr(gateway_link._get_user_info, "func", no_name)
    link, calls = _recording_link()
    empty = {"userID": "42", "body": None, "attachments": [], "chatJid": "42@msgr"}
    await link.forward("shop", _Bot(), {**empty, "messageID": "m1", "type": "e2ee"})
    # Tin thường rỗng (sự kiện hệ thống) vẫn bỏ qua.
    await link.forward("shop", _Bot(), {**empty, "messageID": "m2", "type": "thread"})
    assert [c[1]["text"] for c in calls] == [gateway_link.UNSUPPORTED_E2EE_TEXT]


def _ls(table: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "raw",
        "data": {"from": "lightspeed", "type": "LSTable", "data": table},
    }


@pytest.mark.asyncio
async def test_group_changes_only_from_known_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    link, calls = _recording_link()
    member = "LSAddParticipantIdToGroupThread"
    # Đồng bộ lúc kết nối: ảnh chụp hội thoại + cả danh sách thành viên.
    sync = {
        "LSDeleteThenInsertThread": [{"ThreadKey": 38, "ThreadName": "Nhóm A"}],
        member: [{"ThreadKey": 38, "ContactId": c} for c in (1, 2, 3, 4)],
    }
    assert link.observe_raw("acc", _ls(sync)) == []
    assert link.observe_raw("acc", _ls(sync)) == []
    # Cùng tên khi đồng bộ lại: không phải đổi tên.
    same = {"LSSyncUpdateThreadName": [{"ThreadKey": 38, "ThreadName": "Nhóm A"}]}
    assert link.observe_raw("acc", _ls(same)) == []
    changes = link.observe_raw(
        "acc",
        _ls(
            {
                "LSSyncUpdateThreadName": [{"ThreadKey": 38, "ThreadName": "Nhóm B"}],
                member: [{"ThreadKey": 38, "ContactId": 9}],
                "LSUpdateThreadParticipantAdminStatus": [
                    {"ThreadKey": 38, "ContactId": 2, "IsAdmin": True},
                    {"ThreadKey": 38, "ContactId": 77, "IsAdmin": True},
                ],
                "LSRemoveParticipantFromThread": [
                    {"ThreadKey": 38, "ParticipantId": 3}
                ],
            }
        ),
    )
    assert changes == [
        ("38", "rename", "Nhóm B"),
        ("38", "add", "9"),
        ("38", "admin", "2"),
        ("38", "remove", "3"),
    ]
    # Nhóm chưa từng thấy: thành viên đầu tiên chỉ được ghi nhận.
    assert (
        link.observe_raw("acc", _ls({member: [{"ThreadKey": 50, "ContactId": 1}]}))
        == []
    )

    await link.post_group_changes("acc", _Bot(), changes[:2])
    texts = [(c[1]["thread_id"], c[1]["text"]) for c in calls]
    assert texts == [
        ("e2ee:38@g.us", "Nhóm đổi tên thành «Nhóm B»"),
        ("thread:38", "Nhóm đổi tên thành «Nhóm B»"),
        ("e2ee:38@g.us", "User 9 đã vào nhóm"),
        ("thread:38", "User 9 đã vào nhóm"),
    ]
    assert all(c[1]["kind"] == "group_event" and c[1]["is_group"] for c in calls)


def _wm(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": "raw", "data": {"from": "whatsmeow", "type": kind, "data": payload}}


@pytest.mark.asyncio
async def test_undecryptable_message_becomes_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    info = {"Chat": "385@g.us", "Sender": "42.0:3@msgr", "ID": "abc", "IsFromMe": False}
    message = gateway_link.undecryptable_message(
        _wm("UndecryptableMessage", {"Info": info})
    )
    assert message is not None and message["messageID"] == "undecryptable-abc"
    assert message["userID"] == "42"
    link, calls = _recording_link()
    await link.forward("acc", _Bot(), message)
    body = calls[0][1]
    assert body["thread_id"] == "e2ee:385@g.us" and body["is_group"] is True
    assert body["text"] == gateway_link.UNDECRYPTABLE_TEXT
    assert body["sender_name"] == "User 42"
    for skipped in (
        _wm("UndecryptableMessage", {"Info": {**info, "IsFromMe": True}}),
        _wm("UndecryptableMessage", {"Info": info, "DecryptFailMode": "hide"}),
        _wm("Receipt", {"Info": info}),
    ):
        assert gateway_link.undecryptable_message(skipped) is None


@pytest.mark.asyncio
async def test_quoted_reply_uses_original_message_and_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    link = _link(lambda r: httpx.Response(200))
    bot = _Bot()
    link.bots["acc1"] = bot  # type: ignore[assignment]
    customer = {
        "messageID": "mid.c1",
        "userID": "42",
        "body": "giá?",
        "chatJid": "42@msgr",
        "senderJid": "42.0:3@msgr",
        "type": "e2ee",
    }
    await link.forward("acc1", bot, customer)  # type: ignore[arg-type]
    reply = {"account": "acc1", "thread_id": "e2ee:42@msgr", "text": "Dạ 5 triệu"}
    await link.send_reply({**reply, "message_id": "r1", "reply_to": "mid.c1"})
    # Tin gốc không còn trong bộ nhớ: gửi thường, không trích dẫn.
    await link.send_reply({**reply, "message_id": "r2", "reply_to": "mid.gone"})
    assert bot.listener.reply_args == [("mid.c1", "42.0:3@msgr"), ()]


@pytest.mark.asyncio
async def test_send_returns_ids_and_recall_unsends_without_duplicate_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200)

    unsent: list[tuple[str, ...]] = []

    class _Actions:
        def __init__(self, bridge: Any) -> None:
            pass

        async def unsend_e2ee_message(
            self, chat_jid: str, message_id: str
        ) -> dict[str, Any]:
            unsent.append(("e2ee", chat_jid, message_id))
            return {}

        async def unsend_message(self, message_id: str) -> dict[str, Any]:
            unsent.append(("thread", message_id))
            return {}

        async def edit_e2ee_message(
            self, chat_jid: str, message_id: str, text: str
        ) -> dict[str, Any]:
            unsent.append(("edit", chat_jid, message_id, text))
            return {}

    monkeypatch.setattr(gateway_link, "BridgeActions", _Actions)
    link = _link(handler)
    bot = _Bot()
    bot.listener._bridge = _FakeBridge()  # type: ignore[attr-defined]
    link.bots["acc1"] = bot  # type: ignore[assignment]
    status, body = await link.send_reply(
        {"account": "acc1", "thread_id": "e2ee:8@msgr", "text": "a", "message_id": "r1"}
    )
    assert status == 200 and json.loads(body)["message_ids"] == ["mid.out"]
    status, _ = await link.recall(
        {"account": "acc1", "thread_id": "e2ee:8@msgr", "message_ids": ["mid.out"]}
    )
    assert status == 200 and unsent == [("e2ee", "8@msgr", "mid.out")]
    # Messenger báo lại sự kiện thu hồi của chính tin đó: không ghi chú lặp.
    await link.handle_meta(
        "acc1",
        bot,  # type: ignore[arg-type]
        {
            "type": "messageUnsend",
            "data": {"messageId": "mid.out", "threadId": "8@msgr", "isE2EE": True},
        },
    )
    assert not [c for c in calls if c[0] == "/v1/event"]
    # Tài khoản kia (khách, cùng tiến trình) vẫn ghi chú tin bị thu hồi.
    await link.handle_meta(
        "acc2",
        bot,  # type: ignore[arg-type]
        {
            "type": "messageUnsend",
            "data": {"messageId": "mid.out", "threadId": "9@msgr", "isE2EE": True},
        },
    )
    assert [c[1]["kind"] for c in calls if c[0] == "/v1/event"] == ["recall"]
    assert (
        await link.recall(
            {"account": "nope", "thread_id": "e2ee:8@msgr", "message_ids": ["x"]}
        )
    )[0] == 404


def test_contact_names_from_lightspeed_tables() -> None:
    link, _ = _recording_link()
    link.observe_raw(
        "acc",
        _ls(
            {
                "LSDeleteThenInsertContact": [
                    {
                        "Id": 615,
                        "Name": "Shop Hai",
                        "ProfilePictureUrl": "https://cdn/s.jpg",
                    }
                ],
                "LSVerifyContactRowExists": [{"ContactId": 42, "Name": " An "}],
            }
        ),
    )
    assert link.cached_profile("615") == ("Shop Hai", "https://cdn/s.jpg")
    assert link.cached_profile("42") == ("An", "")
    assert link.cached_profile("7") == ("", "")


@pytest.mark.asyncio
async def test_edit_agent_reply_without_duplicate_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    edits: list[tuple[str, ...]] = []

    class _Actions:
        def __init__(self, bridge: Any) -> None:
            pass

        async def edit_e2ee_message(
            self, chat_jid: str, message_id: str, text: str
        ) -> dict[str, Any]:
            edits.append((chat_jid, message_id, text))
            return {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200)

    monkeypatch.setattr(gateway_link, "BridgeActions", _Actions)
    link = _link(handler)
    bot = _Bot()
    bot.listener._bridge = _FakeBridge()  # type: ignore[attr-defined]
    link.bots["acc1"] = bot  # type: ignore[assignment]
    await link.send_reply(
        {
            "account": "acc1",
            "thread_id": "e2ee:8@msgr",
            "text": "giá 5tr",
            "message_id": "r1",
        }
    )
    edit = {
        "account": "acc1",
        "thread_id": "e2ee:8@msgr",
        "message_id": "mid.out",
        "text": "giá 4tr",
    }
    assert (await link.edit(edit))[0] == 200
    assert edits == [("8@msgr", "mid.out", "giá 4tr")]
    # Messenger báo lại sự kiện sửa của chính tin đó: không ghi chú lặp.
    await link.handle_meta(
        "acc1",
        bot,  # type: ignore[arg-type]
        {
            "type": "messageEdit",
            "data": {"messageId": "mid.out", "newText": "giá 4tr", "threadId": 0},
        },
    )
    assert not [c for c in calls if c[0] == "/v1/event"]
    assert (await link.edit({**edit, "text": " "}))[0] == 400


def test_presence_of_facebook_events() -> None:
    own = "100"
    p = gateway_link.presence_of
    assert p(
        {
            "type": "e2eeReceipt",
            "data": {
                "type": "read",
                "chat": "42@msgr",
                "sender": "42.0:1@msgr",
                "messageIds": ["m1"],
            },
        },
        own,
    ) == ("e2ee:42@msgr", "read", ["m1"])
    assert (
        p(
            {
                "type": "e2eeReceipt",
                "data": {"type": "delivered", "chat": "42@msgr", "sender": "42@msgr"},
            },
            own,
        )
        is None
    )
    assert (
        p(
            {
                "type": "e2eeReceipt",
                "data": {"type": "read", "chat": "42@msgr", "sender": "100.0:2@msgr"},
            },
            own,
        )
        is None
    )
    assert p({"type": "readReceipt", "data": {"threadId": 9, "readerId": 42}}, own) == (
        "thread:9",
        "read",
        [],
    )
    assert (
        p({"type": "readReceipt", "data": {"threadId": 9, "readerId": 100}}, own)
        is None
    )
    assert p(
        {"type": "typing", "data": {"threadId": 9, "senderId": 42, "isTyping": False}},
        own,
    ) == ("thread:9", "stopped", [])
    raw = {
        "type": "raw",
        "data": {
            "from": "whatsmeow",
            "type": "ChatPresence",
            "data": {
                "Chat": "385@g.us",
                "Sender": "42.0:3@msgr",
                "IsFromMe": False,
                "State": "composing",
            },
        },
    }
    assert p(raw, own) == ("e2ee:385@g.us", "typing", [])


@pytest.mark.asyncio
async def test_post_presence_throttles_typing() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(204)

    link = _link(handler)
    bot = _Bot()
    link.bots["acc1"] = bot  # type: ignore[assignment]
    typing = {
        "type": "typing",
        "data": {"threadId": 9, "senderId": 42, "isTyping": True},
    }
    await link.post_presence("acc1", typing)
    await link.post_presence("acc1", typing)  # trong 3 giây: bỏ
    await link.post_presence(
        "acc1", {"type": "readReceipt", "data": {"threadId": 9, "readerId": 42}}
    )
    assert [(c["kind"], c["thread_id"]) for c in calls] == [
        ("typing", "thread:9"),
        ("read", "thread:9"),
    ]


def test_facebook_user_id_from_id_or_profile_link() -> None:
    f = gateway_link.facebook_user_id
    assert f("61568459183039") == "61568459183039"
    assert (
        f("https://www.facebook.com/profile.php?id=100024107767037&sk=about")
        == "100024107767037"
    )
    assert f("facebook.com/100024107767037/") == "100024107767037"
    assert f("https://facebook.com/some.name") == ""
    assert f("123") == ""


@pytest.mark.asyncio
async def test_resolve_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    link = _link(lambda r: httpx.Response(200))
    link.bots["acc1"] = _Bot()  # type: ignore[assignment]
    status, body = await link.resolve(
        {"account": "acc1", "to": "profile.php?id=4242424"}
    )
    assert status == 200 and json.loads(body) == {
        "thread_id": "e2ee:4242424@msgr",
        "name": "User 4242424",
        "avatar": "",
    }
    assert (await link.resolve({"account": "acc1", "to": "some.name"}))[0] == 400


@pytest.mark.asyncio
async def test_reaction_removal_and_owner_reaction_carry_badge_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    link, calls = _recording_link()
    bot = _Bot()
    own = str(bot.dataFB["FacebookID"])
    for data in (
        {"chatJid": "7@msgr", "messageId": "m2", "reaction": "", "senderId": 7},
        {"chatJid": "7@msgr", "messageId": "m2", "reaction": "😆", "senderId": own},
    ):
        await link.handle_meta("acc1", bot, {"type": "e2eeReaction", "data": data})
    events = [c[1] for c in calls if c[0] == "/v1/event"]
    assert [(e["reaction"], e["reactor_id"]) for e in events] == [
        ("", "7"),
        ("😆", "self"),
    ]
    assert events[0]["text"].startswith("(bỏ cảm xúc)")


@pytest.mark.asyncio
async def test_agent_reaction_goes_through_the_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    link, _ = _recording_link()
    bot = _Bot()
    link.bots["acc1"] = bot
    await link.forward(
        "acc1",
        bot,
        {
            "messageID": "m1",
            "userID": "7",
            "body": "hi",
            "chatJid": "7@msgr",
            "senderJid": "7.0@msgr",
        },
    )
    bridge = bot.listener._bridge
    ok = await link.react(
        {
            "account": "acc1",
            "thread_id": "e2ee:7@msgr",
            "message_id": "m1",
            "emoji": "❤️",
        }
    )
    gone = await link.react(
        {"account": "acc1", "thread_id": "thread:55", "message_id": "m9", "emoji": ""}
    )
    assert ok[0] == 200 and gone[0] == 200
    assert bridge.calls[-2] == (
        "sendE2EEReaction",
        {"chatJid": "7@msgr", "messageId": "m1", "senderJid": "7.0@msgr", "emoji": "❤"},
    )
    assert bridge.calls[-1] == (
        "sendReaction",
        {"threadId": 55, "messageId": "m9", "emoji": ""},
    )
    bad = await link.react(
        {"account": "acc1", "thread_id": "x", "message_id": "m1", "emoji": "❤"}
    )
    assert bad[0] == 400
    assert (
        await link.react(
            {
                "account": "nope",
                "thread_id": "e2ee:7@msgr",
                "message_id": "m1",
                "emoji": "❤",
            }
        )
    )[0] == 404


def _box(kind: bytes, body: bytes) -> bytes:
    return (8 + len(body)).to_bytes(4, "big") + kind + body


def test_audio_seconds_reads_mp4_and_ogg() -> None:
    mvhd0 = _box(
        b"mvhd",
        bytes(4) + bytes(8) + (1000).to_bytes(4, "big") + (2500).to_bytes(4, "big"),
    )
    mp4 = _box(b"ftyp", b"M4A " + bytes(4)) + _box(b"moov", mvhd0)
    assert audio_seconds(mp4, "audio/mp4") == 3  # 2,5 giây làm tròn lên
    mvhd1 = _box(
        b"mvhd",
        b"\x01"
        + bytes(3)
        + bytes(16)
        + (600).to_bytes(4, "big")
        + (6000).to_bytes(8, "big"),
    )
    assert audio_seconds(_box(b"moov", mvhd1), "audio/mp4") == 10
    page = b"OggS" + bytes(2) + (48000 * 4).to_bytes(8, "little") + bytes(10)
    assert audio_seconds(b"OggS" + bytes(30) + page, "audio/ogg; codecs=opus") == 4
    assert audio_seconds("rác".encode(), "audio/mp4") == 0
    assert audio_seconds(b"", "audio/ogg") == 0
    b64 = base64.b64encode(mp4).decode()
    method, params = media_rpc(
        "e2ee", "8@msgr", {"name": "a.m4a", "content_type": "audio/mp4", "data": b64}
    )
    assert (
        method == "sendE2EEAudio" and params["ptt"] is True and params["duration"] == 3
    )


@pytest.mark.asyncio
async def test_e2ee_reaction_without_sender_timestamp_is_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway_link._get_user_info, "func", _names)
    link, calls = _recording_link()
    bot = _Bot()
    base = {"chatJid": "7@msgr", "messageId": "m3", "reaction": "❤", "senderId": 7}
    for extra in ({"senderTimestampMs": 1793600000123}, {"senderTimestampMs": 0}, {}):
        await link.handle_meta(
            "acc1", bot, {"type": "e2eeReaction", "data": {**base, **extra}}
        )
    texts = [c[1]["text"] for c in calls if c[0] == "/v1/event"]
    assert [gateway_link.MISSING_REACTION_TS in t for t in texts] == [
        False,
        True,
        False,
    ]


def test_forget_account_drops_only_that_accounts_memory() -> None:
    link = _link(lambda request: httpx.Response(204))
    for account in ("acc2", "shop1"):
        link._recent[f"{account}:m1"] = {"summary": f"tin của {account}"}
        link._threads[f"{account}:t1"] = {"name": "Nhóm"}
        link._members[f"{account}:t1"] = {"u": False}
        link._recalled[f"{account}:m1"] = None
        link._edited[f"{account}:m1"] = None
        link._last_typing[f"{account}:t1"] = 1.0
        link._group_lookups[f"{account}:t1"] = 1.0
        link._pending.append({"account": account, "thread_id": "t1"})
    link.bots["acc2"] = object()  # type: ignore[assignment]

    link.forget_account("acc2")

    for cache in (
        link._recent,
        link._threads,
        link._members,
        link._recalled,
        link._edited,
        link._last_typing,
        link._group_lookups,
    ):
        assert not any(k.startswith("acc2:") for k in cache)
        assert any(k.startswith("shop1:") for k in cache)
    assert [p["account"] for p in link._pending] == ["shop1"]
    assert "acc2" not in link.bots
