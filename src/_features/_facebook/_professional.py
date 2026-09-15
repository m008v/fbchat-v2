"""
Đường dẫn file:
  src/_features/_facebook/_professional.py

Mục đích:
  - Bật/tắt chế độ chuyên nghiệp (Professional Mode).

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


def _normalize_status(value: bool | str | None) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().casefold()
    if normalized in {"on", "bật", "true", "1"}:
        return True
    if normalized in {"off", "tắt", "false", "0"}:
        return False
    raise ValueError("statusBusiness chỉ nhận on/off, bật/tắt hoặc bool.")


def _build_request(dataFB: dict[str, Any], enabled: bool) -> dict[str, Any]:
    if enabled:
        doc_id = "6580386111988379"
        friendly_name = "CometProfilePlusOnboardingDialogTransitionMutation"
        variables = {"category_id": random.randrange(1738263827237839), "surface": None}
    else:
        doc_id = "4947853815250139"
        friendly_name = "CometProfilePlusRollbackMutation"
        variables = {}
    data_form = formAll(dataFB, friendly_name, doc_id)
    data_form["variables"] = json.dumps(variables, separators=(",", ":"))
    return data_form


def _parse_response(payload: dict[str, Any], enabled: bool) -> dict[str, Any]:
    action = "Bật" if enabled else "Tắt"
    errors = payload.get("errors") or []
    message = (
        errors[0].get("message")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict)
        else None
    )
    if errors:
        return {
            "error": 1,
            "messages": message or "Facebook từ chối thay đổi chế độ chuyên nghiệp.",
        }

    data = payload.get("data")
    if isinstance(data, dict):
        # Persisted-doc revisions có thể đổi hậu tố root; chỉ chấp nhận đúng họ
        # profile_plus/professional và một node xác nhận không rỗng.
        for node_name, node in data.items():
            normalized_name = str(node_name).casefold()
            expected_name = (
                "profile_plus" in normalized_name or "professional" in normalized_name
            )
            if expected_name and _is_confirmed_node(node):
                return {
                    "success": 1,
                    "messages": f"{action} trang cá nhân chuyên nghiệp thành công!",
                }

    return {
        "error": 1,
        "messages": "Facebook không xác nhận thay đổi chế độ chuyên nghiệp.",
    }


def _is_confirmed_node(value: Any) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    for field in ("success", "status"):
        if field in value and not _is_success_value(value[field]):
            return False
    for field in ("error", "error_message"):
        if field in value and _is_nonempty(value[field]):
            return False
    return any(
        field not in {"__typename", "client_mutation_id", "error", "error_message"}
        and _is_nonempty(field_value)
        for field, field_value in value.items()
    )


def _is_nonempty(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (dict, list, tuple, set, str)):
        return bool(value)
    return value != 0


def _is_success_value(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in {
            "",
            "0",
            "error",
            "failed",
            "failure",
            "false",
        }
    return value != 0


async def func(
    dataFB: dict[str, Any],
    statusBusiness: bool | str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        enabled = _normalize_status(statusBusiness)
        payload = await post_form_json_async(
            GRAPHQL_URL,
            _build_request(dataFB, enabled),
            dataFB["cookieFacebook"],
            client=client,
        )
        return _parse_response(payload, enabled)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}
