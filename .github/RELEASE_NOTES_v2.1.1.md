## 🎉 fbchat-v2 đã có trên PyPI!

> **Bản vá tài liệu & hạ tầng phân phối.** Không thay đổi runtime — không breaking change.
> Từ phiên bản này bạn có thể cài đặt trực tiếp:
>
> ```bash
> pip install fbchat-v2
> # hoặc nâng cấp
> pip install --upgrade fbchat-v2
> ```
>
> 🔗 https://pypi.org/project/fbchat-v2/

---

### ✨ Added

- 📦 **PyPI publish** — gói `fbchat-v2` đã chính thức lên Python Package Index.
- 🏷 **Badge `pypi/v` (live version)** ở đầu cả `README.md` và `README_EN.md`,
  kèm nút **PyPI** trong dải nav và trong hero của website.
- 🔐 **Section E2EE mới trên website** (`#guide-e2ee`):
  - Liên kết sidebar **"E2EE · Mã hoá / Encryption"** (Chương II).
  - File-tree `_messaging/` thêm `_listening_e2ee.py`.
  - Module card `listeningE2EEEvent(dataFB)` với code mẫu `@on_message`
    + `send_e2ee_message`.
  - Hướng dẫn song ngữ VI/EN: kiến trúc, lệnh build bridge Go,
    bảng 8 loại event, persist `device_path`, FAQ.
- 🤖 **`CLAUDE.md` viết lại theo hướng *agent-first*** (Claude / Codex /
  Copilot): TL;DR ở đầu file, bảng *Quick reference*, bảng *Common gotchas*
  (đã liệt kê các bug `@attr.s` override `__init__`, `EventBuffer` thiếu
  method, `BridgeError binary not found`…), tách rõ phần bridge Go.

### 🛠 Changed

- 🟢 Cảnh báo E2EE trên home website đổi từ `alert--danger` ("bypass đang
  chuẩn bị phát hành") → `alert--success` **"E2EE READY"** với link nội bộ
  trỏ thẳng tới section `#guide-e2ee`.
- 📑 Dải nav 2 README sắp xếp lại: link **PyPI** đứng ngay sau link song ngữ.

### 🔧 Fixed

- _Không có thay đổi mã nguồn Python / Go._

### 📦 Dependencies

- _Không thay đổi._

---

### ⚠️ Lưu ý nâng cấp từ 2.1.0

Không có breaking change. Chỉ cần:

```bash
pip install --upgrade fbchat-v2
```

Người dùng E2EE (`_listening_e2ee.py`) vẫn cần build bridge Go một lần như
hướng dẫn ở v2.1.0 — xem [README §Cài đặt bước 5](../README.md#5-tu%E1%BB%B3-ch%E1%BB%8Dn-build-bridge-e2ee--cho-tin-nh%E1%BA%AFn-1-1).

---

### 🔗 Liên kết

- 📦 **PyPI**: https://pypi.org/project/fbchat-v2/
- 📖 **Docs**: [DOCS.md](../DOCS.md)
- 📊 **Flowchart**: [FLOWCHART.md](../FLOWCHART.md)
- 📋 **Changelog**: [CHANGELOG.md](../CHANGELOG.md)
- 🐛 **Báo lỗi**: https://github.com/MinhHuyDev/fbchat-v2/issues
- 💬 **Telegram**: https://t.me/MinhHuyDev

**Full Changelog**: https://github.com/MinhHuyDev/fbchat-v2/compare/v2.1.0...v2.1.1
