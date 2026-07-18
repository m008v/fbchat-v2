from __future__ import annotations

from typing import Any

import httpx

from _core._utils import formAll, post_form_json, post_form_json_async

USER_INFO_URL = "https://www.facebook.com/chat/user_info/"


def _build_request(dataFB: dict[str, Any], userID: str | int) -> dict[str, Any]:
    data_form = formAll(dataFB, requireGraphql=False)
    data_form["ids[0]"] = str(userID)
    return data_form


def _parse_response(payload: dict[str, Any], userID: str | int) -> dict[str, Any]:
    profiles = (payload.get("payload") or {}).get("profiles") or {}
    profile = profiles.get(str(userID))
    if not isinstance(profile, dict):
        return {
            "error": 1,
            "messages": "Không tìm thấy hồ sơ người dùng trong response.",
        }

    gender = profile.get("gender")
    gender_label = {1: "Female (Nữ)", 2: "Male (Nam)"}.get(
        gender, "Unknown (Không xác định)"
    )
    return {
        "idUser": profile.get("id"),
        "nameUser": profile.get("name"),
        "firstName": profile.get("firstName"),
        "Username": profile.get("vanity"),
        "thumbSrc": profile.get("thumbSrc")
        or profile.get("thumb_src")
        or profile.get("thumnSrc"),
        "urlProfile": profile.get("uri"),
        "genderUser": gender_label,
        "alternateName": profile.get("alternateName"),
        "chatWithUSerIsNonFriend": profile.get("is_nonfriend_messenger_contact"),
    }


def _func_blocking(dataFB: dict[str, Any], userID: str | int) -> dict[str, Any]:
    try:
        payload = post_form_json(
            USER_INFO_URL,
            _build_request(dataFB, userID),
            dataFB["cookieFacebook"],
            strip_for_loop_prefix=True,
        )
        return _parse_response(payload, userID)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}


async def func(
    dataFB: dict[str, Any],
    userID: str | int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        payload = await post_form_json_async(
            USER_INFO_URL,
            _build_request(dataFB, userID),
            dataFB["cookieFacebook"],
            strip_for_loop_prefix=True,
            client=client,
        )
        return _parse_response(payload, userID)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}

# Backwards-compatible aliases for the old `_async` API.
func_async = func
