# fbchat-v2 - Async API guide

Tài liệu này mô tả API hiện hành. Mọi ví dụ mạng đều dùng `async`/`await`; API sync chỉ còn để tương thích code cũ.

## 1. Quy tắc event loop

Ứng dụng CLI có thể dùng một `asyncio.run()` duy nhất ở entry point:

```python
import asyncio


async def main() -> None:
    ...


asyncio.run(main())
```

FastAPI, Quart, Jupyter và các bot framework đã có event loop: chỉ dùng `await`, không lồng thêm `asyncio.run()`.

## 2. Tạo session

```python
from _core._session import dataGetHome

data_fb = await dataGetHome("c_user=...; xs=...; fr=...; datr=...;")
if data_fb is None:
    raise RuntimeError("Không tạo được session Facebook.")
```

`data_fb` chứa cookie và token CSRF (`fb_dtsg`, `jazoest`, `sessionID`, `FacebookID`, `clientRevision`). Không log hoặc serialize object này vào nơi công khai.

Khi lưu cookie trong bot mẫu:

```python
from _core._session import dataGetHome
from _core._storage import FileSessionStorage

storage = FileSessionStorage("src/config.json", key="cookies")
data_fb = await dataGetHome(storage=storage)
```

`src/config.json` phải nằm trong `.gitignore`.

## 3. Tái sử dụng HTTP connection

Các feature mới chấp nhận `client=`. Dùng một `httpx.AsyncClient` cho một workflow nhiều request:

```python
import httpx

from _features._facebook import _notification, _search

async with httpx.AsyncClient(timeout=30) as client:
    notifications = await _notification.func(data_fb, client=client)
    users = await _search.func(data_fb, "Minh Huy", client=client)
```

Client do caller tạo thì caller đóng. Nếu bỏ `client=`, thư viện tự quản lý client cho từng lời gọi.

## 4. Gửi tin nhắn

```python
from _messaging._send import api as SendAPI

sender = SendAPI()
result = await sender.send(
    data_fb,
    "Nội dung",
    threadID="100012345678",
    typeChat="user",          # None nếu là group thread
    typeAttachment=None,
    attachmentID=None,
    replyMessage=False,
    messageID=None,
)
```

Mỗi lời gọi tự xây form cục bộ nên kết quả trả về an toàn khi nhiều coroutine gửi đồng thời. Thuộc tính `sender.results` chỉ là snapshot của lời gọi hoàn tất gần nhất; logic ứng dụng phải dùng giá trị được `return`.

## 5. Upload và gửi attachment

```python
from _messaging import _attachments
from _messaging._send import api as SendAPI

uploaded = await _attachments.func("photo.jpg", data_fb)
if not uploaded or not uploaded.get("attachmentID"):
    raise RuntimeError("Upload thất bại.")

result = await SendAPI().send(
    data_fb,
    "Ảnh đính kèm",
    threadID="100012345678",
    typeChat="user",
    typeAttachment="image",
    attachmentID=uploaded["attachmentID"],
)
```

Luôn kiểm tra file tồn tại và response có `attachmentID`. File handle được đóng sau request.

## 6. Listener MQTT

```python
import asyncio

from _messaging._listening import listeningEvent

listener = listeningEvent(data_fb, message_queue_maxsize=1000)
task = asyncio.create_task(listener.connect_mqtt())
try:
    while True:
        event = await listener.get_message(timeout=30)
        if event is not None:
            print(event["body"], event["replyToID"])
finally:
    await listener.disconnect()
    await task
```

Event có các field `body`, `timestamp`, `userID`, `messageID`, `replyToID`, `type`, `attachments`. Queue đầy sẽ bỏ event cũ nhất và tăng `droppedMessages`.

Reconnect được xử lý bằng vòng lặp ngoài callback. Không tự gọi lại `connect_mqtt()` từ callback vì cách đó tích lũy stack và tạo nhiều MQTT client.

## 7. Sửa, reaction và thu hồi

```python
from _messaging import _editMessage, _reactions, _unsend

edited = await _editMessage.func(data_fb, "mid.$...", "Nội dung mới")
reacted = await _reactions.func(data_fb, "ADD_REACTION", "mid.$...", "❤")
removed = await _unsend.func("mid.$...", data_fb)
```

Sửa tin và đổi theme publish LS task qua `paho-mqtt`. Adapter async đưa phần blocking của thư viện MQTT sang worker thread; đây không phải HTTP async giả.

## 8. Note và theme

```python
from _messaging import _changeTheme, _createNotes

themes = await _changeTheme.listThemes(data_fb)
changed = await _changeTheme.changeTheme(data_fb, "thread-id", "Love")

current = await _createNotes.checkNote(data_fb)
created = await _createNotes.createNote(data_fb, "Đang viết bot", privacy="FRIENDS")
deleted = await _createNotes.deleteNote(data_fb, "note-id")
```

## 9. Feature Facebook

