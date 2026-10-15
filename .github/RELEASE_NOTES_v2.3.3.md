# 🚀 fbchat-v2 v.2.3.3 — LightSpeed DB1 và E2EE ổn định hơn

Tên hiển thị của GitHub Release là `v.2.3.3`; package version là `2.3.3` và
tag kỹ thuật vẫn là `v2.3.3` để giữ SemVer cùng contract tải bridge hiện có.

## Thay đổi chính

- Cập nhật Messagix/LightSpeed lên DGW hiện hành và hỗ trợ sync V4 cho
  `databaseID=1`, khôi phục nhận message group thường qua Go bridge.
- Sửa thứ tự pairing: device được đăng ký và lưu bền vững trước khi khởi tạo
  Whatsmeow client. Lỗi kiểu “regular connected nhưng E2EE chưa ready” không
  còn bị nuốt thành trạng thái kết nối giả.
- Tách timeout startup theo từng phase: contract, new client, regular connect,
  regular ready, E2EE connect và E2EE ready. `BridgeStartupError` giữ nguyên
  exception chain để debug mà không làm rò secret.
- Watchdog reconnect được sửa để `wait_until_connected()` chờ đúng generation
  mới sau khi subprocess chết.
- Bot/demo bắt buộc chạy E2EE. Message group thường được trả lời qua Go
  LightSpeed `sendMessage`; không có fallback Python MQTT âm thầm.
- Chuẩn hóa toàn bộ hướng dẫn onboarding, submodule và import public theo
  namespace `fbchat_v2`.

## Bảo mật và quyền riêng tư

Runtime log ở cả Python và Go che cookie, access token, provider ID, JID, tên
thread, URL, cursor, payload/data, database object, XML crypto, prekey và chữ
ký. `database_id` không nhạy cảm vẫn được giữ lại để phân biệt DB1/DB2 khi
chẩn đoán sync. Demo không in nội dung message trừ khi người chạy bật opt-in
rõ ràng.

## Kiểm chứng canary

Canary bằng tài khoản clone đã xác minh chuỗi sau trên group có sẵn:

1. DB1 sync hoàn tất và E2EE chuyển sang `ready`.
2. Nhận `ping` qua Go LightSpeed và gửi reply trước reconnect.
3. Dừng đúng bridge child process; watchdog respawn ở attempt đầu.
4. E2EE kết nối lại và Go LightSpeed tiếp tục gửi reply sau reconnect.

Cookie và ID thật không được đưa vào log, source hoặc release note.

## Cài đặt sau khi phát hành

```bash
python -m pip install --upgrade "fbchat-v2==2.3.3"
```

Bridge E2EE tải asset từ tag `v2.3.3` và từ chối chạy khi version, capability
hoặc checksum không khớp.
