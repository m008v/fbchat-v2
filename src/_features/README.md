# `_features` — nghiệp vụ Facebook async

Tầng này nhận `dataFB` từ `_core` và thực hiện nghiệp vụ tài khoản hoặc quản lý thread. Tài liệu chỉ dùng API async; hàm sync giữ lại cho tương thích.

## Facebook

| Module | API async | Ghi chú |
|---|---|---|
| `_changeBio` | `func_async(dataFB, newContents, uploadPost=False)` | Đổi bio |
| `_createPost` | `func_async(dataFB, newContents, attachmentID=None)` | Attachment chưa hỗ trợ sẽ fail rõ ràng |
| `_professional` | `func_async(dataFB, statusBusiness)` | Nhận bool hoặc on/off, bật/tắt |
| `_search` | `func_async(dataFB, keywordSearch)` | Tối đa 5 kết quả đã loại trùng |
| `_blocking` | `func_async(dataFB, idUser, choiceInteract)` | `block` / `unblock` |
| `_registerOnProfile` | `func_async(dataFB, newName, newUsername)` | Tạo profile bổ sung |
| `_notification` | `func_async(dataFB)` | Lấy thông báo |
| `_get_user_info` | `func_async(dataFB, userID)` | Lấy thông tin profile |
| `_marketplace` | `createItem_async(...)` | Validate category, giá, ảnh và tọa độ |
| `_marketplace` | `getInformationProductItemMarketPlace_async(...)` | Chi tiết sản phẩm |

```python
import asyncio
import httpx

from _core._session import dataGetHome_async
from _features._facebook import _blocking, _notification, _search


async def main() -> None:
    data_fb = await dataGetHome_async("c_user=...; xs=...; fr=...; datr=...;")
    if data_fb is None:
        raise RuntimeError("Session không hợp lệ.")

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

## Thread

| Module | API async |
|---|---|
| `_all_thread_data` | `func_async(dataFB)` và `features_async(...)` |
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

## Quy tắc

- Validate đầu vào trước khi gửi request.
- Dùng helper `post_form_json_async`; không import `requests`.
- Cho phép inject `httpx.AsyncClient` bằng `client=`.
- Không giả thành công khi response thiếu `data` hoặc có `errors`.
- Không âm thầm bỏ tham số chưa hỗ trợ.
- `features_async()` chỉ parse dữ liệu trong RAM nên hoàn tất ngay, không cần worker thread.
