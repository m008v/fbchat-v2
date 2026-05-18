# `_messaging` — Messaging Layer

> Every direct Messenger operation: send, edit, realtime listen, upload, react, unsend, change themes, message requests.

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
  - [`_editMessage.py`](#editmessagepy)
  - [`_send_e2ee.py`](#send_e2eepy)
  - [`_listening.py`](#listeningpy)
  - [`_listening_e2ee.py`](#listening_e2eepy)
  - [`_attachments.py`](#attachmentspy)
  - [`_reactions.py`](#reactionspy)
  - [`_changeTheme.py`](#changethemepy)
  - [`_unsend.py`](#unsendpy)
  - [`_message_requests.py`](#message_requestspy)
  - [`_createNotes.py`](#createnotespy)
- [Dependency Map](#-dependency-map)
- [Examples](#-examples)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Responsibilities

`_messaging` wraps Messenger endpoints into ergonomic Python functions/classes. It does **not** manage session/token concerns (that's `_core`):

- 📤 Send text messages to a user or a thread.
- ✏️ Edit sent messages through MQTT LS tasks.
- 📎 Upload attachments for Messenger sending.
- 📡 Listen to realtime events through **MQTT over WebSocket**.
- ❤️ Add / remove reactions.
- 🎨 Change a Messenger thread theme / background.
- ↩️ Unsend messages.
- 📥 Fetch **Message Requests** (pending messages).
- 📝 Manage **Messenger Notes** (24h status-style notes): check / create / delete / recreate.

---

## 📦 Installation

`_messaging` ships as part of the `fbchat-v2` source tree — you do not install it on its own. This section lists **what the module needs** at runtime.

### 1. Python dependencies (already in `requirements.txt`)

| Package | Used by | Notes |
|---|---|---|
| `requests` | `_send` · `_attachments` · `_reactions` · `_unsend` · `_message_requests` · `_createNotes` · `_changeTheme` | HTTP client |
| `paho-mqtt` | `_listening` · `_editMessage` · `_changeTheme` | MQTT over WebSocket / LS task |
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
├── _changeTheme.py        # Change Messenger thread theme / background
├── _createNotes.py        # Messenger Notes (24h status): check/create/delete/recreate
├── _editMessage.py        # Edit sent messages through MQTT LS task
├── _listening.py          # MQTT realtime listener (group messages)
├── _listening_e2ee.py     # Go bridge — E2EE listener (1-on-1 messages)
├── _message_requests.py   # Pending messages
├── _reactions.py          # Add / remove reactions
├── _send.py               # Send messages (HTTP)
├── _send_e2ee.py          # Go bridge — E2EE sender (1-on-1 Secret Conversations)
├── _unsend.py             # Unsend messages
├── README.md
└── README_EN.md           # ← you are here
```

---

## 📦 Public API

```python
# src/_messaging/__init__.py
__all__ = [
    "_attachments", "_changeTheme", "_createNotes", "_editMessage",
    "_listening", "_listening_e2ee", "_reactions", "_send",
    "_send_e2ee", "_unsend", "_message_requests",
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

### `_editMessage.py`

Edit a sent message by publishing an MQTT LS task with
`queue_name="edit_message"`.

```python
from _messaging import _editMessage

_editMessage.editMessage(dataFB, messageID="mid.$abc...", newText="Edited content")

# Or use the unified entry point:
_editMessage.func(dataFB, "mid.$abc...", "Edited content")
```

| Function | Description |
|---|---|
| `editMessage(dataFB, messageID, newText, timeout=20)` | Publishes the LS task that edits a message. |
| `func(dataFB, messageID, newText, timeout=20)` | Alias matching the fbchat-v2 module style. |

**Returns:**

- ✅ `{ "success": 1, "messages": "...", "data": { "messageID": ..., "text": ... } }`
- ❌ `{ "error": 1, "messages": "...", "payload": {...} }`

> ⚠️ Facebook usually only allows editing messages sent by the current
> account. Success here means the LS task was published to `/ls_req`; the
> server can still reject old messages or messages you do not own.

---

### `_send_e2ee.py`

#### `class api`

E2EE counterpart of `_send.api` — sends text messages into 1-on-1 Secret
Conversations through the Go bridge (`fbchat-bridge-e2ee`). Same return
schema as `_send.api.send` so caller code does not need a special branch.

Two construction modes:

```python
# A) Reuse the listener's bridge — RECOMMENDED.
#    No extra pairing handshake; no "new device" notification on the peer.
sender = api(listener=listeningE2EEEvent_instance)

# B) Standalone — spawn a private bridge process.
sender = api(
    dataFB=dataFB,
    log_level="warn",
    device_path=None,        # set to a path + e2ee_memory_only=False to persist Signal keys
    e2ee_memory_only=True,
    binary_path=None,        # auto-resolves build/fbchat-bridge-e2ee[.exe]
)
sender.connect()             # blocking pairing — only for standalone
```

| Method | Description |
|---|---|
| `send(chat_jid, contentSend, replyMessage="", replySenderJid="")` | Send one E2EE text message. `chat_jid` is a Signal JID like `<id>@s.whatsapp.net` — copy from `evt["data"]["chatJid"]`, do **not** construct it from a numeric `threadID`. |
| `reply(evt_data, contentSend)` | Helper that pulls `chatJid`, `id`, `senderJid` from a listener event and quote-replies in one call. |
| `connect(*, enable_e2ee=True, timeout=120)` | Standalone-only. Calls `newClient` → `connect` → `connectE2EE` on the bridge. |
| `close()` | Standalone-only. Stops the owned bridge subprocess. |
| `__enter__` / `__exit__` | Standalone context-manager support — auto `connect()` + `close()`. |

**Returns** — same shape as [`_send.py`](#sendpy):

- ✅ `{ "success": 1, "payload": { "messageID": ..., "timestamp": ... } }`
- ❌ `{ "error": 1, "payload": { "error-decription": ..., "error-code": "bridge_error" | "not_connected" } }`

> ⚠️ E2EE media sending (`SendE2EEImage` / `Video` / `Audio`) is implemented
> in the Go bridge but not yet exposed by the Python wrapper — text only for now.

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

### `_changeTheme.py`

List Messenger themes and change a thread theme / background through MQTT LS
tasks. This ports the `ws3-fca/theme.js` flow into the fbchat-v2 style.

```python
from _messaging import _changeTheme

_changeTheme.listThemes(dataFB)
_changeTheme.findTheme(dataFB, "love")
_changeTheme.changeTheme(dataFB, threadID="1234567890", themeName="love")

# Unified entry point:
_changeTheme.func(dataFB, action="list")
_changeTheme.func(dataFB, "1234567890", "default")
```

| Function | Description |
|---|---|
| `listThemes(dataFB)` | Calls GraphQL `MWPThreadThemeQuery_AllThemesQuery` to fetch available themes. |
| `findTheme(dataFB, themeName)` | Matches by ID, exact name, or partial keyword. |
| `changeTheme(dataFB, threadID, themeName, initiatorID=None, timeout=20)` | Publishes 4 LS tasks that update the thread theme. |
| `func(dataFB, threadID=None, themeName=None, action="set", **kwargs)` | Unified entry point: `list` / `find` / `set`. |

**Returns:**

- ✅ `{ "success": 1, "messages": "...", "data": { "threadID": ..., "themeID": ..., "themeName": ... } }`
- ❌ `{ "error": 1, "messages": "...", "details"|"payload"|"raw": ... }`

**Internals:**

- `listThemes` uses GraphQL `doc_id=24474714052117636`.
- `changeTheme` publishes 4 queues: `ai_generated_theme`,
  `msgr_custom_thread_theme`, `thread_theme_writer`, `thread_theme`.

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

### `_createNotes.py`

Manage **Messenger Notes** — the 24-hour status-style notes shown at the
top of the Messenger inbox. Ported from `ws3-fca/notes.js`
(@ChoruOfficial) into the fbchat-v2 style.

```python
from _messaging import _createNotes

_createNotes.checkNote(dataFB)
_createNotes.createNote(dataFB, text, privacy="FRIENDS")
_createNotes.deleteNote(dataFB, noteID)
_createNotes.recreateNote(dataFB, oldNoteID, newText, privacy="FRIENDS")

# Or use the unified entry point:
_createNotes.func(dataFB, action="check")
_createNotes.func(dataFB, action="create",   text="Hello", privacy="FRIENDS")
_createNotes.func(dataFB, action="delete",   noteID="<note_id>")
_createNotes.func(dataFB, action="recreate", oldNoteID="<id>", newText="...")
```

| Function | Description |
|---|---|
| `checkNote(dataFB)` | Returns the current note of the logged-in account (`msgr_user_rich_status`). |
| `createNote(dataFB, text, privacy="FRIENDS")` | Creates a new text note with a 86400s (24h) lifetime. |
| `deleteNote(dataFB, noteID)` | Deletes a note by `rich_status_id`. |
| `recreateNote(dataFB, oldNoteID, newText, privacy="FRIENDS")` | Deletes the old note then creates a new one (atomic 2-step). |
| `func(dataFB, action, **kwargs)` | Unified entry point — `action` ∈ `"check" / "create" / "delete" / "recreate"`. |

**`privacy` argument** (case-insensitive):

| Input | Mapped to |
|---|---|
| `"FRIENDS"` *(default)* | `FRIENDS` |
| `"EVERYONE"` · `"PUBLIC"` | `FRIENDS` *(Messenger Notes currently only support FRIENDS)* |
| Other | Kept as-is in UPPERCASE |

**Returns:**

- ✅ `{ "success": 1, "messages": "...", "data": {...} }`
- ❌ `{ "error": 1, "messages": "...", "details"|"raw": ... }`

**Internals:**

- Calls 3 separate GraphQL `friendly_name` / `doc_id` (check / create / delete).
- Has **timeout** `(connect=10s, read=45s)` and up to **2 retries** for
  `requests.Timeout` / `requests.RequestException`.
- Auto-strips Facebook's `for (;;);` response prefix before `json.loads`.
- `client_mutation_id` is a random 0–10 int; `session_id` is generated by
  `_core._utils.generate_client_id()`.

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

> `_listening_e2ee.py` **and** `_send_e2ee.py` additionally require the Go binary `fbchat-bridge-e2ee` (subprocess, not a Python dependency). `_send_e2ee.py` re-uses `_BridgeProcess`, `_resolve_binary` and `parse_cookie_string` from `_listening_e2ee.py` — both modules can share a single bridge instance.

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

### Edit a sent message

```python
from _messaging import _editMessage

print(_editMessage.editMessage(dataFB, "mid.$abc...", "Edited content"))
```

### Change a thread theme / background

```python
from _messaging import _changeTheme

print(_changeTheme.func(dataFB, action="list"))
print(_changeTheme.changeTheme(dataFB, "1234567890", "love"))
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

### Create / delete a Messenger Note (24h status)

```python
from _messaging import _createNotes

# Inspect the current note
print(_createNotes.checkNote(dataFB))

# Create a new note (default 24h lifetime, privacy FRIENDS)
created = _createNotes.createNote(dataFB, "Coding fbchat-v2 ❤️")
note_id = created["data"]["id"]

# Delete the note
_createNotes.deleteNote(dataFB, note_id)

# Or replace the old note with a new one in a single call
_createNotes.recreateNote(dataFB, note_id, "Shipped v2.1.3 🎉")
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

### Send an E2EE message (reuse listener's bridge)

```python
import threading
from _messaging._listening_e2ee import listeningE2EEEvent
from _messaging._send_e2ee import api as E2EESender

listener = listeningE2EEEvent(dataFB)
threading.Thread(target=listener.connect_mqtt, daemon=True).start()
# (wait for the "e2eeConnected" event before sending)

sender = E2EESender(listener=listener)

@listener.on_message
def on_msg(evt):
    if evt["type"] == "e2eeMessage" and evt["data"].get("text") == "ping":
        print(sender.reply(evt["data"], "pong"))
        # → {'success': 1, 'payload': {'messageID': '3EB0…', 'timestamp': 1715000000000}}
```

### Send an E2EE message (standalone — no listener)

```python
from _messaging._send_e2ee import api as E2EESender

with E2EESender(dataFB=dataFB, log_level="warn") as sender:
    sender.send(
        chat_jid    = "100012345678@s.whatsapp.net",
        contentSend = "hello E2EE",
    )
```

---

## 🛠 Troubleshooting

| Symptom | Suggested fix |
|---|---|
| Sending fails | Check cookies & `dataFB`; verify `threadID`/`userID`; ensure `typeAttachment` matches the uploaded file. |
| Upload fails | Verify path exists & is readable; inspect upload response (Facebook may rename keys). |
| `_editMessage` / `_changeTheme` times out while publishing | Check the cookie, WebSocket access to `edge-chat.facebook.com`, and your permission in the thread. |
| `_send_e2ee.api` returns `{"error": 1, ..., "error-code": "not_connected"}` | Standalone mode forgot `sender.connect()`; reuse mode means the listener's `connect_mqtt()` thread hasn't reached the `e2eeConnected` event yet. |
| `_send_e2ee.api` returns `{"error": 1, ..., "error-code": "bridge_error"}` | The Go bridge subprocess died or the JSON-RPC call failed — turn on `log_level="debug"` to see bridge stderr. |
| `ValueError: Phải truyền 'listener=' (reuse) HOẶC 'dataFB=' (standalone)` | Pass exactly one of `listener=` or `dataFB=` to `_send_e2ee.api(...)`. |
| Listener disconnects / receives no events | Run in a dedicated thread (`loop_forever()` is blocking); inspect MQTT `errorCode`; mind `errorCode == 100` (queue overflow). |
| JSON parse errors | Strip the `for (;;);` prefix before `json.loads`. |
| `FileNotFoundError` from `_listening_e2ee` | Build the `fbchat-bridge-e2ee` binary (see `bridge-e2ee/README.md`) or set the `FBCHAT_E2EE_BIN` env var. |
| Bridge crashes inside `connect_mqtt()` | Verify cookies are still valid, inspect stderr (logged by default), and retry after re-authenticating to Messenger. |

---

<div align="right">

⬆️ [Back to main README](../../README_EN.md) · 🇻🇳 [Tiếng Việt](README.md)

</div>
