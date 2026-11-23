"""Nối bot Facebook với omnichannel gateway (Libredesk).

- Tin khách gửi tới: ``POST {GATEWAY_URL}/v1/inbound``.
- Tin nhân viên trả lời: gateway gọi ``POST /send`` trên server HTTP nội bộ này.

``thread_id`` gửi cho gateway mang tiền tố để biết đường trả lời:
``e2ee:<chatJid>`` (chat mã hóa) hoặc ``thread:<threadId>`` (chat thường).
File đính kèm đi kèm dạng base64 ở cả hai chiều; bot tải/gửi file qua RPC của
bridge (``downloadE2EEMedia``/``downloadMedia``, ``sendE2EE*``/``sendImage``/
``sendFile``). Chỉ bật khi có ``GATEWAY_URL``; token qua ``GATEWAY_TOKEN``.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hmac
import json
import os
import re
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx
from _messaging._bridge_actions import BridgeActions

from _features._facebook import _get_user_info

CHANNEL = "facebook"
# Messenger ThreadType (mautrix-meta table.ThreadType) của chat 1-1.
ONE_TO_ONE_THREAD_TYPES = frozenset({1, 7, 10, 13, 14, 15})
MAX_REQUEST_BYTES = 96 << 20  # base64 của vài file 20 MiB
MAX_FILE_BYTES = int(os.environ.get("GATEWAY_MAX_FILE_MB", "20")) << 20
RECENT_MAX = 4096
NAME_RETRY_SECONDS = 3600.0
MEDIA_RPC_TIMEOUT = 180.0
# Loại attachment của bridge có nội dung tải được; sticker/location/link chỉ mô tả.
DOWNLOADABLE_TYPES = frozenset(
    {"image", "video", "audio", "voice", "file", "gif", "sticker"}
)
# Event phụ (SimpleBot upstream lọc bỏ) cần thành ghi chú nội bộ.
META_EVENT_TYPES = frozenset(
    {"e2eeReaction", "reaction", "messageEdit", "messageUnsend"}
)
ECHO_WINDOW_SECONDS = 60.0
# Bridge gửi tin E2EE không có chữ/file cho loại nó chưa đọc được (danh thiếp,
# bình chọn, xem một lần, vị trí trực tiếp...): báo thay vì bỏ qua im lặng.
UNSUPPORTED_E2EE_TEXT = "❓ Loại tin chưa hỗ trợ: xem trên Messenger"
# Bridge chỉ phát lỗi chung cho tin E2EE không giải mã được; sự kiện raw của
# whatsmeow (UndecryptableMessage) vẫn có chat, người gửi và ID tin.
UNDECRYPTABLE_TEXT = (
    "⚠️ Tin nhắn mã hóa không giải mã được: xem trên Messenger"
    " (tin có thể tự đến sau khi giải mã lại)"
)
OWNER = "Chủ tài khoản"
# Nhãn cho file không tải được (lỗi, quá lớn, sticker không tra được URL) và
# cho dòng tóm tắt tin (cảm xúc, trích dẫn), thay cho "[image] URL".
MEDIA_LABELS = {
    "image": "🖼️ Ảnh",
    "gif": "🖼️ GIF",
    "video": "🎬 Video",
    "audio": "🎵 Âm thanh",
    "voice": "🎤 Tin thoại",
    "file": "📎 Tệp",
    "sticker": "🧩 Sticker",
}
# mediaType cho downloadE2EEMedia (bridge nhận image/video/audio/voice/file/sticker).
E2EE_MEDIA_TYPE = {"gif": "video"}
# Dấu trong ghi chú cảm xúc thiếu thời điểm thả (canary tìm đúng chuỗi này).
MISSING_REACTION_TS = "⚠️ thiếu thời điểm thả, app Messenger không hiện"
EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/ogg": "ogg",
    # Tin thoại Messenger (opus) và audio nhân viên gửi (aac) từng thành "audio.bin".
    "audio/opus": "opus",
    "audio/aac": "aac",
    "audio/wav": "wav",
    "audio/webm": "webm",
    "video/quicktime": "mov",
    "video/webm": "webm",
    "application/pdf": "pdf",
}
# Chữ ký đầu tệp cho file thiếu MIME (sticker Messenger tải qua URL CDN không kèm
# mimeType): đoán đúng loại để Libredesk hiện ảnh thay vì "sticker.bin".
MAGIC_MIME = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
)
GENERIC_MIMES = frozenset({"", "application/octet-stream", "binary/octet-stream"})
MEDIA_FAMILIES = frozenset({"image", "video", "audio"})


class _Bridge(Protocol):
    async def call(
        self, method: str, params: dict[str, Any] | None = None, timeout: float = 60.0
    ) -> dict[str, Any]: ...


class _Listener(Protocol):
    async def send_e2ee_message(
        self,
        chat_jid: str,
        text: str,
        reply_to_id: str = "",
        reply_to_sender_jid: str = "",
    ) -> dict[str, Any]: ...

    async def send_message(
        self, thread_id: int, text: str, reply_to_id: str = ""
    ) -> dict[str, Any]: ...


class _Bot(Protocol):
    @property
    def dataFB(self) -> dict[str, Any]: ...

    @property
    def listener(self) -> _Listener: ...


def _raw(message: dict[str, Any]) -> dict[str, Any]:
    raw = message.get("raw")
    return raw if isinstance(raw, dict) else {}


def _rows(table: dict[str, Any], name: str) -> list[dict[str, Any]]:
    rows = table.get(name)
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _jid_user(jid: Any) -> str:
    """ "100012.0:3@msgr" -> "100012" (phần user, bỏ agent/thiết bị)."""
    if not isinstance(jid, str):
        return ""
    return jid.split("@", 1)[0].split(":", 1)[0].split(".", 1)[0]


def undecryptable_message(event: dict[str, Any]) -> dict[str, Any] | None:
    """Tin giả cho ``forward`` từ raw UndecryptableMessage; None nếu không cần báo."""
    data = event.get("data")
    if not isinstance(data, dict) or data.get("type") != "UndecryptableMessage":
        return None
    payload = data.get("data")
    info = payload.get("Info") if isinstance(payload, dict) else None
    if not isinstance(info, dict) or info.get("IsFromMe"):
        return None
    # "hide": loại tin client cũng không hiện (reaction, sửa tin... hỏng).
    if payload.get("DecryptFailMode") == "hide":
        return None
    chat, message_id = info.get("Chat"), info.get("ID")
    if not isinstance(chat, str) or "@" not in chat or not message_id:
        return None
    return {
        # ID riêng: nếu sau đó giải mã lại được, tin thật không bị coi là trùng.
        "messageID": f"undecryptable-{message_id}",
        "userID": _jid_user(info.get("Sender")),
        "body": UNDECRYPTABLE_TEXT,
        "chatJid": chat,
        "type": "e2ee",
        "attachments": [],
    }


PRESENCE_EVENT_TYPES = frozenset({"typing", "e2eeReceipt", "readReceipt"})
TYPING_THROTTLE_SECONDS = 3.0


def presence_of(
    event: dict[str, Any], own_id: str
) -> tuple[str, str, list[str]] | None:
    """(thread_id, typing|stopped|read, message_ids) cho "đã xem"/"đang soạn tin"
    của khách; None nếu không phải hoặc do chính tài khoản."""
    kind = event.get("type")
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    if kind == "e2eeReceipt":
        chat = str(data.get("chat") or "")
        if data.get("type") != "read" or "@" not in chat:
            return None
        if _jid_user(data.get("sender")) == own_id:
            return None
        ids = [str(i) for i in (data.get("messageIds") or []) if i]
        return f"e2ee:{chat}", "read", ids
    if kind == "readReceipt":
        if not data.get("threadId") or str(data.get("readerId") or "") == own_id:
            return None
        return f"thread:{data['threadId']}", "read", []
    if kind == "typing":
        if not data.get("threadId") or str(data.get("senderId") or "") == own_id:
            return None
        state = "typing" if data.get("isTyping") else "stopped"
        return f"thread:{data['threadId']}", state, []
    if kind == "raw" and data.get("type") == "ChatPresence":
        info = data.get("data")
        if not isinstance(info, dict) or info.get("IsFromMe"):
            return None
        chat = str(info.get("Chat") or "")
        if "@" not in chat or _jid_user(info.get("Sender")) == own_id:
            return None
        state = "typing" if info.get("State") == "composing" else "stopped"
        return f"e2ee:{chat}", state, []
    return None


def facebook_user_id(raw: Any) -> str:
    """ID số Facebook từ ID hoặc link hồ sơ (profile.php?id=..., facebook.com/123...)."""
    text = str(raw or "").strip()
    if text.isdigit() and len(text) >= 5:
        return text
    match = re.search(r"[?&]id=(\d{5,})", text) or re.search(
        r"facebook\.com/(\d{5,})(?:[/?#]|$)", text
    )
    return match.group(1) if match else ""


def thread_ref(message: dict[str, Any]) -> tuple[str, bool] | None:
    """Trả về (thread_id cho gateway, is_group) hoặc None nếu thiếu thông tin."""
    chat_jid = message.get("chatJid")
    if chat_jid:
        # Nhóm E2EE có JID dạng <id>@g.us; chat 1-1 là <id>@msgr.
        return f"e2ee:{chat_jid}", str(chat_jid).endswith("@g.us")
    raw = _raw(message)
    thread_id = raw.get("threadId") or message.get("replyToID")
    if not thread_id:
        return None
    thread_type = raw.get("threadType") or 0
    is_group = bool(thread_type) and thread_type not in ONE_TO_ONE_THREAD_TYPES
    return f"thread:{thread_id}", is_group


def describe_attachment(attachment: dict[str, Any], *, with_url: bool = True) -> str:
    """Chữ hiển thị cho attachment không tải được hoặc không có file (vị trí, link)."""
    kind = attachment.get("type") or "attachment"
    lat, lng = attachment.get("latitude"), attachment.get("longitude")
    if kind == "location" and lat is not None and lng is not None:
        label = attachment.get("description") or attachment.get("fileName") or ""
        return "\n".join(
            p
            for p in (
                f"📍 Vị trí{': ' + label if label else ''}",
                f"https://maps.google.com/?q={lat},{lng}",
            )
            if p
        )
    if kind == "link":
        lines = [
            f"🔗 {attachment.get('description') or attachment.get('url') or 'Liên kết'}"
        ]
        lines += [
            str(v) for v in (attachment.get("url"), attachment.get("sourceText")) if v
        ]
        return "\n".join(lines)
    label = MEDIA_LABELS.get(kind)
    if label is None:
        detail = attachment.get("fileName") or attachment.get("url") or ""
        return f"[{kind}] {detail}".strip()
    name = attachment.get("fileName")
    if name and kind != "sticker":
        label = f"{label}: {name}"
    # Chat thường có URL CDN: nhân viên vẫn mở được khi bot không tải về.
    url = attachment.get("url") if with_url and kind != "sticker" else None
    return f"{label}\n{url}" if url else label


def describe_message(message: dict[str, Any], *, with_url: bool = True) -> str:
    """Nội dung chữ, kèm mô tả ngắn cho file đính kèm."""
    parts = []
    body = message.get("body")
    if isinstance(body, str) and body.strip():
        parts.append(body)
    for attachment in message.get("attachments") or []:
        if isinstance(attachment, dict):
            parts.append(describe_attachment(attachment, with_url=with_url))
    return "\n".join(parts)


def _bridge_of(bot: Any) -> _Bridge | None:
    # SimpleBot upstream cũng dùng listener._bridge cho BridgeActions.
    return getattr(bot.listener, "_bridge", None)


def sniff_mime(raw: bytes) -> str:
    """MIME theo chữ ký đầu tệp; "" nếu không nhận ra."""
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    for magic, mime in MAGIC_MIME:
        if raw.startswith(magic):
            return mime
    return ""


def file_name(name: Any, mime: str, fallback: str) -> str:
    clean = str(name or "").replace("/", "_").replace("\\", "_").strip()[:120]
    if "." in clean:
        return clean
    base = mime.split(";")[0].strip().lower()
    family = base.split("/")[0]
    # GIF Messenger tới với type "video" nhưng là ảnh webp: đặt tên theo loại thật.
    if not clean and family in MEDIA_FAMILIES and fallback in MEDIA_FAMILIES | {"gif"}:
        fallback = family
    return f"{clean or fallback}.{EXT_BY_MIME.get(base, 'bin')}"


async def fetch_attachment(
    bridge: _Bridge, attachment: dict[str, Any]
) -> dict[str, str] | None:
    """Tải nội dung một attachment qua bridge; None nếu loại này không tải được."""
    kind = str(attachment.get("type") or "")
    if kind not in DOWNLOADABLE_TYPES:
        return None
    if int(attachment.get("fileSize") or 0) > MAX_FILE_BYTES:
        raise ValueError("file quá lớn")
    mime = str(attachment.get("mimeType") or "application/octet-stream")
    if attachment.get("directPath") and attachment.get("mediaKey"):
        result = await bridge.call(
            "downloadE2EEMedia",
            {
                "directPath": attachment["directPath"],
                "mediaKey": attachment["mediaKey"],
                "mediaSha256": attachment.get("mediaSha256") or "",
                "mediaEncSha256": attachment.get("mediaEncSha256") or "",
                "mediaType": E2EE_MEDIA_TYPE.get(kind, kind),
                "mimeType": mime,
                "fileSize": int(attachment.get("fileSize") or 0),
            },
            MEDIA_RPC_TIMEOUT,
        )
        mime = str(result.get("mimeType") or mime)
    elif attachment.get("url"):
        result = await bridge.call(
            "downloadMedia", {"url": attachment["url"]}, MEDIA_RPC_TIMEOUT
        )
    else:
        return None
    data = str(result.get("data") or "")
    raw = base64.b64decode(data, validate=True)
    if len(raw) == 0 or len(raw) > MAX_FILE_BYTES:
        raise ValueError("file rỗng hoặc quá lớn")
    if mime.split(";")[0].strip().lower() in GENERIC_MIMES:
        mime = sniff_mime(raw) or mime
    return {
        "name": file_name(attachment.get("fileName"), mime, kind),
        "content_type": mime,
        "data": data,
    }


def audio_seconds(raw: bytes, mime: str) -> int:
    """Thời lượng (giây, làm tròn lên) của audio m4a/mp4 hoặc ogg opus; 0 nếu
    không đọc được. Messenger hiện thời lượng của tin thoại từ số này."""
    try:
        if "ogg" in mime:
            last = raw.rfind(b"OggS")
            if last < 0 or len(raw) < last + 14:
                return 0
            granule = int.from_bytes(raw[last + 6 : last + 14], "little")
            return max(1, -(-granule // 48000)) if granule > 0 else 0  # opus: 48 kHz
        return _mp4_seconds(raw, 0, len(raw))
    except (ValueError, IndexError):
        return 0


def _mp4_seconds(raw: bytes, start: int, end: int) -> int:
    pos = start
    while pos + 8 <= end:
        size = int.from_bytes(raw[pos : pos + 4], "big")
        box = raw[pos + 4 : pos + 8]
        header = 8
        if size == 1:
            size, header = int.from_bytes(raw[pos + 8 : pos + 16], "big"), 16
        elif size == 0:
            size = end - pos
        if size < header:
            return 0
        if box == b"moov":
            return _mp4_seconds(raw, pos + header, pos + size)
        if box == b"mvhd":
            body = pos + header
            if raw[body] == 1:
                scale = int.from_bytes(raw[body + 20 : body + 24], "big")
                duration = int.from_bytes(raw[body + 24 : body + 32], "big")
            else:
                scale = int.from_bytes(raw[body + 12 : body + 16], "big")
                duration = int.from_bytes(raw[body + 16 : body + 20], "big")
            return max(1, -(-duration // scale)) if scale and duration else 0
        pos += size
    return 0


def media_rpc(
    kind: str, target: str, file: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Chọn RPC gửi file theo loại chat và MIME type; data giữ nguyên base64."""
    mime = str(file.get("content_type") or "application/octet-stream")
    name = file_name(file.get("name"), mime, "file")
    data = str(file.get("data") or "")
    if kind == "e2ee":
        common = {"chatJid": target, "data": data, "mimeType": mime}
        reply = {"replyToId": "", "replyToSenderJid": ""}
        if mime.startswith("image/"):
            return "sendE2EEImage", {
                **common,
                "caption": "",
                "width": 0,
                "height": 0,
                **reply,
            }
        if mime.startswith("video/"):
            return "sendE2EEVideo", {
                **common,
                "caption": "",
                "width": 0,
                "height": 0,
                "duration": 0,
                **reply,
            }
        if mime.startswith("audio/"):
            # ptt: gửi thành tin thoại (bấm nghe trong chat), không phải tệp audio.
            seconds = audio_seconds(base64.b64decode(data or b""), mime)
            return "sendE2EEAudio", {
                **common,
                "duration": seconds,
                "ptt": True,
                **reply,
            }
        return "sendE2EEDocument", {**common, "filename": name, **reply}
    thread = {
        "threadId": int(target),
        "data": data,
        "filename": name,
        "caption": "",
        "replyToId": "",
    }
    if mime.startswith("image/"):
        return "sendImage", thread
    return "sendFile", {**thread, "mimeType": mime}


