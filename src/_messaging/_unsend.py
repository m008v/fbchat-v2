from __future__ import annotations

import json
from typing import Any
import httpx
from _core._utils import formAll, mainRequests, send_request, send_request_async
 
def _build_request(messageID: str, dataFB: dict[str, Any]) -> dict[str, Any]:
     dataForm = formAll(dataFB, requireGraphql=False)
     dataForm["message_id"] = messageID
     return mainRequests("https://www.facebook.com/messaging/unsend_message/", dataForm, dataFB["cookieFacebook"])

def _parse_response(text: str) -> dict[str, Any] | Exception:
     sendRequests = json.loads(text.split("for (;;);")[1])
     if (sendRequests.get("error")):
          return Exception({"error": str(sendRequests)})
     return {
          "success": 1,
          "messages": "Thu hồi tin nhắn thành công."
     }

def func(messageID: str, dataFB: dict[str, Any]) -> dict[str, Any] | Exception:
     res = send_request(_build_request(messageID, dataFB))
     return _parse_response(res.text)

async def func_async(messageID: str, dataFB: dict[str, Any]) -> dict[str, Any] | Exception:
     res = await send_request_async(_build_request(messageID, dataFB))
     return _parse_response(res.text)

# completed at 09:36 30/06/2023 | last updated at 19:50 13/12/2023
