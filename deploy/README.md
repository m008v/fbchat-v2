# fbchat-v2 - Triển khai bằng Docker (fork)

[English](README_EN.md)

Thư mục này là phần riêng của fork: chạy bot mẫu trong Docker, đăng nhập Facebook qua trình duyệt trên web (noVNC) và chạy nhiều tài khoản trong một container. Phần lớn nằm trong `deploy/`, nhưng fork cũng sửa một số file của thư viện (xem [Đồng bộ với upstream](#-đồng-bộ-với-upstream)), nên merge từ repo gốc có thể conflict ở các file đó.

## 📂 Cấu trúc

```text
deploy/
├── docker-compose.yml          # project "fbchat-v2", volume fbchat-data
├── login/                      # Alpine + Chromium + noVNC, lấy cookie rồi tự dừng
│   ├── Dockerfile
│   ├── extract_cookie.py
│   └── control.py              # dịch vụ fb-login-ui: bật trình duyệt theo yêu cầu
├── bot/                        # python:3.12-alpine + bridge Go build tĩnh
│   ├── Dockerfile
│   └── Dockerfile.dockerignore # allowlist riêng (BuildKit), không đụng thư mục gốc
├── multi_main.py               # runner nhiều tài khoản, dựa trên SimpleBot của src/main.py
├── gateway_link.py             # nối với omnichannel gateway (khi có GATEWAY_URL)
├── session_keeper.py           # giữ phiên Facebook: lưu cookie Facebook cấp lại
├── connection_history.py       # lịch sử kết nối từng tài khoản (history.json)
└── tests/                      # test runner + contract test với upstream
```

`Dockerfile.dockerignore` là allowlist: thêm file Python mới cho bot thì phải thêm cả dòng `!deploy/<file>` vào đó và vào lệnh `COPY` trong `deploy/bot/Dockerfile`, nếu không image sẽ thiếu file.

## 🚀 Bắt đầu nhanh

```bash
cd deploy
docker compose up -d --build
```

Muốn chạy lệnh `docker compose` từ thư mục gốc mà không cần `-f`, tạo file `.env` ở thư mục gốc (upstream đã gitignore `.env`):

```bash
echo "COMPOSE_FILE=deploy/docker-compose.yml" >> .env
```

1. `login` mở trình duyệt tại <http://localhost:6080/vnc.html?autoconnect=1&resize=scale>. Đăng nhập Facebook ở đó.
2. Khi có cookie `c_user` và `xs`, `login` ghi `/data/accounts/<ACCOUNT>/config.json` (quyền `0600`, `ACCOUNT` mặc định `default`) vào volume rồi tự dừng. Có thể phải chờ tới khoảng 30 giây để Chromium ghi cookie xuống đĩa; màn hình "Aw, Snap!" lúc đó là bình thường.
3. `bot` khởi động sau khi `login` thành công và chạy mọi tài khoản trong `/data/accounts`.

## 👥 Nhiều tài khoản

```bash
ACCOUNT=acc2 docker compose run --rm --service-ports login            # đăng nhập thêm acc2
docker compose restart bot                                            # nạp tài khoản mới
FORCE_LOGIN=1 ACCOUNT=acc2 docker compose run --rm --service-ports login  # đăng nhập lại khi cookie hết hạn
```

- Mọi tài khoản dùng chung một tiến trình Python, event loop và `httpx.AsyncClient`. Mỗi tài khoản vẫn có một tiến trình bridge Go riêng vì bridge chỉ hỗ trợ một client.
- Log có nhãn tài khoản, ví dụ `[acc2] [bot] ...`. Dòng log của chính bridge chưa có nhãn.
- Tài khoản lỗi được thử lại với backoff (30 giây, nhân đôi) mà không làm dừng tài khoản khác. Chỉ **phiên hết hạn thật** (vẫn tới được Facebook nhưng cookie không còn cho ra dataFB) mới dừng sau 2 lần; mất mạng, lỗi bridge… thì thử lại mãi, tối đa mỗi 2 phút, để có mạng lại là tự kết nối. `dataGetHome` trả `None` cả khi mất mạng, nên bot thử tải `facebook.com/robots.txt` (không cookie) để phân biệt. Bộ đếm reset nếu lần chạy trước kéo dài từ 10 phút trở lên.
- Từ fbchat-v2 2.3.4 thư viện tự nối lại khi mất mạng (cả lúc khởi động) thay vì ném lỗi: bot nhận trạng thái `reconnecting` của thư viện để chuyển tài khoản sang `retrying` (ghi lịch sử "Mất kết nối, thư viện đang tự nối lại"), và về `running` khi thư viện báo `connected` hoặc bridge báo đã nối lại E2EE (`reconnected`, `e2eeConnected`): có lần thư viện chỉ nối lại socket E2EE mà không báo `connected`, tài khoản từng kẹt `retrying` làm container `unhealthy` dù vẫn chạy (30/10/2026). Lỗi xác thực vẫn dừng listener và đi qua vòng thử lại ở trên.
- Tên tài khoản chỉ gồm chữ, số, `_`, `.`, `-` (tối đa 64 ký tự, bắt đầu bằng chữ hoặc số). Xóa tài khoản: dừng bot, xóa `/data/accounts/<tên>` trong volume rồi khởi động lại.

## 🩺 Healthcheck và restart

- `multi_main.py` ghi trạng thái từng tài khoản (`starting`, `running`, `retrying`, `dropped`) vào `FBCHAT_HEALTH_FILE` (`/tmp/fbchat-health.json` trong image).
- Container chỉ `healthy` khi mọi tài khoản là `running`; `docker compose ps` hiện `unhealthy` khi có tài khoản đang thử lại hoặc bị bỏ. Chưa có tài khoản nào thì chỉ `healthy` ở chế độ gateway (có `GATEWAY_URL`); chạy riêng lẻ vẫn cần ít nhất một tài khoản, nếu không container dừng ngay khi khởi động.
- Giữ phiên: mọi request (HTTP lẫn bridge E2EE) dùng cùng một danh tính trình duyệt (Linux, Chrome 141), không xoay User-Agent. 10 phút sau khi kết nối rồi mỗi ngày (± 2 giờ), bot lấy cookie hiện tại từ bridge (`getCookies`), mở trang chủ Facebook một lần bằng cookie đó và lưu cookie Facebook cấp lại vào `config.json` (`deploy/session_keeper.py`). Chỉ lưu khi `c_user` không đổi, `xs` còn và trang chủ vẫn đăng nhập; không xoá khoá cũ, log chỉ ghi tên cookie đổi. Không cần mở trình duyệt hằng ngày: phiên thứ hai (hoặc dùng chung cookie trên trình duyệt) dễ bị Facebook coi là bất thường.
- Bot dùng `restart: unless-stopped`. Khi mọi tài khoản bị bỏ, tiến trình vẫn chạy (không thoát) để Docker không restart và gọi lại Facebook bằng cookie hỏng. Hãy đăng nhập lại rồi `docker compose restart bot`.

## 📊 Tài nguyên

| Dịch vụ | Image | Giới hạn | Đo thực tế |
|---|---|---|---|
| `login` | `alpine:3.22` + Chromium (~880 MB) | 1 CPU, 768 MiB | ~225-325 MiB khi đang đăng nhập, sau đó dừng |
| `bot` | `python:3.12-alpine` (~95 MB) | `BOT_CPUS` (mặc định 1), `BOT_MEMORY_LIMIT` (mặc định 512M) | Python ~25 MiB chung + 15-25 MiB mỗi tài khoản lúc rảnh; 2 tài khoản ~60 MiB, CPU < 1% |

Tăng `BOT_MEMORY_LIMIT` khi thêm nhiều tài khoản hoặc gửi media lớn, vì bridge giữ cả file media trong RAM khi gửi hoặc tải. Sau khi đăng nhập xong có thể xóa image login: `docker image rm fbchat-v2-login`.

Biến môi trường (shell hoặc `.env`): `ACCOUNT`, `FORCE_LOGIN`, `LOGIN_TIMEOUT` (giây, mặc định 900), `VNC_PASSWORD`, `BOT_ADMINS` (ID cách nhau bằng dấu phẩy), `BOT_PREFIX`, `BOT_CPUS`, `BOT_MEMORY_LIMIT`.

## 🛡️ Bảo mật

- noVNC chỉ bind `127.0.0.1`. Profile Chromium nằm trên tmpfs và mất khi container dừng.
- Chromium không bật remote debugging hay automation flag; script đọc và giải mã file SQLite `Cookies` trong profile (`--password-store=basic`). Policy tắt DevTools và trình quản lý mật khẩu.
- Chromium chạy với `--no-sandbox` vì seccomp mặc định của Docker chặn sandbox của nó; container chỉ dùng để mở Facebook.
- Bot chạy user không phải root, root FS read-only, `cap_drop: ALL`, `no-new-privileges`. Cookie nằm trong volume `fbchat-data`, không nằm trong image hay thư mục repo.

## 🔗 Chế độ omnichannel (gateway)

Khi đặt `GATEWAY_URL` và `GATEWAY_TOKEN` (ít nhất 32 ký tự), `multi_main.py` chuyển mọi tin khách sang omnichannel gateway (`POST /v1/inbound`) thay vì chạy lệnh `/ping`..., và mở `POST /send` tại cổng `BOT_HTTP_PORT` (mặc định 7002) để nhận tin nhân viên trả lời. Đặt `BOT_COMMANDS=1` để vẫn chạy lệnh. Code nằm trong `gateway_link.py`; stack đầy đủ (Libredesk + gateway + bot) ở thư mục `omnichannel/` riêng.

- `thread_id` gửi cho gateway: `e2ee:<chatJid>` cho chat mã hóa, `thread:<threadId>` cho chat thường; nhóm nhận biết theo `threadType`.
- Tên người gửi lấy bằng `_get_user_info` và được cache.
- File đính kèm (ảnh, video, audio, file): bot tải qua `downloadE2EEMedia` (chat mã hóa) hoặc `downloadMedia` (chat thường) rồi gửi kèm base64 cho gateway; file nhân viên gửi đi bằng `sendE2EEImage`/`sendE2EEVideo`/`sendE2EEAudio`/`sendE2EEDocument` hoặc `sendImage`/`sendFile`. Sticker tải về như ảnh (sticker kho của Messenger trong chat mã hóa: bridge lấy URL qua `receiverFetchID`); link, vị trí thành dòng mô tả. File không tải được (lỗi, quá lớn) thành nhãn `🧩 Sticker`, `🖼️ Ảnh`, `🎬 Video`, `📎 Tệp: tên`... kèm link gốc nếu chat thường có; bridge báo lý do tra sticker thất bại qua `fetchError` và bot ghi vào log `Không lấy được sticker: ...`. Dòng tóm tắt tin (ghi chú cảm xúc, trích dẫn) dùng cùng nhãn, không kèm link. Giới hạn mỗi tệp `GATEWAY_MAX_FILE_MB` (mặc định 20).
- Loại tin E2EE bridge chưa đọc được (danh thiếp, bình chọn, xem một lần, vị trí trực tiếp...) đến dưới dạng tin rỗng: bot gửi dòng `❓ Loại tin chưa hỗ trợ: xem trên Messenger` thay vì bỏ qua. Tin thường rỗng vẫn bỏ qua.
- Tin E2EE không giải mã được: sự kiện `raw` của whatsmeow (`UndecryptableMessage`) có chat, người gửi và ID tin; lý do nằm ở sự kiện `error` code 2 (xem "Tin E2EE không giải mã được" bên dưới). Bot chờ 15 giây (`UNDECRYPTABLE_GRACE_SECONDS`) rồi gửi tin `⚠️ Tin nhắn mã hóa không giải mã được: xem trên Messenger` vào đúng hội thoại, trừ khi tin thật cùng ID đã tới trong lúc chờ (thường gặp với tin nhóm khi bot chưa có khoá nhóm của người gửi: bridge xin gửi lại và tin tới sau khoảng 1 giây). Tin báo lỗi dùng ID riêng `undecryptable-<id>`, nên nếu tin thật tới muộn hơn thì vẫn vào. Bỏ qua tin của chính mình và loại `DecryptFailMode=hide`.
- Tin chat thường (không E2EE) gửi lúc bot không chạy: bridge bỏ tin cũ hơn lúc kết nối, và đợt đồng bộ khi kết nối cũng không gửi lại tin bị lỡ (Messenger chỉ tải khi mở hội thoại), nên chưa lấy lại được. Chat Facebook mới đều là E2EE, bridge tự đồng bộ lại.
- Tin trả lời không có xác nhận từ bridge (deliveryStatus UNKNOWN) vẫn trả 200 để gateway không gửi lại, tránh khách nhận trùng.

### Trích dẫn và thu hồi tin nhân viên

- `POST /send` nhận thêm `reply_to` (messageID tin khách): bot gửi trả lời có trích dẫn (`send_e2ee_message(..., reply_to_id, reply_to_sender_jid)` hoặc `send_message(..., reply_to_id)`), JID người gửi lấy từ bộ nhớ 4096 tin gần nhất. Trả về `{"ok": true, "message_ids": [...]}`.
- Tin nhân viên kèm audio trong chat mã hóa đi thành **tin thoại** (`sendE2EEAudio` với `ptt: true`); thời lượng đọc từ header file (m4a/mp4: hộp `mvhd`, ogg opus: granule trang cuối), định dạng khác gửi 0.
- `POST /react {account, thread_id, message_id, emoji}`: nhân viên thả cảm xúc lên tin khách qua RPC `sendE2EEReaction` (cần JID người gửi tin gốc; chat 1-1 thì là khách) hoặc `sendReaction`; `emoji` rỗng là bỏ, FE0F được bỏ đi (Messenger dùng ❤).
- `POST /recall {account, thread_id, message_ids}`: `unsendE2EEMessage` / `unsendMessage` qua `BridgeActions`; sự kiện `messageUnsend` của chính tin đó không ghi chú lặp.

### Sửa tin, trạng thái khách và nhắn trước

- `POST /edit {account, thread_id, message_id, text}`: `editE2EEMessage`/`editMessage`; sự kiện `messageEdit` của chính tin đó không ghi chú lặp.
- "Đang soạn"/"đã xem" của khách (`typing`, `readReceipt`, `e2eeReceipt` loại `read`, `ChatPresence` trong `raw` của whatsmeow) → `POST /v1/presence`; bỏ qua của chính tài khoản, "đang soạn" tối đa 3 giây/lần.
- `POST /resolve {account, to}`: ID số hoặc link hồ sơ (`profile.php?id=…`, `facebook.com/<id>`) → `{thread_id: "e2ee:<id>@msgr", name, avatar}`.

### Quản lý tài khoản (/accounts)

Server HTTP của bot (cùng `GATEWAY_TOKEN` với `/send`) có thêm các route cho trang **Channel accounts** của Libredesk; gateway gọi, trình duyệt không gọi trực tiếp:

| Route | Việc |
|---|---|
| `GET /accounts` | Danh sách: `name`, `state` (`starting`, `running`, `retrying`, `dropped`, `stopped`), `profile` (`uid`, `displayName`, `avatar`), `error` (lỗi gần nhất: `session_expired` khi cookie không còn cho ra dataFB, cần đăng nhập lại; `connection` cho lỗi khác; hết phiên thì `message` kèm "Nguyên nhân: …" và `cause`: `revoked` Facebook xoá cookie `c_user`/`xs`, `checkpoint`, `login`, `token`, `unknown`), `history` (lịch sử kết nối, mới nhất trước: `at`, `kind` `connected`/`manual`/`network`/`disconnected`/`platform`/`session_expired`/`decrypt`/`keycheck`, `message`, `count`/`last_at` khi lặp; lưu ở `<tài khoản>/history.json` 0600, tối đa 30 mốc) |
| `POST /accounts/<tên>/cookie` `{"cookie": "..."}` | Chỉ dùng nội bộ (giao diện chỉ đăng nhập bằng trình duyệt). Cookie phải có `c_user` và `xs`; bot gọi `dataGetHome` để kiểm tra với Facebook (422 nếu bị từ chối, không lưu), rồi ghi `config.json` (0600) và chạy tài khoản |
| `POST /accounts/<tên>/restart` | Kết nối lại (cũng dùng sau khi đăng nhập bằng trình duyệt) |
| `DELETE /accounts/<tên>` | Dừng và xoá thư mục tài khoản, cùng tin đã nhớ của tài khoản (trích dẫn, nhóm, thành viên) và tệp trace. Tin báo lỗi giải mã đang chờ bị huỷ |

Tên/ảnh của chính tài khoản lấy từ `/chat/user_info`; một số tài khoản không tra được chính mình, khi đó lấy từ bảng danh bạ LightSpeed (`LSDeleteThenInsertContact`, `LSVerifyContactRowExists`) bridge gửi lúc kết nối. Bảng này cũng điền tên cho khách có trong danh bạ.

`AccountManager` (trong `multi_main.py`) chạy mỗi tài khoản trong một task; dừng hoặc kết nối lại là huỷ task, `SimpleBot.run()` tự dừng bridge. Khi bật gateway, bot vẫn khởi động khi chưa có tài khoản nào, và healthcheck vẫn `healthy`; chạy riêng lẻ (không có `GATEWAY_URL`) vẫn cần ít nhất một tài khoản.

Đăng nhập bằng trình duyệt dùng dịch vụ `fb-login-ui` (image `login/`, lệnh `control.py`): rảnh chỉ có server điều khiển (~20 MiB); `POST /session {"account", "target"}` chạy `extract_cookie.py` với `FORCE_LOGIN=1` (Chromium + noVNC cổng 6080); `target` mặc định `facebook` ghi cookie cho fb-bot (`/data/accounts/<tên>`), `fbweb` ghi cho agent Fanpage Web của omnichannel (`/fbweb/<tên>/config.json`, volume `fbweb-logins`, D18), `GET /session` trả `starting` tới khi noVNC sẵn sàng rồi `running`, `saving` khi `extract_cookie.py` đã thấy đăng nhập và đóng Chromium để ghi cookie, `success` khi đã ghi cookie, `DELETE /session` huỷ. Mỗi lúc một phiên; hồ sơ Chromium bị xoá trước và sau mỗi phiên để tài khoản sau không nhận nhầm cookie. Server điều khiển cần `GATEWAY_TOKEN` và không log URL/header. Giao cookie (omi, một container và một volume mỗi tài khoản, D28): đặt `LOGIN_HANDOFF_DIR` (tmpfs) thì `target` `facebook` không ghi vào volume bot mà giữ cookie ở đó; gateway gọi `POST /session/cookie {"account"}` lấy một lần (xoá ngay sau đó, 404 nếu không có) rồi đưa vào `POST /accounts/<tên>/cookie` của container bot; `target` `fbweb` ở chế độ này chỉ nhận khi `FBWEB_LOGINS_DIR` được đặt rõ (omi-host gắn volume phiên Fanpage Web của phòng khám ở đó; thư mục `/fbweb` có sẵn trong image, không gắn volume thì cookie mất cùng container), không thì 400.

### Tin giàu nội dung và sự kiện

- Trích dẫn: tin E2EE chỉ có `replyTo.messageId`, nên bot nhớ 4096 tin gần nhất mỗi tài khoản (khoá `tài khoản:messageId`) để gửi `quote` = `Tên: nội dung`.
- Sticker tải về như ảnh; vị trí thành link Google Maps; link kèm mô tả.
- Avatar: chat 1-1 gửi `thread_avatar` = `thumbSrc` của người nhắn (cùng lần tra tên); nhóm gửi `sender_avatar` của từng người để giao diện hiện avatar thành viên.
- Nhóm: chat E2EE có JID `<id>@g.us` là nhóm. Tin E2EE không mang tên nhóm, nên bot đọc tên/ảnh nhóm từ bảng LightSpeed trong sự kiện `raw` (`LSDeleteThenInsertThread`, `LSSyncUpdateThreadName`, `LSSetThreadImageURL`). Bảng này chỉ nhắc nhóm khi Messenger đồng bộ đúng nhóm đó, và bot quên khi khởi động lại, nên nhóm E2EE chưa biết tên thì bot hỏi server qua bridge (`get_e2ee_group_info`, mỗi nhóm tối đa một lần mỗi giờ). Vẫn chưa biết thì gửi tên trống: gateway giữ tên nhóm đã biết, hoặc đặt `👥 Nhóm Facebook` nếu chưa từng biết (không bao giờ lấy tên người gửi).
- Sự kiện nhóm Facebook (đổi tên, thêm/rời/xoá thành viên, quản trị viên) cũng đọc từ bảng LightSpeed (`LSSyncUpdateThreadName`, `LSAddParticipantIdToGroupThread`, `LSRemoveParticipantFromThread`, `LSUpdateThreadParticipantAdminStatus`) thành ghi chú `group_event`. Các bảng này cũng là dữ liệu đồng bộ lúc kết nối, nên bot chỉ báo khi khác trạng thái đã biết: đổi tên khi tên khác tên đã biết, thêm thành viên/đổi quản trị chỉ khi đã thấy danh sách thành viên nhóm đó và lô không phải ảnh chụp cả hội thoại. Thà bỏ sót còn hơn báo sai cả loạt mỗi lần khởi động.
- `AccountBot._forward_listener_event` chặn `e2eeReaction`, `reaction`, `messageEdit`, `messageUnsend` (SimpleBot upstream lọc bỏ) và gửi `POST /v1/event`, thành ghi chú nội bộ. Cảm xúc gửi thêm `target_ids` (messageId), `reactor_id` (ID người thả, `self` cho chủ tài khoản) và `reaction` (emoji, rỗng khi bỏ) để gateway hiện huy hiệu trên đúng tin; không tìm được tin thì vẫn là ghi chú.
- Tin có `senderId` là chính tài khoản (gửi từ thiết bị khác) thành ghi chú `owner_message`; tin do bot gửi qua `/send` được nhận ra bằng `messageId` trả về hoặc trùng nội dung trong 60 giây.
- Tên Facebook: `/chat/user_info` trước; không có hồ sơ (người lạ, không phải bạn bè) thì hỏi danh bạ Messenger qua bridge (`get_user_info`, cả ảnh đại diện). Cả hai không có thì dùng nhãn `Facebook <id>` và tra lại sau 1 giờ.

### Trạng thái thiết bị E2EE

`AccountBot` lưu trạng thái thiết bị E2EE vào `/data/accounts/<tên>/e2ee_device.json` (quyền `0600`). Upstream mặc định giữ trạng thái này trong RAM (`e2ee_memory_only=True`): mỗi lần restart là một thiết bị E2EE mới và tin đến thường báo `E2EE message could not be decrypted or was unavailable`. Đặt `FBCHAT_E2EE_PERSIST=0` để quay lại hành vi upstream. File này là khóa mã hóa của tài khoản: không copy ra ngoài volume.

#### Tin E2EE không giải mã được

Mỗi tin không giải mã được (sự kiện `error` code 2, trừ `reason=unavailable`):

- Ghi vào lịch sử tài khoản (trang Tài khoản kênh) với `kind: "decrypt"`: nhóm hay chat 1-1, mã thiết bị gửi (8 ký tự đầu SHA-256 của JID, không lộ ID), loại bản mã lỗi (tin mở phiên, tin thường, tin nhóm) và lý do. Nếu thiết bị đó từng gửi tin mở phiên `state=false` (bridge không lưu phiên) thì mục ghi thêm số tin này. Các lần liền nhau từ cùng thiết bị gộp một mục.
- Cùng một thiết bị gửi có 3 tin khác nhau lỗi trong 24 giờ thì báo một lần qua `POST /v1/alert` của gateway (Telegram theo trang Cảnh báo). Bridge thử lại mỗi tin vài lần với cùng ID nên đếm theo ID tin.

Từ 03/11/2026 app Messenger mới gửi tin Signal có trường protobuf mới; libsignal v0.2.2 kiểm tra MAC trên bản serialize lại nên mọi tin từ các máy này lỗi `bad_mac`/`no_valid_session` (cả tin mở phiên). Bridge dùng libsignal v0.2.3 (kiểm tra trên byte gốc). Gặp lại kiểu lỗi này với mọi người gửi của một máy thì kiểm tra phiên bản libsignal trước khi đổi thiết bị.

`bad_mac` (MAC không khớp) cũng có thể nghĩa là phiên Signal giữa thiết bị của bot và một thiết bị của người gửi đã lệch. Lỗi này không tự hết: bridge xin gửi lại nhưng Messenger vẫn mã hoá bằng phiên cũ. Cách sửa:

1. Người gửi đăng xuất rồi đăng nhập lại Messenger trên thiết bị đó (thiết bị mới thì phiên mới).
2. Nếu không biết thiết bị nào hoặc nhiều người cùng lỗi: dừng tài khoản, đổi tên `e2ee_device.json` rồi chạy lại để bot thành thiết bị E2EE mới (Facebook thấy thêm một thiết bị; tin đã lỗi không lấy lại được).

Mỗi lần E2EE kết nối, lịch sử có thêm mục `keycheck`: khoá E2EE server phát cho thiết bị bot khớp hay lệch khoá bot giữ (lệch khoá nào). Lệch thì người khác không mở được phiên mới với bot.

fb-bot in mỗi sự kiện khoá nhóm (`e2eeSenderKey`) ra log với nhãn `[e2ee-key]`, chỉ kèm mã thiết bị đã băm: tin nhóm là lần gửi lại thứ mấy, có kèm khoá nhóm không, đã lưu khoá nhóm của thiết bị nào. Khi bước khoá nhóm hỏng (không lưu được khoá, khoá đến trong chat 1-1, không gửi được yêu cầu gửi lại) thì ghi thêm mục `decrypt` vào lịch sử.

Chế độ một tài khoản (omi, một container và một volume mỗi tài khoản, D28): `BOT_ACCOUNT=<tên>` chỉ chạy tài khoản này, `GET /accounts` chỉ hiện nó (kể cả khi chưa đăng nhập), mọi lệnh cho tài khoản khác trả 404. Trống: mọi tài khoản trong `/data/accounts` như trước.

Debug payload: `FBBOT_TRACE=acc2,shop2` (tên tài khoản, cách nhau bởi dấu phẩy) ghi mọi sự kiện thô của listener, kể cả loại bot đang bỏ qua (vd. tín hiệu cuộc gọi), vào `/data/trace/<tên>-<giờ UTC>.jsonl` (quyền `0600`, tối đa 20 MiB mỗi tệp). Tệp có nội dung tin nhắn: chỉ bật cho tài khoản thử, xoá tệp và tắt biến khi xong.

## 🔄 Đồng bộ với upstream

Quy trình chung cho mọi fork của hệ thống omnichannel (nhánh riêng, kiểm tra, canary, ghim lại, bẫy đã gặp): `omnichannel/docs/UPSTREAM.md`.

Remote `upstream` trỏ tới repo gốc, `origin` trỏ tới fork:

```bash
git fetch upstream
git merge upstream/main          # hoặc: git rebase upstream/main
cd deploy && docker compose build && docker compose up -d
```

Fork không chỉ thêm file trong `deploy/`: nó còn sửa `src/_core/_utils.py`, `src/_core/_session.py`, `src/_messaging/_listening_e2ee.py`, `_attachments.py`, `_editMessage.py`, `_listening.py`, `src/main.py`, `bridge-e2ee/main.go`, `CHANGELOG.md` và `CLAUDE.md` (cùng bản sinh trong `src/fbchat_v2/`). Merge có thể conflict ở các file này; xem trước bằng `git diff upstream/main -- . ':!deploy'`. Rủi ro còn lại là upstream đổi API mà code trong `deploy/` dựa vào; khi đó chạy:

```bash
pytest deploy/tests
```

Các điểm bám vào upstream (được `test_upstream_contract_used_by_fork` kiểm tra):

- `src/main.py`: `SimpleBot` (tham số `prefix`, `admins`, `log_message_content`, `debug_errors`, `http_client`; method `_queue_event`, `_forward_listener_event`), `log`, `DEFAULT_HTTP_TIMEOUT`, `is_valid_datafb`.
- `listeningE2EEEvent`: thuộc tính `device_path`, `e2ee_memory_only`, `startup_timeout`, `wait_until_connected(timeout, require_e2ee=...)`.
- `dataGetHome(storage=...)`, `FileSessionStorage`, `set_private_file_permissions`.

Các điểm bám khác (test không kiểm trực tiếp, nhưng import hỏng thì test cũng lỗi):

- `listeningE2EEEvent.get_cookies()` (`multi_main.py`, cho `session_keeper.py`).
- `_core._session._build_home_request`, `_core._utils.parse_cookie_string`, `send_get_request_async` (`session_keeper.py`, `connection_history.py`).
- `_core._console.configure_utf8_console`, `_messaging._listening_e2ee._format_exception_chain` (`multi_main.py`).
- `BridgeActions`, `_features._facebook._get_user_info` (`gateway_link.py`).

`_build_home_request` và `_format_exception_chain` là helper nội bộ, upstream có thể đổi mà không báo trước.
