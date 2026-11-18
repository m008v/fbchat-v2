# fbchat-v2 v2.3.5

Bản này vá dependency Go, sửa CI với PyOTP mới và làm gọn cách bắt đầu viết bot.

## Thay đổi

- Bridge dùng Go 1.26.11 cùng bản vá của brotli, compress và golang.org/x/net.
  Bộ quét lỗ hổng vẫn là điều kiện bắt buộc trước khi phát hành.
- Fixture TOTP dùng key thử RFC 6238 đủ độ dài cho PyOTP 2.12, sửa lỗi CI trên
  các phiên bản Python được hỗ trợ.
- Thêm ba bot mẫu: echo, quản lý nhóm với poll bằng text và bot E2EE có Go
  bridge. Xem [examples](https://github.com/m008v/fbchat-v2/tree/v2.3.5/examples).
- Tách tài liệu API thành các trang trong `docs/`, refactor bot `src/main.py`
  và dùng mapping để suy luận loại attachment; thứ tự ưu tiên không đổi.
- Bỏ bản package sinh trùng khỏi source của main. Khi cài/build, package được
  sinh vào `build/fbchat_v2`; wheel vẫn cung cấp namespace `fbchat_v2` như trước.

## Cài đặt

```bash
python -m pip install --upgrade "fbchat-v2==2.3.5"
```

E2EE cần bridge 2.3.5. Nếu đang đặt `FBCHAT_E2EE_BIN` hoặc `binary_path`, thay
binary cũ bằng bản cùng phiên bản. Các asset bridge có checksum để đối chiếu.

[Quickstart](https://github.com/m008v/fbchat-v2/blob/v2.3.5/docs/getting-started/quickstart.md)
và [hướng dẫn E2EE](https://github.com/m008v/fbchat-v2/blob/v2.3.5/docs/messaging/e2ee.md)
ghi cách cấu hình và giới hạn reconnect.

Các kiểm tra phát hành chạy offline và dùng mock/loopback. Bản này không bổ
sung bằng chứng Facebook live cho cold restart hoặc phục hồi sau mất mạng.
