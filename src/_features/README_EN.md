# `_features` - async Facebook business features

This layer receives `dataFB` from `_core` and implements account or thread-management operations. Documentation uses suffix-free async APIs; blocking helpers, when present, are internal compatibility paths.

## Facebook

| Module | Async API | Notes |
|---|---|---|
| `_changeBio` | `func(dataFB, newContents, uploadPost=False)` | Update bio |
| `_createPost` | `func(dataFB, newContents, attachmentID=None)` | Unsupported attachments fail explicitly |
| `_professional` | `func(dataFB, statusBusiness)` | Accepts bool or on/off strings |
| `_search` | `func(dataFB, keywordSearch)` | Up to 5 deduplicated results |
| `_blocking` | `func(dataFB, idUser, choiceInteract)` | `block` / `unblock` |
| `_registerOnProfile` | `func(dataFB, newName, newUsername)` | Create an additional profile |
| `_notification` | `func(dataFB)` | Fetch notifications |
| `_get_user_info` | `func(dataFB, userID)` | Fetch profile details |
| `_marketplace` | `createItem(...)` | Validates category, price, photos, and coordinates |
| `_marketplace` | `getInformationProductItemMarketPlace(...)` | Product details |

```python
import asyncio
import httpx

from _core._session import dataGetHome
from _features._facebook import _blocking, _notification, _search


async def main() -> None:
    data_fb = await dataGetHome("c_user=...; xs=...; fr=...; datr=...;")
    if data_fb is None:
        raise RuntimeError("Invalid session.")

    async with httpx.AsyncClient(timeout=30) as client:
        notifications, users = await asyncio.gather(
            _notification.func(data_fb, client=client),
            _search.func(data_fb, "m008v", client=client),
        )
        blocked = await _blocking.func(
            data_fb, "100012345678", "block", client=client
        )
    print(notifications, users, blocked)


asyncio.run(main())
```

## Thread management

| Module | Async API |
|---|---|
| `_all_thread_data` | `func(dataFB)` and `features(...)` |
| `_changeNameThread` | `func(dataFB, threadID, newNameThread)` |
| `_changeEmoji` | `func(dataFB, threadID, newEmoji)` |
| `_addAdmin` | `func(dataFB, threadID, idUser, statusChoice=True)` |
| `_changeNickname` | `func(dataFB, threadID, idUser, NewNickname)` |

```python
from _features._thread import _addAdmin, _all_thread_data, _changeEmoji

threads = await _all_thread_data.func(data_fb)
details = await _all_thread_data.features(
    threads["dataGet"], "thread-id", "threadInfomation"
)
await _addAdmin.func(data_fb, "thread-id", "user-id", statusChoice=False)
await _changeEmoji.func(data_fb, "thread-id", "🔥")
```

## Rules

- Validate inputs before sending a request.
- Use `post_form_json_async` or `send_request_async`; do not create ad-hoc transports.
- Accept an injected `httpx.AsyncClient` through `client=`.
- Do not report success when responses omit `data` or contain `errors`.
- Do not silently ignore unsupported arguments.
- `features()` only parses in-memory data and completes immediately without a worker thread.
