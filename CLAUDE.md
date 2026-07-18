# CLAUDE.md - Hướng dẫn codebase fbchat-v2 cho contributor và coding agent

File này cung cấp context triển khai. Tài liệu cho người dùng nằm ở `README.md`, `README_EN.md` và `DOCS.md`.

## Tóm tắt bắt buộc

- Repository dùng kiến trúc 3 tầng: `_core`, `_features`, `_messaging`.
- Public I/O API mới là async-first và không có hậu tố `_async`.
- HTTP async phải dùng `httpx.AsyncClient` thật.
- Helper blocking còn lại phải có hậu tố `_blocking` và chỉ nằm ở boundary.
- `dataFB`, cookie, credential, token, TOTP và E2EE device state là secret.
- `src/config.json` là local-only; chỉ track `src/config.example.json`.
- Bot mẫu dùng E2EE listener làm receive/send transport chính.
- Mọi thay đổi public behavior phải cập nhật cả tài liệu Việt và Anh.
- Commit dùng Conventional Commits có scope.

## Cấu trúc repository

```text
fbchat-v2/
├── src/
│   ├── main.py
│   ├── config.example.json
│   ├── _core/
│   │   ├── _http.py
│   │   ├── _session.py
│   │   ├── _storage.py
│   │   ├── _utils.py
│   │   └── _facebookLogin.py
│   ├── _features/
│   │   ├── _facebook/
│   │   └── _thread/
│   └── _messaging/
│       ├── _send.py
│       ├── _attachments.py
│       ├── _listening.py
│       ├── _listening_e2ee.py
│       ├── _bridge_actions.py
│       ├── _send_e2ee.py
│       ├── _editMessage.py
│       ├── _changeTheme.py
│       ├── _createNotes.py
│       ├── _reactions.py
│       ├── _unsend.py
│       └── _message_requests.py
├── bridge-e2ee/
│   ├── main.go
│   ├── bridge/
│   ├── meta/
│   └── go.mod
├── tests/
├── README.md
├── README_EN.md
├── DOCS.md
├── FLOWCHART.md
└── pyproject.toml
```

## Kiến trúc 3 tầng

### Tầng 1: `_core`

Sở hữu:

- HTTP transport.
- Session bootstrap.
- Storage abstraction.
- Cookie/form/parser/ID utilities.
- Credential login và 2FA.

Không được import `_features` hoặc `_messaging`.

### Tầng 2: `_features`

Sở hữu nghiệp vụ Facebook và thread:

- Account/profile/Marketplace.
- Search, notification, block/unblock.
- Thread list, rename, emoji, nickname, admin.

Phụ thuộc `_core`, không sở hữu listener hoặc bot lifecycle.

### Tầng 3: `_messaging`

Sở hữu:

- Send và attachment HTTP.
- MQTT listener thường.
- E2EE bridge listener/action.
- Reaction, edit, unsend, theme, notes, message requests.

Phụ thuộc `_core`. Chỉ bot/application mới phối hợp `_features` với `_messaging`.

## Hợp đồng `dataFB`

Schema tối thiểu:

```python
{
    "fb_dtsg": "...",
    "jazoest": "...",
    "sessionID": "...",
    "FacebookID": "100012345678",
    "clientRevision": "...",
    "cookieFacebook": "c_user=...; xs=...; fr=...; datr=...;",
}
```

Nguồn duy nhất:

```python
data_fb = await dataGetHome(cookie_or_storage)
```

Không tự tạo dict giả ở runtime. Tests dùng fixture synthetic trong `tests/conftest.py`.

Không log object. Khi validate, chỉ báo tên field thiếu:

```python
missing = [name for name in REQUIRED if not data_fb.get(name)]
logger.error("Missing dataFB fields: %s", missing)
```

## Hợp đồng async

### Naming

Public coroutine dùng tên domain ngắn:

```python
await dataGetHome(...)
await module.func(...)
await sender.send(...)
await listener.connect_mqtt()
```

Không thêm:

```python
func_async = func
func_sync = func
```

Blocking compatibility helper phải rõ nghĩa:

```python
send_blocking(...)
connect_mqtt_blocking(...)
call_blocking(...)
```

### Native async và thread adapter

Native async bắt buộc cho HTTP:

```python
response = await send_request_async(req, client=client)
```

Thread adapter chỉ hợp lệ cho thư viện blocking không thể thay:

```python
await asyncio.to_thread(self.connect_mqtt_blocking)
await asyncio.to_thread(self.call_blocking, method, params, timeout)
```

