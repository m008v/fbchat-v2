from __future__ import annotations

import attr, re, json, random, string, time, os
from io import BufferedReader
from mimetypes import guess_type
from typing import Any, Generator

# User-Agent pool — xoay ngẫu nhiên để giảm fingerprint detection từ Facebook
_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
]
_SEC_CH_UA = '"Chromium";v="137", "Not;A=Brand";v="24", "Google Chrome";v="137"'

def Headers(dataForm: dict[str, Any] | str | None = None, Host: str = 'www.facebook.com') -> dict[str, str]:
     headers: dict[str, str] = {}
     headers["Host"] = Host
     headers["Connection"] = "keep-alive"
     headers["User-Agent"] = random.choice(_USER_AGENTS)
     headers["Accept"] = "*/*"
     headers["Origin"] = "https://" + Host
     headers["Sec-Fetch-Site"] = "same-origin"
     headers["Sec-Fetch-Mode"] = "cors"
     headers["Sec-Fetch-Dest"] = "empty"
     headers["Referer"] = "https://" + Host
     headers["sec-ch-ua"] = _SEC_CH_UA
     headers["sec-ch-ua-mobile"] = "?0"
     headers["sec-ch-ua-platform"] = "\"Windows\""
     headers["Accept-Language"] = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
     return headers
     
def digitToChar(digit: int) -> str:
          if digit < 10:
               return str(digit)
          return chr(ord("a") + digit - 10)

def str_base(number: int, base: int) -> str:
     if number < 0:
          return "-" + str_base(-number, base)
     (d, m) = divmod(number, base)
     if d > 0:
          return str_base(d, base) + digitToChar(m)
     return digitToChar(m)

def parse_cookie_string(cookie_str: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out

def dataSplit(string1: str, string2: str, numberSplit1: int | None = None, numberSplit2: int | None = None, HTML: str | None = None, amount: int | None = None, string3: str | None = None, numberSplit3: int | None = None, defaultValue: bool | None = None) -> str | None:
     if (defaultValue): numberSplit1, numberSplit2 = 1, 0
     if (amount == None):
          return HTML.split(string1)[numberSplit1].split(string2)[numberSplit2]
     elif (amount == 3):
          return HTML.split(string1)[numberSplit1].split(string2)[numberSplit2].split(string3)[numberSplit3]
     
def formAll(dataFB: dict[str, Any], FBApiReqFriendlyName: str | None = None, docID: str | int | None = None, requireGraphql: bool = True) -> dict[str, Any]:
     __reg = attr.ib(0).counter
     __reg += 1 
     dataForm: dict[str, Any] = {
          "fb_dtsg": dataFB["fb_dtsg"],
          "jazoest": dataFB["jazoest"],
          "__a": 1,
          "__user": str(dataFB["FacebookID"]),
          "__req": str_base(__reg, 36),
          "__rev": dataFB["clientRevision"],
          "av": dataFB["FacebookID"],
     }
     
     if (requireGraphql != False):
          dataForm["fb_api_caller_class"] = "RelayModern"
          dataForm["fb_api_req_friendly_name"] = FBApiReqFriendlyName
          dataForm["server_timestamps"] = "true"
          dataForm["doc_id"] = str(docID)

     return dataForm
     
def clearHTML(text: str) -> str:
     regex = re.compile(r'<[^>]+>')
     return regex.sub('', text)
     
import httpx

def mainRequests(urlRequests: str, dataForm: dict[str, Any], setCookies: str) -> dict[str, Any]:
     return {
          "headers": Headers(dataForm, 'www.facebook.com'),
          "timeout": 30,
          "url": urlRequests,
          "data": dataForm,
          "cookies": parse_cookie_string(setCookies),
          "verify": True
     }

def send_request(req_kwargs: dict[str, Any]) -> httpx.Response:
     verify = req_kwargs.pop('verify', True)
     timeout = req_kwargs.pop('timeout', 5)
     req_kwargs.pop('proxies', None)
     with httpx.Client(verify=verify, timeout=timeout) as client:
          return client.post(**req_kwargs)

async def send_request_async(req_kwargs: dict[str, Any]) -> httpx.Response:
     verify = req_kwargs.pop('verify', True)
     timeout = req_kwargs.pop('timeout', 5)
     req_kwargs.pop('proxies', None)
     async with httpx.AsyncClient(verify=verify, timeout=timeout) as client:
          return await client.post(**req_kwargs)

def send_get_request(req_kwargs: dict[str, Any]) -> httpx.Response:
     verify = req_kwargs.pop('verify', True)
     timeout = req_kwargs.pop('timeout', 5)
     req_kwargs.pop('proxies', None)
     with httpx.Client(verify=verify, timeout=timeout) as client:
          return client.get(**req_kwargs)

async def send_get_request_async(req_kwargs: dict[str, Any]) -> httpx.Response:
     verify = req_kwargs.pop('verify', True)
     timeout = req_kwargs.pop('timeout', 5)
     req_kwargs.pop('proxies', None)
     async with httpx.AsyncClient(verify=verify, timeout=timeout) as client:
          return await client.get(**req_kwargs)

     
def generate_session_id() -> int:

     """Generate a random session ID between 1 and 9007199254740991."""
     return random.randint(1, 2 ** 53)  

def generate_client_id() -> str:
     
     def gen(length: int) -> str:
          return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
     return gen(8) + '-' + gen(4) + '-' + gen(4) + '-' + gen(4) + '-' + gen(12)
     
def json_minimal(data: Any) -> str:

     """Get JSON data in minimal form."""
     return json.dumps(data, separators=(",", ":"))

def _set_chat_on(value: Any) -> str:

     return json_minimal(value)

def gen_threading_id() -> str:

     return str(
          int(format(int(time.time() * 1000), "b") + 
          ("0000000000000000000000" + 
          format(int(random.random() * 4294967295), "b"))
          [-22:], 2)
     )

def require_list(list_: list[Any] | Any) -> set[Any]:
     if isinstance(list_, list):
          return set(list_)
     else:
          return set([list_])
def get_files_from_paths(filenames: str | list[str]) -> Generator[tuple[str, BufferedReader, str | None], None, None]:
     if isinstance(filenames, str):
          filenames = [filenames]
     for filename in filenames:
          yield (os.path.basename(filename), open(filename, "rb"), guess_type(filename)[0])
def formatResults(type: str, text: str) -> dict[str, str]:
     return {
          "status": type,
          "message": text
     }

def randStr(length: int) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
