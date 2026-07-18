# 🚀 fbchat-v2 v2.2.0 - Async/Await đã chính thức lên sóng

> *Release date: 2026-07-19*
> *Author: MinhHuyDev*

`v2.2.0` là bản nâng cấp lớn của `fbchat-v2`: codebase chuyển sang hướng **async-first**, HTTP runtime ưu tiên `httpx`, listener E2EE được ổn định lại, bot mẫu chạy theo lifecycle `asyncio` rõ ràng hơn và tài liệu được viết lại để người dùng không copy nhầm flow blocking cũ.

Nếu bạn vẫn cần bản `requests` cũ, hãy dùng nhánh/tag `v2.1.4`: <https://github.com/m008v/fbchat-v2/tree/v2.1.4>

---

## ✨ Highlight

### ⚡ Async-first API

- Các API chính chuyển sang coroutine và dùng `await`.
- Module feature và messaging dùng tên hàm thống nhất `func(...)`.
- Loại bỏ alias dư như `func_async = func` và `func_sync` để public API gọn hơn.
- Hỗ trợ truyền `client=httpx.AsyncClient(...)` để tái sử dụng connection khi gọi nhiều API liên tiếp.

Ví dụ:

```python
import asyncio

from _core._session import dataGetHome
from _messaging._send import api as SendAPI


async def main() -> None:
    data_fb = await dataGetHome("c_user=...; xs=...; fr=...; datr=...;")
    if data_fb is None:
        raise RuntimeError("Cookie hết hạn hoặc không lấy được dataFB.")

    result = await SendAPI().send(
        data_fb,
        "Xin chào từ fbchat-v2 v2.2.0",
        threadID="100012345678",
    )
    print(result)


asyncio.run(main())
```

### 🌐 HTTP runtime dùng `httpx`

- Transport HTTP được gom về `_core/_http.py`.
- API async dùng `httpx.AsyncClient`.
- Caller có thể inject client chung để giảm overhead tạo connection.
- Các boundary blocking còn lại được cô lập rõ, không giả async bằng cách bọc `requests` lung tung.

### 🔐 E2EE listener ổn định hơn

- `listeningE2EEEvent.connect_mqtt()` là coroutine dùng được trực tiếp với `asyncio.create_task(...)`.
- Bridge Go chạy qua JSON-RPC stdin/stdout và không kéo process Python chết theo khi bridge lỗi.
- Callback bridge được khuyến nghị đẩy vào `asyncio.Queue` bằng `loop.call_soon_threadsafe(...)`.
- Hỗ trợ event thường và event E2EE trong cùng listener.

### 🤖 Bot mẫu `src/main.py` viết lại theo lifecycle async

- Đọc config local từ `src/config.json`.
- Gọi `await dataGetHome(...)` và validate field bắt buộc trước khi chạy bot.
- Dùng một `httpx.AsyncClient` chung cho command HTTP.
- Chờ E2EE handshake sẵn sàng trước khi xử lý lệnh.
- Reply bằng E2EE khi có `chatJid`, fallback gửi thường khi chỉ có `threadId`.
- Shutdown listener và HTTP client rõ ràng khi Ctrl+C.

### 📎 Upload attachment được cứng hơn

- Parser upload không còn crash khi Facebook trả `payload: null`.
- `include_error=True` trả lỗi có cấu trúc để debug cookie, file hoặc endpoint.
- Kết quả upload ưu tiên `attachmentID` và `typeAttachment` để truyền thẳng qua `_send`.

### 🔑 Login FB4A và 2FA được gom lại

- Giữ default FB4A `apiKey` và `appAccessToken` trong code, vì đây là constant mặc định của app Facebook.
- Cho phép override qua config/env khi thật sự cần.
- Luồng 2FA vẫn giữ password gốc khi gửi request xác minh.
- Login credential là compatibility boundary và vẫn không nên chạy trong event loop nóng.

### 📚 Tài liệu được đồng bộ lại

- `README.md` và `README_EN.md` viết lại cho v2.2.0.
- `DOCS.md` bổ sung workflow async, httpx, upload, listener, E2EE, bot lifecycle và migration.
- README từng module trong `src/_core`, `src/_features`, `src/_messaging` được cập nhật theo API async.
- `bridge-e2ee/README.md` mô tả build bridge, submodule `meta`, binary discovery và biến `FBCHAT_E2EE_BIN`.

---

## 💥 Breaking Changes

### API cần `await`

Code blocking cũ kiểu:

```python
result = _notification.func(dataFB)
```

phải đổi thành:

```python
result = await _notification.func(dataFB)
```

Trong file CLI, đặt `asyncio.run(main())` ở entry point. Trong FastAPI, Jupyter hoặc bot framework đã có event loop, gọi `await` trực tiếp và không lồng thêm `asyncio.run()`.

### Không còn alias `func_async` / `func_sync`

Public API thống nhất về `func(...)`. Nếu project cũ đang import `func_async`, đổi sang `func` và thêm `await` ở call site.

### `requests` không còn là transport chính

