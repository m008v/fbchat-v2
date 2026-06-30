### 🎉 Cập nhật quan trọng: Đóng gói hiện đại & Tự động tải E2EE Bridge

Bản phát hành `v2.1.4` mang đến những cải tiến lớn về trải nghiệm cài đặt và tự động hóa cho cả Dev và User.

#### 🚀 Tính năng mới (Features)
- **Tự động tải E2EE Bridge**: Khi user gọi module E2EE (nhắn tin riêng 1-1) mà máy chưa có sẵn file nhị phân Go (bridge), `fbchat-v2` sẽ tự động xác định Hệ điều hành (Windows/Linux/macOS) và Kiến trúc CPU (amd64/arm64) để kéo thẳng file tương ứng từ bản Release mới nhất về máy và cấp quyền thực thi tự động. Tạm biệt chuỗi ngày phải tự gõ `go build`!

#### 🛠 Nâng cấp hệ thống (Build & CI)
- **Chào `pyproject.toml`, tạm biệt `requirements.txt`**: Cấu trúc project đã được quy hoạch lại theo chuẩn PEP 621. Giờ đây việc cài đặt chỉ đơn giản là `pip install -e .`
- **Sửa luồng CI/CD**: Cập nhật lại `.github/workflows/ci.yml` để cài đặt dependencies qua `pyproject.toml` thay vì file cũ, đảm bảo CI không bị chạy mù.

#### 📝 Tài liệu (Documentation)
- Quét dọn toàn bộ các tài liệu (README, DOCS, CLAUDE, FLOWCHART...) để phản ánh cách cài đặt mới thông qua `pyproject.toml`.

> **💡 Dành cho User E2EE:**
> Kể từ bản cập nhật này, bạn chỉ cần `pip install fbchat-v2` và chạy code. Mọi thứ liên quan đến file Bridge Go sẽ được thư viện tự động lo liệu phía sau hậu trường trong vòng 3 giây!
