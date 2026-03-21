# _features (`src/_features`)

`_features` là tầng triển khai các tính năng thao tác trực tiếp trên Facebook và tin nhắn. Thư mục này không xử lý phần nền tảng session/token như `_core`, mà tập trung vào logic nghiệp vụ cấp tính năng:

- Thao tác hồ sơ cá nhân (bio, bài viết, profile phụ, professional mode).
- Truy xuất dữ liệu người dùng và thông báo.
- Tìm kiếm Facebook, chặn/bỏ chặn người dùng.
- Tạo/lấy thông tin bài đăng Marketplace.
- Quản trị thread nhóm (đổi tên, emoji, nickname, thêm admin).

---

## 1) Sơ đồ thư mục

```text
src/_features/
├── _facebook/
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
├── _thread/
│   ├── __init__.py
│   ├── _addAdmin.py
│   ├── _all_thread_data.py
│   ├── _changeEmoji.py
│   ├── _changeNameThread.py
│   └── _changeNickname.py
└── README.md
```

### Export chính

`src/_features/_facebook/__init__.py` hiện export:

```python
__all__ = [
    "_changeBio",
    "_createPost",
    "_professional",
    "_search",
    "_blocking",
    "_registerOnProfile",
    "_notification",
    "_marketplace",
    "_get_user_info",
]
```

`src/_features/_thread/__init__.py` hiện export:

```python
__all__ = [
    "_changeNickname",
    "_addAdmin",
    "_changeEmoji",
    "_changeNameThread",
]
```

Nghĩa là bạn chỉ cần gọi `_thread` hoặc `_facebook` là có thể dùng được các ***module*** bên trong nó.

---

## 2) Nhiệm vụ chính (***QUAN TRỌNG***): `_features_`

### `_features` được ứng dụng để:

- Triển khai nghiệp vụ theo từng tính năng cụ thể.
- Tái sử dụng dữ liệu phiên `dataFB` từ `_core._session`.
- Tích hợp những tính năng quan trọng cho *tools*/*bot*.

---

## 3) Dữ liệu đầu vào chung (***QUAN TRỌNG***): `dataFB`

**!!** đa số các *functions* trong `_features` nhận `dataFB` làm tham số đầu tiên.

### Các giá trị thường được dùng:

- `fb_dtsg`
- `jazoest`
- `FacebookID`
- `clientRevision`
- `sessionID`
- `cookieFacebook`

`dataFB` được tạo từ `_core._session.dataGetHome(setCookies)`.

---

## 4) Tài liệu module chi tiết
(**QUAN TRỌNG**): `dataFB`: được xuất từ *_core._session* -> `dataGetHome(setCookies)`




## 4.1 `_features._facebook` | Nhóm *_facebook*


### `_changeBio.py`

- Hàm: `func(dataFB, newContents, uploadPost=False)`
- Mục đích: đổi bio tài khoản Facebook.
- Đầu vào:
  - `newContents`: nội dung bio mới.
  - `uploadPost`: có đăng feed khi đổi bio hay không.
- Đầu ra:
  - Thành công: `{ "success": 1, "messages": ... }`
  - Thất bại: `{ "error": 1, ... }`

### `_createPost.py`

- Hàm: `func(dataFB, newContents, attachmentID=None)`
- Mục đích: tạo bài viết mới trên timeline.
- Đầu vào:
  - `newContents`: nội dung bài viết.
  - `attachmentID`: tham số dự phòng, hiện chưa được dùng thực tế trong tính năng.
- Đầu ra:
  - Thành công: xuất `urlPost` đã tạo thành công.
  - Thất bại: trả `error` và message từ API.

### `_professional.py`

- Hàm: `func(dataFB, statusBusiness=None)`
- Mục đích: bật/tắt chế độ chuyên nghiệp trang cá nhân.
- Đầu vào:
  - `statusBusiness`: nhận `"on"`, `"off"`, `"bật"`, `"tắt"`, `True`, `False`.
- Đầu ra: dict `success` hoặc `error`.

### `_search.py`

- Hàm: `func(dataFB, keywordSearch)`
- Mục đích: tìm kiếm người dùng trên Facebook.
- Đầu vào:
  - `keywordSearch`: từ khóa tìm kiếm.
- Đầu ra:
  - `searchResults`: chuỗi định dạng đẹp (được xuất sẵn dành cho *tools*/*bot*).
  - `searchResultsDict`: danh sách dict gồm `name`, `id`, `url`.

### `_blocking.py`

- Hàm: `func(dataFB, idUser, choiceInteract)`
- Mục đích: chặn hoặc bỏ chặn người dùng.
- Đầu vào:
  - `choiceInteract`: `"block"` hoặc `"unblock"`.
- Đầu ra: dict `success`/`error` theo kết quả API.

### `_registerOnProfile.py`

- Hàm: `func(dataFB, newName, newUsername)`
- Mục đích: tạo profile phụ trên cùng tài khoản.
- Đầu vào:
  - `newName`: tên profile phụ.
  - `newUsername`: username profile phụ.
- Đầu ra:
  - Thành công: `{ "success": 1, ... }`
  - Lỗi nghiệp vụ/API: `{ "error": 1, ... }`
- ***LƯU Ý***: Tính năng này chỉ hoạt động trên một số tài khoản nhất định.

### `_notification.py`

- Hàm: `func(dataFB)`
- Mục đích: lấy danh sách thông báo.
- Đầu vào: không có.
- Đầu ra:
  - Thành công: `{ "success": 1, "NotificationResults": [...] }`
  - Thất bại: `{ "error": 1, "messages": ... }`

### `_marketplace.py`

