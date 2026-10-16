## fbchat-v2 v2.1.1 - Phân phối qua PyPI

> Đây là ghi chú phát hành của v2.1.1. Khi dùng phiên bản mới, xem [`README.md`](../README.md) và [`DOCS.md`](../DOCS.md) để biết API async hiện hành.

> Bản vá này cập nhật tài liệu và cách phân phối, không thay đổi runtime hoặc API.
> Từ v2.1.1, có thể cài trực tiếp qua PyPI:
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

- Gói `fbchat-v2` được phát hành trên Python Package Index.
- Badge `pypi/v` hiển thị phiên bản PyPI ở đầu cả `README.md` và `README_EN.md`,
  kèm nút PyPI trong dải nav và trong hero của website.
- Thêm phần hướng dẫn E2EE trên website (`#guide-e2ee`):
  - Liên kết sidebar "E2EE · Mã hoá / Encryption" (Chương II).
  - File-tree `_messaging/` thêm `_listening_e2ee.py`.
  - Module card `listeningE2EEEvent(dataFB)` với code mẫu `@on_message`
    + `send_e2ee_message`.
  - Hướng dẫn song ngữ VI/EN: kiến trúc, lệnh build bridge Go,
    bảng 8 loại event, persist `device_path`, FAQ.
- `CLAUDE.md` được sắp xếp lại để Claude, Codex và Copilot tra cứu:
  TL;DR ở đầu file, bảng *Quick reference*, bảng *Common gotchas*
  (đã liệt kê các bug `@attr.s` override `__init__`, `EventBuffer` thiếu
  method, `BridgeError binary not found`…), tách rõ phần bridge Go.

### 🛠 Changed

- Cảnh báo E2EE trên trang chủ website đổi từ `alert--danger` ("bypass đang
  chuẩn bị phát hành") -> `alert--success` "E2EE READY" với link nội bộ
  trỏ thẳng tới section `#guide-e2ee`.
- Dải điều hướng của hai README đặt link PyPI ngay sau link đổi ngôn ngữ.

### 🔧 Fixed

- _Không có thay đổi mã nguồn Python / Go._

### 📦 Dependencies

- _Không thay đổi._

---

### ⚠️ Lưu ý nâng cấp từ 2.1.0

Không có breaking change. Nâng cấp bằng:

```bash
pip install --upgrade fbchat-v2
```

Người dùng E2EE (`_listening_e2ee.py`) vẫn cần bridge Go - xem
[hướng dẫn build và binary discovery](../bridge-e2ee/README.md#build-từ-source).

---

### 🔗 Liên kết

- 📦 PyPI: https://pypi.org/project/fbchat-v2/
- 📖 Docs: [DOCS.md](../DOCS.md)
- 📊 Flowchart: [FLOWCHART.md](../FLOWCHART.md)
- 📋 Changelog: [CHANGELOG.md](../CHANGELOG.md)
- 🐛 Báo lỗi: https://github.com/m008v/fbchat-v2/issues
- 💬 Telegram: https://t.me/MinhHuyDev

Full Changelog: https://github.com/m008v/fbchat-v2/compare/v2.1.0...v2.1.1
