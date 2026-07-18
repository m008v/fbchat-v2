from __future__ import annotations

import json
import random
from typing import Any

import httpx

from _core._utils import formAll, post_form_json_async

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"


def _build_request(
    dataFB: dict[str, Any], newContents: str, uploadPost: bool
) -> dict[str, Any]:
    data_form = formAll(dataFB, "ProfileCometSetBioMutation", 6293552847364844)
    data_form["variables"] = json.dumps(
        {
            "input": {
                "bio": str(newContents),
                "publish_bio_feed_story": bool(uploadPost),
                "actor_id": dataFB["FacebookID"],
                "client_mutation_id": str(random.randrange(1025)),
            },
            "hasProfileTileViewID": False,
            "profileTileViewID": None,
            "scale": 1,
        },
        separators=(",", ":"),
    )
    return data_form


def _parse_response(payload: dict[str, Any], new_contents: str) -> dict[str, Any]:
    bio = (
        ((payload.get("data") or {}).get("profile_intro_card_set") or {}).get(
            "profile_intro_card"
        )
        or {}
    ).get("bio") or {}
    if bio.get("text") == str(new_contents):
        return {"success": 1, "messages": "Thay đổi bio thành công!"}
    message = ((payload.get("errors") or [{}])[0]).get("message")
    return {
        "error": 1,
        "messages": message or "Facebook không xác nhận nội dung bio mới.",
    }



async def func(
    dataFB: dict[str, Any],
    newContents: str,
    uploadPost: bool = False,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        payload = await post_form_json_async(
            GRAPHQL_URL,
            _build_request(dataFB, newContents, uploadPost),
            dataFB["cookieFacebook"],
            client=client,
        )
        return _parse_response(payload, newContents)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}

# Backwards-compatible aliases for the old `_async` API.
func_async = func
