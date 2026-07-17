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


def post_sync(
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


def get_sync(
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
