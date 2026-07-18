from __future__ import annotations

import json
import time
import asyncio
from typing import Any

import httpx

from _core._utils import formAll, mainRequests, send_request, send_request_async
from _messaging._editMessage import (
    APP_ID,
    _build_ls_context,
    _error_response,
    _json,
    _publish_ls_requests,
)

THEME_LIST_FRIENDLY_NAME = "MWPThreadThemeQuery_AllThemesQuery"
THEME_LIST_DOC_ID = 24474714052117636
THEME_VERSION_ID = "24631415369801570"
GRAPHQL_TIMEOUT = 45
GRAPHQL_RETRIES = 2
_DEFAULT_TIMEOUT = 20


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


def _graphql_error_response(resData: dict[str, Any]) -> dict[str, Any]:
    error = (resData.get("errors") or [{}])[0]
    return {
        "error": 1,
        "messages": error.get("message", str(error)),
        "details": error,
    }


def _build_graphql_request(
    dataFB: dict[str, Any], friendly_name: str, doc_id: int, variables: dict[str, Any]
) -> dict[str, Any]:
    dataForm = formAll(dataFB, friendly_name, doc_id)
    dataForm["variables"] = json.dumps(
        variables, separators=(",", ":"), ensure_ascii=False
    )
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


def _post_graphql(
    dataFB: dict[str, Any],
    friendly_name: str,
    doc_id: int,
    variables: dict[str, Any],
    timeout: int = GRAPHQL_TIMEOUT,
    retries: int = GRAPHQL_RETRIES,
) -> dict[str, Any]:
    request_args = _build_graphql_request(dataFB, friendly_name, doc_id, variables)
    request_args["timeout"] = timeout

    last_error = None
    for attempt in range(retries + 1):
        try:
            response = send_request(request_args)
            response.raise_for_status()
            return _parse_graphql_text(response.text)
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < retries:
                continue
            return _request_error(
                f"Facebook GraphQL request timed out after {timeout} seconds.",
                exc,
                friendly_name,
                doc_id,
            )
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < retries:
                continue
            return _request_error(
                "Facebook GraphQL request failed.", exc, friendly_name, doc_id
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

    last_error = None
    for attempt in range(retries + 1):
        try:
            response = await send_request_async(request_args)
            response.raise_for_status()
            return _parse_graphql_text(response.text)
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < retries:
                continue
            return _request_error(
                f"Facebook GraphQL request timed out after {timeout} seconds.",
                exc,
                friendly_name,
                doc_id,
            )
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < retries:
                continue
            return _request_error(
                "Facebook GraphQL request failed.", exc, friendly_name, doc_id
            )

    return _request_error(
        "Facebook GraphQL request failed after retry.",
        last_error,
        friendly_name,
        doc_id,
    )


def _normalize_theme(themeData: dict[str, Any]) -> dict[str, Any] | None:
    if not themeData or not themeData.get("id"):
        return None
    return {
        "id": str(themeData.get("id")),
        "name": themeData.get("accessibility_label"),
        "description": themeData.get("description"),
        "appColorMode": themeData.get("app_color_mode"),
        "composerBackgroundColor": themeData.get("composer_background_color"),
        "backgroundGradientColors": themeData.get("background_gradient_colors"),
        "titleBarButtonTintColor": themeData.get("title_bar_button_tint_color"),
        "inboundMessageGradientColors": themeData.get(
            "inbound_message_gradient_colors"
        ),
        "titleBarTextColor": themeData.get("title_bar_text_color"),
        "composerTintColor": themeData.get("composer_tint_color"),
        "titleBarAttributionColor": themeData.get("title_bar_attribution_color"),
        "composerInputBackgroundColor": themeData.get(
            "composer_input_background_color"
        ),
        "hotLikeColor": themeData.get("hot_like_color"),
        "backgroundImage": (
            (themeData.get("background_asset") or {}).get("image") or {}
        ).get("uri"),
        "messageTextColor": themeData.get("message_text_color"),
        "inboundMessageTextColor": themeData.get("inbound_message_text_color"),
        "primaryButtonBackgroundColor": themeData.get(
            "primary_button_background_color"
        ),
        "titleBarBackgroundColor": themeData.get("title_bar_background_color"),
        "tertiaryTextColor": themeData.get("tertiary_text_color"),
        "reactionPillBackgroundColor": themeData.get("reaction_pill_background_color"),
        "secondaryTextColor": themeData.get("secondary_text_color"),
        "fallbackColor": themeData.get("fallback_color"),
        "gradientColors": themeData.get("gradient_colors"),
        "normalThemeId": themeData.get("normal_theme_id"),
        "iconAsset": ((themeData.get("icon_asset") or {}).get("image") or {}).get(
            "uri"
        ),
    }


def _listThemes_blocking(dataFB: dict[str, Any]) -> dict[str, Any]:
    resData = _post_graphql(
        dataFB,
        THEME_LIST_FRIENDLY_NAME,
        THEME_LIST_DOC_ID,
        {"version": "default"},
    )

    if resData.get("errors"):
        return _graphql_error_response(resData)

    try:
        rawThemes = resData["data"]["messenger_thread_themes"]
    except (KeyError, TypeError):
        return {
            "error": 1,
            "messages": "Could not retrieve thread themes from response.",
            "raw": resData,
        }

    themes = [_normalize_theme(themeData) for themeData in rawThemes]
    themes = [themeData for themeData in themes if themeData]
    return {
        "success": 1,
        "messages": "Lấy danh sách theme thành công.",
        "data": themes,
        "total_count": len(themes),
    }


def _match_theme(themes: list[dict[str, Any]], themeName: str) -> dict[str, Any] | None:
    normalized = str(themeName).strip().lower()
    if not normalized:
        return None

    if normalized.isdigit():
        matched = next(
            (theme for theme in themes if str(theme.get("id")) == normalized), None
        )
        if matched:
            return matched

    matched = next(
        (
            theme
            for theme in themes
            if str(theme.get("name") or "").lower() == normalized
        ),
        None,
    )
    if matched:
        return matched

    return next(
        (
            theme
            for theme in themes
            if normalized in str(theme.get("name") or "").lower()
        ),
        None,
    )


def _findTheme_blocking(dataFB: dict[str, Any], themeName: str) -> dict[str, Any]:
    listed = listThemes(dataFB)
    if listed.get("error"):
        return listed

    matched = _match_theme(listed.get("data", []), themeName)
    if not matched:
        return _error_response(
            f'Theme "{themeName}" not found. Use listThemes(dataFB) or func(dataFB, "list") to view available themes.',
            {"themeName": themeName},
        )

    return {
        "success": 1,
        "messages": "Tìm theme thành công.",
        "data": matched,
    }


def _theme_query(
    threadID: str,
    themeID: str,
    label: str,
    queueName: str,
    taskID: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queryPayload = {
        "thread_key": str(threadID),
        "theme_fbid": str(themeID),
        "sync_group": 1,
    }
    if payload:
        queryPayload.update(payload)

    return {
        "failure_count": None,
        "label": str(label),
        "payload": _json(queryPayload),
        "queue_name": str(queueName),
        "task_id": int(taskID),
    }


def _build_theme_contexts(threadID: str, themeID: str) -> list[dict[str, Any]]:
    tasks = [
        ("1013", "ai_generated_theme", {}),
        ("1037", "msgr_custom_thread_theme", {}),
        ("1028", "thread_theme_writer", {}),
        ("43", "thread_theme", {"source": None, "payload": None}),
    ]
    contexts = []
    for index, (label, queueName, payload) in enumerate(tasks, start=1):
        query = _theme_query(threadID, themeID, label, queueName, index, payload)
        contexts.append(
            _build_ls_context(
                [query],
                request_id=index,
                app_id=APP_ID,
                version_id=THEME_VERSION_ID,
            )
        )
    return contexts


def _changeTheme_blocking(
    dataFB: dict[str, Any],
    threadID: str,
    themeName: str,
    initiatorID: str | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    if not threadID:
        return _error_response("threadID is required.")
    if not themeName:
        return _error_response(
            "themeName is required. Use 'list' to view available themes."
        )

    if str(themeName).strip().lower() == "list":
        return _listThemes_blocking(dataFB)

    themeResult = findTheme(dataFB, themeName)
    if themeResult.get("error"):
        return themeResult

    theme = themeResult["data"]
    contexts = _build_theme_contexts(threadID, theme["id"])
    published = _publish_ls_requests(dataFB, contexts, timeout=timeout)
    if published.get("error"):
        return published

    return {
        "success": 1,
        "messages": "Gửi yêu cầu đổi theme thành công.",
        "data": {
            "type": "thread_theme_update",
            "threadID": str(threadID),
            "themeID": theme["id"],
            "themeName": theme.get("name"),
            "senderID": str(initiatorID or dataFB["FacebookID"]),
            "BotID": str(dataFB["FacebookID"]),
            "timestamp": int(time.time() * 1000),
            "published": published.get("payload"),
        },
    }



async def listThemes(dataFB: dict[str, Any]) -> dict[str, Any]:
    resData = await _post_graphql_async(
        dataFB,
        THEME_LIST_FRIENDLY_NAME,
        THEME_LIST_DOC_ID,
        {"version": "default"},
    )

    if resData.get("errors"):
        return _graphql_error_response(resData)

    try:
        rawThemes = resData["data"]["messenger_thread_themes"]
    except (KeyError, TypeError):
        return {
            "error": 1,
            "messages": "Could not retrieve thread themes from response.",
            "raw": resData,
        }

    themes = [_normalize_theme(themeData) for themeData in rawThemes]
    themes = [themeData for themeData in themes if themeData]
    return {
        "success": 1,
        "messages": "Lấy danh sách theme thành công.",
        "data": themes,
        "total_count": len(themes),
    }


async def findTheme(dataFB: dict[str, Any], themeName: str) -> dict[str, Any]:
    if not themeName:
        return _error_response("themeName cannot be empty.")

    listResult = await listThemes(dataFB)
    if listResult.get("error"):
        return listResult

    themes = listResult["data"]
    matchedTheme = _match_theme(themes, themeName)

    if not matchedTheme:
        return _error_response(f"Could not find any theme matching '{themeName}'.")

    return {
        "success": 1,
        "data": matchedTheme,
    }


async def changeTheme(
    dataFB: dict[str, Any],
    threadID: str,
    themeName: str,
    initiatorID: str | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    if not threadID:
        return _error_response("threadID is required.")
    if not themeName:
        return _error_response(
            "themeName is required. Use 'list' to view available themes."
        )

    if str(themeName).strip().lower() == "list":
        return await listThemes(dataFB)

    themeResult = await findTheme(dataFB, themeName)
    if themeResult.get("error"):
        return themeResult

    theme = themeResult["data"]
    contexts = _build_theme_contexts(threadID, theme["id"])
    published = await asyncio.to_thread(_publish_ls_requests, dataFB, contexts, timeout)
    if published.get("error"):
        return published

    return {
        "success": 1,
        "messages": "Gửi yêu cầu đổi theme thành công.",
        "data": {
            "type": "thread_theme_update",
            "threadID": str(threadID),
            "themeID": theme["id"],
            "themeName": theme.get("name"),
            "senderID": str(initiatorID or dataFB["FacebookID"]),
            "BotID": str(dataFB["FacebookID"]),
            "timestamp": int(time.time() * 1000),
            "published": published.get("payload"),
        },
    }


async def func(
    dataFB: dict[str, Any],
    threadID: str | None = None,
    themeName: str | None = None,
    action: str = "set",
    **kwargs: Any,
) -> dict[str, Any]:
    action = (action or "set").lower()
    if str(threadID or "").strip().lower() == "list" and themeName is None:
        return await listThemes(dataFB)
    if action == "list" or str(themeName or "").strip().lower() == "list":
        return await listThemes(dataFB)
    if action == "find":
        return await findTheme(dataFB, themeName)
    return await changeTheme(
        dataFB,
        threadID,
        themeName,
        initiatorID=kwargs.get("initiatorID"),
        timeout=kwargs.get("timeout", _DEFAULT_TIMEOUT),
    )


""" Hướng dẫn sử dụng (Tutorial)

* Dữ liệu yêu cầu (args):

     - dataFB: lấy từ _core._session.dataGetHome(setCookies)
     - threadID: ID nhóm / thread cần đổi nền
     - themeName: tên theme, một phần tên theme, theme id, hoặc "list"
     - initiatorID: ID người thực hiện (tuỳ chọn, mặc định là FacebookID hiện tại)

* Ví dụ:

     from _core._session import dataGetHome
     from _messaging import _changeTheme

     dataFB = dataGetHome("<cookie Facebook>")
     print(_changeTheme.listThemes(dataFB))
     print(_changeTheme.changeTheme(dataFB, "123456789", "love"))
     print(_changeTheme.func(dataFB, "123456789", "default"))
     print(_changeTheme.func(dataFB, action="list"))

* Kết quả trả về:

     - {"success": 1, "messages": "...", "data": {...}} khi thành công
     - {"error": 1, "messages": "...", "details" | "payload" | "raw": ...} khi thất bại

* Ghi chú:

     - listThemes dùng GraphQL friendly_name="MWPThreadThemeQuery_AllThemesQuery".
     - changeTheme publish 4 MQTT LS tasks: ai_generated_theme, msgr_custom_thread_theme,
       thread_theme_writer, thread_theme.
     - Success nghĩa là request đổi theme đã publish lên /ls_req; Messenger có thể vẫn từ chối
       nếu tài khoản không có quyền đổi theme trong thread đó.
"""

# Backwards-compatible aliases for the old `_async` API.
listThemes_async = listThemes
findTheme_async = findTheme
changeTheme_async = changeTheme
func_async = func
