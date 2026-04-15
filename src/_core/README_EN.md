# _core (`src/_core`)

`_core` is the shared technical foundation for the entire codebase. This folder does not implement end-user features directly. Instead, it is responsible for:

- Initializing sessions from cookies.
- Building base payloads/requests for Facebook endpoints.
- Parsing cookies and extracting dynamic tokens.
- Generating IDs for messaging send/listen flows.
- Providing reusable utility functions for `_features` and `_messaging`.

---

## 1) Folder structure

```text
src/_core/
├── __init__.py
├── _session.py
├── _utils.py
├── _facebookLogin.py
├── README.md
├── REAME.md
├── REAME_VI.md
└── README_EN.md
```

### Primary exports

`src/_core/__init__.py` currently exports:

```python
__all__ = ["_session", "_utils", "_facebookLogin"]
```

This means you can import from `_core` and access these exported modules directly.

---

## 2) Responsibility scope

### `_core` is used for:

- Building shared headers and request forms.
- Converting cookie strings into `requests`-compatible dictionaries.
- Extracting dynamic values from the Facebook homepage (`fb_dtsg`, `jazoest`, etc.).
- Generating runtime IDs for messaging workflows.
- Providing shared parsing/formatting/helper utilities.

---

## 3) Core data contract (**IMPORTANT**): `dataFB`

`_session.dataGetHome(setCookies)` returns a dictionary usually named `dataFB`.

### Returned fields

- `fb_dtsg`
- `fb_dtsg_ag`
- `jazoest`
- `hash`
- `sessionID`
- `FacebookID`
- `clientRevision`
- `cookieFacebook`

Almost every module in `_features/*` and `_messaging/*` depends on these values.

---

## 4) Detailed module reference

## 4.1 `_session.py`

### Function: `dataGetHome(setCookies)`

This function requests `https://www.facebook.com/` using the provided cookies, then extracts the tokens/values required for follow-up API calls.

### Input

- `setCookies` (`str`): raw cookie string, for example:
  - `"c_user=...; xs=...; fr=...; datr=...;"`

### Output

- A `dict` in the `dataFB` format shown above.

### Workflow

1. Build browser-like GET headers.
2. Convert the cookie string to a dictionary using `_utils.parse_cookie_string`.
3. Download the homepage HTML.
4. Extract token values with `_utils.dataSplit`.
5. Return the session dictionary plus the original cookie string.

### Notes

- The current extraction is marker/split-based and may fail if Facebook changes its HTML structure.
- Accounts may hit checkpoint flows.

---

## 4.2 `_utils.py`

This is the most important module inside `_core`, and it contains many shared helpers.

### A) HTTP/request helper group

- `Headers(dataForm=None, Host=None)`
  - Builds the base header set.
  - Can add `Content-Length` based on `dataForm` size.
- `parse_cookie_string(cookie_string)`
  - Converts cookie strings into dictionaries for `requests`.
- `mainRequests(urlRequests, dataForm, setCookies)`
  - Returns a kwargs dictionary ready for `requests.post(**kwargs)`.

### B) Parse/format helper group

- `digitToChar(digit)`
- `str_base(number, base)`
- `dataSplit(...)`
  - Splits/extracts data using delimiters.
- `clearHTML(text)`
  - Removes HTML tags via regex.
- `formatResults(type, text)`
  - Normalizes output into `{ "status": ..., "message": ... }`.

### C) General form builder

- `formAll(dataFB, FBApiReqFriendlyName=None, docID=None, requireGraphql=None)`

This is the backbone helper for most request flows.

It builds baseline payloads for Facebook endpoints in two modes:

1. GraphQL mode (`requireGraphql is None`)
   - Includes `fb_api_req_friendly_name`, `doc_id`, `fb_api_caller_class`, etc.
2. Minimal/legacy mode (`requireGraphql != None`)
   - Keeps only fields required for non-GraphQL endpoints.

### D) Messaging ID helper group

- `generate_session_id()`
- `generate_client_id()`
- `gen_threading_id()`
- `json_minimal(data)`
- `_set_chat_on(value)`

These are used by message sending and event listening modules.

### E) Other utility helpers

- `require_list(list_)`
- `get_files_from_paths(filenames)`
- `randStr(length)`

---

## 4.3 `_facebookLogin.py`

This module handles Facebook login using username/password.

### Public components

- `class loginFacebook`
  - `__init__(username, password, AuthenticationGoogleCode=None)`
  - `main()` returns a success/failure dictionary.
- `GetToken2FA(key2Fa)`
  - Calls `https://2fa.live/tok/...` to fetch an OTP code.
- `jsonResults(...)`
  - Normalizes the login response structure.

### On successful login

- `success.setCookies`
- `success.accessTokenFB`
- `success.cookiesKey-ValueList`

### On failed login

- `error.title`
- `error.description`
- `error.error_subcode`
- `error.error_code`
- `error.fbtrace_id`

### Security warning

- This module handles sensitive data: username, password, cookies, and access token.
- In production use, prefer cookie-based login whenever possible.
- The login flow may break if Facebook changes auth endpoints.

---

## 5) Dependency map in the project

`_core._utils` is widely imported by:

- `src/_features/_facebook/*`
- `src/_features/_thread/*`
- `src/_messaging/*`

Most frequently used helpers:

- `formAll`
- `mainRequests`
- `parse_cookie_string`
- `Headers`
- `formatResults`
- `gen_threading_id`, `generate_session_id`, `generate_client_id`
- `str_base`, `randStr`, `get_files_from_paths`

**Warning**: changes in core payload/cookie logic can affect a large portion of the feature layer.

---

## 6) Example source code

## 6.1 Initialize `dataFB` from cookies

```python
from _core._session import dataGetHome

setCookies = "c_user=...; xs=...; fr=...; datr=...;"
dataFB = dataGetHome(setCookies)

print(dataFB["FacebookID"])
print(dataFB["fb_dtsg"])
```

## 6.2 Build and send a GraphQL request

```python
import json
import requests

from _core._utils import formAll, mainRequests

dataForm = formAll(
    dataFB,
    FBApiReqFriendlyName="CometNotificationsDropdownQuery",
    docID=6770067089747450,
)

dataForm["variables"] = json.dumps({
    "count": 10,
    "environment": "MAIN_SURFACE",
    "scale": 1,
})

resp = requests.post(**mainRequests(
    "https://www.facebook.com/api/graphql/",
    dataForm,
    dataFB["cookieFacebook"],
))

print(resp.status_code)
```

## 6.3 Build a minimal payload (non-GraphQL)

```python
from _core._utils import formAll

payload = formAll(dataFB, requireGraphql=False)
payload["message_id"] = "mid...."
```

---

## 7) Common issues and handling

### Case 1: many requests fail with auth/session errors

- Check whether the cookie is still valid.
- Re-run `_session.dataGetHome(...)` and verify required keys.

### Case 2: parsed field returns a fallback value

- Facebook homepage HTML likely changed.
- Update split markers in `_session.py`.