def summarize(message: dict[str, Any]) -> str:
    text = " ".join(describe_message(message, with_url=False).split())
    return text if len(text) <= 200 else text[:199] + "…"


class GatewayLink:
    def __init__(
        self,
        url: str,
        token: str,
        http_client: httpx.AsyncClient,
        log: Callable[[str, str], None],
    ) -> None:
        self.url = url.rstrip("/")
        self.token = token
        self.http = http_client
        self.log = log
        self.bots: dict[str, _Bot] = {}
        # user id -> (tên, ảnh đại diện, lúc tra)
        self._names: dict[str, tuple[str, str, float]] = {}
        self._recent_replies: OrderedDict[str, None] = OrderedDict()
        # messageId -> {summary, sender, thread_id, is_group}: cho trích dẫn E2EE
        # (chỉ có messageId), sửa tin (threadId=0), thu hồi và reaction.
        self._recent: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._bot_sent: OrderedDict[str, None] = OrderedDict()
        self._pending: list[dict[str, Any]] = []
        # "tài khoản:threadKey" -> {"name", "picture"}: tên/ảnh nhóm đọc từ bảng
        # LightSpeed trong sự kiện raw (tin E2EE không mang tên nhóm).
        self._threads: OrderedDict[str, dict[str, str]] = OrderedDict()
        # Lần cuối hỏi tên nhóm E2EE qua bridge (theo tài khoản:nhóm), để không hỏi mỗi tin.
        self._group_lookups: OrderedDict[str, float] = OrderedDict()
        # "tài khoản:threadKey" -> {contactId: isAdmin}: thành viên nhóm đã thấy, để
        # chỉ báo thay đổi thật chứ không báo cả danh sách mỗi lần đồng bộ.
        self._members: OrderedDict[str, dict[str, bool]] = OrderedDict()
        # "tài khoản:messageId" các tin bot thu hồi theo yêu cầu nhân viên: gateway đã ghi chú.
        self._recalled: OrderedDict[str, None] = OrderedDict()
        # "tài khoản:messageId" các tin bot sửa theo yêu cầu nhân viên.
        self._edited: OrderedDict[str, None] = OrderedDict()
        # "tài khoản:thread_id" -> lúc gửi "đang soạn" gần nhất (chặn gửi dồn).
        self._last_typing: dict[str, float] = {}
        # Route thêm trên cùng server HTTP (multi_main: /accounts), cùng token.
        self.routes: (
            Callable[[str, str, bytes], Awaitable[tuple[int, Any] | None]] | None
        ) = None

    @classmethod
    def from_env(
        cls, http_client: httpx.AsyncClient, log: Callable[[str, str], None]
    ) -> GatewayLink | None:
        url = os.environ.get("GATEWAY_URL", "")
        if not url:
            return None
        token = os.environ.get("GATEWAY_TOKEN", "")
        if len(token) < 32:
            raise RuntimeError("GATEWAY_TOKEN phải dài ít nhất 32 ký tự.")
        return cls(url, token, http_client, log)

    async def _post(self, path: str, body: dict[str, Any]) -> None:
        # File 20 MiB: gateway còn upload tiếp vào Libredesk trước khi trả lời.
        timeout = 120 if body.get("attachments") else 30
        response = await self.http.post(
            self.url + path,
            json=body,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=timeout,
        )
        response.raise_for_status()

    async def register(self, account: str, bot: _Bot) -> None:
        self.bots[account] = bot
        try:
            await self._post("/v1/register", {"channel": CHANNEL, "account": account})
        except httpx.HTTPError as error:
            # Gateway tự tạo inbox ở tin nhắn đầu tiên nên không chặn bot.
            self.log("gateway", f"Đăng ký inbox thất bại: {error}")

    async def post_alert(self, text: str) -> None:
        """Cảnh báo Telegram theo cài đặt trang Cảnh báo (204 khi đang tắt)."""
        await self._post("/v1/alert", {"text": text})

    def unregister(self, account: str, bot: _Bot) -> None:
        if self.bots.get(account) is bot:
            del self.bots[account]

    def forget_account(self, account: str) -> None:
        """Quên mọi thứ đã nhớ về một tài khoản vừa gỡ (tin, nhóm, thành viên, tin chờ echo)."""
        self.bots.pop(account, None)
        prefix = f"{account}:"
        for cache in (
            self._recent,
            self._threads,
            self._group_lookups,
            self._members,
            self._recalled,
            self._edited,
            self._last_typing,
        ):
            for key in [k for k in cache if k.startswith(prefix)]:
                del cache[key]
        self._pending = [p for p in self._pending if p.get("account") != account]

    def observe_raw(
        self, account: str, event: dict[str, Any]
    ) -> list[tuple[str, str, str]]:
        """Nhớ tên/ảnh/thành viên nhóm từ bảng LightSpeed (gọi từ listener thread).

        Trả về các thay đổi nhóm ``(threadKey, loại, giá trị)`` để ghi chú. Bảng
        LightSpeed vừa là sự kiện vừa là dữ liệu đồng bộ lúc kết nối, nên chỉ báo
        khi khác trạng thái đã biết: thà bỏ sót còn hơn báo sai cả loạt.
        """
        data = event.get("data")
        if not isinstance(data, dict) or data.get("type") != "LSTable":
            return []
        table = data.get("data")
        if not isinstance(table, dict):
            return []
        changes: list[tuple[str, str, str]] = []
        snapshots = set()
        for row in _rows(table, "LSDeleteThenInsertThread"):
            snapshots.add(str(row.get("ThreadKey") or ""))
            self._remember_thread(
                account,
                row.get("ThreadKey"),
                row.get("ThreadName"),
                row.get("ThreadPictureUrl"),
            )
        for row in _rows(table, "LSSyncUpdateThreadName"):
            key = str(row.get("ThreadKey") or "")
            name = row.get("ThreadName")
            known = self._threads.get(f"{account}:{key}", {}).get("name")
            self._remember_thread(account, key, name, None)
            if known and isinstance(name, str) and name.strip() not in ("", known):
                changes.append((key, "rename", name.strip()))
        # Danh bạ (kể cả chính tài khoản): tên/ảnh dùng khi /chat/user_info
        # không trả hồ sơ (một số tài khoản không tra được chính mình).
        for name, id_key in (
            ("LSDeleteThenInsertContact", "Id"),
            ("LSVerifyContactRowExists", "ContactId"),
        ):
            for row in _rows(table, name):
                self._remember_contact(
                    row.get(id_key), row.get("Name"), row.get("ProfilePictureUrl")
                )
        for row in _rows(table, "LSSetThreadImageURL"):
            self._remember_thread(
                account, row.get("ThreadKey"), None, row.get("ImageURL")
            )
        added: dict[str, list[dict[str, Any]]] = {}
        for row in _rows(table, "LSAddParticipantIdToGroupThread"):
            added.setdefault(str(row.get("ThreadKey") or ""), []).append(row)
        for key, rows in added.items():
            members = self._thread_members(account, key)
            # Ảnh chụp cả hội thoại hoặc lần đầu thấy nhóm: chỉ ghi nhận.
            report = members is not None and key not in snapshots and len(rows) <= 3
            members = members if members is not None else {}
            for row in rows:
                contact = str(row.get("ContactId") or "")
                if not contact:
                    continue
                if report and contact not in members:
                    changes.append((key, "add", contact))
                members[contact] = bool(row.get("IsAdmin"))
            self._set_thread_members(account, key, members)
        for row in _rows(table, "LSUpdateThreadParticipantAdminStatus"):
            key, contact = str(row.get("ThreadKey") or ""), str(
                row.get("ContactId") or ""
            )
            members = self._thread_members(account, key)
            if members is None or contact not in members:
                continue
            is_admin = bool(row.get("IsAdmin"))
            if members[contact] != is_admin:
                changes.append((key, "admin" if is_admin else "unadmin", contact))
            members[contact] = is_admin
        for row in _rows(table, "LSRemoveParticipantFromThread"):
            key = str(row.get("ThreadKey") or "")
            contact = str(row.get("ParticipantId") or "")
            if not key or not contact:
                continue
            members = self._thread_members(account, key)
            if members is not None:
                members.pop(contact, None)
            changes.append((key, "remove", contact))
        return [c for c in changes if c[0]]

    def _remember_contact(self, user_id: Any, name: Any, picture: Any) -> None:
        if not user_id or not isinstance(name, str) or not name.strip():
            return
        key = str(user_id)
        cached = self._names.get(key)
        avatar = (
            picture
            if isinstance(picture, str) and picture.startswith("https://")
            else ""
        )
        if cached and cached[0] == name.strip() and (cached[1] or not avatar):
            return
        try:
            now = asyncio.get_running_loop().time()
        except RuntimeError:  # listener thread: không có event loop
            now = cached[2] if cached else 0.0
        self._names[key] = (name.strip(), avatar or (cached[1] if cached else ""), now)

    def cached_profile(self, user_id: str) -> tuple[str, str]:
        """(tên, ảnh) đã biết của user, không gọi mạng."""
        cached = self._names.get(str(user_id))
        return (cached[0], cached[1]) if cached else ("", "")

    def _thread_members(self, account: str, key: str) -> dict[str, bool] | None:
        return self._members.get(f"{account}:{key}")

    def _set_thread_members(
        self, account: str, key: str, members: dict[str, bool]
    ) -> None:
        cache_key = f"{account}:{key}"
        self._members[cache_key] = members
        self._members.move_to_end(cache_key)
        while len(self._members) > RECENT_MAX:
            self._members.popitem(last=False)

    async def post_group_changes(
        self, account: str, bot: _Bot, changes: list[tuple[str, str, str]]
    ) -> None:
        """Thay đổi nhóm Facebook thành ghi chú ``group_event``.

        Không biết nhóm là E2EE hay chat thường, nên gửi cho cả hai thread id:
        gateway bỏ qua (202) thread chưa có hội thoại.
        """
        for key, change, value in changes:
            if change == "rename":
                text = f"Nhóm đổi tên thành «{value}»"
            else:
                name = await self._user_name(bot, value) or f"Facebook {value}"
                text = {
                    "add": f"{name} đã vào nhóm",
                    "remove": f"{name} đã rời hoặc bị xoá khỏi nhóm",
                    "admin": f"{name} được làm quản trị viên",
                    "unadmin": f"{name} không còn là quản trị viên",
                }[change]
            minute = int(time.time() // 60)
            for thread_id in (f"e2ee:{key}@g.us", f"thread:{key}"):
                await self._post_event(
                    account,
                    thread_id,
                    True,
                    "group_event",
                    "",
                    text,
                    f"{change}-{key}-{value}-{minute}",
                )

    def _remember_thread(
        self,
        account: str,
        key: Any,
        name: Any,
        picture: Any,
        source: str = "bảng LightSpeed",
    ) -> None:
        if not key:
            return
        cache_key = f"{account}:{key}"
        entry = dict(self._threads.get(cache_key) or {})
        if isinstance(name, str) and name.strip():
            if "name" not in entry:
                self.log("gateway", f"Đã biết tên nhóm {key} (từ {source}).")
            entry["name"] = name.strip()
        if isinstance(picture, str) and picture.startswith("https://"):
            entry["picture"] = picture
        if not entry:
            return
        self._threads[cache_key] = entry
        self._threads.move_to_end(cache_key)
        while len(self._threads) > RECENT_MAX:
            self._threads.popitem(last=False)

    async def _e2ee_group_info(
        self, account: str, bot: _Bot, thread_id: str
    ) -> dict[str, str]:
        """Như ``group_info``; nhóm E2EE chưa biết tên thì hỏi server qua bridge.

        Bảng LightSpeed chỉ nhắc tên nhóm khi Messenger đồng bộ đúng nhóm đó, và
        bộ nhớ mất khi bot khởi động lại: tin nhóm sau đó không có tên. Hỏi lại
        tối đa mỗi giờ một lần cho mỗi nhóm.
        """
        group = self.group_info(account, thread_id)
        bridge = _bridge_of(bot)
        if group.get("name") or bridge is None or not thread_id.startswith("e2ee:"):
            return group
        chat_jid = thread_id.removeprefix("e2ee:")
        key = chat_jid.split("@", 1)[0]
        lookup_key = f"{account}:{key}"
        now = asyncio.get_running_loop().time()
        last = self._group_lookups.get(lookup_key)
        if last is not None and now - last < NAME_RETRY_SECONDS:
            return group
        self._group_lookups[lookup_key] = now
        self._group_lookups.move_to_end(lookup_key)
        while len(self._group_lookups) > RECENT_MAX:
            self._group_lookups.popitem(last=False)
        try:
            info = await BridgeActions(bridge).get_e2ee_group_info(chat_jid)  # type: ignore[arg-type]
        except Exception as error:  # chưa nối E2EE, hết giờ, server từ chối
            self.log(
                "gateway",
                f"Không tra được tên nhóm {key}: {type(error).__name__}",
            )
            return group
        if isinstance(info, dict):
            self._remember_thread(account, key, info.get("name"), None, "server E2EE")
        return self.group_info(account, thread_id)

    def group_info(self, account: str, thread_id: str) -> dict[str, str]:
        """Tên/ảnh nhóm đã biết cho thread id của gateway (e2ee:<id>@g.us hoặc thread:<id>)."""
        key = thread_id.split(":", 1)[-1].split("@", 1)[0]
        return self._threads.get(f"{account}:{key}") or {}

    async def user_profile(self, bot: _Bot, user_id: str) -> tuple[str, str]:
        """(tên, ảnh đại diện) Facebook của user, có cache."""
        return await self._user_profile(bot, user_id)

    async def _user_profile(self, bot: _Bot, user_id: str) -> tuple[str, str]:
        """Tên và ảnh đại diện Facebook của user; tra lại sau 1 giờ nếu lần trước
        không có tên (tài khoản không phải bạn bè hoặc ẩn hồ sơ thường không trả tên).
        """
        if not user_id:
            return "", ""
        now = asyncio.get_running_loop().time()
        cached = self._names.get(user_id)
        if cached is None or (not cached[0] and now - cached[2] > NAME_RETRY_SECONDS):
            info = await _get_user_info.func(bot.dataFB, user_id, client=self.http)
            info = info if isinstance(info, dict) else {}
            name, avatar = info.get("nameUser"), info.get("thumbSrc")
            if not (isinstance(name, str) and name.strip()):
                # /chat/user_info không trả hồ sơ người lạ (nhắn lần đầu, không
                # phải bạn bè): hỏi danh bạ Messenger qua socket bridge đang mở.
                name, avatar = await self._contact_profile(bot, user_id)
            cached = (
                name.strip() if isinstance(name, str) else "",
                avatar if isinstance(avatar, str) else "",
                now,
            )
            self._names[user_id] = cached
        return cached[0], cached[1]

    async def _contact_profile(self, bot: _Bot, user_id: str) -> tuple[Any, Any]:
        """(tên, ảnh) từ danh bạ Messenger qua bridge; ("", "") nếu không có."""
        bridge = _bridge_of(bot)
        if bridge is None or not user_id.isdigit():
            return "", ""
        try:
            info = await BridgeActions(bridge).get_user_info(user_id)  # type: ignore[arg-type]
        except Exception as error:  # bridge chưa nối, không tìm thấy, hết giờ
            self.log(
                "gateway",
                f"Không tra được tên Facebook {user_id} qua danh bạ: {type(error).__name__}",
            )
            return "", ""
        if not isinstance(info, dict):
            return "", ""
        picture = info.get("profilePictureUrl")
        if not (isinstance(picture, str) and picture.startswith("https://")):
            picture = ""
        return info.get("name"), picture

    async def _user_name(self, bot: _Bot, user_id: str) -> str:
        return (await self._user_profile(bot, user_id))[0]

    def _remember(self, account: str, message_id: str, entry: dict[str, Any]) -> None:
        # Khoá theo tài khoản: cùng một tin được bot của cả hai bên nhìn thấy.
        if not message_id:
            return
        key = f"{account}:{message_id}"
        self._recent[key] = entry
        self._recent.move_to_end(key)
        while len(self._recent) > RECENT_MAX:
            self._recent.popitem(last=False)

    def _mark_bot_sent(self, message_id: Any) -> None:
        if message_id:
            self._bot_sent[str(message_id)] = None
            while len(self._bot_sent) > RECENT_MAX:
                self._bot_sent.popitem(last=False)

    def is_bot_echo(
        self, account: str, thread_id: str, message: dict[str, Any]
    ) -> bool:
        """Tin của chính tài khoản do bot gửi (qua /send) thì không ghi chú lại."""
        if str(message.get("messageID") or "") in self._bot_sent:
            return True
        now = asyncio.get_running_loop().time()
        self._pending = [p for p in self._pending if p["until"] > now]
        body = message.get("body") if isinstance(message.get("body"), str) else ""
        for pending in self._pending:
            if (
                pending["account"] == account
                and pending["thread_id"] == thread_id
                and (
                    (body and body == pending["text"])
                    or (not body and pending["files"] > 0)
                )
            ):
                self._pending.remove(pending)
                return True
        return False

    def _quote(self, account: str, message: dict[str, Any]) -> str:
        reply = _raw(message).get("replyTo")
        if not isinstance(reply, dict):
            return ""
        cached = self._recent.get(f"{account}:{reply.get('messageId') or ''}")
        text = reply.get("text") or (cached or {}).get("summary") or ""
        sender = (cached or {}).get("sender") or ""
        if not text:
            return "(tin được trả lời không còn trong bộ nhớ của bot)"
        return f"{sender}: {text}" if sender else str(text)

    async def _post_event(
        self,
        account: str,
        thread_id: str,
        is_group: bool,
        kind: str,
        sender: str,
        text: str,
        event_id: str,
        files: list[dict[str, str]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        try:
            await self._post(
                "/v1/event",
                {
                    **(extra or {}),
                    "channel": CHANNEL,
                    "account": account,
                    "thread_id": thread_id,
                    "is_group": is_group,
                    "sender_name": sender,
                    "kind": kind,
                    "text": text,
                    "message_id": f"{kind}-{event_id}" if event_id else "",
                    "attachments": files or [],
                },
            )
        except httpx.HTTPError as error:
            self.log("gateway", f"❌ Không ghi được sự kiện {kind}: {error}")

    async def forward_owner(
        self, account: str, bot: _Bot, message: dict[str, Any]
    ) -> None:
        """Tin chủ tài khoản gửi từ thiết bị khác thành ghi chú nội bộ."""
        ref = thread_ref(message)
        if ref is None:
            return
        thread_id, is_group = ref
        self._remember(
            account,
            str(message.get("messageID") or ""),
            {
                "summary": summarize(message),
                "sender": OWNER,
                "thread_id": thread_id,
                "is_group": is_group,
            },
        )
        if self.is_bot_echo(account, thread_id, message):
            return
        text, files = await self._collect(bot, message)
        if text or files:
            await self._post_event(
                account,
                thread_id,
                is_group,
                "owner_message",
                OWNER,
                text,
                str(message.get("messageID") or ""),
                files,
            )

    async def handle_meta(self, account: str, bot: _Bot, event: dict[str, Any]) -> None:
        """Reaction, sửa tin, thu hồi thành ghi chú nội bộ."""
        raw_data = event.get("data")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
        kind = event.get("type")
        message_id = str(data.get("messageId") or "")
        cached = self._recent.get(f"{account}:{message_id}") or {}
        own_id = str(bot.dataFB.get("FacebookID"))
        if kind in ("e2eeReaction", "reaction"):
            if kind == "e2eeReaction":
                thread_id, is_group = f"e2ee:{data.get('chatJid')}", False
                actor = str(data.get("senderId") or "")
            else:
                thread_id = cached.get("thread_id") or f"thread:{data.get('threadId')}"
                is_group = bool(cached.get("is_group"))
                actor = str(data.get("actorId") or "")
            who = (
                OWNER
                if actor == own_id
                else await self._user_name(bot, actor) or f"Facebook {actor}"
            )
            target = f" vào tin «{cached['summary']}»" if cached.get("summary") else ""
            emoji = data.get("reaction") or "(bỏ cảm xúc)"
            # Bridge gửi senderTimestampMs = 0 khi gói cảm xúc thiếu thời điểm thả:
            # app Messenger bỏ qua cảm xúc đó dù bridge khác vẫn đọc được. Canary
            # thả cảm xúc giữa hai tài khoản thử và trượt khi thấy dấu này.
            if kind == "e2eeReaction" and data.get("senderTimestampMs", 1) in (0, None):
                target += f" {MISSING_REACTION_TS}"
                self.log(
                    "gateway",
                    "❌ Cảm xúc E2EE thiếu senderTimestampMs: app Messenger sẽ không hiện.",
                )
            # Gateway gắn cảm xúc lên đúng tin trong Libredesk (huy hiệu như
            # Messenger); không tìm được tin thì ghi chú bằng `text` như cũ.
            await self._post_event(
                account,
                thread_id,
                is_group,
                "reaction",
                who,
                f"{emoji}{target}",
                f"{message_id}-{actor}-{emoji}",
                extra={
                    "target_ids": [message_id] if message_id else [],
                    "reactor_id": "self" if actor == own_id else actor,
                    "reaction": str(data.get("reaction") or ""),
                },
            )
        elif kind == "messageEdit" and f"{account}:{message_id}" in self._edited:
            # Bot vừa sửa theo yêu cầu nhân viên: gateway đã ghi chú. Chỉ cập nhật
            # nội dung đã nhớ (cho trích dẫn/thu hồi sau này).
            cached["summary"] = str(data.get("newText") or "")
            return
        elif kind == "messageEdit":
            if not cached.get("thread_id"):
                return  # sửa tin không rõ thread (bot chưa thấy tin gốc)
            new_text = str(data.get("newText") or "")
            text = f"«{cached.get('summary', '')}» → «{new_text}»"
            cached["summary"] = new_text
            await self._post_event(
                account,
                cached["thread_id"],
                bool(cached.get("is_group")),
                "edit",
                cached.get("sender", ""),
                text,
                f"{message_id}-{data.get('editCount', '')}",
            )
        elif (
            kind == "messageUnsend"
            and f"{account}:{data.get('messageId') or ''}" in self._recalled
        ):
            return
        elif kind == "messageUnsend":
            raw_thread = str(data.get("threadId") or "")
            thread_id = cached.get("thread_id") or (
                f"e2ee:{raw_thread}" if data.get("isE2EE") else f"thread:{raw_thread}"
            )
            text = (
                f"«{cached['summary']}»"
                if cached.get("summary")
                else "(nội dung tin không còn trong bộ nhớ của bot)"
            )
            await self._post_event(
                account,
                thread_id,
                bool(cached.get("is_group")),
                "recall",
                cached.get("sender", ""),
                text,
                message_id,
            )

    async def _collect(
        self, bot: _Bot, message: dict[str, Any]
    ) -> tuple[str, list[dict[str, str]]]:
        """Chữ của tin + file tải được; file lỗi/không tải được thành dòng mô tả."""
        body = message.get("body")
        parts = [body] if isinstance(body, str) and body.strip() else []
        files: list[dict[str, str]] = []
        bridge = _bridge_of(bot)
        for attachment in message.get("attachments") or []:
            if not isinstance(attachment, dict):
                continue
            file = None
            if bridge is not None:
                try:
                    file = await fetch_attachment(bridge, attachment)
                except Exception as error:  # bridge/mạng/dữ liệu: vẫn báo bằng chữ
                    self.log("gateway", f"Không tải được file đính kèm: {error}")
                if file is None and attachment.get("fetchError"):
                    # Bridge không tra được URL (sticker kho Messenger); lý do đã lọc bí mật.
                    self.log(
                        "gateway",
                        f"Không lấy được {attachment.get('type') or 'file'}: "
                        f"{str(attachment['fetchError'])[:160]}",
                    )
            if file is not None:
                files.append(file)
            else:
                parts.append(describe_attachment(attachment))
        if not parts and not files and message.get("type") == "e2ee":
            parts.append(UNSUPPORTED_E2EE_TEXT)
        return "\n".join(parts), files

    async def forward(self, account: str, bot: _Bot, message: dict[str, Any]) -> None:
        """Chuyển một tin khách sang gateway; lỗi chỉ được ghi log."""
        ref = thread_ref(message)
        if ref is None:
            return
        text, files = await self._collect(bot, message)
        if not text and not files:
            return
        thread_id, is_group = ref
        user_id = str(message.get("userID") or "")
        # Không tra được tên (ẩn hồ sơ / không phải bạn bè): dùng nhãn dễ đọc.
        name, avatar = await self._user_profile(bot, user_id)
        sender_name = name or (f"Facebook {user_id}" if user_id else "")
        self._remember(
            account,
            str(message.get("messageID") or ""),
            {
                "summary": summarize(message),
                "sender": sender_name,
                "thread_id": thread_id,
                "is_group": is_group,
                # Trả lời trích dẫn E2EE cần JID người gửi tin gốc.
                "sender_jid": str(message.get("senderJid") or ""),
            },
        )
        raw = _raw(message)
        group = await self._e2ee_group_info(account, bot, thread_id) if is_group else {}
        # Nhóm chưa biết tên: để trống, gateway giữ tên đã biết hoặc đặt tên chung
        # (không lấy tên người gửi).
        thread_name = raw.get("threadName") or (
            group.get("name", "") if is_group else sender_name
        )
        try:
            await self._post(
                "/v1/inbound",
                {
                    "channel": CHANNEL,
                    "account": account,
                    "thread_id": thread_id,
                    "is_group": is_group,
                    "thread_name": thread_name,
                    "sender_name": sender_name,
                    "text": text,
                    "message_id": str(message.get("messageID") or ""),
                    "attachments": files,
                    "quote": self._quote(account, message),
                    # Nhóm Facebook: chưa có API ảnh nhóm, Libredesk dùng chữ viết tắt.
                    "thread_avatar": group.get("picture", "") if is_group else avatar,
                    "sender_avatar": avatar,
                },
            )
        except httpx.HTTPError as error:
            self.log("gateway", f"❌ Không chuyển được tin tới gateway: {error}")

    def _seen_reply(self, message_id: str) -> bool:
        if not message_id:
            return False
        if message_id in self._recent_replies:
            return True
        self._recent_replies[message_id] = None
        if len(self._recent_replies) > RECENT_MAX:
            self._recent_replies.popitem(last=False)
        return False

    async def send_reply(self, payload: dict[str, Any]) -> tuple[int, str]:
        """Gửi tin trả lời của nhân viên (chữ và/hoặc file); trả về (status, mô tả)."""
        account = str(payload.get("account") or "")
        bot = self.bots.get(account)
        if bot is None:
            return 404, "unknown account"
        thread_id = payload.get("thread_id")
        raw_text = payload.get("text")
        text = raw_text if isinstance(raw_text, str) else ""
        files = [
            f
            for f in (payload.get("attachments") or [])
            if isinstance(f, dict) and isinstance(f.get("data"), str) and f["data"]
        ]
        if not isinstance(thread_id, str) or (not text.strip() and not files):
            return 400, "invalid payload"
        try:
            for f in files:
                base64.b64decode(f["data"], validate=True)
        except (binascii.Error, ValueError):
            return 400, "invalid attachment data"
        kind, _, target = thread_id.partition(":")
        if not ((kind == "e2ee" and target) or (kind == "thread" and target.isdigit())):
            return 400, "invalid thread_id"
        message_id = str(payload.get("message_id") or "")
        if self._seen_reply(message_id):
            return 200, "duplicate"
        bridge = _bridge_of(bot)
        if files and bridge is None:
            self._recent_replies.pop(message_id, None)
            return 502, "bridge not ready"
        result: dict[str, Any] = {}
        pending = {
            "account": str(payload.get("account")),
            "thread_id": thread_id,
            "text": text,
            "files": len(files),
            "until": asyncio.get_running_loop().time() + ECHO_WINDOW_SECONDS,
        }
        self._pending.append(pending)
        # Nhân viên trả lời trích dẫn: gateway gửi reply_to = messageID của tin khách.
        reply_to = str(payload.get("reply_to") or "")
        quoted = self._recent.get(f"{account}:{reply_to}") if reply_to else None
        try:
            if text.strip() and kind == "e2ee":
                if quoted is not None:
                    result = await bot.listener.send_e2ee_message(
                        target, text, reply_to, str(quoted.get("sender_jid") or "")
                    )
                else:
                    result = await bot.listener.send_e2ee_message(target, text)
            elif text.strip():
                result = await bot.listener.send_message(
                    int(target), text, reply_to if quoted is not None else ""
                )
            sent_ids: list[str] = []
            if text.strip():
                sent_ids.append(self._after_send(account, result, thread_id, text))
            for f in files:
                method, params = media_rpc(kind, target, f)
                assert bridge is not None
                result = await bridge.call(method, params, MEDIA_RPC_TIMEOUT)
                sent_ids.append(
                    self._after_send(
                        account, result, thread_id, f"[Tệp] {f.get('name', '')}"
                    )
                )
        except Exception as error:  # lỗi bridge/mạng: để gateway thử lại
            self._recent_replies.pop(message_id, None)
            if pending in self._pending:
                self._pending.remove(pending)
            self.log("gateway", f"❌ Gửi tin trả lời thất bại: {type(error).__name__}")
            return 502, "send failed"
        if not (result.get("messageId") or result.get("id")):
            # Có thể đã gửi nhưng không xác nhận (deliveryStatus UNKNOWN): không
            # trả lỗi để gateway không gửi lại, tránh khách nhận trùng.
            self.log("gateway", "Gửi tin trả lời chưa được xác nhận; không thử lại.")
        else:
            suffix = f" ({len(files)} tệp)" if files else ""
            self.log("gateway", f"Đã gửi tin trả lời của nhân viên{suffix}.")
        # Gateway giữ các id này để nhân viên thu hồi tin sau.
        return 200, json.dumps({"ok": True, "message_ids": [i for i in sent_ids if i]})

    async def post_presence(self, account: str, event: dict[str, Any]) -> None:
        """Chuyển "đã xem"/"đang soạn tin" của khách cho gateway (bỏ qua lỗi)."""
        bot = self.bots.get(account)
        own_id = str(bot.dataFB.get("FacebookID") or "") if bot is not None else ""
        found = presence_of(event, own_id)
        if found is None:
            return
        thread_id, kind, ids = found
        now = asyncio.get_running_loop().time()
        key = f"{account}:{thread_id}"
        if kind == "typing":
            if now - self._last_typing.get(key, -1e9) < TYPING_THROTTLE_SECONDS:
                return
            self._last_typing[key] = now
            if len(self._last_typing) > RECENT_MAX:
                self._last_typing.pop(next(iter(self._last_typing)))
        else:
            self._last_typing.pop(key, None)
        try:
            await self._post(
                "/v1/presence",
                {
                    "channel": CHANNEL,
                    "account": account,
                    "thread_id": thread_id,
                    "kind": kind,
                    "message_ids": ids,
                },
            )
        except httpx.HTTPError:
            pass  # trạng thái phụ: mất một lần không sao

    async def resolve(self, payload: dict[str, Any]) -> tuple[int, str]:
        """Người nhận cho tin nhân viên nhắn trước: ID Facebook -> chat E2EE."""
        bot = self.bots.get(str(payload.get("account") or ""))
        if bot is None:
            return 404, "unknown account"
        user_id = facebook_user_id(payload.get("to"))
        if not user_id:
            return 400, "Nhập ID số Facebook của khách (hoặc link hồ sơ có id=...)."
        name, avatar = await self._user_profile(bot, user_id)
        return 200, json.dumps(
            {"thread_id": f"e2ee:{user_id}@msgr", "name": name, "avatar": avatar}
        )

    async def edit(self, payload: dict[str, Any]) -> tuple[int, str]:
        """Sửa tin nhân viên đã gửi (gateway gọi POST /edit)."""
        account = str(payload.get("account") or "")
        bot = self.bots.get(account)
        if bot is None:
            return 404, "unknown account"
        thread_id = str(payload.get("thread_id") or "")
        kind, _, target = thread_id.partition(":")
        message_id = str(payload.get("message_id") or "")
        text = payload.get("text")
        if not message_id or not isinstance(text, str) or not text.strip():
            return 400, "invalid payload"
        if kind not in ("e2ee", "thread") or not target:
            return 400, "invalid payload"
        bridge = _bridge_of(bot)
        if bridge is None:
            return 502, "bridge not ready"
        actions = BridgeActions(bridge)  # type: ignore[arg-type]
        key = f"{account}:{message_id}"
        self._edited[key] = None
        while len(self._edited) > RECENT_MAX:
            self._edited.popitem(last=False)
        try:
            if kind == "e2ee":
                await actions.edit_e2ee_message(target, message_id, text)
            else:
                await actions.edit_message(message_id, text)
        except Exception as error:  # bridge/Facebook từ chối (vd. quá hạn sửa)
            self._edited.pop(key, None)
            self.log("gateway", f"❌ Sửa tin thất bại: {error}")
            return 502, f"Facebook không sửa được tin: {error}"
        cached = self._recent.get(key)
        if cached is not None:
            cached["summary"] = text[:200]
        self.log("gateway", "Đã sửa tin nhân viên.")
        return 200, json.dumps({"ok": True})

    async def recall(self, payload: dict[str, Any]) -> tuple[int, str]:
        """Thu hồi tin nhân viên đã gửi (gateway gọi POST /recall)."""
        account = str(payload.get("account") or "")
        bot = self.bots.get(account)
        if bot is None:
            return 404, "unknown account"
        thread_id = str(payload.get("thread_id") or "")
        kind, _, target = thread_id.partition(":")
        ids = [str(i) for i in (payload.get("message_ids") or []) if i]
        if not ids or kind not in ("e2ee", "thread") or not target:
            return 400, "invalid payload"
        bridge = _bridge_of(bot)
        if bridge is None:
            return 502, "bridge not ready"
        actions = BridgeActions(bridge)  # type: ignore[arg-type]
        try:
            for message_id in ids:
                # Theo tài khoản: một tiến trình chạy nhiều tài khoản, tài khoản
                # nhận (khách) vẫn phải ghi chú tin bị thu hồi.
                self._recalled[f"{account}:{message_id}"] = None
                while len(self._recalled) > RECENT_MAX:
                    self._recalled.popitem(last=False)
                if kind == "e2ee":
                    await actions.unsend_e2ee_message(target, message_id)
                else:
                    await actions.unsend_message(message_id)
        except Exception as error:  # bridge/Facebook từ chối
            self.log("gateway", f"❌ Thu hồi thất bại: {error}")
            return 502, f"Facebook không thu hồi được: {error}"
        self.log("gateway", f"Đã thu hồi tin nhân viên ({len(ids)} tin).")
        return 200, json.dumps({"ok": True})

    async def react(self, payload: dict[str, Any]) -> tuple[int, str]:
        """Nhân viên thả cảm xúc lên tin khách (gateway gọi POST /react); emoji
        rỗng là bỏ cảm xúc."""
        account = str(payload.get("account") or "")
        bot = self.bots.get(account)
        if bot is None:
            return 404, "unknown account"
        thread_id = str(payload.get("thread_id") or "")
        kind, _, target = thread_id.partition(":")
        message_id = str(payload.get("message_id") or "")
        emoji = payload.get("emoji")
        if not message_id or not isinstance(emoji, str) or len(emoji) > 16:
            return 400, "invalid payload"
        if kind not in ("e2ee", "thread") or not target:
            return 400, "invalid payload"
        bridge = _bridge_of(bot)
        if bridge is None:
            return 502, "bridge not ready"
        emoji = emoji.replace("\ufe0f", "")  # Messenger dùng ❤ không kèm FE0F
        try:
            if kind == "e2ee":
                cached = self._recent.get(f"{account}:{message_id}") or {}
                # Cảm xúc E2EE cần JID người gửi tin gốc; chat 1-1 thì là khách.
                sender = cached.get("sender_jid") or (
                    "" if cached.get("is_group") else target
                )
                if not sender:
                    return 409, "Bot không còn nhớ người gửi tin này."
                await bridge.call(
                    "sendE2EEReaction",
                    {
                        "chatJid": target,
                        "messageId": message_id,
                        "senderJid": sender,
                        "emoji": emoji,
                    },
                )
            else:
                await bridge.call(
                    "sendReaction",
                    {"threadId": int(target), "messageId": message_id, "emoji": emoji},
                )
        except Exception as error:  # bridge/Facebook từ chối
            self.log("gateway", f"❌ Thả cảm xúc thất bại: {error}")
            return 502, f"Facebook không thả được cảm xúc: {error}"
        self.log(
            "gateway",
            "Nhân viên đã thả cảm xúc." if emoji else "Nhân viên đã bỏ cảm xúc.",
        )
        return 200, json.dumps({"ok": True})

    def _after_send(
        self, account: str, result: dict[str, Any], thread_id: str, summary: str
    ) -> str:
        sent_id = result.get("messageId") or result.get("id")
        self._mark_bot_sent(sent_id)
        if sent_id and summary.strip():
            self._remember(
                account,
                str(sent_id),
                {
                    "summary": summary[:200],
                    "sender": "Nhân viên",
                    "thread_id": thread_id,
                    "is_group": False,
                },
            )
        return str(sent_id or "")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        status, text = 500, "error"
        content_type = "text/plain; charset=utf-8"
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=10)
            headers: dict[str, str] = {}
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=10)
                if line in (b"\r\n", b"\n", b""):
                    break
                name, _, value = line.decode("latin-1").partition(":")
                headers[name.strip().lower()] = value.strip()
            method, path, *_ = request_line.decode("latin-1").split()
            length = int(headers.get("content-length") or 0)
            is_send = method == "POST" and path in (
                "/send",
                "/recall",
                "/edit",
                "/resolve",
                "/react",
            )
            if not is_send and self.routes is None:
                status, text = 404, "not found"
            elif not hmac.compare_digest(
                headers.get("authorization", ""), f"Bearer {self.token}"
            ):
                status, text = 401, "unauthorized"
            elif length > MAX_REQUEST_BYTES:
                status, text = 413, "too large"
            elif not is_send and self.routes is not None:
                body = await asyncio.wait_for(reader.readexactly(length), timeout=10)
                routed = await self.routes(method, path, body)
                if routed is None:
                    status, text = 404, "not found"
                else:
                    status = routed[0]
                    text = "" if routed[1] is None else json.dumps(routed[1])
                    content_type = "application/json"
            else:
                body = await asyncio.wait_for(reader.readexactly(length), timeout=10)
                try:
                    payload = json.loads(body)
                except ValueError:
                    status, text = 400, "invalid json"
                else:
                    if isinstance(payload, dict) and path in (
                        "/recall",
                        "/edit",
                        "/resolve",
                        "/react",
                    ):
                        handler = {
                            "/react": self.react,
                            "/recall": self.recall,
                            "/edit": self.edit,
                            "/resolve": self.resolve,
                        }[path]
                        status, text = await handler(payload)
                        content_type = (
                            "application/json" if status == 200 else content_type
                        )
                    elif isinstance(payload, dict):
                        status, text = await self.send_reply(payload)
                        content_type = (
                            "application/json" if status == 200 else content_type
                        )
                    else:
                        status, text = 400, "invalid json"
        except (ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError):
            status, text = 400, "bad request"
        finally:
            data = text.encode()
            writer.write(
                f"HTTP/1.1 {status} X\r\nContent-Type: {content_type}\r\n"
                f"Content-Length: {len(data)}\r\nConnection: close\r\n\r\n".encode()
                + data
            )
            try:
                await writer.drain()
            finally:
                writer.close()

    async def serve(self, port: int) -> asyncio.Server:
        server = await asyncio.start_server(self._handle_connection, "0.0.0.0", port)
        self.log("gateway", f"Nhận tin trả lời tại :{port}/send")
        return server
