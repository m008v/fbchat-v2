# Changelog

Tất cả thay đổi đáng chú ý của `fbchat-v2` sẽ được ghi lại tại đây.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/),
phiên bản tuân theo [Semantic Versioning](https://semver.org/lang/vi/).

---

## [2.1.3b] — 2026-05-18

### 🛠 Changed

- `_messaging/_send_e2ee.py`: tiếp tục hoàn thiện flow gửi chủ động bằng
  Facebook numeric ID.
  - `normalize_chat_jid(...)` / `chat_jid_from_user_id(...)` vẫn normalize
    `100012345678` → `100012345678@msgr`.
  - `api.send(...)` chấp nhận cả JID đầy đủ lẫn user ID; input sai trả
    `invalid_chat_jid` rõ ràng hơn.
  - `api.send_to_user(...)` là entry point tiện dụng cho flow chủ động.
- `src/_e2ee_send_test.py`: test script giờ tự resolve `--device-path` relative
  về root `fbchat-v2`, nên không còn phụ thuộc cwd hiện tại khi spawn bridge.
- `bridge-e2ee`: fix gốc cho proactive E2EE send.
  - `Client.sendE2EEMessage(...)` sẽ ensure encrypted DM thread trước khi gửi.
  - `DeviceStore.GetManySessions()` trả đủ session address được hỏi để
    `whatsmeow` nhận ra device chưa có session và tự fetch prekey.
  - `NewDeviceStore(...)` tạo luôn thư mục cha của file device nếu chưa tồn tại,
    giúp path như `./src/e2ee_device.json` không bị fail khi lưu mới.

### 📝 Documentation

- `DOCS.md`, `src/_messaging/README.md`, `src/_messaging/README_EN.md`:
  cập nhật troubleshooting cho lỗi `can't encrypt message for device: no signal
  session established` và cách dùng binary bridge mới.

### ⚠️ Lưu ý nâng cấp từ 2.1.3

- Nếu bạn dùng `--persist-device`, nên để bridge binary mới nhất ở
  `build/fbchat-bridge-e2ee.exe` để các fix session/prekey có hiệu lực.
- Không có breaking change cho API Python hiện có.

## [2.1.3] — 2026-05-18

### ✨ Added

- **`src/_e2ee_send_test.py`** — script test riêng cho `_messaging/_send_e2ee.py`.
  - Chạy không tham số sẽ hỏi interactive `UID/JID người nhận` và `nội dung cần gửi`.
  - `--dry-run` kiểm tra normalize Facebook numeric ID → `<id>@msgr` mà không
    cần cookie/bridge.
  - Chế độ gửi thật đọc cookie từ `FBCHAT_COOKIE` hoặc `src/config.json`, tự
    `dataGetHome(...)`, connect bridge và gọi `send_to_user(...)` / `send(...)`.
  - Hỗ trợ `--reply-message`, `--reply-sender-jid`, `--persist-device`,
    `--device-path`, `--binary-path`, timeout connect/send.

- **`_messaging/_editMessage.py`** — module mới cho phép **sửa tin nhắn đã gửi**
  bằng MQTT Lightspeed task `queue_name="edit_message"` publish lên `/ls_req`.
  - API chính: `editMessage(dataFB, messageID, newText, timeout=20)`.
  - Alias theo style fbchat-v2: `func(dataFB, messageID, newText, timeout=20)`.
  - Tự mở kết nối MQTT WebSocket ngắn hạn tới `edge-chat.facebook.com`, publish
    task rồi đóng client.
  - Schema return:
    - ✅ `{"success": 1, "messages": "...", "data": {"messageID": str, "text": str, ...}}`
    - ❌ `{"error": 1, "messages": "...", "payload": {...}}`
  - Lưu ý: success nghĩa là task đã publish thành công; Messenger vẫn có thể
    từ chối nếu tin nhắn quá cũ, không thuộc tài khoản hiện tại, hoặc không còn
    được phép sửa.

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
  - Return shape theo chuẩn `success/error` của fbchat-v2.

### 📝 Documentation

- README VI/EN gốc: cập nhật feature list, kiến trúc Messaging, cây thư mục,
  mindmap nhúng, Quick Start cho `_editMessage`, `_changeTheme`, `_createNotes`,
  và roadmap.
- `DOCS.md`: thêm **§8 Editing a sent message** và
  **§10 Changing a thread theme / background**; renumber các mục sau thành
  §11–§16; thêm FAQ cho edit/theme.
- `CLAUDE.md`: cập nhật cây thư mục, bảng Layer 3, dependencies, trạng thái
  release/backlog cho agent và ghi chú phân biệt `_editMessage.py` thường với
  `editMessage` của bridge E2EE chưa expose qua JSON-RPC.
- `FLOWCHART.md`, `mindmap-mermaid.md`: thêm node `_editMessage.py` và
  `_changeTheme.py`; runtime flow thể hiện LS task publish qua MQTT.
- `src/_messaging/README.md` + `README_EN.md`: đã có module reference, ví dụ,
  dependency map và troubleshooting cho hai module mới.

### 🛠 Changed

- `_messaging/_send_e2ee.py`: hỗ trợ gửi chủ động bằng Facebook numeric ID.
  - Thêm `normalize_chat_jid(target)` / `chat_jid_from_user_id(user_id)` để đổi
    `100012345678` → `100012345678@msgr`.
  - `api.send(...)` giờ nhận được cả JID đầy đủ `<facebook_id>@msgr` lẫn
    Facebook numeric ID; input sai trả `error-code="invalid_chat_jid"`.
  - Thêm `api.send_to_user(user_id, contentSend, ...)` cho flow chủ động nhắn
    khi chưa có event chứa `chatJid`.
- `bridge-e2ee`: trước khi gửi E2EE DM chủ động tới `<facebook_id>@msgr`, bridge
  tự chạy `CreateWhatsAppThreadTask` (`ENCRYPTED_OVER_WA_ONE_TO_ONE`) và các
  subtask server trả về để tránh lỗi `can't encrypt message for device: no
  signal session established`.
- `bridge-e2ee`: sửa `DeviceStore.GetManySessions()` để trả cả các Signal
  session address chưa tồn tại bằng giá trị `nil`; nhờ vậy `whatsmeow` nhận ra
  device thiếu session và tự fetch prekey thay vì bỏ qua rồi báo `no signal
  session established`.
- `_messaging/__init__.py`: `__all__` thêm `_editMessage`, `_changeTheme`, đồng
  thời giữ `_listening_e2ee` và `_send_e2ee` trong danh sách public module nội bộ.

### 📦 Dependencies

- Không thêm package mới. Hai module mới dùng lại `requests` và `paho-mqtt`
  đã có trong `requirements.txt`.

### ⚠️ Lưu ý nâng cấp từ 2.1.2b

- **Không có breaking change.** Các module hiện có vẫn giữ nguyên import/API.
- `_editMessage.py` và `_changeTheme.py` dùng MQTT LS task; cần cookie còn sống
  và mạng không chặn WebSocket tới `edge-chat.facebook.com`.

---

## [2.1.2b] — 2026-05-15

### ✨ Added

- **`_messaging/_createNotes.py`** — module mới quản lý **Messenger Notes**
  (status 24h hiển thị trên đầu inbox Messenger). Port từ
  `ws3-fca/notes.js` (© @ChoruOfficial) sang style fbchat-v2.
  - 4 hàm CRUD độc lập:
    - `checkNote(dataFB)` — lấy note hiện tại (`msgr_user_rich_status`).
    - `createNote(dataFB, text, privacy="FRIENDS")` — tạo note text 24h.
    - `deleteNote(dataFB, noteID)` — xoá note theo `rich_status_id`.
    - `recreateNote(dataFB, oldNoteID, newText, privacy="FRIENDS")` — xoá +
      tạo lại nguyên tử (fail-fast nếu bước nào lỗi thì abort).
  - Entry point thống nhất:
    `func(dataFB, action="check"|"create"|"delete"|"recreate", **kwargs)`.
  - Mỗi call hit một GraphQL `friendly_name` / `doc_id` riêng — không share
    mutation, lỗi ở `delete` không cascade sang `create`:
    - `MWInboxTrayNoteCreationDialogQuery` (doc_id `30899655739648624`)
    - `MWInboxTrayNoteCreationDialogCreationStepContentMutation`
      (doc_id `24060573783603122`)
    - `useMWInboxTrayDeleteNoteMutation` (doc_id `9532619970198958`)
  - **Privacy mapping** (`PRIVACY_ALIASES`): `EVERYONE` / `PUBLIC` đều bị
    normalize về `FRIENDS` (Messenger Notes hiện chỉ hỗ trợ scope FRIENDS).
    Input tự uppercase, các giá trị khác forward as-is.
  - **Resilience**: `timeout=(connect=10s, read=45s)` + 2 retries cho
    `requests.Timeout` / `requests.RequestException` (tổng ≤ 3 lần thử).
  - Tự strip prefix `for (;;);` trước khi `json.loads`.
  - `client_mutation_id` random `0-10`; `session_id` sinh nội bộ qua
    `generate_client_id()` — caller không cần truyền.
  - **Schema return chuẩn fbchat-v2**:
    - ✅ `{"success": 1, "messages": "...", "data": {...}}`
    - ❌ `{"error": 1, "messages": "...", "details" | "raw": ...}`
  - Hard-coded `duration = 86400s` (24h) — Messenger web flow chưa hỗ trợ
    duration tuỳ ý.

### 📝 Documentation

- `DOCS.md`: thêm **§10 Messenger Notes (24h status)** đầy đủ ví dụ CRUD,
  bảng function reference (kèm `friendly_name` GraphQL), bảng privacy
  mapping, return shape, internals; **§13 FAQ** thêm subsection Messenger
  Notes; renumber §10–§14.
- `src/_messaging/README.md` + `README_EN.md`: thêm `_createNotes.py` vào
  cây thư mục, table of contents, module reference, dependency map và
  block ví dụ usage.
- `CLAUDE.md`: thêm `_createNotes.py` vào cây thư mục + bảng Layer 3.
- `FLOWCHART.md`, `mindmap-mermaid.md`: cập nhật sơ đồ phản ánh module mới.
- README VI/EN gốc: cập nhật cây thư mục + Quick Start mention `createNotes`.

### 🛠 Changed

- Thay thế các tham chiếu legacy `__facebookToolsV2` còn sót lại trong
  comment hướng dẫn của 6 file module (giờ dùng tên class chuẩn).
- Cập nhật link liên hệ `m.me/Booking.MinhHuyDev` → `m.me/zminhhuydev` ở
  `_reactions.py` và `_get_user_info.py`.

### 🔧 Fixed

- Sửa typo `datatFB` → `dataFB` trong tutorial của `_changeNickname.py`.

### 📦 Dependencies

- Không thay đổi.

### ⚠️ Lưu ý nâng cấp từ 2.1.2a

- **Không có breaking change.** Chỉ thêm module mới `_createNotes` — code
  hiện tại không bị ảnh hưởng.
- Bản PyPI tương ứng được phát hành dưới tag stable
  [`fbchat-v2 2.1.4`](https://pypi.org/project/fbchat-v2/2.1.4/).

---

## [2.1.2a] - 2026-05-13

### ✨ Added

- **`_messaging/_send_e2ee.py`** — module mới `class api` cho phép **gửi tin
  nhắn E2EE** (Secret Conversations) vào các cuộc trò chuyện 1-1, hoàn thiện
  cặp listener + sender E2EE.
  - Hai chế độ khởi tạo:
    - **Reuse** (khuyến nghị): `api(listener=listeningE2EEEvent_instance)` —
      dùng chung bridge Go với listener, không pair lại với Meta, không bắn
      thông báo "đăng nhập thiết bị mới".
    - **Standalone**: `api(dataFB=..., log_level=, device_path=, e2ee_memory_only=, binary_path=)`
      rồi `sender.connect()` — spawn bridge riêng. Hỗ trợ context manager
      (`with api(dataFB=...) as sender:`) để tự connect/close.
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

### 📝 Documentation

- `DOCS.md` được viết lại hoàn toàn bằng tiếng Anh + bổ sung section **FAQ**
  ~20 câu hỏi (cookie expiry, `BridgeError`, `chat_jid` vs `threadID`,
  phân biệt `_send.api` vs `_send_e2ee.api`, persist Signal keys, v.v.).
- `src/_messaging/README.md` + `README_EN.md`: thêm mục `_send_e2ee.py` vào
  table of contents, module reference, dependency map và ví dụ (reuse +
  standalone). Cập nhật bảng troubleshooting với 3 lỗi thường gặp:
  `not_connected`, `bridge_error`, `ValueError: Phải truyền 'listener=' ...`.
- `CLAUDE.md`: thêm `_send_e2ee.py` vào cây thư mục, bảng Layer 3 và một
  block flow ngắn cho `_send_e2ee.api` (mode A vs mode B + return shape).
- `bridge-e2ee/README.md`: ghi chú rằng `sendE2EEMessage` hiện được expose
  qua wrapper Python `_messaging._send_e2ee.api`.

### 📦 Dependencies

- Không thay đổi.

---

## [2.1.1] — 2026-05-12

> **Bản vá tài liệu & hạ tầng phân phối.** Không thay đổi runtime; chủ yếu
> hoàn thiện tài liệu trên website, README và đẩy gói lên **PyPI** để
> `pip install fbchat-v2` hoạt động chính thức.

### ✨ Added

- **PyPI**: dự án đã lên [pypi.org/project/fbchat-v2](https://pypi.org/project/fbchat-v2/).
  - Badge `pypi/v` (live version) ở đầu cả `README.md` và `README_EN.md`.
  - Nút **📦 PyPI** trong dải nav phía dưới badge của 2 README.
  - Nút **PyPI** (icon Python) trong hero website (`website/index.html`)
    bên cạnh nút *Mã nguồn / Source*.
- **Website — Section E2EE mới** (`#guide-e2ee`):
  - Sidebar Chương II thêm liên kết **"E2EE · Mã hoá / Encryption"**
    (icon `fa-shield-halved`).
  - File-tree `_messaging/` thêm dòng `_listening_e2ee.py # E2EE qua Go bridge`.
  - Module card mới: `_listening_e2ee.listeningE2EEEvent(dataFB)` với code
    mẫu decorator `@on_message` + `send_e2ee_message`.
  - Trang hướng dẫn song ngữ VI/EN: kiến trúc, lệnh build bridge Go,
    bảng 8 loại event, ví dụ gửi tin E2EE, persist `device_path`, FAQ.
- **`CLAUDE.md`** viết lại theo hướng *agent-first* (Claude / Codex /
  Copilot): thêm TL;DR, bảng "Quick reference", bảng *Common gotchas* (đã
  liệt kê các bug `@attr.s` override `__init__`, `EventBuffer` thiếu method,
  `BridgeError binary not found`…), tách rõ phần bridge Go.

### 🛠 Changed

- **Cảnh báo E2EE trên home website**: alert `alert--danger` *"E2EE NOTICE —
  bypass đang chuẩn bị phát hành"* → `alert--success` **"E2EE READY"** với
  link nội bộ trỏ thẳng tới section `#guide-e2ee`.
- README VI/EN: dải nav được sắp xếp lại để link **PyPI** đứng ngay sau
  link song ngữ.

### 🔧 Fixed

- Không có thay đổi mã nguồn Python / Go.

### 📦 Dependencies

- Không thay đổi.

### ⚠️ Lưu ý nâng cấp từ 2.1.0

- **Không có breaking change.** Có thể nâng cấp bằng:
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

[2.1.1]: https://github.com/MinhHuyDev/fbchat-v2/releases/tag/v2.1.1
[2.1.0]: https://github.com/MinhHuyDev/fbchat-v2/releases/tag/v2.1.0
[2.0.x]: https://github.com/MinhHuyDev/fbchat-v2/releases
