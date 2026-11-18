# Chạy các bot mẫu

Chạy từ thư mục gốc repo với Python 3.10 trở lên. Các mẫu dùng cookie tài khoản
Facebook cá nhân; chỉ thử trong nhóm/hội thoại mà những người tham gia đã đồng ý.

```powershell
python -m pip install -e .
$env:FB_COOKIES = "c_user=...; xs=...; fr=...; datr=...;"
$env:FB_THREAD_ID = "ID_NHÓM_TEST"
python examples/01_echo_bot.py
```

Thay các giá trị mẫu bằng cookie và ID thật trên máy của bạn. Không commit cookie,
chụp màn hình terminal có cookie hoặc gửi chúng vào issue. Trên macOS/Linux,
dùng `export FB_COOKIES='...'` và `export FB_THREAD_ID='...'`.

## 01: Echo cơ bản

[`01_echo_bot.py`](01_echo_bot.py) trả lại text vào đúng nhóm `FB_THREAD_ID`.
Bot bỏ qua tin của chính tài khoản, tin ngoài nhóm, tin không có text và text
dài hơn 2000 ký tự. Mẫu này dùng Python MQTT thường, không cần Go.

File echo có dưới 20 dòng. Phần tạo session, lọc nhóm và đóng listener nằm trong
[`_common.py`](_common.py), dùng chung với mẫu 02. Đây là helper của các ví dụ,
không phải API public để import từ package `fbchat_v2`.

## 02: Biệt danh, danh sách thành viên và poll bằng tin nhắn

```powershell
$env:FB_ADMIN_ID = "ID_NGƯỜI_ĐƯỢC_PHÉP_ĐIỀU_KHIỂN"
python examples/02_group_manager.py
```

Mẫu [`02_group_manager.py`](02_group_manager.py) tiếp tục dùng cookie và nhóm ở
bước trên. Gửi lệnh từ tài khoản có ID khớp `FB_ADMIN_ID`, khác tài khoản bot:

- `/nick 100012345678 Biệt danh mới`: đổi biệt danh của thành viên đó.
- `/members an`: tìm tên chứa "an", không phân biệt hoa thường. Để trống từ
  tìm kiếm để xem tối đa 20 thành viên. Lệnh chỉ xem danh sách, không kick.
- `/poll Đi ngày nào? | Thứ bảy | Chủ nhật`: mở poll có 2 đến 6 lựa chọn.
- `/close`: đóng poll và trả kết quả cuối.

Mọi thành viên trong nhóm đã chọn có thể gửi `1`, `2`, ... để bỏ phiếu hoặc đổi
phiếu, dùng `/results` để xem tổng. Poll giới hạn 1000 người, chỉ có một poll mở;
khởi động lại bot sẽ mất toàn bộ phiếu. Đây là poll bằng text, không tạo đối
tượng poll native của Messenger. Mẫu không lưu danh sách người bỏ phiếu ra file.

`FB_ADMIN_ID` là quyền điều khiển bot do bạn cấu hình. Facebook vẫn kiểm tra
quyền của tài khoản bot khi đổi biệt danh. API danh sách nhóm chỉ tải tối đa
50 cuộc trò chuyện; nếu nhóm không nằm trong kết quả, bot báo không tìm thấy,
không đoán danh sách thành viên.

## 03: E2EE với Go bridge

```powershell
$env:FB_CHAT_JID = "JID_HỘI_THOẠI_E2EE_TEST"
python examples/03_e2ee_bot.py
```

Mẫu [`03_e2ee_bot.py`](03_e2ee_bot.py) dùng `FB_COOKIES` cùng `FB_CHAT_JID`;
không dùng `FB_THREAD_ID`. Lấy đúng `chatJid` từ event của hội thoại, không tự
đoán bằng cách nối thread ID với một suffix. Nếu cần xem event schema và build
binary, đọc [hướng dẫn E2EE](../docs/messaging/e2ee.md).

Cần bridge Go cùng phiên bản Python package. Có thể đặt `FBCHAT_E2EE_BIN` trỏ
tới binary đã build; nếu dùng cơ chế tải tự động, thư viện kiểm checksum asset.
Chờ thông báo `E2EE READY`, sau đó gửi `/ping` hoặc `/echo Xin chào` từ tài khoản
khác vào hội thoại đã chọn. Event regular không được dùng để phản hồi trong mẫu này.

Callback chuyển event về queue asyncio, có giới hạn và báo số event bị bỏ khi
đầy. Mẫu chờ readiness, giới hạn retry của wrapper ở năm lượt và không tự gửi
lại khi kết quả gửi là `unknown`. Lượt chờ native reconnect không phải số lần
TCP connect của Go; xem [ReconnectPolicy](../docs/messaging/e2ee.md#tự-nối-lại).
Device mặc định chỉ nằm trong RAM; process bridge mất thì mẫu không tự pair lại.

## Dừng và phạm vi sử dụng

Nhấn Ctrl+C để hủy task và chờ thư viện đóng listener/bridge. Chỉ chạy một bot
trên cùng tài khoản test tại một thời điểm. Hai mẫu đầu dành cho chat thường;
nếu không nhận được tin trong hội thoại mã hóa, chuyển sang mẫu 03.

Các mẫu minh họa API, chưa có lưu trạng thái bền vững hay chống spam đủ cho
nhóm lớn. Chúng không log nội dung chat, cookie hoặc lỗi provider thô. Thiếu
biến môi trường sẽ có thông báo cấu hình; lỗi provider chỉ in tên loại lỗi.
Các test trong repo chạy bằng mock/loopback, không thay cho kiểm chứng Facebook live.
