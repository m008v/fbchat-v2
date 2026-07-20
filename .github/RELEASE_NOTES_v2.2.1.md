# 🚀 Release Notes - V2.2.1

Bản cập nhật V2.2.1 bổ sung thêm các tính năng quản lý bài viết trên Timeline Facebook. Giờ đây bạn có thể dọn dẹp profile dễ dàng thông qua GraphQL API nội bộ thay vì phải xoá tay.

## ✨ Tính năng mới (New Features)

### 1. Xoá bài viết vào thùng rác (`_deletePost.py`)
- Hỗ trợ di chuyển các bài viết trên dòng thời gian (Timeline) vào thùng rác an toàn thông qua GraphQL mutation `useCometTrashPostMutation`.
- Tránh việc xoá vĩnh viễn ngay lập tức (dễ khôi phục nếu lỡ tay).
- **Hỗ trợ phân loại:**
  - `typePost="my_post"`: Dành cho bài viết chính chủ (bạn tự viết).
  - `typePost="others"`: Dành cho bài viết share hoặc của người khác đăng lên tường.

### 2. Lưu trữ bài viết (`_archivePost.py`)
- Hỗ trợ ẩn bài viết khỏi Timeline và chuyển vào Kho lưu trữ (Archive) sử dụng `useCometArchivePostMutation`.
- Phù hợp với nhu cầu dọn dẹp profile nhưng không muốn xoá đi kỷ niệm.
- Hỗ trợ tham số `typePost` tương tự như tính năng xoá bài viết.

---

## 🛠 Fixes & Chores
- Cập nhật chuẩn hoá tài liệu API (`DOCS.md`, `README.md`, `README_EN.md`) cho hai module mới.
- Khắc phục lỗi copy-paste nhầm key parse payload trong `_deletePost.py` từ các bản nháp trước.
- Loại bỏ các comment/docstring không đạt chuẩn để tối ưu clean code.
