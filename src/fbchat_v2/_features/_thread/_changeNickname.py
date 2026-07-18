from __future__ import annotations

from typing import Any

import httpx

from fbchat_v2._core._utils import formatResults, formAll, post_form_json_async

_URL = "https://www.facebook.com/messaging/save_thread_nickname/-source=thread_settings&dpr=1"


def _build_form(
    dataFB: dict[str, Any],
    threadID: str | int,
    idUser: str | int,
    newNickname: str,
) -> dict[str, Any]:
    data_form = formAll(dataFB, requireGraphql=False)
    data_form.update(
        {
            "nickname": newNickname,
            "participant_id": str(idUser),
            "thread_or_other_fbid": str(threadID),
        }
    )
    return data_form


def _parse_result(payload: dict[str, Any]) -> dict[str, str]:
    error = payload.get("error")
    if error == 1545014:
        return formatResults("error", "Người dùng không tồn tại trong cuộc trò chuyện.")
    if error == 1357031:
        return formatResults("error", "Cuộc trò chuyện không tồn tại.")
    if error:
        return formatResults("error", f"Facebook từ chối đổi biệt danh: {error}.")
    return formatResults("success", "Thay đổi biệt danh thành công.")



async def func(
    dataFB: dict[str, Any],
    threadID: str | int,
    idUser: str | int,
    NewNickname: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    payload = await post_form_json_async(
        _URL,
        _build_form(dataFB, threadID, idUser, NewNickname),
        dataFB["cookieFacebook"],
        strip_for_loop_prefix=True,
        client=client,
    )
    return _parse_result(payload)
