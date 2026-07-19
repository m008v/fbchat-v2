# Tài liệu ngôn ngữ

`fbchat-v2` duy trì tài liệu người dùng và tài liệu module theo hai ngôn ngữ:

| Phạm vi | Tiếng Việt | English |
|---|---|---|
| Tổng quan | [`../README.md`](../README.md) | [`../README_EN.md`](../README_EN.md) |
| Core | [`../src/_core/README.md`](../src/_core/README.md) | [`../src/_core/README_EN.md`](../src/_core/README_EN.md) |
| Features | [`../src/_features/README.md`](../src/_features/README.md) | [`../src/_features/README_EN.md`](../src/_features/README_EN.md) |
| Messaging | [`../src/_messaging/README.md`](../src/_messaging/README.md) | [`../src/_messaging/README_EN.md`](../src/_messaging/README_EN.md) |

[`../DOCS.md`](../DOCS.md) là tài liệu API chi tiết bằng tiếng Việt. [`../FLOWCHART.md`](../FLOWCHART.md) và [`../mindmap-mermaid.md`](../mindmap-mermaid.md) mô tả kiến trúc bằng Mermaid.

## 📏 Quy tắc cập nhật

- Khi public API đổi, cập nhật cả bản Việt và Anh trong cùng commit.
- Ví dụ mạng mới phải dùng `async`/`await` và `httpx.AsyncClient` đúng hợp đồng hiện tại.
- Giữ tên module, function, parameter và result key giống source; không dịch identifier.
- Chuỗi tiếng Việt viết đủ dấu và lưu UTF-8.
- Không dùng em dash; dùng dấu gạch ngang `-`.
- Kiểm tra internal link, code fence và Mermaid syntax trước push.
- Không đưa cookie, token, password, TOTP secret hoặc `dataFB` thật vào ví dụ.

## 🧪 Kiểm tra encoding

PowerShell có thể hiển thị sai tiếng Việt dù file vẫn là UTF-8. Trước khi sửa hàng loạt, đọc file với encoding rõ ràng hoặc kiểm tra codepoint. Quét tối thiểu:

- UTF-8 invalid.
- U+FFFD replacement character.
- NUL.
- Các chuỗi mojibake phổ biến.

Chỉ xác nhận tài liệu sạch sau khi kiểm tra bytes/codepoint, không dựa riêng vào cách terminal render.
