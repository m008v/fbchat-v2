"""
Đường dẫn file:
  src/_features/_facebook/_changeBio.py

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
"""

from __future__ import annotations

import json
import random
from typing import Any

import httpx

from _core._utils import formAll, post_form_json_async

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"


def _build_request(
    dataFB: dict[str, Any], newContents: str, uploadPost: bool
) -> dict[str, Any]:
    data_form = formAll(dataFB, "ProfileCometSetBioMutation", 6293552847364844)
    data_form["variables"] = json.dumps(
        {
            "input": {
                "bio": str(newContents),
                "publish_bio_feed_story": bool(uploadPost),
                "actor_id": dataFB["FacebookID"],
                "client_mutation_id": str(random.randrange(1025)),
            },
            "hasProfileTileViewID": False,
            "profileTileViewID": None,
            "scale": 1,
        },
        separators=(",", ":"),
    )
    return data_form


def _parse_response(payload: dict[str, Any], new_contents: str) -> dict[str, Any]:
    bio = (
        ((payload.get("data") or {}).get("profile_intro_card_set") or {}).get(
            "profile_intro_card"
        )
        or {}
    ).get("bio") or {}
    if bio.get("text") == str(new_contents):
        return {"success": 1, "messages": "Thay đổi bio thành công!"}
    message = ((payload.get("errors") or [{}])[0]).get("message")
    return {
        "error": 1,
        "messages": message or "Facebook không xác nhận nội dung bio mới.",
    }



async def func(
    dataFB: dict[str, Any],
    newContents: str,
    uploadPost: bool = False,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        payload = await post_form_json_async(
            GRAPHQL_URL,
            _build_request(dataFB, newContents, uploadPost),
            dataFB["cookieFacebook"],
            client=client,
        )
        return _parse_response(payload, newContents)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}
