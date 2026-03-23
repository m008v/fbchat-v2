# _messaging (`src/_messaging`)

`_messaging` is the layer that implements messaging capabilities.
This folder focuses on direct Messenger operations and does not manage
session/token infrastructure like `_core`.

- Send text messages to a user or a thread.
- Upload attachments to send through Messenger.
- Listen to realtime message events through MQTT over WebSocket.
- Add or remove message reactions.
- Unsend messages.
- Retrieve pending messages (Message Requests).

---

## 1) Folder structure

```text
src/_messaging/
├── __init__.py
├── _attachments.py
├── _listening.py
├── _message_requests.py
├── _reactions.py
├── _send.py
├── _unsend.py
└── README.md
```

### Main exports

`src/_messaging/__init__.py` currently exports:

```python
__all__ = [
    "_attachments",
    "_listening",
    "_reactions",
    "_send",
    "_unsend",
    "_message_requests",
]
```

This means you can import from `_messaging` and access the core messaging modules directly.

---

## 2) Primary responsibility (**IMPORTANT**): `_messaging_`

### `_messaging` is used to:

- Wrap Messenger endpoints into callable Python functions/classes.
- Reuse `dataFB` from `_core._session` for request authentication.
- Standardize send/listen/reaction/unsend operations by separate modules.
- Support both synchronous (HTTP) and realtime (MQTT) bot/tool workflows.

---

## 3) Shared input data (**IMPORTANT**): `dataFB`

Most APIs in `_messaging` accept `dataFB` as a required input.

### Commonly used fields

- `fb_dtsg`
- `jazoest`
- `FacebookID`
- `clientRevision`
- `cookieFacebook`

`dataFB` is created by `_core._session.dataGetHome(setCookies)`.

---

## 4) Detailed module reference

## 4.1 `_send.py`

### Class: `api`

This is the main message-sending module.

### Key method: `send(...)`

```python
send(
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

### Input

- `contentSend`: message content.
- `threadID`: target group/thread ID or user ID.
- `typeChat`:
  - `"user"`: send direct message to a user.
  - `None`: send to a thread/group.
- `typeAttachment`: attachment type. Supported values:
  - `"gif"`, `"image"`, `"video"`, `"file"`, `"audio"`
- `attachmentID`: uploaded attachment ID (from `_attachments.py`).
- `replyMessage` + `messageID`: used for reply flows.

### Output

- Success:
  - `{ "success": 1, "payload": { "messageID": ..., "timestamp": ... } }`
- Failure:
  - `{ "error": 1, "payload": { "error-decription": ..., "error-code": ... } }`

### Notes

- The module auto-generates `offline_threading_id`, `message_id`, and `threading_id`.
- Responses from `/messaging/send/` are prefixed with `for (;;);`; the module strips this prefix before `json.loads`.

---

## 4.2 `_listening.py`

### Class: `listeningEvent`

This module listens for realtime message events through MQTT over WebSocket
(`wss://edge-chat.facebook.com/...`).

### Initialization

```python
listeningEvent(dataFB)
```

### Main functions

- `get_last_seq_id()`
  - Fetches and updates the latest `last_seq_id` from thread data.
- `connect_mqtt()`
  - Initializes MQTT client, publishes queue sync events, and receives message deltas.

### Received data shape

When a message event arrives, the class updates `self.bodyResults` with:

- `body`, `timestamp`, `userID`, `messageID`, `replyToID`, `type`
- `attachments.id`, `attachments.url`

### Highlights

- Includes reconnect handling for unexpected disconnects.
- Handles `errorCode == 100` (queue overflow) by resetting sync state.
- `connect_mqtt()` uses `loop_forever()`, so it is usually run in a dedicated thread/process.

---

## 4.3 `_attachments.py`

### Function: `func(filenames, dataFB)`

- Purpose: upload files to Facebook and return an `attachmentID` for message sending.
- Endpoint: `https://upload.facebook.com/ajax/mercury/upload.php`

### Input

- `filenames`: file path or list of paths to upload.
- `dataFB`: contains `cookieFacebook`, `fb_dtsg`, etc.

