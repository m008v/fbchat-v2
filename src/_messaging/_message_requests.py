"""
Đường dẫn file:
  src/_messaging/_message_requests.py

Mục đích:
  - Đọc và duyệt các tin nhắn chờ (message requests).

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

from _core._utils import formAll, mainRequests, send_request_async

_URL = "https://www.facebook.com/api/graphqlbatch/"


def _build_request(dataFB: dict[str, Any]) -> dict[str, Any]:
    data_form = formAll(dataFB, requireGraphql=False)
    data_form["queries"] = json.dumps(
        {
            "o0": {
                "doc_id": "3336396659757871",
                "query_params": {
                    "limit": 100,
                    "before": None,
                    "tags": ["PENDING"],
                    "includeDeliveryReceipts": False,
                    "includeSeqID": True,
                },
            }
        },
        separators=(",", ":"),
    )
    return mainRequests(_URL, data_form, dataFB["cookieFacebook"])


def _find_batch_root(text: str) -> dict[str, Any] | None:
    payload = text.strip()
    if payload.startswith("for (;;);"):
        payload = payload[len("for (;;);") :].lstrip()
    decoder = json.JSONDecoder()
    index = 0
    while index < len(payload):
        while index < len(payload) and payload[index].isspace():
            index += 1
        if index >= len(payload):
            break
        try:
            item, index = decoder.raw_decode(payload, index)
        except json.JSONDecodeError:
            return None
        if isinstance(item, dict) and "o0" in item:
            return item
    return None


def _parse_response(text: str) -> dict[str, Any]:
    root = _find_batch_root(text)
    if root is None:
        return {"error": 1, "messages": "Không thể đọc phản hồi message requests."}

    errors = (root.get("o0") or {}).get("errors") or []
    if errors:
        message = errors[0].get("summary") if isinstance(errors[0], dict) else None
        return {"error": 1, "messages": message or "Facebook trả lỗi message requests."}

    pending = (
        (root.get("o0") or {})
        .get("data", {})
        .get("viewer", {})
        .get("message_threads", {})
        .get("nodes", [])
    )
    exported: dict[str | int, Any] = {"data": {}}
    total = 0
    for thread in pending:
        messages = (thread.get("last_message") or {}).get("nodes") or []
        if not messages or not isinstance(messages[0], dict):
            continue
        message = messages[0]
        actor = (message.get("message_sender") or {}).get("messaging_actor") or {}
        exported[total] = {
            "senderID": actor.get("id"),
            "snippet": message.get("snippet"),
            "timestamp_precise": message.get("timestamp_precise"),
        }
        total += 1
    exported["total_count"] = total
    return {
        "success": 1,
        "messages": "Lấy danh sách message requests thành công.",
        "data": exported,
    }



async def func(
    dataFB: dict[str, Any], *, client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    response = await send_request_async(_build_request(dataFB), client=client)
    response.raise_for_status()
    return _parse_response(response.text)
