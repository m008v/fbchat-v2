### fbchat-v2 v2.1.4 - Đóng gói và tự tải E2EE bridge

> Đây là ghi chú phát hành của v2.1.4. Khi dùng phiên bản mới, xem [`README.md`](../README.md) và [`DOCS.md`](../DOCS.md) để biết API async hiện hành.

`v2.1.4` chuyển cấu hình đóng gói sang `pyproject.toml` và thêm cơ chế tải E2EE bridge khi máy chưa có binary.

#### 🚀 Tính năng mới (Features)
- Khi đường dẫn mặc định chưa có binary, wrapper tìm asset trên GitHub Releases theo hệ điều hành và kiến trúc. Nếu không có asset phù hợp hoặc đường dẫn override sai, module trả lỗi để người dùng kiểm tra cấu hình hoặc tự build.

#### 🛠 Nâng cấp hệ thống (Build & CI)
- Chuyển metadata và dependency sang `pyproject.toml` theo PEP 621; hỗ trợ cài editable bằng `pip install -e .`.
- Cập nhật `.github/workflows/ci.yml` để cài dependency từ `pyproject.toml`.

#### 📝 Tài liệu (Documentation)
- Cập nhật README, DOCS, CLAUDE và FLOWCHART theo cách cài đặt qua `pyproject.toml`.

> Với E2EE, auto-download còn phụ thuộc asset của release, mạng và kiến trúc máy. Production nên đặt `FBCHAT_E2EE_BIN` tới binary đã xác minh; xem [`bridge-e2ee/README.md`](../bridge-e2ee/README.md) để biết cách build và kiểm tra.
