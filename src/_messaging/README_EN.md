# `_messaging` — async Messenger APIs

This layer sends and receives messages, attachments, reactions, notes, themes, and E2EE traffic. Build `dataFB` with `dataGetHome()` first.

## APIs

| Module | Async API |
|---|---|
| `_send.py` | `api().send(...)` |
| `_attachments.py` | `func(filenames, dataFB)` |
| `_reactions.py` | `func(dataFB, typeAdded, messageID, emojiChoice)` |
| `_unsend.py` | `func(messageID, dataFB)` |
| `_editMessage.py` | `func(dataFB, messageID, newText)` |
| `_message_requests.py` | `func(dataFB)` |
| `_createNotes.py` | `checkNote`, `createNote`, `deleteNote`, `recreateNote` |
| `_changeTheme.py` | `listThemes`, `findTheme`, `changeTheme` |
| `_listening.py` | `connect_mqtt`, `get_message`, `disconnect` |
| `_listening_e2ee.py` | `connect_mqtt`, `send_message`, `send_e2ee_message` |
| `_bridge_actions.py` | suffix-free async actions with explicit blocking helpers |

## Send and reply

```python
from _messaging._send import api as SendAPI

result = await SendAPI().send(
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

uploaded = await _attachments.func(["a.jpg", "b.jpg"], data_fb)
if uploaded and uploaded.get("attachmentID"):
    await SendAPI().send(
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
task = asyncio.create_task(listener.connect_mqtt())
try:
    while True:
        event = await listener.get_message(timeout=30)
        if event:
            print(event)
finally:
    await listener.disconnect()
    await task
```

`bodyResults` is only a compatibility snapshot. New bots must consume the queue through `get_message()` to survive bursts. `paho-mqtt` has a blocking loop, so the async adapter uses one dedicated worker thread; callbacks never reconnect recursively.

## E2EE

```python
import asyncio

from _messaging._listening_e2ee import listeningE2EEEvent

listener = listeningE2EEEvent(data_fb)
task = asyncio.create_task(listener.connect_mqtt())
try:
    await listener.send_e2ee_message(
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

await _editMessage.func(data_fb, "mid.$...", "New text")
await _reactions.func(data_fb, "ADD_REACTION", "mid.$...", "🔥")
await _unsend.func("mid.$...", data_fb)
await _createNotes.createNote(data_fb, "Online")
await _changeTheme.changeTheme(data_fb, "thread-id", "Love")
```

## Edge cases

- Listener task exits early: inspect its exception instead of leaving the bot silently stalled.
- Queue pressure: monitor `droppedMessages` and use a bounded larger queue when justified.
- Upload lacks `attachmentID`: do not call send.
- A successful LS publish only confirms delivery to `/ls_req`, not server-side application.
- E2EE bridge is not ready: wait for connection before sending.
- Shutdown: disconnect/stop first, then await the listener task.
