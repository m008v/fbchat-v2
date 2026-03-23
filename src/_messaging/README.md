# _messaging (`src/_messaging`)

`_messaging` là phần để triển khai các tính năng nhắn tin. Thư mục này tập trung vào thao tác Messenger trực tiếp, không xử lý lớp nền session/token như `_core`:

- Gửi tin nhắn văn bản vào user hoặc thread.
- Upload tệp đính kèm để gửi qua Messenger.
- Lắng nghe sự kiện tin nhắn realtime qua MQTT/WebSocket.
- Thêm/xóa reaction cho tin nhắn.
- Thu hồi tin nhắn đã gửi.
- Lấy danh sách tin nhắn chờ (Message Requests).

---

## 1) Sơ đồ thư mục

```text
src/_messaging/
├── __init__.py
├── _attachments.py
├── _listening.py
├── _message_requests.py
├── _reactions.py
├── _send.py
├── _unsend.py
└── README.md
```

### export chính

`src/_messaging/__init__.py` hiện export:

```python
__all__ = [
    '_attachments',
    '_listening',
    '_reactions',
    '_send',
    '_unsend',
    '_message_requests'
]
```

Nghĩa là bạn có thể import qua `_messaging` để dùng các module nhắn tin cốt lõi.

---

## 2) Nhiệm vụ chính (***QUAN TRỌNG***): `_messaging_`

### `_messaging` được ứng dụng để:

- Đóng gói endpoint Messenger thành hàm/class Python dễ gọi.
- Tái sử dụng `dataFB` từ `_core._session` để xác thực request.
- Chuẩn hóa thao tác gửi/nhận/react/unsend theo từng module riêng.
- Hỗ trợ bot/tool xử lý tin nhắn đồng bộ (HTTP) và realtime (MQTT).

---

## 3) Dữ liệu đầu vào chung (***QUAN TRỌNG***): `dataFB`

Hầu hết API trong `_messaging` nhận `dataFB` làm tham số đầu vào.

### Các giá trị thường được dùng:

- `fb_dtsg`
- `jazoest`
- `FacebookID`
- `clientRevision`
- `cookieFacebook`

`dataFB` được tạo từ `_core._session.dataGetHome(setCookies)`.

---

## 4) Tài liệu module chi tiết

## 4.1 `_send.py`

### Class: `api`

Đây là module gửi tin nhắn chính.

### Hàm quan trọng: `send(...)`

```python
send(
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

### Đầu vào

- `contentSend`: nội dung tin nhắn.
- `threadID`: ID nhóm hoặc user cần nhắn.
- `typeChat`:
  - `"user"`: nhắn trực tiếp user.
  - `None`: nhắn vào thread/group.
- `typeAttachment`: loại tệp gửi kèm, hỗ trợ:
  - `"gif"`, `"image"`, `"video"`, `"file"`, `"audio"`
- `attachmentID`: ID tệp đính kèm (sau khi upload).
- `replyMessage` + `messageID`: dùng cho luồng trả lời tin nhắn.

### Đầu ra

- Thành công:
  - `{ "success": 1, "payload": { "messageID": ..., "timestamp": ... } }`
- Thất bại:
  - `{ "error": 1, "payload": { "error-decription": ..., "error-code": ... } }`

### Lưu ý

- Module tự sinh `offline_threading_id`, `message_id`, `threading_id`.
- Response từ endpoint `/messaging/send/` có tiền tố `for (;;);`, module đã xử lý tách trước `json.loads`.

---

## 4.2 `_listening.py`

### Class: `listeningEvent`

Module lắng nghe tin nhắn realtime qua MQTT over WebSocket (`wss://edge-chat.facebook.com/...`).

### Khởi tạo

```python
listeningEvent(dataFB)
```

### function chính

- `connect_mqtt()`
  - Thiết lập MQTT client, subscribe queue sync, nhận delta tin nhắn.

### Dữ liệu nhận được

Khi có sự kiện, class cập nhật `self.bodyResults`:

- `body`, `timestamp`, `userID`, `messageID`, `replyToID`, `type`
- `attachments.id`, `attachments.url`

### Tính năng nổi bật

- Có cơ chế reconnect khi disconnect bất thường.
- Có xử lý `errorCode == 100` (queue overflow) bằng reset queue token.
- `connect_mqtt()` dùng `loop_forever()`, nên thường chạy trong thread riêng.

---

## 4.3 `_attachments.py`

### Hàm: `_uploadAttachment(filenames, dataFB)`

- Mục đích: upload tệp lên Facebook để lấy `attachmentID` dùng cho gửi tin.
- Endpoint: `https://upload.facebook.com/ajax/mercury/upload.php`

### Đầu vào

- `filenames`: đường dẫn tệp cần upload.
- `dataFB`: chứa `cookieFacebook`, `fb_dtsg`, ....

### Đầu ra

