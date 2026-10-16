# Tài liệu ngôn ngữ

Tài liệu tổng quan và module có bản tiếng Việt và tiếng Anh:

| Phạm vi | Tiếng Việt | English |
|---|---|---|
| Tổng quan | [`../README.md`](../README.md) | [`../README_EN.md`](../README_EN.md) |
| Core | [`../src/_core/README.md`](../src/_core/README.md) | [`../src/_core/README_EN.md`](../src/_core/README_EN.md) |
| Features | [`../src/_features/README.md`](../src/_features/README.md) | [`../src/_features/README_EN.md`](../src/_features/README_EN.md) |
| Messaging | [`../src/_messaging/README.md`](../src/_messaging/README.md) | [`../src/_messaging/README_EN.md`](../src/_messaging/README_EN.md) |

[`../DOCS.md`](../DOCS.md) là tài liệu API chi tiết bằng tiếng Việt. [`../FLOWCHART.md`](../FLOWCHART.md) và [`../mindmap-mermaid.md`](../mindmap-mermaid.md) mô tả kiến trúc bằng Mermaid.

## 📏 Quy tắc cập nhật

- Khi đổi public API, cập nhật cả bản Việt và Anh trong cùng commit.
- Ví dụ gọi mạng mới dùng `async`/`await` và `httpx.AsyncClient` theo API hiện tại.
- Giữ nguyên tên module, hàm, tham số và result key như trong source; không dịch identifier.
- Chuỗi tiếng Việt viết đủ dấu và lưu UTF-8.
- Không dùng em dash; dùng dấu gạch ngang `-`.
- Kiểm tra liên kết nội bộ, code fence và cú pháp Mermaid trước khi push.
- Không đưa cookie, token, password, TOTP secret hoặc `dataFB` thật vào ví dụ.

## 🧪 Kiểm tra encoding

PowerShell đôi khi hiển thị sai tiếng Việt dù file là UTF-8. Trước khi sửa hàng loạt, đọc với encoding cụ thể hoặc kiểm tra codepoint. Cần kiểm tra:

- Byte không hợp lệ theo UTF-8.
- Ký tự thay thế U+FFFD.
- NUL.
- Các chuỗi mojibake phổ biến.

Kiểm tra byte/codepoint trước khi kết luận file bị lỗi; cách terminal hiển thị chưa đủ để xác định encoding.
