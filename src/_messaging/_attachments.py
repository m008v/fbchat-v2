from __future__ import annotations

import json
import mimetypes
import random
from itertools import count
from pathlib import Path
from typing import Any

import httpx

from _core._utils import str_base

USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 Chrome/42.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/137 Safari/537.36",
)
_REQUEST_COUNTER = count(1)
_UPLOAD_URL = "https://upload.facebook.com/ajax/mercury/upload.php"


def _close_request_files(request: dict[str, Any]) -> None:
    for file_tuple in request.get("files", {}).values():
        if (
            isinstance(file_tuple, tuple)
            and len(file_tuple) >= 2
            and hasattr(file_tuple[1], "close")
        ):
            file_tuple[1].close()


def _build_request(
    filenames: str | list[str], dataFB: dict[str, Any]
) -> dict[str, Any]:
    paths = (
        [Path(filenames)]
        if isinstance(filenames, str)
        else [Path(f) for f in filenames]
    )
    if not paths:
        raise ValueError("Danh sách tệp upload không được để trống.")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Không tìm thấy tệp upload: {', '.join(missing)}")

    request: dict[str, Any] = {
        "url": _UPLOAD_URL,
        "headers": {
            "Referer": "https://www.facebook.com",
            "Accept": "text/html",
            "User-Agent": random.choice(USER_AGENTS),
            "Cookie": dataFB["cookieFacebook"],
        },
        "data": {
            "voice_clip": False,
            "__a": 1,
            "__req": str_base(next(_REQUEST_COUNTER), 36),
            "fb_dtsg": dataFB["fb_dtsg"],
        },
        "files": {},
    }
    try:
        for index, path in enumerate(paths):
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            request["files"][f"upload_{index}"] = (
                path.name,
                path.open("rb"),
                mime,
            )
    except OSError:
        _close_request_files(request)
        raise
    return request


def _parse_response(text: str) -> dict[str, Any] | None:
    try:
        root = json.loads(text.removeprefix("for (;;);"))
    except json.JSONDecodeError:
        return None

    if not isinstance(root, dict):
        return None

    payload = root.get("payload")
    if not isinstance(payload, dict):
        return None

    metadata = payload.get("metadata")
    if isinstance(metadata, list) and metadata:
        item = metadata[0]
    elif isinstance(metadata, dict):
        item = metadata.get("0")
    else:
        item = None
    if not isinstance(item, dict):
        return None
    return {
        "attachmentID": item.get("attachmentID"),
        "attachmentUrl": item.get("attachmentUrl"),
        "videoDuration": item.get("videoDuration"),
        "typeAttachment": item.get("typeAttachment"),
    }


def func(
    filenames: str | list[str],
    dataFB: dict[str, Any],
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    request = _build_request(filenames, dataFB)
    try:
        if client is not None:
            response = client.post(**request)
        else:
            with httpx.Client(timeout=30) as owned_client:
                response = owned_client.post(**request)
        response.raise_for_status()
        return _parse_response(response.text)
    finally:
        _close_request_files(request)


async def func_async(
    filenames: str | list[str],
    dataFB: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    request = _build_request(filenames, dataFB)
    try:
        if client is not None:
            response = await client.post(**request)
        else:
            async with httpx.AsyncClient(timeout=30) as owned_client:
                response = await owned_client.post(**request)
        response.raise_for_status()
        return _parse_response(response.text)
    finally:
        _close_request_files(request)