Không bọc code `requests` mới trong `to_thread` chỉ để gắn nhãn async. Chỉ giữ boundary legacy có lý do rõ ràng và test.

### Client injection

Feature HTTP nên có keyword-only client:

```python
async def func(
    dataFB: dict[str, Any],
    feature_value: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    ...
```

Caller-owned client không được đóng bên trong feature. Owned temporary client phải được context manager đóng.

## HTTP implementation

### Transport flow

```text
feature._build_request
  -> _core._utils helper
    -> _core._http.post_async/get_async
      -> httpx.AsyncClient
```

`_core._http._clean_kwargs()` copy input trước khi pop. Giữ behavior này; mutate request dict của caller sẽ tạo race khi retry hoặc concurrent use.

### GraphQL flow

```python
form = formAll(
    data_fb,
    FBApiReqFriendlyName="FriendlyName",
    docID="123",
)
payload = await post_form_json_async(
    GRAPHQL_URL,
    form,
    data_fb["cookieFacebook"],
    client=client,
)
```

Parser phải kiểm tra:

- HTTP status.
- JSON decode.
- Top-level `error`.
- GraphQL `errors`.
- Nested `data`/`payload` và field bắt buộc.

HTTP 200 không đồng nghĩa mutation success.

### TLS và timeout

- Không dùng `verify=False`.
- Không dùng `ssl.CERT_NONE` cho MQTT chứa cookie.
- Mọi request có timeout hữu hạn.
- Retry chỉ áp dụng lỗi transient, có backoff và giới hạn.
- Không retry mutation mù nếu request có thể đã được server áp dụng.

## Session và storage

`dataGetHome()`:

1. Resolve cookie từ tham số hoặc storage.
2. GET homepage.
3. Parse token.
4. Validate `FacebookID` và field bắt buộc.
5. Trả `dataFB` hoặc `None`.

`FileSessionStorage` ghi atomically. Không đổi thành `write_text()` trực tiếp cho file cookie; process bị kill có thể cắt hỏng JSON.

`src/config.json` không được track. Đừng “tiện tay” commit file này khi test bot.

## Feature conventions

Mỗi module mới nên tách:

```python
def _validate_inputs(feature_value: str) -> None: ...
def _build_request(dataFB: dict, feature_value: str) -> dict: ...
def _parse_response(text: str) -> dict: ...

async def func(dataFB: dict, feature_value: str, *, client=None):
    _validate_inputs(feature_value)
    request = _build_request(dataFB, feature_value)
    response = await send_request_async(request, client=client)
    response.raise_for_status()
    return _parse_response(response.text)
```

Yêu cầu:

- Validate ID rỗng, enum, price, coordinate và file trước I/O.
- Không giữ request form mutable ở module global hoặc instance state.
- Không silently ignore tham số.
- Chưa hỗ trợ schema thì raise `NotImplementedError` rõ ràng.
- Error result giữ message hữu ích nhưng không chứa secret.
- Parser unit-test được mà không gọi mạng.

## Regular messaging

`_send.api.send()` build một form mới cho mỗi call. Giữ concurrency safety này. `self.results` chỉ dành cho compatibility/debug snapshot.

Input rules:

- `threadID` list chỉ dùng với `typeChat="user"`.
- `typeChat` chỉ `None` hoặc `"user"`.
- Attachment type nằm trong map hỗ trợ.
- `typeAttachment` và `attachmentID` luôn đi cùng nhau.
- Reply cần `messageID`.
- Content hoặc attachment phải có ít nhất một.

`_attachments.func()` luôn đóng file handle. Success send dùng `typeAttachment`, không dùng MIME `attachmentType`.

`_reactions.func()` trả raw `httpx.Response`, khác với phần lớn module trả dict. Đừng document sai contract này.

## Regular listener lifecycle

`listeningEvent.__init__()` không chạy network. Workflow:

```python
listener = listeningEvent(data_fb)
task = asyncio.create_task(listener.connect_mqtt())
try:
    event = await listener.get_message(timeout=30)
finally:
    await listener.disconnect()
    await task
```

Invariant:

- Queue có giới hạn.
- Full queue drop oldest và tăng `droppedMessages`.
- Parse toàn bộ delta, không chỉ index 0.
- `bodyResults` chỉ là latest snapshot.
- Reconnect ở vòng ngoài, không đệ quy trong callback.
- TLS certificate verification bật.

## E2EE bridge architecture

