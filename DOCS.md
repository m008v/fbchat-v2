# 📖 fbchat-v2 — Documentation

> Modern, account-based Python library for the **unofficial** Facebook Messenger API.
> Now with **End-to-End Encryption** support for 1-on-1 chats via a Go bridge.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Project layout](#2-project-layout)
3. [Installation & setup](#3-installation--setup)
4. [Authentication](#4-authentication)
   - [4.1 Login with cookies](#41-login-with-cookies)
   - [4.2 Login with username / password (+ 2FA)](#42-login-with-username--password--2fa)
   - [4.3 Verifying a session is alive](#43-verifying-a-session-is-alive)
5. [Receiving messages](#5-receiving-messages)
   - [5.1 Group messages — `listeningEvent` (MQTT)](#51-group-messages--listeningevent-mqtt)
   - [5.2 1-on-1 messages — `listeningE2EEEvent` (E2EE bridge)](#52-1-on-1-messages--listeninge2eeevent-e2ee-bridge)
6. [Sending messages](#6-sending-messages)
   - [6.1 Plain messages — `_send.api`](#61-plain-messages--_sendapi)
   - [6.2 E2EE messages — `_send_e2ee.api`](#62-e2ee-messages--_send_e2eeapi)
7. [Attachments — upload & send](#7-attachments--upload--send)
8. [Reactions](#8-reactions)
9. [Unsending a message](#9-unsending-a-message)
10. [Building the E2EE Go bridge](#10-building-the-e2ee-go-bridge)
11. [Reference: the `dataFB` dictionary](#11-reference-the-datafb-dictionary)
12. [FAQ](#12-faq)
13. [Author's note](#13-authors-note)

---

## 1. Introduction

**fbchat-v2** is a spiritual successor to the original [`fbchat`](https://github.com/fbchat-dev/fbchat). It authenticates as a **real Facebook user** (cookies or username / password) and talks to private Facebook endpoints — there is no Graph API key required, and there is **no rate-limiting from Meta's developer console** because Facebook does not know your code is a bot.

> ⚠️ **This project is not endorsed by Facebook.** Using it may violate Facebook's Terms of Service and can result in account flags, checkpoints, or permanent bans. We accept **no responsibility** for misuse — political spam, religious harassment, scraping at scale, or anything that violates local law.

Since November 2024 Facebook has rolled out **End-to-End Encryption (E2EE)** for all 1-on-1 Messenger chats. fbchat-v2 ≥ 2.1.0 ships an E2EE listener (`listeningE2EEEvent`) and sender (`_send_e2ee.api`) that decrypt and encrypt those messages by spawning a tiny Go binary built from `bridge-e2ee/`. Group / community messages still flow over the public MQTT WebSocket.

If you have any questions reach out on Telegram → [@MinhHuyDev](https://t.me/MinhHuyDev).

— *MinhHuyDev*

---

## 2. Project layout

```text
fbchat-v2/
├── src/                              # All Python source
│   ├── main.py                       # Entry-point demo bot
│   ├── config.json                   # Cookies + prefix + admins (gitignored)
│   ├── _core/                        # Layer 1 — session, login, utils
│   │   ├── _session.py               # dataGetHome(setCookies) → dataFB
│   │   ├── _facebookLogin.py
│   │   └── _utils.py
│   ├── _features/                    # Layer 2 — actions on FB & threads
│   │   ├── _facebook/                # post, bio, search, blocking, …
│   │   └── _thread/                  # admin, nickname, emoji, all-thread-data
│   └── _messaging/                   # Layer 3 — send / listen / react
│       ├── _send.py                  # class api  (plain)
│       ├── _send_e2ee.py             # class api  (E2EE)
│       ├── _attachments.py
│       ├── _reactions.py
│       ├── _message_requests.py
│       ├── _unsend.py
│       ├── _listening.py             # class listeningEvent
│       └── _listening_e2ee.py        # class listeningE2EEEvent
├── bridge-e2ee/                      # Go subprocess for E2EE crypto
└── build/fbchat-bridge-e2ee[.exe]    # Output of `go build`
```

The codebase is strictly layered. **Higher layers may import from lower; never the reverse.**

```
main.py → _core → _features  ↘
                  _messaging  → bridge-e2ee (subprocess)
```

---

## 3. Installation & setup

### From PyPI (recommended)

```bash
pip install fbchat-v2
```

This pulls `requests`, `paho-mqtt`, `attrs`, `pyotp`. The MQTT group-chat listener works out of the box. **For E2EE 1-on-1 chats** you must also build the Go bridge — see [§10](#10-building-the-e2ee-go-bridge).

### From source

```bash
git clone https://github.com/MinhHuyDev/fbchat-v2
cd fbchat-v2
pip install -r requirements.txt
```

Then make `src/` importable:

```powershell
# Windows PowerShell
$env:PYTHONPATH = "src"
python src\main.py

# Linux / macOS
export PYTHONPATH=src
python src/main.py
```

> 💡 If you want to run scripts **outside** `fbchat-v2/`, rename the folder from `fbchat-v2` to `fbchat_v2` (Python identifiers cannot contain `-`) and import as `from fbchat_v2.src._core._session import dataGetHome`. The PyPI distribution already does this for you under the package name `fbchat_v2`.

---

## 4. Authentication

> ⚠️ **Cookies are credentials.** Anyone holding `c_user` + `xs` can hijack your account. Never paste them into screenshots, public chats, or LLM prompts. Keep `config.json` out of Git.

### 4.1 Login with cookies

Easiest and most stable. Log in to Facebook in any browser, open **DevTools → Network**, copy the value of the `Cookie:` request header (the long `c_user=…; xs=…; datr=…; fr=…;` string).

```python
from _core._session import dataGetHome

setCookies = "c_user=61551671683861; xs=8:51DRVMpDOiHp1A:2:..."
dataFB = dataGetHome(setCookies)
print("Logged in as:", dataFB["FacebookID"])
```

### 4.2 Login with username / password (+ 2FA)

Useful for bootstrapping but more fragile (Facebook may issue a checkpoint).

```python
from _core import _facebookLogin

client = _facebookLogin.loginFacebook(
    username="minhhuydev@icloud.com",
    password="<your-password>",
    twofa=None,                # or your TOTP secret string
)
result = client.main()

if "success" not in result:
    raise SystemExit(
        f"Login failed: {result['error']['description']} "
        f"(code {result['error']['error_code']})"
    )

setCookies = result["success"]["setCookies"]
print(setCookies)
```

A successful response contains `setCookies`, an `accessTokenFB`, and the full `cookiesKey-ValueList`. A failure looks like:

```python
{'error': {'title': 'Wrong Credentials',
           'description': 'Invalid username or password',
           'error_subcode': 1348131,
           'error_code': 401,
           'fbtrace_id': 'AQ1wRUfc-SJoGJ4m4iXGy1B'}}
```

### 4.3 Verifying a session is alive

`dataGetHome` scrapes `fb_dtsg` & `jazoest` from `facebook.com`. If those exist you can issue authenticated POSTs:

```python
try:
    print(f"{dataFB['FacebookID']} → cookies are working ✅")
except KeyError:
    raise SystemExit("Cookies are DEAD ❌")
```

---

## 5. Receiving messages

Choose the listener that matches the conversation type:

| Listener | Module | Use for |
|---|---|---|
| `listeningEvent` | `_messaging._listening` | **Group chats** (still plain MQTT) |
| `listeningE2EEEvent` | `_messaging._listening_e2ee` | **1-on-1 chats** (E2EE — needs Go bridge) |

Both expose the **same `bodyResults` schema** so a single handler can consume either.

### 5.1 Group messages — `listeningEvent` (MQTT)

```python
import time, threading
from _core._session import dataGetHome
from _messaging._listening import listeningEvent

dataFB   = dataGetHome(setCookies)
listener = listeningEvent(dataFB)
listener.get_last_seq_id()                     # required before connect
threading.Thread(target=listener.connect_mqtt, daemon=True).start()

last_seen = None
while True:
    msg = listener.bodyResults
    if msg["messageID"] and msg["messageID"] != last_seen:
        last_seen = msg["messageID"]
        print(msg)
    time.sleep(0.3)
```

`bodyResults` is mutated in place each time a new event arrives:

```json
{
  "body": "hi from a group",
  "timestamp": "1702314310077",
  "userID": "1619995045",
  "messageID": "mid.$gABESRz00DD6SixxBvWMWdb3w_KEg",
  "replyToID": "4805171782880318",
  "type": "thread",
  "attachments": {
    "id": "...",
    "url": "https://scontent.xx.fbcdn.net/..."
  }
}
```

### 5.2 1-on-1 messages — `listeningE2EEEvent` (E2EE bridge)

```python
import threading
from _core._session import dataGetHome
from _messaging._listening_e2ee import listeningE2EEEvent

dataFB   = dataGetHome(setCookies)
listener = listeningE2EEEvent(
    dataFB,
    log_level="warn",        # "none" | "error" | "warn" | "info" | "debug"
    e2ee_memory_only=True,   # set False + device_path="./device.json" to persist keys
    enable_e2ee=True,
    binary_path=None,        # auto-resolves build/fbchat-bridge-e2ee[.exe]
)
listener.get_last_seq_id()
threading.Thread(target=listener.connect_mqtt, daemon=True).start()

@listener.on_message
def on_event(evt):
    etype, data = evt["type"], evt.get("data") or {}
    if etype == "e2eeMessage":
        print("[E2EE]", data["senderJid"], "→", data["text"])
    elif etype == "message":
        print("[plain]", data["senderId"], "→", data["text"])
```

Event types you can expect: `ready`, `e2eeConnected`, `message`, `e2eeMessage`, `reaction`, `e2eeReaction`, `messageEdit`, `messageUnsend`, `typing`, `readReceipt`, `disconnected`, `error`.

In addition to `bodyResults`, the E2EE listener exposes `e2eeBodyResults = {"chatJid": ..., "senderJid": ...}` so you can reply to encrypted DMs.

---

## 6. Sending messages

### 6.1 Plain messages — `_send.api`

```python
from _messaging import _send

sender = _send.api()

result = sender.send(
    dataFB,
    contentSend = "hello!",
    threadID    = 4805171782880318,
    typeChat    = None,        # "user" → DM, None → group/thread
    replyMessage= None,        # truthy + messageID = reply
    messageID   = None,
)
print(result)
# → {'success': 1, 'payload': {'messageID': 'mid.$cAABa-…', 'timestamp': 1702656627619}}
```

**Argument reference for `sender.send(...)`:**

| Argument | Type | Description |
|---|---|---|
| `dataFB` | dict | Session built by `dataGetHome()` |
| `contentSend` | str | Message body |
| `threadID` | int / str / list[str] | Group thread ID **or** user ID. List = broadcast to many users |
| `typeAttachment` | `"image"` / `"video"` / `"gif"` / `"audio"` / `"file"` / `None` | Required only if attaching |
| `attachmentID` | int / str / list | Returned by [`_attachments.func()`](#7-attachments--upload--send) |
| `typeChat` | `"user"` / `None` | `"user"` for DMs, anything else (or `None`) for groups |
| `replyMessage` | truthy / `None` | Truthy + `messageID` → quote-reply |
| `messageID` | str | The Mercury `mid.$…` of the message you are replying to |

> **Reply rule:** to **reply**, set both `replyMessage` (any truthy value, e.g. `1`) **and** `messageID`. To just send a normal message, leave `replyMessage=None`.

### 6.2 E2EE messages — `_send_e2ee.api`

`_send_e2ee.api` mirrors the API of `_send.api` but works through the Go bridge. There are two modes:

**Mode A — re-use the listener's bridge (recommended):**

```python
import threading
from _messaging._listening_e2ee import listeningE2EEEvent
from _messaging._send_e2ee import api as E2EESender

listener = listeningE2EEEvent(dataFB)
threading.Thread(target=listener.connect_mqtt, daemon=True).start()
# (wait for the "e2eeConnected" event)

sender = E2EESender(listener=listener)

@listener.on_message
def handler(evt):
    if evt["type"] == "e2eeMessage" and evt["data"]["text"] == "ping":
        sender.reply(evt["data"], "pong")     # auto-fills chatJid / id / senderJid
```

**Mode B — standalone (no listener):**

```python
from _messaging._send_e2ee import api as E2EESender

with E2EESender(dataFB=dataFB, log_level="warn") as sender:
    sender.send(
        chat_jid    = "100012345678@s.whatsapp.net",
        contentSend = "hello E2EE",
    )
```

Both modes return the same shape as `_send.api.send`:

```python
# success
{'success': 1, 'payload': {'messageID': '3EB0…', 'timestamp': 1715000000000}}

# failure
{'error':   1, 'payload': {'error-decription': 'bridge exited',
                           'error-code': 'bridge_error'}}
```

> 🔑 `chat_jid` is **not** a numeric thread ID — it is a Signal-style JID like `<id>@s.whatsapp.net`. Always copy it from `evt["data"]["chatJid"]` rather than constructing it yourself.

---

## 7. Attachments — upload & send

```python
from _messaging import _attachments, _send

upload = _attachments.func("mhuydev_profile_avatar.jpg", dataFB)
attachmentID = upload.get("attachmentID")

sender = _send.api()
sender.send(
    dataFB,
    contentSend    = "look at this",
    threadID       = 4805171782880318,
    typeAttachment = "image",         # MUST match the file kind
    attachmentID   = attachmentID,
)
```

**Match `typeAttachment` to the file extension:**

| `typeAttachment` | Extensions |
|---|---|
| `image` | `.jpg`, `.jpeg`, `.png` |
| `video` | `.mp4`, `.avi`, `.mkv` |
| `gif`   | `.gif` |
| `audio` | `.mp3`, `.wav`, `.flac` |
| `file`  | `.txt`, `.docx`, `.zip`, `.rar`, … |

E2EE media (`SendE2EEImage`, `SendE2EEVideo`, `SendE2EEAudio`) is implemented in the Go bridge but **not yet wired** into the Python wrapper — it will land in v2.2.x.

---

## 8. Reactions

```python
from _messaging import _reactions

# typeAdded: "added" or "removed"
_reactions.func(dataFB, typeAdded="added",
                messageID="mid.$cAABa-wot0daSn4Obo2Mbj5L5njhO",
                emojiChoice="❤")
```

For E2EE reactions, the Go bridge exposes `SendE2EEReaction` but the Python wrapper does not surface it yet — track [Issues](https://github.com/MinhHuyDev/fbchat-v2/issues) for progress.

---

## 9. Unsending a message

```python
from _messaging import _unsend

messageID = result["payload"]["messageID"]
print(_unsend.func(messageID, dataFB))
# → {'success': 1, 'messages': 'Thu hồi tin nhắn thành công.'}
```

---

## 10. Building the E2EE Go bridge

Required only if you intend to use `listeningE2EEEvent` or `_send_e2ee.api`.

**Prerequisites:** Go ≥ 1.24 ([go.dev/dl](https://go.dev/dl/)) and Git.

```powershell
cd fbchat-v2/bridge-e2ee
git clone https://github.com/mautrix/meta.git ./meta   # required by go.mod replace
go mod tidy
go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee.exe .   # Windows
# go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee .     # Linux / macOS
```

Override the auto-discovered binary path if needed:

```powershell
$env:FBCHAT_E2EE_BIN = "D:\bin\fbchat-bridge-e2ee.exe"
```

> Why Go and not pure Python? The cryptographic stack (Signal Protocol — Curve25519, Double Ratchet, Sender Keys, AES-GCM, Noise XX — wrapped in Meta's Labyrinth / Lightspeed protobufs) is ~100 k LoC. Python equivalents (`python-axolotl`, `dissononce`) have been unmaintained since 2019. Re-implementing them is a security and maintenance hazard.

---

## 11. Reference: the `dataFB` dictionary

`dataGetHome(setCookies)` returns this dict, which is the **first argument to almost every function** in the codebase:

| Key | Description |
|---|---|
| `FacebookID` | Authenticated user's numeric ID |
| `fb_dtsg` | CSRF token for POST requests |
| `fb_dtsg_ag` | Async variant of `fb_dtsg` |
| `jazoest` | Jazoest field for forms |
| `hash` | Session hash |
| `sessionID` | Session ID |
| `clientRevision` | Used in headers / GraphQL |
| `cookieFacebook` | Original raw cookie string |

Treat it as opaque state — don't mutate keys.

---

## 12. FAQ

### General

**Q: Will my account get banned?**
Maybe. Cookie-driven automation is against Facebook's Terms of Service. Risk goes up with: high message rate, repetitive identical content, sending to strangers, mass-DMing groups, running on hosting IPs flagged by Meta. Use a throwaway account if you can; never your main personal one.

**Q: Why does the listener stop receiving messages after a while?**
Almost always because the `xs` cookie rotated. Open Facebook in your browser, copy a fresh `Cookie:` header, restart your script.

**Q: Can I run multiple accounts in the same process?**
Yes — build a separate `dataFB` for each account and instantiate one listener / sender per account. Run each `connect_mqtt()` in its own daemon thread.

**Q: Is there async / await support?**
Not yet. The codebase is synchronous (`requests`-based). Native `async`/`await` is on the roadmap for v2.3.x.

### MQTT (group chat) listener

**Q: `get_last_seq_id()` raises a KeyError.**
Your cookies are dead — re-run [§4.3](#43-verifying-a-session-is-alive).

**Q: Why does `bodyResults` only show one message at a time?**
By design — it's mutated in place. Poll it from the main thread and de-duplicate by `messageID`. For a queue-style API, switch to `listeningE2EEEvent` and use the `@on_message` decorator (it works on plain messages too).

**Q: Do I have to call `get_last_seq_id()` every run?**
Yes. The seq ID is what tells Messenger where to resume the inbox feed.

### E2EE listener / sender

**Q: `BridgeError: bridge binary not found`.**
Build it ([§10](#10-building-the-e2ee-go-bridge)) or set `FBCHAT_E2EE_BIN`.

**Q: `*DeviceStore does not implement EventBuffer (missing method AddOutgoingEvent)` when I `go build`.**
You picked up a newer `whatsmeow` that extended the interface. Add three no-op stubs (`GetOutgoingEvent`, `AddOutgoingEvent`, `DeleteOldOutgoingEvents`) to `bridge-e2ee/bridge/store.go`, or pin `whatsmeow` in `go.mod`.

**Q: `TypeError: __init__() got an unexpected keyword argument 'log_level'`.**
You added an `@attr.s` decorator on top of a class that already has a manual `__init__`. Remove the decorator. (Lesson learned the hard way.)

**Q: My standalone `_send_e2ee.api` re-pairs every run.**
Pass `e2ee_memory_only=False, device_path="./device.json"` so the bridge persists Signal keys to disk.

**Q: Will the same bridge process work for listening + sending?**
Yes — that is exactly what *Mode A* in [§6.2](#62-e2ee-messages--_send_e2eeapi) does. **Strongly recommended** — pairing handshakes are slow and pop "new device" notifications on the victim user's end.

**Q: What is `chat_jid`? I have a `threadID`, not a JID.**
The bridge speaks Signal-style JIDs (`<id>@s.whatsapp.net` for DMs, `<id>@g.us` for groups). Always lift it from the listener event:
```python
chat_jid = evt["data"]["chatJid"]
```

**Q: Can I send E2EE images / videos / voice notes from Python?**
Not yet from the wrapper — the Go side has the methods, the wrapper does not surface them. Tracking issue: open one if you need this.

### Attachments

**Q: Upload returns `attachmentID = None`.**
Either the file path is wrong or Facebook rejected the upload (size limit, content scan). Re-upload with `print(_attachments.func(...))` to see the raw response.

**Q: I uploaded an image and sent it as `typeAttachment="file"`. Now Messenger shows a broken icon.**
Always match `typeAttachment` to the actual extension — see [§7](#7-attachments--upload--send).

### Login & 2FA

**Q: 2FA login fails with the right TOTP.**
`twofa` should be the **shared secret** (e.g. `JBSWY3DPEHPK3PXP`), **not** the 6-digit code. The library uses `pyotp` to derive the code at request time.

**Q: I get `Wrong Credentials` even with correct password.**
Usually a checkpoint. Log in via browser to clear it, then retry — or switch to cookie auth.

### Project layout

**Q: Why are all module / package names prefixed with `_`?**
Convention from v1 — it makes them obviously *internal* and avoids shadowing built-in names like `messaging`. The PyPI package re-exports a public API (`fbchat_v2.dataGetHome`, `fbchat_v2.listeningEvent`, `fbchat_v2.listeningE2EEEvent`, …) without underscores.

**Q: Can I import from outside `src/`?**
Either `set PYTHONPATH=src` first, or `pip install fbchat-v2` and use `from fbchat_v2 import ...`. Don't try `from src._core...` — `src` isn't a package.

**Q: Where do I add a new feature?**
- Pure HTTP action against a Facebook endpoint → `src/_features/_facebook/` or `src/_features/_thread/`.
- Send / receive / react / upload → `src/_messaging/`.
- Session / login / low-level → `src/_core/`.

Each new module should expose a single `def func(dataFB, ...)` (or a `class api` with a single verb method) and return either `{"success": 1, "payload": {...}}` or `{"error": 1, "payload": {...}}`.

---

## 13. Author's note

> I'm in a serious relationship with laziness, but if you're feeling adventurous and want to be a contributor, **shoot me a message**! 😝
>
> — *MinhHuyDev*, last updated 12 May 2026
