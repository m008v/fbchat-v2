"""
Đường dẫn file:
  src/_features/_facebook/_notification.py

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

import json
from typing import Any

import httpx

from _core._utils import formAll, post_form_json_async

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"


def _build_request(dataFB: dict[str, Any]) -> dict[str, Any]:
    data_form = formAll(dataFB, "CometNotificationsDropdownQuery", 6770067089747450)
    data_form["variables"] = json.dumps(
        {"count": 15, "environment": "MAIN_SURFACE", "scale": 3},
        separators=(",", ":"),
    )
    return data_form


def _parse_response(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        edges = payload["data"]["viewer"]["notifications_page"]["edges"]
    except (KeyError, TypeError):
        message = ((payload.get("errors") or [{}])[0]).get("message")
        return {"error": 1, "messages": message or "Response thông báo không hợp lệ."}

    results: list[str] = []
    for edge in edges if isinstance(edges, list) else []:
        try:
            text = edge["node"]["notif"]["body"]["text"]
        except (KeyError, TypeError):
            continue
        results.append(f"{len(results) + 1}.{text}")
    return {"success": 1, "NotificationResults": results}



async def func(
    dataFB: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        payload = await post_form_json_async(
            GRAPHQL_URL,
            _build_request(dataFB),
            dataFB["cookieFacebook"],
            client=client,
        )
        return _parse_response(payload)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}
