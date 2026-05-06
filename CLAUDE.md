# CLAUDE.md — fbchat-v2 Codebase Guide

This file describes the structure, conventions, and key patterns of **fbchat-v2** for AI assistants (Claude, Codex, etc.) working on this repository.

---

## Project Purpose

`fbchat-v2` is an **unofficial Python library** for Facebook Messenger that authenticates as a real user account via cookies or username/password rather than using the official Graph API. It enables sending/receiving messages, managing group threads, interacting with Facebook features (posts, profiles, notifications, etc.), and listening for real-time events over MQTT/WebSocket.

> ⚠️ Since November 2024, Facebook enforces E2EE for 1-to-1 chats. Only group (thread) messages are currently readable through public endpoints. E2EE decryption for 1-to-1 messages is planned.

---

## Repository Layout

```
fbchat-v2/
├── src/                        # All Python source code lives here
│   ├── main.py                 # Entry point — minimal demo bot
│   ├── config.json             # Runtime config (cookies, prefix, admins)
│   ├── _core/                  # Layer 1 — Foundation
│   │   ├── __init__.py
│   │   ├── _facebookLogin.py   # Username/password + 2FA login
│   │   ├── _session.py         # Cookie-based session bootstrap (dataGetHome)
│   │   └── _utils.py           # Shared helpers (headers, form builder, parsers)
│   ├── _features/              # Layer 2 — Facebook & Thread features
│   │   ├── _facebook/          # Facebook-level actions
│   │   │   ├── __init__.py
│   │   │   ├── _blocking.py
│   │   │   ├── _changeBio.py
│   │   │   ├── _createPost.py
│   │   │   ├── _get_user_info.py
│   │   │   ├── _marketplace.py
│   │   │   ├── _notification.py
│   │   │   ├── _professional.py
│   │   │   ├── _registerOnProfile.py
│   │   │   └── _search.py
│   │   └── _thread/            # Group/thread management
│   │       ├── __init__.py
│   │       ├── _addAdmin.py
│   │       ├── _all_thread_data.py   # Core thread listing + seq_id
│   │       ├── _changeEmoji.py
│   │       ├── _changeNameThread.py
│   │       └── _changeNickname.py
│   └── _messaging/             # Layer 3 — Messaging
│       ├── __init__.py
│       ├── _attachments.py     # Upload attachment files
│       ├── _listening.py       # Real-time MQTT listener
│       ├── _message_requests.py
│       ├── _reactions.py
│       ├── _send.py            # Send text/attachments
│       └── _unsend.py          # Retract messages
├── language/
│   └── vi_VN.lang              # Vietnamese locale strings
├── requirements.txt
├── DOCS.md                     # API usage documentation (English)
├── README.md                   # Project overview (Vietnamese)
├── README_EN.md                # Project overview (English)
├── FLOWCHART.md                # Mermaid flow diagrams
└── CODE_OF_CONDUCT.md
```

---

## Three-Layer Architecture

The codebase is strictly split into three layers. Higher layers import from lower ones — **never the reverse**.

```
main.py
  └── _core          (session, login, utilities)
        └── _features  (Facebook & thread operations)
        └── _messaging (send, listen, reactions, attachments)
```

### Layer 1 — `_core`

| File | Purpose |
|---|---|
| `_session.py` | `dataGetHome(cookies)` — GETs `facebook.com`, scrapes `fb_dtsg`, `jazoest`, `FacebookID`, `clientRevision`, etc. Returns the `dataFB` dict used everywhere. |
| `_facebookLogin.py` | `loginFacebook(username, password, 2fa_key).main()` — POSTs to `b-graph.facebook.com/auth/login`, handles 2FA, returns cookies or error. |
| `_utils.py` | Shared helpers: `formAll()` (builds POST form), `mainRequests()` (builds request kwargs), `Headers()`, `dataSplit()`, `parse_cookie_string()`, ID generators, etc. |

### Layer 2 — `_features`

Each file exposes a single `func(dataFB, ...)` function (module-level, no class).

- **`_facebook/`** — Actions on the Facebook platform: search users, create posts, change bio, manage notifications, block/unblock, marketplace, professional mode, register on profile.
- **`_thread/`** — Group chat management: list threads, add admins, change name/emoji/nickname, export member data.

Key file: `_thread/_all_thread_data.py` — `func(dataFB)` fetches inbox threads via GraphQL batch and returns `last_seq_id` (required by the MQTT listener).

### Layer 3 — `_messaging`

| File | Purpose |
|---|---|
| `_send.py` | `api().send(dataFB, content, threadID, ...)` — POSTs to `/messaging/send/` |
| `_unsend.py` | `func(messageID, dataFB)` — POSTs to `/messaging/unsend_message/` |
| `_listening.py` | `listeningEvent(dataFB)` — connects to Facebook's MQTT broker over WSS (`edge-chat.facebook.com`), populates `self.bodyResults` on each incoming message |
| `_attachments.py` | Upload files before sending; returns `attachmentID` |
| `_reactions.py` | React to messages |
| `_message_requests.py` | Accept/decline message requests |

---

## The `dataFB` Dictionary

Almost every function accepts `dataFB` as its first argument. It is produced by `_session.dataGetHome(cookie_string)` and contains:

| Key | Description |
|---|---|
| `FacebookID` | The authenticated user's numeric Facebook ID |
| `fb_dtsg` | CSRF token required for all POST requests |
| `fb_dtsg_ag` | Async variant of the CSRF token |
| `jazoest` | Jazoest field for form submissions |
| `hash` | Session hash |
| `sessionID` | Session ID |
| `clientRevision` | Client revision number |
| `cookieFacebook` | Raw cookie string, passed to `parse_cookie_string()` |

---

## Key Utilities (`_core/_utils.py`)

| Function | Description |
|---|---|
| `formAll(dataFB, FBApiReqFriendlyName, docID, requireGraphql)` | Builds the base POST form dict. Set `requireGraphql=False` for non-GraphQL endpoints. |
| `mainRequests(url, dataForm, cookies)` | Returns a `requests.post(**...)` kwargs dict. |
| `Headers(dataForm, Host)` | Builds browser-like request headers. |
| `dataSplit(str1, str2, ..., HTML)` | Simple string split helper used to scrape values from raw HTML. |
| `parse_cookie_string(s)` | Converts `"key=val; key2=val2"` → `{"key": "val", ...}`. |
| `gen_threading_id()` | Generates Facebook-style threading IDs. |
| `generate_session_id()` / `generate_client_id()` | Random IDs for MQTT. |
| `randStr(n)` | Random alphanumeric string of length `n`. |

---

## Real-Time Listener (`_messaging/_listening.py`)

The listener uses **paho-mqtt over WebSocket/TLS** to connect to `edge-chat.facebook.com:443`.

Typical usage:
```python
from _core._session import dataGetHome
from _messaging._listening import listeningEvent

dataFB = dataGetHome(cookie_string)
listener = listeningEvent(dataFB)
listener.get_last_seq_id()   # fetches seq_id via _all_thread_data.func()
listener.connect_mqtt()      # blocking — run in a daemon thread
```

After connection, incoming messages populate `listener.bodyResults`:
```python
{
    "body": str | None,
    "timestamp": int,
    "userID": str,
    "messageID": str | None,
    "replyToID": str,   # thread_fbid or otherUserFbId
    "type": "user" | "thread",
    "attachments": {"id": ..., "url": ...}
}
```

The dict is mutated in-place; poll it from the main thread with a short `time.sleep()` loop and compare `messageID` to a cached "last seen" value to de-duplicate.

---

## Entry Point (`src/main.py`)

`main.py` is a self-contained demo bot that:
1. Loads `config.json` (creates a template if missing).
2. Calls `dataGetHome(cookies)` to build `dataFB`.
3. Instantiates `SimpleBot`, which wraps `SendAPI` and `listeningEvent`.
4. Runs the listener in a daemon thread; the main thread polls `bodyResults` every 0.3 s.
5. Dispatches prefix-based commands (`/ping`, `/help`, `/id`, `/echo`, `/search`, `/unsend`).

Run with:
```bash
export PYTHONPATH=src   # macOS/Linux
python src/main.py
```

---

## Configuration (`src/config.json`)

```json
{
  "cookies": "c_user=...; xs=...; fr=...; datr=...;",
  "prefix": "/",
  "admins": ["<facebook_numeric_id>"]
}
```

> 🔒 **Never commit `config.json`** — it contains live session cookies.

---

## Conventions

- **Module names** start with a single underscore (`_send.py`, `_utils.py`). Package dirs also start with underscore (`_core/`, `_features/`, `_messaging/`).
- **Feature modules** expose a bare `func(dataFB, ...)` function (not a class), except `_send.py` which uses `class api` and `_facebookLogin.py` which uses `class loginFacebook`.
- **Return shape**: success → `{"success": 1, ...}`, error → `{"error": 1, ...}` or `{"error": {...}}`.
- **No async/await yet** — the codebase is synchronous (`requests`-based). Full async support is on the roadmap.
- **Python ≥ 3.10** is required (uses `match`/`case` in `_all_thread_data.py`).
- **`PYTHONPATH=src`** must be set (or `sys.path` adjusted) so that `_core`, `_features`, `_messaging` are importable without a package prefix.
- **Commit style**: [Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`, `docs:`, `refactor:`, etc.
- **.gitignore** excludes `__pycache__/`, `*.py[cod]`, and should exclude `config.json`.

---

## Dependencies (`requirements.txt`)

| Package | Use |
|---|---|
| `requests` | All HTTP requests to Facebook endpoints |
| `paho-mqtt` | MQTT over WebSocket for the real-time listener |
| `attrs` | Used for `attr.ib()` counter in `_utils.formAll` and the `listeningEvent` class |
| `pyotp` | Generate TOTP codes for 2FA login |

---

## Adding New Features

1. Decide which layer owns the feature:
   - Pure HTTP action against a Facebook endpoint → `_features/_facebook/` or `_features/_thread/`.
   - Messaging action (send, react, unsend, upload) → `_messaging/`.
   - Session or auth-related → `_core/`.
2. Create a new `_myFeature.py` file in the appropriate subdirectory.
3. Expose a `func(dataFB, ...)` function (follow existing patterns).
4. Build your POST form with `formAll()` + `mainRequests()` from `_core._utils`.
5. Import and call from `main.py` or user code — `PYTHONPATH=src` is always assumed.

---

## Roadmap (as of 2026)

- [ ] Full `async`/`await` API
- [ ] E2EE decryption for 1-to-1 Messenger messages (prototype complete)
- [ ] Type hints across the entire public API
- [ ] Pluggable session storage backend
- [ ] Integration tests & CI
