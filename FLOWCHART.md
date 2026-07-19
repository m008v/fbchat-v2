# fbchat-v2 - Sơ đồ luồng async

[README](README.md) | [Tài liệu API](DOCS.md) | [Mindmap](mindmap-mermaid.md)

Tài liệu này mô tả đường đi của dữ liệu trong runtime hiện tại. Worker thread chỉ xuất hiện ở boundary thư viện blocking; HTTP feature chạy native async qua `httpx`.

## 1. 🛤️ Luồng thư mục và dependency

```mermaid
flowchart TD
    App[src/main.py hoặc application] --> Core[src/_core]
    App --> Features[src/_features]
    App --> Messaging[src/_messaging]

    Features --> Core
    Messaging --> Core

    Core --> HTTP[httpx]
    Messaging --> MQTT[paho-mqtt]
    Messaging --> PyBridge[Python bridge wrapper]
    PyBridge <--> GoBridge[bridge-e2ee Go process]
    GoBridge --> Meta[mautrix-meta submodule]

    Tests[tests/] --> Core
    Tests --> Features
    Tests --> Messaging
```

Dependency phải đi một chiều. `_core` không import ngược `_features` hoặc `_messaging`.

## 2. 💾 Session bootstrap

```mermaid
flowchart TD
    A[Cookie string hoặc SessionStorage] --> B{Có cookie không?}
    B -- Không --> C[Log thiếu cookie và trả None]
    B -- Có --> D[parse_cookie_string]
    D --> E[GET facebook.com qua httpx]
    E --> F{HTTP thành công?}
    F -- Không --> G[Log lỗi an toàn và trả None]
    F -- Có --> H[Parse token từ HTML]
    H --> I{Đủ field bắt buộc và FacebookID là số?}
    I -- Không --> J[Log tên field thiếu và trả None]
    I -- Có --> K[dataFB]
    K --> L[_features]
    K --> M[_messaging]
```

`dataFB` chứa cookie và CSRF token. Mọi nhánh sau đó phải coi object này là secret.

## 3. 🌍 HTTP feature async

```mermaid
sequenceDiagram
    participant App
    participant Feature
    participant Utils as _core._utils
    participant Transport as _core._http
    participant Client as httpx.AsyncClient
    participant FB as Facebook endpoint

    App->>Feature: await func(dataFB, ..., client=client)
    Feature->>Feature: validate input
    Feature->>Feature: build request/form
    Feature->>Utils: send_request_async hoặc post_form_json_async
    Utils->>Transport: post_async/get_async
    Transport->>Client: await request
    Client->>FB: HTTPS request
    FB-->>Client: HTTP response
    Client-->>Transport: httpx.Response
    Transport-->>Utils: response
    Utils->>Utils: raise_for_status + parse JSON
    Utils-->>Feature: payload
    Feature->>Feature: validate error/data fields
    Feature-->>App: success hoặc error dict
```

Nếu caller không truyền client, transport tạo client tạm và đóng sau call. Với workflow nhiều request, caller nên sở hữu một `AsyncClient` dùng chung.

## 4. 💬 Gửi tin thường

```mermaid
flowchart TD
    A[SendAPI.send] --> B[Validate thread, type, reply, attachment]
    B --> C{Input hợp lệ?}
    C -- Không --> D[Raise ValueError]
    C -- Có --> E[Tạo form mới cho call]
    E --> F[Sinh threading/offline ID]
    F --> G[POST /messaging/send qua httpx]
    G --> H[Strip prefix for loop]
    H --> I{Payload có message_id?}
    I -- Có --> J[success + messageID + timestamp]
    I -- Không --> K[error + description + code]
```

Form không được lưu làm mutable state dùng chung. `sender.results` chỉ là snapshot compatibility.

## 5. 📎 Upload attachment

