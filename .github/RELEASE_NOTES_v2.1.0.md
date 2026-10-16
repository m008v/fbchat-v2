# fbchat-v2 v2.1.0 - Listener E2EE cho Messenger

> Đây là ghi chú phát hành của v2.1.0. Ví dụ bên dưới đã được chuyển sang API async ở lần cập nhật tài liệu sau đó. Khi dùng phiên bản mới, xem [`README.md`](../README.md) và [`DOCS.md`](../DOCS.md).

> *Release date: 2026-05-12*

> *Codename: Labyrinth*

> *Author: MinhHuyDev*

`v2.1.0` thêm listener cho tin nhắn Messenger 1-1 dùng E2EE. Listener giữ schema event của `_listening.py` để ứng dụng có thể dùng lại phần xử lý tin nhắn. Phần giải mã chạy qua bridge Go, cần được build và cấu hình riêng.

---

## ✨ Highlight

### 🔓 E2EE Listener cho tin nhắn 1-1
- Class mới [`listeningE2EEEvent`](../src/_messaging/_listening_e2ee.py) - listener bridge cho event thường và E2EE.
- Cung cấp `bodyResults` theo schema của `_listening.py` cũ (`body`, `timestamp`, `userID`, `messageID`, `replyToID`, `type`, `attachments.id`, `attachments.url`).
- Thêm `e2eeBodyResults` để lấy metadata Signal (`chatJid`, `senderJid`).
- Tự suy luận `type = "user" / "thread"`, giữ cách phân biệt tin cá nhân và tin nhóm của listener cũ.

### 🌉 Bridge Go độc lập (`bridge-e2ee/`)
- Binary Go single-file (`fbchat-bridge-e2ee[.exe]`, ~25-40 MB) đóng gói:
  - Signal Protocol (Curve25519, Double Ratchet, Sender Keys, AES-GCM, HKDF, Noise XX) qua `whatsmeow`.
  - Meta Labyrinth / Lightspeed qua `mautrix-meta`.
- Giao tiếp Python ↔ Go bằng JSON-RPC line-delimited trên stdin/stdout.
- Chạy ở subprocess riêng để tách lỗi process của bridge khỏi Python.
- Có thể đặt đường dẫn binary qua biến môi trường `FBCHAT_E2EE_BIN`.

### 📚 Tài liệu cài đặt từ đầu đến cuối
- README gốc (VI + EN) chia phần cài đặt thành 7 bước, kèm:
  - Bảng yêu cầu mở rộng (Python / Go / Git / RAM / Network).
  - Sanity check `python -c "import httpx, paho.mqtt.client, pyotp; print('OK')"`.
  - Smoke test `python src/main.py`.
- README `_messaging` có mục Cài đặt riêng + Module Reference cho `_listening_e2ee.py`.
- README `bridge-e2ee/` mô tả RPC contract.

---

## 🎯 Vì sao bản update này quan trọng

| Trước v2.1.0 | Từ v2.1.0 |
|---|---|
| Chỉ đọc được tin nhắn nhóm | Đọc cả tin nhắn nhóm + tin nhắn 1-1 (E2EE) |
| `type` chỉ có giá trị legacy | Vẫn `"user" / "thread"` - không breaking |
| Chưa có hướng dẫn build native dependency | Có hướng dẫn cài Go và build bridge |
| Bridge prototype dùng DLL/ctypes chung process | Bridge dùng JSON-RPC trong subprocess riêng |

---

## 🚦 Quick Start (E2EE)

```powershell
# 1. Build bridge một lần trên Windows
Set-Location fbchat-v2
git submodule update --init --recursive bridge-e2ee/meta
Set-Location bridge-e2ee
go mod download
New-Item -ItemType Directory -Force ..\build | Out-Null
go build -ldflags="-s -w" -o ..\build\fbchat-bridge-e2ee.exe .
```

