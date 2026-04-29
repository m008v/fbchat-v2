# `_features` — Tầng tính năng

> Triển khai các nghiệp vụ Facebook & Messenger cấp người dùng: hồ sơ, bài viết, tìm kiếm, thông báo, Marketplace, quản trị thread…

[![Layer](https://img.shields.io/badge/layer-features-3B82F6)](.)
[![Status](https://img.shields.io/badge/status-stable-22c55e)](.)
[![English](https://img.shields.io/badge/docs-English-blue)](README_EN.md)

---

## 📑 Mục lục

- [Vai trò](#-vai-trò)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Public API](#-public-api)
- [Hợp đồng `dataFB`](#-hợp-đồng-datafb)
- [Tham chiếu module](#-tham-chiếu-module)
  - [`_facebook` — Nghiệp vụ Facebook](#facebook--nghiệp-vụ-facebook)
  - [`_thread` — Quản trị thread](#thread--quản-trị-thread)
- [Sơ đồ phụ thuộc](#-sơ-đồ-phụ-thuộc)
- [Ví dụ](#-ví-dụ)
- [Khắc phục sự cố](#-khắc-phục-sự-cố)

---

## 🎯 Vai trò

`_features` **không** quản lý session/token (đó là việc của `_core`). Tầng này chỉ tập trung vào **business logic**:

- 👤 Thao tác hồ sơ: bio, bài viết, profile phụ, professional mode.
- 🔔 Truy xuất user info & notification.
- 🔍 Tìm kiếm Facebook · 🚫 chặn / bỏ chặn.
- 🛒 Tạo / lấy thông tin Marketplace listing.
- 👥 Quản trị thread nhóm: đổi tên, emoji, biệt danh, thêm admin.

---

## 📂 Cấu trúc thư mục

```text
src/_features/
├── _facebook/                # Nghiệp vụ trên tài khoản Facebook
│   ├── __init__.py
│   ├── _blocking.py
│   ├── _changeBio.py
│   ├── _createPost.py
│   ├── _get_user_info.py
│   ├── _marketplace.py
│   ├── _notification.py
│   ├── _professional.py
│   ├── _registerOnProfile.py
│   └── _search.py
├── _thread/                  # Quản trị nhóm chat
│   ├── __init__.py
│   ├── _addAdmin.py
│   ├── _all_thread_data.py
│   ├── _changeEmoji.py
│   ├── _changeNameThread.py
│   └── _changeNickname.py
├── README.md                 # ← bạn đang ở đây
└── README_EN.md
```

---

## 📦 Public API

```python
# src/_features/_facebook/__init__.py
__all__ = [
    "_changeBio", "_createPost", "_professional", "_search",
    "_blocking", "_registerOnProfile", "_notification",
    "_marketplace", "_get_user_info",
]

# src/_features/_thread/__init__.py
__all__ = [
    "_changeNickname", "_addAdmin", "_changeEmoji", "_changeNameThread",
]
```

Sau khi `from _features._facebook import *` (hoặc `_thread`), bạn có thể gọi trực tiếp các module liệt kê trên.

---

## 🧩 Hợp đồng `dataFB`

Hầu hết các hàm trong `_features` đều nhận **`dataFB`** làm tham số đầu tiên — sinh ra từ `_core._session.dataGetHome(setCookies)`.

Trường thường dùng: `fb_dtsg` · `jazoest` · `FacebookID` · `clientRevision` · `sessionID` · `cookieFacebook`.

> 📖 Chi tiết schema: xem [`_core/README.md`](../_core/README.md#-hợp-đồng-dữ-liệu-datafb).

---

## 📚 Tham chiếu module

### `_facebook` — Nghiệp vụ Facebook

#### `_changeBio.py`

```python
func(dataFB, newContents, uploadPost=False)
```

Đổi bio tài khoản. `uploadPost=True` sẽ đăng feed story kèm theo.

- ✅ Thành công: `{ "success": 1, "messages": ... }`
- ❌ Thất bại: `{ "error": 1, ... }`

#### `_createPost.py`

```python
func(dataFB, newContents, attachmentID=None)
```

Tạo bài viết mới trên timeline. `attachmentID` là tham số dự phòng (chưa hoạt động trong flow hiện tại).

- ✅ Trả về `urlPost`.
- ❌ Trả `error` + message từ API.

#### `_professional.py`

```python
func(dataFB, statusBusiness=None)
```

Bật/tắt **Professional Mode**. `statusBusiness` chấp nhận: `"on"`, `"off"`, `"bật"`, `"tắt"`, `True`, `False`.

#### `_search.py`

```python
func(dataFB, keywordSearch)
```

Tìm kiếm người dùng. Trả về:

- `searchResults` — chuỗi đã format đẹp (cho bot/CLI).
- `searchResultsDict` — list các dict `{name, id, url}`.

#### `_blocking.py`

```python
func(dataFB, idUser, choiceInteract)
```

Chặn / bỏ chặn user. `choiceInteract`: `"block"` hoặc `"unblock"`.

#### `_registerOnProfile.py`

```python
func(dataFB, newName, newUsername)
```

Tạo **profile phụ** trên cùng tài khoản.

> ⚠️ Chỉ hoạt động trên một số tài khoản đủ điều kiện.

#### `_notification.py`

```python
func(dataFB)
```

Lấy danh sách thông báo.

- ✅ `{ "success": 1, "NotificationResults": [...] }`
- ❌ `{ "error": 1, "messages": ... }`

#### `_marketplace.py`

| Hàm | Mục đích |
|---|---|
| `createItem(dataFB, nameItem, brandItem, priceItem, currencyItem, decriptionItem, hashtagList, typeItem, photoIDList, locationSeller)` | Đăng sản phẩm Marketplace mới. `photoIDList` lấy từ `_messaging._attachments`. |
| `getInformationProductItemMarketPlace(dataFB, idProductItem)` | Lấy chi tiết sản phẩm theo ID. |

#### `_get_user_info.py`

```python
func(dataFB, userID)
```

Lấy thông tin người dùng qua endpoint chat user info.

- ✅ Dict thông tin chi tiết.
- ❌ `{ "err": 0 }`.

---

### `_thread` — Quản trị thread

| Module | Hàm | Mục đích |
|---|---|---|
| `_changeNameThread.py` | `func(dataFB, threadID, newNameThread)` | Đổi tên nhóm. |
| `_changeEmoji.py` | `func(dataFB, threadID, newEmoji)` | Đổi emoji mặc định của thread. |
| `_addAdmin.py` | `func(dataFB, threadID, idUser, statusChoice=True)` | Thêm / bỏ quyền admin. |
| `_changeNickname.py` | `func(dataFB, threadID, idUser, NewNickname)` | Đổi biệt danh thành viên. |

Tất cả trả về `formatResults("success" \| "error", message)` từ `_core._utils`.

#### `_all_thread_data.py`

| Hàm | Mục đích |
|---|---|
| `func(dataFB)` | Lấy danh sách INBOX + `last_seq_id`. Trả về `dataGet`, `ProcessingTime`, `last_seq_id`, `dataAllThread`. |
| `features(dataGet, threadID, commandUse)` | Bóc tách dữ liệu từ `dataGet`. `commandUse` ∈ `{"getAdmin", "threadInfomation", "exportMemberListToJson"}`. |

---

## 🔗 Sơ đồ phụ thuộc

`_features` chủ yếu phụ thuộc vào `_core`:

```text
_core._session.dataGetHome(setCookies)  →  dataFB
_core._utils  →  formAll · mainRequests · parse_cookie_string
                 Headers · formatResults · randStr
```

> ⚠️ Có thể gãy nếu Facebook đổi schema GraphQL hoặc `doc_id`.

---

## 💡 Ví dụ

```python
from _core._session import dataGetHome
from _features._facebook import _notification, _blocking
from _features._thread import _changeEmoji, _all_thread_data

dataFB = dataGetHome("c_user=...; xs=...;")

# Lấy thông báo
print(_notification.func(dataFB))

# Chặn người dùng
print(_blocking.func(dataFB, idUser="1000...", choiceInteract="block"))

# Đổi emoji nhóm
print(_changeEmoji.func(dataFB, threadID="1234567890", newEmoji="🔥"))

# Lấy toàn bộ inbox
threads = _all_thread_data.func(dataFB)
print(threads["dataAllThread"])
```

---

## 🛠 Khắc phục sự cố

| Triệu chứng | Hướng xử lý |
|---|---|
| Lỗi auth/session ở nhiều feature | Cookie hết hạn → tạo lại `dataFB`. |
| API trả lỗi hoặc rỗng dữ liệu | Endpoint / `doc_id` đã đổi; verify `variables` đúng schema mới. |
| Lỗi parse JSON response | Một số endpoint có tiền tố `for (;;);` — split trước khi `json.loads`. |

---

<div align="right">

⬆️ [Về README chính](../../README.md) · 🇬🇧 [English](README_EN.md)

</div>