```mermaid
flowchart TD
    A[Path hoặc list path] --> B[Validate danh sách và file tồn tại]
    B --> C[Open file + đoán MIME]
    C --> D{Có AsyncClient do caller truyền?}
    D -- Có --> E[Multipart POST native async]
    D -- Không --> F[Compatibility upload trong worker thread]
    E --> G[Parse JSON/prefix]
    F --> G
    G --> H{metadata item là dict?}
    H -- Không --> I[None hoặc error diagnostics]
    H -- Có --> J[Extract attachment ID, URL, MIME]
    J --> K[Normalize typeAttachment]
    K --> L[Đóng toàn bộ file handle]
    I --> L
```

`uploadID` và `attachmentID` là hai giá trị khác nhau. Chỉ `attachmentID` hợp lệ mới được đưa vào send.

## 6. 📡 Listener MQTT thường

```mermaid
sequenceDiagram
    participant App
    participant Listener as listeningEvent
    participant Worker as MQTT worker
    participant Queue as bounded message queue
    participant FB as edge-chat.facebook.com

    App->>Listener: create_task(connect_mqtt())
    Listener->>Worker: asyncio.to_thread(connect_mqtt_blocking)
    Worker->>FB: TLS WebSocket connect + subscribe
    FB-->>Worker: MQTT deltas
    Worker->>Worker: parse toàn bộ deltas
    Worker->>Queue: enqueue từng event
    alt queue đầy
        Queue->>Queue: drop oldest
        Worker->>Worker: droppedMessages += 1
    end
    App->>Listener: await get_message(timeout)
    Listener->>Queue: dequeue
    Queue-->>App: normalized event hoặc None
    App->>Listener: await disconnect()
    Listener->>Worker: signal stop
```

Reconnect xảy ra ở vòng ngoài của listener. Callback chỉ signal state; không tự gọi đệ quy connection setup.

## 7. 🔐 E2EE startup

```mermaid
sequenceDiagram
    participant App
    participant Listener as listeningE2EEEvent
    participant Process as _BridgeProcess
    participant Go as fbchat-bridge-e2ee
    participant Meta as Messenger E2EE

    App->>Listener: đăng ký on_message callback
    App->>Listener: create_task(connect_mqtt())
    Listener->>Listener: resolve binary
    Listener->>Process: spawn subprocess
    Process->>Go: start stdin/stdout JSON-RPC
    Listener->>Process: newClient(cookie config)
    Process->>Go: request
    Go-->>Process: response
    Listener->>Process: connect
    Go->>Meta: regular Messenger connect
    Meta-->>Go: user/session info
    Go-->>Listener: connected
    Listener->>Listener: set connected event
    Listener->>Process: connectE2EE
    Go->>Meta: E2EE handshake
    Meta-->>Go: ready
    Go-->>Listener: e2eeConnected
    Listener->>Listener: set e2ee ready event
    App->>Listener: wait_until_connected qua to_thread
    Listener-->>App: True
```

Send trước bước readiness là race. `wait_until_connected` là blocking event wait nên application async gọi nó qua `asyncio.to_thread`.

## 8. 🔐 E2EE event delivery

```mermaid
sequenceDiagram
    participant FB as Messenger
    participant Go as Go bridge
    participant Reader as Python reader thread
    participant Poll as bridge poll loop
    participant Callback as on_message callback
    participant Loop as asyncio loop
    participant Queue as asyncio.Queue
    participant Bot

    FB-->>Go: encrypted/regular event
    Go->>Go: decrypt + normalize
    Go-->>Reader: JSON line with event
    Reader->>Poll: thread-safe event queue
    Poll->>Callback: callback(event)
    Callback->>Loop: call_soon_threadsafe(enqueue)
    Loop->>Queue: put_nowait
    Bot->>Queue: await get()
    Queue-->>Bot: event
    Bot->>Bot: filter, dedupe, dispatch command
```

Callback không `await` handler. Việc chuyển về event loop là responsibility của application, như pattern trong `src/main.py`.

