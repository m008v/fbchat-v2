# fbchat-v2 - Docker deployment (fork)

[Tiếng Việt](README.md)

This directory is the fork-only part of the repository: it runs the sample bot in Docker, signs in to Facebook through a web-based browser (noVNC) and runs several accounts in one container. Most of it lives in `deploy/`, but the fork also changes some library files (see [Syncing with upstream](#-syncing-with-upstream)), so merges from the original repository can conflict in those files.

## 📂 Layout

```text
deploy/
├── docker-compose.yml          # project "fbchat-v2", volume fbchat-data
├── login/                      # Alpine + Chromium + noVNC, captures cookies then stops
│   ├── Dockerfile
│   ├── extract_cookie.py
│   └── control.py              # fb-login-ui service: browser on demand
├── bot/                        # python:3.12-alpine + statically built Go bridge
│   ├── Dockerfile
│   └── Dockerfile.dockerignore # per-Dockerfile allowlist (BuildKit), root untouched
├── multi_main.py               # multi-account runner built on SimpleBot from src/main.py
├── gateway_link.py             # omnichannel gateway link (when GATEWAY_URL is set)
├── session_keeper.py           # keeps the Facebook session fresh: saves reissued cookies
├── connection_history.py       # per-account connection history (history.json)
└── tests/                      # runner tests + contract tests against upstream
```

`Dockerfile.dockerignore` is an allowlist: a new Python file for the bot must be added both as a `!deploy/<file>` line there and to the `COPY` line in `deploy/bot/Dockerfile`, or the image will miss it.

## 🚀 Quick start

```bash
cd deploy
docker compose up -d --build
```

To run `docker compose` from the repository root without `-f`, create a root `.env` file (upstream already gitignores `.env`):

```bash
echo "COMPOSE_FILE=deploy/docker-compose.yml" >> .env
```

1. `login` opens a browser at <http://localhost:6080/vnc.html?autoconnect=1&resize=scale>. Sign in to Facebook there.
2. Once the `c_user` and `xs` cookies exist, `login` writes `/data/accounts/<ACCOUNT>/config.json` (mode `0600`, `ACCOUNT` defaults to `default`) to the volume and stops. It can take up to about 30 seconds for Chromium to flush cookies to disk; the "Aw, Snap!" screen shown at that point is expected.
3. `bot` starts after `login` succeeds and runs every account in `/data/accounts`.

## 👥 Multiple accounts

```bash
ACCOUNT=acc2 docker compose run --rm --service-ports login            # sign in an extra account acc2
docker compose restart bot                                            # load the new account
FORCE_LOGIN=1 ACCOUNT=acc2 docker compose run --rm --service-ports login  # sign in again after cookies expire
```

- All accounts share one Python process, event loop and `httpx.AsyncClient`. Each account still gets its own Go bridge process because the bridge supports a single client.
- Log lines carry the account name, for example `[acc2] [bot] ...`. Lines printed by the bridge itself are not labelled yet.
- A failing account is retried with backoff (30 seconds, doubling) without stopping the other accounts. Only a **really expired session** (Facebook reachable but the cookie no longer yields dataFB) stops after 2 attempts; network loss, bridge errors… are retried forever, at most every 2 minutes, so the account reconnects once the network is back. `dataGetHome` also returns `None` when offline, so the bot fetches `facebook.com/robots.txt` (no cookie) to tell the two apart. The counter resets when the previous run lasted 10 minutes or more.
- Since fbchat-v2 2.3.4 the library reconnects on its own after network loss (startup included) instead of raising: the bot follows the library's `reconnecting` state to move the account to `retrying` (history "Mất kết nối, thư viện đang tự nối lại"), and back to `running` when the library reports `connected` or the bridge reports an E2EE reconnect (`reconnected`, `e2eeConnected`): some drops are healed by reconnecting only the E2EE socket with no `connected` status, which once left an account stuck in `retrying` and the container `unhealthy` while it kept working (30/10/2026). Authentication failures still stop the listener and go through the retry loop above.
- Account names may contain only letters, digits, `_`, `.` and `-` (up to 64 characters, starting with a letter or digit). To remove an account, stop the bot, delete `/data/accounts/<name>` in the volume and start the bot again.

## 🩺 Healthcheck and restarts

- `multi_main.py` writes each account's state (`starting`, `running`, `retrying`, `dropped`) to `FBCHAT_HEALTH_FILE` (`/tmp/fbchat-health.json` in the image).
- The container is `healthy` only when every account is `running`; `docker compose ps` shows `unhealthy` while an account is retrying or dropped. With no accounts at all it is `healthy` only in gateway mode (`GATEWAY_URL` set); standalone still needs at least one account, otherwise the container stops right at startup.
- Keeping sessions: every request (HTTP and the E2EE bridge) uses the same browser identity (Linux, Chrome 141) instead of rotating User-Agents. Ten minutes after connecting and then daily (± 2 hours), the bot takes the current cookies from the bridge (`getCookies`), opens the Facebook home page once with them and saves the cookies Facebook hands back to `config.json` (`deploy/session_keeper.py`). It saves only when `c_user` is unchanged, `xs` is present and the home page is still signed in; it never drops keys and logs only the names of changed cookies. No need to open a browser every day: a second session (or sharing the cookie with a browser) is what Facebook tends to treat as suspicious.
- The bot uses `restart: unless-stopped`. When every account is dropped, the process keeps running (it does not exit) so Docker does not restart it and call Facebook with broken cookies again. Sign in again and run `docker compose restart bot`.

## 📊 Resources

| Service | Image | Limits | Measured |
|---|---|---|---|
| `login` | `alpine:3.22` + Chromium (~880 MB) | 1 CPU, 768 MiB | ~225-325 MiB while signing in, then stops |
| `bot` | `python:3.12-alpine` (~95 MB) | `BOT_CPUS` (default 1), `BOT_MEMORY_LIMIT` (default 512M) | ~25 MiB shared Python + 15-25 MiB per account at idle; two accounts ~60 MiB, CPU < 1% |

Raise `BOT_MEMORY_LIMIT` when adding many accounts or sending large media, because the bridge holds whole media files in memory while sending or downloading. Once signed in you can remove the login image: `docker image rm fbchat-v2-login`.

Environment variables (shell or `.env`): `ACCOUNT`, `FORCE_LOGIN`, `LOGIN_TIMEOUT` (seconds, default 900), `VNC_PASSWORD`, `BOT_ADMINS` (comma-separated IDs), `BOT_PREFIX`, `BOT_CPUS`, `BOT_MEMORY_LIMIT`.

## 🛡️ Security

- noVNC binds to `127.0.0.1` only. The Chromium profile lives on tmpfs and is discarded when the container stops.
- Chromium runs without remote debugging or automation flags; the script reads and decrypts the profile's SQLite `Cookies` file (`--password-store=basic`). Policies disable DevTools and the password manager.
- Chromium runs with `--no-sandbox` because Docker's default seccomp profile blocks its sandbox; the container is only used to open Facebook.
- The bot runs as a non-root user with a read-only root FS, `cap_drop: ALL` and `no-new-privileges`. Cookies live in the `fbchat-data` volume, not in the image or the repository.

## 🔗 Omnichannel mode (gateway)

With `GATEWAY_URL` and `GATEWAY_TOKEN` (at least 32 characters) set, `multi_main.py` forwards every customer message to the omnichannel gateway (`POST /v1/inbound`) instead of running `/ping`-style commands, and serves `POST /send` on `BOT_HTTP_PORT` (default 7002) for agent replies. Set `BOT_COMMANDS=1` to keep the commands. The code lives in `gateway_link.py`; the full stack (Libredesk + gateway + bots) lives in a separate `omnichannel/` directory.

- `thread_id` sent to the gateway: `e2ee:<chatJid>` for encrypted chats, `thread:<threadId>` for regular chats; groups are detected from `threadType`.
- Sender names come from `_get_user_info` and are cached.
- Attachments (image, video, audio, file): the bot downloads them through `downloadE2EEMedia` (encrypted chats) or `downloadMedia` (regular chats) and sends them to the gateway as base64; agent files go out through `sendE2EEImage`/`sendE2EEVideo`/`sendE2EEAudio`/`sendE2EEDocument` or `sendImage`/`sendFile`. Stickers are downloaded as images (Messenger catalog stickers in encrypted chats: the bridge resolves their URL from the `receiverFetchID`); links and locations become a one-line description. A file that cannot be downloaded (error, too large) becomes a label such as `🧩 Sticker`, `🖼️ Ảnh`, `🎬 Video` or `📎 Tệp: name`, plus the original link when a regular chat has one; the bridge reports why a sticker lookup failed in `fetchError` and the bot logs `Không lấy được sticker: ...`. Message summaries (reaction notes, quotes) use the same labels without links. Per-file limit `GATEWAY_MAX_FILE_MB` (default 20).
- E2EE kinds the bridge cannot read yet (contact cards, polls, view-once, live location...) arrive as empty messages: the bot sends the line `❓ Loại tin chưa hỗ trợ: xem trên Messenger` instead of dropping them. Empty regular messages are still skipped.
- Undecryptable E2EE messages: the whatsmeow `raw` event (`UndecryptableMessage`) carries the chat, sender and message ID; the reason is in the `error` event code 2 (see "Undecryptable E2EE messages" below). The bot waits 15 seconds (`UNDECRYPTABLE_GRACE_SECONDS`) and then sends `⚠️ Tin nhắn mã hóa không giải mã được: xem trên Messenger` into the right conversation, unless the real message with the same ID arrived meanwhile (common for group messages when the bot lacks the sender's group key: the bridge asks for a resend and the message arrives about 1 second later). The placeholder has its own ID `undecryptable-<id>`, so a real message that arrives later still gets through. Own messages and `DecryptFailMode=hide` are skipped.
- Regular (non-E2EE) messages sent while the bot was down: the bridge drops messages older than the connect time, and the sync on connect does not resend missed messages either (Messenger loads them only when a thread is opened), so they are not recovered yet. New Facebook chats are E2EE, which the bridge resyncs itself.
- A reply the bridge does not confirm (deliveryStatus UNKNOWN) still returns 200 so the gateway does not resend it and the customer does not get duplicates.

### Quoting and recalling agent replies

- `POST /send` also takes `reply_to` (messageID of a customer message): the bot sends a quoted reply (`send_e2ee_message(..., reply_to_id, reply_to_sender_jid)` or `send_message(..., reply_to_id)`), the sender JID coming from the cache of the last 4096 messages. It returns `{"ok": true, "message_ids": [...]}`.
- Agent audio in encrypted chats goes out as a **voice message** (`sendE2EEAudio` with `ptt: true`); the duration is read from the file header (m4a/mp4: the `mvhd` box, ogg opus: the last page granule), other formats send 0.
- `POST /react {account, thread_id, message_id, emoji}`: an agent reacts to a customer message through the `sendE2EEReaction` RPC (needs the original sender JID; the customer in 1-1 chats) or `sendReaction`; empty `emoji` removes, FE0F is stripped (Messenger uses ❤).
- `POST /recall {account, thread_id, message_ids}`: `unsendE2EEMessage` / `unsendMessage` through `BridgeActions`; the `messageUnsend` event of that message is not noted twice.

### Editing, customer state and messaging first

- `POST /edit {account, thread_id, message_id, text}`: `editE2EEMessage`/`editMessage`; that message's own `messageEdit` event is not noted twice.
- Customer typing/seen (`typing`, `readReceipt`, `e2eeReceipt` of type `read`, whatsmeow `ChatPresence` in `raw`) → `POST /v1/presence`; the account's own events are skipped and typing is sent at most every 3 seconds.
- `POST /resolve {account, to}`: a numeric ID or profile link (`profile.php?id=…`, `facebook.com/<id>`) → `{thread_id: "e2ee:<id>@msgr", name, avatar}`.

### Account management (/accounts)

The bot's HTTP server (same `GATEWAY_TOKEN` as `/send`) also serves routes for the Libredesk **Channel accounts** page; the gateway calls them, browsers never do:

| Route | Action |
|---|---|
| `GET /accounts` | Accounts: `name`, `state` (`starting`, `running`, `retrying`, `dropped`, `stopped`), `profile` (`uid`, `displayName`, `avatar`), `error` (last error: `session_expired` when the cookie no longer yields dataFB, sign in again; `connection` otherwise; on expiry `message` adds "Nguyên nhân: …" and `cause`: `revoked` Facebook deleted the `c_user`/`xs` cookies, `checkpoint`, `login`, `token`, `unknown`), `history` (connection history, newest first: `at`, `kind` `connected`/`manual`/`network`/`disconnected`/`platform`/`session_expired`/`decrypt`/`keycheck`, `message`, `count`/`last_at` when repeated; saved in `<account>/history.json` 0600, at most 30 entries) |
| `POST /accounts/<name>/cookie` `{"cookie": "..."}` | Internal only (the UI signs in with the browser). The cookie must contain `c_user` and `xs`; the bot runs `dataGetHome` to check it with Facebook (422 when rejected, nothing saved), then writes `config.json` (0600) and starts the account |
| `POST /accounts/<name>/restart` | Reconnect (also used after a browser sign-in) |
| `DELETE /accounts/<name>` | Stop and delete the account directory, with what was remembered for it (quotes, groups, members) and its trace files. Pending undecryptable-message notes are cancelled |

The account's own name/picture comes from `/chat/user_info`; some accounts cannot look themselves up, so the LightSpeed contact tables (`LSDeleteThenInsertContact`, `LSVerifyContactRowExists`) sent on connect fill it in. The same tables also name customers found in the contact list.

`AccountManager` (in `multi_main.py`) runs each account in its own task; stopping or reconnecting cancels the task and `SimpleBot.run()` stops the bridge. With the gateway enabled the bot also starts with no accounts and the healthcheck stays `healthy`; standalone (no `GATEWAY_URL`) still needs at least one account.

Browser sign-in uses the `fb-login-ui` service (`login/` image, `control.py` command): idle it is only the control server (~20 MiB); `POST /session {"account", "target"}` runs `extract_cookie.py` with `FORCE_LOGIN=1` (Chromium + noVNC on port 6080); `target` defaults to `facebook`, which writes cookies for fb-bot (`/data/accounts/<name>`), while `fbweb` writes them for omnichannel's Fanpage Web agent (`/fbweb/<name>/config.json`, volume `fbweb-logins`, D18), `GET /session` reports `starting` until noVNC accepts connections, then `running`, `saving` once `extract_cookie.py` saw the sign-in and closed Chromium to flush cookies, and `success` once the cookie is written; `DELETE /session` cancels. One session at a time; the Chromium profile is wiped before and after each session so the next account never inherits cookies. The control server requires `GATEWAY_TOKEN` and does not log URLs or headers. Cookie handoff (omi, one container and one volume per account, D28): with `LOGIN_HANDOFF_DIR` (tmpfs) set, the `facebook` target keeps the cookie there instead of writing the bot volume; the gateway calls `POST /session/cookie {"account"}` to take it once (deleted right after, 404 if none) and gives it to the bot container's `POST /accounts/<name>/cookie`; in this mode the `fbweb` target is taken only when `FBWEB_LOGINS_DIR` is set explicitly (omi-host mounts the clinic's Fanpage Web volume there; `/fbweb` exists in the image, and without a volume the cookie would go with the container), otherwise 400.

### Rich content and events

- Quotes: E2EE messages only carry `replyTo.messageId`, so the bot caches the last 4096 messages per account (key `account:messageId`) to send `quote` = `Name: text`.
- Stickers are downloaded as images; locations become a Google Maps link; links carry their description.
- Avatars: 1-1 chats send `thread_avatar` = the sender's `thumbSrc` (from the same lookup as the name); groups send each member's `sender_avatar` so the UI can show member avatars.
- Groups: E2EE chats with a `<id>@g.us` JID are groups. E2EE messages carry no group name, so the bot reads group names/pictures from LightSpeed tables in `raw` events (`LSDeleteThenInsertThread`, `LSSyncUpdateThreadName`, `LSSetThreadImageURL`). Those tables only name a group when Messenger syncs that group, and the bot forgets on restart, so for an E2EE group with no known name the bot asks the server through the bridge (`get_e2ee_group_info`, at most once an hour per group). If the name is still unknown it sends an empty name: the gateway keeps the group's known name, or uses `👥 Nhóm Facebook` if it never had one (never the sender's name).
- Facebook group events (rename, member added/left/removed, admin changes) are also read from LightSpeed tables (`LSSyncUpdateThreadName`, `LSAddParticipantIdToGroupThread`, `LSRemoveParticipantFromThread`, `LSUpdateThreadParticipantAdminStatus`) and become `group_event` notes. These tables double as sync data on connect, so the bot only reports changes against known state: a rename when the name differs from the known one, member adds/admin changes only once the group's member list was seen and the batch is not a full thread snapshot. Missing an event beats a burst of false notes on every restart.
- `AccountBot._forward_listener_event` intercepts `e2eeReaction`, `reaction`, `messageEdit` and `messageUnsend` (dropped by the upstream SimpleBot) and sends them to `POST /v1/event`, where they become private notes. Reactions also carry `target_ids` (messageId), `reactor_id` (who reacted, `self` for the account owner) and `reaction` (emoji, empty when removed) so the gateway shows a badge on the right message; when the message is unknown it is still a note.
- Messages whose `senderId` is the account itself (sent from another device) become `owner_message` notes; messages the bot sent through `/send` are recognised by the returned `messageId` or by matching text within 60 seconds.
- Facebook names: `/chat/user_info` first; with no profile (strangers, not friends) the bot asks Messenger's contact table through the bridge (`get_user_info`, picture included). If neither has one, the label `Facebook <id>` is used and retried after an hour.

### E2EE device state

`AccountBot` stores the E2EE device state in `/data/accounts/<name>/e2ee_device.json` (mode `0600`). Upstream keeps it in memory by default (`e2ee_memory_only=True`): every restart becomes a new E2EE device and incoming messages often fail with `E2EE message could not be decrypted or was unavailable`. Set `FBCHAT_E2EE_PERSIST=0` to restore the upstream behaviour. The file holds the account's encryption keys: do not copy it out of the volume.

#### Undecryptable E2EE messages

For every message that fails to decrypt (`error` event code 2, except `reason=unavailable`):

- It is recorded in the account history (Channel accounts page) with `kind: "decrypt"`: group or 1-1 chat, a sender device tag (first 8 hex characters of the SHA-256 of the JID, no raw ID), which ciphertext failed (session-opening, normal or group message) and the reason. If that device sent session-opening messages with `state=false` (the bridge does not store their session), the entry also gives how many. Consecutive failures from the same device are merged into one entry.
- When one sender device has 3 distinct messages fail within 24 hours, the bot alerts once through the gateway's `POST /v1/alert` (Telegram, per the Alerts page). The bridge retries each message a few times with the same ID, so the count is per message ID.

Since 03/11/2026 newer Messenger apps send Signal messages with new protobuf fields; libsignal v0.2.2 checked the MAC over a re-serialized copy, so every message from those devices failed with `bad_mac`/`no_valid_session` (session-opening messages included). The bridge uses libsignal v0.2.3, which checks the original bytes. If this pattern returns for every sender on one device, check the libsignal version before recreating the device.

`bad_mac` (mismatching MAC) can also mean the Signal session between the bot's device and one of the sender's devices is out of sync. It does not heal by itself: the bridge asks for a resend, but Messenger keeps encrypting with the old session. To fix it:

1. The sender logs out and back in to Messenger on that device (a new device means a new session).
2. If the device is unknown or several senders fail: stop the account, rename `e2ee_device.json` and start it again so the bot becomes a new E2EE device (Facebook sees one more device; messages that already failed are not recovered).

Each time E2EE connects, the history also gets a `keycheck` entry: whether the E2EE keys the server hands out for the bot's device match the keys the bot holds (and which ones differ). On a mismatch nobody can open a new session with the bot.

fb-bot logs each group sender key event (`e2eeSenderKey`) with the `[e2ee-key]` tag and only a hashed device tag: which retry a group message was, whether it carried the sender key, which device's sender key was stored. When a sender key step fails (the key cannot be stored, it arrives in a 1-1 chat, a retry request cannot be sent) the history also gets a `decrypt` entry.

Single-account mode (omi, one container and one volume per account, D28): `BOT_ACCOUNT=<name>` runs only this account, `GET /accounts` lists only it (even before it signs in), and any call for another account gets 404. Empty: every account in `/data/accounts`, as before.

Payload debugging: `FBBOT_TRACE=acc2,shop2` (comma-separated account names) writes every raw listener event, including types the bot ignores (such as call signals), to `/data/trace/<name>-<UTC time>.jsonl` (mode `0600`, at most 20 MiB per file). The file holds message content: enable it only for test accounts, then delete the file and unset the variable.

## 🔄 Syncing with upstream

The shared process for every fork in the omnichannel system (separate branch, checks, canary, re-pinning, known traps): `omnichannel/docs/UPSTREAM.md`.

The `upstream` remote points to the original repository and `origin` to the fork:

```bash
git fetch upstream
git merge upstream/main          # or: git rebase upstream/main
cd deploy && docker compose build && docker compose up -d
```

The fork does not only add files under `deploy/`: it also changes `src/_core/_utils.py`, `src/_core/_session.py`, `src/_messaging/_listening_e2ee.py`, `_attachments.py`, `_editMessage.py`, `_listening.py`, `src/main.py`, `bridge-e2ee/main.go`, `CHANGELOG.md` and `CLAUDE.md` (plus the generated copies in `src/fbchat_v2/`). Merges can conflict in these files; preview them with `git diff upstream/main -- . ':!deploy'`. The remaining risk is upstream changing an API that the code in `deploy/` relies on; to catch that, run:

```bash
pytest deploy/tests
```

Upstream touch points (checked by `test_upstream_contract_used_by_fork`):

- `src/main.py`: `SimpleBot` (parameters `prefix`, `admins`, `log_message_content`, `debug_errors`, `http_client`; methods `_queue_event`, `_forward_listener_event`), `log`, `DEFAULT_HTTP_TIMEOUT`, `is_valid_datafb`.
- `listeningE2EEEvent`: attributes `device_path`, `e2ee_memory_only`, `startup_timeout`, `wait_until_connected(timeout, require_e2ee=...)`.
- `dataGetHome(storage=...)`, `FileSessionStorage`, `set_private_file_permissions`.

Other touch points (not checked directly by the test, but a broken import fails the tests too):

- `listeningE2EEEvent.get_cookies()` (`multi_main.py`, for `session_keeper.py`).
- `_core._session._build_home_request`, `_core._utils.parse_cookie_string`, `send_get_request_async` (`session_keeper.py`, `connection_history.py`).
- `_core._console.configure_utf8_console`, `_messaging._listening_e2ee._format_exception_chain` (`multi_main.py`).
- `BridgeActions`, `_features._facebook._get_user_info` (`gateway_link.py`).

`_build_home_request` and `_format_exception_chain` are internal helpers that upstream may change without notice.
