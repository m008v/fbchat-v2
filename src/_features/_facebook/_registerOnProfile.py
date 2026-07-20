"""
Đường dẫn file:
  src/_features/_facebook/_registerOnProfile.py

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
import random
from typing import Any

import httpx

from _core._utils import formAll, post_form_json_async

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"


def _build_request(
    dataFB: dict[str, Any], newName: str, newUsername: str
) -> dict[str, Any]:
    data_form = formAll(dataFB, "AdditionalProfileCreateMutation", 4699419010168408)
    data_form["variables"] = json.dumps(
        {
            "input": {
                "name": str(newName),
                "source": "PROFILE_SWITCHER",
                "user_name": str(newUsername),
                "actor_id": dataFB["FacebookID"],
                "client_mutation_id": str(random.randrange(1025)),
            }
        },
        separators=(",", ":"),
    )
    return data_form


def _parse_response(payload: dict[str, Any]) -> dict[str, Any]:
    result = (payload.get("data") or {}).get("additional_profile_create") or {}
    if result.get("error_message"):
        return {"error": 1, "messages": result["error_message"]}
    if payload.get("data"):
        return {"success": 1, "messages": "Tạo trang cá nhân bổ sung thành công!"}
    message = ((payload.get("errors") or [{}])[0]).get("message")
    return {"error": 1, "messages": message or "Tạo trang cá nhân bổ sung thất bại."}



async def func(
    dataFB: dict[str, Any],
    newName: str,
    newUsername: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        payload = await post_form_json_async(
            GRAPHQL_URL,
            _build_request(dataFB, newName, newUsername),
            dataFB["cookieFacebook"],
            client=client,
        )
        return _parse_response(payload)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}
