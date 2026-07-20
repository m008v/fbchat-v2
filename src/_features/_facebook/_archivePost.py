from __future__ import annotations

import json
import base64
from typing import Any

import httpx

from _core._utils import formAll, post_form_json_async

_URL = "https://www.facebook.com/api/graphql/"
_DOC_ID = 25498450883167126


def _build_form(
    dataFB: dict[str, Any], postID: str , typePost: str = "my_post"
) -> dict[str, Any]:
    if not str(postID).strip():
        raise ValueError("ID bài viết không được để trống.")
    """
        my_post = những bài viết của chính bản thân bạn viết nên (không phải share)
        others = phần còn lại, những bài viết của người khác, hoặc bài viết share từ người khác
    """
    if typePost == "my_post":
        postID_Params = f"S:_I1054626957723036:{postID}"
    else:
        postID_Params = f"S:_I{dataFB['FacebookID']}:{postID}:{postID}"
    PostID_Base64 = base64.b64encode(postID_Params.encode()).decode()
    data_form = formAll(dataFB, "useCometArchivePostMutation", _DOC_ID)
    data_form["variables"] = json.dumps(
        {
            "input": {
                "story_id": PostID_Base64,
                "story_location": "TIMELINE",
                "surface": "POST_CHEVRON_MENU_TIMELINE",
                "actor_id": dataFB["FacebookID"],
                "client_mutation_id": "1"
            }
        },
        separators=(",", ":"),
    )
    print(data_form)
    return data_form


def _parse_result(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        status = payload["data"]["archive_story"]["success"]
    except (KeyError, TypeError):
        errors = payload.get("errors") or []
        message = (
            errors[0].get("message") if errors and isinstance(errors[0], dict) else None
        )
        return {
            "error": 1,
            "messages": message or "Facebook không phản hồi hợp lệ.",
        }
    return {"success": 1, "messages": "Lưu trữ bài viết thành công!"}


async def func(
    dataFB: dict[str, Any],
    postID: str,
    typePost: str = "my_post",
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    payload = await post_form_json_async(
        _URL,
        _build_form(dataFB, postID, typePost),
        dataFB["cookieFacebook"],
        client=client,
    )
    return _parse_result(payload)

