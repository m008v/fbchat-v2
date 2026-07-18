# fbchat-v2 - Tài liệu API async

Tài liệu này mô tả API hiện hành trên nhánh `beta-async/await`. Các ví dụ I/O mới đều dùng `async`/`await`; API blocking chỉ được nhắc đến khi cần giải thích boundary hoặc hỗ trợ code legacy.

> [!NOTE]
> Đây là API Facebook không chính thức. Endpoint, token HTML, GraphQL `doc_id`, MQTT payload và E2EE protocol có thể thay đổi mà không báo trước.

> [!WARNING]
> Cookie, password, access token, TOTP secret và toàn bộ `dataFB` là secret. Không đưa chúng vào issue, log, test fixture thật hoặc commit Git.

## Mục lục

1. [Mô hình thực thi async](#1-mô-hình-thực-thi-async)
2. [Cài đặt và import](#2-cài-đặt-và-import)
3. [Tạo session và `dataFB`](#3-tạo-session-và-datafb)
4. [Session storage](#4-session-storage)
5. [HTTP transport và connection pool](#5-http-transport-và-connection-pool)
6. [Login credential và 2FA](#6-login-credential-và-2fa)
7. [Gửi tin nhắn thường](#7-gửi-tin-nhắn-thường)
8. [Upload và gửi attachment](#8-upload-và-gửi-attachment)
9. [Listener MQTT thường](#9-listener-mqtt-thường)
10. [Listener E2EE](#10-listener-e2ee)
11. [Gửi và thao tác qua bridge](#11-gửi-và-thao-tác-qua-bridge)
12. [Sửa, reaction và thu hồi tin thường](#12-sửa-reaction-và-thu-hồi-tin-thường)
13. [Theme và Messenger Notes](#13-theme-và-messenger-notes)
14. [Tính năng Facebook](#14-tính-năng-facebook)
15. [Quản lý thread](#15-quản-lý-thread)
16. [Bot mẫu `src/main.py`](#16-bot-mẫu-srcmainpy)
17. [Timeout, lỗi và cancellation](#17-timeout-lỗi-và-cancellation)
18. [Hợp đồng kết quả](#18-hợp-đồng-kết-quả)
19. [Chuyển từ sync sang async](#19-chuyển-từ-sync-sang-async)
20. [Kiểm tra chất lượng](#20-kiểm-tra-chất-lượng)
21. [FAQ và troubleshooting](#21-faq-và-troubleshooting)

---

## 1. Mô hình thực thi async

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

Không gọi `asyncio.run()` bên trong coroutine. Python sẽ báo `RuntimeError: asyncio.run() cannot be called from a running event loop`, đồng thời coroutine chưa await có thể sinh warning.

### Boundary blocking hợp lệ

Không phải thư viện nào cũng cung cấp API asyncio:

- `paho-mqtt` dùng vòng lặp blocking.
- Bridge E2EE dùng hàng đợi response và subprocess pipe blocking.
- Credential login cũ dùng `requests`.

Các boundary này được cô lập bằng `asyncio.to_thread()` trong wrapper. Feature HTTP mới không được bọc `requests` bằng thread để giả async; chúng phải dùng `httpx.AsyncClient` thật.

---

## 2. Cài đặt và import

```bash
git clone --branch beta-async/await --recurse-submodules https://github.com/MinhHuyDev/fbchat-v2.git
cd fbchat-v2
python -m venv .venv
python -m pip install -e ".[dev]"
```

Editable install làm cho các package `_core`, `_features` và `_messaging` import được từ mọi script trong virtual environment.

```python
from _core._session import dataGetHome
from _features._facebook import _search
from _messaging._send import api as SendAPI
```

Không import private helper bắt đầu bằng `_build_`, `_parse_` hoặc `_BridgeProcess` trong application code. Chúng là implementation detail và có thể đổi giữa các bản.

---

## 3. Tạo session và `dataFB`

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
from _core._session import dataGetHome

data_fb = await dataGetHome("c_user=...; xs=...; fr=...; datr=...;")
if data_fb is None:
    raise RuntimeError("Không tạo được session Facebook.")
```

`dataGetHome()` gọi homepage bằng HTTPS, parse token và chỉ trả dict khi các field bắt buộc hợp lệ:

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

Các field bắt buộc hiện tại là `fb_dtsg`, `jazoest`, `sessionID`, `FacebookID` và `clientRevision`. `FacebookID` phải là chuỗi số. Nếu cookie thiếu, HTTP lỗi hoặc HTML không còn token, hàm trả `None` và in chẩn đoán ngắn không chứa cookie.

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

---

## 4. Session storage

Ba class public:

| Class | Mục đích |
|---|---|
| `SessionStorage` | Interface `load`, `save`, `clear` |
| `FileSessionStorage` | Lưu cookie trong một key của file JSON |
| `EnvSessionStorage` | Đọc và ghi biến môi trường của tiến trình |

### File JSON local

```python
from _core._session import dataGetHome
from _core._storage import FileSessionStorage

storage = FileSessionStorage("src/config.json", key="cookies")
data_fb = await dataGetHome(storage=storage)
```

`FileSessionStorage.save()` ghi file tạm, flush, `fsync` rồi `os.replace()`. Cách này giảm nguy cơ JSON bị cắt khi process bị dừng giữa lúc ghi. Nó không mã hóa cookie; quyền truy cập file và secret management vẫn là trách nhiệm của ứng dụng.

### Biến môi trường

```python
from _core._session import dataGetHome
from _core._storage import EnvSessionStorage

data_fb = await dataGetHome(storage=EnvSessionStorage("FB_COOKIES"))
```

Windows PowerShell:

```powershell
$env:FB_COOKIES = "c_user=...; xs=...; fr=...; datr=...;"
```

Biến môi trường giúp tách secret khỏi source, nhưng vẫn có thể bị đọc bởi process cùng quyền. Production nên dùng secret manager phù hợp với nền tảng deploy.

---

## 5. HTTP transport và connection pool

`_core._http` cung cấp transport thấp:

```python
await post_async(request_kwargs, client=client)
await get_async(request_kwargs, client=client)
```

`_core._utils` cung cấp helper mức Facebook:

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

from _features._facebook import _notification, _search

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

- Tái sử dụng TCP/TLS connection.
- Đặt timeout và proxy ở một chỗ.
- Dễ inject `httpx.MockTransport` khi test.
- Đóng tài nguyên đúng lifecycle ứng dụng.

### Quyền sở hữu client

- Caller truyền `client=` thì caller phải đóng client.
- Caller bỏ `client=` thì helper tự tạo và đóng client cho call đó.
- Không dùng client sau khi thoát `async with`.
- Không chia sẻ một client giữa nhiều event loop ở các thread khác nhau.

Transport copy request kwargs trước khi loại `url`, `verify`, `timeout`, vì vậy dict đầu vào của caller không bị mutate.

---

## 6. Login credential và 2FA

Cookie session là luồng khuyến nghị. Credential login dễ gặp checkpoint, rate limit và thay đổi subcode.

```python
from _core._facebookLogin import loginFacebook

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

`login.main()` đưa luồng `requests` legacy sang worker thread để không block event loop. Nó không biến protocol cũ thành native async, nhưng giữ boundary rõ ràng.

### FB4A defaults và override

Module có sẵn default API key và app access token của flow FB4A legacy. Chỉ override khi Facebook hoặc môi trường test yêu cầu:

```powershell
$env:FBCHAT_API_KEY = "<optional-override>"
$env:FBCHAT_APP_ACCESS_TOKEN = "<optional-override>"
```

Không hardcode override thật vào source hoặc `.env.example`.

### Kết quả login

Success thường chứa cookie đã export và trạng thái login. Error nên được đọc qua message, code và subcode Facebook trả về. Các continuation subcode đã biết trong codebase gồm `1348162` và `1348023`, nhưng không có đảm bảo chúng ổn định.

TOTP secret không được gửi tới `2fa.live` hoặc dịch vụ bên thứ ba.

---

## 7. Gửi tin nhắn thường

API:

```python
await SendAPI().send(
    dataFB,
    contentSend,
    threadID,
    typeAttachment=None,
    attachmentID=None,
    typeChat=None,
    replyMessage=None,
    messageID=None,
    client=None,
)
```

### Gửi tới một user

```python
from _messaging._send import api as SendAPI

result = await SendAPI().send(
    data_fb,
    "Xin chào",
    threadID="100012345678",
    typeChat="user",
)
```

### Gửi tới group thread

```python
result = await SendAPI().send(
    data_fb,
    "Thông báo nhóm",
    threadID="987654321",
    typeChat=None,
)
```

### Gửi tới nhiều user

```python
result = await SendAPI().send(
    data_fb,
    "Thông báo riêng",
    threadID=["10001", "10002"],
    typeChat="user",
)
```

Danh sách recipient chỉ hợp lệ với `typeChat="user"`.

### Reply message

```python
result = await SendAPI().send(
    data_fb,
    "Nội dung trả lời",
    threadID="100012345678",
    typeChat="user",
    replyMessage=True,
    messageID="mid.$original",
)
```

Nếu `replyMessage=True` mà thiếu `messageID`, API raise `ValueError` trước khi gửi request.

### Validation

`send()` reject các input sau:

- `threadID` rỗng.
- `typeChat` khác `None` hoặc `"user"`.
- `typeAttachment` ngoài `gif`, `image`, `video`, `file`, `audio`.
- Chỉ truyền một trong hai `typeAttachment` và `attachmentID`.
- Cả content lẫn attachment đều rỗng.
- Danh sách recipient rỗng hoặc chứa ID rỗng.

Mỗi call build form cục bộ nên có thể chạy đồng thời. `sender.results` chỉ là snapshot call hoàn tất gần nhất; logic phải dùng dict được `return`.

---

## 8. Upload và gửi attachment

API:

```python
await _attachments.func(
    filenames,
    dataFB,
    client=None,
    include_error=False,
)
```

`filenames` nhận một path hoặc danh sách path. Module kiểm tra file tồn tại trước request và luôn đóng file handle trong `finally`.

Parser hiện trả metadata của item đầu tiên (`metadata[0]` hoặc `metadata["0"]`), không trả danh sách result. Nếu cần gửi nhiều attachment một cách xác định, hãy upload từng file, kiểm tra từng `attachmentID` rồi truyền list ID vào `_send`.

```python
from _messaging import _attachments

uploaded = await _attachments.func(
    "photo.jpg",
    data_fb,
    include_error=True,
)
```

Success:

```python
{
    "attachmentID": "123...",
    "attachmentUrl": "https://...",
    "videoDuration": None,
    "attachmentType": "image/jpeg",
    "typeAttachment": "image",
}
```

`attachmentType` có thể là MIME hoặc type từ Facebook. Khi gọi `_send`, dùng `typeAttachment` đã được normalize:

```python
from _messaging._send import api as SendAPI

if not uploaded or not uploaded.get("attachmentID"):
    raise RuntimeError(f"Upload không có attachment ID: {uploaded}")

result = await SendAPI().send(
    data_fb,
    "Ảnh của bạn đây",
    threadID="100012345678",
    typeChat="user",
    typeAttachment=uploaded["typeAttachment"],
    attachmentID=uploaded["attachmentID"],
)
```

Khi `include_error=False`, response không parse được trả `None`. Khi `include_error=True`, module trả error payload có `error-code`, `error-summary`, `error-description`, `metadata`, `file-rejected` và `raw-excerpt` đã giới hạn độ dài.

Nếu Facebook trả `metadata: {"0": null}` hoặc error `1357054`, đó là server từ chối upload hoặc endpoint/session không còn phù hợp, không phải attachment ID hợp lệ.

---

## 9. Listener MQTT thường

Khởi tạo:

```python
from _messaging._listening import listeningEvent

listener = listeningEvent(data_fb, message_queue_maxsize=1000)
```

Public async methods:

| Method | Kết quả |
|---|---|
| `await get_last_seq_id()` | Lấy sequence ID ban đầu |
| `await connect_mqtt()` | Chạy MQTT loop đến khi disconnect |
| `await get_message(timeout=None)` | Lấy event tiếp theo hoặc `None` khi timeout |
| `await disconnect()` | Dừng client và worker loop |

Workflow:

```python
import asyncio

listener_task = asyncio.create_task(listener.connect_mqtt())
try:
    while True:
        if listener_task.done():
            listener_task.result()
        event = await listener.get_message(timeout=30)
        if event is None:
            continue
        print(event["body"], event["messageID"])
finally:
    await listener.disconnect()
    await listener_task
```

Event normalized:

```python
{
    "body": "...",
    "timestamp": 1710000000000,
    "userID": "1000...",
    "messageID": "mid.$...",
    "replyToID": "thread-id",
    "type": "thread",
    "attachments": {"id": 0, "url": None},
    "mentions": [],
}
```

Listener parse toàn bộ delta trong payload, dùng queue có giới hạn và drop event cũ nhất khi đầy. `droppedMessages` tăng sau mỗi lần drop. Theo dõi metric này để biết consumer quá chậm.

Không poll `bodyResults` cho bot mới. Nó chỉ là snapshot tương thích và không lưu được burst nhiều event.

---

## 10. Listener E2EE

Khởi tạo:

```python
listener = listeningE2EEEvent(
    data_fb,
    log_level="none",
    device_path=None,
    e2ee_memory_only=True,
    enable_e2ee=True,
    binary_path=None,
)
```

| Tham số | Ý nghĩa |
|---|---|
| `log_level` | Mức log gửi cho bridge |
| `device_path` | Path state thiết bị khi muốn persist |
| `e2ee_memory_only` | Giữ device state trong RAM khi `True` |
| `enable_e2ee` | Có gọi handshake E2EE hay không |
| `binary_path` | Override binary cho instance này |

Cookie bridge bắt buộc có `c_user`, `xs`, `datr`, `fr`. Wrapper chỉ chuyển các cookie cần thiết sang bridge.

### Binary discovery

Thứ tự:

1. `binary_path=` trên constructor.
2. `FBCHAT_E2EE_BIN`.
3. `build/fbchat-bridge-e2ee.exe` trên Windows hoặc không đuôi trên Unix.
4. Auto-download GitHub Release nếu path mặc định chưa có.

Khi override path được chỉ định mà file không tồn tại, wrapper raise `FileNotFoundError` và không tải fallback.

### Callback và event loop

`on_message()` là callback đồng bộ chạy từ poll loop bridge. Không `await` trực tiếp trong callback. Chuyển event về loop:

```python
import asyncio

listener = listeningE2EEEvent(data_fb)
loop = asyncio.get_running_loop()
events: asyncio.Queue[dict] = asyncio.Queue(maxsize=1000)


def enqueue(event: dict) -> None:
    if events.full():
        events.get_nowait()
    events.put_nowait(event)


listener.on_message(
    lambda event: loop.call_soon_threadsafe(enqueue, event)
)
task = asyncio.create_task(listener.connect_mqtt())
```

### Đợi bridge sẵn sàng

`wait_until_connected()` dùng `threading.Event`, nên gọi qua worker thread để không block loop:

```python
ready = await asyncio.to_thread(
    listener.wait_until_connected,
    90,
    require_e2ee=True,
)
if not ready:
    raise TimeoutError("E2EE listener chưa sẵn sàng.")
```

Không gửi ngay sau `create_task(connect_mqtt())`. Bridge có thể mới spawn nhưng chưa chạy `newClient`, `connect` và `connectE2EE`.

### Schema event

Raw callback event:

```python
{
    "type": "e2eeMessage",
    "data": {
        "id": "...",
        "text": "ping",
        "timestampMs": 1710000000000,
        "senderId": "1000...",
        "threadId": "...",
        "chatJid": "1000...@msgr",
        "senderJid": "1000...@msgr",
        "attachments": [],
        "mentions": [],
    },
}
```

`listener.bodyResults` giữ schema normalized giống listener thường. `listener.e2eeBodyResults` giữ `chatJid` và `senderJid`. Với ứng dụng mới, ưu tiên raw callback event để không gặp race khi nhiều event cập nhật snapshot liên tiếp.

### Shutdown

```python
try:
    ...
finally:
    listener.stop()
    await task
```

`stop()` là sync vì nó signal và đóng subprocess. Việc chờ task kết thúc vẫn phải `await`.

---

## 11. Gửi và thao tác qua bridge

### Gửi text E2EE

Sau khi listener ready:

```python
result = await listener.send_e2ee_message(
    "100012345678@msgr",
    "Xin chào",
    reply_to_id="",
    reply_to_sender_jid="",
)
```

Reply:

```python
data = event["data"]
result = await listener.send_e2ee_message(
    data["chatJid"],
    "pong",
    reply_to_id=data["id"],
    reply_to_sender_jid=data["senderJid"],
)
```

### Gửi tin thường qua cùng bridge

```python
result = await listener.send_message(
    int(thread_id),
    "Thông báo group",
    reply_to_id="mid.$original",
)
```

### `BridgeActions`

```python
from _messaging._bridge_actions import BridgeActions

if listener._bridge is None:
    raise RuntimeError("Bridge chưa sẵn sàng.")
actions = BridgeActions(listener._bridge)
```

Public async actions:

| Method | Mục đích |
|---|---|
| `edit_message(message_id, new_text)` | Sửa tin thường qua bridge |
| `unsend_message(message_id)` | Thu hồi tin thường |
| `edit_e2ee_message(chat_jid, message_id, new_text)` | Sửa tin E2EE |
| `unsend_e2ee_message(chat_jid, message_id)` | Thu hồi tin E2EE |
| `send_typing_indicator(thread_id, is_typing, ...)` | Typing thường |
| `mark_read(thread_id, watermark_ts)` | Đánh dấu đã đọc |
| `send_e2ee_typing(chat_jid, is_typing)` | Typing E2EE |
| `send_e2ee_audio(chat_jid, data, ...)` | Gửi audio bytes |
| `send_e2ee_image(chat_jid, data, ...)` | Gửi image bytes |
| `download_media(url)` | Download media thường thành bytes |
| `download_e2ee_media(...)` | Download và giải mã media E2EE |

Ví dụ gửi ảnh:

```python
image_bytes = await asyncio.to_thread(Path("photo.jpg").read_bytes)
result = await actions.send_e2ee_image(
    "100012345678@msgr",
    image_bytes,
    mime_type="image/jpeg",
    caption="Ảnh test",
)
```

Bridge mã hóa bytes thành base64 tại JSON-RPC boundary. Tránh đọc file rất lớn vào event loop; dùng `asyncio.to_thread()` hoặc I/O async phù hợp.

### `_send_e2ee.api`

`_send_e2ee.api` hiện là compatibility sender blocking cho standalone hoặc reuse bridge. Application asyncio mới nên dùng `await listener.send_e2ee_message(...)` và `BridgeActions`. Nếu bắt buộc dùng standalone sender, gọi nó qua boundary riêng để không block loop.

---

## 12. Sửa, reaction và thu hồi tin thường

```python
from _messaging import _editMessage, _reactions, _unsend

edited = await _editMessage.func(
    data_fb,
    "mid.$message",
    "Nội dung mới",
)

reacted = await _reactions.func(
    data_fb,
    "ADD_REACTION",
    "mid.$message",
    "🔥",
)

removed = await _unsend.func("mid.$message", data_fb)
```

`_reactions.func()` chấp nhận `add`, `ADD_REACTION`, `remove` hoặc `REMOVE_REACTION` sau khi normalize hoa thường. ID và emoji rỗng bị reject.

`_editMessage` publish LS task bằng MQTT. Success nghĩa là task đã được publish lên `/ls_req`, không đảm bảo server đã áp dụng. Facebook thường chỉ cho sửa tin của chính tài khoản và có thể giới hạn độ tuổi message.

---

## 13. Theme và Messenger Notes

### Theme

```python
from _messaging import _changeTheme

themes = await _changeTheme.listThemes(data_fb)
match = await _changeTheme.findTheme(data_fb, "love")
changed = await _changeTheme.changeTheme(
    data_fb,
    "thread-id",
    "love",
)
```

Entry point thống nhất:

```python
await _changeTheme.func(data_fb, action="list")
await _changeTheme.func(data_fb, themeName="love", action="find")
await _changeTheme.func(
    data_fb,
    threadID="thread-id",
    themeName="love",
    action="set",
)
```

Theme được match theo ID, tên chính xác rồi keyword. `changeTheme()` publish nhiều LS task cần thiết cho thread theme.

### Messenger Notes

```python
from _messaging import _createNotes

current = await _createNotes.checkNote(data_fb)
created = await _createNotes.createNote(
    data_fb,
    "Đang viết bot",
    privacy="FRIENDS",
)
deleted = await _createNotes.deleteNote(data_fb, "note-id")
replaced = await _createNotes.recreateNote(
    data_fb,
    "old-note-id",
    "Nội dung mới",
)
```

Entry point:

```python
await _createNotes.func(data_fb, action="check")
await _createNotes.func(data_fb, action="create", text="Hello")
await _createNotes.func(data_fb, action="delete", noteID="note-id")
await _createNotes.func(
    data_fb,
    action="recreate",
    oldNoteID="old-id",
    newText="New note",
)
```

`recreateNote()` là workflow fail-fast gồm delete rồi create, không phải transaction server-side. Nếu delete thành công nhưng create thất bại, note cũ đã mất.

---

## 14. Tính năng Facebook

Mọi API trong bảng là coroutine và phần lớn nhận optional keyword-only `client: httpx.AsyncClient`.

| Module | Chữ ký rút gọn | Mục đích |
|---|---|---|
| `_changeBio` | `func(dataFB, newContents, uploadPost=False)` | Đổi bio |
| `_createPost` | `func(dataFB, newContents, attachmentID=None)` | Tạo bài timeline |
| `_professional` | `func(dataFB, statusBusiness=None)` | Bật/tắt Professional mode |
| `_search` | `func(dataFB, keywordSearch)` | Tìm user, tối đa 5 kết quả đã loại trùng |
| `_blocking` | `func(dataFB, idUser, choiceInteract)` | `block` hoặc `unblock` |
| `_registerOnProfile` | `func(dataFB, newName, newUsername)` | Tạo profile bổ sung |
| `_notification` | `func(dataFB)` | Lấy notification |
| `_get_user_info` | `func(dataFB, userID)` | Lấy thông tin user |
| `_marketplace` | `createItem(...)` | Đăng sản phẩm |
| `_marketplace` | `getInformationProductItemMarketPlace(...)` | Lấy chi tiết sản phẩm |

Ví dụ workflow có connection pool:

```python
import httpx

from _features._facebook import _blocking, _get_user_info, _search

async with httpx.AsyncClient(timeout=30) as client:
    search = await _search.func(data_fb, "m008v", client=client)
    info = await _get_user_info.func(
        data_fb,
        "100012345678",
        client=client,
    )
    blocked = await _blocking.func(
        data_fb,
        "100012345678",
        "block",
        client=client,
    )
```

`_createPost` chưa có schema Composer ổn định cho attachment. Truyền `attachmentID` sẽ raise `NotImplementedError`, tránh trường hợp caller tưởng ảnh đã được đăng trong khi module âm thầm bỏ qua.

Marketplace validate category, tên, giá không âm, danh sách ảnh và tọa độ seller trước request.

---

## 15. Quản lý thread

| Module | API |
|---|---|
| `_all_thread_data` | `await func(dataFB, client=...)` |
| `_all_thread_data` | `await features(dataGet, threadID, commandUse)` |
| `_changeNameThread` | `await func(dataFB, threadID, newNameThread, client=...)` |
| `_changeEmoji` | `await func(dataFB, threadID, newEmoji, client=...)` |
| `_addAdmin` | `await func(dataFB, threadID, idUser, statusChoice=True, client=...)` |
| `_changeNickname` | `await func(dataFB, threadID, idUser, NewNickname, client=...)` |

```python
from _features._thread import (
    _addAdmin,
    _all_thread_data,
    _changeEmoji,
    _changeNameThread,
    _changeNickname,
)

threads = await _all_thread_data.func(data_fb)
if threads.get("error"):
    raise RuntimeError(threads)

info = await _all_thread_data.features(
    threads["dataGet"],
    "thread-id",
    "threadInfomation",
)

await _changeNameThread.func(data_fb, "thread-id", "Tên mới")
await _changeEmoji.func(data_fb, "thread-id", "🔥")
await _changeNickname.func(data_fb, "thread-id", "user-id", "Biệt danh")
await _addAdmin.func(data_fb, "thread-id", "user-id", statusChoice=True)
await _addAdmin.func(data_fb, "thread-id", "user-id", statusChoice=False)
```

`statusChoice=False` thực sự gỡ admin. `features()` parse dữ liệu đã tải trong RAM và giữ coroutine để hợp đồng gọi nhất quán.

---

## 16. Bot mẫu `src/main.py`

Bot mẫu là reference cho lifecycle, không phải framework bot production.

### Cấu hình

```json
{
  "prefix": "/",
  "cookies": "c_user=...; xs=...; fr=...; datr=...;",
  "admins": ["100012345678"]
}
```

### Luồng runtime

1. `load_config()` validate `prefix` và `admins`.
2. `FileSessionStorage` đưa cookie vào `await dataGetHome(...)`.
3. `is_valid_datafb()` kiểm tra token bắt buộc.
4. Một `httpx.AsyncClient` được dùng lại cho command HTTP.
5. E2EE listener start thành task.
6. Callback bridge chuyển event về queue bằng `call_soon_threadsafe`.
7. Bot bỏ self-message, dedupe message ID và dispatch handler async.
8. Reply E2EE hoặc regular dựa trên `chatJid`.
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

Thêm command bằng cách khai báo async handler và đăng ký trong `self._handlers`. Handler không nên giữ CPU lâu; đưa CPU-bound work sang process pool hoặc worker phù hợp.

---

## 17. Timeout, lỗi và cancellation

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

Log loại exception, endpoint logical và ID không nhạy cảm. Không log request form, cookie, access token, password hoặc TOTP.

---

## 18. Hợp đồng kết quả

Các module lịch sử chưa có một dataclass chung, nhưng thường dùng hai schema:

Success:

```python
{
    "success": 1,
    "payload": {...},
}
```

Error:

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

---

## 19. Chuyển từ sync sang async

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

---

## 20. Kiểm tra chất lượng

Pytest giống CI:

```bash
pytest tests/ -v --tb=short
```

Lint, format và compile:

```bash
ruff check src tests
ruff format --check src tests
python -m compileall -q src tests
git diff --check
```

Bridge:

```bash
cd bridge-e2ee
go test ./...
go vet ./...
```

Trước push, quét mọi file text tracked để phát hiện UTF-8 invalid, U+FFFD, NUL và mojibake thật. PowerShell hiển thị sai encoding không tự động có nghĩa file đã hỏng.

---

## 21. FAQ và troubleshooting

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

Watchdog retry theo exponential backoff và phát `bridge_fatal` khi vượt giới hạn. Đọc stderr bridge, xác nhận binary đúng kiến trúc, cookie còn sống và submodule/build cùng version. Không start thêm listener để che lỗi; mỗi listener sẽ spawn thêm process và pairing state.

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

---

Chi tiết theo module:

- [`src/_core/README.md`](src/_core/README.md)
- [`src/_features/README.md`](src/_features/README.md)
- [`src/_messaging/README.md`](src/_messaging/README.md)
- [`bridge-e2ee/README.md`](bridge-e2ee/README.md)
