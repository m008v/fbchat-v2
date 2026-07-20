"""
Đường dẫn file:
  src/_core/_session.py

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

import httpx
from typing import Any

from _core._utils import (
    parse_cookie_string,
    dataSplit,
    send_get_request,
    send_get_request_async,
)
from _core._storage import SessionStorage

REQUIRED_SESSION_FIELDS: tuple[str, ...] = (
    "fb_dtsg",
    "jazoest",
    "sessionID",
    "FacebookID",
    "clientRevision",
)


def _has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _build_home_request(setCookies: str) -> dict[str, Any]:
    return {
        "headers": {
            "authority": "www.facebook.com",
            "method": "GET",
            "path": "/",
            "scheme": "https",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5",
            "cache-control": "max-age=0",
            "cookie": setCookies,
            "dpr": "1.25",
            "priority": "u=0, i",
            "sec-ch-prefers-color-scheme": "dark",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-full-version-list": '"Chromium";v="140.0.7339.128", "Not=A?Brand";v="24.0.0.0", "Google Chrome";v="140.0.7339.128"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-platform-version": '"19.0.0"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "viewport-width": "493",
        },
        "timeout": 30,
        "url": "https://www.facebook.com/",
        "cookies": parse_cookie_string(setCookies),
        "verify": True,
    }


_SPLIT_DATA_LIST: list[list[str]] = [
    # FORMAT: nameValue, stringData_1, stringData_2
    ["fb_dtsg", 'DTSGInitialData",[],{"token":"', '"'],
    ["fb_dtsg_ag", 'async_get_token":"', '"'],
    ["jazoest", "jazoest=", '"'],
    ["hash", 'hash":"', '"'],
    ["sessionID", 'sessionId":"', '"'],
    ["FacebookID", '"actorID":"', '"'],
    ["clientRevision", 'client_revision":', ","],
]


def _parse_home_response(html: str, setCookies: str) -> dict[str, Any] | None:
    """Parse HTML response từ Facebook homepage, trích xuất session tokens."""
    dictValueSaved: dict[str, Any] = {}
    for i in _SPLIT_DATA_LIST:
        nameValue = i[0]
        try:
            exportValue = dataSplit(i[1], i[2], HTML=html, defaultValue=True)
        except (IndexError, AttributeError, TypeError):
            exportValue = None
        dictValueSaved[nameValue] = exportValue
    dictValueSaved["cookieFacebook"] = setCookies

    missing = [
        field
        for field in REQUIRED_SESSION_FIELDS
        if not _has_value(dictValueSaved.get(field))
    ]
    facebook_id = str(dictValueSaved.get("FacebookID") or "").strip()
    if facebook_id and not facebook_id.isdigit():
        missing.append("FacebookID")

    if missing:
        missing_fields = ", ".join(dict.fromkeys(missing))
        print(f"[session] Thiếu hoặc sai token bắt buộc: {missing_fields}")
        return None

    return dictValueSaved


def _resolve_cookies(
    setCookies: str | None, storage: SessionStorage | None
) -> str | None:
    """Lấy cookie string từ tham số hoặc storage."""
    if setCookies is None and storage is not None:
        setCookies = storage.load()
    return setCookies


def _dataGetHome_blocking(
    setCookies: str | None = None, storage: SessionStorage | None = None
) -> dict[str, Any] | None:
    setCookies = _resolve_cookies(setCookies, storage)
    if not setCookies:
        print("[session] Không có cookie để khởi tạo session.")
        return None

    try:
        response = send_get_request(_build_home_request(setCookies))
        response.raise_for_status()
    except httpx.RequestError as err:
        print(f"[session] Không thể lấy homepage Facebook: {err}")
        return None
    except httpx.HTTPStatusError as err:
        print(f"[session] Lỗi HTTP khi lấy homepage: {err}")
        return None

    return _parse_home_response(response.text, setCookies)


async def dataGetHome(
    setCookies: str | None = None, storage: SessionStorage | None = None
) -> dict[str, Any] | None:
    """Async version của dataGetHome — dùng cho async context."""
    setCookies = _resolve_cookies(setCookies, storage)
    if not setCookies:
        print("[session] Không có cookie để khởi tạo session.")
        return None

    try:
        response = await send_get_request_async(_build_home_request(setCookies))
        response.raise_for_status()
    except httpx.RequestError as err:
        print(f"[session] Không thể lấy homepage Facebook: {err}")
        return None
    except httpx.HTTPStatusError as err:
        print(f"[session] Lỗi HTTP khi lấy homepage: {err}")
        return None

    return _parse_home_response(response.text, setCookies)
