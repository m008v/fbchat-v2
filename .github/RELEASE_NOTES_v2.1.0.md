# 🚀 fbchat-v2 v2.1.0 — Messenger E2EE đã chính thức landed!

> *Release date: 2026-05-12*

> *Codename: **Labyrinth***

> *Author: ***MinhHuyDev***

Sau **18 tháng** kể từ khi Facebook bật E2EE mặc định cho Messenger (11/2024) và làm "đứt" toàn bộ luồng đọc tin nhắn 1-1 của các thư viện account-based, hôm nay `fbchat-v2` chính thức **mở khoá lại** khả năng đó — và tất cả những gì bạn cần làm là **đổi 1 dòng import**.

---

## ✨ Highlight

### 🔓 E2EE Listener cho tin nhắn 1-1
- Class mới [`listeningE2EEEvent`](src/_messaging/_listening_e2ee.py) — drop-in replacement cho `listeningEvent`.
- Phơi `bodyResults` với **đúng schema** của `_listening.py` cũ (`body`, `timestamp`, `userID`, `messageID`, `replyToID`, `type`, `attachments.id`, `attachments.url`).
- Bonus: `e2eeBodyResults` chứa metadata Signal (`chatJid`, `senderJid`).
- Tự suy luận `type = "user" / "thread"` — code xử lý event của bạn **không cần sửa**.

### 🌉 Bridge Go độc lập (`bridge-e2ee/`)
- Binary Go single-file (`fbchat-bridge-e2ee[.exe]`, ~25–40 MB) đóng gói:
  - **Signal Protocol** (Curve25519, Double Ratchet, Sender Keys, AES-GCM, HKDF, Noise XX) qua `whatsmeow`.
  - **Meta Labyrinth / Lightspeed** qua `mautrix-meta`.
- Giao tiếp Python ↔ Go bằng **JSON-RPC line-delimited** trên stdin/stdout.
- Chạy ở **subprocess riêng** → bridge crash không kéo Python crash theo.
- Override path bằng env var `FBCHAT_E2EE_BIN`.

### 📚 Tài liệu cài đặt từ đầu đến cuối
- README gốc (VI + EN) viết lại §**Cài đặt** thành **7 bước rõ ràng**, kèm:
  - Bảng yêu cầu mở rộng (Python / Go / Git / RAM / Network).
  - Sanity check `python -c "import requests, paho.mqtt.client, attr, pyotp; print('OK')"`.
  - Smoke test `python src/main.py`.
- README `_messaging` có mục **Cài đặt riêng** + **Module Reference** cho `_listening_e2ee.py`.
- README `bridge-e2ee/` mô tả RPC contract đầy đủ.

---

## 🎯 Vì sao bản update này quan trọng

| Trước v2.1.0 | Từ v2.1.0 |
|---|---|
| Chỉ đọc được tin nhắn nhóm | Đọc cả **tin nhắn nhóm + tin nhắn 1-1 (E2EE)** |
| `type` chỉ có giá trị legacy | Vẫn `"user" / "thread"` — **không** breaking |
| Không có hướng dẫn build native dep | Hướng dẫn Go toolchain step-by-step |
| Bridge prototype DLL/ctypes (rủi ro crash) | **Subprocess JSON-RPC** an toàn, có thể đóng gói exe đơn |

---

## 🚦 Quick Start (E2EE)

```powershell
# 1. Build bridge 1 lần
cd fbchat-v2/bridge-e2ee
git clone https://github.com/mautrix/meta.git ./meta
go mod tidy
go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee.exe .   # Windows
# Linux/macOS: bỏ đuôi .exe
```

```python
# 2. Dùng y hệt _listening.py
import threading
from _messaging._listening_e2ee import listeningE2EEEvent

listener = listeningE2EEEvent(dataFB)
listener.get_last_seq_id()

@listener.on_message
def handle(evt):
    print(listener.bodyResults)        # ← cùng schema với _listening.py
    print(listener.e2eeBodyResults)    # chatJid / senderJid

threading.Thread(target=listener.connect_mqtt, daemon=True).start()
```

> 💡 Không cần build E2EE? Tiếp tục `from _messaging._listening import listeningEvent` như cũ — **không có gì thay đổi**.

---

## 🔧 Nâng cấp từ 2.0.x

- ✅ **Không có breaking change** với code đang dùng `_listening.py`.
- 🆕 Để dùng E2EE: cài Go ≥ 1.24 + Git, build binary 1 lần (xem README §Cài đặt bước 5).
- 🧹 Có thể xoá thư mục `meta-messenger.js/` (nếu còn) — bridge mới hoàn toàn độc lập.

```powershell
git pull
pip install -r requirements.txt   # không có dep Python mới, nhưng nên chạy cho chắc
```

---

## 📦 Yêu cầu hệ thống

| Thành phần | Tối thiểu | Khuyến nghị | Ghi chú |
|---|---|---|---|
| Python | 3.10 | 3.11 / 3.12 | Bắt buộc |
| Go | 1.24 | 1.24+ | Chỉ cần cho E2EE |
| Git | bất kỳ | latest | Để clone `mautrix/meta` |
| RAM | 256 MB | 1 GB+ | Bridge ~80–150 MB khi chạy |
| OS | Windows / Linux / macOS | — | — |

---

## 🐛 Known Issues

- Bridge prebuilt binary chưa có sẵn trên trang Releases — **bạn cần build local**. Đây là mục tiếp theo trên [Roadmap](README.md#-l%E1%BB%99-tr%C3%ACnh-ph%C3%A1t-tri%E1%BB%83n).
- Lần `go mod tidy` đầu tiên tải ~300 MB cache module — hãy kiên nhẫn.
- Trên một số mạng VN, kết nối WebSocket tới `edge-chat.facebook.com` có thể bị throttle → cần proxy.

---

## 📝 Changelog đầy đủ

Xem [CHANGELOG.md](CHANGELOG.md#210--2026-05-12).

**So sánh diff:** [`v2.0.x...v2.1.0`](https://github.com/MinhHuyDev/fbchat-v2/compare/v2.0.x...v2.1.0)

---

## 🙏 Cảm ơn

- Cộng đồng đã kiên nhẫn chờ đợi suốt 18 tháng kể từ khi Messenger bật E2EE.
- Dự án [`mautrix/meta`](https://github.com/mautrix/meta) và [`tulir/whatsmeow`](https://github.com/tulir/whatsmeow) — nền tảng giúp việc giải mã trở nên khả thi.
- Dự án [`yumi-team/meta-messenger.js`](https://github.com/yumi-team/meta-messenger.js) — tham chiếu thiết kế bridge.
- Tất cả contributor được liệt kê ở [README §Vinh danh người đóng góp](README.md#-vinh-danh-người-đóng-góp).

---

<div align="center">

**📥 Tải về:** [Source code (zip)](https://github.com/MinhHuyDev/fbchat-v2/archive/refs/tags/v2.1.0.zip) · [Source code (tar.gz)](https://github.com/MinhHuyDev/fbchat-v2/archive/refs/tags/v2.1.0.tar.gz)

**💬 Hỏi đáp & báo lỗi:** [GitHub Issues](https://github.com/MinhHuyDev/fbchat-v2/issues) · [Telegram @MinhHuyDev](https://t.me/MinhHuyDev)

*Made with ❤️ by [MinhHuyDev](https://github.com/MinhHuyDev)*

</div>
