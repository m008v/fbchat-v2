# Tra nhanh và xử lý lỗi

[Bắt đầu](../getting-started/quickstart.md) · [Tin nhắn thường](../messaging/standard.md) · [E2EE](../messaging/e2ee.md) · [Facebook](../features/facebook-actions.md) · [Tra nhanh](cheatsheet.md)

Trong trang này:

- [Mô hình thực thi async](#mô-hình-thực-thi-async)
- [HTTP transport và connection pool](#http-transport-và-connection-pool)
- [Login credential và 2FA](#login-credential-và-2fa)
- [Timeout, lỗi và cancellation](#timeout-lỗi-và-cancellation)
- [Hợp đồng kết quả](#hợp-đồng-kết-quả)
- [Chuyển từ sync sang async](#chuyển-từ-sync-sang-async)
- [Kiểm tra chất lượng](#kiểm-tra-chất-lượng)
- [FAQ và troubleshooting](#faq-và-troubleshooting)

Chọn việc cần làm:

- [Tạo session, cấu hình bot mẫu](../getting-started/quickstart.md).
- [Gửi text, upload file, reaction, theme và Notes](../messaging/standard.md).
- [Callback, readiness, reconnect và media E2EE](../messaging/e2ee.md).
- [Bài viết, user và quản lý nhóm](../features/facebook-actions.md).

## Mô hình thực thi async

Ứng dụng CLI nên có đúng một `asyncio.run()` tại entry point:

```python
import asyncio


async def main() -> None:
    ...


if __name__ == "__main__":
    asyncio.run(main())
```

FastAPI, Quart, Jupyter, Discord bot và nhiều framework khác đã có event loop. Trong môi trường đó, gọi trực tiếp:

```python
data_fb = await dataGetHome(cookie)
result = await _search.func(data_fb, "Minh")
```

Không gọi `asyncio.run()` bên trong coroutine. Python sẽ báo `RuntimeKết quả lỗi: asyncio.run() cannot be called from a running event loop`, đồng thời coroutine chưa await có thể sinh warning.

### Boundary blocking hợp lệ

Không phải thư viện nào cũng cung cấp API asyncio:

- `paho-mqtt` dùng vòng lặp blocking.
- Bridge E2EE dùng hàng đợi response và subprocess pipe blocking.
- Credential login cũ dùng `requests`.

Wrapper chạy các phần blocking này qua `asyncio.to_thread()` để không chặn event loop. API HTTP mới dùng `httpx.AsyncClient`; thread adapter chỉ dành cho những phần blocking còn cần giữ lại.


## HTTP transport và connection pool

`_core._http` cung cấp các hàm HTTP dùng chung:

```python
await post_async(request_kwargs, client=client)
await get_async(request_kwargs, client=client)
```

`_core._utils` bổ sung các hàm gửi request theo định dạng Facebook:

```python
await send_request_async(request_kwargs, client=client)
await send_get_request_async(request_kwargs, client=client)
await post_form_json_async(
    url,
    data_form,
    cookie,
    strip_for_loop_prefix=True,
    client=client,
)
```

### Tái sử dụng một client

```python
import asyncio
import httpx

from fbchat_v2._features._facebook import _notification, _search

async with httpx.AsyncClient(
    timeout=httpx.Timeout(30.0, connect=10.0),
    follow_redirects=True,
) as client:
    notifications, users = await asyncio.gather(
        _notification.func(data_fb, client=client),
        _search.func(data_fb, "m008v", client=client),
    )
```

Lợi ích:

- Tái sử dụng kết nối TCP/TLS.
- Đặt timeout và proxy ở một chỗ.
- Có thể truyền `httpx.MockTransport` khi test.
- Đóng tài nguyên cùng vòng đời ứng dụng.

### Quyền sở hữu client

- Nếu bạn truyền `client=`, bạn chịu trách nhiệm đóng client.
- Nếu không truyền `client=`, helper tự tạo và đóng client cho lần gọi đó.
- Không dùng client sau khi thoát `async with`.
- Không chia sẻ một client giữa nhiều event loop ở các thread khác nhau.

Transport sao chép request kwargs trước khi bỏ `url`, `verify`, `timeout`, nên không sửa dict mà ứng dụng truyền vào.


## Login credential và 2FA

Nên dùng cookie phiên có sẵn. Đăng nhập bằng thông tin tài khoản dễ gặp checkpoint, giới hạn tần suất hoặc thay đổi mã lỗi từ Facebook.

```python
from fbchat_v2._core._facebookLogin import loginFacebook

login = loginFacebook(
    "email@example.com",
    "password",
    AuthenticationGoogleCode="JBSWY3DPEHPK3PXP",
)
result = await login.main()
```

`AuthenticationGoogleCode` nhận một trong hai dạng:

- OTP hiện hành gồm 6 đến 8 chữ số.
- TOTP shared secret để module tạo OTP cục bộ bằng `pyotp`.

`login.main()` chạy phần đăng nhập cũ dùng `requests` trên worker thread để không chặn event loop. Phần này vẫn là xử lý blocking, không phải HTTP async.

### FB4A defaults và override

Module có API key và app access token mặc định cho luồng FB4A cũ. Chỉ ghi đè khi Facebook hoặc môi trường test yêu cầu:

```powershell
$env:FBCHAT_API_KEY = "<optional-override>"
$env:FBCHAT_APP_ACCESS_TOKEN = "<optional-override>"
```

Không ghi giá trị bí mật thật vào mã nguồn hoặc `.env.example`.

### Kết quả login

Kết quả thành công thường chứa cookie đã xuất và trạng thái đăng nhập. Khi có lỗi, đọc message, code và subcode Facebook trả về. Code hiện xử lý các continuation subcode `1348162` và `1348023`; chúng có thể thay đổi.

TOTP secret không được gửi tới `2fa.live` hoặc dịch vụ bên thứ ba.

## Timeout, lỗi và cancellation

Các đoạn dưới dùng lại `data_fb` đã tạo trong quickstart. Với ví dụ tìm kiếm
và notification, import hai module trước:

```python
from fbchat_v2._features._facebook import _notification, _search
```

### Timeout một feature

```python
import asyncio

try:
    result = await asyncio.wait_for(
        _search.func(data_fb, "query"),
        timeout=20,
    )
except asyncio.TimeoutError:
    result = {"error": 1, "messages": "Quá thời gian tìm kiếm."}
```

### Structured concurrency

Với Python 3.11+:

```python
async with asyncio.TaskGroup() as group:
    notification_task = group.create_task(_notification.func(data_fb))
    search_task = group.create_task(_search.func(data_fb, "Minh"))

notifications = notification_task.result()
users = search_task.result()
```

Nếu một task fail, `TaskGroup` cancel task còn lại và gom lỗi thành `ExceptionGroup`.

### Cleanup khi cancel

Luôn đặt cleanup listener và client trong `finally` hoặc context manager. Không bắt `asyncio.CancelledError` rồi nuốt, vì ứng dụng sẽ không shutdown đúng.

```python
try:
    await bot.run()
finally:
    listener.stop()
```

### Log an toàn

Log loại exception và tên thao tác, không log provider ID/JID, request form, cookie, access token, mật khẩu hoặc TOTP. Logger của bridge và bộ đọc stderr Python đều che metadata nhạy cảm trước khi in. Bật `debug_errors` cũng không nên làm lộ nội dung chat.

Go logger và Python stderr drain giới hạn dòng thô ở 64 KiB. Dòng vượt ngưỡng
bị bỏ toàn bộ đến newline, chỉ phát diagnostic cố định; không in prefix/tail
có thể chứa secret. Python vẫn drain khi tắt log và giữ đúng UTF-8 qua ranh giới
chunk. E2EE typing dùng deadline 10 giây, nhận cancellation từ lifecycle client.
Media giải mã được ghi vào temp file có quyền riêng ngay khi tạo, gồm DACL
protected trên Windows.


## Hợp đồng kết quả

Các module lịch sử chưa có một dataclass chung, nhưng thường dùng hai schema:

Kết quả thành công:

```python
{
    "success": 1,
    "payload": {...},
}
```

Kết quả lỗi:

```python
{
    "error": 1,
    "messages": "...",
    "payload": {...},
}
```

Một số feature trả key domain-specific như `NotificationResults`, `searchResultsDict`, `messageRequests` hoặc `urlPost`. Vì endpoint private không ổn định, caller nên:

```python
if not isinstance(result, dict):
    raise TypeError("API không trả dict.")
if result.get("error"):
    ...
```

Không chỉ kiểm tra HTTP status. Facebook thường trả HTTP 200 nhưng body chứa `error`, `errors` hoặc metadata null.


## Chuyển từ sync sang async

### Session

Trước:

```python
data_fb = dataGetHome(cookie)
```

Hiện tại:

```python
data_fb = await dataGetHome(cookie)
```

### Feature module

Trước:

```python
result = _search.func(data_fb, "Minh")
```

Hiện tại:

```python
result = await _search.func(data_fb, "Minh")
```

### Send

Trước:

```python
result = sender.send(data_fb, "hello", user_id, typeChat="user")
```

Hiện tại:

```python
result = await sender.send(data_fb, "hello", user_id, typeChat="user")
```

### Listener

Trước thường start `connect_mqtt` bằng `threading.Thread`. Hiện tại:

```python
listener_task = asyncio.create_task(listener.connect_mqtt())
event = await listener.get_message(timeout=30)
```

Không tìm `func_async`; alias đó đã được loại bỏ. Helper blocking còn tồn tại ở một số class với hậu tố `_blocking`, nhưng application async không gọi chúng trực tiếp.


## Kiểm tra chất lượng

Pytest giống CI:

```bash
pytest tests/ -v --tb=short
```

Lint, format và compile:

```bash
ruff check src tests scripts
black --check src tests scripts
mypy
python -m compileall -q src tests scripts
python -m build --wheel
python scripts/verify_distribution.py dist/fbchat_v2-2.3.4-py3-none-any.whl
git diff --check
```

CI còn cài riêng wheel và sdist vào virtual environment sạch để xác minh namespace
`fbchat_v2`, module lồng sâu và các public export như `_unFriend`.

Bridge:

```bash
cd bridge-e2ee
go test ./...
go vet ./...
```

Trước push, quét mọi file text tracked để phát hiện UTF-8 invalid, U+FFFD, NUL và mojibake thật. PowerShell hiển thị sai encoding không tự động có nghĩa file đã hỏng.

## FAQ và troubleshooting

### `dataGetHome()` trả `None`

Kiểm tra:

1. Cookie có `c_user`, `xs`, `fr`, `datr` và chưa hết hạn.
2. Tài khoản không bị checkpoint.
3. Mạng/proxy truy cập được `https://www.facebook.com/`.
4. Facebook có còn trả các token homepage mà parser cần hay không.

Không in cookie để debug. Chỉ log danh sách tên cookie hoặc tên field thiếu.

### `RuntimeWarning: coroutine was never awaited`

Một hàm async đã bị gọi như sync:

```python
listener.connect_mqtt()  # Sai nếu không await hoặc create_task
```

Sửa:

```python
task = asyncio.create_task(listener.connect_mqtt())
```

Không truyền coroutine trực tiếp làm target của `threading.Thread`.

### `'coroutine' object has no attribute 'get'`

Kết quả coroutine chưa được await:

```python
info = bridge.call("connect")
user = info.get("user")
```

Sửa:

```python
info = await bridge.call("connect")
user = info.get("user", {})
```

Code blocking nội bộ phải gọi `call_blocking()`, không gọi async method rồi đọc như dict.

### Upload trả `metadata: {"0": null}`

Facebook không trả attachment metadata. Kiểm tra session, file, MIME, endpoint và response error. Bật `include_error=True` để nhận excerpt có giới hạn. Không lấy `uploadID` làm `attachmentID`.

### Listener E2EE không nhận command

Kiểm tra:

1. Callback đã đăng ký trước khi start listener.
2. `wait_until_connected(..., require_e2ee=True)` trả `True`.
3. Ứng dụng xử lý cả `e2eeMessage` và `message`.
4. Callback đã chuyển event về event loop bằng `call_soon_threadsafe`.
5. Bot không bỏ nhầm message vì self-ID, prefix hoặc dedupe.
6. `listener_task` chưa kết thúc với exception.

### Bridge binary không tìm thấy

Build từ source:

```bash
git submodule update --init --recursive bridge-e2ee/meta
cd bridge-e2ee
go mod download
mkdir -p ../build
go build -o ../build/fbchat-bridge-e2ee .
```

Trên Windows thêm `.exe`. Hoặc set `FBCHAT_E2EE_BIN` tới file tuyệt đối đã tồn tại.

### Bridge liên tục respawn

Watchdog dùng retry policy và báo `bridge_fatal` khi hết budget đã cấu hình hoặc gặp lỗi không thể tự phục hồi. Đọc `connection_status` trước: `auth_required` cần cập nhật phiên, `protocol` cần build bridge đúng source, còn `device_state_lost` nghĩa là state memory-only không còn sau process crash. Không start thêm listener để che lỗi; chờ task cũ dừng hẳn trước.

### Login credential báo code `-1`

Đây thường là response transport/schema không khớp hoặc Facebook không trả error code chuẩn. Đọc description đã sanitize, kiểm tra override env và thử cookie session. Không suy diễn `-1` thành sai password nếu chưa có evidence từ response.

### `All Thread Data: 0` hoặc lỗi index

Không index thẳng response GraphQL. Kiểm tra `result.get("error")`, `dataGet` và object batch `o0`. Facebook có thể trả error object thay vì danh sách thread.

### `Get Notifications: slice(None, 2, None)`

Code caller đang slice một dict như list. Kết quả notification là dict có key `NotificationResults`; lấy list trước:

```python
result = await _notification.func(data_fb)
items = result.get("NotificationResults", [])
print(items[:2])
```

### Có nên dùng API blocking không?

Chỉ tại entry point sync hoặc integration chưa có event loop. Trong coroutine, ưu tiên API async. Nếu phải gọi thư viện legacy không có wrapper, đặt boundary rõ ràng bằng `asyncio.to_thread()` và không chia sẻ object không thread-safe.


Chi tiết theo module:

- [`src/_core/README.md`](../../src/_core/README.md)
- [`src/_features/README.md`](../../src/_features/README.md)
- [`src/_messaging/README.md`](../../src/_messaging/README.md)
- [`bridge-e2ee/README.md`](../../bridge-e2ee/README.md)
