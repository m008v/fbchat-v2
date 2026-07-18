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

# Backwards-compatible aliases for the old `_async` API.
func_async = func
