from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

from _core._utils import (
    formAll,
    gen_threading_id,
    mainRequests,
    send_request,
    send_request_async,
)

_SEND_URL = "https://www.facebook.com/messaging/send/"
_PROPERTIES = (
    "is_unread",
    "is_cleared",
    "is_forward",
    "is_filtered_content",
    "is_filtered_content_bh",
    "is_filtered_content_account",
    "is_filtered_content_quasar",
    "is_filtered_content_invalid_app",
    "is_spoof_warning",
)
_ATTACHMENT_FIELDS = {
    "gif": "gif_ids",
    "image": "image_ids",
    "video": "video_ids",
    "file": "file_ids",
    "audio": "audio_ids",
}


def _validate_inputs(
    content: str,
    thread_id: str | int | list[str | int],
    attachment_type: str | None,
    attachment_id: str | int | list[str | int] | None,
    chat_type: str | None,
    reply_message: bool | None,
    message_id: str | None,
) -> None:
    if isinstance(thread_id, list):
        if not thread_id or any(not str(item).strip() for item in thread_id):
            raise ValueError("Danh sách người nhận không được rỗng hoặc chứa ID rỗng.")
        if chat_type != "user":
            raise ValueError("Danh sách người nhận chỉ hợp lệ khi typeChat='user'.")
    elif not str(thread_id).strip():
        raise ValueError("threadID không được để trống.")
    if chat_type not in {None, "user"}:
        raise ValueError("typeChat chỉ nhận None hoặc 'user'.")
    if attachment_type is not None and attachment_type not in _ATTACHMENT_FIELDS:
        raise ValueError(
            f"typeAttachment không hợp lệ: {attachment_type}. "
            f"Hỗ trợ: {', '.join(_ATTACHMENT_FIELDS)}."
        )
    if (attachment_type is None) != (attachment_id is None):
        raise ValueError("typeAttachment và attachmentID phải được truyền cùng nhau.")
    if not content and attachment_id is None:
        raise ValueError("Tin nhắn phải có nội dung hoặc attachment.")
    if reply_message and not message_id:
        raise ValueError("messageID là bắt buộc khi replyMessage=True.")


def _build_form(
    dataFB: dict[str, Any],
    content: str,
    thread_id: str | int | list[str | int],
    attachment_type: str | None,
    attachment_id: str | int | list[str | int] | None,
    chat_type: str | None,
    reply_message: bool | None,
    message_id: str | None,
) -> dict[str, Any]:
    _validate_inputs(
        content,
        thread_id,
        attachment_type,
        attachment_id,
        chat_type,
        reply_message,
        message_id,
    )
    data_form = formAll(dataFB, requireGraphql=False)
    data_form.update({property_name: False for property_name in _PROPERTIES})

    if chat_type == "user":
        recipients = thread_id if isinstance(thread_id, list) else [thread_id]
        for index, recipient in enumerate(recipients):
            data_form[f"specific_to_list[{index}]"] = f"fbid:{recipient}"
        data_form[f"specific_to_list[{len(recipients)}]"] = (
            f"fbid:{dataFB['FacebookID']}"
        )
        if len(recipients) == 1:
            data_form["other_user_fbid"] = str(recipients[0])
    else:
        data_form["thread_fbid"] = str(thread_id)

    now_ms = int(time.time() * 1000)
    offline_id = gen_threading_id()
    data_form.update(
        {
            "action_type": "ma-type:user-generated-message",
            "body": content,
            "author": f"fbid:{dataFB['FacebookID']}",
            "timestamp": now_ms,
            "timestamp_absolute": "Today",
            "source": "source:chat:web",
            "source_tags[0]": "source:chat",
            "client_thread_id": f"root:{offline_id}",
            "offline_threading_id": offline_id,
            "message_id": offline_id,
            "threading_id": (
                f"<{now_ms}:{random.randrange(2**32)}-"
                f"{random.randrange(2**31):x}@mail.projektitan.com>"
            ),
            "ephemeral_ttl_mode": "0",
            "manual_retry_cnt": "0",
            "ui_push_phase": "V3",
        }
    )
    if reply_message:
        data_form["replied_to_message_id"] = message_id
    if attachment_type is not None and attachment_id is not None:
        data_form["has_attachment"] = True
        attachment_ids = (
            attachment_id if isinstance(attachment_id, list) else [attachment_id]
        )
        field = _ATTACHMENT_FIELDS[attachment_type]
        for index, value in enumerate(attachment_ids):
            data_form[f"{field}[{index}]"] = value
    return data_form


def _parse_response(text: str) -> dict[str, Any]:
    payload = text.strip()
    if payload.startswith("for (;;);"):
        payload = payload[len("for (;;);") :].lstrip()
    try:
        response = json.loads(payload)
    except json.JSONDecodeError:
        return {
            "error": 1,
            "payload": {"error-description": "Facebook trả về JSON không hợp lệ."},
        }

    actions = (response.get("payload") or {}).get("actions") or []
    if actions and isinstance(actions[0], dict):
        action = actions[0]
        if action.get("message_id"):
            return {
                "success": 1,
                "payload": {
                    "messageID": action["message_id"],
                    "timestamp": action.get("timestamp"),
                },
            }
    return {
        "error": 1,
        "payload": {
            "error-description": response.get("errorDescription")
            or "Facebook không xác nhận tin nhắn đã gửi.",
            "error-code": response.get("error"),
        },
    }


class api:
    """Messenger sender; mỗi lời gọi xây request độc lập và an toàn khi await."""

    def __init__(self) -> None:
        self.properties = list(_PROPERTIES)
        self.results: dict[str, Any] = {}

    def send(
        self,
        dataFB: dict[str, Any],
        contentSend: str | int,
        threadID: str | int | list[str | int],
        typeAttachment: str | None = None,
        attachmentID: str | int | list[str | int] | None = None,
        typeChat: str | None = None,
        replyMessage: bool | None = None,
        messageID: str | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        form = _build_form(
            dataFB,
            str(contentSend),
            threadID,
            typeAttachment,
            attachmentID,
            typeChat,
            replyMessage,
            messageID,
        )
        response = send_request(
            mainRequests(_SEND_URL, form, dataFB["cookieFacebook"]), client=client
        )
        response.raise_for_status()
        result = _parse_response(response.text)
        self.results = result
        return result

    async def send_async(
        self,
        dataFB: dict[str, Any],
        contentSend: str | int,
        threadID: str | int | list[str | int],
        typeAttachment: str | None = None,
        attachmentID: str | int | list[str | int] | None = None,
        typeChat: str | None = None,
        replyMessage: bool | None = None,
        messageID: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        form = _build_form(
            dataFB,
            str(contentSend),
            threadID,
            typeAttachment,
            attachmentID,
            typeChat,
            replyMessage,
            messageID,
        )
        response = await send_request_async(
            mainRequests(_SEND_URL, form, dataFB["cookieFacebook"]), client=client
        )
        response.raise_for_status()
        result = _parse_response(response.text)
        self.results = result
        return result
