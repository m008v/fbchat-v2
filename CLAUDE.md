# fbchat-v2 — contributor context

This file is implementation context for coding agents and contributors. User-facing examples live in `README.md` and `DOCS.md`.

## Architecture

```text
src/
├── _core/
│   ├── _http.py          # shared sync/async httpx transport
│   ├── _utils.py         # Facebook forms, JSON parsing, cookie and ID helpers
│   ├── _session.py       # dataGetHome -> dataFB
│   ├── _facebookLogin.py # credential login and local TOTP
│   └── _storage.py       # session storage abstraction
├── _features/
│   ├── _facebook/        # account/profile/Marketplace operations
│   └── _thread/          # group/thread operations and inbox sequence ID
├── _messaging/           # send, listener, LS actions, E2EE, media
└── main.py               # async-first example bot
bridge-e2ee/               # Go line-delimited JSON-RPC subprocess
tests/                     # pytest suite
```

## Async contract

- Current documentation and new application code use suffix-free async public APIs.
- HTTP async functions must call `httpx.AsyncClient`; wrapping sync HTTP in `asyncio.to_thread()` is not acceptable.
- `paho-mqtt` and bridge queue waits are blocking libraries. Their async adapters may use a dedicated worker thread.
- Accept an optional `client: httpx.AsyncClient` when a feature benefits from connection-pool reuse and test injection.
- Sync APIs remain compatibility shims and must not be called from a coroutine.

```python
data_fb = await dataGetHome(cookie)
result = await feature.func(data_fb, ...)
```

## `dataFB` contract

Required fields used across the project:

```python
{
    "fb_dtsg": "...",
    "jazoest": "...",
    "sessionID": "...",
    "FacebookID": "1000...",
    "clientRevision": "...",
    "cookieFacebook": "c_user=...; xs=...; ...",
}
```

Treat the entire object as secret. Tests use synthetic values from `tests/conftest.py`.

## HTTP implementation

Build forms with `formAll()` and send them through `post_form_json_async()` or `send_request_async()`. The transport:

- copies caller kwargs instead of mutating them;
- uses finite timeouts and TLS verification;
- supports caller-owned clients;
- strips `for (;;);` only when requested;
- returns `httpx.Response` or parsed JSON, depending on helper.

Do not add `requests`, disable TLS, print request forms, or catch all exceptions without preserving a useful error.

## Listener lifecycle

`listeningEvent.__init__()` performs no network I/O. `connect_mqtt()` starts the MQTT loop, `get_message()` consumes a bounded queue, and `disconnect()` ends it.

```python
listener = listeningEvent(data_fb)
task = asyncio.create_task(listener.connect_mqtt())
try:
    event = await listener.get_message(timeout=30)
finally:
    await listener.disconnect()
    await task
```

Never recursively call connection setup from an MQTT callback. Signal an outer reconnect loop instead.

## E2EE bridge

Python starts `fbchat-bridge-e2ee(.exe)` and exchanges one JSON object per line over stdin/stdout. `_BridgeProcess.call()` adapts the blocking response queue. `BridgeActions` must provide matching `*_sync` and suffix-free async methods.

Auto-download rules:

- GitHub Releases only over HTTPS;
- reject unexpected initial hosts;
- maximum 200 MiB;
- stream into a temporary file and atomically replace the target;
- verify GitHub's SHA-256 digest when present.

## Login security

- `FBCHAT_APP_ACCESS_TOKEN` is required for credential login and never belongs in source.
- TOTP uses local `pyotp`; never send a shared secret to `2fa.live` or another service.
- Never log password, login form, cookies, OTP, or access token.
- Preserve handling for known 2FA continuation subcodes `1348162` and `1348023`, but do not claim live validation without a real controlled account test.

## Feature conventions

- Separate `_build_*`, transport call, and `_parse_*` so parsers can be unit-tested.
- Validate empty IDs, enum-like inputs, coordinates, price, and required files before I/O.
- Do not silently ignore an argument. Raise a clear exception when the server schema is not implemented.
- Parse missing or changed response fields without leaking the full request or credentials.
- Keep Vietnamese strings valid UTF-8 with full diacritics.

## Validation

Run before every commit:

```powershell
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
python -m compileall -q src tests
git diff --check
go test ./...
```

Also scan tracked text for invalid UTF-8, U+FFFD, NUL, and common mojibake markers. Do not rewrite valid Vietnamese merely because PowerShell rendered it with the wrong terminal encoding.

## Git rules

- Keep `src/config.json` local; only `src/config.example.json` is tracked.
- Do not commit `.vbsec-tmp`, security scan output, build artifacts, cookies, or tokens.
- Use Conventional Commits with scope, for example `refactor(async): ...`.
- Update relevant README files when behavior changes.
