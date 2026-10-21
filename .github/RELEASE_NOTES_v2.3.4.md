# fbchat-v2 v2.3.4 — Tự reconnect MQTT/E2EE

Bản này thêm retry khi khởi động lúc mất mạng và khi kết nối bị ngắt. Mặc định
wrapper thử lại lỗi mạng không giới hạn, với exponential backoff, jitter và
delay trần. Có thể giới hạn hoặc tắt retry bằng `ReconnectPolicy`.

## Thay đổi chính

- MQTT dùng một supervisor quản lý retry, giữ sync token/sequence và cache
  message ID có giới hạn qua reconnect.
- E2EE để socket Go tự nối lại khi bridge/RPC còn khỏe. Python chỉ thay
  subprocess khi generation không còn dùng được; không replay send/mutation.
- `connection_state`, `connection_status` và callback cho biết listener đang
  startup, connected, reconnecting, cần xác thực, gặp lỗi hoặc đã dừng.
- Bridge có capability `structuredConnectionStatus`, trả failure code an toàn
  theo từng transport. Lỗi auth/checkpoint/config/protocol dừng thay vì retry
  cùng credential hoặc cấu hình; lỗi chưa phân loại cũng dừng rõ ràng.
- Stop/cancel ngắt chờ retry và chờ worker thu dọn. Bot mẫu không thoát chỉ vì
  một cửa sổ startup timeout kết thúc trong lúc listener vẫn đang reconnecting.
- Go được nâng lên `1.26.10` để vá `GO-2026-6809` trong `crypto/x509`.

## Nâng cấp

```bash
python -m pip install --upgrade "fbchat-v2==2.3.4"
```

E2EE cần bridge 2.3.4. Wrapper kiểm version, capability và checksum; nếu đang
override binary bằng `FBCHAT_E2EE_BIN` hoặc `binary_path`, hãy thay binary cũ.
Nếu tự build, lấy bridge và package Python từ cùng checkout.

Xem [hướng dẫn cấu hình reconnect](https://github.com/m008v/fbchat-v2/blob/v2.3.4/DOCS.md#tự-nối-lại)
để giới hạn retry và nhận callback trạng thái. Callback chỉ chứa trạng thái,
reason code, attempt và delay; không có cookie hay nội dung chat.

## Những điều cần lưu ý

- E2EE mặc định giữ device trong RAM. Process chết sẽ báo `device_state_lost`,
  không tự pair device mới hoặc ghi key ra đĩa. Muốn phục hồi qua process mới,
  chủ động dùng `e2ee_memory_only=False` cùng `device_path` riêng. File này chứa
  key/session; không commit hoặc chia sẻ.
- `max_delay` không ghi đè backoff socket native Go. Khi E2EE chờ native
  reconnect, `attempt` đếm lượt wrapper quan sát, không phải TCP connect.
  Budget hữu hạn có thể hết trước lần thử socket tiếp theo.
- Cache lọc replay có giới hạn. Reconnect không đảm bảo nhận đủ mọi tin gửi
  trong thời gian offline; thay process có thông báo nguy cơ message gap.
- Tin gửi trả kết quả `unknown` không được tự gửi lại chỉ vì mạng đã hồi phục.
- Bộ test offline bao gồm startup mất mạng, outage, socket E2EE rớt riêng,
  retry budget, cancellation, replay và native RPC contract. Đây không phải
  bằng chứng provider-live: cold restart sau payload thật và mất mạng riêng
  bridge vẫn cần được kiểm chứng bằng một lượt live được cho phép riêng.
