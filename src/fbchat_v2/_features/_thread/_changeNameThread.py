from __future__ import annotations

import random
import time
from typing import Any

import httpx

from fbchat_v2._core._utils import (
    formatResults,
    formAll,
    gen_threading_id,
    post_form_json_async,
)

_URL = "https://www.facebook.com/messaging/set_thread_name/"


def _build_form(
    dataFB: dict[str, Any], threadID: str | int, newNameThread: str
) -> dict[str, Any]:
    if not newNameThread.strip():
        raise ValueError("Tên cuộc trò chuyện không được để trống.")
    threading_id = gen_threading_id()
    now_ms = int(time.time() * 1000)
    data_form = formAll(dataFB, requireGraphql=False)
    data_form.update(
        {
            "client": "mercury",
            "author": f"fbid:{dataFB['FacebookID']}",
            "timestamp": now_ms,
            "timestamp_absolute": "Today",
            "is_unread": False,
            "is_cleared": False,
            "is_forward": False,
            "is_filtered_content": False,
            "is_filtered_content_bh": False,
            "is_filtered_content_account": False,
            "is_filtered_content_quasar": False,
            "is_filtered_content_invalid_app": False,
            "is_spoof_warning": False,
            "thread_fbid": str(threadID),
            "thread_name": newNameThread.strip(),
            "thread_id": str(threadID),
            "source": "source:chat:web",
            "source_tags[0]": "source:chat",
            "client_thread_id": f"root:{threading_id}",
            "offline_threading_id": threading_id,
            "message_id": threading_id,
            "threading_id": f"<{now_ms}:{random.randrange(2**32)}-{random.randrange(2**31):x}@mail.projektitan.com>",
            "ephemeral_ttl_mode": "0",
            "manual_retry_cnt": "0",
            "ui_push_phase": "V3",
            "log_message_type": "log:thread-name",
        }
    )
    return data_form


def _parse_result(payload: dict[str, Any]) -> dict[str, str]:
    error = payload.get("error")
    if error == 1545012:
        return formatResults(
            "error", "Bạn không thể đổi tên khi không còn là thành viên."
        )
    if error == 1545003:
        return formatResults(
            "error", "Không thể đổi tên cuộc trò chuyện không tồn tại."
        )
    if error:
        return formatResults("error", f"Facebook từ chối đổi tên: {error}.")
    return formatResults("success", "Thay đổi tên cuộc trò chuyện thành công.")



async def func(
    dataFB: dict[str, Any],
    threadID: str | int,
    newNameThread: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    payload = await post_form_json_async(
        _URL,
        _build_form(dataFB, threadID, newNameThread),
        dataFB["cookieFacebook"],
        strip_for_loop_prefix=True,
        client=client,
    )
    return _parse_result(payload)
