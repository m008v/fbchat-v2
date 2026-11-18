# Cài đặt và chạy lần đầu

[Bắt đầu](quickstart.md) · [Tin nhắn thường](../messaging/standard.md) · [E2EE](../messaging/e2ee.md) · [Facebook](../features/facebook-actions.md) · [Tra nhanh](../recipes/cheatsheet.md)

Trong trang này:

- [Cài package và kiểm tra session](#cài-package-và-kiểm-tra-session)
- [Làm việc với source](#làm-việc-với-source)
- [Tạo session và `dataFB`](#tạo-session-và-datafb)
- [Chọn bot mẫu](#chọn-bot-mẫu)
- [Bot mẫu `src/main.py`](#bot-mẫu-srcmainpy)
- [Session storage](#session-storage)

Dùng Python 3.10 trở lên. Các ví dụ bên dưới dùng `fbchat-v2==2.3.4`.
Đây là API Facebook không chính thức; endpoint, token HTML, GraphQL `doc_id`,
payload MQTT và protocol E2EE có thể đổi mà không báo trước.

Cookie, mật khẩu, access token, TOTP secret và toàn bộ `dataFB` là thông tin
nhạy cảm. Không đưa chúng vào issue, log, dữ liệu test hoặc commit Git.

## Cài package và kiểm tra session

```bash
python -m pip install "fbchat-v2==2.3.4"
```

Đặt cookie vào biến môi trường `FB_COOKIES` trên máy của bạn. Trong PowerShell:

```powershell
$env:FB_COOKIES = "c_user=...; xs=...; fr=...; datr=...;"
```

Thay giá trị mẫu bằng cookie phiên của bạn. Không gửi cookie cho người khác.
Lưu đoạn sau thành `check_session.py` và chạy `python check_session.py` trong
chính terminal vừa đặt biến môi trường. Ví dụ chỉ tạo session, chưa gửi tin nhắn:

```python
import asyncio

from fbchat_v2 import EnvSessionStorage, dataGetHome


async def main() -> None:
    data_fb = await dataGetHome(storage=EnvSessionStorage("FB_COOKIES"))
    if data_fb is None:
        raise RuntimeError("Không tạo được session Facebook.")
    print("Đã tạo session Facebook.")


if __name__ == "__main__":
    asyncio.run(main())
```

Sau khi có session, xem [gửi và nhận tin thường](../messaging/standard.md).
HTTP API và Python MQTT thường không cần Go. Cuộc trò chuyện E2EE cần
[bridge Go cùng phiên bản](../messaging/e2ee.md); bot mẫu `src/main.py` cũng bắt buộc E2EE.

Các ví dụ ngắn ở các trang còn lại dùng lại `data_fb` từ bước tạo session.
Đặt những lệnh có `await` trong coroutine của ứng dụng. Không chạy các ví dụ
xóa bài, block user hoặc đổi admin trên dữ liệu thật nếu chưa kiểm tra ID.

## Làm việc với source

```bash
git clone --recurse-submodules https://github.com/m008v/fbchat-v2.git
cd fbchat-v2
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

python -m pip install -e ".[dev]"
python scripts/verify_distribution.py
```

Sau khi cài ở chế độ editable, các script trong virtual environment có thể import `fbchat_v2`.
Không cần đặt `PYTHONPATH=src` hoặc thêm prefix `src.` vào import.

Sửa thư viện trong `src/_core`, `src/_features` và `src/_messaging`. Khi cài hoặc
build, package `fbchat_v2` được sinh vào `build/fbchat_v2`; thư mục này không
đưa vào Git. Sau khi sửa source, chạy `python scripts/sync_canonical_package.py`
hoặc cài editable lại để cập nhật package trước khi thử bot.

```python
from fbchat_v2._core._session import dataGetHome
from fbchat_v2._features._facebook import _search
from fbchat_v2._messaging._send import api as SendAPI
```

Ứng dụng không nên import các helper riêng như `_build_`, `_parse_` hoặc `_BridgeProcess`. Chúng phục vụ nội bộ và có thể thay đổi giữa các phiên bản.


## Tạo session và `dataFB`

API:

```python
async def dataGetHome(
    setCookies: str | None = None,
    storage: SessionStorage | None = None,
) -> dict[str, Any] | None:
    ...
```

### Từ chuỗi cookie

```python
from fbchat_v2._core._session import dataGetHome

data_fb = await dataGetHome("c_user=...; xs=...; fr=...; datr=...;")
if data_fb is None:
    raise RuntimeError("Không tạo được session Facebook.")
```

`dataGetHome()` tải trang chủ qua HTTPS, đọc token từ HTML và trả dict khi đủ các trường bắt buộc:

```python
{
    "fb_dtsg": "...",
    "fb_dtsg_ag": "...",       # Có thể không xuất hiện ở mọi response
    "jazoest": "...",
    "hash": "...",             # Có thể không xuất hiện ở mọi response
    "sessionID": "...",
    "FacebookID": "1000...",
    "clientRevision": "...",
    "cookieFacebook": "c_user=...; xs=...; ...",
}
```

Các trường bắt buộc là `fb_dtsg`, `jazoest`, `sessionID`, `FacebookID` và `clientRevision`. `FacebookID` phải là chuỗi số. Nếu thiếu cookie, request HTTP lỗi hoặc HTML không còn token cần thiết, hàm trả `None` và in chẩn đoán ngắn, không chứa cookie.

### Không log `dataFB`

Sai:

```python
print(data_fb)
logger.debug("session=%r", data_fb)
```

Đúng hơn:

```python
logger.info("Facebook session ready for uid=%s", data_fb["FacebookID"])
```


## Chọn bot mẫu

Bắt đầu với [echo cơ bản](../../examples/01_echo_bot.py), rồi thử
[quản lý nhóm](../../examples/02_group_manager.py) hoặc
[E2EE có Go bridge](../../examples/03_e2ee_bot.py).
[Hướng dẫn chạy](../../examples/README.md) ghi các biến môi trường và lệnh cho
từng mẫu. Mẫu echo có dưới 20 dòng; phần kết nối/cleanup dùng chung ở `_common.py`.

## Bot mẫu `src/main.py`

Chạy các lệnh sau từ thư mục gốc repo, sau khi đã cài editable ở mục
[Làm việc với source](#làm-việc-với-source):

```bash
python src/main.py
```

Lần đầu, bot tạo `src/config.json` nếu chưa có và yêu cầu bạn điền cookie.
Điền cấu hình theo ví dụ bên dưới rồi chạy lại lệnh. Cần bridge E2EE cùng
phiên bản; xem [cách tìm hoặc build binary](../messaging/e2ee.md#tìm-binary-bridge).

Bot mẫu minh họa cách khởi động, nhận tin và dừng listener. Đây không phải framework bot để dùng nguyên trạng khi triển khai.

Bot mẫu cần Go E2EE bridge và chỉ xử lý lệnh sau khi E2EE sẵn sàng. Nó kiểm tra readiness theo từng khoảng `startup_timeout` và tiếp tục chờ khi listener đang `reconnecting`; lỗi terminal khiến bot dừng. Bot không chuyển sang Python MQTT. Nếu chỉ cần listener MQTT thường, hãy khởi tạo `listeningEvent` riêng; đó không phải chế độ dự phòng của bot mẫu.

### Cấu hình

```json
{
  "prefix": "/",
  "cookies": "c_user=...; xs=...; fr=...; datr=...;",
  "admins": ["100012345678"],
  "log_message_content": false,
  "debug_errors": false
}
```

Cookie được giữ trong file riêng tư (`0600` trên POSIX hoặc ACL chỉ dành cho
user hiện tại/SYSTEM trên Windows). Nội dung chat và chi tiết exception bị che
mặc định; chỉ bật `log_message_content` hoặc `debug_errors` trong môi trường
debug được kiểm soát.

### Luồng runtime

1. `load_config()` siết quyền file và validate `prefix`, `admins` cùng hai cờ log.
2. `FileSessionStorage` đưa cookie vào `await dataGetHome(...)`.
3. `is_valid_datafb()` kiểm tra token bắt buộc.
4. Một `httpx.AsyncClient` được dùng lại cho command HTTP.
5. E2EE listener start thành task.
6. Callback bridge chuyển event về queue bằng `call_soon_threadsafe`.
7. Bot bỏ self-message, dedupe message ID và dispatch handler async.
8. Reply qua bridge theo event nhận được; startup vẫn bắt buộc hoàn tất E2EE.
9. Shutdown stop bridge, await listener task và đóng HTTP client.

### Command có sẵn

| Lệnh | Mục đích |
|---|---|
| `/ping` | Đo latency dựa trên timestamp event |
| `/help` | Liệt kê lệnh |
| `/id` | In type, chatJid, threadID, userID, senderJid, messageID |
| `/echo <text>` | Reply lại text |
| `/search <query>` | Gọi `_search.func` bằng HTTP client dùng chung |
| `/unsend` | Admin thu hồi tin E2EE cuối của bot trong chat |

Để thêm lệnh, viết async handler rồi đăng ký trong `self._handlers`. Không chạy tác vụ tính toán nặng ngay trong handler; hãy đưa chúng sang process pool hoặc worker phù hợp.


## Session storage

Ba class public:

| Class | Mục đích |
|---|---|
| `SessionStorage` | Interface `load`, `save`, `clear` |
| `FileSessionStorage` | Lưu cookie trong một key của file JSON |
| `EnvSessionStorage` | Đọc và ghi biến môi trường của tiến trình |

### File JSON local

```python
from fbchat_v2._core._session import dataGetHome
from fbchat_v2._core._storage import FileSessionStorage

storage = FileSessionStorage("src/config.json", key="cookies")
data_fb = await dataGetHome(storage=storage)
```

`FileSessionStorage.save()` ghi vào file tạm, flush, `fsync` rồi thay file bằng `os.replace()`. Cách này giảm nguy cơ file JSON bị ghi dở khi tiến trình dừng đột ngột. Cookie không được mã hóa; ứng dụng vẫn cần bảo vệ quyền truy cập file và quản lý thông tin nhạy cảm.

### Biến môi trường

```python
from fbchat_v2._core._session import dataGetHome
from fbchat_v2._core._storage import EnvSessionStorage

data_fb = await dataGetHome(storage=EnvSessionStorage("FB_COOKIES"))
```

Windows PowerShell:

```powershell
$env:FB_COOKIES = "c_user=...; xs=...; fr=...; datr=...;"
```

Biến môi trường giúp giữ thông tin nhạy cảm ngoài mã nguồn, nhưng tiến trình cùng quyền vẫn có thể đọc chúng. Khi triển khai, nên dùng công cụ quản lý secret của nền tảng đang chạy.

Xem [cách dùng asyncio](../recipes/cheatsheet.md#mô-hình-thực-thi-async),
[HTTP client dùng chung](../recipes/cheatsheet.md#http-transport-và-connection-pool)
và [đăng nhập bằng mật khẩu/2FA](../recipes/cheatsheet.md#login-credential-và-2fa)
khi cần tích hợp sâu hơn.
