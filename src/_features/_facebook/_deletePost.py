from __future__ import annotations

import json
import base64
from typing import Any

import httpx

from _core._utils import formAll, post_form_json_async

_URL = "https://www.facebook.com/api/graphql/"
_DOC_ID = 26146132388368957


def _build_form(
    dataFB: dict[str, Any], postID: str 
) -> dict[str, Any]:
    """
    Tạo form dữ liệu GraphQL mutation để xoá bài viết.

    Args:
        dataFB (dict[str, Any]): Dữ liệu phiên đăng nhập Facebook (chứa FacebookID, cookie, v.v.).
        postID (str): ID của bài viết cần xoá.

    Returns:
        dict[str, Any]: Payload form đã được format sẵn sàng để gửi lên Facebook.

    Raises:
        ValueError: Nếu postID trống hoặc không hợp lệ.
    """
    if not str(postID).strip():
        raise ValueError("ID bài viết không được để trống.")

    postID_Params = f"S:_I{dataFB.get('FacebookID')}:{postID}:{postID}"
    print(f"[deletePost] postID_Params: {postID_Params}")
    PostID_Base64 = base64.b64encode(postID_Params.encode()).decode()
    print(f"[deletePost] PostID_Base64: {PostID_Base64}")
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
    """
    Xử lý phản hồi từ Facebook GraphQL sau khi gửi yêu cầu xoá bài.

    Args:
        payload (dict[str, Any]): JSON response từ Facebook API.

    Returns:
        dict[str, Any]: Kết quả dạng dictionary chứa trạng thái thành công hoặc lỗi.
    """
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
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Hàm chính thực thi chức năng xoá bài viết trên Facebook (di chuyển vào thùng rác).

    Args:
        dataFB (dict[str, Any]): Dữ liệu phiên đăng nhập Facebook.
        postID (str): ID của bài viết cần xoá.
        client (httpx.AsyncClient | None, optional): Session HTTP client nếu có. Mặc định None.

    Returns:
        dict[str, Any]: Kết quả trả về chứa "success" hoặc "error".
    """
    payload = await post_form_json_async(
        _URL,
        _build_form(dataFB, postID),
        dataFB["cookieFacebook"],
        client=client,
    )
    return _parse_result(payload)