- **Hàm 1**: `createItem(dataFB, nameItem, brandItem, priceItem, currencyItem, decriptionItem, hashtagList, typeItem, photoIDList, locationSeller)`
  - Mục đích: tạo bài đăng bán hàng trên Marketplace.
  - Đầu vào:
    - `nameItem`: tên sản phẩm.
    - `brandItem`: thương hiệu.
    - `priceItem`: giá sản phẩm.
    - `currencyItem`: đơn vị tiền tệ.
    - `decriptionItem`: mô tả sản phẩm.
    - `hashtagList`: danh sách hashtag.
    - `typeItem`: Phân loại sản phẩm.
    - `photoIDList`: Danh sách ID tệp đính kèm đã được tải lên thông qua *_messaging._attachments.py*
    - `locationSeller`: Vị trí của người bán hàng.
  - Đầu ra: `success` kèm `url`/`id` khi tải lên sản phẩm thành công, hoặc `error`.

- **Hàm 2**: `getInformationProductItemMarketPlace(dataFB, idProductItem)`
  - Mục đích: lấy chi tiết sản phẩm theo ID.
  - Đầu vào: `idProductItem`: ID sản phẩm cần lấy thông tin.
  - Đầu ra: dict chứa thông tin sản phẩm, giá, người bán, link, thời gian tạo.

### `_get_user_info.py`

- Hàm: `func(dataFB, userID)`
- Mục đích: lấy thông tin người dùng qua endpoint chat user info.
- Đầu vào:
  - `userID`: ID người dùng cần lấy thông tin.
- Đầu ra:
  - Thành công: dict chi tiết người dùng.
  - Thất bại: `{ "err": 0 }`.

---

## 4.2 `_features._thread` | Nhóm *_thread_*

### `_changeNameThread.py`

- Hàm: `func(dataFB, threadID, newNameThread)`
- Mục đích: đổi tên nhóm/chat thread.
- Đầu vào:
  - `newNameThread`: tên mới.
  - `threadID`: ID thread cần đổi tên.
- Đầu ra: chuẩn `formatResults(status, message)` từ `_core._utils`.

### `_changeEmoji.py`

- Hàm: `func(dataFB, threadID, newEmoji)`
- Mục đích: đổi emoji mặc định của thread.
- Đầu vào:
  - `newEmoji`: emoji mới.
  - `threadID`: ID thread cần đổi emoji.
- Đầu ra: `formatResults("success"|"error", message)`.

### `_addAdmin.py`

- Hàm: `func(dataFB, threadID, idUser, statusChoice=True)`
- Mục đích: thêm/bỏ quyền admin trong nhóm.
- Đầu vào:
  - `idUser`: ID người dùng cần thêm/bỏ quyền admin thread.
  - `threadID`: ID thread cần thêm/bỏ quyền admin thread.

- Đầu ra: `formatResults("success"|"error", message)`.

### `_changeNickname.py`

- Hàm: `func(datatFB, threadID, idUser, NewNickname)`
- Mục đích: đổi biệt danh thành viên trong thread.
- Đầu vào:
  - `threadID`: ID thread cần đổi nickname.
  - `idUser`: ID người dùng cần đổi nickname.
  - `NewNickname`: nickname mới.
- Đầu ra: `formatResults("success"|"error", message)`.

### `_all_thread_data.py`

- Hàm 1: `func(dataFB)`
  - Mục đích: lấy danh sách thread INBOX + *`last_seq_id`*.
  - Đầu vào: không có.
  - Đầu ra: gồm `dataGet`, `ProcessingTime`, `last_seq_id`, `dataAllThread`.

- Hàm 2: `features(dataGet, threadID, commandUse)`
  - Mục đích: bóc tách dữ liệu sâu từ `dataGet` theo lệnh.
  - `commandUse` hỗ trợ:
    - `"getAdmin"`
    - `"threadInfomation"`
    - `"exportMemberListToJson"`

---

## 5) Sơ đồ phụ thuộc trong dự án

`_features` phụ thuộc chính vào `_core._utils` và `dataFB`:

- `_core._session` -> `dataGetHome(setCookies)`
- `formAll`
- `mainRequests`
- `parse_cookie_string`
- `Headers`
- `formatResults`
- `randStr`

*WARNING*: Có thể xảy ra lỗi nếu Facebook thay đổi cấu trúc giá trị `graphql`

---

## 6) Mã nguồn mẫu

```python
from _features._facebook import *
from _features._thread import *


# Lấy thông báo Facebook (_core._facebook)

result = _notification.func(dataFB)
print(result)

# Chặn người dùng (_core._facebook)

result = _blocking.func(dataFB, idUser="1000...", choiceInteract="block")
print(result)

# Thay đổi emoji nhóm (_core._thread)

result = _changeEmoji.func(dataFB, threadID="1234567890", newEmoji="🔥")
print(result)

# 6.4 Lấy dữ liệu tổng thread (_core._thread)


threads = _all_thread_data.func(dataFB)
print(threads["dataAllThread"])
```

---

## 7) Lỗi có thể gặp và hướng xử lý

### TH.1: lỗi auth/session ở nhiều feature

- Kiểm tra cookie còn hạn hay không.
- Tạo lại `dataFB` từ `_core._session.dataGetHome(...)`.

### TH.2: API trả lỗi hoặc không có dữ liệu

- Endpoint/doc_id có thể đã đổi.
- Kiểm tra payload `variables` đúng schema hiện tại.

### TH.3: lỗi parse JSON phản hồi

- Một số endpoint trả dạng có tiền tố `for (;;);`.
- Cần split tiền tố trước `json.loads` (một số module đã làm sẵn).
