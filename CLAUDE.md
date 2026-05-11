# CLAUDE.md — fbchat-v2 Codebase Guide for AI Agents

> Audience: **Claude / Codex / Copilot agents**. This file is a *map*, not a tutorial.
> Read this top-to-bottom **before** running searches. Most "where is X?" questions are answered here.

---

## TL;DR

- **What:** Unofficial Python ≥ 3.10 library that talks to Facebook Messenger as a real user (cookies, not Graph API).
- **How:** Synchronous `requests` calls to private Facebook endpoints + `paho-mqtt` listener over WebSocket. E2EE (Secret Conversations) is delegated to a Go subprocess (`bridge-e2ee/`) using whatsmeow.
- **Layout:** Strict 3 layers under `src/` — `_core` → `_features` → `_messaging`. Higher layers may import lower; **never the reverse**.
- **Convention:** Every module exposes a `func(dataFB, ...)` (or a class with one verb method). The first argument is almost always `dataFB`.
- **Run:** `set PYTHONPATH=src` (Windows) / `export PYTHONPATH=src` (POSIX), then `python src/main.py`.

---

## Repository layout (as of 2026-05)

```
fbchat-v2/
├── src/                              # All Python source
│   ├── main.py                       # Demo bot, entry point
│   ├── config.json                   # Cookies + prefix + admins (gitignored)
│   ├── _core/                        # L1: session, login, utils
│   │   ├── _session.py               # dataGetHome(cookie) → dataFB
│   │   ├── _facebookLogin.py         # User+pass+2FA login
│   │   └── _utils.py                 # formAll, mainRequests, Headers, etc.
│   ├── _features/                    # L2: actions on FB & threads
│   │   ├── _facebook/                # Profile-level actions
│   │   └── _thread/                  # Group/inbox actions
│   │       └── _all_thread_data.py   # Inbox + last_seq_id (needed by listener)
│   └── _messaging/                   # L3: send / listen / react
│       ├── _send.py                  # class api().send(...)
│       ├── _unsend.py
│       ├── _attachments.py
│       ├── _reactions.py
│       ├── _message_requests.py
│       ├── _listening.py             # Plain MQTT listener
│       └── _listening_e2ee.py        # E2EE listener (drives Go bridge)
├── bridge-e2ee/                      # Go subprocess for E2EE crypto
│   ├── main.go                       # stdio JSON-RPC loop
│   ├── go.mod                        # requires Go ≥ 1.24
│   └── bridge/                       # whatsmeow + mautrix-meta wrappers
├── build/                            # Output of `go build` (binary lives here)
│   └── fbchat-bridge-e2ee[.exe]
├── website/                          # Static docs site (index.html)
├── docs/                             # Markdown docs
├── DOCS.md / FLOWCHART.md / mindmap-mermaid.md
├── language/vi_VN.lang               # i18n strings
└── requirements.txt
```

---

## Three-layer architecture (hard rule)

```
main.py
  │
  ├─→ _core            (foundation, no internal deps)
  │
  ├─→ _features        (imports _core only)
  │     ├─ _facebook/
  │     └─ _thread/
  │
  └─→ _messaging       (imports _core + _features as needed)
        ├─ _send / _unsend / _attachments / _reactions / _message_requests
        ├─ _listening
        └─ _listening_e2ee  ──────► subprocess: build/fbchat-bridge-e2ee.exe
```

**If you find an import from `_messaging` inside `_core`, that is a bug.**

---

## The `dataFB` dictionary (single source of truth)

Produced by `_core._session.dataGetHome(cookie_string)`. Passed as **first arg** to almost every function in the codebase.

| Key              | Type | What it is                                           |
|------------------|------|------------------------------------------------------|
| `FacebookID`     | str  | Authenticated user's numeric ID                      |
| `fb_dtsg`        | str  | CSRF token for POSTs                                 |
| `fb_dtsg_ag`     | str  | Async variant of CSRF token                          |
| `jazoest`        | str  | Form jazoest field                                   |
| `hash`           | str  | Session hash                                         |
| `sessionID`      | str  | Session ID                                           |
| `clientRevision` | str  | Client revision (used in headers / GraphQL)          |
| `cookieFacebook` | str  | Raw `"k=v; k2=v2; ..."` cookie string                |

> Whenever you see `dataFB` in code, treat it as opaque state. Do **not** mutate it.

---

## `_core/_utils.py` cheat sheet

