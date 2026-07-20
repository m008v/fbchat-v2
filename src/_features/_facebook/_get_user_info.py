"""
Đường dẫn file:
  src/_features/_facebook/_get_user_info.py

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

from _core._utils import formAll, post_form_json_async

USER_INFO_URL = "https://www.facebook.com/chat/user_info/"


def _build_request(dataFB: dict[str, Any], userID: str | int) -> dict[str, Any]:
    data_form = formAll(dataFB, requireGraphql=False)
    data_form["ids[0]"] = str(userID)
    return data_form


def _parse_response(payload: dict[str, Any], userID: str | int) -> dict[str, Any]:
    profiles = (payload.get("payload") or {}).get("profiles") or {}
    profile = profiles.get(str(userID))
    if not isinstance(profile, dict):
        return {
            "error": 1,
            "messages": "Không tìm thấy hồ sơ người dùng trong response.",
        }

    gender = profile.get("gender")
    gender_label = {1: "Female (Nữ)", 2: "Male (Nam)"}.get(
        gender, "Unknown (Không xác định)"
    )
    return {
        "idUser": profile.get("id"),
        "nameUser": profile.get("name"),
        "firstName": profile.get("firstName"),
        "Username": profile.get("vanity"),
        "thumbSrc": profile.get("thumbSrc")
        or profile.get("thumb_src")
        or profile.get("thumnSrc"),
        "urlProfile": profile.get("uri"),
        "genderUser": gender_label,
        "alternateName": profile.get("alternateName"),
        "chatWithUSerIsNonFriend": profile.get("is_nonfriend_messenger_contact"),
    }



async def func(
    dataFB: dict[str, Any],
    userID: str | int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        payload = await post_form_json_async(
            USER_INFO_URL,
            _build_request(dataFB, userID),
            dataFB["cookieFacebook"],
            strip_for_loop_prefix=True,
            client=client,
        )
        return _parse_response(payload, userID)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}
