# `_messaging` — Tầng nhắn tin

> Mọi thao tác Messenger trực tiếp: gửi, nhận realtime, upload tệp, react, thu hồi, message requests.

[![Layer](https://img.shields.io/badge/layer-messaging-EC4899)](.)
[![Status](https://img.shields.io/badge/status-stable-22c55e)](.)
[![English](https://img.shields.io/badge/docs-English-blue)](README_EN.md)

---

## 📑 Mục lục

- [Vai trò](#-vai-trò)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Public API](#-public-api)
- [Hợp đồng `dataFB`](#-hợp-đồng-datafb)
- [Tham chiếu module](#-tham-chiếu-module)
  - [`_send.py`](#sendpy)
  - [`_listening.py`](#listeningpy)
  - [`_attachments.py`](#attachmentspy)
  - [`_reactions.py`](#reactionspy)
  - [`_unsend.py`](#unsendpy)
  - [`_message_requests.py`](#message_requestspy)
- [Sơ đồ phụ thuộc](#-sơ-đồ-phụ-thuộc)
- [Ví dụ](#-ví-dụ)
- [Khắc phục sự cố](#-khắc-phục-sự-cố)

---

## 🎯 Vai trò

`_messaging` đóng gói các endpoint Messenger thành hàm/class Python dễ dùng. Tầng này **không** xử lý session/token (đã có `_core`):

- 📤 Gửi tin văn bản tới user hoặc thread.
- 📎 Upload tệp đính kèm để gửi qua Messenger.
- 📡 Lắng nghe sự kiện realtime qua **MQTT over WebSocket**.
- ❤️ Thêm / xoá reaction.
- ↩️ Thu hồi tin nhắn đã gửi.
- 📥 Lấy danh sách **Message Requests** (tin nhắn chờ).

---

## 📂 Cấu trúc thư mục

```text
src/_messaging/
├── __init__.py
├── _attachments.py        # Upload tệp → attachmentID
├── _listening.py          # MQTT realtime listener
├── _message_requests.py   # Tin nhắn chờ
├── _reactions.py          # Thả / gỡ reaction
├── _send.py               # Gửi tin nhắn (HTTP)
├── _unsend.py             # Thu hồi tin nhắn
├── README.md              # ← bạn đang ở đây
└── README_EN.md
```

---

## 📦 Public API

```python
# src/_messaging/__init__.py
__all__ = [
    "_attachments", "_listening", "_reactions",
    "_send", "_unsend", "_message_requests",
]
```

Import qua `_messaging._send`, `_messaging._listening`, … để dùng từng module.

---

## 🧩 Hợp đồng `dataFB`

Mọi API trong `_messaging` đều nhận **`dataFB`** — sinh từ `_core._session.dataGetHome(setCookies)`.

Trường thường dùng: `fb_dtsg` · `jazoest` · `FacebookID` · `clientRevision` · `cookieFacebook`.

> 📖 Schema đầy đủ: [`_core/README.md`](../_core/README.md#-hợp-đồng-dữ-liệu-datafb).

---

## 📚 Tham chiếu module

### `_send.py`

#### `class api`

Module gửi tin nhắn chính.

```python
api().send(
    dataFB,
    contentSend,
    threadID,
    typeAttachment=None,
    attachmentID=None,
    typeChat=None,
    replyMessage=None,
    messageID=None,
)
```

| Tham số | Mô tả |
|---|---|
| `contentSend` | Nội dung tin nhắn. |
| `threadID` | ID nhóm hoặc user nhận. |
| `typeChat` | `"user"` để nhắn 1-1, `None` để nhắn vào thread/group. |
| `typeAttachment` | `"gif"` · `"image"` · `"video"` · `"file"` · `"audio"`. |
| `attachmentID` | ID tệp đã upload qua `_attachments`. |
| `replyMessage` + `messageID` | Dùng cho luồng reply tin nhắn. |

**Trả về:**

- ✅ `{ "success": 1, "payload": { "messageID": ..., "timestamp": ... } }`
- ❌ `{ "error": 1, "payload": { "error-decription": ..., "error-code": ... } }`

> 📝 Module tự sinh `offline_threading_id`, `message_id`, `threading_id`. Response `/messaging/send/` có tiền tố `for (;;);` — đã được tách sẵn.

---

### `_listening.py`

#### `class listeningEvent(dataFB)`

Lắng nghe sự kiện realtime qua **MQTT over WebSocket** (`wss://edge-chat.facebook.com/...`).

| Method | Mô tả |
|---|---|
| `get_last_seq_id()` | Lấy & cập nhật `last_seq_id` mới nhất. |
| `connect_mqtt()` | Khởi tạo MQTT client, subscribe sync queue, nhận message delta. **Blocking** (`loop_forever()`). |

**Khi có sự kiện** — `self.bodyResults` chứa:

```text
body · timestamp · userID · messageID · replyToID · type
attachments.id · attachments.url
```

**Highlights:**

- Có cơ chế **reconnect** khi disconnect bất thường.
- Tự xử lý `errorCode == 100` (queue overflow) bằng cách reset queue token.
- Vì `connect_mqtt()` blocking → nên chạy trong **thread / process riêng**.

---

### `_attachments.py`

```python
_uploadAttachment(filenames, dataFB)
```

Upload tệp lên `https://upload.facebook.com/ajax/mercury/upload.php` để lấy `attachmentID`.

**Trả về:**

```python
{
    "attachmentID": ...,
    "attachmentUrl": ...,
    "attachmentType": ...,
    "attachmentDataSend": None,
}
```

> ⚠️ Một call = một file. Khi lỗi, hàm in trực tiếp ra console thay vì raise exception chi tiết.

---

### `_reactions.py`

```python
func(dataFB, typeAdded, messageID, emojiChoice)
```

Thêm / xoá reaction trên tin nhắn.

| Tham số | Giá trị |
|---|---|
| `typeAdded` | `"add"` để thêm; bất kỳ giá trị khác để xoá. |
| `messageID` | ID tin nhắn cần react. |
| `emojiChoice` | Emoji muốn dùng. |

**Trả về:** `requests.Response` thô — bạn cần tự parse `response.text`.

---

### `_unsend.py`

```python
func(messageID, dataFB)
```

Thu hồi tin nhắn theo `messageID`. Endpoint: `/messaging/unsend_message/`.

- ✅ `{ "success": 1, "messages": "Thu hồi tin nhắn thành công." }`
- ❌ Trả về `Exception({...})`.

---

### `_message_requests.py`

```python
func(dataFB)
```

Lấy danh sách tin nhắn chờ (`PENDING`).

- ✅ `{ "success": 1, "messageRequests": "<json string đã format>" }`

Nội dung gồm danh sách người gửi, snippet, timestamp và `total_count`.

---

## 🔗 Sơ đồ phụ thuộc

`_messaging` phụ thuộc chính vào `_core`:

```text
_core._session.dataGetHome(setCookies)  →  dataFB
_core._utils  →  formAll · mainRequests · gen_threading_id
                 generate_session_id · generate_client_id · json_minimal
                 str_base · get_files_from_paths · Headers · parse_cookie_string
```

**Thư viện ngoài:** `requests`, `paho-mqtt`.

---

## 💡 Ví dụ

### Gửi tin nhắn văn bản

```python
from _messaging._send import api

sender = api()
print(sender.send(dataFB, "Xin chào", "1234567890"))
```

### Upload ảnh rồi gửi kèm

```python
from _messaging._attachments import _uploadAttachment
from _messaging._send import api

uploaded = _uploadAttachment("path/to/image.jpg", dataFB)
sender = api()
print(sender.send(
    dataFB,
    "Ảnh của bạn đây",
    "1234567890",
    typeAttachment="image",
    attachmentID=uploaded["attachmentID"],
))
```

### React vào tin nhắn

```python
from _messaging._reactions import func

resp = func(dataFB, "add", "mid.$abc...", "👍")
print(resp.status_code, resp.text)
```

### Thu hồi tin nhắn

```python
from _messaging._unsend import func
print(func("mid.$abc...", dataFB))
```

### Lấy tin nhắn chờ

```python
from _messaging._message_requests import func
print(func(dataFB))
```

### Lắng nghe realtime

```python
import threading
from _messaging._listening import listeningEvent

listener = listeningEvent(dataFB)
listener.get_last_seq_id()
threading.Thread(target=listener.connect_mqtt, daemon=True).start()
```

---

## 🛠 Khắc phục sự cố

| Triệu chứng | Hướng xử lý |
|---|---|
| Gửi tin nhắn thất bại | Kiểm tra cookie & `dataFB` còn hợp lệ; verify `threadID`/`userID`; `typeAttachment` khớp với file đã upload. |
| Upload tệp lỗi | Verify đường dẫn tồn tại + quyền đọc; kiểm tra metadata response (Facebook có thể đổi key). |
| Listener tự ngắt / không nhận event | Chạy trong thread riêng (`loop_forever()` blocking); theo dõi `errorCode` trong MQTT payload; quan tâm `errorCode == 100` (queue overflow). |
| Lỗi parse JSON | Loại tiền tố `for (;;);` trước `json.loads`. |

---

<div align="right">

⬆️ [Về README chính](../../README.md) · 🇬🇧 [English](README_EN.md)

</div>
