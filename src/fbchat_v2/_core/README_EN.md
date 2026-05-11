# `_core` — Foundation Layer

> The foundation of `fbchat-v2`. Bootstraps sessions, builds request payloads, parses cookies, generates IDs — every higher layer depends on this module.

[![Layer](https://img.shields.io/badge/layer-core-6E40C9)](.)
[![Status](https://img.shields.io/badge/status-stable-22c55e)](.)
[![Vietnamese](https://img.shields.io/badge/docs-Ti%E1%BA%BFng%20Vi%E1%BB%87t-blue)](README.md)

---

## 📑 Table of Contents

- [Responsibilities](#-responsibilities)
- [Folder Structure](#-folder-structure)
- [Public API](#-public-api)
- [The `dataFB` Contract](#-the-datafb-contract)
- [Module Reference](#-module-reference)
  - [`_session.py`](#sessionpy)
  - [`_utils.py`](#utilspy)
  - [`_facebookLogin.py`](#facebookloginpy)
- [Dependency Map](#-dependency-map)
- [Examples](#-examples)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Responsibilities

`_core` is the shared technical foundation — it does **not** implement end-user features. Its responsibilities are:

- 🔑 Bootstrap a **user session** from cookies.
- 🧱 Build standardized **payloads / requests** for Facebook endpoints.
- 🍪 Parse cookies and extract **dynamic tokens** (`fb_dtsg`, `jazoest`, …).
- 🆔 Generate the various **IDs** required by send/listen flows.
- 🛠 Provide **utilities** reused by `_features` and `_messaging`.

---

## 📂 Folder Structure

```text
src/_core/
├── __init__.py
├── _session.py           # Bootstraps dataFB from cookies
├── _utils.py             # HTTP helpers, parsers, ID generators…
├── _facebookLogin.py     # Username/password login (+ 2FA)
├── README.md
└── README_EN.md          # ← you are here
```

---

## 📦 Public API

```python
# src/_core/__init__.py
__all__ = ["_session", "_utils", "_facebookLogin"]
```

After `import _core` you can reach every submodule via `_core._session`, `_core._utils`, `_core._facebookLogin`.

---

## 🧩 The `dataFB` Contract

`_session.dataGetHome(setCookies)` returns a `dict` (commonly named **`dataFB`**) — the **single source of truth** for every subsequent request.

| Key | Description |
|---|---|
| `fb_dtsg` | Runtime CSRF token |
| `fb_dtsg_ag` | Variant of `fb_dtsg` for certain endpoints |
| `jazoest` | Companion token to `fb_dtsg` |
| `hash` | Current session hash |
| `sessionID` | Runtime session ID |
| `FacebookID` | UID of the logged-in account |
| `clientRevision` | Client revision (Facebook updates it) |
| `cookieFacebook` | Original cookies as a dict, ready for `requests` |

> ⚠️ Almost **every** module in `_features/*` and `_messaging/*` depends on these values.

---

## 📚 Module Reference

### `_session.py`

#### `dataGetHome(setCookies: str) -> dict`

Hits `https://www.facebook.com/` with the supplied cookies and extracts the tokens needed for follow-up API calls.

| Param | Type | Description |
|---|---|---|
| `setCookies` | `str` | Raw cookie string, e.g. `"c_user=...; xs=...; fr=...; datr=...;"` |

**Returns:** a `dict` matching the `dataFB` schema above.

**Workflow:**

1. Build browser-like GET headers.
2. Convert the cookie string into a dict (`_utils.parse_cookie_string`).
3. Download the homepage HTML.
4. Extract tokens via `_utils.dataSplit`.
5. Return the session dict.

> ⚠️ Extraction is split-marker based and may break when Facebook changes its HTML. Accounts can also hit **checkpoint** flows.

---

### `_utils.py`

The most important module inside `_core`. Five helper groups:

#### A. HTTP / Request

| Function | Description |
|---|---|
| `Headers(dataForm=None, Host=None)` | Builds the base headers; auto-sets `Content-Length` when `dataForm` is given. |
| `parse_cookie_string(cookie_string)` | Cookie string → `dict` for `requests`. |
| `mainRequests(urlRequests, dataForm, setCookies)` | Returns a `kwargs` dict ready for `requests.post(**kwargs)`. |

#### B. Parse / Format

| Function | Description |
|---|---|
| `digitToChar(digit)` | Digit → char mapping. |
| `str_base(number, base)` | Numeric base conversion. |
| `dataSplit(...)` | Slice text by delimiter. |
| `clearHTML(text)` | Strip HTML tags via regex. |
| `formatResults(type, text)` | Normalize output to `{ "status": ..., "message": ... }`. |

#### C. General Form Builder

```python
formAll(dataFB, FBApiReqFriendlyName=None, docID=None, requireGraphql=None)
```

The backbone of most request flows — supports two modes:

1. **GraphQL** (`requireGraphql is None`): includes `fb_api_req_friendly_name`, `doc_id`, `fb_api_caller_class`, …
2. **Legacy / minimal** (`requireGraphql != None`): keeps only the fields needed for non-GraphQL endpoints.

#### D. Messaging ID Generators

`generate_session_id()` · `generate_client_id()` · `gen_threading_id()` · `json_minimal(data)` · `_set_chat_on(value)`

> Used heavily by `_messaging._send` and `_messaging._listening`.

#### E. Misc Utilities

`require_list(list_)` · `get_files_from_paths(filenames)` · `randStr(length)`

---

### `_facebookLogin.py`

Logs into Facebook with **username / password** (+ optional 2FA).

#### Public components

| Symbol | Description |
|---|---|
| `class loginFacebook(username, password, AuthenticationGoogleCode=None)` | Login class; call `.main()` to execute. |
| `GetToken2FA(key2Fa)` | Fetches a 2FA OTP via `https://2fa.live/tok/...`. |
| `jsonResults(...)` | Normalizes the response shape. |

#### Result shape

| Status | Returned fields |
|---|---|
| ✅ Success | `success.setCookies` · `success.accessTokenFB` · `success.cookiesKey-ValueList` |
| ❌ Failure | `error.title` · `error.description` · `error.error_subcode` · `error.error_code` · `error.fbtrace_id` |

> 🔒 This module handles highly sensitive data. **Strongly prefer** cookie-based login in production.

---

## 🔗 Dependency Map

`_core._utils` is widely imported by:

- `src/_features/_facebook/*`
- `src/_features/_thread/*`
- `src/_messaging/*`

Most-used helpers:

```text
formAll · mainRequests · parse_cookie_string · Headers · formatResults
gen_threading_id · generate_session_id · generate_client_id
str_base · randStr · get_files_from_paths
```

> ⚠️ **Warning:** changes to core payload / cookie logic ripple across most features.

---

## 💡 Examples

### Bootstrap `dataFB` from cookies

```python
from _core._session import dataGetHome

setCookies = "c_user=...; xs=...; fr=...; datr=...;"
dataFB = dataGetHome(setCookies)

print(dataFB["FacebookID"])
print(dataFB["fb_dtsg"])
```

### Build & send a GraphQL request

```python
import json, requests
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

### Minimal payload (non-GraphQL)

```python
from _core._utils import formAll

payload = formAll(dataFB, requireGraphql=False)
payload["message_id"] = "mid...."
```

---

## 🛠 Troubleshooting

| Symptom | Suggested fix |
|---|---|
| Many requests fail with auth/session errors | Cookies expired → regenerate `dataFB` via `dataGetHome(...)`. |
| Parsed field returns a fallback value | Homepage HTML changed → update split markers in `_session.py`. |
| Login hits checkpoint | Switch to cookie-based login; if you must keep the login flow, check IP / 2FA. |

---

<div align="right">

⬆️ [Back to main README](../../README_EN.md) · 🇻🇳 [Tiếng Việt](README.md)

</div>