```bash
# Linux hoặc macOS
cd fbchat-v2
git submodule update --init --recursive bridge-e2ee/meta
cd bridge-e2ee
go mod download
mkdir -p ../build
go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee .
```

```python
# 2. Dùng API async hiện hành
import asyncio

from _messaging._listening_e2ee import listeningE2EEEvent


async def run(data_fb: dict) -> None:
    listener = listeningE2EEEvent(data_fb)
    listener.on_message(lambda event: print(event))
    task = asyncio.create_task(listener.connect_mqtt())
    try:
        ready = await asyncio.to_thread(
            listener.wait_until_connected,
            90,
            require_e2ee=True,
        )
        if not ready:
            raise TimeoutError("E2EE bridge chưa sẵn sàng.")
        await task
    finally:
        listener.stop()
        if not task.done():
            await task
```

> Nếu không dùng E2EE, vẫn có thể dùng `from _messaging._listening import listeningEvent` như trước mà không build bridge.

---

## 🔧 Nâng cấp từ 2.0.x

- Bản v2.1.0 không đổi API của code dùng `_listening.py`.
- Ghi chú build trong tài liệu này dùng Go 1.26.5 + Git. Khi build source mới, dùng Go version trong `bridge-e2ee/go.mod` và làm theo [`bridge-e2ee/README.md`](../bridge-e2ee/README.md).
- Bridge không còn phụ thuộc thư mục `meta-messenger.js/`; có thể xóa thư mục này nếu ứng dụng không dùng đến.

```powershell
git pull
python -m pip install -e .
```

---

## 📦 Yêu cầu hệ thống

| Thành phần | Tối thiểu | Khuyến nghị | Ghi chú |
|---|---|---|---|
| Python | 3.10 | 3.11 / 3.12 | Bắt buộc |
| Go | 1.26.5 | 1.26.5+ | Chỉ cần khi tự build E2EE |
| Git | bất kỳ | latest | Để clone `mautrix/meta` |
| RAM | 256 MB | 1 GB+ | Bridge ~80-150 MB khi chạy |
| OS | Windows / Linux / macOS | - | - |

---

## 🐛 Known Issues

- Asset prebuilt phụ thuộc release và hệ điều hành; production nên pin binary đã tự xác minh.
- Lần `go mod download` đầu tiên có thể tải lượng lớn Go module cache.
- Trên một số mạng VN, kết nối WebSocket tới `edge-chat.facebook.com` có thể bị throttle -> cần proxy.

---

## 📝 Changelog đầy đủ

Xem [CHANGELOG.md](../CHANGELOG.md#210---2026-05-12).

So sánh diff: [`v2.0.x...v2.1.0`](https://github.com/m008v/fbchat-v2/compare/v2.0.x...v2.1.0)

---

## 🙏 Cảm ơn

- Cộng đồng đã chờ đợi, thử nghiệm và báo lỗi khi Messenger chuyển sang E2EE.
- Dự án [`mautrix/meta`](https://github.com/mautrix/meta) và [`tulir/whatsmeow`](https://github.com/tulir/whatsmeow), được dùng cho kết nối Meta và Signal Protocol.
- Dự án [`yumi-team/meta-messenger.js`](https://github.com/yumi-team/meta-messenger.js) - tham chiếu thiết kế bridge.
- Tất cả contributor và upstream được liệt kê ở [README - Vinh danh](../README.md#vinh-danh).

---

<div align="center">

📥 Tải về: [Source code (zip)](https://github.com/m008v/fbchat-v2/archive/refs/tags/v2.1.0.zip) · [Source code (tar.gz)](https://github.com/m008v/fbchat-v2/archive/refs/tags/v2.1.0.tar.gz)

💬 Hỏi đáp & báo lỗi: [GitHub Issues](https://github.com/m008v/fbchat-v2/issues) · [Telegram @MinhHuyDev](https://t.me/MinhHuyDev)

*Made with ❤️ by [MinhHuyDev](https://github.com/MinhHuyDev)*

</div>
