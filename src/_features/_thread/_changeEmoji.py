"""
Đường dẫn file:
  src/_features/_thread/_changeEmoji.py

Mục đích:
  - Thay đổi biểu tượng cảm xúc (emoji) mặc định của nhóm chat.

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

from typing import Any

import httpx

from _core._utils import formatResults, formAll, post_form_json_async

_URL = "https://www.facebook.com/messaging/save_thread_emoji/?source=thread_settings&__pc=EXP1%3Amessengerdotcom_pkg"


def _build_form(
    dataFB: dict[str, Any], threadID: str | int, newEmoji: str
) -> dict[str, Any]:
    if not newEmoji:
        raise ValueError("Emoji mới không được để trống.")
    data_form = formAll(dataFB, requireGraphql=False)
    data_form.update({"emoji_choice": newEmoji, "thread_or_other_fbid": str(threadID)})
    return data_form


def _parse_result(payload: dict[str, Any]) -> dict[str, str]:
    error = payload.get("error")
    if error == 1357031:
        return formatResults(
            "error", "Không thể đổi emoji của cuộc trò chuyện không tồn tại."
        )
    if error:
        return formatResults("error", f"Facebook từ chối đổi emoji: {error}.")
    return formatResults("success", "Thay đổi emoji mặc định thành công.")



async def func(
    dataFB: dict[str, Any],
    threadID: str | int,
    newEmoji: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    payload = await post_form_json_async(
        _URL,
        _build_form(dataFB, threadID, newEmoji),
        dataFB["cookieFacebook"],
        strip_for_loop_prefix=True,
        client=client,
    )
    return _parse_result(payload)
