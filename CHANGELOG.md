# Changelog

Tất cả thay đổi đáng chú ý của `fbchat-v2` sẽ được ghi lại tại đây.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/),
phiên bản tuân theo [Semantic Versioning](https://semver.org/lang/vi/).

---

## [Unreleased]

> Các thay đổi website dưới đây hiện chỉ nằm trong working copy `website/` đang
> bị Git ignore; chúng chưa thuộc tag hoặc package phát hành nào.

### Added

- Thêm `website/validate_i18n.py` để kiểm tra cấu trúc song ngữ, các cặp VI/EN,
  tab/panel, liên kết nội bộ và nội dung bị rò giữa hai locale.
- Thay spinner cũ bằng package-stream preloader dùng lệnh `pip`, tiến trình
  indeterminate, trạng thái screen reader, hard timeout fail-open 3,5 giây và
  chế độ giảm chuyển động.
- Bổ sung tài liệu vận hành và migration v2.3 cho bridge contract, error payload,
  lifecycle async, privacy flags, năm bridge binary, `SHA256SUMS` và provenance.

### Changed

- Chuẩn hóa website thành giao diện VI/EN dùng chung DOM; metadata, ARIA,
  placeholder, tìm kiếm, nút sao chép và định dạng số đổi theo locale hiện tại.
- Khôi phục lấy release và số sao theo thời gian thực từ GitHub API, chuẩn hóa
  tag legacy về SemVer, dùng mục tiêu 200 sao và canonical URL
  `https://nqminkhuy.com/fbchat/`.
- Đặt light theme làm mặc định, giữ action hero nằm ngang trên mobile và trình
  bày owner/maintainer, super-contributor và contributor theo một hệ visual
  thống nhất.

### Fixed

- Sửa language/theme toggle, version và star counter bị vô hiệu do literal
  newline, phần tử locale bị ẩn hoặc skeleton không được gỡ.
- Sửa bản dịch thiếu/lặp/lồng nhau, chuỗi tiếng Việt bị hỏng, code block và nút
  copy biến mất khi chuyển sang tiếng Anh.
- Clip hiệu ứng shine bên trong phần progress thật, sửa đường nối sọc chéo,
  khoảng trắng thừa đầu hero, CSS variable thiếu, V2 badge bị ẩn và layout
  contributor/preloader trên màn hình nhỏ.

## [2.3.1] - 2026-09-07

### Added

- Thêm `_features._facebook._reactionPost.func(...)` để thả hoặc gỡ cảm xúc
  trên bài viết timeline Facebook.
- Hỗ trợ `LIKE`, `LOVE`, `CARE`/`SUPPORT`, `HAHA`, `WOW`,
  `SAD`/`SORRY`, `ANGRY`/`ANGER` và `UNDO`/`UNREACT`/`NONE`;
  input không phân biệt hoa thường.
- Thêm tài liệu VI/EN cho toàn bộ 13 module Facebook cá nhân, bảng reaction,
  alias, chuẩn hóa feedback ID, telemetry và ví dụ sử dụng.

### Changed

- Bổ sung `_reactionPost`, `_archivePost` và `_deletePost` vào
  `_features._facebook.__all__` để public export phản ánh đúng module hiện có.
- Sửa `.gitattributes` để GitHub Linguist tính source Go do dự án duy trì,
  nhưng tiếp tục loại submodule upstream `bridge-e2ee/meta/` khỏi thống kê.

### Fixed

- Chuẩn hóa `feedback_id`: encode post ID thô thành Base64
  `feedback:<postID>`, giữ token hợp lệ và không double-encode.
- Dùng actor ID, `jazoest`, epoch milliseconds, client mutation ID và profile
  referrer động thay cho attribution/referrer tĩnh bất thường.
- Trả lỗi có cấu trúc khi reaction type, post ID, session data hoặc async
  transport không hợp lệ; dọn tracking payload thừa.
- Khắc phục Ruff F401/F541 và định dạng lại `_reactionPost.py` cùng
  `_features._facebook.__init__.py` bằng Black.

### Packaging and CI

- Đồng bộ version `2.3.1` trong metadata Python, runtime fallback, Go bridge,
  workflow, verifier, test và tài liệu; rebuild bridge với đúng
  `bridgeVersion` để tag validation không còn đọc nhầm `2.3.0`.
- Mở rộng distribution verifier để bắt buộc package có `_reactionPost`.
- Gỡ job tự động publish PyPI khỏi release workflow, nhưng giữ quality gate,
  verified distributions, provenance, workflow artifact và GitHub Release.
- Publish distribution `fbchat-v2==2.3.1` lên PyPI từ checkout phân phối riêng
  sau khi wheel/sdist đạt Twine strict và không chứa file rác/cache.
- Quality gate xác minh Ruff, Black, 149 pytest, Go test/vet và native bridge
  RPC theo ma trận nền tảng.

## [2.3.0] - 2026-08-29

### Added

- Thêm `_features._facebook._unFriend.func(...)` để hủy kết bạn theo Facebook
  ID với validation input và kiểm tra lỗi GraphQL.
- Thêm JSON-RPC `hello` để xác minh protocol version, bridge version và
  capability trước khi bridge nhận traffic.
- Thêm reusable quality gate, release artifact validator và native bridge RPC
  smoke test cho quy trình phát hành.

### Changed

- Chuyển feature HTTP sang transport `httpx` sync/async dùng chung; legacy
  adapter chỉ còn ở boundary nội bộ có lý do rõ.
- Viết lại bot mẫu, listener thường, listener E2EE và bridge actions theo
  lifecycle async có startup, readiness, cancellation, shutdown và cleanup rõ.
- Quản lý E2EE bridge theo generation với total deadline, exponential backoff,
  recovery tuần tự, writer queue riêng và timeout cho process/pipe treo.
- Chỉ công bố readiness khi socket thường đã kết nối và E2EE đã đăng nhập;
  listener E2EE trở thành single-use sau khi `stop()`.
- Viết lại README VI/EN, `DOCS.md` và tài liệu module theo API async/await,
  error contract, migration cùng quy trình build bridge hiện hành.

### Security

- Thay RNG tạo `AdvSecretKey` bằng `crypto/rand` và trả lỗi nếu nguồn ngẫu
  nhiên an toàn thất bại.
- Pin bridge auto-download vào đúng tag/package version, chỉ nhận trusted HTTPS
  host, kiểm tra redirect, giới hạn 200 MiB và fail closed khi SHA-256 sai.
- Giới hạn Go media download vào trusted Facebook/Messenger CDN, kiểm soát
  redirect và hard cap 100 MiB để giảm SSRF cùng tải dữ liệu vô hạn.
- Sinh mã TOTP cục bộ bằng `pyotp`, không gửi secret 2FA tới dịch vụ trung
  gian; nâng toolchain Go lên `1.26.5` và `golang.org/x/net` lên `v0.55.0`
  trong đợt hardening.
- Ghi device state tuần tự bằng temp file, `fsync` và atomic rename; rollback
  cả RAM khi persistence lỗi và không chặn Signal ratchet trong callback.
- Tạo config cookie atomic với quyền riêng tư/ACL phù hợp; ẩn nội dung message,
  command và traceback mặc định.

### Fixed

- Khôi phục delivery tin nhắn thường và E2EE từ live upsert; lọc typing,
  read-receipt, reaction cùng event phụ trước queue, giới hạn queue và chống
  replay/dedupe placeholder.
- Sửa async `disconnect()` không await shutdown, cleanup startup nằm ngoài
  `finally`, bridge response sai kiểu, short write, stale generation và race
  giữa close/reconnect.
- Mutation unfriend/archive/delete không còn báo thành công khi GraphQL trả
  `data=null`, `success=false` hoặc có `errors`.
- Hoàn thiện identity/session/prekey cùng LID/account/platform/device metadata
  trong DeviceStore; không hạ cấp E2EE sang transport thường khi chưa sẵn sàng.
- Sửa boundary sync/async trong listener, theme, note và attachment; khôi phục
  tương thích CPython 3.10 và loại bảy lỗi `from __future__` làm source không
  compile.
- Sửa gỡ admin báo sai action, `professional` xử lý bool, profile bổ sung dựng
  header sai, Marketplace khóa nhầm category và post bỏ attachment.
- Xử lý socket error của Messagix không có `Err` mà không làm listener crash.

### Packaging and CI

- Wheel export đúng `_core`, `_features`, `_messaging` thay vì namespace
  `src`; thêm Twine strict, wheel/sdist và fresh-install smoke test.
- CI enforce compileall, Ruff, Black, full mypy, pytest Python 3.10-3.14,
  Go test/vet/race, package smoke và native JSON-RPC trên Linux/macOS/Windows.
- Release build đúng năm bridge binary, tạo `SHA256SUMS`, nhúng checksum vào
  wheel/sdist và tạo provenance attestation trước khi phát hành.
- Chuẩn hóa clean-environment test bằng `pythonpath = ["src", "."]` và
  `python -m pytest` để import `scripts.*` không phụ thuộc máy dev.

### Compatibility

- Yêu cầu Python `>=3.10`; API async phải được `await` và caller phải xử lý
  payload `{"error": 1, ...}` thay vì chỉ tin HTTP 200.
- Custom bridge phải cùng package version và hỗ trợ protocol `1`; Windows
  ARM64 chưa có binary dựng sẵn.

## [2.2.1] - 2026-07-21

### Added

- Thêm `_features._facebook._deletePost` để đưa bài timeline vào thùng rác
  bằng `useCometTrashPostMutation`.
- Thêm `_features._facebook._archivePost` để chuyển bài timeline vào kho lưu
  trữ bằng `useCometArchivePostMutation`.
- Cả hai module hỗ trợ `typePost="my_post"` và `typePost="others"` để chọn
  đúng payload theo nguồn bài viết.

### Fixed

- Sửa key parse payload bị copy-paste sai trong `_deletePost.py` và loại debug
  text còn sót.

### Documentation

- Đồng bộ tài liệu VI/EN, flowchart và module reference cho archive/delete;
  làm rõ đây là thao tác lưu trữ hoặc chuyển vào thùng rác, không xóa vĩnh viễn.

## [2.2.0] - 2026-07-19

### Changed

- Chuyển public feature/messaging API sang async-first coroutine và thống nhất
  entry point `func(...)`; loại các alias `func_async`/`func_sync` dư thừa.
- Gom HTTP runtime về `_core._http` với `httpx.AsyncClient` có thể inject và
  tái sử dụng connection; `requests` chỉ còn ở compatibility boundary.
- Viết lại `src/main.py` theo lifecycle `asyncio`, dùng HTTP client chung,
  chờ E2EE readiness và cleanup listener/client khi dừng.
- `listeningE2EEEvent.connect_mqtt()` trở thành coroutine; callback bridge có
  thể chuyển event an toàn vào `asyncio.Queue`.

### Fixed

- Gia cố attachment upload khi Facebook trả payload null/malformed, trả lỗi có
  cấu trúc và chuẩn hóa `attachmentID`/`typeAttachment` cho send flow.
- Khôi phục luồng login FB4A/2FA, hỗ trợ override config/env và giữ password
  gốc trong bước xác minh.
- Sửa sync path gọi bridge coroutine sai, thêm readiness gate cho E2EE listener
  và route bot command qua listener E2EE.
- Sửa test consumer lấy dữ liệu notification/thread từ result dict trước khi
  slice hoặc index.

### Documentation

- Viết lại README VI/EN, `DOCS.md` và README của `_core`, `_features`,
  `_messaging` cùng bridge theo API async, `httpx` và E2EE hiện hành.
- Thêm `src/config.example.json`, hướng dẫn build/discover bridge và biến
  `FBCHAT_E2EE_BIN`.

### Breaking changes

- Call site dùng API public phải thêm `await`; không lồng `asyncio.run()` khi
  framework đã có event loop.
- Import `func_async`/`func_sync` phải đổi về `func`; integration E2EE async
  nên dùng listener hoặc `BridgeActions`.

## [2.2.0-beta] - 2026-07-06

### ✨ Added
- Dual API (Sync & Async) cho toàn bộ `_messaging`: Hỗ trợ native `async`/`await` cho tất cả các hành động (`send`, `unsend`, `react`, ...).
- Hỗ trợ `httpx` cho HTTP async: Các API async dùng `httpx`; endpoint legacy được cô lập sau adapter riêng thay vì lộ ra API public.
- Type Hints đầy đủ: Tích hợp kiểu dữ liệu (`TypedDict`, `Literal`) cho 11 module core và messaging (giảm thiểu lỗi type runtime).
- E2EE Bridge Auto-Respawn: Cơ chế tự động hồi sinh Bridge E2EE (`_listening_e2ee.py`) với exponential backoff (2s -> 32s) khi mất kết nối đột ngột hoặc crash.

### 🛠 Changed
- Module `_core._session.py` và `_utils.py` hiện tại sử dụng helper `send_request` và `send_request_async`.

---

## [2.1.4] - 2026-06-30

### Added

- Tự động chọn và tải E2EE bridge asset theo hệ điều hành/kiến trúc khi binary
  mặc định chưa có; trả lỗi rõ khi asset hoặc kiến trúc không được hỗ trợ.

### Changed

- Chuyển metadata và dependency sang `pyproject.toml` theo PEP 621; hỗ trợ cài
  editable bằng `python -m pip install -e .`.
- Cập nhật CI/CD để cài dependency từ `pyproject.toml`, checkout submodule,
  đóng gói namespace dưới `src` và lấy nội dung GitHub Release từ release note.
- Đồng bộ README, `DOCS.md`, `CLAUDE.md`, flowchart và tài liệu bridge theo
  quy trình cài đặt mới.

### Security

- Loại cookie config và E2EE device state từng bị track khỏi source; giữ chúng
  ở local/ignored path và không đưa credential vào package.
- Production có thể pin `FBCHAT_E2EE_BIN` vào binary đã tự xác minh thay vì
  phụ thuộc auto-download.

## [2.1.3b] - 2026-05-19

### 🛠 Changed

- `_messaging/_send_e2ee.py`: tiếp tục hoàn thiện flow gửi chủ động bằng
  Facebook numeric ID.
  - `normalize_chat_jid(...)` / `chat_jid_from_user_id(...)` vẫn normalize
    `100012345678` -> `100012345678@msgr`.
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

## [2.1.3] - 2026-05-18

### ✨ Added

- `src/_e2ee_send_test.py` - script test riêng cho `_messaging/_send_e2ee.py`.
  - Chạy không tham số sẽ hỏi interactive `UID/JID người nhận` và `nội dung cần gửi`.
  - `--dry-run` kiểm tra normalize Facebook numeric ID -> `<id>@msgr` mà không
    cần cookie/bridge.
  - Chế độ gửi thật đọc cookie từ `FBCHAT_COOKIE` hoặc `src/config.json`, tự
    `dataGetHome(...)`, connect bridge và gọi `send_to_user(...)` / `send(...)`.
  - Hỗ trợ `--reply-message`, `--reply-sender-jid`, `--persist-device`,
    `--device-path`, `--binary-path`, timeout connect/send.

- `_messaging/_editMessage.py` - module mới cho phép sửa tin nhắn đã gửi
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

- `_messaging/_changeTheme.py` - module mới để lấy danh sách theme và đổi
  nền / theme thread Messenger.
  - `listThemes(dataFB)` gọi GraphQL
    `MWPThreadThemeQuery_AllThemesQuery` (`doc_id=24474714052117636`).
  - `findTheme(dataFB, themeName)` match theo theme ID, tên chính xác, hoặc
    keyword không phân biệt hoa thường.
  - `changeTheme(dataFB, threadID, themeName, initiatorID=None, timeout=20)`
    publish 4 LS queues: `ai_generated_theme`, `msgr_custom_thread_theme`,
    `thread_theme_writer`, `thread_theme`.
  - `func(...)` hỗ trợ keyword arguments cho `threadID`, `themeName`, `action`,
    `action="list"`, `action="find"`, và set theme mặc định.
  - Return shape theo chuẩn `success/error` của fbchat-v2.

### 📝 Documentation

- README VI/EN gốc: cập nhật feature list, kiến trúc Messaging, cây thư mục,
  mindmap nhúng, Quick Start cho `_editMessage`, `_changeTheme`, `_createNotes`,
  và roadmap.
- `DOCS.md`: thêm §8 Editing a sent message và
  §10 Changing a thread theme / background; renumber các mục sau thành
  §11-§16; thêm FAQ cho edit/theme.
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
    `100012345678` -> `100012345678@msgr`.
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

- Không thêm package mới. Hai module mới dùng lại transport nội bộ và `paho-mqtt`
  đã có trong `requirements.txt`.

### ⚠️ Lưu ý nâng cấp từ 2.1.2b

- Không có breaking change. Các module hiện có vẫn giữ nguyên import/API.
- `_editMessage.py` và `_changeTheme.py` dùng MQTT LS task; cần cookie còn sống
  và mạng không chặn WebSocket tới `edge-chat.facebook.com`.

---

## [2.1.2b] - 2026-05-15

### ✨ Added

- `_messaging/_createNotes.py` - module mới quản lý Messenger Notes
  (status 24h hiển thị trên đầu inbox Messenger). Port từ
  `ws3-fca/notes.js` (© @ChoruOfficial) sang style fbchat-v2.
  - 4 hàm CRUD độc lập:
    - `checkNote(dataFB)` - lấy note hiện tại (`msgr_user_rich_status`).
    - `createNote(dataFB, text, privacy="FRIENDS")` - tạo note text 24h.
    - `deleteNote(dataFB, noteID)` - xoá note theo `rich_status_id`.
    - `recreateNote(dataFB, oldNoteID, newText, privacy="FRIENDS")` - xoá +
      tạo lại nguyên tử (fail-fast nếu bước nào lỗi thì abort).
  - Entry point thống nhất:
    `func(...)` với `action="check"|"create"|"delete"|"recreate"` và keyword arguments.
  - Mỗi call hit một GraphQL `friendly_name` / `doc_id` riêng - không share
    mutation, lỗi ở `delete` không cascade sang `create`:
    - `MWInboxTrayNoteCreationDialogQuery` (doc_id `30899655739648624`)
    - `MWInboxTrayNoteCreationDialogCreationStepContentMutation`
      (doc_id `24060573783603122`)
    - `useMWInboxTrayDeleteNoteMutation` (doc_id `9532619970198958`)
  - Privacy mapping (`PRIVACY_ALIASES`): `EVERYONE` / `PUBLIC` đều bị
    normalize về `FRIENDS` (Messenger Notes hiện chỉ hỗ trợ scope FRIENDS).
    Input tự uppercase, các giá trị khác forward as-is.
  - Resilience: `timeout=(connect=10s, read=45s)` + 2 retries cho
    lỗi timeout / lỗi transport (tổng <= 3 lần thử).
  - Tự strip prefix `for (;;);` trước khi `json.loads`.
  - `client_mutation_id` random `0-10`; `session_id` sinh nội bộ qua
    `generate_client_id()` - caller không cần truyền.
  - Schema return chuẩn fbchat-v2:
    - ✅ `{"success": 1, "messages": "...", "data": {...}}`
    - ❌ `{"error": 1, "messages": "...", "details" | "raw": ...}`
  - Hard-coded `duration = 86400s` (24h) - Messenger web flow chưa hỗ trợ
    duration tuỳ ý.

### 📝 Documentation

- `DOCS.md`: thêm §10 Messenger Notes (24h status) đầy đủ ví dụ CRUD,
  bảng function reference (kèm `friendly_name` GraphQL), bảng privacy
  mapping, return shape, internals; §13 FAQ thêm subsection Messenger
  Notes; renumber §10-§14.
- `src/_messaging/README.md` + `README_EN.md`: thêm `_createNotes.py` vào
  cây thư mục, table of contents, module reference, dependency map và
  block ví dụ usage.
- `CLAUDE.md`: thêm `_createNotes.py` vào cây thư mục + bảng Layer 3.
- `FLOWCHART.md`, `mindmap-mermaid.md`: cập nhật sơ đồ phản ánh module mới.
- README VI/EN gốc: cập nhật cây thư mục + Quick Start mention `createNotes`.

### 🛠 Changed

- Thay thế các tham chiếu legacy `__facebookToolsV2` còn sót lại trong
  comment hướng dẫn của 6 file module (giờ dùng tên class chuẩn).
- Cập nhật link liên hệ `m.me/Booking.MinhHuyDev` -> `m.me/zminhhuydev` ở
  `_reactions.py` và `_get_user_info.py`.

### 🔧 Fixed

- Sửa typo `datatFB` -> `dataFB` trong tutorial của `_changeNickname.py`.

### 📦 Dependencies

- Không thay đổi.

### ⚠️ Lưu ý nâng cấp từ 2.1.2a

- Không có breaking change. Chỉ thêm module mới `_createNotes` - code
  hiện tại không bị ảnh hưởng.
- Bản PyPI tương ứng được phát hành dưới tag stable
  [`fbchat-v2 2.1.4`](https://pypi.org/project/fbchat-v2/2.1.4/).

---

## [2.1.2a] - 2026-05-13

### ✨ Added

- `_messaging/_send_e2ee.py` - module mới `class api` cho phép gửi tin
  nhắn E2EE (Secret Conversations) vào các cuộc trò chuyện 1-1, hoàn thiện
  cặp listener + sender E2EE.
  - Hai chế độ khởi tạo:
    - Reuse (khuyến nghị): `api(listener=listeningE2EEEvent_instance)` -
      dùng chung bridge Go với listener, không pair lại với Meta, không bắn
      thông báo "đăng nhập thiết bị mới".
    - Standalone: `api(dataFB=..., log_level=, device_path=, e2ee_memory_only=, binary_path=)`
      rồi `sender.connect()` - spawn bridge riêng. Hỗ trợ context manager
      (`with api(dataFB=...) as sender:`) để tự connect/close.
  - API chính: `send(chat_jid, contentSend, replyMessage="", replySenderJid="")`
    - gọi RPC `sendE2EEMessage` qua bridge Go.
  - Helper `reply(evt_data, contentSend)` tự bóc `chatJid` / `id` / `senderJid`
    từ event của `listeningE2EEEvent` để quote-reply nhanh.
  - Schema return trùng khớp `_send.api.send` - caller code không cần branch:
    - ✅ `{"success": 1, "payload": {"messageID": str, "timestamp": int}}`
    - ❌ `{"error": 1, "payload": {"error-decription": str, "error-code": "bridge_error" | "not_connected"}}`
  - Tái sử dụng `_BridgeProcess`, `_resolve_binary`, `parse_cookie_string`,
    `_REQUIRED_COOKIES` từ `_listening_e2ee.py` - không nhân đôi logic
    discovery binary / parse cookie.

### 📝 Documentation

- `DOCS.md` được viết lại hoàn toàn bằng tiếng Anh + bổ sung section FAQ
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

## [2.1.1] - 2026-05-12

> Bản vá tài liệu & hạ tầng phân phối. Không thay đổi runtime; chủ yếu
> hoàn thiện tài liệu trên website, README và đẩy gói lên PyPI để
> `pip install fbchat-v2` hoạt động chính thức.

### ✨ Added

- PyPI: dự án đã lên [pypi.org/project/fbchat-v2](https://pypi.org/project/fbchat-v2/).
  - Badge `pypi/v` (live version) ở đầu cả `README.md` và `README_EN.md`.
  - Nút 📦 PyPI trong dải nav phía dưới badge của 2 README.
  - Nút PyPI (icon Python) trong hero website (`website/index.html`)
    bên cạnh nút *Mã nguồn / Source*.
- Website - Section E2EE mới (`#guide-e2ee`):
  - Sidebar Chương II thêm liên kết "E2EE · Mã hoá / Encryption"
    (icon `fa-shield-halved`).
  - File-tree `_messaging/` thêm dòng `_listening_e2ee.py # E2EE qua Go bridge`.
  - Module card mới: `_listening_e2ee.listeningE2EEEvent(dataFB)` với code
    mẫu decorator `@on_message` + `send_e2ee_message`.
  - Trang hướng dẫn song ngữ VI/EN: kiến trúc, lệnh build bridge Go,
    bảng 8 loại event, ví dụ gửi tin E2EE, persist `device_path`, FAQ.
- `CLAUDE.md` viết lại theo hướng *agent-first* (Claude / Codex /
  Copilot): thêm TL;DR, bảng "Quick reference", bảng *Common gotchas* (đã
  liệt kê các bug `@attr.s` override `__init__`, `EventBuffer` thiếu method,
  `BridgeError binary not found`…), tách rõ phần bridge Go.

### 🛠 Changed

- Cảnh báo E2EE trên home website: alert `alert--danger` *"E2EE NOTICE -
  bypass đang chuẩn bị phát hành"* -> `alert--success` "E2EE READY" với
  link nội bộ trỏ thẳng tới section `#guide-e2ee`.
- README VI/EN: dải nav được sắp xếp lại để link PyPI đứng ngay sau
  link song ngữ.

### 🔧 Fixed

- Không có thay đổi mã nguồn Python / Go.

### 📦 Dependencies

- Không thay đổi.

### ⚠️ Lưu ý nâng cấp từ 2.1.0

- Không có breaking change. Có thể nâng cấp bằng:
  ```bash
  pip install --upgrade fbchat-v2
  ```

---

## [2.1.0] - 2026-05-12

> Bản cập nhật lớn: chính thức hỗ trợ giải mã End-to-End Encryption (E2EE)
> cho tin nhắn cá nhân Messenger. Schema event giữ nguyên tương thích ngược 100%
> với `_listening.py` cũ - chỉ cần đổi import là chạy.

### ✨ Added

- `_messaging/_listening_e2ee.py` - class `listeningE2EEEvent(dataFB)` lắng
  nghe tin nhắn 1-1 đã giải mã, API tương thích `listeningEvent`:
  - `get_last_seq_id()`, `connect_mqtt()`, `on_message(fn)`, `stop()`.
  - Phơi `self.bodyResults` với đúng schema của `_listening.py`
    (`body`, `timestamp`, `userID`, `messageID`, `replyToID`, `type`,
    `attachments.id`, `attachments.url`).
  - Phơi thêm `self.e2eeBodyResults` (`chatJid`, `senderJid`) cho metadata
    Signal Protocol.
  - Tự suy luận `type` = `"user"` / `"thread"` (DM vs nhóm) từ `chatType` /
    `isGroup`, không dùng giá trị `"e2ee"` riêng.
  - Attachment fallback `"Unable to retrieve attachment ID"` giống legacy.
- `bridge-e2ee/` - bridge Go độc lập (`fbchat-bridge-e2ee[.exe]`) giao tiếp
  với Python qua line-delimited JSON-RPC trên stdin/stdout. Đóng gói Signal
  Protocol (`whatsmeow`) + Meta Labyrinth (`mautrix-meta`).
  - RPC methods: `newClient`, `connect`, `connectE2EE`, `isConnected`,
    `sendMessage`, `sendE2EEMessage`, `disconnect`.
  - Override đường dẫn binary qua biến môi trường `FBCHAT_E2EE_BIN`.
  - Mặc định nạp tại `fbchat-v2/build/fbchat-bridge-e2ee[.exe]`.
- README (cả tiếng Việt và tiếng Anh):
  - Mục Yêu cầu hệ thống mở rộng: thêm Go 1.24, Git, RAM, danh sách
    package Python kèm mục đích.
  - Mục Cài đặt 7 bước với sanity check `python -c "import ..."` và
    smoke test `python src/main.py`.
  - Hướng dẫn build bridge E2EE chi tiết (cài Go -> clone `mautrix/meta` ->
    `go mod tidy` -> `go build` -> verify).
  - Snippet Quick Start cho `listeningE2EEEvent`.
- `src/_messaging/README{,_EN}.md` - thêm mục Cài đặt riêng (deps Python,
  build bridge Go, hợp đồng `dataFB`) và mục Module Reference cho
  `_listening_e2ee.py`.
- `CHANGELOG.md` (file này).

### 🛠 Changed

- README gốc: cập nhật Important Notice từ "E2EE sắp tới" -> "E2EE đã
  release".
- Mindmap & cây thư mục: phản ánh thêm `_listening_e2ee.py`, `bridge-e2ee/`,
  thư mục `build/`.
- Roadmap: tick `[x]` cho mục giải mã E2EE; bổ sung mục mới "phát hành
  bridge E2EE dạng prebuilt binary".
- Bảng Troubleshooting trong `_messaging/README*.md`: thêm 2 dòng cho lỗi
  `FileNotFoundError` (thiếu binary) và bridge crash.

### 🔧 Fixed

- `_listening_e2ee.py`: chuẩn hoá output `bodyResults` cho khớp 1-1 với
  `_listening.py` để code tiêu thụ event không phải sửa đổi.
  - `type` không còn là chuỗi `"e2ee"`.
  - `replyToID`, `attachments.id`/`url` đọc theo đúng thứ tự ưu tiên của
    legacy (`fbid -> id -> stickerId`; `url -> previewUrl -> mercury…preview.uri`).
  - `get_last_seq_id()` in log đúng định dạng (`[<datetime>]last_seq_id: …`)
    và `return` rỗng - parity với `_listening.py`.

### 🔒 Security

- Bridge Go chạy ở subprocess riêng: bridge crash không kéo Python crash
  theo (an toàn hơn so với phương án ctypes/DLL trước đây).
- `_listening_e2ee` không lưu cookie ra disk; truyền cookie qua RPC trong bộ
  nhớ.

### 📦 Dependencies

- Python: không thêm package mới - vẫn dùng transport nội bộ, `paho-mqtt`, `attrs`,
  `pyotp`.
- Go (mới, tuỳ chọn): `mautrix/meta`, `whatsmeow`, dependency truyền vận
  của `mautrix-go`. Chỉ cần khi build bridge E2EE.

### ⚠️ Lưu ý nâng cấp từ 2.0.x

- Không có breaking change với code đang dùng `_listening.py`.
- Tại thời điểm phát hành, người dùng cần build bridge thủ công. Hướng dẫn
  hiện hành nằm tại [bridge-e2ee/README.md](bridge-e2ee/README.md#build-từ-source).

---

## [2.0.x] - 2024 -> 2026-03

- Tái cấu trúc toàn bộ codebase thành 3 tầng `_core` / `_features` /
  `_messaging`.
- Listener MQTT WebSocket cho tin nhắn nhóm (`_listening.py`).
- Bộ tính năng đầy đủ: gửi tin / sticker / attachment, react, unsend, message
  transport HTTP, quản lý nhóm (admin / nickname / emoji / poll), facebook
  features (post, bio, search, marketplace, professional…).
- Đăng nhập bằng cookie hoặc username/password (kèm 2FA TOTP).

> Chi tiết các bản 2.0.x được tổng hợp trong commit history trước
> ngày 12/05/2026.

---

[Unreleased]: https://github.com/m008v/fbchat-v2/compare/v2.3.1...HEAD
[2.3.1]: https://github.com/m008v/fbchat-v2/releases/tag/v2.3.1
[2.3.0]: https://github.com/m008v/fbchat-v2/releases/tag/v2.3.0
[2.2.1]: https://github.com/m008v/fbchat-v2/releases/tag/v.2.2.1
[2.2.0]: https://github.com/m008v/fbchat-v2/releases/tag/v2.2.0
[2.2.0-beta]: https://github.com/m008v/fbchat-v2/tree/beta-async/await
[2.1.4]: https://github.com/m008v/fbchat-v2/releases/tag/v2.1.4
[2.1.3b]: https://github.com/m008v/fbchat-v2/releases/tag/v2.1.3b
[2.1.3]: https://github.com/m008v/fbchat-v2/releases/tag/v.2.1.3
[2.1.2b]: https://github.com/m008v/fbchat-v2/releases/tag/v2.1.2b
[2.1.2a]: https://github.com/m008v/fbchat-v2/releases/tag/v2.1.2a
[2.1.1]: https://github.com/m008v/fbchat-v2/releases/tag/v.2.1.1
[2.1.0]: https://github.com/m008v/fbchat-v2/releases/tag/v2.1.0
[2.0.x]: https://github.com/m008v/fbchat-v2/releases
