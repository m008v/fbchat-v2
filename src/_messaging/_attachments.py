from __future__ import annotations

import random, attr, json, httpx
from typing import Any
from _core._utils import str_base, get_files_from_paths

USER_AGENTS: list[str] = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/601.1.10 (KHTML, like Gecko) Version/8.0.5 Safari/601.1.10", "Mozilla/5.0 (Windows NT 6.3; WOW64; ; NCT50_AAP285C84A1328) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1", "Mozilla/5.0 (X11; CrOS i686 2268.111.0) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.57 Safari/536.11", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1092.0 Safari/536.6"]

def _build_request(filenames: str | list[str], dataFB: dict[str, Any]) -> dict[str, Any]:
     headers: dict[str, str] = {
          "Referer": "https://www.facebook.com",
          "Accept": "text/html",
          "User-Agent": random.choice(USER_AGENTS),
          "Cookie": dataFB["cookieFacebook"],
     }
     
     __reg = attr.ib(0).counter
     __reg += 1
     dataForm: dict[str, Any] = {} 
     dataForm["voice_clip"] = False
     dataForm["__a"] = 1
     dataForm["__req"] = str_base(__reg, 36) 
     dataForm["fb_dtsg"] = dataFB["fb_dtsg"]
     
     if isinstance(filenames, str):
          filenames = [filenames]
          
     file_dict: dict[str, Any] = {}
     import os, mimetypes
     for i, fpath in enumerate(filenames):
          mime = mimetypes.guess_type(fpath)[0] or 'application/octet-stream'
          file_dict[f"upload_{i}"] = (os.path.basename(fpath), open(fpath, "rb"), mime)
     
     return {
          "url": "https://upload.facebook.com/ajax/mercury/upload.php",
          "headers": headers,
          "data": dataForm,
          "files": file_dict,
     }

def _parse_response(resultRequests: str) -> dict[str, Any] | None:
     try: 
          parsed = json.loads(resultRequests.replace("for (;;);", ""))["payload"]
     except (json.JSONDecodeError, KeyError, TypeError): 
          print("ERROR-UPLOADED: " + str(resultRequests))
          return None
     dataList: list[Any] = []
     try:
          for data in parsed["metadata"][0].values():
               dataList.append(data)
     except (KeyError, TypeError):
          try:
               for data in parsed["metadata"]['0'].values():
                    dataList.append(data)
          except (KeyError, TypeError):
               print("ERROR-UPLOADED (metadata fallback failed): " + str(resultRequests))
               return None
     def safe_get(idx: int) -> Any:
          return dataList[idx] if len(dataList) > idx else None

     return {
          "attachmentID": safe_get(0),
          "attachmentUrl": safe_get(3),
          "videoDuration": safe_get(2),
          "typeAttachment": safe_get(4)
     }

def func(filenames: str | list[str], dataFB: dict[str, Any]) -> dict[str, Any] | None:
     req = _build_request(filenames, dataFB)
     try:
          with httpx.Client(timeout=30) as client:
               res = client.post(**req)
     finally:
          for f_tuple in req.get("files", {}).values():
               if isinstance(f_tuple, tuple) and len(f_tuple) >= 2 and hasattr(f_tuple[1], 'close'):
                    f_tuple[1].close()
     return _parse_response(res.text)

async def func_async(filenames: str | list[str], dataFB: dict[str, Any]) -> dict[str, Any] | None:
     req = _build_request(filenames, dataFB)
     try:
          async with httpx.AsyncClient(timeout=30) as client:
               res = await client.post(**req)
     finally:
          for f_tuple in req.get("files", {}).values():
               if isinstance(f_tuple, tuple) and len(f_tuple) >= 2 and hasattr(f_tuple[1], 'close'):
                    f_tuple[1].close()
     return _parse_response(res.text)

# func("file-name.jpg", dataFB)
# from _core._session import dataGetHome
# print(func("Name file to need uploads", dataGetHome("this is cookie Facebook")))
# output-image: {'attachmentID': 676421537934928, 'attachmentUrl': 'https://scontent.fsgn5-8.fna.fbcdn.net/v/t1.15752-9/328999258_555852780015611_2452318447980968642_n.jpg?_nc_cat=109&ccb=1-7&_nc_sid=b65b05&_nc_ohc=ngkZ0e3NqzYAX8ZdVYx&_nc_ht=scontent.fsgn5-8.fna&oh=03_AdTrTWSDqWiSrYcTG8c_WKn1ksUdttUbcK3hmvTu2WEmRQ&oe=65A10D97', 'attachmentType': 'image/jpeg', 'attachmentDataSend': [(676421537934928, 'image/jpeg')]}
# ouput-video: {'attachmentID': 848156417052481, 'attachmentUrl': 'https://scontent.fsgn5-10.fna.fbcdn.net/v/t15.3394-10/416827059_6699338906842547_1263326403482126710_n.jpg?_nc_cat=107&ccb=1-7&_nc_sid=407108&_nc_eui2=AeGD75e6KV6vQfPcP4aCq9Yua-QBDRBkDOJr5AENEGQM4oV21IQSIev2_QwXWrdXFSg&_nc_ohc=aFezV-zIf3EAX_UjIAF&_nc_ht=scontent.fsgn5-10.fna&oh=03_AdQESAAFJ9GODQx-H36DmwWZ_ENQvbqnWz5Mm6lcZmoc8Q&oe=6599A974', 'attachmentType': 'video/mp4', 'attachmentDataSend': None}

# completed at 14:03 19/06/2023 | last updated at 12:03 AM 10/03/2026
