"""
Đường dẫn file:
  src/_features/_facebook/_blocking.py

Mục đích:
  - Cung cấp module cho thư viện fbchat-v2 (phiên bản async).
  - Comment đầu file giúp developer dễ dàng theo dõi vị trí, luồng xử lý và dữ liệu của tính năng.

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
import random
from typing import Any

import httpx

from _core._utils import formAll, post_form_json_async

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"


def _build_request(
    dataFB: dict[str, Any], idUser: str | int, choiceInteract: str
) -> tuple[dict[str, Any], str]:
    choice = str(choiceInteract).strip().lower()
    if choice == "block":
        friendly_name = "ProfileCometActionBlockUserMutation"
        doc_id = "6305880099497989"
        variables = {
            "collectionID": None,
            "hasCollectionAndSectionID": False,
            "input": {
                "blocksource": "PROFILE",
                "should_apply_to_later_created_profiles": False,
                "user_id": int(idUser),
                "actor_id": dataFB["FacebookID"],
                "client_mutation_id": str(random.randrange(1025)),
            },
            "scale": 3,
            "sectionID": None,
            "isPrivacyCheckupContext": False,
        }
    elif choice == "unblock":
        friendly_name = "BlockingSettingsBlockMutation"
        doc_id = "6009824239038988"
        variables = {
            "input": {
                "block_action": "UNBLOCK",
                "setting": "USER",
                "target_id": str(idUser),
                "actor_id": dataFB["FacebookID"],
                "client_mutation_id": "1",
            },
            "profile_picture_size": 36,
        }
    else:
        raise ValueError("choiceInteract chỉ nhận 'block' hoặc 'unblock'.")

    data_form = formAll(dataFB, friendly_name, doc_id)
    data_form["variables"] = json.dumps(variables, separators=(",", ":"))
    return data_form, choice


def _parse_response(payload: dict[str, Any], choice: str) -> dict[str, Any]:
    label = "Chặn" if choice == "block" else "Bỏ chặn"
    if payload.get("data"):
        return {"success": 1, "messages": f"{label} người dùng thành công!"}
    message = ((payload.get("errors") or [{}])[0]).get("message")
    return {"error": 1, "messages": message or f"{label} người dùng thất bại!"}



async def func(
    dataFB: dict[str, Any],
    idUser: str | int,
    choiceInteract: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    try:
        data_form, choice = _build_request(dataFB, idUser, choiceInteract)
        payload = await post_form_json_async(
            GRAPHQL_URL,
            data_form,
            dataFB["cookieFacebook"],
            client=client,
        )
        return _parse_response(payload, choice)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return {"error": 1, "messages": str(exc)}
