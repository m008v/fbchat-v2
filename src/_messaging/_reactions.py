"""
Đường dẫn file:
  src/_messaging/_reactions.py

Mục đích:
  - Thả cảm xúc (reaction) vào tin nhắn cụ thể.

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
    Headers,
    parse_cookie_string,
    formAll,
    send_request_async,
)


def _build_request(
    dataFB: dict[str, Any], typeAdded: str, messageID: str | int, emojiChoice: str
) -> dict[str, Any]:
    normalized_action = str(typeAdded).strip().casefold()
    action_map = {
        "add": "ADD_REACTION",
        "add_reaction": "ADD_REACTION",
        "remove": "REMOVE_REACTION",
        "remove_reaction": "REMOVE_REACTION",
    }
    if normalized_action not in action_map:
        raise ValueError(
            "typeAdded chỉ nhận add/ADD_REACTION hoặc remove/REMOVE_REACTION."
        )
    if not str(messageID).strip():
        raise ValueError("messageID không được để trống.")
    if not emojiChoice:
        raise ValueError("emojiChoice không được để trống.")
    dataForm: dict[str, Any] = formAll(dataFB, docID=1491398900900362)
    dataForm["variables"] = json.dumps(
        {
            "data": {
                "action": action_map[normalized_action],
                "client_mutation_id": "1",
                "actor_id": dataFB["FacebookID"],
                "message_id": str(messageID),
                "reaction": emojiChoice,
            }
        }
    )
    dataForm["dpr"] = 1

    return {
        "headers": Headers(dataForm),
        "timeout": 30,
        "url": "https://www.facebook.com/webgraphql/mutation/",
        "data": dataForm,
        "cookies": parse_cookie_string(dataFB["cookieFacebook"]),
        "verify": True,
    }



async def func(
    dataFB: dict[str, Any],
    typeAdded: str,
    messageID: str | int,
    emojiChoice: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> httpx.Response:
    req = _build_request(dataFB, typeAdded, messageID, emojiChoice)
    response = await send_request_async(req, client=client)
    response.raise_for_status()
    return response


""" Hướng dẫn sử dụng (Tutorial)

 * Dữ liệu yêu cầu (args):

     - dataFB: lấy từ _core._session.dataGetHome(setCookies)
     - typeAdded: "add" thêm reaction vào tin nhắn đó. "remove" để xoá reaction tại tin nhắn đó
     - messageID: messageID của tin nhắn
     - emojiChoice: emoji cần reaction vào tin nhắn (VD: 👍, 😭, 😎,....)(All emoji)

* Kết quả trả về:

     - Không có dữ liệu
     - Ghi chú: tùy thuộc vào nhiều trường hợp mà error có thể báo code lỗi và chi tiết khác nhau!

* Thông tin tác giả:
     Facebook:  m.me/zminhhuydev
     Telegram: t.me/minhhuydev
     Github: MinhHuyDev

✓Remake by Nguyễn Minh Huy
✓Remake from Fbchat Python (https://fbchat.readthedocs.io/en/stable/)
✓Hoàn thành vào lúc 21:22 ngày 23/6/2023 • Cập nhật mới nhất: 7:52 20/7/2023
✓Tôn trọng tác giả ❤️
"""
