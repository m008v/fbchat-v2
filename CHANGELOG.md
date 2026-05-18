# Changelog

Tất cả thay đổi đáng chú ý của `fbchat-v2` sẽ được ghi lại tại đây.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/),
phiên bản tuân theo [Semantic Versioning](https://semver.org/lang/vi/).

---
## [2.1.5] — 2026-05-18

### ✨ Added

- **`_messaging/_editMessage.py`** — module mới cho phép **sửa tin nhắn đã gửi**
  bằng MQTT Lightspeed task `queue_name="edit_message"` publish lên `/ls_req`.
  - API chính: `editMessage(dataFB, messageID, newText, timeout=20)`.
  - Alias theo style fbchat-v2: `func(dataFB, messageID, newText, timeout=20)`.
  - Tự mở kết nối MQTT WebSocket ngắn hạn tới `edge-chat.facebook.com`, publish
    task rồi đóng client.
  - Schema return: ✅ `{"success": 1, "messages": "...", "data": {...}}`
    / ❌ `{"error": 1, "messages": "...", "payload": {...}}`.

- **`_messaging/_changeTheme.py`** — module mới để **lấy danh sách theme và đổi
  nền / theme thread Messenger**.
  - `listThemes(dataFB)` gọi GraphQL
    `MWPThreadThemeQuery_AllThemesQuery` (`doc_id=24474714052117636`).
  - `findTheme(dataFB, themeName)` match theo theme ID, tên chính xác, hoặc
    keyword không phân biệt hoa thường.
  - `changeTheme(dataFB, threadID, themeName, initiatorID=None, timeout=20)`
    publish 4 LS queues: `ai_generated_theme`, `msgr_custom_thread_theme`,
    `thread_theme_writer`, `thread_theme`.
  - `func(dataFB, threadID=None, themeName=None, action="set", **kwargs)` hỗ trợ
    `action="list"`, `action="find"`, và set theme mặc định.

- **`fbchat_v2.__init__`**: re-export `editMessage` và `changeTheme` ở top-level
  (`from fbchat_v2 import editMessage, changeTheme`).

### 📝 Documentation

- README PyPI: thêm section **"Edit messages and thread themes"** với ví dụ,
  bảng function reference, return shape và lưu ý quyền thao tác server-side.
- README PyPI: cập nhật feature list, cây thư mục `_messaging/`, bảng Public API,
  Architecture và Roadmap.
- Sub-README `_messaging/` VI/EN: cập nhật tree, `__all__`, dependency map,
  module reference, ví dụ và troubleshooting cho `editMessage` / `changeTheme`.

### 🛠 Changed

- Bump `__version__` → `2.1.5`.
- `pyproject.toml` → `version = "2.1.5"`.
- `_messaging/__init__.py`: `__all__` thêm `_editMessage`, `_changeTheme`.

### 📦 Dependencies

- Không thay đổi. Hai module mới dùng lại `requests` và `paho-mqtt` đã có sẵn.

### ⚠️ Lưu ý nâng cấp

```bash
pip install --upgrade fbchat-v2
```

Không có breaking change so với 2.1.4; mọi import cũ vẫn hoạt động bình thường.

---
## [2.1.4] — 2026-05-15

### ✨ Added

- **`_messaging/_createNotes.py`** — module mới quản lý **Messenger Notes**
  (status 24h hiển thị trên đầu inbox Messenger). Port từ
  `ws3-fca/notes.js` (© @ChoruOfficial) sang style fbchat-v2.
  - 4 hàm CRUD: `checkNote(dataFB)` · `createNote(dataFB, text, privacy="FRIENDS")`
    · `deleteNote(dataFB, noteID)` · `recreateNote(dataFB, oldNoteID, newText, privacy="FRIENDS")`.
  - Entry point thống nhất: `func(dataFB, action="check"|"create"|"delete"|"recreate", **kwargs)`.
  - Mỗi call dùng GraphQL `friendly_name` / `doc_id` riêng (3 endpoint:
    `MWInboxTrayNoteCreationDialogQuery`, `MWInboxTrayNoteCreationDialogCreationStepContentMutation`,
    `useMWInboxTrayDeleteNoteMutation`).
  - **Privacy mapping**: `EVERYONE` / `PUBLIC` đều bị normalize về `FRIENDS`
    (Messenger Notes hiện chỉ hỗ trợ scope FRIENDS).
  - **Resilience**: timeout `(connect=10s, read=45s)` + 2 retries cho
    `requests.Timeout` / `requests.RequestException` (tổng ≤ 3 lần thử).
  - Tự strip prefix `for (;;);` trước khi `json.loads`.
  - Schema return: ✅ `{"success": 1, "messages": "...", "data": {...}}`
    / ❌ `{"error": 1, "messages": "...", "details"|"raw": ...}`.
  - Hard-coded `duration = 86400s` (24h) — Messenger web flow chưa hỗ trợ
    duration tuỳ ý.
  - **Hạn chế**: chỉ `note_type="TEXT_NOTE"` (chưa wire music / sticker).

- **`fbchat_v2.__init__`**: re-export `createNotes` ở top-level
  (`from fbchat_v2 import createNotes` → `createNotes.checkNote(dataFB)` …).

### 📝 Documentation

- README PyPI: section mới **"Messenger Notes (24h status) — `createNotes`"**
  với ví dụ CRUD, bảng function reference (kèm GraphQL `friendly_name`),
  bảng privacy mapping, return shape, internals.
- README PyPI: cập nhật cây thư mục `_messaging/` thêm `_createNotes.py`,
  bảng Public API thêm dòng `createNotes`.
- Sub-README `_messaging/`: cập nhật cây thư mục + `__all__`.

### 🛠 Changed

- Bump `__version__` → `2.1.4`.
- `pyproject.toml` → `version = "2.1.4"`.
- `_messaging/__init__.py`: `__all__` thêm `_createNotes`, `_listening_e2ee`,
  `_send_e2ee` (đồng bộ với các module đã thêm trong các bản trước).

### 📦 Dependencies

- Không thay đổi.

### ⚠️ Lưu ý nâng cấp

```bash
pip install --upgrade fbchat-v2
```

Không có breaking change so với 2.1.3; mọi import cũ vẫn hoạt động bình thường.

---
## [2.1.3] — 2026-05-13

> **Stable release.** Promotes the `2.1.2a1` alpha to a full release so the
> new `sendingE2EEEvent` shows up on the main PyPI project page and gets
> picked up by `pip install fbchat-v2` (no `--pre` needed).

### ✨ Added

- **`_messaging/_send_e2ee.py`** — module mới `class api` (alias công khai
  `sendingE2EEEvent`) cho phép **gửi tin nhắn E2EE** (Secret Conversations)
  vào các cuộc trò chuyện 1-1 thông qua bridge Go `fbchat-bridge-e2ee`.
  - Hai chế độ khởi tạo:
    - **Reuse** (khuyến nghị): `sendingE2EEEvent(listener=listeningE2EEEvent_instance)`
      — dùng chung bridge với listener, không pair lại với Meta, không bắn
      thông báo "đăng nhập thiết bị mới" cho người nhận.
    - **Standalone**: `sendingE2EEEvent(dataFB=..., log_level=, device_path=,
      e2ee_memory_only=, binary_path=)` rồi `sender.connect()` — spawn bridge
      riêng. Hỗ trợ context manager (`with sendingE2EEEvent(dataFB=...) as sender:`)
      tự `connect()` + `close()`.
  - API chính: `send(chat_jid, contentSend, replyMessage="", replySenderJid="")`
    — gọi RPC `sendE2EEMessage` qua bridge Go.
  - Helper `reply(evt_data, contentSend)` tự bóc `chatJid` / `id` / `senderJid`
    từ event của `listeningE2EEEvent` để quote-reply nhanh.
  - **Schema return trùng khớp `_send.api.send`** — caller code không cần branch:
    - ✅ `{"success": 1, "payload": {"messageID": str, "timestamp": int}}`
    - ❌ `{"error": 1, "payload": {"error-decription": str, "error-code": "bridge_error" | "not_connected"}}`

- **`fbchat_v2.__init__`**: re-export `sendingE2EEEvent` ở top-level cùng
  với `listeningEvent`, `listeningE2EEEvent`, `dataGetHome`.

### 📝 Documentation

- README PyPI: section **"1-on-1 E2EE sender — `sendingE2EEEvent`"** với
  ví dụ Mode A (reuse) + Mode B (standalone with-statement), bảng đối số
  `send(...)`, bảng method tiện ích, cảnh báo `chat_jid` vs `threadID`.
- README PyPI: cập nhật cây thư mục, bảng Public API và liệt kê
  `_send_e2ee.py` mới.

### 🛠 Changed

- Bump `__version__` → `2.1.3` (promote `2.1.2a1` → stable).
- `pyproject.toml` → `version = "2.1.3"`.

### 📦 Dependencies

- Không thay đổi.

### ⚠️ Lưu ý nâng cấp

```bash
pip install --upgrade fbchat-v2
```

Không có breaking change so với 2.1.2; mọi import cũ vẫn hoạt động bình thường.

---
## [2.1.2a1] — 2026-05-13

> **Pre-release alpha.** Bổ sung sender E2EE để ghép cặp với listener đã có
> từ 2.1.0. Schema return tương thích 100% với `_send.api` cũ — caller code
> chỉ cần import thêm là dùng được.

### ✨ Added

- **`_messaging/_send_e2ee.py`** — module mới `class api` (alias công khai
  `sendingE2EEEvent`) cho phép **gửi tin nhắn E2EE** (Secret Conversations)
  vào các cuộc trò chuyện 1-1 thông qua bridge Go `fbchat-bridge-e2ee`.
  - Hai chế độ khởi tạo:
    - **Reuse** (khuyến nghị): `sendingE2EEEvent(listener=listeningE2EEEvent_instance)`
      — dùng chung bridge với listener, không pair lại với Meta, không bắn
      thông báo "đăng nhập thiết bị mới" cho người nhận.
    - **Standalone**: `sendingE2EEEvent(dataFB=..., log_level=, device_path=,
      e2ee_memory_only=, binary_path=)` rồi `sender.connect()` — spawn bridge
      riêng. Hỗ trợ context manager (`with sendingE2EEEvent(dataFB=...) as sender:`)
      tự `connect()` + `close()`.
  - API chính: `send(chat_jid, contentSend, replyMessage="", replySenderJid="")`
    — gọi RPC `sendE2EEMessage` qua bridge Go.
  - Helper `reply(evt_data, contentSend)` tự bóc `chatJid` / `id` / `senderJid`
    từ event của `listeningE2EEEvent` để quote-reply nhanh.
  - **Schema return trùng khớp `_send.api.send`** — caller code không cần branch:
    - ✅ `{"success": 1, "payload": {"messageID": str, "timestamp": int}}`
    - ❌ `{"error": 1, "payload": {"error-decription": str, "error-code": "bridge_error" | "not_connected"}}`
  - Tái sử dụng `_BridgeProcess`, `_resolve_binary`, `parse_cookie_string`,
    `_REQUIRED_COOKIES` từ `_listening_e2ee.py` — không nhân đôi logic
    discovery binary / parse cookie.

- **`fbchat_v2.__init__`**: re-export `sendingE2EEEvent` ở top-level cùng
  với `listeningEvent`, `listeningE2EEEvent`, `dataGetHome` — đặt tên đối
  xứng với `listeningE2EEEvent` cho dễ nhớ.

### 📝 Documentation

- README PyPI: thêm section **"1-on-1 E2EE sender — `sendingE2EEEvent`"** với
  ví dụ Mode A (reuse) + Mode B (standalone with-statement), bảng đối số
  `send(...)`, bảng method tiện ích, cảnh báo `chat_jid` vs `threadID`.
- README PyPI: cập nhật cây thư mục, bảng Public API và liệt kê
  `_send_e2ee.py` mới.

### 🛠 Changed

- Bump `__version__` → `2.1.2a1` (PEP 440 alpha pre-release).
- `pyproject.toml` → `version = "2.1.2a1"`.

### 📦 Dependencies

- Không thay đổi.

### ⚠️ Lưu ý nâng cấp

Đây là **bản pre-release alpha** — pip mặc định **bỏ qua** các bản pre-release.
Để cài chính thức:

```bash
pip install --upgrade --pre fbchat-v2
# hoặc khoá version:
pip install fbchat-v2==2.1.2a1
```

Không có breaking change so với 2.1.2; mọi import cũ vẫn hoạt động bình thường.

---
## [2.1.2] — 2026-05-12

> **Bug-fix tài liệu.** Không đổi runtime; chỉ sửa README trên PyPI vì
> đoạn Quick Start trước đó gọi sai chữ ký `dataGetHome(...)`.

### 🔧 Fixed

- README PyPI: sửa ví dụ `dataGetHome(cookies=YOUR_COOKIES)` (không tồn tại
  kwarg `cookies=`) thành `dataGetHome("c_user=...; xs=...; ...")` — đúng chữ
  ký `dataGetHome(setCookies)` (1 chuỗi positional).
- Bổ sung note giải thích `setCookies` là chuỗi `Cookie:` header copy từ
  DevTools, không phải dict.
- Quick Start E2EE: liệt kê đầy đủ keyword args `log_level`,
  `e2ee_memory_only`, `device_path`, `enable_e2ee`, `binary_path`; thêm
  block decorator `@listener.on_message` với ví dụ `send_e2ee_message`.

### 🛠 Changed

- Bump `__version__` → `2.1.2`.

### 📦 Dependencies

- Không thay đổi.

### ⚠️ Lưu ý nâng cấp

Không có breaking change. Cách nâng cấp:

```bash
pip install --upgrade fbchat-v2
```

---
## [2.1.0] — 2026-05-12

> **Bản cập nhật lớn:** chính thức hỗ trợ giải mã **End-to-End Encryption (E2EE)**
> cho tin nhắn cá nhân Messenger. Schema event giữ nguyên tương thích ngược 100%
> với `_listening.py` cũ — chỉ cần đổi import là chạy.

### ✨ Added

- **`_messaging/_listening_e2ee.py`** — class `listeningE2EEEvent(dataFB)` lắng
  nghe tin nhắn 1-1 đã giải mã, API tương thích `listeningEvent`:
  - `get_last_seq_id()`, `connect_mqtt()`, `on_message(fn)`, `stop()`.
  - Phơi `self.bodyResults` với **đúng schema của `_listening.py`**
    (`body`, `timestamp`, `userID`, `messageID`, `replyToID`, `type`,
    `attachments.id`, `attachments.url`).
  - Phơi thêm `self.e2eeBodyResults` (`chatJid`, `senderJid`) cho metadata
    Signal Protocol.
  - Tự suy luận `type` = `"user"` / `"thread"` (DM vs nhóm) từ `chatType` /
    `isGroup`, **không** dùng giá trị `"e2ee"` riêng.
  - Attachment fallback `"Unable to retrieve attachment ID"` giống legacy.
- **`bridge-e2ee/`** — bridge Go độc lập (`fbchat-bridge-e2ee[.exe]`) giao tiếp
  với Python qua line-delimited JSON-RPC trên stdin/stdout. Đóng gói Signal
  Protocol (`whatsmeow`) + Meta Labyrinth (`mautrix-meta`).
  - RPC methods: `newClient`, `connect`, `connectE2EE`, `isConnected`,
    `sendMessage`, `sendE2EEMessage`, `disconnect`.
  - Override đường dẫn binary qua biến môi trường `FBCHAT_E2EE_BIN`.
  - Mặc định nạp tại `fbchat-v2/build/fbchat-bridge-e2ee[.exe]`.
- **README** (cả tiếng Việt và tiếng Anh):
  - Mục **Yêu cầu hệ thống** mở rộng: thêm Go 1.24, Git, RAM, danh sách
    package Python kèm mục đích.
  - Mục **Cài đặt** 7 bước với sanity check `python -c "import ..."` và
    smoke test `python src/main.py`.
  - Hướng dẫn build bridge E2EE chi tiết (cài Go → clone `mautrix/meta` →
    `go mod tidy` → `go build` → verify).
  - Snippet Quick Start cho `listeningE2EEEvent`.
- **`src/_messaging/README{,_EN}.md`** — thêm mục **Cài đặt** riêng (deps Python,
  build bridge Go, hợp đồng `dataFB`) và mục Module Reference cho
  `_listening_e2ee.py`.
- **`CHANGELOG.md`** (file này).

### 🛠 Changed

- README gốc: cập nhật **Important Notice** từ "E2EE sắp tới" → "E2EE đã
  release".
- Mindmap & cây thư mục: phản ánh thêm `_listening_e2ee.py`, `bridge-e2ee/`,
  thư mục `build/`.
- **Roadmap**: tick `[x]` cho mục giải mã E2EE; bổ sung mục mới "phát hành
  bridge E2EE dạng prebuilt binary".
- Bảng Troubleshooting trong `_messaging/README*.md`: thêm 2 dòng cho lỗi
  `FileNotFoundError` (thiếu binary) và bridge crash.

### 🔧 Fixed

- `_listening_e2ee.py`: chuẩn hoá output `bodyResults` cho **khớp 1-1** với
  `_listening.py` để code tiêu thụ event không phải sửa đổi.
  - `type` không còn là chuỗi `"e2ee"`.
  - `replyToID`, `attachments.id`/`url` đọc theo đúng thứ tự ưu tiên của
    legacy (`fbid → id → stickerId`; `url → previewUrl → mercury…preview.uri`).
  - `get_last_seq_id()` in log đúng định dạng (`[<datetime>]last_seq_id: …`)
    và `return` rỗng — parity với `_listening.py`.

### 🔒 Security

- Bridge Go chạy ở **subprocess riêng**: bridge crash không kéo Python crash
  theo (an toàn hơn so với phương án ctypes/DLL trước đây).
- `_listening_e2ee` không lưu cookie ra disk; truyền cookie qua RPC trong bộ
  nhớ.

### 📦 Dependencies

- **Python**: không thêm package mới — vẫn `requests`, `paho-mqtt`, `attrs`,
  `pyotp`.
- **Go (mới, tuỳ chọn)**: `mautrix/meta`, `whatsmeow`, dependency truyền vận
  của `mautrix-go`. Chỉ cần khi build bridge E2EE.

### ⚠️ Lưu ý nâng cấp từ 2.0.x

- **Không có breaking change** với code đang dùng `_listening.py`.
- Để bật E2EE, người dùng cần cài Go 1.24+ và build binary 1 lần — xem
  [README §Cài đặt bước 5](README.md#5-tu%E1%BB%B3-ch%E1%BB%8Dn-build-bridge-e2ee--cho-tin-nh%E1%BA%AFn-1-1).

---

## [2.0.x] — 2024 → 2026-03

- Tái cấu trúc toàn bộ codebase thành 3 tầng `_core` / `_features` /
  `_messaging`.
- Listener MQTT WebSocket cho tin nhắn nhóm (`_listening.py`).
- Bộ tính năng đầy đủ: gửi tin / sticker / attachment, react, unsend, message
  requests, quản lý nhóm (admin / nickname / emoji / poll), facebook
  features (post, bio, search, marketplace, professional…).
- Đăng nhập bằng cookie hoặc username/password (kèm 2FA TOTP).

> Chi tiết các bản 2.0.x được tổng hợp trong commit history trước
> ngày 12/05/2026.

---

[2.1.0]: https://github.com/MinhHuyDev/fbchat-v2/releases/tag/v2.1.0
[2.0.x]: https://github.com/MinhHuyDev/fbchat-v2/releases
