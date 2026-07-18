from __future__ import annotations

import json
import mimetypes
import random
from pathlib import Path
from typing import Any

import httpx

from _core._utils import formAll

USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 Chrome/42.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/137 Safari/537.36",
)
_UPLOAD_URL = "https://upload.facebook.com/ajax/mercury/upload.php"
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

    data_form = formAll(dataFB, requireGraphql=False)
    data_form["voice_clip"] = False

    request: dict[str, Any] = {
        "url": _UPLOAD_URL,
        "headers": {
            "Referer": "https://www.facebook.com",
            "Accept": "text/html",
            "User-Agent": random.choice(USER_AGENTS),
            "Cookie": dataFB["cookieFacebook"],
        },
        "data": data_form,
        "files": {},
    }
    try:
        for index, path in enumerate(paths):
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            field_name = "file" if len(paths) == 1 else f"upload_{index}"
            request["files"][field_name] = (
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
    return {
        "attachmentID": attachment_id,
        "attachmentUrl": item.get("attachmentUrl"),
        "videoDuration": item.get("videoDuration"),
        "attachmentType": attachment_type,
        "typeAttachment": _infer_attachment_type(item, attachment_type),
    }


def func(
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
            with httpx.Client(timeout=30) as owned_client:
                response = owned_client.post(**request)
        response.raise_for_status()
        return _parse_response(response.text, include_error=include_error)
    finally:
        _close_request_files(request)


async def func_async(
    filenames: str | list[str],
    dataFB: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
    include_error: bool = False,
) -> dict[str, Any] | None:
    request = _build_request(filenames, dataFB)
    try:
        if client is not None:
            response = await client.post(**request)
        else:
            async with httpx.AsyncClient(timeout=30) as owned_client:
                response = await owned_client.post(**request)
        response.raise_for_status()
        return _parse_response(response.text, include_error=include_error)
    finally:
        _close_request_files(request)
