# `_core` — nền tảng async

`_core` quản lý HTTP transport, session Facebook, login credentials, storage và utility dùng chung. Code feature không nên tự dựng transport mới; ngoại lệ hiện tại là một số endpoint legacy của Facebook bắt buộc đi qua `requests`.

## Module

| File | Trách nhiệm |
|---|---|
| `_http.py` | `httpx.Client` / `httpx.AsyncClient`, timeout và chuẩn hóa kwargs |
| `_utils.py` | form Facebook, parser JSON, cookie, ID và helper request |
| `_session.py` | lấy token homepage thành `dataFB` |
| `_facebookLogin.py` | login credentials + 2FA cục bộ |
| `_storage.py` | abstraction lưu cookie/session |
| `_types.py` | type dùng chung |

## Tạo `dataFB`

```python
import asyncio

from _core._session import dataGetHome


async def main() -> None:
    data_fb = await dataGetHome("c_user=...; xs=...; fr=...; datr=...;")
    if data_fb is None:
        raise RuntimeError("Không tạo được session.")
    print(data_fb["FacebookID"])


asyncio.run(main())
```

Các field quan trọng: `fb_dtsg`, `jazoest`, `sessionID`, `FacebookID`, `clientRevision`, `cookieFacebook`. Toàn bộ dict là dữ liệu nhạy cảm.

## Transport dùng chung

```python
import httpx

from _core._utils import formAll, post_form_json_async

form = formAll(data_fb, "FriendlyName", "123456")
async with httpx.AsyncClient(timeout=30) as client:
    payload = await post_form_json_async(
        "https://www.facebook.com/api/graphql/",
        form,
        data_fb["cookieFacebook"],
        client=client,
    )
```

`post_form_json_async` gọi `raise_for_status()`, hỗ trợ prefix `for (;;);` và không sửa dict request của caller. Dùng `send_request_async` nếu cần đọc raw `httpx.Response`.

## Login và 2FA

```python
from _core._facebookLogin import loginFacebook

login = loginFacebook(
    "email@example.com",
    "password",
    AuthenticationGoogleCode="JBSWY3DPEHPK3PXP",
)
result = await login.main()
```

Phải cấu hình `FBCHAT_APP_ACCESS_TOKEN`. TOTP secret được tính ngay trên máy bằng `pyotp`; OTP 6–8 số cũng được chấp nhận trực tiếp. Module không gọi `2fa.live`, không hardcode app secret và không in password/request form. Credential login dùng form/header FB4A legacy và `requests` dưới hood; `main()` bọc phần I/O này bằng worker thread.

## Quy tắc phát triển

- Feature có I/O phải cung cấp API `_async`; ưu tiên `httpx.AsyncClient`, trừ endpoint legacy đã có bằng chứng cần `requests`.
- Cho phép inject `client=` để test và tái sử dụng connection pool.
- Đặt timeout hữu hạn, gọi `raise_for_status()` và parse response thiếu field an toàn.
- Không tắt TLS verification.
- Không log `dataFB`, cookie, password, OTP secret hoặc access token.
- API sync là compatibility layer; không gọi trong event loop.

## Xử lý lỗi

| Hiện tượng | Kiểm tra |
|---|---|
| `dataGetHome()` trả `None` | Cookie hết hạn, mạng lỗi hoặc marker HTML đổi |
| HTTP 401/403 | Cookie/token không còn hợp lệ |
| Login trả code `-4` | Thiếu `FBCHAT_APP_ACCESS_TOKEN` |
| Login yêu cầu 2FA | Truyền TOTP secret hoặc OTP hiện hành |
| JSON parse lỗi | Facebook đổi endpoint/prefix/response schema |