| Module | Async API chính | Mục đích |
|---|---|---|
| `_changeBio` | `func(data_fb, newContents)` | Đổi bio |
| `_createPost` | `func(data_fb, newContents)` | Tạo bài timeline |
| `_professional` | `func(data_fb, statusBusiness)` | Bật/tắt professional mode |
| `_search` | `func(data_fb, keywordSearch)` | Tìm người dùng |
| `_blocking` | `func(data_fb, idUser, choiceInteract)` | Chặn/bỏ chặn |
| `_registerOnProfile` | `func(data_fb, newName, newUsername)` | Tạo profile bổ sung |
| `_notification` | `func(data_fb)` | Lấy thông báo |
| `_get_user_info` | `func(data_fb, userID)` | Lấy thông tin người dùng |
| `_marketplace` | `createItem(...)` | Đăng sản phẩm |
| `_marketplace` | `getInformationProductItemMarketPlace(...)` | Đọc sản phẩm |

`_createPost.attachmentID` chưa có schema Composer ổn định. Nếu truyền giá trị, API ném `NotImplementedError` thay vì âm thầm bỏ attachment.

Ví dụ:

```python
from _features._facebook import _blocking, _professional, _search

profile = await _professional.func(data_fb, True)
users = await _search.func(data_fb, "m008v")
blocked = await _blocking.func(data_fb, "100012345678", "block")
```

## 10. Quản lý thread

```python
from _features._thread import (
    _addAdmin,
    _all_thread_data,
    _changeEmoji,
    _changeNameThread,
    _changeNickname,
)

threads = await _all_thread_data.func(data_fb)
info = await _all_thread_data.features(
    threads["dataGet"], "thread-id", "threadInfomation"
)
await _addAdmin.func(data_fb, "thread-id", "user-id", statusChoice=True)
await _changeEmoji.func(data_fb, "thread-id", "🔥")
await _changeNameThread.func(data_fb, "thread-id", "Tên mới")
await _changeNickname.func(data_fb, "thread-id", "user-id", "Biệt danh")
```

`statusChoice=False` thực sự gỡ admin và response sẽ ghi đúng hành động.

## 11. E2EE

```python
import asyncio

from _messaging._listening_e2ee import listeningE2EEEvent

listener = listeningE2EEEvent(data_fb)
task = asyncio.create_task(listener.connect_mqtt())
try:
    await listener.send_e2ee_message(
        "100012345678@msgr",
        "Xin chào",
    )
finally:
    listener.stop()
    await task
```

Các action bridge khác trong `BridgeActions` dùng tên async không hậu tố: edit, unsend, typing, mark-read, gửi audio/image và download media.

Bridge tự tải chỉ nhận asset từ GitHub Releases, giới hạn 200 MiB, ghi file tạm rồi replace atomically và kiểm tra SHA-256 khi GitHub cung cấp digest. Môi trường production nên pin binary đã kiểm tra bằng `FBCHAT_E2EE_BIN`.

## 12. Login credentials và TOTP

```powershell
$env:FBCHAT_APP_ACCESS_TOKEN = "<optional-override>"
```

```python
from _core._facebookLogin import loginFacebook

login = loginFacebook(
    "email@example.com",
    "password",
    AuthenticationGoogleCode="JBSWY3DPEHPK3PXP",
)
result = await login.main()
```

- `FBCHAT_APP_ACCESS_TOKEN` và `FBCHAT_API_KEY` chỉ là override tùy chọn; mặc định FB4A legacy đã có sẵn trong module.
- Có thể truyền trực tiếp OTP 6-8 số hoặc TOTP secret.
- TOTP được tính cục bộ bằng `pyotp`, không gửi secret ra ngoài.
- Facebook checkpoint hoặc thay đổi subcode có thể làm login credentials thất bại; cookie session vẫn là luồng ưu tiên.

## 13. Timeout, lỗi và hủy tác vụ

```python
import asyncio

try:
    result = await asyncio.wait_for(_search.func(data_fb, "query"), timeout=20)
except asyncio.TimeoutError:
    result = {"error": 1, "messages": "Quá thời gian tìm kiếm."}
```

Không bắt `Exception` rồi bỏ qua. Tại boundary của bot, log loại lỗi và thông tin không nhạy cảm; tuyệt đối không log password, cookie, request form login hoặc access token.

## 14. Kiểm tra trước khi commit

```powershell
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
git diff --check
go test ./...
```

Ngoài test tự động, quét UTF-8 để chắc chắn không có U+FFFD, NUL hoặc các chuỗi mojibake phổ biến (ví dụ cặp codepoint U+00F0/U+0178) trước khi push.

## 15. API sync tương thích

Các tên `dataGetHome`, `func`, `send`, `connect_mqtt` vẫn tồn tại cho script đồng bộ. Không gọi chúng trong coroutine vì chúng có thể chặn event loop. Tài liệu mới chỉ dùng async API; tham chiếu sync trong release notes cũ là lịch sử, không phải khuyến nghị hiện hành.
