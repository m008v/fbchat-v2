# `_core` — Tầng nền tảng

> Foundation layer của `fbchat-v2`. Khởi tạo phiên, sinh payload, parse cookie, sinh ID — mọi tầng phía trên đều phụ thuộc vào module này.

[![Layer](https://img.shields.io/badge/layer-core-6E40C9)](.)
[![Status](https://img.shields.io/badge/status-stable-22c55e)](.)
[![English](https://img.shields.io/badge/docs-English-blue)](README_EN.md)

---

## 📑 Mục lục

- [Vai trò](#-vai-trò)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Public API](#-public-api)
- [Hợp đồng dữ liệu `dataFB`](#-hợp-đồng-dữ-liệu-datafb)
- [Tham chiếu module](#-tham-chiếu-module)
  - [`_session.py`](#sessionpy)
  - [`_utils.py`](#utilspy)
  - [`_facebookLogin.py`](#facebookloginpy)
- [Sơ đồ phụ thuộc](#-sơ-đồ-phụ-thuộc)
- [Ví dụ](#-ví-dụ)
- [Khắc phục sự cố](#-khắc-phục-sự-cố)

---

## 🎯 Vai trò

`_core` là tầng kỹ thuật dùng chung — **không** chứa tính năng người dùng cuối. Trách nhiệm chính:

- 🔑 Khởi tạo **phiên làm việc** từ cookie người dùng.
- 🧱 Tạo **payload / request** chuẩn cho các endpoint Facebook.
- 🍪 Parse cookie & trích xuất **token động** (`fb_dtsg`, `jazoest`, …).
- 🆔 Sinh các loại **ID** phục vụ luồng gửi / nhận tin.
- 🛠 Cung cấp **utilities** dùng lại bởi `_features` và `_messaging`.

---

## 📂 Cấu trúc thư mục

```text
src/_core/
├── __init__.py
├── _session.py           # Khởi tạo dataFB từ cookie
├── _utils.py             # HTTP helpers, parser, ID generator…
├── _facebookLogin.py     # Đăng nhập username/password (+ 2FA)
├── README.md             # ← bạn đang ở đây
└── README_EN.md
```

---

## 📦 Public API

```python
# src/_core/__init__.py
__all__ = ["_session", "_utils", "_facebookLogin"]
```

Sau khi `import _core`, bạn có thể truy cập tất cả module con thông qua `_core._session`, `_core._utils`, `_core._facebookLogin`.

---

## 🧩 Hợp đồng dữ liệu `dataFB`

`_session.dataGetHome(setCookies)` trả về một `dict` (thường đặt tên là **`dataFB`**) — đây là **single source of truth** cho mọi request về sau.

| Khoá | Mô tả |
|---|---|
| `fb_dtsg` | Token CSRF runtime |
| `fb_dtsg_ag` | Biến thể `fb_dtsg` cho một số endpoint |
| `jazoest` | Token kèm `fb_dtsg` |
| `hash` | Hash phiên hiện tại |
| `sessionID` | ID phiên runtime |
| `FacebookID` | UID người dùng đang đăng nhập |
| `clientRevision` | Revision client (cập nhật theo Facebook) |
| `cookieFacebook` | Cookie gốc dạng dict, sẵn sàng cho `requests` |

> ⚠️ Gần như **mọi** module trong `_features/*` và `_messaging/*` đều phụ thuộc vào các giá trị này.

---

## 📚 Tham chiếu module

### `_session.py`

#### `dataGetHome(setCookies: str) -> dict`

Truy cập `https://www.facebook.com/` bằng cookie đã cung cấp, trích xuất các token cần thiết.

| Tham số | Kiểu | Mô tả |
|---|---|---|
| `setCookies` | `str` | Cookie thô, ví dụ `"c_user=...; xs=...; fr=...; datr=...;"` |

**Trả về:** `dict` theo schema `dataFB` ở trên.

**Quy trình:**

1. Tạo header GET kiểu trình duyệt.
2. Chuyển cookie string → dict (`_utils.parse_cookie_string`).
3. Tải HTML homepage.
4. Cắt token bằng `_utils.dataSplit`.
5. Trả về session dict.

> ⚠️ Cách trích xuất hiện dùng split-marker; có thể vỡ khi Facebook đổi HTML. Tài khoản cũng có thể dính **checkpoint**.

---

### `_utils.py`

Module quan trọng nhất của `_core`. Gồm 5 nhóm hàm chính:

#### A. HTTP / Request

| Hàm | Mô tả |
|---|---|
| `Headers(dataForm=None, Host=None)` | Tạo bộ header chuẩn; tự thêm `Content-Length` nếu có `dataForm`. |
| `parse_cookie_string(cookie_string)` | Cookie string → `dict` cho `requests`. |
| `mainRequests(urlRequests, dataForm, setCookies)` | Trả về `kwargs` sẵn sàng dùng `requests.post(**kwargs)`. |

#### B. Parse / Format

| Hàm | Mô tả |
|---|---|
| `digitToChar(digit)` | Chuyển digit → char. |
| `str_base(number, base)` | Đổi cơ số. |
| `dataSplit(...)` | Cắt chuỗi theo delimiter. |
| `clearHTML(text)` | Loại thẻ HTML qua regex. |
| `formatResults(type, text)` | Chuẩn hoá output `{ "status": ..., "message": ... }`. |

#### C. Form builder tổng quát

```python
formAll(dataFB, FBApiReqFriendlyName=None, docID=None, requireGraphql=None)
```

Backbone của hầu hết flow request, hỗ trợ 2 chế độ:

1. **GraphQL** (`requireGraphql is None`): có `fb_api_req_friendly_name`, `doc_id`, `fb_api_caller_class`, …
2. **Legacy / minimal** (`requireGraphql != None`): chỉ giữ trường tối thiểu.

#### D. Messaging ID generators

`generate_session_id()` · `generate_client_id()` · `gen_threading_id()` · `json_minimal(data)` · `_set_chat_on(value)`

> Dùng nhiều trong `_messaging._send` và `_messaging._listening`.

#### E. Tiện ích khác

`require_list(list_)` · `get_files_from_paths(filenames)` · `randStr(length)`

---

### `_facebookLogin.py`

Đăng nhập Facebook bằng **username / password** (+ tuỳ chọn 2FA).

#### Thành phần công khai

| Symbol | Mô tả |
|---|---|
| `class loginFacebook(username, password, AuthenticationGoogleCode=None)` | Đăng nhập; gọi `.main()` để chạy. |
| `GetToken2FA(key2Fa)` | Lấy OTP 2FA qua `https://2fa.live/tok/...`. |
| `jsonResults(...)` | Chuẩn hoá cấu trúc trả về. |

#### Kết quả

| Trạng thái | Trường trả về |
|---|---|
| ✅ Thành công | `success.setCookies` · `success.accessTokenFB` · `success.cookiesKey-ValueList` |
| ❌ Thất bại | `error.title` · `error.description` · `error.error_subcode` · `error.error_code` · `error.fbtrace_id` |

> 🔒 Module xử lý dữ liệu cực kỳ nhạy cảm. **Khuyến nghị mạnh mẽ** dùng cookie-login trong production.

---

## 🔗 Sơ đồ phụ thuộc

`_core._utils` được import rộng rãi bởi:

- `src/_features/_facebook/*`
- `src/_features/_thread/*`
- `src/_messaging/*`

Helpers được dùng nhiều nhất:

```text
formAll · mainRequests · parse_cookie_string · Headers · formatResults
gen_threading_id · generate_session_id · generate_client_id
str_base · randStr · get_files_from_paths
```

> ⚠️ **Cảnh báo:** thay đổi logic core payload / cookie sẽ ảnh hưởng dây chuyền tới phần lớn tính năng.

---

## 💡 Ví dụ

### Khởi tạo `dataFB` từ cookie

```python
from _core._session import dataGetHome

setCookies = "c_user=...; xs=...; fr=...; datr=...;"
dataFB = dataGetHome(setCookies)

print(dataFB["FacebookID"])
print(dataFB["fb_dtsg"])
```

### Gửi request GraphQL

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

### Payload tối giản (non-GraphQL)

```python
from _core._utils import formAll

payload = formAll(dataFB, requireGraphql=False)
payload["message_id"] = "mid...."
```

---

## 🛠 Khắc phục sự cố

| Triệu chứng | Hướng xử lý |
|---|---|
| Nhiều request lỗi auth/session | Cookie hết hạn → tạo lại `dataFB` qua `dataGetHome(...)`. |
| Trường trả về giá trị fallback | HTML homepage đã đổi → cập nhật split markers trong `_session.py`. |
| Login dính checkpoint | Đổi sang cookie-login; nếu giữ nguyên login flow, kiểm tra IP / 2FA. |

---

<div align="right">

⬆️ [Về README chính](../../README.md) · 🇬🇧 [English](README_EN.md)

</div>
