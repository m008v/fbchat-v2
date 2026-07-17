# `_messaging` — async Messenger APIs

This layer sends and receives messages, attachments, reactions, notes, themes, and E2EE traffic. Build `dataFB` with `dataGetHome_async()` first.

## APIs

| Module | Async API |
|---|---|
| `_send.py` | `api().send_async(...)` |
| `_attachments.py` | `func_async(filenames, dataFB)` |
| `_reactions.py` | `func_async(dataFB, typeAdded, messageID, emojiChoice)` |
| `_unsend.py` | `func_async(messageID, dataFB)` |
| `_editMessage.py` | `func_async(dataFB, messageID, newText)` |
| `_message_requests.py` | `func_async(dataFB)` |
| `_createNotes.py` | `checkNote_async`, `createNote_async`, `deleteNote_async`, `recreateNote_async` |
| `_changeTheme.py` | `listThemes_async`, `findTheme_async`, `changeTheme_async` |
| `_listening.py` | `connect_mqtt_async`, `get_message_async`, `disconnect_async` |
| `_listening_e2ee.py` | `connect_mqtt_async`, `send_message_async`, `send_e2ee_message_async` |
| `_bridge_actions.py` | action methods suffixed with `_async` |

## Send and reply

```python
from _messaging._send import api as SendAPI

result = await SendAPI().send_async(
    data_fb,
    "Hello",
    threadID="100012345678",
    typeChat="user",
    replyMessage=True,
    messageID="mid.$...",
)
```

Each call builds an independent form. During concurrent sends, use the returned value; `sender.results` is only the latest completed-call snapshot.

## Upload

```python
from _messaging import _attachments
from _messaging._send import api as SendAPI

uploaded = await _attachments.func_async(["a.jpg", "b.jpg"], data_fb)
if uploaded and uploaded.get("attachmentID"):
    await SendAPI().send_async(
        data_fb,
        "Two images",
        threadID="thread-id",
        typeAttachment="image",
        attachmentID=uploaded["attachmentID"],
    )
```

## Regular listener

```python
import asyncio

from _messaging._listening import listeningEvent

listener = listeningEvent(data_fb, message_queue_maxsize=1000)
task = asyncio.create_task(listener.connect_mqtt_async())
try:
    while True:
        event = await listener.get_message_async(timeout=30)
        if event:
            print(event)
finally:
    await listener.disconnect_async()
    await task
```

`bodyResults` is only a compatibility snapshot. New bots must consume the queue through `get_message_async()` to survive bursts. `paho-mqtt` has a blocking loop, so the async adapter uses one dedicated worker thread; callbacks never reconnect recursively.

## E2EE

```python
import asyncio

from _messaging._listening_e2ee import listeningE2EEEvent

listener = listeningE2EEEvent(data_fb)
task = asyncio.create_task(listener.connect_mqtt_async())
try:
    await listener.send_e2ee_message_async(
        "100012345678@msgr",
        "Encrypted message",
    )
finally:
    listener.stop()
    await task
```

`BridgeActions` exposes async edit/unsend/typing/mark-read, media send, and media download methods. Binary data is base64-encoded only at the JSON-RPC boundary.

## Notes, themes, and message actions

```python
from _messaging import _changeTheme, _createNotes, _editMessage, _reactions, _unsend

await _editMessage.func_async(data_fb, "mid.$...", "New text")
await _reactions.func_async(data_fb, "ADD_REACTION", "mid.$...", "🔥")
await _unsend.func_async("mid.$...", data_fb)
await _createNotes.createNote_async(data_fb, "Online")
await _changeTheme.changeTheme_async(data_fb, "thread-id", "Love")
```

## Edge cases

- Listener task exits early: inspect its exception instead of leaving the bot silently stalled.
- Queue pressure: monitor `droppedMessages` and use a bounded larger queue when justified.
- Upload lacks `attachmentID`: do not call send.
- A successful LS publish only confirms delivery to `/ls_req`, not server-side application.
- E2EE bridge is not ready: wait for connection before sending.
- Shutdown: disconnect/stop first, then await the listener task.
