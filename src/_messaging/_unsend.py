"""
Đường dẫn file:
  src/_messaging/_unsend.py

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

from typing import Any

import httpx

from _core._utils import (
    formAll,
    mainRequests,
    parse_json_response,
    send_request_async,
)

_URL = "https://www.facebook.com/messaging/unsend_message/"


def _build_request(messageID: str, dataFB: dict[str, Any]) -> dict[str, Any]:
    if not str(messageID).strip():
        raise ValueError("messageID không được để trống.")
    data_form = formAll(dataFB, requireGraphql=False)
    data_form["message_id"] = str(messageID)
    return mainRequests(_URL, data_form, dataFB["cookieFacebook"])


def _parse_response(text: str) -> dict[str, Any]:
    try:
        payload = parse_json_response(text, strip_for_loop_prefix=True)
    except (ValueError, TypeError) as error:
        return {"error": 1, "messages": f"Phản hồi thu hồi không hợp lệ: {error}"}
    if payload.get("error"):
        return {
            "error": 1,
            "messages": payload.get("errorDescription")
            or f"Facebook từ chối thu hồi tin nhắn: {payload['error']}",
        }
    return {"success": 1, "messages": "Thu hồi tin nhắn thành công."}



async def func(
    messageID: str,
    dataFB: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    response = await send_request_async(
        _build_request(messageID, dataFB), client=client
    )
    response.raise_for_status()
    return _parse_response(response.text)