## 9. 🔐 E2EE send/action

```mermaid
flowchart LR
    A[Async bot handler] --> B{Action}
    B -- Text E2EE --> C[listener.send_e2ee_message]
    B -- Text thường --> D[listener.send_message]
    B -- Edit/unsend/media --> E[BridgeActions async method]
    C --> F[_BridgeProcess.call]
    D --> F
    E --> F
    F --> G[Worker chờ call_blocking]
    G --> H[JSON-RPC request]
    H --> I[Go dispatcher]
    I --> J[Messenger protocol]
    J --> I
    I --> H
    H --> G
    G --> F
    F --> A
```

Binary media được base64 tại RPC boundary. JSON-RPC request bị giới hạn 150 MiB.

## 10. 🌉 Bridge watchdog

```mermaid
flowchart TD
    A[Bridge process exit] --> B{Listener đang stop?}
    B -- Có --> C[Kết thúc watchdog]
    B -- Không --> D{Đã đủ 5 retry?}
    D -- Có --> E[Emit bridge_fatal]
    D -- Không --> F[Đợi exponential backoff]
    F --> G[Respawn process]
    G --> H[Replay newClient + connect + connectE2EE]
    H --> I{Thành công?}
    I -- Có --> J[Reset retry count]
    I -- Không --> K[Tăng retry]
    J --> A
    K --> D
```

Application vẫn phải monitor listener task và `bridge_fatal`; watchdog không biến lỗi credential hoặc binary hỏng thành kết nối khỏe.

## 11. 🤖 Bot command flow

```mermaid
flowchart TD
    A[Raw bridge event] --> B{Type message/e2eeMessage?}
    B -- Không --> C[Log lifecycle hoặc bỏ qua]
    B -- Có --> D[Normalize message]
    D --> E{Có message ID và chưa thấy?}
    E -- Không --> F[Bỏ qua duplicate]
    E -- Có --> G{Sender là bot hoặc body rỗng?}
    G -- Có --> H[Bỏ qua]
    G -- Không --> I{Body bắt đầu bằng prefix?}
    I -- Không --> J[Không dispatch]
    I -- Có --> K[Parse command + argument]
    K --> L{Handler tồn tại?}
    L -- Không --> M[Log unknown command]
    L -- Có --> N[await handler]
    N --> O{Có chatJid?}
    O -- Có --> P[send_e2ee_message]
    O -- Không --> Q[send_message bằng threadId]
```

## 12. 📌 Shutdown

```mermaid
sequenceDiagram
    participant Signal as Ctrl+C/cancel
    participant App
    participant Listener
    participant Task
    participant Client as httpx.AsyncClient

    Signal->>App: cancellation
    App->>Listener: stop() hoặc await disconnect()
    Listener->>Task: signal worker/subprocess
    App->>Task: await với timeout
    alt task không dừng
        App->>Task: cancel
        App->>Task: await cancellation
    end
    App->>Client: exit async context
```

Không đóng client trước khi handler đang dùng xong. Không bỏ listener task chạy nền sau khi event loop kết thúc.

## 13. 🩺 Error boundary

```mermaid
flowchart TD
    A[Input] --> B{Validation}
    B -- Sai --> C[ValueError/NotImplementedError]
    B -- Đúng --> D[Transport]
    D --> E{HTTP/RPC error?}
    E -- Có --> F[HTTPError/BridgeError hoặc error dict]
    E -- Không --> G[Parser]
    G --> H{Schema hợp lệ?}
    H -- Không --> I[Error dict có message/excerpt an toàn]
    H -- Có --> J[Domain result]
    C --> K[Application boundary]
    F --> K
    I --> K
    J --> K
    K --> L[Log không chứa secret + quyết định retry/reply]
```

Không catch `Exception` rồi trả `{}`. Error boundary phải giữ đủ thông tin để caller phân biệt input, network, auth và schema failure.