| Symbol                                                                | Purpose                                                              |
|-----------------------------------------------------------------------|----------------------------------------------------------------------|
| `formAll(dataFB, FBApiReqFriendlyName, docID, requireGraphql)`        | Build base POST form. `requireGraphql=False` for non-GraphQL routes. |
| `mainRequests(url, dataForm, cookies)`                                | Returns kwargs ready for `requests.post(**kwargs)`.                  |
| `Headers(dataForm, Host)`                                             | Browser-like headers.                                                |
| `dataSplit(s1, s2, ..., HTML)`                                        | Cheap regex-free string splitting on raw HTML.                       |
| `parse_cookie_string(s)`                                              | `"k=v; k2=v2"` → dict.                                               |
| `gen_threading_id()`                                                  | Facebook-style threading ID.                                         |
| `generate_session_id()` / `generate_client_id()`                      | Random IDs for MQTT.                                                 |
| `randStr(n)`                                                          | Random alphanumeric of length `n`.                                   |

---

## Layer 2 — `_features` conventions

Each file = one feature = one module-level function:

```python
# _features/_facebook/_changeBio.py
def func(dataFB, new_bio: str) -> dict:
    form = formAll(dataFB, "ProfileBioMutation", "<docID>", True)
    form["variables"] = json.dumps({"input": {"bio": new_bio, ...}})
    kw = mainRequests("https://www.facebook.com/api/graphql/", form, dataFB["cookieFacebook"])
    r = requests.post(**kw)
    return {"success": 1, "data": r.json()} if r.ok else {"error": 1, "raw": r.text}
```

Return shape contract:
- ✅ success → `{"success": 1, ...payload}`
- ❌ error   → `{"error": 1, ...}` or `{"error": {...}}`

`_features/_thread/_all_thread_data.py` is special: it both lists inbox threads **and** returns `last_seq_id`, which is required to seed the MQTT listener.

---

## Layer 3 — `_messaging`

| File                   | Public surface                                   | Notes                                              |
|------------------------|--------------------------------------------------|----------------------------------------------------|
| `_send.py`             | `class api`, `.send(dataFB, content, threadID)`  | POST `/messaging/send/`                            |
| `_unsend.py`           | `func(messageID, dataFB)`                        | POST `/messaging/unsend_message/`                  |
| `_attachments.py`      | `func(...)`                                      | Upload first, returns attachmentID                 |
| `_reactions.py`        | `func(...)`                                      | Add/remove reaction                                |
| `_message_requests.py` | `func(...)`                                      | Accept/decline pending requests                    |
| `_listening.py`        | `class listeningEvent(dataFB)`                   | paho-mqtt over WSS to `edge-chat.facebook.com:443` |
| `_listening_e2ee.py`   | `class listeningE2EEEvent(dataFB, **opts)`       | Subprocess bridge for Secret Conversations         |

### `_listening.listeningEvent` flow

```python
listener = listeningEvent(dataFB)
listener.get_last_seq_id()   # uses _features._thread._all_thread_data
listener.connect_mqtt()      # blocking — run in a daemon thread
# poll listener.bodyResults from main thread, dedupe by messageID
```
`bodyResults` shape:
```python
{
  "body": str | None,
  "timestamp": int,
  "userID": str,
  "messageID": str | None,
  "replyToID": str,           # thread_fbid or otherUserFbId
  "type": "user" | "thread",
  "attachments": {"id": ..., "url": ...},
}
```

### `_listening_e2ee.listeningE2EEEvent` flow

```python
listener = listeningE2EEEvent(
    dataFB,
    log_level="warn",
    e2ee_memory_only=True,         # False + device_path=... persists keys
    enable_e2ee=True,
    binary_path=None,              # auto-resolves build/fbchat-bridge-e2ee[.exe]
)

@listener.on_message
def on_msg(evt):                   # evt = {"type": "...", "data": {...}, "timestamp": ms}
    if evt["type"] == "e2eeMessage":
        listener.send_e2ee_message(
            evt["data"]["chatJid"], "pong",
            reply_to_id=evt["data"]["id"],
            reply_to_sender_jid=evt["data"]["senderJid"],
        )

listener.connect_mqtt()            # blocking
```

Event types emitted by the Go bridge: `ready`, `e2eeConnected`, `message`, `e2eeMessage`, `reaction`, `e2eeReaction`, `messageEdit`, `messageUnsend`, `typing`, `readReceipt`, `disconnected`, `error`.

