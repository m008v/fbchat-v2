# `_features` — nghiệp vụ Facebook async

Tầng này nhận `dataFB` từ `_core` và thực hiện nghiệp vụ tài khoản hoặc quản lý thread. Tài liệu chỉ dùng API async; hàm sync giữ lại cho tương thích.

## Facebook

| Module | API async | Ghi chú |
|---|---|---|
| `_changeBio` | `func(dataFB, newContents, uploadPost=False)` | Đổi bio |
| `_createPost` | `func(dataFB, newContents, attachmentID=None)` | Attachment chưa hỗ trợ sẽ fail rõ ràng |
| `_professional` | `func(dataFB, statusBusiness)` | Nhận bool hoặc on/off, bật/tắt |
| `_search` | `func(dataFB, keywordSearch)` | Tối đa 5 kết quả đã loại trùng |
| `_blocking` | `func(dataFB, idUser, choiceInteract)` | `block` / `unblock` |
| `_registerOnProfile` | `func(dataFB, newName, newUsername)` | Tạo profile bổ sung |
| `_notification` | `func(dataFB)` | Lấy thông báo |
| `_get_user_info` | `func(dataFB, userID)` | Lấy thông tin profile |
| `_marketplace` | `createItem(...)` | Validate category, giá, ảnh và tọa độ |
| `_marketplace` | `getInformationProductItemMarketPlace(...)` | Chi tiết sản phẩm |

```python
import asyncio
import httpx

from _core._session import dataGetHome
from _features._facebook import _blocking, _notification, _search


async def main() -> None:
    data_fb = await dataGetHome("c_user=...; xs=...; fr=...; datr=...;")
    if data_fb is None:
        raise RuntimeError("Session không hợp lệ.")

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

## Thread

| Module | API async |
|---|---|
| `_all_thread_data` | `func(dataFB)` và `features(...)` |
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

## Quy tắc

- Validate đầu vào trước khi gửi request.
- Dùng helper `post_form_json_async`; không import `requests`.
- Cho phép inject `httpx.AsyncClient` bằng `client=`.
- Không giả thành công khi response thiếu `data` hoặc có `errors`.
- Không âm thầm bỏ tham số chưa hỗ trợ.
- `features()` chỉ parse dữ liệu trong RAM nên hoàn tất ngay, không cần worker thread.
