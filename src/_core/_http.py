"""Shared HTTP client module — async-first, sync fallback.

Tập trung hoá toàn bộ HTTP transport cho fbchat-v2.
Mọi module khác nên import từ đây thay vì tự tạo httpx client.
"""
from __future__ import annotations

import httpx
from typing import Any


_DEFAULT_TIMEOUT = 30


def _clean_kwargs(kwargs: dict[str, Any]) -> tuple[bool, float, dict[str, Any]]:
    """Tách verify/timeout/proxies ra khỏi request kwargs, trả về (verify, timeout, cleaned_kwargs)."""
    verify = kwargs.pop("verify", True)
    timeout = kwargs.pop("timeout", _DEFAULT_TIMEOUT)
    kwargs.pop("proxies", None)
    return verify, timeout, kwargs


# ── Sync ────────────────────────────────────────────────────────────────

def post_sync(url: str, *, data: Any = None, headers: dict[str, str] | None = None,
              cookies: dict[str, str] | None = None, files: Any = None,
              timeout: float = _DEFAULT_TIMEOUT, verify: bool = True) -> httpx.Response:
    """Sync POST — dùng cho backward compat hoặc context không hỗ trợ async."""
    with httpx.Client(verify=verify, timeout=timeout) as client:
        return client.post(url, data=data, headers=headers, cookies=cookies, files=files)


def get_sync(url: str, *, headers: dict[str, str] | None = None,
             cookies: dict[str, str] | None = None,
             timeout: float = _DEFAULT_TIMEOUT, verify: bool = True) -> httpx.Response:
    """Sync GET."""
    with httpx.Client(verify=verify, timeout=timeout) as client:
        return client.get(url, headers=headers, cookies=cookies)


# ── Async ───────────────────────────────────────────────────────────────

async def post_async(url: str, *, data: Any = None, headers: dict[str, str] | None = None,
                     cookies: dict[str, str] | None = None, files: Any = None,
                     timeout: float = _DEFAULT_TIMEOUT, verify: bool = True) -> httpx.Response:
    """Async POST — primary transport."""
    async with httpx.AsyncClient(verify=verify, timeout=timeout) as client:
        return await client.post(url, data=data, headers=headers, cookies=cookies, files=files)


async def get_async(url: str, *, headers: dict[str, str] | None = None,
                    cookies: dict[str, str] | None = None,
                    timeout: float = _DEFAULT_TIMEOUT, verify: bool = True) -> httpx.Response:
    """Async GET."""
    async with httpx.AsyncClient(verify=verify, timeout=timeout) as client:
        return await client.get(url, headers=headers, cookies=cookies)
