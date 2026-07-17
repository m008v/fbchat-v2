from __future__ import annotations

import json
import random
from typing import Any

import httpx

from _core._utils import formAll, post_form_json, post_form_json_async

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"


def _normalize_status(value: bool | str | None) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().casefold()
    if normalized in {"on", "bật", "true", "1"}:
        return True
    if normalized in {"off", "tắt", "false", "0"}:
        return False
    raise ValueError("statusBusiness chỉ nhận on/off, bật/tắt hoặc bool.")


def _build_request(dataFB: dict[str, Any], enabled: bool) -> dict[str, Any]:
    if enabled:
        doc_id = "6580386111988379"
        friendly_name = "CometProfilePlusOnboardingDialogTransitionMutation"
        variables = {"category_id": random.randrange(1738263827237839), "surface": None}
    else:
        doc_id = "4947853815250139"
        friendly_name = "CometProfilePlusRollbackMutation"
        variables = {}
    data_form = formAll(dataFB, friendly_name, doc_id)
    data_form["variables"] = json.dumps(variables, separators=(",", ":"))
    return data_form


def _parse_response(payload: dict[str, Any], enabled: bool) -> dict[str, Any]:
    if payload.get("data"):
        action = "Bật" if enabled else "Tắt"
        return {
            "success": 1,
            "messages": f"{action} trang cá nhân chuyên nghiệp thành công!",
        }
    message = ((payload.get("errors") or [{}])[0]).get("message")
    return {
        "error": 1,
        "messages": message or "Facebook từ chối thay đổi chế độ chuyên nghiệp.",
    }


def func(
    dataFB: dict[str, Any], statusBusiness: bool | str | None = None
) -> dict[str, Any]:
    try:
        enabled = _normalize_status(statusBusiness)
        payload = post_form_json(
            GRAPHQL_URL, _build_request(dataFB, enabled), dataFB["cookieFacebook"]
        )
        return _parse_response(payload, enabled)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}


async def func_async(
    dataFB: dict[str, Any],
    statusBusiness: bool | str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        enabled = _normalize_status(statusBusiness)
        payload = await post_form_json_async(
            GRAPHQL_URL,
            _build_request(dataFB, enabled),
            dataFB["cookieFacebook"],
            client=client,
        )
        return _parse_response(payload, enabled)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}
