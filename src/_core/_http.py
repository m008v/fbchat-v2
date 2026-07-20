"""
Đường dẫn file:
  src/_core/_http.py

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

"""HTTP transport dùng chung, ưu tiên async và vẫn giữ tương thích sync."""

from __future__ import annotations

from typing import Any

import httpx


DEFAULT_TIMEOUT = 60.0
TimeoutValue = float | httpx.Timeout | None


def _clean_kwargs(
    kwargs: dict[str, Any],
) -> tuple[str, bool, TimeoutValue, dict[str, Any]]:
    """Sao chép và chuẩn hoá kwargs mà không sửa dict của caller."""
    cleaned = dict(kwargs)
    url = str(cleaned.pop("url"))
    verify = bool(cleaned.pop("verify", True))
    timeout = cleaned.pop("timeout", DEFAULT_TIMEOUT)
    cleaned.pop("proxies", None)  # tên cũ của requests, không hợp lệ với httpx
    return url, verify, timeout, cleaned


# ── Sync ────────────────────────────────────────────────────────────────


def post_blocking(
    request_kwargs: dict[str, Any],
    *,
    client: httpx.Client | None = None,
) -> httpx.Response:
    """Gửi POST đồng bộ; cho phép tái sử dụng ``httpx.Client`` nếu cần."""
    url, verify, timeout, kwargs = _clean_kwargs(request_kwargs)
    if client is not None:
        return client.post(url, timeout=timeout, **kwargs)
    with httpx.Client(verify=verify, timeout=timeout) as owned_client:
        return owned_client.post(url, **kwargs)


def get_blocking(
    request_kwargs: dict[str, Any],
    *,
    client: httpx.Client | None = None,
) -> httpx.Response:
    """Gửi GET đồng bộ; cho phép tái sử dụng ``httpx.Client`` nếu cần."""
    url, verify, timeout, kwargs = _clean_kwargs(request_kwargs)
    if client is not None:
        return client.get(url, timeout=timeout, **kwargs)
    with httpx.Client(verify=verify, timeout=timeout) as owned_client:
        return owned_client.get(url, **kwargs)


# ── Async ───────────────────────────────────────────────────────────────


async def post_async(
    request_kwargs: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> httpx.Response:
    """Gửi POST bất đồng bộ, không chặn event loop."""
    url, verify, timeout, kwargs = _clean_kwargs(request_kwargs)
    if client is not None:
        return await client.post(url, timeout=timeout, **kwargs)
    async with httpx.AsyncClient(verify=verify, timeout=timeout) as owned_client:
        return await owned_client.post(url, **kwargs)


async def get_async(
    request_kwargs: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> httpx.Response:
    """Gửi GET bất đồng bộ, không chặn event loop."""
    url, verify, timeout, kwargs = _clean_kwargs(request_kwargs)
    if client is not None:
        return await client.get(url, timeout=timeout, **kwargs)
    async with httpx.AsyncClient(verify=verify, timeout=timeout) as owned_client:
        return await owned_client.get(url, **kwargs)
