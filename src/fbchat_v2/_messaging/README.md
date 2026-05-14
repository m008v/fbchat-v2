# `_messaging` — Tầng nhắn tin

> Mọi thao tác Messenger trực tiếp: gửi, nhận realtime, upload tệp, react, thu hồi, message requests.

[![Layer](https://img.shields.io/badge/layer-messaging-EC4899)](.)
[![Status](https://img.shields.io/badge/status-stable-22c55e)](.)
[![English](https://img.shields.io/badge/docs-English-blue)](README_EN.md)

---

## 📑 Mục lục

- [Vai trò](#-vai-trò)
- [Cài đặt](#-cài-đặt)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Public API](#-public-api)
- [Hợp đồng `dataFB`](#-hợp-đồng-datafb)
- [Tham chiếu module](#-tham-chiếu-module)
  - [`_send.py`](#sendpy)
  - [`_listening.py`](#listeningpy)
  - [`_listening_e2ee.py`](#listening_e2eepy)
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

## 📦 Cài đặt

`_messaging` đi kèm mã nguồn `fbchat-v2` — bạn không cài riêng. Phần này chỉ liệt kê **những gì module này cần** ở cấp runtime.

### 1. Phụ thuộc Python (đã có trong `requirements.txt`)

| Package | Dùng cho | Ghi chú |
|---|---|---|
| `requests` | `_send` · `_attachments` · `_reactions` · `_unsend` · `_message_requests` | HTTP client |
| `paho-mqtt` | `_listening` | MQTT over WebSocket |
| `attrs` | `_listening` | Decorator class |

Cài nhanh nếu chỉ muốn dùng riêng `_messaging`:

```bash
pip install requests paho-mqtt attrs
```

### 2. Bridge Go cho `_listening_e2ee` (tuỳ chọn)

Chỉ cần nếu bạn dùng `listeningE2EEEvent` để nhận tin nhắn 1-1 (E2EE). Yêu cầu **Go ≥ 1.24** + **Git**.

```bash
cd ../../bridge-e2ee            # từ fbchat-v2/src/_messaging/
git clone https://github.com/mautrix/meta.git ./meta
go mod tidy

# Windows
go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee.exe .
# Linux / macOS
go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee .
```

Python wrapper tìm binary theo thứ tự:

1. Biến môi trường `FBCHAT_E2EE_BIN` (nếu set).
2. `fbchat-v2/build/fbchat-bridge-e2ee[.exe]` (mặc định).

Nếu thiếu binary, `_listening_e2ee` raise `FileNotFoundError` kèm hướng dẫn build.

### 3. `dataFB` từ `_core`

Mọi hàm trong `_messaging` đều nhận `dataFB` sinh từ `_core._session.dataGetHome(setCookies)` — xem [`_core/README.md`](../_core/README.md#-hợp-đồng-dữ-liệu-datafb).

Hướng dẫn cài đặt đầy đủ (clone, venv, Go toolchain, smoke test): xem [README gốc § Cài đặt](../../README.md#-cài-đặt).

---

## 📂 Cấu trúc thư mục

```text
src/_messaging/
├── __init__.py
├── _attachments.py        # Upload tệp → attachmentID
├── _createNotes.py        # Messenger Notes (24h status): check/create/delete/recreate
├── _listening.py          # MQTT realtime listener (tin nhắn nhóm)
├── _listening_e2ee.py     # Bridge Go — listener E2EE (tin nhắn 1-1)
├── _message_requests.py   # Tin nhắn chờ
├── _reactions.py          # Thả / gỡ reaction
├── _send.py               # Gửi tin nhắn (HTTP)
├── _send_e2ee.py          # Bridge Go — sender E2EE (tin nhắn 1-1)
├── _unsend.py             # Thu hồi tin nhắn
├── README.md              # ← bạn đang ở đây
└── README_EN.md
```

---

## 📦 Public API

```python
# src/_messaging/__init__.py
__all__ = [
    "_attachments", "_listening", "_listening_e2ee", "_reactions",
    "_send", "_send_e2ee", "_unsend", "_message_requests", "_createNotes",
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

### `_listening_e2ee.py`

#### `class listeningE2EEEvent(dataFB, *, log_level="none", binary=None)`

Lắng nghe tin nhắn **E2EE** (1-1) thông qua binary Go `fbchat-bridge-e2ee` chạy ngầm. Schema sự kiện trả về **giống hệt** [`_listening.py`](#listeningpy) để bạn hoán đổi 1-1 mà không phải sửa logic xử lý.

| Method | Mô tả |
|---|---|
| `get_last_seq_id()` | In `last_seq_id` ra console (parity với `_listening.py`). |
| `connect_mqtt()` | Spawn bridge, đăng nhập, nhận tin nhắn E2EE. **Blocking**. |
| `on_message(fn)` | Decorator/handler: callback nhận `dict` event (đã decrypt). |
| `stop()` | Dừng bridge và đóng subprocess. |

**Khi có sự kiện** — `self.bodyResults` chứa cùng các trường với `_listening.py`:

```text
body · timestamp · userID · messageID · replyToID · type
attachments.id · attachments.url
```

Thêm `self.e2eeBodyResults` cho metadata Signal: `chatJid` · `senderJid`.

**Yêu cầu:**

- Binary tại `fbchat-v2/build/fbchat-bridge-e2ee[.exe]` hoặc đường dẫn từ env `FBCHAT_E2EE_BIN`.
- Hướng dẫn build: [`bridge-e2ee/README.md`](../../bridge-e2ee/README.md).

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

> Riêng `_listening_e2ee.py` còn cần binary Go `fbchat-bridge-e2ee` (subprocess, không phải Python dependency).

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

### Lắng nghe E2EE (tin nhắn 1-1)

```python
import threading
from _messaging._listening_e2ee import listeningE2EEEvent

listener = listeningE2EEEvent(dataFB)
listener.get_last_seq_id()

@listener.on_message
def handle(evt):
    print(listener.bodyResults)        # cùng schema với _listening.py
    print(listener.e2eeBodyResults)    # chatJid / senderJid

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
| `FileNotFoundError` ở `_listening_e2ee` | Build binary `fbchat-bridge-e2ee` (xem `bridge-e2ee/README.md`) hoặc set env `FBCHAT_E2EE_BIN`. |
| Bridge crash khi `connect_mqtt()` | Kiểm tra cookie còn hiệu lực + log stderr (mặc định bật); thử lại sau khi đăng nhập lại Messenger. |

---

<div align="right">

⬆️ [Về README chính](../../README.md) · 🇬🇧 [English](README_EN.md)

</div>
