# `_features` — async Facebook business features

This layer receives `dataFB` from `_core` and implements account or thread-management operations. Documentation uses async APIs; sync functions remain for compatibility.

## Facebook

| Module | Async API | Notes |
|---|---|---|
| `_changeBio` | `func_async(dataFB, newContents, uploadPost=False)` | Update bio |
| `_createPost` | `func_async(dataFB, newContents, attachmentID=None)` | Unsupported attachments fail explicitly |
| `_professional` | `func_async(dataFB, statusBusiness)` | Accepts bool or on/off strings |
| `_search` | `func_async(dataFB, keywordSearch)` | Up to 5 deduplicated results |
| `_blocking` | `func_async(dataFB, idUser, choiceInteract)` | `block` / `unblock` |
| `_registerOnProfile` | `func_async(dataFB, newName, newUsername)` | Create an additional profile |
| `_notification` | `func_async(dataFB)` | Fetch notifications |
| `_get_user_info` | `func_async(dataFB, userID)` | Fetch profile details |
| `_marketplace` | `createItem_async(...)` | Validates category, price, photos, and coordinates |
| `_marketplace` | `getInformationProductItemMarketPlace_async(...)` | Product details |

```python
import asyncio
import httpx

from _core._session import dataGetHome_async
from _features._facebook import _blocking, _notification, _search


async def main() -> None:
    data_fb = await dataGetHome_async("c_user=...; xs=...; fr=...; datr=...;")
    if data_fb is None:
        raise RuntimeError("Invalid session.")

    async with httpx.AsyncClient(timeout=30) as client:
        notifications, users = await asyncio.gather(
            _notification.func_async(data_fb, client=client),
            _search.func_async(data_fb, "m008v", client=client),
        )
        blocked = await _blocking.func_async(
            data_fb, "100012345678", "block", client=client
        )
    print(notifications, users, blocked)


asyncio.run(main())
```

## Thread management

| Module | Async API |
|---|---|
| `_all_thread_data` | `func_async(dataFB)` and `features_async(...)` |
| `_changeNameThread` | `func_async(dataFB, threadID, newNameThread)` |
| `_changeEmoji` | `func_async(dataFB, threadID, newEmoji)` |
| `_addAdmin` | `func_async(dataFB, threadID, idUser, statusChoice=True)` |
| `_changeNickname` | `func_async(dataFB, threadID, idUser, NewNickname)` |

```python
from _features._thread import _addAdmin, _all_thread_data, _changeEmoji

threads = await _all_thread_data.func_async(data_fb)
details = await _all_thread_data.features_async(
    threads["dataGet"], "thread-id", "threadInfomation"
)
await _addAdmin.func_async(data_fb, "thread-id", "user-id", statusChoice=False)
await _changeEmoji.func_async(data_fb, "thread-id", "🔥")
```

## Rules

- Validate inputs before sending a request.
- Use `post_form_json_async`; never import `requests`.
- Accept an injected `httpx.AsyncClient` through `client=`.
- Do not report success when responses omit `data` or contain `errors`.
- Do not silently ignore unsupported arguments.
- `features_async()` only parses in-memory data and completes immediately without a worker thread.
