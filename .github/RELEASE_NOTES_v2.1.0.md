# 🚀 fbchat-v2 v2.1.0 - Messenger E2EE đã chính thức landed!

> Tài liệu lịch sử của v2.1.0. Snippet bên dưới đã được cập nhật theo API async hiện hành để người đọc không copy nhầm code blocking cũ. Xem [`README.md`](../README.md) và [`DOCS.md`](../DOCS.md) để biết workflow đầy đủ.

> *Release date: 2026-05-12*

> *Codename: Labyrinth*

> *Author: MinhHuyDev*

Sau 18 tháng kể từ khi Facebook bật E2EE mặc định cho Messenger (11/2024) và làm "đứt" toàn bộ luồng đọc tin nhắn 1-1 của các thư viện account-based, hôm nay `fbchat-v2` chính thức mở khoá lại khả năng đó - và tất cả những gì bạn cần làm là đổi 1 dòng import.

---

## ✨ Highlight

### 🔓 E2EE Listener cho tin nhắn 1-1
- Class mới [`listeningE2EEEvent`](../src/_messaging/_listening_e2ee.py) - listener bridge cho event thường và E2EE.
- Phơi `bodyResults` với đúng schema của `_listening.py` cũ (`body`, `timestamp`, `userID`, `messageID`, `replyToID`, `type`, `attachments.id`, `attachments.url`).
- Bonus: `e2eeBodyResults` chứa metadata Signal (`chatJid`, `senderJid`).
- Tự suy luận `type = "user" / "thread"` - code xử lý event của bạn không cần sửa.

### 🌉 Bridge Go độc lập (`bridge-e2ee/`)
- Binary Go single-file (`fbchat-bridge-e2ee[.exe]`, ~25-40 MB) đóng gói:
  - Signal Protocol (Curve25519, Double Ratchet, Sender Keys, AES-GCM, HKDF, Noise XX) qua `whatsmeow`.
  - Meta Labyrinth / Lightspeed qua `mautrix-meta`.
- Giao tiếp Python ↔ Go bằng JSON-RPC line-delimited trên stdin/stdout.
- Chạy ở subprocess riêng -> bridge crash không kéo Python crash theo.
- Override path bằng env var `FBCHAT_E2EE_BIN`.

### 📚 Tài liệu cài đặt từ đầu đến cuối
- README gốc (VI + EN) viết lại §Cài đặt thành 7 bước rõ ràng, kèm:
  - Bảng yêu cầu mở rộng (Python / Go / Git / RAM / Network).
  - Sanity check `python -c "import httpx, paho.mqtt.client, pyotp; print('OK')"`.
  - Smoke test `python src/main.py`.
- README `_messaging` có mục Cài đặt riêng + Module Reference cho `_listening_e2ee.py`.
- README `bridge-e2ee/` mô tả RPC contract đầy đủ.

---

## 🎯 Vì sao bản update này quan trọng

| Trước v2.1.0 | Từ v2.1.0 |
|---|---|
| Chỉ đọc được tin nhắn nhóm | Đọc cả tin nhắn nhóm + tin nhắn 1-1 (E2EE) |
| `type` chỉ có giá trị legacy | Vẫn `"user" / "thread"` - không breaking |
| Không có hướng dẫn build native dep | Hướng dẫn Go toolchain step-by-step |
| Bridge prototype DLL/ctypes (rủi ro crash) | Subprocess JSON-RPC an toàn, có thể đóng gói exe đơn |

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

> 💡 Không cần build E2EE - Tiếp tục `from _messaging._listening import listeningEvent` như cũ - không có gì thay đổi.

---

## 🔧 Nâng cấp từ 2.0.x

- ✅ Không có breaking change với code đang dùng `_listening.py`.
- 🆕 Để build source E2EE hiện tại: cài Go 1.26.5 + Git và build binary một lần (xem [`bridge-e2ee/README.md`](../bridge-e2ee/README.md)).
- 🧹 Có thể xoá thư mục `meta-messenger.js/` (nếu còn) - bridge mới hoàn toàn độc lập.

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

So sánh diff: [`v2.0.x...v2.1.0`](https://github.com/MinhHuyDev/fbchat-v2/compare/v2.0.x...v2.1.0)

---

## 🙏 Cảm ơn

- Cộng đồng đã kiên nhẫn chờ đợi suốt 18 tháng kể từ khi Messenger bật E2EE.
- Dự án [`mautrix/meta`](https://github.com/mautrix/meta) và [`tulir/whatsmeow`](https://github.com/tulir/whatsmeow) - nền tảng giúp việc giải mã trở nên khả thi.
- Dự án [`yumi-team/meta-messenger.js`](https://github.com/yumi-team/meta-messenger.js) - tham chiếu thiết kế bridge.
- Tất cả contributor và upstream được liệt kê ở [README - Vinh danh](../README.md#vinh-danh).

---

<div align="center">

📥 Tải về: [Source code (zip)](https://github.com/MinhHuyDev/fbchat-v2/archive/refs/tags/v2.1.0.zip) · [Source code (tar.gz)](https://github.com/MinhHuyDev/fbchat-v2/archive/refs/tags/v2.1.0.tar.gz)

💬 Hỏi đáp & báo lỗi: [GitHub Issues](https://github.com/MinhHuyDev/fbchat-v2/issues) · [Telegram @MinhHuyDev](https://t.me/MinhHuyDev)

*Made with ❤️ by [MinhHuyDev](https://github.com/MinhHuyDev)*

</div>
