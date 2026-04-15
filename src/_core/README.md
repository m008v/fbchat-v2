# _core (`src/_core`)

`_core` là nền tảng kỹ thuật dùng chung cho toàn bộ codebase. Thư mục này không chứa tính năng người dùng cuối, mà chịu trách nhiệm:

- Khởi tạo phiên làm việc (session) từ cookie.
- Tạo payload/request cơ bản cho các endpoint Facebook.
- Phân tích cookie và trích xuất token động.
- Sinh ID phục vụ gửi/nhận tin nhắn.
- Cung cấp các hàm tiện ích dùng lại ở `_features` và `_messaging`.

---

## 1) Sơ đồ thư mục

```text
src/_core/
├── __init__.py
├── _session.py
├── _utils.py
├── _facebookLogin.py
├── README.md
├── README.md
└── README_EN.md 
```

### export chính

`src/_core/__init__.py` hiện export:

```python
__all__ = ["_session", "_utils", "_facebookLogin"]
```

Nghĩa là bạn chỉ cần gọi `_core` là có thể dùng được các ***module*** bên trong nó.

---

## 2) Nhiệm vụ chính (***QUAN TRỌNG***): `_core`

### `_core` được ứng dụng:

- Tạo header và form request dùng chung.
- Chuyển cookie string thành dict cho `requests`.
- Trích xuất các giá trị động từ homepage Facebook (`fb_dtsg`, `jazoest`, ...).
- Sinh ID runtime cho luồng gửi/nhận tin nhắn.
- Cung cấp hàm format/parse/tiện ích dùng chung. 

---

## 3) Dữ liệu chính (***QUAN TRỌNG***): `dataFB`

`_session.dataGetHome(setCookies)` trả về một dict thường được đặt tên là `dataFB`.

### Các giá trị được trả về:

- `fb_dtsg`
- `fb_dtsg_ag`
- `jazoest`
- `hash`
- `sessionID`
- `FacebookID`
- `clientRevision`
- `cookieFacebook`

Gần như tất cả module trong `_features/*` và `_messaging/*` đều phụ thuộc vào **những giá trị này**.

---

## 4) Tài liệu module chi tiết

## 4.1 `_session.py`

### Hàm: `dataGetHome(setCookies)`

Hàm này truy cập `https://www.facebook.com/` bằng cookie đã cung cấp, sau đó trích xuất các token/giá trị cần thiết để gọi API tiếp theo.

### Đầu vào

- `setCookies` (`str`): chuỗi cookie thô, ví dụ:
  - `"c_user=...; xs=...; fr=...; datr=...;"`

### Đầu ra

- `dict` theo cấu trúc `dataFB` ở trên.

### Quy trình hoạt động

1. Tạo header GET giống trình duyệt.
2. Đổi cookie string sang dict qua `_utils.parse_cookie_string`.
3. Tải HTML homepage.
4. Dùng `_utils.dataSplit` để cắt token.
5. Trả về dict session + cookie gốc.

### Lưu ý

- Cách trích xuất hiện tại dựa trên split marker trong HTML, có thể xảy ra lỗi khi Facebook thay đổi cấu trúc HTML
- Có thể dính **checkpoint**

---

## 4.2 `_utils.py`

Đây là module quan trọng nhất của `_core`, chứa nhiều hàm dùng chung.

### A) Nhóm hàm HTTP/request

- `Headers(dataForm=None, Host=None)`
  - Tạo bộ header cơ bản.
  - Có thể gắn `Content-Length` dựa theo độ dài `dataForm`.
- `parse_cookie_string(cookie_string)`
  - Chuyển cookie string thành dict cho `requests`.
- `mainRequests(urlRequests, dataForm, setCookies)`
  - Trả về kwargs sẵn để gọi `requests.post(**kwargs)`.

### B) Nhóm hàm parse/format

- `digitToChar(digit)`
- `str_base(number, base)`
- `dataSplit(...)`
  - Tách dữ liệu bằng delimiter.
- `clearHTML(text)`
  - Xóa thẻ HTML qua regex.
