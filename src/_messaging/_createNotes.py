"""
Đường dẫn file:
  src/_messaging/_createNotes.py

Mục đích:
  - Tạo hoặc cập nhật ghi chú (notes) trên Messenger.

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

import httpx
import json
from typing import Any
from _core._utils import (
    formAll,
    mainRequests,
    generate_client_id,
    send_request,
    send_request_async,
)

# =====================================================================
# Messenger Notes (the temporary status-like notes shown in Messenger)
# Converted from ws3-fca/src/deltas/apis/messaging/notes.js
# =====================================================================

PRIVACY_ALIASES = {
    "EVERYONE": "FRIENDS",  # Messenger Notes hiện trả/nhận visibility FRIENDS
    "PUBLIC": "FRIENDS",
}
GRAPHQL_TIMEOUT = 45
GRAPHQL_RETRIES = 2
GRAPHQL_MUTATION_RETRIES = 0


def _normalize_privacy(privacy: str | None) -> str:
    return PRIVACY_ALIASES.get(
        str(privacy or "FRIENDS").upper(), str(privacy or "FRIENDS").upper()
    )


def _error_response(resData: dict[str, Any]) -> dict[str, Any]:
    errors = resData.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        error = errors[0]
    elif isinstance(errors, dict):
        error = errors
    else:
        error = {}
    return {
        "error": 1,
        "messages": error.get("message") or "Facebook trả về lỗi GraphQL không hợp lệ.",
        "details": error,
    }


def _request_error(
    message: str,
    exc: Exception | None = None,
    friendly_name: str | None = None,
    doc_id: int | str | None = None,
) -> dict[str, Any]:
    error = {
        "message": message,
        "friendly_name": friendly_name,
        "doc_id": str(doc_id) if doc_id is not None else None,
    }
    if exc is not None:
        error["exception"] = str(exc)
    return {"errors": [error]}


def _build_graphql_request(
    dataFB: dict[str, Any], friendly_name: str, doc_id: int, variables: dict[str, Any]
) -> dict[str, Any]:
    """Chuẩn bị request args cho GraphQL call."""
    dataForm = formAll(dataFB, friendly_name, doc_id)
    dataForm["variables"] = json.dumps(variables)
    request_args = mainRequests(
        "https://www.facebook.com/api/graphql/",
        dataForm,
        dataFB["cookieFacebook"],
    )
    request_args["timeout"] = GRAPHQL_TIMEOUT
    return request_args


def _parse_graphql_text(text: str) -> dict[str, Any]:
    if text.startswith("for (;;);"):
        text = text.split("for (;;);", 1)[1]
    try:
        return json.loads(text)
    except (ValueError, json.JSONDecodeError):
        return {"errors": [{"message": "Invalid JSON response", "raw": text[:300]}]}


def _missing_mutation_response(
    message: str, response: dict[str, Any]
) -> dict[str, Any]:
    return {"error": 1, "messages": message, "raw": response}


def _parse_create_response(
    response: dict[str, Any], success_message: str, *, return_full_data: bool
) -> dict[str, Any]:
    if response.get("errors"):
        return _error_response(response)

    data = response.get("data")
    node = data.get("xfb_rich_status_create") if isinstance(data, dict) else None
    status = node.get("status") if isinstance(node, dict) else None
    if not _is_nonempty_mutation_node(status):
        return _missing_mutation_response(
            "Facebook không trả về trạng thái tạo note hợp lệ.", response
        )
    return {
        "success": 1,
        "messages": success_message,
        "data": data if return_full_data else status,
    }


def _parse_delete_response(
    response: dict[str, Any], success_message: str, *, return_full_data: bool
) -> dict[str, Any]:
    if response.get("errors"):
        return _error_response(response)

    data = response.get("data")
    node = data.get("xfb_rich_status_delete") if isinstance(data, dict) else None
    if not _is_nonempty_mutation_node(node):
        return _missing_mutation_response(
            "Facebook không trả về trạng thái xoá note hợp lệ.", response
        )
    return {
        "success": 1,
        "messages": success_message,
        "data": data if return_full_data else node,
    }


def _is_nonempty_mutation_node(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, dict):
        if not value:
            return False
        for field in ("success", "status"):
            if field in value and not _is_nonempty_mutation_node(value[field]):
                return False
        for field in ("error", "error_message"):
            if field in value and _is_nonempty_mutation_node(value[field]):
                return False
        return any(
            field not in {"__typename", "client_mutation_id", "error", "error_message"}
            and _is_nonempty_mutation_node(field_value)
            for field, field_value in value.items()
        )
    if isinstance(value, str):
        return value.strip().casefold() not in {
            "",
            "0",
            "error",
            "failed",
            "failure",
            "false",
        }
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return value != 0


def _post_graphql(
    dataFB: dict[str, Any],
    friendly_name: str,
    doc_id: int,
    variables: dict[str, Any],
    timeout: int = GRAPHQL_TIMEOUT,
    retries: int = GRAPHQL_RETRIES,
) -> dict[str, Any]:
    """Gửi 1 GraphQL request và trả về JSON đã parse."""
    request_args = _build_graphql_request(dataFB, friendly_name, doc_id, variables)
    request_args["timeout"] = timeout

    last_error: httpx.HTTPError | None = None
    for attempt in range(retries + 1):
        try:
            response = send_request(request_args)
            response.raise_for_status()
            return _parse_graphql_text(response.text)
        except httpx.TimeoutException as e:
            last_error = e
            if attempt < retries:
                continue
            return _request_error(
                f"Facebook GraphQL request timed out after {timeout} seconds.",
                e,
                friendly_name,
                doc_id,
            )
        except httpx.HTTPError as e:
            last_error = e
            if attempt < retries:
                continue
            return _request_error(
                "Facebook GraphQL request failed.", e, friendly_name, doc_id
            )

    return _request_error(
        "Facebook GraphQL request failed after retry.",
        last_error,
        friendly_name,
        doc_id,
    )


async def _post_graphql_async(
    dataFB: dict[str, Any],
    friendly_name: str,
    doc_id: int,
    variables: dict[str, Any],
    timeout: int = GRAPHQL_TIMEOUT,
    retries: int = GRAPHQL_RETRIES,
) -> dict[str, Any]:
    """Async version của _post_graphql."""
    request_args = _build_graphql_request(dataFB, friendly_name, doc_id, variables)
    request_args["timeout"] = timeout

    last_error: httpx.HTTPError | None = None
    for attempt in range(retries + 1):
        try:
            response = await send_request_async(request_args)
            response.raise_for_status()
            return _parse_graphql_text(response.text)
        except httpx.TimeoutException as e:
            last_error = e
            if attempt < retries:
                continue
            return _request_error(
                f"Facebook GraphQL request timed out after {timeout} seconds.",
                e,
                friendly_name,
                doc_id,
            )
        except httpx.HTTPError as e:
            last_error = e
            if attempt < retries:
                continue
            return _request_error(
                "Facebook GraphQL request failed.", e, friendly_name, doc_id
            )

    return _request_error(
        "Facebook GraphQL request failed after retry.",
        last_error,
        friendly_name,
        doc_id,
    )


# ---------------------------------------------------------------------
# CHECK
# ---------------------------------------------------------------------
def _checkNote_blocking(dataFB: dict[str, Any]) -> dict[str, Any]:
    """Kiểm tra note hiện tại của tài khoản đang đăng nhập."""
    variables = {"scale": 2}
    resData = _post_graphql(
        dataFB,
        "MWInboxTrayNoteCreationDialogQuery",
        30899655739648624,
        variables,
    )

    if resData.get("errors"):
        return _error_response(resData)

    try:
        currentNote = resData["data"]["viewer"]["actor"]["msgr_user_rich_status"]
    except (KeyError, TypeError):
        currentNote = None

    return {
        "success": 1,
        "messages": "Lấy note hiện tại thành công.",
        "data": currentNote,
    }


# ---------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------
def _createNote_blocking(
    dataFB: dict[str, Any], text: str, privacy: str = "FRIENDS"
) -> dict[str, Any]:
    """Tạo một note mới (mặc định tồn tại 24 giờ)."""
    variables = {
        "input": {
            "client_mutation_id": generate_client_id(),
            "actor_id": str(dataFB["FacebookID"]),
            "description": text,
            "duration": 86400,  # 24 giờ
            "note_type": "TEXT_NOTE",
            "privacy": _normalize_privacy(privacy),
            "session_id": generate_client_id(),
        }
    }
    resData = _post_graphql(
        dataFB,
        "MWInboxTrayNoteCreationDialogCreationStepContentMutation",
        24060573783603122,
        variables,
        retries=GRAPHQL_MUTATION_RETRIES,
    )
    return _parse_create_response(
        resData, "Tạo note thành công.", return_full_data=False
    )


# ---------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------
def _deleteNote_blocking(
    dataFB: dict[str, Any],
    noteID: str,
) -> dict[str, Any]:
    """Xoá note theo ID."""
    variables = {
        "input": {
            "client_mutation_id": generate_client_id(),
            "actor_id": str(dataFB["FacebookID"]),
            "rich_status_id": str(noteID),
        }
    }
    resData = _post_graphql(
        dataFB,
        "useMWInboxTrayDeleteNoteMutation",
        9532619970198958,
        variables,
        retries=GRAPHQL_MUTATION_RETRIES,
    )
    return _parse_delete_response(
        resData, "Xoá note thành công.", return_full_data=False
    )


# ---------------------------------------------------------------------
# RECREATE (delete + create)
# ---------------------------------------------------------------------
def re_createNote_blocking(
    dataFB: dict[str, Any], oldNoteID: str, newText: str, privacy: str = "FRIENDS"
) -> dict[str, Any]:
    """Xoá note cũ rồi tạo note mới."""
    deleted = _deleteNote_blocking(dataFB, oldNoteID)
    if deleted.get("error"):
        return deleted

    created = _createNote_blocking(dataFB, newText, privacy=privacy)
    if created.get("error"):
        return created

    return {
        "success": 1,
        "messages": "Tạo lại note thành công.",
        "data": {
            "deleted": deleted.get("data"),
            "created": created.get("data"),
        },
    }


# ---------------------------------------------------------------------
# Default entry point (theo style fbchat-v2): func(dataFB, action, ...)
# ---------------------------------------------------------------------


async def checkNote(dataFB: dict[str, Any]) -> dict[str, Any]:
    variables = {"scale": 2}
    resData = await _post_graphql_async(
        dataFB,
        "MWInboxTrayNoteCreationDialogQuery",
        30899655739648624,
        variables,
    )

    if resData.get("errors"):
        return _error_response(resData)

    try:
        has_note = resData["data"]["viewer"]["notes_management_info"]["has_notes"]
    except (KeyError, TypeError):
        has_note = False

    return {
        "success": 1,
        "messages": "Kiểm tra note hiện tại thành công.",
        "data": {"has_notes": has_note},
    }


async def createNote(
    dataFB: dict[str, Any], text: str, privacy: str = "FRIENDS"
) -> dict[str, Any]:
    if not text:
        return {"error": 1, "messages": "Text cannot be empty."}

    variables = {
        "input": {
            "client_mutation_id": generate_client_id(),
            "actor_id": str(dataFB["FacebookID"]),
            "text": str(text),
            "duration": 86400,
            "note_type": "TEXT_NOTE",
            "privacy": _normalize_privacy(privacy),
            "session_id": generate_client_id(),
        }
    }
    resData = await _post_graphql_async(
        dataFB,
        "MWInboxTrayNoteCreationDialogCreationStepContentMutation",
        24060573783603122,
        variables,
        retries=GRAPHQL_MUTATION_RETRIES,
    )
    return _parse_create_response(
        resData, "Tạo note mới thành công.", return_full_data=True
    )


async def deleteNote(dataFB: dict[str, Any], noteID: str) -> dict[str, Any]:
    if not noteID:
        return {"error": 1, "messages": "noteID cannot be empty."}

    variables = {
        "input": {
            "client_mutation_id": generate_client_id(),
            "actor_id": str(dataFB["FacebookID"]),
            "rich_status_id": str(noteID),
        }
    }
    resData = await _post_graphql_async(
        dataFB,
        "useMWInboxTrayDeleteNoteMutation",
        9532619970198958,
        variables,
        retries=GRAPHQL_MUTATION_RETRIES,
    )
    return _parse_delete_response(
        resData, "Xoá note thành công.", return_full_data=True
    )


async def recreateNote(
    dataFB: dict[str, Any], oldNoteID: str, newText: str, privacy: str = "FRIENDS"
) -> dict[str, Any]:
    deleted = await deleteNote(dataFB, oldNoteID)
    if deleted.get("error"):
        return deleted

    created = await createNote(dataFB, newText, privacy=privacy)
    if created.get("error"):
        return created

    return {
        "success": 1,
        "messages": "Tạo lại note thành công.",
        "data": {
            "deleted": deleted.get("data"),
            "created": created.get("data"),
        },
    }


async def func(
    dataFB: dict[str, Any], action: str = "check", **kwargs: Any
) -> dict[str, Any]:
    action = (action or "check").lower()
    if action == "check":
        return await checkNote(dataFB)
    if action == "create":
        return await createNote(
            dataFB, kwargs["text"], privacy=kwargs.get("privacy", "FRIENDS")
        )
    if action == "delete":
        return await deleteNote(dataFB, kwargs["noteID"])
    if action == "recreate":
        return await recreateNote(
            dataFB,
            kwargs["oldNoteID"],
            kwargs["newText"],
            privacy=kwargs.get("privacy", "FRIENDS"),
        )
    return {"error": 1, "messages": f"Unknown action: {action}"}


""" Hướng dẫn sử dụng (Tutorial)

* Dữ liệu yêu cầu (args):

     - dataFB: lấy từ _core._session.dataGetHome(setCookies)
     - action: "check" / "create" / "delete" / "recreate"
     - text / privacy / noteID / oldNoteID / newText: tuỳ theo action

* Ví dụ:

     from _core._session import dataGetHome
     from _messaging import _createNotes

     dataFB = dataGetHome("<cookie Facebook>")
     _createNotes.checkNote(dataFB)
     _createNotes.createNote(dataFB, "Hello world", privacy="FRIENDS")
     _createNotes.deleteNote(dataFB, "<note_id>")
     _createNotes.recreateNote(dataFB, "<old_note_id>", "New note text")

* Kết quả trả về:
     - { "success": 1, "messages": "...", "data": {...} } khi thành công
     - { "error": 1, "messages": "..." } khi thất bại

* Thông tin tác giả:
     ✓ Convert from ws3-fca (notes.js by @ChoruOfficial) -> fbchat-v2 style
     ✓ Tôn trọng tác giả ❤️
"""
