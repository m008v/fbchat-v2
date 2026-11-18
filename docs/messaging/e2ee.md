# Nhận và gửi tin E2EE

[Bắt đầu](../getting-started/quickstart.md) · [Tin nhắn thường](standard.md) · [E2EE](e2ee.md) · [Facebook](../features/facebook-actions.md) · [Tra nhanh](../recipes/cheatsheet.md)

Trong trang này:

- [Listener E2EE](#listener-e2ee)
- [Gửi và thao tác qua bridge](#gửi-và-thao-tác-qua-bridge)
- [Tự nối lại](#tự-nối-lại)
- [Canary E2EE và soak có kiểm soát](#canary-e2ee-và-soak-có-kiểm-soát)
- [Cold restart sau payload và test mất mạng riêng bridge](#cold-restart-sau-payload-và-test-mất-mạng-riêng-bridge)
- [Diễn tập recovery hoàn toàn offline](#diễn-tập-recovery-hoàn-toàn-offline)

Tạo session theo [quickstart](../getting-started/quickstart.md), rồi dùng bridge Go cùng phiên bản package.
Đăng ký callback trước khi khởi động, chờ E2EE ready rồi mới gửi tin. Các đoạn code dưới đây tiếp tục dùng `data_fb` của session đó.

## Listener E2EE

Import listener trước khi khởi tạo:

```python
from fbchat_v2 import listeningE2EEEvent
```

Khởi tạo:

```python
listener = listeningE2EEEvent(
    data_fb,
    log_level="none",
    device_path=None,
    e2ee_memory_only=True,
    enable_e2ee=True,
    binary_path=None,
)
```

| Tham số | Ý nghĩa |
|---|---|
| `log_level` | Mức log gửi cho bridge |
| `device_path` | Path state thiết bị khi muốn persist |
| `e2ee_memory_only` | Giữ device state trong RAM khi `True` |
| `enable_e2ee` | Có gọi handshake E2EE hay không |
| `binary_path` | Override binary cho instance này |

Cookie bridge bắt buộc có `c_user`, `xs`, `datr`, `fr`. Wrapper chỉ chuyển các cookie cần thiết sang bridge.

### Tìm binary bridge

Thứ tự:

1. `binary_path=` trên constructor.
2. `FBCHAT_E2EE_BIN`.
3. `build/fbchat-bridge-e2ee.exe` trên Windows hoặc không đuôi trên Unix.
4. Auto-download GitHub Release nếu path mặc định chưa có.

Nếu bạn chỉ định đường dẫn nhưng file không tồn tại, wrapper báo `FileNotFoundError`, không tự tải binary khác.

### Callback và event loop

`on_message()` nhận callback đồng bộ, được gọi từ vòng lặp đọc event của bridge. Không dùng `await` trực tiếp trong callback; hãy chuyển event về event loop:

```python
import asyncio

listener = listeningE2EEEvent(data_fb)
loop = asyncio.get_running_loop()
events: asyncio.Queue[dict] = asyncio.Queue(maxsize=1000)


def enqueue(event: dict) -> None:
    if events.full():
        events.get_nowait()
    events.put_nowait(event)


listener.on_message(
    lambda event: loop.call_soon_threadsafe(enqueue, event)
)
task = asyncio.create_task(listener.connect_mqtt())
```

### Đợi bridge sẵn sàng

`wait_until_connected()` dùng `threading.Event`. Gọi qua worker thread để không chặn event loop:

```python
ready = await asyncio.to_thread(
    listener.wait_until_connected,
    listener.startup_timeout,
    require_e2ee=True,
)
if not ready:
    raise TimeoutError("E2EE listener chưa sẵn sàng.")
```

Đừng gửi tin ngay sau `create_task(connect_mqtt())`; tiến trình bridge có thể đã chạy nhưng chưa xong `newClient`, `connect` và `connectE2EE`. Wrapper đặt timeout riêng cho các bước `contract`, `new client`, `regular connect`, `regular ready`, `E2EE connect` và `E2EE ready`. `startup_timeout` là ngân sách cho một lượt khởi động, không phải deadline cho toàn bộ thời gian retry. `wait_until_connected()` trả `False` khi hết thời gian chờ của caller; nếu listener còn `reconnecting`, ứng dụng có thể tiếp tục chờ. Lỗi terminal vẫn được trả về, không bị đổi thành timeout chung.

### Schema event

Event nhận qua callback:

```python
{
    "type": "e2eeMessage",
    "data": {
        "id": "...",
        "text": "ping",
        "timestampMs": 1710000000000,
        "senderId": "1000...",
        "threadId": "...",
        "chatJid": "1000...@msgr",
        "senderJid": "1000...@msgr",
        "attachments": [],
        "mentions": [],
    },
}
```

`listener.bodyResults` giữ dữ liệu đã chuẩn hóa giống listener thường. `listener.e2eeBodyResults` giữ `chatJid` và `senderJid`. Ứng dụng mới nên xử lý event nhận qua callback, tránh đọc kết quả bị ghi đè khi nhiều tin đến liên tiếp.

### Dừng listener

```python
try:
    ...
finally:
    listener.stop()
    await task
```

`stop()` là hàm đồng bộ: nó báo dừng và đóng tiến trình con. Bạn vẫn cần `await` task để chờ listener kết thúc. Trong ứng dụng async, có thể gọi `stop()` qua `asyncio.to_thread()` như bot mẫu để tránh chặn event loop trong lúc thu dọn.


## Gửi và thao tác qua bridge

### Gửi text E2EE

Sau khi listener ready:

```python
result = await listener.send_e2ee_message(
    "100012345678@msgr",
    "Xin chào",
    reply_to_id="",
    reply_to_sender_jid="",
)
```

Reply:

```python
data = event["data"]
result = await listener.send_e2ee_message(
    data["chatJid"],
    "pong",
    reply_to_id=data["id"],
    reply_to_sender_jid=data["senderJid"],
)
```

### Gửi tin thường qua cùng bridge

```python
result = await listener.send_message(
    int(thread_id),
    "Thông báo group",
    reply_to_id="mid.$original",
)
```

### `BridgeActions`

```python
from fbchat_v2._messaging._bridge_actions import BridgeActions

if listener._bridge is None:
    raise RuntimeError("Bridge chưa sẵn sàng.")
actions = BridgeActions(listener._bridge)
```

Các thao tác async:

| Method | Mục đích |
|---|---|
| `edit_message(message_id, new_text)` | Sửa tin thường qua bridge |
| `unsend_message(message_id)` | Thu hồi tin thường |
| `edit_e2ee_message(chat_jid, message_id, new_text)` | Sửa tin E2EE |
| `unsend_e2ee_message(chat_jid, message_id)` | Thu hồi tin E2EE |
| `send_typing_indicator(thread_id, is_typing, ...)` | Typing thường |
| `mark_read(thread_id, watermark_ts)` | Đánh dấu đã đọc |
| `send_e2ee_typing(chat_jid, is_typing)` | Typing E2EE |
| `send_e2ee_audio(chat_jid, data, ...)` | Gửi audio bytes |
| `send_e2ee_image(chat_jid, data, ...)` | Gửi image bytes |
| `download_media(url)` | Download media thường thành bytes |
| `download_e2ee_media(...)` | Download và giải mã media E2EE |

Ví dụ gửi ảnh:

Import `Path` trước khi đọc file:

```python
from pathlib import Path
```

```python
image_bytes = await asyncio.to_thread(Path("photo.jpg").read_bytes)
result = await actions.send_e2ee_image(
    "100012345678@msgr",
    image_bytes,
    mime_type="image/jpeg",
    caption="Ảnh test",
)
```

Bytes được chuyển sang base64 khi gửi qua JSON-RPC. Không đọc file lớn trực tiếp trong event loop; dùng `asyncio.to_thread()` hoặc I/O async phù hợp.

### `_send_e2ee.api`

`_send_e2ee.api` là sender blocking được giữ để tương thích, có thể chạy riêng hoặc dùng lại bridge. Ứng dụng asyncio mới nên dùng `await listener.send_e2ee_message(...)` và `BridgeActions`. Nếu cần sender chạy riêng, tách lời gọi blocking khỏi event loop.


## Tự nối lại

API dưới đây có từ `2.3.4`. Với E2EE, dùng bridge cùng phiên bản để có
capability `structuredConnectionStatus`. Nếu tự build, lấy bridge từ cùng
checkout với package Python; binary 2.3.3 không có contract này.

MQTT và E2EE dùng chung `ReconnectPolicy` cho lỗi kết nối tạm thời, kể cả khi
khởi động lúc mất mạng. Mặc định không giới hạn số lượt phục hồi của wrapper;
delay tăng dần từ 1 giây, có jitter 20% và không vượt 60 giây. Sau 60 giây
kết nối ổn định, budget được reset. Muốn giới hạn, truyền `max_attempts=5`;
muốn tắt retry, truyền `enabled=False` hoặc `max_attempts=0`.

Với MQTT, mỗi lượt là một lần thử tạo kết nối mới sau lần đầu. Với E2EE,
policy điều khiển retry từng phase startup và respawn; khi socket Go tự nối lại, mỗi lượt
là một lần wrapper kiểm tra đã phục hồi hay chưa. `attempt` không phải bộ đếm
TCP connect của Go. Delay socket native do thư viện Go quản lý riêng; regular
transport hiện có backoff trần 5 phút, không bị `max_delay` ghi đè. Policy
giới hạn có thể dừng listener trước khi socket native thử lần tiếp theo.

```python
from fbchat_v2 import ReconnectPolicy, listeningE2EEEvent

policy = ReconnectPolicy(
    initial_delay=1.0,
    max_delay=60.0,
    jitter=0.2,
    max_attempts=None,
)

listener = listeningE2EEEvent(
    data_fb,
    reconnect_policy=policy,
    on_connection_state=lambda status: print(status),
    e2ee_memory_only=False,
    device_path=".state/e2ee_device.json",
)
```

File device chứa key thiết bị và session; không commit hoặc chia sẻ file này.
Repo đã bỏ qua thư mục `.state/` trong Git.

Với MQTT thường, truyền hai tham số `reconnect_policy` và `on_connection_state`
cho `listeningEvent` theo cùng cách. Chỉ chạy listener phù hợp với ứng dụng;
không khởi chạy thêm một listener để xử lý việc mất kết nối của listener cũ.

Đọc `listener.connection_state` hoặc `listener.connection_status` để lấy snapshot.
Callback trạng thái nhận `state`, `reason`, `attempt`, `next_retry_in`; không có
cookie, ID hội thoại hoặc nội dung chat. Callback đồng bộ có thể chạy từ worker
hoặc caller gọi `stop()`: giữ nó ngắn và dùng `loop.call_soon_threadsafe()` nếu
cần cập nhật asyncio. Không giả định callback được gọi tuần tự giữa các thread;
`connection_status` luôn là snapshot hiện tại.
Có thể thay callback bằng `listener.set_connection_state_callback(fn)`.

- `starting`: đang khởi tạo transport.
- `connected`: transport yêu cầu đã sẵn sàng; không phải xác nhận một tin gửi đã tới peer.
- `reconnecting`: đang chờ hoặc thử nối lại.
- `auth_required`: cần cập nhật cookie hoặc xử lý checkpoint; không retry cùng credential.
- `fatal`: lỗi protocol/config, hết retry budget hoặc không thể phục hồi an toàn.
- `stopped`: đã yêu cầu dừng.

Lỗi chưa phân loại được dừng với `fatal/unknown`, không retry vô hạn. Ví dụ,
Paho không giữ HTTP status khi WebSocket upgrade bị từ chối; thư viện không
đoán đây là lỗi mạng hay cookie hết hạn chỉ từ một thông báo handshake chung.

Socket Go/whatsmeow giữ quyền tự nối lại khi bridge vẫn khỏe. Python chỉ thay
process khi bridge crash hoặc RPC không còn dùng được, không giết bridge chỉ
vì mạng đang mất. Với E2EE mặc định `e2ee_memory_only=True`, device chỉ nằm trong
RAM của bridge: process chết thì listener báo `device_state_lost`, không tự
pair device mới và không tự ghi key ra đĩa. Nếu cần phục hồi qua process mới,
chọn `e2ee_memory_only=False` cùng `device_path` riêng như ví dụ trên.

MQTT giữ sync token/sequence qua reconnect và có cache message ID giới hạn để
lọc replay. Cache và khả năng đồng bộ của server vẫn có giới hạn; reconnect
không phải cam kết nhận đủ mọi tin đã gửi trong thời gian offline. Theo dõi
queue drop và thông báo khoảng trống dữ liệu khi thay process. Tin gửi trả
`unknown` không được tự gửi lại chỉ vì transport vừa kết nối lại.

`disconnect()`/`stop()` ngắt thời gian chờ retry. Hủy coroutine `connect_mqtt()`
sẽ yêu cầu dừng và chờ worker thu dọn; lời gọi mạng đang chạy vẫn chịu timeout
riêng. Không chạy listener mới trước khi task cũ kết thúc.


## Canary E2EE và soak có kiểm soát

Chạy các lệnh kiểm thử bên dưới từ thư mục gốc repo. Chúng đăng nhập và
gửi tin thật; chỉ chạy khi cả tài khoản test lẫn peer đã sẵn sàng.

Chỉ dùng tài khoản clone và một peer đã đồng ý kiểm thử. Driver đọc cookie từ
`FBCHAT_COOKIE` hoặc `src/config.json` nội bộ, lưu device bền vững và evidence
không có ID/nội dung chat trong một thư mục mới. Không chạy cùng device với bot
khác và không đưa `device.json` vào Git hoặc gửi cho người khác.

```powershell
python scripts/soak_e2ee.py `
  --binary-path .tmp/fbchat-bridge-e2ee-soak.exe `
  --output-dir .tmp/e2ee-soak-run `
  --duration 7200 --sample-interval 60 --fault-after 300
```

Driver đăng nhập, dừng hẳn listener, tạo listener mới từ cùng device rồi so
sánh identity trước khi báo `READY`. Khi đó peer gửi đúng challenge có nonce
được in trên console qua cuộc trò chuyện E2EE; chỉ peer này được kích hoạt
một reply text, một ảnh và một file tối đa 2 MiB. Driver download/giải mã,
đối chiếu SHA-256 của attachment rồi echo lại, không lưu plaintext ra evidence.

Sau khi thật sự nhìn thấy reply, peer gửi mã `text-ok-...` nằm trong reply;
sau khi nhận đủ ảnh và file echo, gửi mã `media-ok-...` mà bot hướng dẫn.
Hai mã này được tạo riêng từng run và chỉ gửi qua E2EE. Đây là xác nhận từ đầu bên kia, khác
với việc RPC gửi trả thành công. Event regular và event cũ không được tính là
bằng chứng E2EE. Timeout gửi không được tự retry.
ACK text cập nhật `peer_confirmed_text`. Khi ACK media hợp lệ xác nhận đã nhận
đủ ảnh và file, bot gửi đúng một tin xác nhận cuối; không phản hồi lặp cho ACK
trùng, tin của bot, event cũ hoặc peer khác. Lỗi gửi/timeout của tin xác nhận
không xóa bằng chứng peer đã ACK và không được tự retry.
`media_ack_notice_delivery=rpc_confirmed` chỉ xác nhận RPC gửi tin cuối trả
thành công, không chứng minh peer đã đọc tin đó. Nếu kết quả gửi chưa rõ,
trường này là `unknown`; acceptance vẫn không đạt dù bằng chứng ACK media
đã được giữ lại.

Khi không thấy phản hồi, xem bộ đếm `observed` trong report: `challenge_message`
nghĩa là mã đã tới qua Go LightSpeed regular, còn `challenge_e2eeMessage` là
event E2EE. Counter không lưu nội dung hay ID. Thêm `--regular-notice` để gửi
đúng một thông báo chẩn đoán cho challenge regular mới; mặc định tắt. Kết quả
`regular_notice_rpc_ok` luôn được ghi riêng, không tính vào điều kiện đạt của
E2EE. Tùy chọn này không chuyển listener sang Python MQTT.

Mặc định mỗi run tạo nonce mới. Có thể dùng `--challenge <mã-chính-xác>` khi
khởi động lại chẩn đoán để peer không cần đổi mã; event trước thời điểm ready
vẫn bị loại. Dùng `--device-path <device-cũ.json>` để tái sử dụng thiết bị từ
run đã dừng sạch, không chạy hai listener cùng device. Path này không được
trùng config, binary, report hoặc file điều khiển.

Mỗi phút driver ghi RSS parent/bridge, generation, trạng thái kết nối và queue
drop. Đến phút thứ năm, nó kill đúng child bridge của mình để kiểm watchdog
respawn, E2EE reconnect và một lần gửi text sau reconnect. Đây là mô phỏng
bridge crash; không phải bằng chứng chịu mất mạng thật hoặc mọi trường hợp
provider outage.

`report.json` ghi từng acceptance check. Exit code `0` nghĩa là các check đều
đạt; `1` là lỗi hoặc bị dừng; `2` là chạy hết thời gian nhưng còn check thiếu
bằng chứng/không đạt. `status=completed` riêng lẻ không đồng nghĩa mọi check
đã pass. Ctrl+C yêu cầu cleanup listener/bridge trước khi ghi report cuối.
Nếu chạy nền, tạo file `stop.request` trong output directory để yêu cầu cùng
luồng shutdown sạch; không xóa device để dừng bot.

## Cold restart sau payload và test mất mạng riêng bridge

Chạy sau khi soak kết thúc và shutdown sạch; không mở hai listener dùng cùng
device. Kiểm tra driver/bridge con của run cũ đã thoát trước khi launch;
recovery lease không khóa được consumer khác không dùng cùng cơ chế.
Runner từ chối report chưa hoàn tất hoặc chưa đạt acceptance. Nó dùng
lại device đã trao đổi payload thật, yêu cầu challenge/ACK mới và echo ảnh/file
để kiểm chứng session được khôi phục, không chỉ so sánh identity.

```powershell
python scripts/recovery_e2ee.py `
  --soak-report .tmp/e2ee-receive-notice-20261015-1350/report.json `
  --binary-path .tmp/fbchat-bridge-e2ee-soak.exe `
  --device-path .tmp/e2ee-soak-20261015-1329/device.json `
  --output-dir .tmp/e2ee-recovery-20261015
```

Parent giữ CONNECT proxy chỉ trên loopback và truyền proxy qua environment
riêng của tiến trình test con. Không thay proxy Windows, firewall hay network
adapter. Proxy relay byte mã hóa, không giải TLS hoặc ghi header/payload.
Sau khi cold restart roundtrip đạt, peer được hướng dẫn gửi chuỗi tin đánh số;
proxy cắt các tunnel của mình và từ chối CONNECT mới trong 30 giây rồi tự mở
lại. Đây là socket reset cộng thời gian không thể CONNECT, không phải mô phỏng
packet blackhole hay mọi dạng mạng half-open.

Phải có bằng chứng transport phục hồi, chuỗi tin đủ/không trùng và ACK E2EE mới
sau phục hồi. Report phân biệt socket tự reconnect với watchdog tạo process
mới; RPC gửi thành công không thay được xác nhận từ peer. Evidence không chứa
chat ID, tên file gốc, nội dung chat hoặc khóa media. Timeout/cancellation phải
dừng đúng child và đóng proxy trước khi kết luận cleanup đạt.
Đọc cả `report.json` của worker và `controller.json` của parent; chỉ báo đạt
khi acceptance của cả hai đều true. Worker hoàn tất không tự chứng minh proxy
đã shutdown sạch. Lệnh `--help` liệt kê timeout của từng phase; output phải mới.
Theo dõi `report.json` để lấy challenge khi `status=cold_restart_ready`; log
worker nằm trong output directory. Hai ACK text/media vẫn được gửi trong
Messenger. Khi bot hướng dẫn, gửi mã `net-ready-...`, rồi gửi riêng năm tin
`netseq-...-1` đến `netseq-...-5`, cách nhau khoảng 10 giây. Cuối cùng gửi
`net-ok-...` chỉ xuất hiện trong reply E2EE sau phục hồi.

Report có `outcome` riêng: `running`, `passed`, `inconclusive`, `failed` hoặc
`cancelled`. `inconclusive` chỉ dành cho trường hợp hết hạn chờ bằng chứng từ
peer. Lỗi thực thi, transport, queue drop hoặc dọn tài nguyên vẫn là lỗi,
không được ghi thành thiếu ACK.
`phase`, `reason_code`, `missing_evidence` và `waiting_for` dùng tập giá trị cố
định để chỉ đúng bước đang chờ, không sao chép nội dung chat hoặc lỗi provider.
Controller kiểm tra kết quả worker, exit code và việc dọn tài nguyên của chính
nó. Thiếu bằng chứng không được tính là đạt.

## Diễn tập recovery hoàn toàn offline

```powershell
python -m pytest tests/test_recovery_offline_integration.py -q
```

Bài này chạy controller, subprocess worker và CONNECT proxy thật với hai
stream localhost. Chỉ session, peer và bridge RPC là fixture giả; payload/ACK
giả vẫn phải đi qua tunnel. Test đối chiếu outage, từ chối CONNECT khi bị cắt,
reconnect, timeout/cancellation, report worker/controller và cleanup process,
socket, device lease. Không mock `Popen` hoặc hành vi proxy trong bài tích hợp.

Config/device chỉ là dữ liệu tổng hợp trong thư mục test tạm; không dùng cookie,
device hoặc bridge live đang có của người dùng. Mọi kết nối đều là loopback,
không thay proxy Windows, firewall hay adapter. Report diễn tập được đánh dấu
`evidence_scope=offline_simulation`, không được dùng làm bằng chứng E2EE thật
hoặc đưa ngược vào gate live. Bài này kiểm driver/protocol giả và wiring local,
không kiểm mật mã Messenger hay khả năng chịu lỗi của provider.