```python
{
    "attachmentID": ...,
    "attachmentUrl": ...,
    "attachmentType": ...,
    "attachmentDataSend": None,
}
```

### Lưu ý

- Hàm hiện thiết kế theo flow một đường dẫn tệp mỗi lần gọi.
- Khi upload lỗi, module in lỗi trực tiếp thay vì ném exception chi tiết.

---

## 4.4 `_reactions.py`

### Hàm: `func(dataFB, typeAdded, messageID, emojiChoice)`

- Mục đích: thêm hoặc xóa reaction trên tin nhắn.
### Đầu vào
  - `messageID`: ID tin nhắn cần reaction.
  - `typeAdded`:
    - `"add"` => thêm reaction
    - giá trị khác => remove reaction
    

### Đầu ra

- Trả về trực tiếp `requests.Response`.
- Bạn cần tự parse `response.text` nếu muốn kiểm tra sâu kết quả.

---

## 4.5 `_unsend.py`

### Hàm: `func(messageID, dataFB)`

- Mục đích: thu hồi tin nhắn theo `messageID`.

### Đầu vào

- `messageID`: ID tin nhắn cần thu hồi.
- Endpoint: `/messaging/unsend_message/`.

### Đầu ra

- Thành công: `{ "success": 1, "messages": "Thu hồi tin nhắn thành công." }`
- Lỗi: trả về object `Exception({...})`.

---

## 4.6 `_message_requests.py`

### Hàm: `func(dataFB)`

- Mục đích: lấy danh sách tin nhắn chờ (`PENDING`).

### Đầu ra

- Thành công:
  - `{ "success": 1, "messageRequests": "<json string đã format>" }`
- Nội dung gồm danh sách người gửi, snippet, timestamp và `total_count`.

---

## 5) Sơ đồ phụ thuộc trong dự án

`_messaging` phụ thuộc chính vào `_core._utils` và `dataFB`:

- `_core._session` -> `dataGetHome(setCookies)`
- `formAll`
- `mainRequests`
- `gen_threading_id`
- `generate_session_id`, `generate_client_id`, `json_minimal`
- `str_base`, `get_files_from_paths`
- `Headers`, `parse_cookie_string`

Ngoài ra có phụ thuộc thư viện ngoài:

- `requests`
- `paho-mqtt`

---

## 6) Mã nguồn mẫu

## 6.1 Gửi tin nhắn văn bản vào thread

```python
from _messaging._send import api

sender = api()
result = sender.send(dataFB, "Xin chào", "1234567890")
print(result)
```

## 6.2 Upload ảnh rồi gửi kèm tin nhắn

```python
from _messaging._attachments import _uploadAttachment
from _messaging._send import api

uploaded = _uploadAttachment("path/to/image.jpg", dataFB)

sender = api()
result = sender.send(
    dataFB,
    "Ảnh của bạn đây",
    "1234567890",
    typeAttachment="image",
    attachmentID=uploaded["attachmentID"],
)
print(result)
```

## 6.3 React vào tin nhắn

```python
from _messaging._reactions import Main

resp = Main(dataFB, "add", "mid.$abc...", "👍")
print(resp.status_code, resp.text)
```

## 6.4 Thu hồi tin nhắn

```python
from _messaging._unsend import _unsend

result = _unsend("mid.$abc...", dataFB)
print(result)
```

## 6.5 Lấy danh sách tin nhắn chờ

```python
from _messaging._message_requests import func

result = func(dataFB)
print(result)
```

## 6.6 Lắng nghe tin nhắn realtime

```python
from _messaging._listening import listeningEvent

listener = listeningEvent(fbt, dataFB)
listener.get_last_seq_id()
listener.connect_mqtt()  # blocking
```

---

## 7) Lỗi có thể gặp và hướng xử lý

### TH.1: gửi tin nhắn thất bại

- Kiểm tra cookie còn hạn và `dataFB` còn hợp lệ.
- Kiểm tra `threadID`/`userID` đúng định dạng.
- Nếu gửi kèm file, xác minh `typeAttachment` khớp với ID đã upload.

### TH.2: upload tệp lỗi

- Đảm bảo đường dẫn file tồn tại và đọc được.
- Kiểm tra quyền truy cập file trên máy chạy bot/tool.
- Kiểm tra response upload vì API có thể thay đổi metadata key.

### TH.3: listener tự ngắt hoặc không nhận event

- Chạy listener trong thread riêng (do `loop_forever()` blocking).
- Kiểm tra log `errorCode` trong MQTT payload.
- Nếu bị queue overflow (`errorCode = 100`), module đã có cơ chế reset nhưng vẫn nên theo dõi reconnect.

### TH.4: lỗi parse JSON response

- Nhiều endpoint trả chuỗi có tiền tố `for (;;);`.
- Cần tách tiền tố trước khi `json.loads`.

