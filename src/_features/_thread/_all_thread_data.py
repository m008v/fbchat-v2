from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from _core._utils import formAll, mainRequests, send_request, send_request_async

GRAPHQLBATCH_TIMEOUT = 60.0
GRAPHQLBATCH_RETRIES = 2
_URL = "https://www.facebook.com/api/graphqlbatch/"


def _parse_graphqlbatch_response(text: str) -> dict[str, Any]:
    """Đọc chuỗi nhiều JSON object mà GraphQL batch trả về."""
    payload = (text or "").strip()
    if payload.startswith("for (;;);"):
        payload = payload[len("for (;;);") :].lstrip()

    decoder = json.JSONDecoder()
    index = 0
    while index < len(payload):
        while index < len(payload) and payload[index].isspace():
            index += 1
        if index >= len(payload):
            break
        item, index = decoder.raw_decode(payload, index)
        if isinstance(item, dict) and "o0" in item:
            return item
    raise ValueError("Không tìm thấy object o0 trong phản hồi GraphQL batch.")


def _normalize_seq_id(value: Any) -> int | None:
    try:
        seq_id = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return seq_id if seq_id >= 0 else None


def _build_form(dataFB: dict[str, Any]) -> dict[str, Any]:
    data_form = formAll(dataFB, requireGraphql=False)
    data_form["queries"] = json.dumps(
        {
            "o0": {
                "doc_id": "3336396659757871",
                "query_params": {
                    "limit": 50,
                    "before": None,
                    "tags": ["INBOX"],
                    "includeDeliveryReceipts": False,
                    "includeSeqID": True,
                },
            }
        },
        separators=(",", ":"),
    )
    return data_form


def _request_args(dataFB: dict[str, Any]) -> dict[str, Any]:
    args = mainRequests(_URL, _build_form(dataFB), dataFB["cookieFacebook"])
    args["timeout"] = GRAPHQLBATCH_TIMEOUT
    return args


def _post_graphqlbatch(
    dataFB: dict[str, Any], client: httpx.Client | None = None
) -> httpx.Response:
    last_error: httpx.HTTPError | None = None
    for attempt in range(GRAPHQLBATCH_RETRIES + 1):
        try:
            response = send_request(_request_args(dataFB), client=client)
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            last_error = error
            if attempt == GRAPHQLBATCH_RETRIES:
                raise
    assert last_error is not None
    raise last_error


async def _post_graphqlbatch_async(
    dataFB: dict[str, Any], client: httpx.AsyncClient | None = None
) -> httpx.Response:
    last_error: httpx.HTTPError | None = None
    for attempt in range(GRAPHQLBATCH_RETRIES + 1):
        try:
            response = await send_request_async(_request_args(dataFB), client=client)
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            last_error = error
            if attempt == GRAPHQLBATCH_RETRIES:
                raise
            await asyncio.sleep(0)
    assert last_error is not None
    raise last_error


def _build_result(response: httpx.Response, elapsed: float) -> dict[str, Any]:
    parsed_batch = _parse_graphqlbatch_response(response.text)
    message_threads = parsed_batch["o0"]["data"]["viewer"]["message_threads"]
    last_seq_id = _normalize_seq_id(message_threads.get("sync_sequence_id"))
    if last_seq_id is None:
        raise ValueError(
            f"sync_sequence_id không hợp lệ: {message_threads.get('sync_sequence_id')}"
        )

    thread_ids: list[str] = []
    thread_names: list[str | None] = []
    for thread in message_threads.get("nodes", []):
        thread_id = thread.get("thread_key", {}).get("thread_fbid")
        if thread_id is not None:
            thread_ids.append(str(thread_id))
            thread_names.append(thread.get("name"))

    return {
        "dataGet": json.dumps(parsed_batch, ensure_ascii=False),
        "ProcessingTime": elapsed,
        "last_seq_id": last_seq_id,
        "dataAllThread": {
            "threadIDList": thread_ids,
            "threadNameList": thread_names,
            "countThread": len(thread_ids),
        },
    }


def func_sync(
    dataFB: dict[str, Any], *, client: httpx.Client | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    response = _post_graphqlbatch(dataFB, client)
    return _build_result(response, time.perf_counter() - started)


async def func(
    dataFB: dict[str, Any], *, client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    response = await _post_graphqlbatch_async(dataFB, client)
    return _build_result(response, time.perf_counter() - started)


def features_sync(dataGet: str, threadID: str | int, commandUse: str) -> Any:
    try:
        root = json.loads(dataGet)["o0"]
        get_data = root["data"]["viewer"]["message_threads"]["nodes"]
    except (KeyError, TypeError, json.JSONDecodeError):
        try:
            return json.loads(dataGet)["o0"]["errors"][0]["summary"]
        except (KeyError, TypeError, IndexError, json.JSONDecodeError):
            return "Không thể xử lý dữ liệu danh sách cuộc trò chuyện."

    data_thread = next(
        (
            thread
            for thread in get_data
            if str(thread.get("thread_key", {}).get("thread_fbid")) == str(threadID)
        ),
        None,
    )
    if data_thread is None:
        return "Không tìm thấy cuộc trò chuyện trong danh sách đã tải."

    if commandUse == "getAdmin":
        return {
            "adminThreadList": [
                str(admin["id"]) for admin in data_thread.get("thread_admins", [])
            ]
        }
    if commandUse == "threadInfomation":
        customization = data_thread.get("customization_info") or {}
        joinable = data_thread.get("joinable_mode") or {}
        return {
            "nameThread": data_thread.get("name"),
            "IDThread": threadID,
            "emojiThread": customization.get("emoji"),
            "messageCount": data_thread.get("messages_count", 0),
            "adminThreadCount": len(data_thread.get("thread_admins", [])),
            "memberCount": len(
                data_thread.get("all_participants", {}).get("edges", [])
            ),
            "approvalMode": "Bật" if data_thread.get("approval_mode") else "Tắt",
            "joinableMode": "Bật" if str(joinable.get("mode")) != "0" else "Tắt",
            "urlJoinableThread": joinable.get("link"),
        }
    if commandUse == "exportMemberListToJson":
        members: list[str] = []
        for edge in data_thread.get("all_participants", {}).get("edges", []):
            actor = edge.get("node", {}).get("messaging_actor", {})
            actor_id = str(actor.get("id", ""))
            if not actor_id:
                continue
            members.append(
                json.dumps(
                    {
                        actor_id: {
                            "nameFB": actor.get("name"),
                            "idFacebook": actor_id,
                            "profileUrl": actor.get("url"),
                            "avatarUrl": (actor.get("big_image_src") or {}).get("uri"),
                            "gender": actor.get("gender"),
                            "usernameFB": actor.get("username"),
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return members
    return {"error": f"Lệnh không được hỗ trợ: {commandUse}"}


async def features(dataGet: str, threadID: str | int, commandUse: str) -> Any:
    """API đồng nhất cho workflow async; bước này chỉ xử lý dữ liệu trong bộ nhớ."""
    return features_sync(dataGet, threadID, commandUse)

# Backwards-compatible aliases for the old `_async` API.
func_async = func
features_async = features
