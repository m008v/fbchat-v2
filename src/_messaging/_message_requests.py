from __future__ import annotations

import json
from typing import Any
from _core._utils import formAll, mainRequests, send_request, send_request_async

def _build_request(dataFB: dict[str, Any]) -> dict[str, Any]:
     dataForm = formAll(dataFB, requireGraphql=0)
     dataForm["queries"] = json.dumps({
          "o0": {
               "doc_id": "3336396659757871",
               "query_params": {
                    "limit": 10000,
                    "before": None,
                    "tags": ["PENDING"],
                    "includeDeliveryReceipts": False,
                    "includeSeqID": True,
               }
          }
     })
     return mainRequests("https://www.facebook.com/api/graphqlbatch/", dataForm, dataFB["cookieFacebook"])

def _parse_response(text: str) -> dict[str, Any]:
     dataGet = json.loads(text.split('{"successful_results"}')[0])
     PendingList: list[dict[str, Any]] = dataGet['o0']['data']['viewer']['message_threads']['nodes']
     dictExportData: dict[str | int, Any] = {"data":{}}
     total: int = 0
     for i in PendingList:
          over: list[dict[str, Any]] = i['last_message']['nodes']
          try:
               contentMessage, senderID, timestamp_precise = over[0]['snippet'], over[0]['message_sender']['messaging_actor']['id'], over[0]['timestamp_precise']
               dictExportData[total] = {'senderID': senderID, 'snippet': contentMessage, 'timestamp_precise': timestamp_precise}
               total += 1
          except (IndexError, KeyError, TypeError):
               pass
     dictExportData['total_count'] = total
     return {
          "success": 1,
          "messages": "Lấy danh sách thành công",
          "data": dictExportData
     }

def func(dataFB: dict[str, Any]) -> dict[str, Any]:
     req = _build_request(dataFB)
     res = send_request(req)
     return _parse_response(res.text)

async def func_async(dataFB: dict[str, Any]) -> dict[str, Any]:
     req = _build_request(dataFB)
     res = await send_request_async(req)
     return _parse_response(res.text)