```text
asyncio application
  -> listeningE2EEEvent
    -> _BridgeProcess
      <-> line-delimited JSON-RPC
        <-> fbchat-bridge-e2ee Go subprocess
          <-> mautrix-meta / Messenger
```

### Binary resolution

Thứ tự:

1. Constructor `binary_path`.
2. `FBCHAT_E2EE_BIN`.
3. Default `build/fbchat-bridge-e2ee[.exe]`.
4. Auto-download cho default missing path.

Auto-download security:

- GitHub Releases API qua HTTPS.
- Kiểm tra initial host.
- Giới hạn 200 MiB.
- Stream file tạm và atomic replace.
- Verify SHA-256 digest khi API cung cấp.

Production nên pin binary đã verify.

### RPC process

`_BridgeProcess` có:

- Reader thread phân response theo request `id`.
- Event queue cho object không có `id`.
- Write lock cho stdin.
- Pending request map có lock.
- Request size limit 150 MiB.
- Timeout và `BridgeError`.
- Watchdog respawn tối đa 5 lần.

Async `call()` phải await `asyncio.to_thread(call_blocking, ...)`. Blocking code nội bộ gọi `call_blocking()` trực tiếp; không gọi coroutine rồi dùng `.get()`.

### Listener callback

`on_message(fn)` nhận callback sync. Callback không chạy trên asyncio loop. `src/main.py` là pattern chuẩn:

```python
loop = asyncio.get_running_loop()
listener.on_message(
    lambda event: loop.call_soon_threadsafe(queue_event, event)
)
```

Không truyền `connect_mqtt` coroutine cho `threading.Thread`.

### Readiness

Sau `create_task(connect_mqtt())`, bridge chưa chắc đã connect. Dùng:

```python
ready = await asyncio.to_thread(
    listener.wait_until_connected,
    90,
    require_e2ee=True,
)
```

Mọi send trước ready là race.

### BridgeActions

Public async methods:

- `edit_message`
- `unsend_message`
- `edit_e2ee_message`
- `unsend_e2ee_message`
- `send_typing_indicator`
- `mark_read`
- `send_e2ee_typing`
- `send_e2ee_audio`
- `send_e2ee_image`
- `download_media`
- `download_e2ee_media`

Mỗi async method có blocking counterpart rõ hậu tố. Binary bytes được base64 đúng tại RPC boundary, không sớm hơn.

## `src/main.py`

Bot mẫu hiện tại:

- Đọc `src/config.json` bằng `FileSessionStorage`.
- Gọi `await dataGetHome()`.
- Dùng một `httpx.AsyncClient` cho command HTTP.
- Start E2EE listener task.
- Chuyển callback về `asyncio.Queue` bounded.
- Nhận cả `e2eeMessage` và `message`.
- Bỏ self-message và dedupe message ID.
- Reply E2EE nếu có `chatJid`; fallback thường nếu có `threadId`.
- `/unsend` dùng `BridgeActions.unsend_e2ee_message`.
- Shutdown stop bridge và await task.

Khi thêm command:

```python
async def _cmd_name(self, message: dict[str, Any], argument: str) -> None:
    await self._reply(message, "...")
```

Đăng ký handler trong `self._handlers`. Không chạy CPU-bound work trực tiếp trên loop.

## Login security

- Cookie session là flow khuyến nghị.
- FB4A key/token built-in là legacy defaults; env chỉ override.
- TOTP dùng local `pyotp`.
- Không gọi `2fa.live`.
- Không log login form, password, OTP hoặc access token.
- Giữ xử lý subcode `1348162`, `1348023` trừ khi có evidence server mới.
- Mocked tests không phải live account validation.

## Config files

`src/config.example.json` được track:

```json
{
  "botName": "fbchat-v2 demo bot",
  "prefix": "/",
  "cookies": "PASTE_YOUR_FACEBOOK_COOKIE_HERE",
  "admins": ["1000xxxxxxxxxx"],
  "version": "0.0.1"
}
```

`src/config.json` phải local và gitignored. Không copy secret vào `.env.example`, README, test hoặc fixture.

## Testing strategy

### Python

```bash
pytest tests/ -v --tb=short
ruff check src tests
ruff format --check src tests
python -m compileall -q src tests
```

Test cần cover:

- Async function là awaitable.
- Injected async client được sử dụng.
- Request form không mutate giữa calls.
- Input validation.
- HTTP error.
- JSON invalid hoặc prefix.
- Missing nested fields.
- Server error payload.
- Listener queue overflow.
- Bridge timeout/error mapping.

Không gọi Facebook live trong CI.

### Go bridge