`httpx` là runtime chính cho session và API async. `requests` chỉ còn ở một số boundary legacy như credential login hoặc compatibility upload khi caller không inject async client.

### E2EE nên gửi qua listener hoặc `BridgeActions`

Ứng dụng async mới nên dùng:

```python
await listener.send_e2ee_message(chat_jid, text)
```

hoặc `BridgeActions` khi cần edit, unsend, typing, mark-read, gửi media hoặc download media. `_send_e2ee.api` chỉ còn phù hợp cho integration blocking/compatibility.

---

## 🚦 Quick Start

### 1. Cài Python package

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

### 2. Expose `src/`

```powershell
$env:PYTHONPATH = "src"
```

```bash
export PYTHONPATH=src
```

### 3. Tạo config local

```powershell
Copy-Item src\config.example.json src\config.json
```

```bash
cp src/config.example.json src/config.json
```

Dán cookie Facebook thật vào `src/config.json`. File này đã bị gitignore, không commit cookie.

### 4. Chạy bot mẫu

```bash
python src/main.py
```

Bot mẫu hỗ trợ các lệnh cơ bản như:

```text
/ping
/help
/id
/echo xin chào
/search Minh
/unsend
```

---

## 🔐 E2EE Setup

Tin nhắn cá nhân Messenger hiện dùng E2EE, nên listener 1-1 cần bridge Go.

### Windows

```powershell
git submodule update --init --recursive bridge-e2ee/meta
Set-Location bridge-e2ee
go mod download
New-Item -ItemType Directory -Force ..\build | Out-Null
go build -ldflags="-s -w" -o ..\build\fbchat-bridge-e2ee.exe .
```

### Linux / macOS

```bash
git submodule update --init --recursive bridge-e2ee/meta
cd bridge-e2ee
go mod download
mkdir -p ../build
go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee .
```

Nếu binary nằm ngoài path mặc định, set biến môi trường:

```powershell
$env:FBCHAT_E2EE_BIN = "C:\path\to\fbchat-bridge-e2ee.exe"
```

```bash
export FBCHAT_E2EE_BIN=/path/to/fbchat-bridge-e2ee
```

---

## 🔧 Nâng cấp từ v2.1.4

1. Cập nhật code:

   ```bash
   git pull
   python -m pip install -e .
   ```

2. Đổi call site sang `await`.

3. Đổi import/call `func_async` hoặc `func_sync` về `func`.

4. Nếu dùng nhiều API HTTP trong một flow, tạo một `httpx.AsyncClient` và truyền `client=client`.

5. Nếu dùng E2EE, build lại bridge và kiểm tra `bridge-e2ee/meta` đã được init bằng submodule.

---

## ✅ Kiểm tra chất lượng

Các gate nên chạy trước khi release:

```bash
pytest tests/ -v --tb=short
python -m compileall -q src tests
git diff --check
```

Với bridge:

```bash
cd bridge-e2ee
go test ./...
go vet ./...
```

---

## 🐛 Known Issues

- Đây không phải SDK chính thức của Facebook. Cookie, token và `dataFB` phải được xem như secret.
- Facebook có thể đổi HTML/token/endpoint bất cứ lúc nào, nhất là login và upload.
- E2EE phụ thuộc bridge Go, submodule `bridge-e2ee/meta`, binary đúng kiến trúc và kết nối tới hạ tầng Messenger.
- Trên một số mạng, kết nối tới `edge-chat.facebook.com` có thể bị throttle hoặc chặn.
- `src/config.json` là file local, không commit. Hãy dùng `src/config.example.json` làm template.

---

## 🔗 Liên kết

- 📖 README: [README.md](../README.md)
- 🌐 README English: [README_EN.md](../README_EN.md)
- 📚 Docs: [DOCS.md](../DOCS.md)
- 📊 Flowchart: [FLOWCHART.md](../FLOWCHART.md)
- 🧩 Messaging docs: [src/_messaging/README.md](../src/_messaging/README.md)
- 🌉 Bridge docs: [bridge-e2ee/README.md](../bridge-e2ee/README.md)
- 📋 Changelog: [CHANGELOG.md](../CHANGELOG.md)
- 🐛 Báo lỗi: <https://github.com/MinhHuyDev/fbchat-v2/issues>
- 💬 Telegram: <https://t.me/MinhHuyDev>

Full Changelog: <https://github.com/MinhHuyDev/fbchat-v2/compare/v2.1.4...v2.2.0>

---

<div align="center">

📥 Tải về: [Source code (zip)](https://github.com/MinhHuyDev/fbchat-v2/archive/refs/tags/v2.2.0.zip) · [Source code (tar.gz)](https://github.com/MinhHuyDev/fbchat-v2/archive/refs/tags/v2.2.0.tar.gz)

💬 Hỏi đáp & báo lỗi: [GitHub Issues](https://github.com/MinhHuyDev/fbchat-v2/issues) · [Telegram @MinhHuyDev](https://t.me/MinhHuyDev)

</div>