- `formatResults(type, text)`
  - Chuẩn hóa kết quả theo mẫu `{ "status": ..., "message": ... }`.

### C) Hàm tạo form tổng quát

- `formAll(dataFB, FBApiReqFriendlyName=None, docID=None, requireGraphql=None)`

Đây là hàm cốt sống của toàn bộ flow request.

Hàm tạo payload cơ bản cho endpoint Facebook theo 2 chế độ:

1. Chế độ GraphQL (`requireGraphql is None`)
   - Có `fb_api_req_friendly_name`, `doc_id`, `fb_api_caller_class`, ...
2. Chế độ tối giản/legacy (`requireGraphql != None`)
   - Chỉ giữ bộ trường cần cho endpoint không cần GraphQL.

### D) Nhóm hàm sinh ID cho messaging

- `generate_session_id()`
- `generate_client_id()`
- `gen_threading_id()`
- `json_minimal(data)`
- `_set_chat_on(value)`

Được dùng trong các module gửi tin, lắng nghe sự kiện.

### E) Nhóm hàm tiện ích khác

- `require_list(list_)`
- `get_files_from_paths(filenames)`
- `randStr(length)`

---

## 4.3 `_facebookLogin.py`

Module này xử lý đăng nhập Facebook bằng username/password.

### Thành phần công khai

- `class loginFacebook`
  - `__init__(username, password, AuthenticationGoogleCode=None)`
  - `main()` trả về dict thành công/thất bại.
- `GetToken2FA(key2Fa)`
  - Gọi `https://2fa.live/tok/...` để lấy mã OTP.
- `jsonResults(...)`
  - Chuẩn hóa cấu trúc dữ liệu đăng nhập.

### Khi đăng nhập **thành công**

- `success.setCookies`
- `success.accessTokenFB`
- `success.cookiesKey-ValueList`

### Khi đăng nhập **thất bại**

- `error.title`
- `error.description`
- `error.error_subcode`
- `error.error_code`
- `error.fbtrace_id`

### Cảnh báo bảo mật

- Module xử lý thông tin nhạy cảm: username/password/cookie/access token.
- ***Nên ưu tiên luồng đăng nhập bằng cookie khi triển khai thực tế.***
- Luồng đăng nhập có thể lỗi khi endpoint auth thay đổi.

---

## 5) Sơ đồ phụ thuộc trong dự án

`_core._utils` được import rộng rãi bởi:

- `src/_features/_facebook/*`
- `src/_features/_thread/*`
- `src/_messaging/*`

Những *function* thường được dùng nhiều nhất:

- `formAll`
- `mainRequests`
- `parse_cookie_string`
- `Headers`
- `formatResults`
- `gen_threading_id`, `generate_session_id`, `generate_client_id`
- `str_base`, `randStr`, `get_files_from_paths`

**CẢNH BÁO**: chỉ cần thay đổi logic core payload/cookie là ảnh hưởng đến phần lớn tính năng.

---

## 6) Mã nguồn mẫu

## 6.1 Khởi tạo `dataFB` từ cookie

```python
from _core._session import dataGetHome

setCookies = "c_user=...; xs=...; fr=...; datr=...;"
dataFB = dataGetHome(setCookies)

print(dataFB["FacebookID"])
print(dataFB["fb_dtsg"])
```

## 6.2 Tạo và gửi request GraphQL

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

## 6.3 Tạo payload tối giản (không GraphQL)

```python
from _core._utils import formAll

payload = formAll(dataFB, requireGraphql=False)
payload["message_id"] = "mid...."
```

---

## 7) Lỗi có thể gặp và hướng xử lý

### TH.1: nhiều request lỗi auth/session

- Kiểm tra lại cookie còn *LIVE* hay không.
- Chạy lại `_session.dataGetHome(...)` và xác minh các key bắt buộc.

### TH.2: trường parse ra giá trị fallback

- Khả năng cao là HTML homepage đã đổi.
<<<<<<< HEAD
- Cập nhật marker split trong `_session.py`.s
=======
- Cập nhật marker split trong `_session.py`.s
>>>>>>> 770781a6930055c51056b28b4dac0b20892d2ce5
