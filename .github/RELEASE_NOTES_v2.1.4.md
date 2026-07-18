### 🎉 Cập nhật quan trọng: Đóng gói hiện đại & Tự động tải E2EE Bridge

> Tài liệu lịch sử của v2.1.4. Cách dùng hiện hành nằm trong [`README.md`](../README.md) và [`DOCS.md`](../DOCS.md), ưu tiên async/await.

Bản phát hành `v2.1.4` mang đến những cải tiến lớn về trải nghiệm cài đặt và tự động hóa cho cả Dev và User.

#### 🚀 Tính năng mới (Features)
- Tự động tải E2EE Bridge: Khi path mặc định chưa có binary, wrapper xác định hệ điều hành và kiến trúc để tìm asset phù hợp trên GitHub Releases. Nếu không có asset, kiến trúc không hỗ trợ hoặc caller đã đặt path override sai, module trả lỗi rõ ràng và yêu cầu build thủ công.

#### 🛠 Nâng cấp hệ thống (Build & CI)
- Chào `pyproject.toml`, tạm biệt `requirements.txt`: Cấu trúc project đã được quy hoạch lại theo chuẩn PEP 621. Giờ đây việc cài đặt chỉ đơn giản là `pip install -e .`
- Sửa luồng CI/CD: Cập nhật lại `.github/workflows/ci.yml` để cài đặt dependencies qua `pyproject.toml` thay vì file cũ, đảm bảo CI không bị chạy mù.

#### 📝 Tài liệu (Documentation)
- Quét dọn toàn bộ các tài liệu (README, DOCS, CLAUDE, FLOWCHART...) để phản ánh cách cài đặt mới thông qua `pyproject.toml`.

> 💡 Dành cho User E2EE:
> Auto-download phụ thuộc asset release, mạng và kiến trúc. Production nên pin `FBCHAT_E2EE_BIN` tới binary đã xác minh; xem [`bridge-e2ee/README.md`](../bridge-e2ee/README.md) để build và kiểm tra bảo mật.
