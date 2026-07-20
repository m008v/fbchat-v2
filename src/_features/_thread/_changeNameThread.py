"""
Đường dẫn file:
  src/_features/_thread/_changeNameThread.py

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

from __future__ import annotations

import random
import time
from typing import Any

import httpx

from _core._utils import (
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
