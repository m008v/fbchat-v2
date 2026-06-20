# `_messaging` — Tầng nhắn tin

> Mọi thao tác Messenger trực tiếp: gửi, sửa, nhận realtime, upload tệp, react, thu hồi, đổi theme, message requests.

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
  - [`_editMessage.py`](#editmessagepy)
  - [`_send_e2ee.py`](#send_e2eepy)
  - [`_listening.py`](#listeningpy)
  - [`_listening_e2ee.py`](#listening_e2eepy)
  - [`_attachments.py`](#attachmentspy)
  - [`_reactions.py`](#reactionspy)
  - [`_changeTheme.py`](#changethemepy)
  - [`_unsend.py`](#unsendpy)
  - [`_message_requests.py`](#message_requestspy)
  - [`_createNotes.py`](#createnotespy)
- [Sơ đồ phụ thuộc](#-sơ-đồ-phụ-thuộc)
- [Ví dụ](#-ví-dụ)
- [Khắc phục sự cố](#-khắc-phục-sự-cố)

---

## 🎯 Vai trò

`_messaging` đóng gói các endpoint Messenger thành hàm/class Python dễ dùng. Tầng này **không** xử lý session/token (đã có `_core`):

- 📤 Gửi tin văn bản tới user hoặc thread.
- ✏️ Sửa tin nhắn đã gửi qua MQTT LS task.
- 📎 Upload tệp đính kèm để gửi qua Messenger.
- 📡 Lắng nghe sự kiện realtime qua **MQTT over WebSocket**.
- ❤️ Thêm / xoá reaction.
- 🎨 Đổi theme / nền của thread Messenger.
- ↩️ Thu hồi tin nhắn đã gửi.
- 📥 Lấy danh sách **Message Requests** (tin nhắn chờ).
- 📝 Quản lý **Messenger Notes** (note 24h dạng status): check / create / delete / recreate.

---

## 📦 Cài đặt

`_messaging` đi kèm mã nguồn `fbchat-v2` — bạn không cài riêng. Phần này chỉ liệt kê **những gì module này cần** ở cấp runtime.

### 1. Phụ thuộc Python (đã có trong `requirements.txt`)

| Package | Dùng cho | Ghi chú |
|---|---|---|
| `requests` | `_send` · `_attachments` · `_reactions` · `_unsend` · `_message_requests` · `_createNotes` · `_changeTheme` | HTTP client |
| `paho-mqtt` | `_listening` · `_editMessage` · `_changeTheme` | MQTT over WebSocket / LS task |
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
├── _changeTheme.py        # Đổi theme / nền thread Messenger
├── _createNotes.py        # Messenger Notes (status 24h): check/create/delete/recreate
├── _editMessage.py        # Sửa tin nhắn đã gửi qua MQTT LS task
├── _listening.py          # MQTT realtime listener (tin nhắn nhóm)
├── _listening_e2ee.py     # Bridge Go — listener E2EE (tin nhắn 1-1)
├── _message_requests.py   # Tin nhắn chờ
├── _reactions.py          # Thả / gỡ reaction
├── _send.py               # Gửi tin nhắn (HTTP)
├── _send_e2ee.py          # Bridge Go — sender E2EE (tin nhắn 1-1 Secret Conversations)
├── _unsend.py             # Thu hồi tin nhắn
├── README.md              # ← bạn đang ở đây
└── README_EN.md
```

---

## 📦 Public API

```python
# src/_messaging/__init__.py
__all__ = [
    "_attachments", "_changeTheme", "_createNotes", "_editMessage",
    "_listening", "_listening_e2ee", "_reactions", "_send",
    "_send_e2ee", "_unsend", "_message_requests",
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
| `replyMessage` + `messageID` | Dùng cho luồng reply tin nhắn; set `replyMessage=True` và truyền `messageID` gốc. |

**Trả về:**

- ✅ `{ "success": 1, "payload": { "messageID": ..., "timestamp": ... } }`
- ❌ `{ "error": 1, "payload": { "error-decription": ..., "error-code": ... } }`

> 📝 Module tự sinh `offline_threading_id`, `message_id`, `threading_id`. Response `/messaging/send/` có tiền tố `for (;;);` — đã được tách sẵn.

---

### `_editMessage.py`

Sửa nội dung tin nhắn đã gửi bằng MQTT LS task `queue_name="edit_message"`.

```python
from _messaging import _editMessage

_editMessage.editMessage(dataFB, messageID="mid.$abc...", newText="Nội dung mới")

# Hoặc entry point thống nhất:
_editMessage.func(dataFB, "mid.$abc...", "Nội dung mới")
```

| Hàm | Mô tả |
|---|---|
| `editMessage(dataFB, messageID, newText, timeout=20)` | Publish LS task sửa tin nhắn. |
| `func(dataFB, messageID, newText, timeout=20)` | Alias theo style module fbchat-v2. |

**Trả về:**

- ✅ `{ "success": 1, "messages": "...", "data": { "messageID": ..., "text": ... } }`
- ❌ `{ "error": 1, "messages": "...", "payload": {...} }`

> ⚠️ Facebook thường chỉ cho sửa tin nhắn do chính tài khoản hiện tại gửi.
> Success ở module này nghĩa là LS task đã publish lên `/ls_req`; server có
> thể vẫn từ chối nếu message quá cũ hoặc tài khoản không có quyền sửa.

---

### `_send_e2ee.py`

#### `class api`

Phiên bản E2EE của `_send.api` — gửi tin nhắn text vào cuộc trò chuyện
1-1 (Secret Conversations) thông qua bridge Go (`fbchat-bridge-e2ee`). Schema
return **giống hệt** `_send.api.send` nên code gọi không cần branch riêng.

Hai chế độ khởi tạo:

```python
# A) Reuse bridge của listener — KHUYẾN NGHỊ.
#    Không cần pair lại, không bắn thông báo "đăng nhập thiết bị mới".
sender = api(listener=listeningE2EEEvent_instance)

# B) Standalone — spawn bridge riêng.
sender = api(
    dataFB=dataFB,
    log_level="warn",
    device_path=None,        # đặt path + e2ee_memory_only=False để persist Signal keys
    e2ee_memory_only=True,
    binary_path=None,        # auto-resolve build/fbchat-bridge-e2ee[.exe]
)
sender.connect()             # blocking pairing — chỉ dùng cho standalone
```

| Method | Mô tả |
|---|---|
| `send(chat_jid, contentSend, replyMessage="", replySenderJid="")` | Gửi 1 tin nhắn E2EE text. `chat_jid` có thể là JID Messenger `<facebook_id>@msgr` hoặc chỉ Facebook numeric ID; module tự normalize thành `@msgr`. **Không** truyền group `threadID`. |
| `send_to_user(user_id, contentSend, replyMessage="", replySenderJid="")` | Gửi chủ động bằng Facebook numeric ID, ví dụ `send_to_user("100012345678", "hello")`. |
| `reply(evt_data, contentSend)` | Helper: tự bóc `chatJid`, `id`, `senderJid` từ event listener để quote-reply. |
| `connect(*, enable_e2ee=True, timeout=120)` | Chỉ standalone. Gọi `newClient` → `connect` → `connectE2EE` trên bridge. |
| `close()` | Chỉ standalone. Đóng bridge subprocess mình sở hữu. |
| `__enter__` / `__exit__` | Standalone dùng `with` — tự `connect()` + `close()`. |

**Trả về** — cùng schema với [`_send.py`](#sendpy):

- ✅ `{ "success": 1, "payload": { "messageID": ..., "timestamp": ... } }`
- ❌ `{ "error": 1, "payload": { "error-decription": ..., "error-code": "bridge_error" | "not_connected" } }`

> ⚠️ Gửi media E2EE (`SendE2EEImage` / `Video` / `Audio`) đã có trong bridge
> Go nhưng **chưa** được expose qua wrapper Python — hiện tại chỉ gửi text.

---

### `_listening.py`

#### `class listeningEvent(dataFB)`

Lắng nghe sự kiện realtime qua **MQTT over WebSocket** (`wss://edge-chat.facebook.com/...`).

| Method | Mô tả |
|---|---|
| `get_last_seq_id()` | Lấy & cập nhật `last_seq_id` mới nhất. |
| `get_message(block=False, timeout=None)` | Lấy từng message event từ queue. Trả `None` nếu queue rỗng. |
| `connect_mqtt()` | Khởi tạo MQTT client, subscribe sync queue, nhận message delta. **Blocking** (`loop_forever()`). |

**Khi có sự kiện** — listener push từng message vào `self.messageQueue`. Mỗi item có schema:

```text
body · timestamp · userID · messageID · replyToID · type
attachments.id · attachments.url
```

`self.bodyResults` vẫn được cập nhật như snapshot cuối để tương thích code cũ, nhưng bot mới nên đọc qua `get_message()` để không mất tin khi nhiều delta về cùng lúc.

Queue mặc định giới hạn `1000` event. Khi consumer chết hoặc xử lý quá chậm, listener **drop event cũ nhất**, tăng `droppedMessages`, và log rõ ràng thay vì để RAM phình vô hạn.

**Highlights:**

- Có cơ chế **reconnect** khi disconnect bất thường.
- MQTT WebSocket bật TLS certificate verification; không dùng `ssl.CERT_NONE` khi gửi cookie phiên.
- Parse toàn bộ `deltas` trong payload MQTT, không chỉ lấy phần tử đầu tiên.
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

### `_changeTheme.py`

Lấy danh sách theme Messenger và đổi theme / nền của một thread bằng MQTT LS
tasks. Module này port flow từ `ws3-fca/theme.js` sang style fbchat-v2.

```python
from _messaging import _changeTheme

_changeTheme.listThemes(dataFB)
_changeTheme.findTheme(dataFB, "love")
_changeTheme.changeTheme(dataFB, threadID="1234567890", themeName="love")

# Entry point chung:
_changeTheme.func(dataFB, action="list")
_changeTheme.func(dataFB, "1234567890", "default")
```

| Hàm | Mô tả |
|---|---|
| `listThemes(dataFB)` | Gọi GraphQL `MWPThreadThemeQuery_AllThemesQuery` để lấy danh sách theme. |
| `findTheme(dataFB, themeName)` | Match theo ID, tên chính xác, hoặc tên chứa keyword. |
| `changeTheme(dataFB, threadID, themeName, initiatorID=None, timeout=20)` | Publish 4 LS task đổi theme cho thread. |
| `func(dataFB, threadID=None, themeName=None, action="set", **kwargs)` | Entry point chung: `list` / `find` / `set`. |

**Trả về:**

- ✅ `{ "success": 1, "messages": "...", "data": { "threadID": ..., "themeID": ..., "themeName": ... } }`
- ❌ `{ "error": 1, "messages": "...", "details"|"payload"|"raw": ... }`

**Cơ chế:**

- `listThemes` dùng GraphQL `doc_id=24474714052117636`.
- `changeTheme` publish 4 queue: `ai_generated_theme`,
  `msgr_custom_thread_theme`, `thread_theme_writer`, `thread_theme`.

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

### `_createNotes.py`

Quản lý **Messenger Notes** — note dạng status hiển thị trên đầu inbox
Messenger, mặc định tồn tại 24 giờ. Module được port từ `ws3-fca/notes.js`
(@ChoruOfficial) sang style fbchat-v2.

```python
from _messaging import _createNotes

_createNotes.checkNote(dataFB)
_createNotes.createNote(dataFB, text, privacy="FRIENDS")
_createNotes.deleteNote(dataFB, noteID)
_createNotes.recreateNote(dataFB, oldNoteID, newText, privacy="FRIENDS")

# Hoặc dùng entry point thống nhất:
_createNotes.func(dataFB, action="check")
_createNotes.func(dataFB, action="create",   text="Hello", privacy="FRIENDS")
_createNotes.func(dataFB, action="delete",   noteID="<note_id>")
_createNotes.func(dataFB, action="recreate", oldNoteID="<id>", newText="...")
```

| Hàm | Mô tả |
|---|---|
| `checkNote(dataFB)` | Trả về note hiện tại của tài khoản (`msgr_user_rich_status`). |
| `createNote(dataFB, text, privacy="FRIENDS")` | Tạo note text mới, thời lượng 86400s (24h). |
| `deleteNote(dataFB, noteID)` | Xoá note theo `rich_status_id`. |
| `recreateNote(dataFB, oldNoteID, newText, privacy="FRIENDS")` | Xoá note cũ rồi tạo note mới (atomic 2-step). |
| `func(dataFB, action, **kwargs)` | Entry point chung — `action` ∈ `"check" / "create" / "delete" / "recreate"`. |

**Tham số `privacy`** (case-insensitive):

| Giá trị truyền vào | Được map thành |
|---|---|
| `"FRIENDS"` *(mặc định)* | `FRIENDS` |
| `"EVERYONE"` · `"PUBLIC"` | `FRIENDS` *(Messenger Notes hiện chỉ hỗ trợ FRIENDS)* |
| Khác | Giữ nguyên dạng UPPERCASE |

**Trả về:**

- ✅ `{ "success": 1, "messages": "...", "data": {...} }`
- ❌ `{ "error": 1, "messages": "...", "details"|"raw": ... }`

**Cơ chế:**

- Gọi 3 GraphQL `friendly_name` / `doc_id` riêng (check / create / delete).
- Có **timeout** `(connect=10s, read=45s)` và **retry** tối đa 2 lần với
  `requests.Timeout` / `requests.RequestException`.
- Tự strip prefix `for (;;);` của response Facebook trước khi `json.loads`.
- `client_mutation_id` random 0–10, `session_id` sinh bằng
  `_core._utils.generate_client_id()`.

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

> Riêng `_listening_e2ee.py` **và** `_send_e2ee.py` còn cần binary Go `fbchat-bridge-e2ee` (subprocess, không phải Python dependency). `_send_e2ee.py` tái sử dụng `_BridgeProcess`, `_resolve_binary` và `parse_cookie_string` từ `_listening_e2ee.py` — hai module có thể chia sẻ chung 1 bridge.

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

### Sửa tin nhắn đã gửi

```python
from _messaging import _editMessage

print(_editMessage.editMessage(dataFB, "mid.$abc...", "Nội dung mới"))
```

### Đổi theme / nền thread

```python
from _messaging import _changeTheme

print(_changeTheme.func(dataFB, action="list"))
print(_changeTheme.changeTheme(dataFB, "1234567890", "love"))
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

### Tạo / xoá Messenger Note (status 24h)

```python
from _messaging import _createNotes

# Xem note hiện tại
print(_createNotes.checkNote(dataFB))

# Tạo note mới (mặc định 24h, privacy FRIENDS)
created = _createNotes.createNote(dataFB, "Đang code fbchat-v2 ❤️")
note_id = created["data"]["id"]

# Xoá note
_createNotes.deleteNote(dataFB, note_id)

# Hoặc thay note cũ bằng note mới trong 1 call
_createNotes.recreateNote(dataFB, note_id, "Đã xong v2.1.3 🎉")
```

### Lắng nghe realtime

```python
import threading
from _messaging._listening import listeningEvent

listener = listeningEvent(dataFB)
listener.get_last_seq_id()
threading.Thread(target=listener.connect_mqtt, daemon=True).start()

while True:
    event = listener.get_message(block=True, timeout=1)
    if event:
        print(event["body"])
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

### Gửi tin nhắn E2EE (reuse bridge của listener)

```python
import threading
from _messaging._listening_e2ee import listeningE2EEEvent
from _messaging._send_e2ee import api as E2EESender

listener = listeningE2EEEvent(dataFB)
threading.Thread(target=listener.connect_mqtt, daemon=True).start()
# (đợi event "e2eeConnected" trước khi gửi)

sender = E2EESender(listener=listener)

@listener.on_message
def on_msg(evt):
    if evt["type"] == "e2eeMessage" and evt["data"].get("text") == "ping":
        print(sender.reply(evt["data"], "pong"))
        # → {'success': 1, 'payload': {'messageID': '3EB0…', 'timestamp': 1715000000000}}
```

### Gửi tin nhắn E2EE (standalone — không listener)

```python
from _messaging._send_e2ee import api as E2EESender

with E2EESender(dataFB=dataFB, log_level="warn") as sender:
    sender.send(
        chat_jid    = "100012345678",
        contentSend = "hello E2EE",
    )
    sender.send_to_user("100012345678", "hello chủ động")
```

---

## 🛠 Khắc phục sự cố

| Triệu chứng | Hướng xử lý |
|---|---|
| Gửi tin nhắn thất bại | Kiểm tra cookie & `dataFB` còn hợp lệ; verify `threadID`/`userID`; `typeAttachment` khớp với file đã upload. |
| Upload tệp lỗi | Verify đường dẫn tồn tại + quyền đọc; kiểm tra metadata response (Facebook có thể đổi key). |
| `_editMessage` / `_changeTheme` timeout khi publish | Kiểm tra cookie còn sống, mạng WebSocket tới `edge-chat.facebook.com`, và quyền thao tác trong thread. |
| `_send_e2ee.api` trả `{"error": 1, ..., "error-code": "not_connected"}` | Standalone quên gọi `sender.connect()`; chế độ reuse đợi `connect_mqtt()` của listener đến event `e2eeConnected`. |
| `_send_e2ee.api` trả `{"error": 1, ..., "error-code": "invalid_chat_jid"}` | Truyền sai đích gửi. Dùng JID đầy đủ `<facebook_id>@msgr` hoặc Facebook numeric ID; không dùng group `threadID` / username. |
| Bridge log `can't encrypt message for device: no signal session established` | Dùng bridge binary mới đã rebuild; bridge giờ tự chạy task tạo encrypted DM và báo missing session đúng để `whatsmeow` fetch prekey trước khi send. Khi test nhiều lần, thêm `--persist-device --device-path ./e2ee_device.json` để giữ Signal session. |
| `_send_e2ee.api` trả `{"error": 1, ..., "error-code": "bridge_error"}` | Bridge Go subprocess chết hoặc JSON-RPC call lỗi — bật `log_level="debug"` để xem stderr của bridge. |
| `ValueError: Phải truyền 'listener=' (reuse) HOẶC 'dataFB=' (standalone)` | Truyền đúng một trong hai — `listener=` hoặc `dataFB=` — cho `_send_e2ee.api(...)`. |
| Listener tự ngắt / không nhận event | Chạy trong thread riêng (`loop_forever()` blocking); theo dõi `errorCode` trong MQTT payload; quan tâm `errorCode == 100` (queue overflow). |
| Bot bị mất tin khi nhiều message tới nhanh | Đọc bằng `listener.get_message()` / `messageQueue`; đừng poll mỗi `bodyResults` vì đó chỉ là snapshot cuối. Nếu log báo `messageQueue full`, consumer đang chết hoặc xử lý quá chậm. |
| Lỗi parse JSON | Loại tiền tố `for (;;);` trước `json.loads`. |
| `FileNotFoundError` ở `_listening_e2ee` | Build binary `fbchat-bridge-e2ee` (xem `bridge-e2ee/README.md`) hoặc set env `FBCHAT_E2EE_BIN`. |
| Bridge crash khi `connect_mqtt()` | Kiểm tra cookie còn hiệu lực + log stderr (mặc định bật); thử lại sau khi đăng nhập lại Messenger. |

---

<div align="right">

⬆️ [Về README chính](../../README.md) · 🇬🇧 [English](README_EN.md)

</div>
