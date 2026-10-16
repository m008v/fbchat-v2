# fbchat-v2 v2.3.0 - Refactor và sửa lỗi runtime

> Ghi chú này được viết khi chuẩn bị `v2.3.0`, sau khi đồng bộ source và version
> metadata. Các mục artifact và kiểm chứng bên dưới mô tả kế hoạch ở thời điểm
> đó, không thay cho kết quả của release workflow.

`v2.3.0` tiếp tục refactor async-first, tập trung vào lifecycle E2EE, xử lý event,
lưu dữ liệu phiên và kiểm tra artifact phát hành. Bản này không chủ đích bỏ
public Python API đang hỗ trợ. Tuy vậy, những trường hợp trước đây bỏ qua lỗi
hoặc báo thành công sai nay trả lỗi, nên ứng dụng cần xử lý các kết quả đó.

## ✨ Điểm nổi bật

### Runtime async và message pipeline

- Bot mẫu quản lý startup, cancellation và shutdown trong lifecycle async;
  công việc blocking được tách khỏi event loop.
- Event `typing`, `read receipt`, `reaction` và payload phụ được lọc trước
  message queue. Queue có giới hạn, có telemetry đã che nội dung và không thể
  tăng bộ nhớ vô hạn khi event dồn dập.
- Khôi phục nhận message thường và E2EE từ live upsert; bổ sung cutoff chống
  replay và dedupe giữa upsert/insert. Placeholder không còn làm mất command
  thật có cùng ID.
- Listener thường sửa luồng refresh sequence khi MQTT overflow và không còn gọi
  coroutine như hàm đồng bộ.

### E2EE bridge lifecycle

- Thêm JSON-RPC handshake `hello` để đối chiếu `protocolVersion`,
  `bridgeVersion` và capability trước khi nhận traffic.
- Watchdog quản lý bridge theo generation, cô lập recovery, áp deadline tổng và
  exponential backoff; process, reader hoặc writer cũ không thể can thiệp vào
  generation mới.
- Writer riêng xử lý short write, pipe treo, timeout và request bị hủy. Shutdown
  có giới hạn thời gian, chống orphan process và race giữa close/reconnect.
- Readiness chỉ được công bố khi socket thường đã kết nối và E2EE đã đăng nhập
  thật. Gửi E2EE khi transport chưa sẵn sàng sẽ trả lỗi thay vì âm thầm hạ cấp
  sang transport thường.
- Listener là single-use: sau khi `stop`, ứng dụng phải tạo instance mới.

### Device state và tính toàn vẹn

- Dùng `crypto/rand` cho `AdvSecretKey`; lỗi nguồn ngẫu nhiên an toàn được trả về
  caller thay vì tiếp tục với state không đáng tin cậy.
- Persist đầy đủ identity, session, prekey, LID/account và device metadata bằng
  temp file, `fsync` và atomic rename.
- Mutation state được tuần tự hóa và rollback cả dữ liệu trong RAM nếu ghi đĩa
  thất bại. Callback snapshot được coalesce để không chặn Signal ratchet.
- Connection health theo dõi socket event thay vì chỉ dựa vào trạng thái cũ
  trong bộ nhớ.

## 🔒 Bảo mật và quyền riêng tư

- Auto-download bridge pin đúng tag/package version, chỉ chấp nhận HTTPS trên
  trusted host, kiểm tra mọi redirect, giới hạn 200 MiB và bắt buộc SHA-256 từ
  nguồn độc lập trước khi atomic replace cache.
- Media download của Go bridge giới hạn trusted Facebook/Messenger CDN, redirect
  và 100 MiB để giảm rủi ro SSRF cùng tải dữ liệu không giới hạn.
- `config.json` chứa cookie được tạo atomic với mode riêng tư trên POSIX hoặc ACL
  chỉ cho user hiện tại và `SYSTEM` trên Windows.
- Nội dung message, command và traceback được ẩn mặc định. Chỉ bật
  `log_message_content` hoặc `debug_errors` trong môi trường kiểm soát.
- Không log, commit hoặc chia sẻ cookie, session token và E2EE device state.

## 🧩 Tính năng và sửa lỗi hành vi

- Thêm `_features._facebook._unFriend.func(dataFB, friendID, client=None)` để hủy
  kết bạn theo Facebook ID; trả lỗi cho input rỗng và GraphQL failure.
- Archive post, move-to-trash và unfriend không còn trả success khi GraphQL trả
  `errors`, `data=null` hoặc `success=false`.
- Sửa các boundary sync/async trong listener, theme, note và attachment; bổ sung
  type annotation tương thích CPython 3.10.
