<div align="center">

# FBChat-Remake — Mã nguồn mở

### Thư viện Python hiện đại cho Facebook Messenger API (không chính thức), hoạt động trên tài khoản người dùng

[![Status](https://img.shields.io/badge/status-active-22c55e)](https://github.com/MinhHuyDev/fbchat-v2)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-2.x-blue)](https://github.com/MinhHuyDev/fbchat-v2/releases)
[![Issues](https://img.shields.io/github/issues/MinhHuyDev/fbchat-v2?color=orange)](https://github.com/MinhHuyDev/fbchat-v2/issues)
[![License](https://img.shields.io/badge/license-Xem%20LICENSE-lightgrey)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-MinhHuyDev-26A5E4?logo=telegram&logoColor=white)](https://t.me/MinhHuyDev)

[**🇬🇧 English**](README_EN.md) · [**📖 Tài liệu**](DOCS.md) · [**📊 Sơ đồ luồng**](FLOWCHART.md) · [**🐛 Báo lỗi**](https://github.com/MinhHuyDev/fbchat-v2/issues)

</div>

---

## 📢 Thông báo quan trọng

> Kể từ **tháng 11/2024**, Facebook đã chính thức triển khai **mã hoá đầu cuối (End-to-End Encryption — E2EE)** cho mọi cuộc trò chuyện giữa người dùng với người dùng trên Messenger. Vì vậy, hiện tại thư viện **chỉ lấy được tin nhắn nhóm**; tin nhắn cá nhân (1–1) không còn truy cập được qua các endpoint công khai như trước.
>
> **Tin tốt:** tính đến **24/03/2026**, mình đã giải mã thành công luồng E2EE của Messenger. Tính năng đọc tin nhắn cá nhân E2EE sẽ được tích hợp vào `fbchat-v2` trong bản cập nhật sắp tới.

> ⚠️ **Tuyên bố miễn trừ** — Đây **không** phải là sản phẩm chính thức của Facebook. Facebook đã có sẵn API chatbot chính thức [tại đây](https://developers.facebook.com/docs/messenger-platform/). `fbchat-v2` khác biệt ở chỗ nó xác thực bằng **tài khoản / cookie người dùng Facebook thực**, vốn tiềm ẩn rủi ro. Hãy cân nhắc kỹ trước khi sử dụng.

---

## 👋 Giới thiệu

Xin chào, mình là **MinhHuyDev** / **raintee.dev** — tác giả và người duy trì dự án này.

Trước hết, mình xin chân thành cảm ơn tất cả người dùng trong và ngoài nước đã đóng góp ý tưởng và báo lỗi cho dự án. Trong **bản cập nhật lớn v2.x** này, codebase đã được **tái cấu trúc hoàn toàn**, xử lý phần lớn các lỗi nhỏ tồn đọng và đặt nền móng cho những tính năng sắp tới như **E2EE** và **`async`/`await`** đầy đủ.

Tất nhiên vẫn sẽ còn những lỗi vặt khó tìm ra, hoặc các đoạn code chưa thật sự đồng bộ. Nếu bạn phát hiện ra ***vấn đề***, hãy mở issue trên [GitHub](https://github.com/MinhHuyDev/fbchat-v2/issues) hoặc nhắn trực tiếp cho mình qua [Telegram](https://t.me/MinhHuyDev).

---

## 📑 Mục lục

- [Tính năng](#-tính-năng)
- [Kiến trúc tổng quan](#-kiến-trúc-tổng-quan)
- [Cấu trúc dự án](#-cấu-trúc-dự-án)
- [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
- [Cài đặt](#-cài-đặt)
- [Bắt đầu nhanh](#-bắt-đầu-nhanh)
- [Cấu hình](#-cấu-hình)
- [Tài liệu từng module](#-tài-liệu-từng-module)
- [Lộ trình phát triển](#-lộ-trình-phát-triển)
- [Đóng góp](#-đóng-góp)
- [Vinh danh người đóng góp](#-vinh-danh-người-đóng-góp)
- [Bản quyền](#-bản-quyền)

---

## ✨ Tính năng

`fbchat-v2` đi theo một hướng hoàn toàn khác so với SDK chính thức: thay vì chỉ chạy trên một fanpage với `access_token`, thư viện điều khiển một **tài khoản Facebook thật** thông qua cookie hoặc thông tin đăng nhập, mở khoá toàn bộ bề mặt của Messenger.

### Xác thực
- 🔐 Đăng nhập bằng **username / password** hoặc **cookie phiên** (*)
- 🍪 Tái sử dụng phiên đăng nhập — không cần đăng nhập lại mỗi lần chạy

### Nhắn tin
- 📥 Đọc tin nhắn từ cả **người dùng** lẫn **nhóm chat (thread)**
- 📤 Gửi văn bản, **tệp đính kèm**, **nhãn dán (sticker)**, **mention người dùng**
- 🔍 Tìm kiếm tin nhắn và chuỗi hội thoại
- ↩️ Thả cảm xúc, thu hồi tin, xử lý message requests
- 📡 **Listener real-time** — phản hồi lệnh người dùng tức thì

### Thread & Nhóm
- 👥 Tạo nhóm, thêm admin, đổi tên / emoji / biệt danh trong nhóm
- 📊 Tạo cuộc thăm dò ý kiến (poll) và lấy toàn bộ metadata của thread

### Tính năng Facebook (`_features._facebook`)
- 📝 Đăng bài, đổi tiểu sử, đăng ký mục trên hồ sơ
- 👤 Tìm kiếm người dùng, lấy thông tin profile, quản lý thông báo
- 🚫 Chặn / bỏ chặn, quản lý Marketplace và chế độ Professional

### Sắp ra mắt
- ⚡ Hỗ trợ **`async` / `await`** đầy đủ
- 🔓 Giải mã **E2EE** Messenger cho tin nhắn cá nhân

> (*) Đăng nhập bằng cookie / mật khẩu mang theo rủi ro bảo mật; tuyệt đối không chia sẻ token của bạn cho ai.

---

## 🏗 Kiến trúc tổng quan

Codebase được chia thành **3 tầng rõ ràng**:

| Tầng | Đường dẫn | Trách nhiệm |
|---|---|---|
| **Core** | `src/_core/` | Quản lý phiên (session), đăng nhập, request helper, tiện ích cấp thấp |
| **Features** | `src/_features/` | Nghiệp vụ Facebook & thread (đăng bài, nhóm, hồ sơ, …) |
| **Messaging** | `src/_messaging/` | Gửi / nhận / react / lắng nghe / thu hồi — mọi thứ liên quan đến nhắn tin |

```mermaid
flowchart LR
    A[main.py] --> B[_core<br/>session • login • utils]
    B --> C[_features<br/>facebook • thread]
    B --> D[_messaging<br/>send • listen • reactions]
    C --> E[(Facebook<br/>endpoints nội bộ)]
    D --> E
```

📊 Sơ đồ luồng đầy đủ có tại [FLOWCHART.md](FLOWCHART.md).

---

## 📂 Cấu trúc dự án

```text
fbchat-v2/
├── src/
│   ├── main.py                          # Bot mẫu — entry point
│   ├── config.json                      # Cookie + cấu hình runtime
│   ├── _core/                           # ── Tầng nền tảng ──
│   │   ├── _facebookLogin.py
│   │   ├── _session.py
│   │   └── _utils.py
│   ├── _features/                       # ── Tầng tính năng ──
│   │   ├── _facebook/
│   │   │   ├── _blocking.py
│   │   │   ├── _changeBio.py
│   │   │   ├── _createPost.py
│   │   │   ├── _get_user_info.py
│   │   │   ├── _marketplace.py
│   │   │   ├── _notification.py
│   │   │   ├── _professional.py
│   │   │   ├── _registerOnProfile.py
│   │   │   └── _search.py
│   │   └── _thread/
│   │       ├── _addAdmin.py
│   │       ├── _all_thread_data.py
│   │       ├── _changeEmoji.py
│   │       ├── _changeNameThread.py
│   │       └── _changeNickname.py
│   └── _messaging/                      # ── Tầng nhắn tin ──
│       ├── _attachments.py
│       ├── _listening.py
│       ├── _message_requests.py
│       ├── _reactions.py
│       ├── _send.py
│       └── _unsend.py
├── language/
│   └── vi_VN.lang                       # Ngôn ngữ
├── docs/                                # Tài liệu mở rộng
├── DOCS.md
├── FLOWCHART.md
├── CODE_OF_CONDUCT.md
├── LICENSE
└── requirements.txt
```

Mỗi thư mục con đều có sẵn `README.md` (tiếng Việt) và `README_EN.md` (tiếng Anh) mô tả chi tiết từng module.

### Mindmap toàn dự án

```mermaid
mindmap
  root((fbchat-v2))
    Tài liệu gốc
      README.md
      README_EN.md
      DOCS.md
      FLOWCHART.md
      CODE_OF_CONDUCT.md
      LICENSE
      requirements.txt
    Mã nguồn (src)
      main.py
      config.json
      _core
        _facebookLogin.py
        _session.py
        _utils.py
      _features
        _facebook
          _blocking.py
          _changeBio.py
          _createPost.py
          _get_user_info.py
          _marketplace.py
          _notification.py
          _professional.py
          _registerOnProfile.py
          _search.py
        _thread
          _addAdmin.py
          _all_thread_data.py
          _changeEmoji.py
          _changeNameThread.py
          _changeNickname.py
      _messaging
        _attachments.py
        _listening.py
        _message_requests.py
        _reactions.py
        _send.py
        _unsend.py
    Ngôn ngữ
      language/vi_VN.lang
    Môi trường
      .venv
      .git
```

---

## 🔧 Yêu cầu hệ thống

| Thành phần | Tối thiểu | Khuyến nghị |
|---|---|---|
| Python | 3.10 | 3.11 / 3.12 |
| Hệ điều hành | Windows / Linux / macOS | — |
| Mạng | Kết nối ổn định, không bị chặn `facebook.com` | — |

Các phụ thuộc được khai báo trong [requirements.txt](requirements.txt).

---

## 📦 Cài đặt

### 1. Clone mã nguồn

```bash
git clone https://github.com/MinhHuyDev/fbchat-v2
cd fbchat-v2
```

> Cách khác: `Code → Download ZIP` trên GitHub.

### 2. Tạo môi trường ảo *(không bắt buộc nhưng khuyến nghị)*

```bash
python -m venv .venv
```

Kích hoạt môi trường:

```bash
# Windows (PowerShell)
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Cài đặt phụ thuộc

```bash
pip install -r requirements.txt
```

### 4. Cho phép import từ `src/`

Khi chạy script ở thư mục gốc dự án, hãy expose `src/` để các module `_core`, `_features`, `_messaging` được import đúng:

```bash
# Windows (PowerShell)
$env:PYTHONPATH = "src"

# macOS / Linux
export PYTHONPATH=src
```

Hoặc bạn có thể import thủ công với prefix đầy đủ `src.`.

---

## 🚀 Bắt đầu nhanh

Một bot demo tối giản đã có sẵn tại [`src/main.py`](src/main.py). File này chứa vài lệnh cơ bản để bạn kiểm tra cài đặt và dùng làm khung mẫu cho bot riêng của mình.

```bash
python src/main.py
```

Trước khi chạy:

1. Mở `src/config.json`.
2. Dán **cookies** Facebook của bạn vào trường `cookies`.
3. (Tuỳ chọn) chỉnh các tham số runtime khác trong file.

---

## ⚙️ Cấu hình

`src/config.json` là nguồn duy nhất cho mọi cấu hình runtime.

| Khoá | Mô tả |
|---|---|
| `cookies` | Cookie phiên Facebook của bạn (chuỗi hoặc object). **Bắt buộc.** |
| `…` | Các trường khác được mô tả ngay trong file và trong [DOCS.md](DOCS.md). |

> 🔒 **Bảo mật:** Hãy coi `config.json` như một file bí mật. Tuyệt đối không commit lên repo công khai, không chia sẻ cookie cho người khác, và đổi cookie ngay nếu nghi ngờ bị lộ.

---

## 📚 Tài liệu từng module

Mỗi tầng đều có README riêng. Hãy bắt đầu từ đó để xem ví dụ API chi tiết:

| Module | Tiếng Việt | English |
|---|---|---|
| `_core` | `src/_core/README.md` | `src/_core/README_EN.md` |
| `_features` | `src/_features/README.md` | `src/_features/README_EN.md` |
| `_messaging` | `src/_messaging/README.md` | `src/_messaging/README_EN.md` |
| Ngôn ngữ | `language/README.md` | — |

Để hiểu thiết kế tổng thể và luồng request đầu-cuối, xem [DOCS.md](DOCS.md) và [FLOWCHART.md](FLOWCHART.md).

---

## 🗺 Lộ trình phát triển

- [ ] API native `async` / `await`
- [ ] Giải mã **E2EE** tin nhắn cá nhân Messenger (đã prototype xong)
- [ ] Bổ sung type hints cho toàn bộ public API
- [ ] Storage backend cắm-rút (pluggable) cho session
- [ ] Bổ sung integration test & CI

Có ý tưởng? Chia sẻ ngay tại [Issues](https://github.com/MinhHuyDev/fbchat-v2/issues).

---

## 🤝 Đóng góp

Mọi đóng góp đều được hoan nghênh.

1. **Fork** repo và tạo nhánh tính năng:
   ```bash
   git checkout -b feat/<ten-tinh-nang>
   ```
2. Tuân thủ coding style hiện tại và kiến trúc 3 tầng (`_core` → `_features` / `_messaging`).
3. Dùng [Conventional Commits](https://www.conventionalcommits.org/) — ví dụ: `feat:`, `fix:`, `docs:`, `refactor:`.
4. Mở Pull Request với mô tả rõ ràng, các bước reproduce (với bug fix), kèm screenshot/log nếu cần.
5. **Tuyệt đối không** commit thông tin nhạy cảm — `config.json`, cookie, token, `.venv`, …

Vui lòng đọc [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) trước khi tham gia.

---

## 🌟 Vinh danh người đóng góp

Sau **4 năm** phát triển, dự án sẽ không thể tồn tại nếu thiếu cộng đồng. Cảm ơn từ tận đáy lòng tới mọi người đã đóng góp ý tưởng, báo lỗi và giữ cho `fbchat` còn sống tới ngày hôm nay:

- [tomdev112](https://github.com/tomdev211)
- [syrex1013](https://github.com/syrex1013)
- [Kheir Eddine](https://www.facebook.com/61557637127396/)
- 陶世玉
- Jihadi John
- [Bắc Trịnh](https://www.facebook.com/1228855777/)
- [Quang Trần](https://www.facebook.com/100005048402622/)
- [Minh Trần Ngọc](https://www.facebook.com/100000277273223/)
- Victor Knutsenberger
- [Hoàng Lân](https://www.facebook.com/100026754347158/)
- Kareem Adel Abomandor
- @lluevy · @phuncnheo · @minhphatnw · @khanh235a · @chapesh1 · @klongg13 · @seafibrahem · @agent1047 · @stefekdziura
- *Claude Opus 4.7* / *Codex 5.3*

> Nếu bạn đã từng đóng góp mà chưa thấy tên ở đây, hãy mở issue hoặc PR — mình rất vinh hạnh được bổ sung bạn vào danh sách.

---

## 📜 Bản quyền

Dự án được phân phối theo các điều khoản trong [LICENSE](LICENSE). Vui lòng đọc kỹ trước khi sử dụng cho mục đích production hoặc thương mại.

---

<div align="center">

**Được làm với ❤️ bởi [MinhHuyDev](https://github.com/MinhHuyDev) · [Telegram](https://t.me/MinhHuyDev)**

</div>
