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

# Backwards-compatible aliases for the old `_async` API.
func_async = func
