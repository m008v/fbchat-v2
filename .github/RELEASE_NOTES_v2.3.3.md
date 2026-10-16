# fbchat-v2 v.2.3.3 - Sửa LightSpeed DB1 và E2EE

Tên GitHub Release là `v.2.3.3`, package version là `2.3.3` và tag kỹ thuật
là `v2.3.3`. Tag giữ định dạng SemVer để wrapper tìm đúng bridge.

## Thay đổi chính

- Cập nhật Messagix/LightSpeed lên DGW hiện hành và hỗ trợ sync V4 cho
  `databaseID=1`, khôi phục nhận message group thường qua Go bridge.
- Sửa thứ tự pairing: đăng ký và lưu device trước khi khởi tạo Whatsmeow
  client. Regular connected không còn được coi là đủ khi E2EE chưa ready.
- Tách timeout startup theo từng phase: contract, new client, regular connect,
  regular ready, E2EE connect và E2EE ready. `BridgeStartupError` giữ nguyên
  exception chain để debug mà không làm rò secret.
- Watchdog reconnect được sửa để `wait_until_connected()` chờ đúng generation
  mới sau khi subprocess chết.
- Bot/demo yêu cầu E2EE sẵn sàng. Message group thường được trả lời qua Go
  LightSpeed `sendMessage`, không fallback sang Python MQTT.
- Chuẩn hóa toàn bộ hướng dẫn onboarding, submodule và import public theo
  namespace `fbchat_v2`.

## Bảo mật và quyền riêng tư

Log runtime của Python và Go che cookie, access token, provider ID, JID, tên
thread, URL, cursor, payload/data, database object, XML crypto, prekey và chữ
ký. `database_id` không nhạy cảm vẫn được giữ lại để phân biệt DB1/DB2 khi
chẩn đoán sync. Demo chỉ in nội dung message khi người chạy chủ động bật tùy
chọn này.

Media E2EE dùng temp file có quyền riêng từ lúc tạo, gồm protected DACL trên
Windows. Typing có deadline 10 giây và bị hủy khi client dừng. Go logger/Python
stderr giữ tối đa 64 KiB mỗi dòng, bỏ nguyên dòng quá cỡ rồi tiếp tục drain;
fragment có thể chứa secret không được in ra.

Toolchain Go được nâng lên `1.26.9`, `golang.org/x/net` lên `0.60.0` để vá các
call path mà vulnerability scanner đã pin phiên bản phát hiện trên bản trước.
CI vẫn giữ bước kiểm tra này.

## Kiểm chứng canary

Lần canary bằng tài khoản clone trên group có sẵn đã kiểm tra:

1. DB1 sync hoàn tất và E2EE chuyển sang `ready`.
2. Nhận `ping` qua Go LightSpeed và gửi reply trước reconnect.
3. Dừng đúng bridge child process; watchdog respawn ở attempt đầu.
4. E2EE kết nối lại và Go LightSpeed tiếp tục gửi reply sau reconnect.

Cookie và ID thật không được đưa vào log, source hoặc release note.

`scripts/soak_e2ee.py` bổ sung quy trình kiểm chứng payload E2EE hai chiều,
media digest/echo, cold restart với cùng persistent device và soak 2 giờ có
RSS/queue telemetry. Kết quả của quy trình này được ghi riêng theo từng run;
test hermetic chỉ kiểm tra driver, không thay cho kết quả live.

Driver recovery có test offline dùng controller, subprocess và hai tunnel
localhost thật để kiểm cắt kết nối, reconnect và dọn tài nguyên. Cold restart
sau payload và ca mất mạng live vẫn chưa đủ bằng chứng để đánh dấu đạt;
không dùng kết quả offline thay cho xác nhận từ peer.

## Cài đặt sau khi phát hành

Lệnh dưới dùng bản trên PyPI. Nếu `2.3.3` chưa có ở đó, tải wheel từ GitHub
Release để cài trực tiếp.

```bash
python -m pip install --upgrade "fbchat-v2==2.3.3"
```

Bridge E2EE dùng asset từ tag `v2.3.3` và từ chối chạy
khi version, capability hoặc checksum không khớp.
