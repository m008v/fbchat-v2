"""
Đường dẫn file:
  src/_features/_facebook/_registerOnProfile.py

Mục đích:
  - Đăng ký tạo hồ sơ bổ sung (Additional Profile).

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
    errors = payload.get("errors") or []
    message = (
        errors[0].get("message")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict)
        else None
    )
    if errors:
        return {
            "error": 1,
            "messages": message or "Tạo trang cá nhân bổ sung thất bại.",
        }

    data = payload.get("data")
    result = data.get("additional_profile_create") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        return {
            "error": 1,
            "messages": "Facebook không xác nhận trang cá nhân bổ sung đã được tạo.",
        }

    error_message = result.get("error_message")
    if error_message:
        return {"error": 1, "messages": str(error_message)}

    for status_field in ("success", "status"):
        if status_field in result and not _is_success_value(result[status_field]):
            return {
                "error": 1,
                "messages": "Facebook không xác nhận trang cá nhân bổ sung đã được tạo.",
            }

    evidence = {
        key: value
        for key, value in result.items()
        if key not in {"__typename", "client_mutation_id", "error_message"}
        and _is_nonempty(value)
    }
    if not evidence:
        return {
            "error": 1,
            "messages": "Facebook không xác nhận trang cá nhân bổ sung đã được tạo.",
        }
    return {"success": 1, "messages": "Tạo trang cá nhân bổ sung thành công!"}


def _is_nonempty(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (dict, list, tuple, set, str)):
        return bool(value)
    return value != 0


def _is_success_value(value: Any) -> bool:
    if not _is_nonempty(value):
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in {
            "0",
            "error",
            "failed",
            "failure",
            "false",
        }
    return True


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
