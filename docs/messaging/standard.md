# Gửi và nhận tin nhắn thường

[Bắt đầu](../getting-started/quickstart.md) · [Tin nhắn thường](standard.md) · [E2EE](e2ee.md) · [Facebook](../features/facebook-actions.md) · [Tra nhanh](../recipes/cheatsheet.md)

Trong trang này:

- [Gửi tin nhắn thường](#gửi-tin-nhắn-thường)
- [Upload và gửi attachment](#upload-và-gửi-attachment)
- [Listener MQTT thường](#listener-mqtt-thường)
- [Sửa, reaction và thu hồi tin thường](#sửa-reaction-và-thu-hồi-tin-thường)
- [Theme và Messenger Notes](#theme-và-messenger-notes)

Dùng các API dưới đây cho tin thường qua HTTP hoặc listener Python MQTT.
Với hội thoại mã hóa, xem [E2EE](e2ee.md). Tạo `data_fb` theo [quickstart](../getting-started/quickstart.md) trước khi gọi các ví dụ.

## Gửi tin nhắn thường

Khối đầu liệt kê tham số của `send()`. Để chạy thử, dùng ví dụ
[gửi tới một user](#gửi-tới-một-user) sau đó.

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
from fbchat_v2._messaging._send import api as SendAPI

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

Chỉ truyền danh sách người nhận khi dùng `typeChat="user"`.

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

Nếu `replyMessage=True` mà thiếu `messageID`, API báo `ValueError` trước khi gửi request.

### Kiểm tra đầu vào

`send()` không nhận các đầu vào sau:

- `threadID` rỗng.
- `typeChat` khác `None` hoặc `"user"`.
- `typeAttachment` ngoài `gif`, `image`, `video`, `file`, `audio`.
- Chỉ truyền một trong hai `typeAttachment` và `attachmentID`.
- Cả nội dung lẫn tệp đính kèm đều rỗng.
- Danh sách người nhận rỗng hoặc chứa ID rỗng.

Mỗi lần gọi tạo form riêng nên có thể chạy đồng thời. `sender.results` chỉ giữ kết quả của lần gọi hoàn tất gần nhất; hãy dùng dict được hàm trả về để xử lý kết quả của từng lần gửi.


## Upload và gửi attachment

API:

```python
await _attachments.func(
    filenames,
    dataFB,
    client=None,
    include_error=False,
)
```

`filenames` nhận một đường dẫn hoặc danh sách đường dẫn. Module kiểm tra file tồn tại trước khi gửi request và luôn đóng file trong `finally`.

Parser hiện chỉ trả metadata của phần tử đầu tiên (`metadata[0]` hoặc `metadata["0"]`), không trả danh sách kết quả. Để gửi nhiều tệp và kiểm tra kết quả của từng tệp, hãy upload lần lượt, lấy từng `attachmentID` rồi truyền danh sách ID vào `_send`.

```python
from fbchat_v2._messaging import _attachments

uploaded = await _attachments.func(
    "photo.jpg",
    data_fb,
    include_error=True,
)
```

Kết quả thành công:

```python
{
    "attachmentID": "123...",
    "attachmentUrl": "https://...",
    "videoDuration": None,
    "attachmentType": "image/jpeg",
    "typeAttachment": "image",
}
```

`attachmentType` có thể là MIME hoặc loại tệp do Facebook trả về. Khi gọi `_send`, dùng `typeAttachment` đã chuẩn hóa:

```python
from fbchat_v2._messaging._send import api as SendAPI

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

Nếu Facebook trả `metadata: {"0": null}` hoặc lỗi `1357054`, server đã từ chối upload hoặc endpoint/session không còn phù hợp. Không dùng kết quả đó làm attachment ID.


## Listener MQTT thường

Khởi tạo:

```python
from fbchat_v2._messaging._listening import listeningEvent

listener = listeningEvent(data_fb, message_queue_maxsize=1000)
```

Các method async:

| Method | Kết quả |
|---|---|
| `await get_last_seq_id()` | Lấy sequence ID ban đầu |
| `await connect_mqtt()` | Chạy MQTT loop đến khi disconnect |
| `await get_message(timeout=None)` | Lấy event tiếp theo hoặc `None` khi timeout |
| `await disconnect()` | Dừng client và worker loop |

Nhận event và dừng listener:

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

Event đã chuẩn hóa:

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

Listener đọc toàn bộ delta trong payload và đưa event vào queue có giới hạn. Khi queue đầy, event cũ nhất bị bỏ và `droppedMessages` tăng. Theo dõi giá trị này để biết ứng dụng có xử lý tin chậm hơn tốc độ nhận hay không.

Bot mới nên đọc event từ queue, không kiểm tra lặp lại `bodyResults`. Thuộc tính này chỉ giữ kết quả gần nhất để tương thích code cũ; nhiều event đến liên tiếp có thể ghi đè nhau.


Xem [ReconnectPolicy và trạng thái kết nối](e2ee.md#tự-nối-lại) để đặt retry cho cả MQTT và E2EE.

## Sửa, reaction và thu hồi tin thường

```python
from fbchat_v2._messaging import _editMessage, _reactions, _unsend

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

`_reactions.func()` chấp nhận `add`, `ADD_REACTION`, `remove` hoặc `REMOVE_REACTION`, không phân biệt hoa thường. ID và emoji không được rỗng.

`_editMessage` gửi LS task qua MQTT. Kết quả thành công chỉ xác nhận task đã được gửi lên `/ls_req`, chưa xác nhận server đã áp dụng thay đổi. Facebook thường chỉ cho sửa tin của chính tài khoản và có thể giới hạn thời gian sửa.


## Theme và Messenger Notes

### Theme

```python
from fbchat_v2._messaging import _changeTheme

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
from fbchat_v2._messaging import _createNotes

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

`recreateNote()` xóa note rồi tạo lại và dừng khi có lỗi. Hai bước này không phải một transaction phía server: nếu xóa thành công nhưng tạo lại thất bại, note cũ đã mất.
