# `_messaging` — Messenger async

Tầng gửi/nhận tin nhắn, attachment, reaction, note, theme và E2EE. `dataFB` phải được tạo trước bằng `dataGetHome_async()`.

## API

| Module | Async API |
|---|---|
| `_send.py` | `api().send_async(...)` |
| `_attachments.py` | `func_async(filenames, dataFB)` |
| `_reactions.py` | `func_async(dataFB, typeAdded, messageID, emojiChoice)` |
| `_unsend.py` | `func_async(messageID, dataFB)` |
| `_editMessage.py` | `func_async(dataFB, messageID, newText)` |
| `_message_requests.py` | `func_async(dataFB)` |
| `_createNotes.py` | `checkNote_async`, `createNote_async`, `deleteNote_async`, `recreateNote_async` |
| `_changeTheme.py` | `listThemes_async`, `findTheme_async`, `changeTheme_async` |
| `_listening.py` | `connect_mqtt_async`, `get_message_async`, `disconnect_async` |
| `_listening_e2ee.py` | `connect_mqtt_async`, `send_message_async`, `send_e2ee_message_async` |
| `_bridge_actions.py` | các action có hậu tố `_async` |

## Gửi và trả lời

```python
from _messaging._send import api as SendAPI

result = await SendAPI().send_async(
    data_fb,
    "Xin chào",
    threadID="100012345678",
    typeChat="user",
    replyMessage=True,
    messageID="mid.$...",
)
```

Form của mỗi lời gọi là độc lập. Khi gửi song song, dùng kết quả được `return`; `sender.results` chỉ là snapshot của lời gọi hoàn tất gần nhất.

## Upload

```python
from _messaging import _attachments
from _messaging._send import api as SendAPI

uploaded = await _attachments.func_async(["a.jpg", "b.jpg"], data_fb)
if uploaded and uploaded.get("attachmentID"):
    await SendAPI().send_async(
        data_fb,
        "Hai ảnh",
        threadID="thread-id",
        typeAttachment="image",
        attachmentID=uploaded["attachmentID"],
    )
```

## Listener thường

```python
import asyncio

from _messaging._listening import listeningEvent

listener = listeningEvent(data_fb, message_queue_maxsize=1000)
task = asyncio.create_task(listener.connect_mqtt_async())
try:
    while True:
        event = await listener.get_message_async(timeout=30)
        if event:
            print(event)
finally:
    await listener.disconnect_async()
    await task
```

`bodyResults` chỉ là snapshot tương thích. Bot mới phải đọc queue bằng `get_message_async()` để không mất burst. `paho-mqtt` có loop blocking nên adapter async dùng một worker thread dành riêng; callback không tự reconnect đệ quy.

## E2EE

```python
import asyncio

from _messaging._listening_e2ee import listeningE2EEEvent

listener = listeningE2EEEvent(data_fb)
task = asyncio.create_task(listener.connect_mqtt_async())
try:
    await listener.send_e2ee_message_async(
        "100012345678@msgr",
        "Tin nhắn mã hóa",
    )
finally:
    listener.stop()
    await task
```

`BridgeActions` cung cấp async edit/unsend/typing/mark-read, gửi media và download media. Dữ liệu binary được base64 chỉ ở boundary JSON-RPC.

## Note, theme và message action

```python
from _messaging import _changeTheme, _createNotes, _editMessage, _reactions, _unsend

await _editMessage.func_async(data_fb, "mid.$...", "Nội dung mới")
await _reactions.func_async(data_fb, "ADD_REACTION", "mid.$...", "🔥")
await _unsend.func_async("mid.$...", data_fb)
await _createNotes.createNote_async(data_fb, "Đang online")
await _changeTheme.changeTheme_async(data_fb, "thread-id", "Love")
```

## Edge case cần xử lý

- Listener task kết thúc sớm: đọc exception của task, không để bot treo im lặng.
- Queue đầy: theo dõi `droppedMessages` và tăng `message_queue_maxsize` có giới hạn.
- Upload thiếu `attachmentID`: không gọi send.
- LS publish thành công chỉ xác nhận task đã lên `/ls_req`, không đảm bảo server đã áp dụng.
- E2EE bridge chưa ready: đợi kết nối trước khi gọi send.
- Khi shutdown: disconnect/stop trước, sau đó await listener task.
