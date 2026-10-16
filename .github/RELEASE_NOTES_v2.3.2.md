# fbchat-v2 v2.3.2 - Sửa runtime, E2EE và kiểm tra artifact

`v2.3.2` sửa lỗi MQTT khi khởi động mới, mutation GraphQL báo thành công sai,
quyền file Windows và cleanup E2EE. Bản này cũng giới hạn tài nguyên và kiểm
tra wheel/sdist để tránh khác biệt giữa package PyPI và source phát hành.

## Thay đổi chính

- Regular MQTT listener dùng entrypoint blocking thật để lấy `last_seq_id`,
  không còn xử lý coroutine như một `dict`; payload sai schema bị loại an toàn.
- Block, Professional mode, register-on-profile và Messenger Notes chỉ báo
  thành công khi đúng mutation node tồn tại và response không có GraphQL errors.
- Notes mutation không retry request không idempotent; client mutation ID không
  còn lấy từ miền 11 giá trị dễ trùng; reaction mutation cũng dùng ID mới cho
  từng request.
- File session giữ ACL riêng sau atomic replace trên Windows; CI chạy full
  pytest trên Windows để giữ regression này.
- E2EE bridge rollback client khởi tạo dở, dọn subprocess khi handshake lỗi,
  giới hạn kích thước RPC/media và queue 1.000 event. Log overflow không chứa
  payload.
- Timeout gửi E2EE trả trạng thái `unknown`, không báo success hoặc cache làm
  message cuối. Không tự retry vì request có thể đã tới server và gây gửi trùng.
- `/unsend` fail closed nếu chưa cấu hình admin.
- `/search` giới hạn độ dài và quota theo sender/toàn bot; log Windows giữ Unicode mà
  không in query hoặc payload nhạy cảm.
- Go `1.26.6`, `gorilla/websocket 1.5.3`; quality gate chạy thêm
  `govulncheck` đã pin.

## Tương thích cần lưu ý

Caller dùng standalone E2EE sender nên xử lý ba nhánh rõ ràng:

```python
result = sender.send(chat_jid, text)
if result.get("success"):
    ...
elif result.get("uncertain"):
    # Không tự retry; dùng messageID để đối soát.
    ...
else:
    ...
```

Public package giữ namespace `fbchat_v2.*`; các import legacy ở source checkout
vẫn được duy trì để không làm gãy ứng dụng hiện có.

## Artifact và provenance

Release workflow build năm bridge binary từ chính tag `v2.3.2`, nhúng checksum
vào Python distribution, smoke-test wheel/sdist trong môi trường sạch, tạo
`SHA256SUMS`/`SHA256SUMS-python` và gắn build provenance. PyPI chỉ nhận đúng
wheel/sdist đã qua chuỗi kiểm tra này, không rebuild thêm một lượt ở checkout
khác. Canonical package dùng exact allowlist, kiểm `RECORD`/`PKG-INFO`; workflow
recheck tag ngay trước upload và từ chối release asset cũ hoặc dư.

## Cài đặt

```bash
python -m pip install --upgrade "fbchat-v2==2.3.2"
```

Bridge E2EE tự tải asset `v2.3.2` đúng nền tảng và từ chối chạy khi checksum,
version hoặc capability không khớp.
