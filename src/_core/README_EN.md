# `_core` — async foundation

`_core` owns HTTP transport, Facebook sessions, credential login, storage, and shared utilities. Feature modules should not import `requests` or create ad-hoc transports.

## Modules

| File | Responsibility |
|---|---|
| `_http.py` | `httpx.Client` / `httpx.AsyncClient`, timeouts, request normalization |
| `_utils.py` | Facebook forms, JSON parsing, cookies, IDs, request helpers |
| `_session.py` | homepage tokens and the `dataFB` object |
| `_facebookLogin.py` | credential login and local 2FA |
| `_storage.py` | cookie/session storage abstraction |
| `_types.py` | shared types |

## Build `dataFB`

```python
import asyncio

from _core._session import dataGetHome_async


async def main() -> None:
    data_fb = await dataGetHome_async("c_user=...; xs=...; fr=...; datr=...;")
    if data_fb is None:
        raise RuntimeError("Could not create a session.")
    print(data_fb["FacebookID"])


asyncio.run(main())
```

Important fields are `fb_dtsg`, `jazoest`, `sessionID`, `FacebookID`, `clientRevision`, and `cookieFacebook`. Treat the entire object as sensitive.

## Shared transport

```python
import httpx

from _core._utils import formAll, post_form_json_async

form = formAll(data_fb, "FriendlyName", "123456")
async with httpx.AsyncClient(timeout=30) as client:
    payload = await post_form_json_async(
        "https://www.facebook.com/api/graphql/",
        form,
        data_fb["cookieFacebook"],
        client=client,
    )
```

`post_form_json_async` calls `raise_for_status()`, optionally strips the `for (;;);` prefix, and never mutates the caller's request dictionary. Use `send_request_async` when raw `httpx.Response` access is required.

## Login and 2FA

```python
from _core._facebookLogin import loginFacebook

login = loginFacebook(
    "email@example.com",
    "password",
    AuthenticationGoogleCode="JBSWY3DPEHPK3PXP",
)
result = await login.main_async()
```

`FBCHAT_APP_ACCESS_TOKEN` must be configured. The TOTP secret is evaluated locally with `pyotp`; a direct 6–8 digit OTP is also accepted. The module does not call `2fa.live`, hardcode an app secret, or print password-bearing request forms.

## Development rules

- I/O features must expose a true `_async` API backed by `httpx.AsyncClient`.
- Accept `client=` for testing and connection-pool reuse.
- Use finite timeouts, call `raise_for_status()`, and handle missing response fields.
- Never disable TLS verification.
- Never log `dataFB`, cookies, passwords, OTP secrets, or access tokens.
- Sync APIs are compatibility layers; do not call them inside an event loop.

## Troubleshooting

| Symptom | Check |
|---|---|
| `dataGetHome_async()` returns `None` | Expired cookie, network failure, or changed HTML markers |
| HTTP 401/403 | Invalid cookie/session tokens |
| Login returns code `-4` | Missing `FBCHAT_APP_ACCESS_TOKEN` |
| Login asks for 2FA | Provide a TOTP secret or current OTP |
| JSON parse failure | Facebook changed the endpoint, prefix, or response schema |
