from __future__ import annotations

import asyncio
import json
import mimetypes
import random
from itertools import count
from pathlib import Path
from typing import Any

import httpx
import requests

from _core._utils import str_base

USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 Chrome/42.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/601.1.10 Version/8.0.5 Safari/601.1.10",
    "Mozilla/5.0 (Windows NT 6.3; WOW64; ; NCT50_AAP285C84A1328) AppleWebKit/537.36 Chrome/42.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 Chrome/22.0 Safari/537.1",
    "Mozilla/5.0 (X11; CrOS i686 2268.111.0) AppleWebKit/536.11 Chrome/20.0 Safari/536.11",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.6 Chrome/20.0 Safari/536.6",
)
_UPLOAD_URL = "https://upload.facebook.com/ajax/mercury/upload.php"
_REQUEST_COUNTER = count(1)
_LEGACY_ATTACHMENT_ID_KEYS = (
    "attachmentID",
    "image_id",
    "gif_id",
    "video_id",
    "file_id",
    "audio_id",
)


def _to_send_attachment_type(mime_type: str | None) -> str:
    if not mime_type:
        return "file"
    if mime_type.lower() == "image/gif":
        return "gif"
    mime_group = mime_type.split("/", 1)[0].lower()
    if mime_group in {"image", "video", "audio"}:
        return mime_group
    return "file"


def _infer_attachment_type(item: dict[str, Any], mime_type: str | None) -> str:
    if "gif_id" in item:
        return "gif"
    if "image_id" in item:
        return "image"
    if "video_id" in item:
        return "video"
    if "audio_id" in item:
        return "audio"
    return _to_send_attachment_type(mime_type)


def _extract_attachment_id(item: dict[str, Any]) -> Any:
    for key in _LEGACY_ATTACHMENT_ID_KEYS:
        value = item.get(key)
        if value is not None:
            return value
    return None


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
        "timeout": 30,
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


def _response_excerpt(text: str, limit: int = 600) -> str:
    return " ".join(text.strip().split())[:limit]


def _parse_upload_error(root: Any, text: str) -> dict[str, Any]:
    if isinstance(root, dict):
        payload = root.get("payload") if isinstance(root.get("payload"), dict) else {}
        metadata = payload.get("metadata") if isinstance(payload, dict) else None
        metadata_items = list(metadata.values()) if isinstance(metadata, dict) else metadata
        rejected_all_files = (
            isinstance(metadata_items, list | tuple)
            and metadata_items
            and all(item is None for item in metadata_items)
        )
        return {
            "error": 1,
            "payload": {
                "error-code": root.get("error") or payload.get("error"),
                "error-summary": root.get("errorSummary")
                or payload.get("errorSummary")
                or payload.get("error-summary"),
                "error-description": root.get("errorDescription")
                or payload.get("errorDescription")
                or payload.get("error-description"),
                "upload-id": payload.get("uploadID"),
                "metadata": metadata,
                "file-rejected": rejected_all_files,
                "raw-excerpt": _response_excerpt(text),
            },
        }
    return {
        "error": 1,
        "payload": {
            "error-description": "Facebook không trả JSON object cho upload.",
            "raw-excerpt": _response_excerpt(text),
        },
    }


def _parse_response(text: str, *, include_error: bool = False) -> dict[str, Any] | None:
    try:
        root = json.loads(text.removeprefix("for (;;);"))
    except json.JSONDecodeError:
        if include_error:
            return _parse_upload_error(None, text)
        return None

    if not isinstance(root, dict):
        if include_error:
            return _parse_upload_error(root, text)
        return None

    payload = root.get("payload")
    if not isinstance(payload, dict):
        if include_error:
            return _parse_upload_error(root, text)
        return None

    metadata = payload.get("metadata")
    if isinstance(metadata, list) and metadata:
        item = metadata[0]
    elif isinstance(metadata, dict):
        item = metadata.get("0")
    else:
        item = None
    if not isinstance(item, dict):
        if include_error:
            return _parse_upload_error(root, text)
        return None
    attachment_type = (
        item.get("attachmentType")
        or item.get("typeAttachment")
        or item.get("mimeType")
        or item.get("mime_type")
    )
    attachment_id = _extract_attachment_id(item)
    values = list(item.values())
    if attachment_id is None and values:
        attachment_id = values[0]
    if attachment_type is None and len(values) > 2:
        attachment_type = values[2]
    attachment_url = item.get("attachmentUrl")
    if attachment_url is None and len(values) > 3:
        attachment_url = values[3]
    return {
        "attachmentID": attachment_id,
        "attachmentUrl": attachment_url,
        "videoDuration": item.get("videoDuration"),
        "attachmentType": attachment_type,
        "typeAttachment": _infer_attachment_type(item, attachment_type),
    }


def _upload_blocking(
    filenames: str | list[str],
    dataFB: dict[str, Any],
    *,
    client: httpx.Client | None = None,
    include_error: bool = False,
) -> dict[str, Any] | None:
    request = _build_request(filenames, dataFB)
    try:
        if client is not None:
            response = client.post(**request)
        else:
            response = requests.post(**request)
        response.raise_for_status()
        return _parse_response(response.text, include_error=include_error)
    finally:
        _close_request_files(request)


async def func(
    filenames: str | list[str],
    dataFB: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
    include_error: bool = False,
) -> dict[str, Any] | None:
    if client is None:
        return await asyncio.to_thread(
            _upload_blocking,
            filenames,
            dataFB,
            include_error=include_error,
        )

    request = _build_request(filenames, dataFB)
    try:
        response = await client.post(**request)
        response.raise_for_status()
        return _parse_response(response.text, include_error=include_error)
    finally:
        _close_request_files(request)