- Wheel export trực tiếp `_core`, `_features` và `_messaging`; không import qua
  namespace `src.*`.

## 💥 Tương thích và thay đổi cần lưu ý

- Yêu cầu Python `>=3.10`; quality gate chạy trên Python 3.10–3.14.
- Không có public Python API được chủ đích loại bỏ so với dòng v2.2.x. Code async
  vẫn phải `await`; code đồng bộ dùng wrapper `*_blocking` tương ứng.
- Caller từng chỉ kiểm tra HTTP thành công cần xử lý thêm response
  `{"error": 1, ...}` từ các mutation bị Facebook từ chối.
- Custom E2EE bridge phải cùng version với package và hỗ trợ protocol `1`. Binary
  cũ hoặc thiếu capability sẽ bị từ chối.
- Source checkout chặn binary cũ hơn Go source. Nếu không có checksum tin cậy,
  hãy tự build bridge hoặc cấu hình `FBCHAT_E2EE_BIN` và
  `FBCHAT_E2EE_SHA256` từ nguồn độc lập.
- Windows ARM64 chưa có binary dựng sẵn và phải tự build.

## 🔧 Nâng cấp từ v2.2.x

Sau khi `v2.3.0` được phát hành:

```bash
python -m pip install --upgrade "fbchat-v2==2.3.0"
```

Với source checkout:

```bash
git submodule update --init --recursive bridge-e2ee/meta
python -m pip install -e .
cd bridge-e2ee
go mod download
go build -trimpath \
  -ldflags="-s -w -X main.bridgeVersion=2.3.0" \
  -o ../build/fbchat-bridge-e2ee .
```

Trên Windows, đổi output cuối thành
`../build/fbchat-bridge-e2ee.exe`. Dùng Go version được khai báo trong
`bridge-e2ee/go.mod`.

Config cũ vẫn dùng được. Hai tùy chọn riêng tư mới mặc định là `false`:

```json
{
  "log_message_content": false,
  "debug_errors": false
}
```

Nếu ứng dụng tự quản lý `httpx.AsyncClient`, ứng dụng cũng chịu trách nhiệm đóng
client. Sau khi dừng listener E2EE, hãy tạo listener instance mới khi reconnect.

## 📦 Artifact dự kiến

GitHub Release sẽ cung cấp `SHA256SUMS` và năm bridge binary được attest:

- `fbchat-bridge-e2ee-darwin-amd64`
- `fbchat-bridge-e2ee-darwin-arm64`
- `fbchat-bridge-e2ee-linux-amd64`
- `fbchat-bridge-e2ee-linux-arm64`
- `fbchat-bridge-e2ee-windows-amd64.exe`

Python wheel `fbchat_v2-2.3.0-py3-none-any.whl` và source distribution
`fbchat_v2-2.3.0.tar.gz` được publish qua PyPI, không phải GitHub Release asset.

## ✅ Release gate

Mỗi tag release phải vượt qua:

- compileall, Ruff, Black và mypy cho Python source cùng release tooling;
- pytest trên Python 3.10, 3.11, 3.12, 3.13 và 3.14;
- build, metadata check và clean-install smoke cho wheel/sdist;
- Go test, vet và race detector;
- native JSON-RPC smoke trên Linux, Windows và macOS;
- đối chiếu đúng năm bridge binary, `SHA256SUMS` và checksum nhúng trong package;
- provenance attestation trước khi publish GitHub Release và PyPI.

Source và mọi thay đổi version trên `main` đều phải vượt qua quality gate hiện
hành. Artifact `v2.3.0`, post-release clean install và canary tài khoản Facebook
thật vẫn phải được xác minh sau khi tạo tag và chạy release workflow.

## ⚠️ Giới hạn đã biết

- `fbchat-v2` sử dụng Facebook API không chính thức; login, HTML token, GraphQL
  và MQTT có thể thay đổi mà không báo trước.
- Watchdog có thể phục hồi process hoặc network failure, nhưng không thể sửa
  cookie hết hạn, account checkpoint hay protocol bridge không tương thích.
- Chưa có bằng chứng canary tài khoản thật 30–60 phút cho receive/reply,
  reconnect, media và Ctrl+C cleanup của bản `v2.3.0`.
- Không phải mọi Go RPC đều có convenience wrapper phía Python; có thể dùng
  `BridgeActions` hoặc bổ sung wrapper có type rõ ràng.

## 🔗 Tài liệu

- [README tiếng Việt](../README.md)
- [README English](../README_EN.md)
- [Hướng dẫn sử dụng](../DOCS.md)
- [E2EE bridge](../bridge-e2ee/README.md)
- [Changelog](../CHANGELOG.md)