### Output

```python
{
    "attachmentID": ...,
    "attachmentUrl": ...,
    "attachmentType": ...,
    "attachmentDataSend": None,
}
```

### Notes

- The flow is commonly used as one upload request per call.
- On upload failure, the function currently prints an error instead of raising a detailed exception.

---

## 4.4 `_reactions.py`

### Function: `func(dataFB, typeAdded, messageID, emojiChoice)`

- Purpose: add or remove a reaction on a message.

### Input

- `messageID`: target message ID.
- `typeAdded`:
  - `"add"` => add reaction
  - any other value => remove reaction
- `emojiChoice`: reaction emoji.

### Output

- Returns `requests.Response` directly.
- Parse `response.text` if you need detailed status handling.

---

## 4.5 `_unsend.py`

### Function: `func(messageID, dataFB)`

- Purpose: unsend a message by `messageID`.
- Endpoint: `/messaging/unsend_message/`.

### Input

- `messageID`: target message ID.

### Output

- Success: `{ "success": 1, "messages": "Message unsent successfully." }`
- Error: returns `Exception({...})`.

---

## 4.6 `_message_requests.py`

### Function: `func(dataFB)`

- Purpose: fetch pending message requests (`PENDING`).

### Output

- Success:
  - `{ "success": 1, "messageRequests": "<formatted json string>" }`
- The content includes sender list, snippets, timestamps, and `total_count`.

---

## 5) Dependency map in the project

`_messaging` mainly depends on `_core._utils` and `dataFB`:

- `_core._session` -> `dataGetHome(setCookies)`
- `formAll`
- `mainRequests`
- `gen_threading_id`
- `generate_session_id`, `generate_client_id`, `json_minimal`
- `str_base`, `get_files_from_paths`
- `Headers`, `parse_cookie_string`

External libraries:

- `requests`
- `paho-mqtt`

---

## 6) Sample source code

## 6.1 Send a text message to a thread

```python
from _messaging._send import api

sender = api()
result = sender.send(dataFB, "Hello", "1234567890")
print(result)
```

## 6.2 Upload an image, then send it in a message

```python
from _messaging._attachments import func as upload_attachment
from _messaging._send import api

uploaded = upload_attachment("path/to/image.jpg", dataFB)

sender = api()
result = sender.send(
    dataFB,
    "Here is your image",
    "1234567890",
    typeAttachment="image",
    attachmentID=uploaded["attachmentID"],
)
print(result)
```

## 6.3 React to a message

```python
from _messaging._reactions import func

resp = func(dataFB, "add", "mid.$abc...", "\\U0001F44D")
print(resp.status_code, resp.text)
```

## 6.4 Unsend a message

```python
from _messaging._unsend import func

result = func("mid.$abc...", dataFB)
print(result)
```

## 6.5 Fetch pending message requests

```python
from _messaging._message_requests import func

result = func(dataFB)
print(result)
```

## 6.6 Listen for realtime messages

```python
from _messaging._listening import listeningEvent

listener = listeningEvent(dataFB)
listener.get_last_seq_id()
listener.connect_mqtt()  # blocking
```

---

## 7) Common issues and troubleshooting

### Case 1: message sending fails

- Check whether cookies are still valid and `dataFB` is still fresh.
- Verify `threadID`/`userID` format.
- If sending an attachment, verify `typeAttachment` matches the uploaded file type.

### Case 2: attachment upload fails

- Ensure the file path exists and is readable.
- Check filesystem permissions on the machine running the bot/tool.
- Inspect upload response shape because Facebook may change metadata keys.

### Case 3: listener disconnects or receives no events

- Run the listener in a dedicated thread/process (`loop_forever()` is blocking).
- Inspect MQTT payload logs for `errorCode`.
- For queue overflow (`errorCode = 100`), reset/reconnect is implemented, but monitoring is still recommended.

### Case 4: JSON parsing errors in responses

- Many endpoints return payloads prefixed with `for (;;);`.
- Remove the prefix before `json.loads`.