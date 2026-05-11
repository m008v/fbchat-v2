# Changelog

Tất cả thay đổi đáng chú ý của `fbchat-v2` sẽ được ghi lại tại đây.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/),
phiên bản tuân theo [Semantic Versioning](https://semver.org/lang/vi/).

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
