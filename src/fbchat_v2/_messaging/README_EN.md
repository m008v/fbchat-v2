# `_messaging` — Messaging Layer

> Every direct Messenger operation: send, realtime listen, upload, react, unsend, message requests.

[![Layer](https://img.shields.io/badge/layer-messaging-EC4899)](.)
[![Status](https://img.shields.io/badge/status-stable-22c55e)](.)
[![Vietnamese](https://img.shields.io/badge/docs-Ti%E1%BA%BFng%20Vi%E1%BB%87t-blue)](README.md)

---

## 📑 Table of Contents

- [Responsibilities](#-responsibilities)
- [Installation](#-installation)
- [Folder Structure](#-folder-structure)
- [Public API](#-public-api)
- [The `dataFB` Contract](#-the-datafb-contract)
- [Module Reference](#-module-reference)
  - [`_send.py`](#sendpy)
  - [`_listening.py`](#listeningpy)
  - [`_listening_e2ee.py`](#listening_e2eepy)
  - [`_attachments.py`](#attachmentspy)
  - [`_reactions.py`](#reactionspy)
  - [`_unsend.py`](#unsendpy)
  - [`_message_requests.py`](#message_requestspy)
- [Dependency Map](#-dependency-map)
- [Examples](#-examples)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Responsibilities

`_messaging` wraps Messenger endpoints into ergonomic Python functions/classes. It does **not** manage session/token concerns (that's `_core`):

- 📤 Send text messages to a user or a thread.
- 📎 Upload attachments for Messenger sending.
- 📡 Listen to realtime events through **MQTT over WebSocket**.
- ❤️ Add / remove reactions.
- ↩️ Unsend messages.
- 📥 Fetch **Message Requests** (pending messages).

---

## 📦 Installation

`_messaging` ships as part of the `fbchat-v2` source tree — you do not install it on its own. This section lists **what the module needs** at runtime.

### 1. Python dependencies (already in `requirements.txt`)

| Package | Used by | Notes |
|---|---|---|
| `requests` | `_send` · `_attachments` · `_reactions` · `_unsend` · `_message_requests` | HTTP client |
| `paho-mqtt` | `_listening` | MQTT over WebSocket |
| `attrs` | `_listening` | Decorator class |

Quick install if you only want `_messaging`:

```bash
pip install requests paho-mqtt attrs
```

### 2. Go bridge for `_listening_e2ee` (optional)

Only needed if you use `listeningE2EEEvent` to receive 1-on-1 (E2EE) messages. Requires **Go ≥ 1.24** and **Git**.

```bash
cd ../../bridge-e2ee            # from fbchat-v2/src/_messaging/
git clone https://github.com/mautrix/meta.git ./meta
go mod tidy

# Windows
go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee.exe .
# Linux / macOS
go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee .
```

The Python wrapper resolves the binary in this order:

1. The `FBCHAT_E2EE_BIN` env var (if set).
2. `fbchat-v2/build/fbchat-bridge-e2ee[.exe]` (default).

If the binary is missing, `_listening_e2ee` raises `FileNotFoundError` with build instructions.

### 3. `dataFB` from `_core`

Every `_messaging` function takes a `dataFB` produced by `_core._session.dataGetHome(setCookies)` — see [`_core/README_EN.md`](../_core/README_EN.md#-the-datafb-contract).

Full setup walkthrough (clone, venv, Go toolchain, smoke test): see [the root README § Installation](../../README_EN.md#-installation).

---

## 📂 Folder Structure

```text
src/_messaging/
├── __init__.py
├── _attachments.py        # Upload file → attachmentID
├── _listening.py          # MQTT realtime listener (group messages)
├── _listening_e2ee.py     # Go bridge — E2EE listener (1-on-1 messages)
├── _message_requests.py   # Pending messages
├── _reactions.py          # Add / remove reactions
├── _send.py               # Send messages (HTTP)
├── _unsend.py             # Unsend messages
├── README.md
└── README_EN.md           # ← you are here
```

---

## 📦 Public API

```python
# src/_messaging/__init__.py
__all__ = [
    "_attachments", "_listening", "_reactions",
    "_send", "_unsend", "_message_requests",
]
```

Import via `_messaging._send`, `_messaging._listening`, … to use each module.

---

## 🧩 The `dataFB` Contract

Every `_messaging` API requires **`dataFB`** — produced by `_core._session.dataGetHome(setCookies)`.

Frequently used keys: `fb_dtsg` · `jazoest` · `FacebookID` · `clientRevision` · `cookieFacebook`.

> 📖 Full schema: [`_core/README_EN.md`](../_core/README_EN.md#-the-datafb-contract).

---

## 📚 Module Reference

### `_send.py`

#### `class api`

The main message-sending module.

```python
api().send(
    dataFB,
    contentSend,
    threadID,
    typeAttachment=None,
    attachmentID=None,
    typeChat=None,
    replyMessage=None,
    messageID=None,
)
```

| Param | Description |
|---|---|
| `contentSend` | Message body. |
| `threadID` | Target group or user ID. |
| `typeChat` | `"user"` for 1-on-1; `None` for thread/group. |
| `typeAttachment` | `"gif"` · `"image"` · `"video"` · `"file"` · `"audio"`. |
| `attachmentID` | Upload ID returned by `_attachments`. |
| `replyMessage` + `messageID` | For reply flows. |

**Returns:**

- ✅ `{ "success": 1, "payload": { "messageID": ..., "timestamp": ... } }`
- ❌ `{ "error": 1, "payload": { "error-decription": ..., "error-code": ... } }`

> 📝 The module auto-generates `offline_threading_id`, `message_id`, `threading_id`. Responses from `/messaging/send/` carry a `for (;;);` prefix — already stripped.

---

### `_listening.py`

#### `class listeningEvent(dataFB)`

Listens for realtime events via **MQTT over WebSocket** (`wss://edge-chat.facebook.com/...`).

| Method | Description |
|---|---|
| `get_last_seq_id()` | Fetches & updates the latest `last_seq_id`. |
| `connect_mqtt()` | Initializes the MQTT client, subscribes to the sync queue, receives deltas. **Blocking** (`loop_forever()`). |

**Event payload** — `self.bodyResults` exposes:

```text
body · timestamp · userID · messageID · replyToID · type
attachments.id · attachments.url
```

**Highlights:**

- Built-in **reconnect** on unexpected disconnect.
- Handles `errorCode == 100` (queue overflow) by resetting sync state.
- Because `connect_mqtt()` is blocking, run it in a **dedicated thread / process**.

---

### `_listening_e2ee.py`

#### `class listeningE2EEEvent(dataFB, *, log_level="none", binary=None)`

Listens to **E2EE** (1-on-1) Messenger messages by spawning the Go binary `fbchat-bridge-e2ee` as a subprocess. The exposed event payload is **identical** to [`_listening.py`](#listeningpy), so you can swap implementations without changing your handler logic.

| Method | Description |
|---|---|
| `get_last_seq_id()` | Prints the latest `last_seq_id` (parity with `_listening.py`). |
| `connect_mqtt()` | Spawns the bridge, signs in, streams decrypted E2EE messages. **Blocking**. |
| `on_message(fn)` | Decorator/handler: receives a `dict` event (already decrypted). |
| `stop()` | Stops the bridge and closes the subprocess. |

**Event payload** — `self.bodyResults` exposes the same shape as `_listening.py`:

```text
body · timestamp · userID · messageID · replyToID · type
attachments.id · attachments.url
```

`self.e2eeBodyResults` adds Signal metadata: `chatJid` · `senderJid`.

**Requirements:**

- Binary at `fbchat-v2/build/fbchat-bridge-e2ee[.exe]`, or a path provided via `FBCHAT_E2EE_BIN`.
- Build instructions: [`bridge-e2ee/README.md`](../../bridge-e2ee/README.md).

---

### `_attachments.py`

```python
_uploadAttachment(filenames, dataFB)
```

Uploads files to `https://upload.facebook.com/ajax/mercury/upload.php` and returns the `attachmentID`.

**Returns:**

```python
{
    "attachmentID": ...,
    "attachmentUrl": ...,
    "attachmentType": ...,
    "attachmentDataSend": None,
}
```

> ⚠️ One call = one file. On failure the function prints to stdout instead of raising a detailed exception.

---

### `_reactions.py`

```python
func(dataFB, typeAdded, messageID, emojiChoice)
```

Add / remove a reaction on a message.

| Param | Value |
|---|---|
| `typeAdded` | `"add"` to add; any other value removes. |
| `messageID` | Target message ID. |
| `emojiChoice` | Reaction emoji. |

**Returns:** raw `requests.Response` — parse `response.text` yourself for details.

---

### `_unsend.py`

```python
func(messageID, dataFB)
```

Unsend a message by `messageID`. Endpoint: `/messaging/unsend_message/`.

- ✅ `{ "success": 1, "messages": "Message unsent successfully." }`
- ❌ returns `Exception({...})`.

---

### `_message_requests.py`

```python
func(dataFB)
```

Fetch pending message requests (`PENDING`).

- ✅ `{ "success": 1, "messageRequests": "<formatted json string>" }`

Includes sender list, snippet, timestamp, and `total_count`.

---

## 🔗 Dependency Map

`_messaging` mainly depends on `_core`:

```text
_core._session.dataGetHome(setCookies)  →  dataFB
_core._utils  →  formAll · mainRequests · gen_threading_id
                 generate_session_id · generate_client_id · json_minimal
                 str_base · get_files_from_paths · Headers · parse_cookie_string
```

**External libraries:** `requests`, `paho-mqtt`.

> `_listening_e2ee.py` additionally requires the Go binary `fbchat-bridge-e2ee` (subprocess, not a Python dependency).

---

## 💡 Examples

### Send a text message

```python
from _messaging._send import api

sender = api()
print(sender.send(dataFB, "Hello", "1234567890"))
```

### Upload an image then send it

```python
from _messaging._attachments import _uploadAttachment
from _messaging._send import api

uploaded = _uploadAttachment("path/to/image.jpg", dataFB)
sender = api()
print(sender.send(
    dataFB,
    "Here is your image",
    "1234567890",
    typeAttachment="image",
    attachmentID=uploaded["attachmentID"],
))
```

### React to a message

```python
from _messaging._reactions import func

resp = func(dataFB, "add", "mid.$abc...", "👍")
print(resp.status_code, resp.text)
```

### Unsend a message

```python
from _messaging._unsend import func
print(func("mid.$abc...", dataFB))
```

### Fetch pending requests

```python
from _messaging._message_requests import func
print(func(dataFB))
```

### Listen in realtime

```python
import threading
from _messaging._listening import listeningEvent

listener = listeningEvent(dataFB)
listener.get_last_seq_id()
threading.Thread(target=listener.connect_mqtt, daemon=True).start()
```

### Listen in realtime (E2EE / 1-on-1)

```python
import threading
from _messaging._listening_e2ee import listeningE2EEEvent

listener = listeningE2EEEvent(dataFB)
listener.get_last_seq_id()

@listener.on_message
def handle(evt):
    print(listener.bodyResults)        # same schema as _listening.py
    print(listener.e2eeBodyResults)    # chatJid / senderJid

threading.Thread(target=listener.connect_mqtt, daemon=True).start()
```

---

## 🛠 Troubleshooting

| Symptom | Suggested fix |
|---|---|
| Sending fails | Check cookies & `dataFB`; verify `threadID`/`userID`; ensure `typeAttachment` matches the uploaded file. |
| Upload fails | Verify path exists & is readable; inspect upload response (Facebook may rename keys). |
| Listener disconnects / receives no events | Run in a dedicated thread (`loop_forever()` is blocking); inspect MQTT `errorCode`; mind `errorCode == 100` (queue overflow). |
| JSON parse errors | Strip the `for (;;);` prefix before `json.loads`. |
| `FileNotFoundError` from `_listening_e2ee` | Build the `fbchat-bridge-e2ee` binary (see `bridge-e2ee/README.md`) or set the `FBCHAT_E2EE_BIN` env var. |
| Bridge crashes inside `connect_mqtt()` | Verify cookies are still valid, inspect stderr (logged by default), and retry after re-authenticating to Messenger. |

---

<div align="right">

⬆️ [Back to main README](../../README_EN.md) · 🇻🇳 [Tiếng Việt](README.md)

</div>
