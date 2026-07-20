"""
Đường dẫn file:
  src/_features/_facebook/_deletePost.py

Mục đích:
  - Xoá bài viết trên dòng thời gian bằng cách đưa vào thùng rác.

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

import json
import base64
from typing import Any

import httpx

from _core._utils import formAll, post_form_json_async

_URL = "https://www.facebook.com/api/graphql/"
_DOC_ID = 26146132388368957


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
    data_form = formAll(dataFB, "useCometTrashPostMutation", _DOC_ID)
    data_form["variables"] = json.dumps(
        {
            "input": {
                "story_id": PostID_Base64,
                "story_location": "TIMELINE",
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
        status = payload["data"]["move_to_trash_story"]["success"]
    except (KeyError, TypeError):
        errors = payload.get("errors") or []
        message = (
            errors[0].get("message") if errors and isinstance(errors[0], dict) else None
        )
        return {
            "error": 1,
            "messages": message or "Facebook không phản hồi hợp lệ.",
        }
    return {"success": 1, "messages": "Xóa bài viết thành công!"}


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