Override binary path: env `FBCHAT_E2EE_BIN=...`.

---

## E2EE bridge (`bridge-e2ee/`)

Standalone Go binary that wraps `whatsmeow` + `mautrix-meta`. Speaks **line-delimited JSON-RPC** on stdin/stdout — no sockets, no IPC libs.

**Why Go, not Python?** The crypto stack (Signal Protocol — Curve25519, Double Ratchet, Sender Keys, AES-GCM — wrapped in Meta's Labyrinth/Lightspeed protobufs) is ~100k LOC. Python equivalents (`python-axolotl`, `dissononce`) have been unmaintained since 2019. Re-implementing is a security and maintenance hazard.

**Build (one time):**
```powershell
cd fbchat-v2/bridge-e2ee
git clone https://github.com/mautrix/meta.git ./meta   # required by go.mod replace directive
go mod tidy
go build -ldflags="-s -w" -o ../build/fbchat-bridge-e2ee.exe .
```

**Wire protocol:**
- Request:  `{"id": <int>, "method": "<name>", "params": {...}}\n`
- Response: `{"id": <int>, "ok": <bool>, "data": {...}|"error": "..."}\n`
- Async event: `{"event": {"type": "...", "data": {...}, "timestamp": <ms>}}\n`

**Methods currently exposed in `main.go`:** `newClient`, `connect`, `connectE2EE`, `isConnected`, `sendMessage`, `sendE2EEMessage`, `disconnect`.

**Not yet wired** (present in `bridge/` Go code but not exposed): `sendReaction`, `editMessage`, `unsendMessage`, `sendTyping`, `markRead`, `MxDownloadE2EEMedia`. To expose: add a `case "..."` to `handle(req)` in `main.go` and recompile.

> ⚠️ Code in `bridge-e2ee/bridge/*.go` originates from `meta-messenger.js` / Yumi Team and is **AGPL-3.0**. The Python wrapper does **not** statically link it — they run as separate processes — but be careful when copying snippets out.

---

## `src/main.py` (entry point)

What it does in order:
1. Loads `src/config.json` (creates a placeholder if absent).
2. `dataFB = dataGetHome(cookies)`.
3. Instantiates a `SimpleBot` wrapping `_send.api` and `_listening.listeningEvent`.
4. Spawns the listener in a daemon thread.
5. Polls `listener.bodyResults` every ~0.3 s.
6. Routes prefix-based commands: `/ping`, `/help`, `/id`, `/echo`, `/search`, `/unsend`.

Run:
```powershell
$env:PYTHONPATH = "src"
python src/main.py
```

---

## Configuration files

### `src/config.json`
```jsonc
{
  "cookies": "c_user=...; xs=...; fr=...; datr=...;",
  "prefix": "/",
  "admins": ["<facebook_numeric_id>"]
}
```
> 🔒 **Never commit `config.json`** — it contains live session cookies. It is gitignored.

### `tester.py` (workspace root, optional)
Standalone test driver for the E2EE listener. Reads cookie from env `FBCHAT_COOKIE` or `src/config.json`, hooks an auto-reply pong handler, traps Ctrl-C cleanly.

---

## Conventions you must follow

| Topic                  | Rule                                                                                                                     |
|------------------------|--------------------------------------------------------------------------------------------------------------------------|
| Module / package names | Start with `_` (`_send.py`, `_core/`).                                                                                   |
| Public function name   | `func(dataFB, ...)` per file. Exceptions: `_send.py` (`class api`), `_facebookLogin.py` (`class loginFacebook`), listener classes. |
| Return shape           | success `{"success": 1, ...}` / error `{"error": 1, ...}`.                                                               |
| Sync only              | Codebase is synchronous (`requests`). No `async/await` yet.                                                              |
| Python version         | ≥ 3.10 (uses `match/case` in `_all_thread_data.py`).                                                                     |
| Import path            | `PYTHONPATH=src`. Write `from _core._session import dataGetHome`, NOT `from src._core...`.                               |
| `attrs` decorator      | **Do NOT** add `@attr.s` to a class that defines a manual `__init__` — it silently overrides yours. (Lesson learned in `_listening_e2ee.py`.) |
| Commit style           | [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`            |
| Strings to user        | Use bilingual `class="vi"/"en"` blocks in `website/`. Keep both languages in sync.                                       |

---

## Dependencies

### Python (`requirements.txt`)
| Package      | Used for                                          |
|--------------|---------------------------------------------------|
| `requests`   | All HTTP                                          |
| `paho-mqtt`  | Real-time listener WSS                            |
| `attrs`      | `attr.ib` counter in `formAll`, listener classes  |
| `pyotp`      | TOTP for 2FA login                                |

### Go (only for E2EE bridge — `bridge-e2ee/go.mod`)
| Package                  | Used for                                |
|--------------------------|-----------------------------------------|
| `go.mau.fi/whatsmeow`    | Signal Protocol implementation          |
| `go.mau.fi/mautrix-meta` | Meta-specific protobufs / Labyrinth     |
| `go.mau.fi/util`         | Logging, helpers                        |
| `github.com/rs/zerolog`  | Structured logging                      |

---

## Adding a new feature — recipe

1. **Pick the layer**:
   - Pure HTTP action against an FB endpoint → `_features/_facebook/` or `_features/_thread/`.
   - Send / receive / react → `_messaging/`.
   - Session, login, low-level → `_core/`.
2. **Create `_myFeature.py`** in that subdirectory.
3. **Define `def func(dataFB, ...) -> dict:`** following the return-shape contract.
4. Build POST with `formAll()` + `mainRequests()`. Use `requests.post(**kw)`.
5. Add a usage block in `DOCS.md` and (if user-facing) a card in `website/index.html`.
6. Commit with `feat: <short imperative summary>`.

---

## Common gotchas (real bugs we hit)

| Symptom                                                                           | Cause / Fix                                                                                                              |
|-----------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| `TypeError: __init__() got an unexpected keyword argument 'log_level'`            | `@attr.s` on a class with a manual `__init__`. Remove `@attr.s` (and its `attr.ib(...)` field defaults).                 |
| `*DeviceStore does not implement EventBuffer (missing method AddOutgoingEvent)`   | whatsmeow extended the interface. Add no-op stubs `GetOutgoingEvent`, `AddOutgoingEvent`, `DeleteOldOutgoingEvents` to `bridge-e2ee/bridge/store.go`. |
| `BridgeError: bridge binary not found`                                            | Build the Go binary (see "E2EE bridge") or set `FBCHAT_E2EE_BIN`.                                                        |
| Listener silently dies after a while                                              | Cookie expired (`xs` rotated). Re-fetch from browser.                                                                    |
| `ImportError: attempted relative import with no known parent package`             | `PYTHONPATH=src` was not set.                                                                                            |

---

## Documentation surface

- `README.md` / `README_EN.md` — project overview (VI / EN).
- `DOCS.md` — full Python API reference (EN).
- `FLOWCHART.md` — Mermaid diagrams of message flows.
- `mindmap-mermaid.md` — feature mindmap.
- `website/index.html` — bilingual static docs (sidebar `data-section` controls visible section).
- `bridge-e2ee/README.md` — Go bridge build & protocol docs.

When updating user-facing docs, update **both** `website/index.html` (preferred, bilingual) and the relevant `DOCS.md` / `README*.md`.

---

## Roadmap (as of 2026-05)

- [x] **E2EE listener for Secret Conversations** (via Go bridge) — shipped 2026-03-24.
- [ ] Expose remaining bridge methods (`sendReaction`, `editMessage`, `markRead`, …) in `main.go`.
- [ ] Auto-respawn `_BridgeProcess` on subprocess crash.
- [ ] Full `async`/`await` API for the Python side.
- [ ] Type hints across the entire public API.
- [ ] Pluggable session storage backend.
- [ ] Integration tests & CI.

---

## Quick reference for AI agents

| When the user says…                | Do…                                                                                                                            |
|------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| "Add a feature to send X"          | Create `src/_messaging/_X.py` with `class api` or `func(dataFB, ...)`. Wire in `main.py` if part of the demo bot.              |
| "Listener doesn't see 1-1 messages" | Switch them to `_listening_e2ee.listeningE2EEEvent` — 1-1 is E2EE since 2024-11.                                              |
| "Build the bridge"                 | `cd bridge-e2ee && git clone https://github.com/mautrix/meta.git ./meta && go mod tidy && go build -o ../build/fbchat-bridge-e2ee.exe .` |
| "Update the docs"                  | Edit `website/index.html` (bilingual `vi`/`en` spans) **and** the matching `DOCS.md` section.                                  |
| "Refactor `_utils.py`"             | Be conservative — every feature module imports from it. Run a workspace grep before changing signatures.                       |