```bash
cd bridge-e2ee
go test ./...
go vet ./...
```

Khi đổi RPC:

1. Thêm/đổi case trong `main.go`.
2. Implement trong `bridge/`.
3. Cập nhật Python wrapper.
4. Thêm Go test và Python mock test.
5. Cập nhật bridge README và messaging docs.

## Documentation surface

| File | Audience |
|---|---|
| `README.md` | User Việt |
| `README_EN.md` | User English |
| `DOCS.md` | API/workflow đầy đủ |
| `src/_core/README*.md` | Core contributor/user |
| `src/_features/README*.md` | Feature contributor/user |
| `src/_messaging/README*.md` | Messaging/E2EE contributor/user |
| `bridge-e2ee/README.md` | Bridge builder/integrator |
| `FLOWCHART.md` | Runtime architecture |
| `mindmap-mermaid.md` | Repository overview |
| `CHANGELOG.md` | Release history |

Không sửa một bản ngôn ngữ rồi bỏ bản còn lại. Internal links và code examples phải được verify.

## UTF-8 và văn bản tiếng Việt

- File Markdown và Python lưu UTF-8.
- Chuỗi tiếng Việt trong code viết đầy đủ dấu.
- Quét U+FFFD, NUL và marker mojibake trước commit.
- PowerShell console có thể render mojibake dù file đúng.
- Đọc bằng `encoding="utf-8"` và kiểm tra codepoint trước khi rewrite hàng loạt.
- Không dùng em dash trong tài liệu của branch này; dùng dấu gạch ngang `-`.

## Git rules

- Kiểm tra branch, remote và worktree trước staging.
- Worktree bẩn thì stage surgical, không `git add -A` mù.
- Không commit `src/config.json`, `.env`, build binary, security report hoặc secret.
- Dùng Conventional Commits có scope, ví dụ:

```text
fix(messaging): handle empty attachment metadata
docs(api): expand async e2ee documentation
refactor(core): reuse async http transport
```

- Chạy `git diff --check` trước commit.
- Không force-push trừ khi task yêu cầu rewrite history; khi cần dùng `--force-with-lease`.

## Quy trình thêm một feature

1. Xác định đúng tầng.
2. Đọc module tương tự gần nhất.
3. Ghi rõ input/result/error contract.
4. Viết validator và parser thuần.
5. Dùng transport `_core` với optional async client.
6. Viết public coroutine.
7. Thêm test success và edge cases.
8. Chạy test/lint/compile.
9. Cập nhật tài liệu Việt và Anh.
10. Quét UTF-8 và `git diff --check`.

## Gotcha đã từng xảy ra

### Coroutine không được await

Sai:

```python
threading.Thread(target=listener.connect_mqtt).start()
```

Đúng:

```python
task = asyncio.create_task(listener.connect_mqtt())
```

### Coroutine bị dùng như dict

Sai:

```python
info = bridge.call("connect")
user = info.get("user")
```

Đúng:

```python
info = await bridge.call("connect")
```

Blocking internal path gọi `call_blocking()`.

### Attachment metadata null

Không truy cập `payload.get()` khi payload là `None`. Parser phải check type từng tầng. `uploadID` không thay thế `attachmentID`.

### Notification slice

`_notification.func()` trả dict. Lấy `NotificationResults` trước khi slice.

### All thread data index

`_all_thread_data.func()` trả dict, không phải tuple/list. Dùng `dataGet`, `last_seq_id`, `dataAllThread`.

### E2EE callback race

Đăng ký callback trước start listener, chuyển event thread-safe về loop và đợi readiness trước send.

### LS publish không phải server success

Edit/theme success chỉ xác nhận publish. Đừng đổi message thành “server applied” nếu chưa có ACK/event tương ứng.

### Terminal mojibake

Không replace Vietnamese chỉ vì `Get-Content` render sai. Verify bytes/codepoints trước.

## Pre-commit checklist

- [ ] Đúng tầng và không circular import.
- [ ] Public I/O async-first.
- [ ] HTTP dùng `httpx.AsyncClient`.
- [ ] Input validation và timeout hữu hạn.
- [ ] Không leak secret.
- [ ] Parser chịu missing/error fields.
- [ ] Test mới đã chạy.
- [ ] Python compile/lint sạch.
- [ ] Go test sạch nếu đụng bridge.
- [ ] Tài liệu Việt và Anh đồng bộ.
- [ ] Không mojibake/U+FFFD/NUL.
- [ ] `git diff --check` sạch.
- [ ] Staging chỉ gồm file thuộc task.
