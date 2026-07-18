from __future__ import annotations

import json
from typing import Any

import httpx

from _core._utils import formAll, post_form_json, post_form_json_async

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"


def _build_request(dataFB: dict[str, Any]) -> dict[str, Any]:
    data_form = formAll(dataFB, "CometNotificationsDropdownQuery", 6770067089747450)
    data_form["variables"] = json.dumps(
        {"count": 15, "environment": "MAIN_SURFACE", "scale": 3},
        separators=(",", ":"),
    )
    return data_form


def _parse_response(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        edges = payload["data"]["viewer"]["notifications_page"]["edges"]
    except (KeyError, TypeError):
        message = ((payload.get("errors") or [{}])[0]).get("message")
        return {"error": 1, "messages": message or "Response thông báo không hợp lệ."}

    results: list[str] = []
    for edge in edges if isinstance(edges, list) else []:
        try:
            text = edge["node"]["notif"]["body"]["text"]
        except (KeyError, TypeError):
            continue
        results.append(f"{len(results) + 1}.{text}")
    return {"success": 1, "NotificationResults": results}


def _func_blocking(dataFB: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = post_form_json(
            GRAPHQL_URL, _build_request(dataFB), dataFB["cookieFacebook"]
        )
        return _parse_response(payload)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}


async def func(
    dataFB: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        payload = await post_form_json_async(
            GRAPHQL_URL,
            _build_request(dataFB),
            dataFB["cookieFacebook"],
            client=client,
        )
        return _parse_response(payload)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}

# Backwards-compatible aliases for the old `_async` API.
func_async = func
