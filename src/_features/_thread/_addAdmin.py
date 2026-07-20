"""
Đường dẫn file:
  src/_features/_thread/_addAdmin.py

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

from typing import Any

import httpx

from _core._utils import formatResults, formAll, post_form_json_async

_URL = "https://www.facebook.com/messaging/save_admins/?dpr=1"


def _build_form(
    dataFB: dict[str, Any], threadID: str | int, idUser: str | int, statusChoice: bool
) -> dict[str, Any]:
    data_form = formAll(dataFB, requireGraphql=False)
    data_form.update(
        {
            "thread_fbid": str(threadID),
            "admin_ids[0]": str(idUser),
            "add": bool(statusChoice),
        }
    )
    return data_form


def _parse_result(payload: dict[str, Any], status_choice: bool) -> dict[str, str]:
    error = payload.get("error")
    if error == 1976004:
        return formatResults("error", "Bạn không phải là quản trị viên.")
    if error == 1357031:
        return formatResults("error", "Chủ đề này không phải là cuộc trò chuyện nhóm.")
    if error:
        return formatResults(
            "error", f"Facebook từ chối cập nhật quyền quản trị: {error}."
        )
    action = "Thêm" if status_choice else "Gỡ"
    return formatResults("success", f"{action} quản trị viên thành công.")



async def func(
    dataFB: dict[str, Any],
    threadID: str | int,
    idUser: str | int,
    statusChoice: bool = True,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    payload = await post_form_json_async(
        _URL,
        _build_form(dataFB, threadID, idUser, statusChoice),
        dataFB["cookieFacebook"],
        strip_for_loop_prefix=True,
        client=client,
    )
    return _parse_result(payload, statusChoice)
