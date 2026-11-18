# Thao tác Facebook và quản lý nhóm

[Bắt đầu](../getting-started/quickstart.md) · [Tin nhắn thường](../messaging/standard.md) · [E2EE](../messaging/e2ee.md) · [Facebook](facebook-actions.md) · [Tra nhanh](../recipes/cheatsheet.md)

Trong trang này:

- [Tính năng Facebook](#tính-năng-facebook)
- [Quản lý thread](#quản-lý-thread)

Các ví dụ dùng `data_fb` từ [quickstart](../getting-started/quickstart.md).
Kiểm tra user ID, post ID và thread ID trước khi gọi API thay đổi dữ liệu.
Đổi quyền admin, block user, xóa hoặc lưu trữ bài đều tác động lên tài khoản thật.

## Tính năng Facebook

Mọi API trong bảng là coroutine và phần lớn nhận optional keyword-only `client: httpx.AsyncClient`.

| Module | Chữ ký rút gọn | Mục đích |
|---|---|---|
| `_changeBio` | `func(dataFB, newContents, uploadPost=False)` | Đổi bio |
| `_createPost` | `func(dataFB, newContents, attachmentID=None)` | Tạo bài timeline |
| `_archivePost` | `func(dataFB, postID, typePost="my_post")` | Lưu trữ bài viết |
| `_deletePost` | `func(dataFB, postID, typePost="my_post")` | Xóa bài viết (vào thùng rác) |
| `_professional` | `func(dataFB, statusBusiness=None)` | Bật/tắt Professional mode |
| `_search` | `func(dataFB, keywordSearch)` | Tìm user, tối đa 5 kết quả đã loại trùng |
| `_blocking` | `func(dataFB, idUser, choiceInteract)` | `block` hoặc `unblock` |
| `_registerOnProfile` | `func(dataFB, newName, newUsername)` | Tạo profile bổ sung |
| `_notification` | `func(dataFB)` | Lấy notification |
| `_get_user_info` | `func(dataFB, userID)` | Lấy thông tin user |
| `_marketplace` | `createItem(...)` | Đăng sản phẩm |
| `_marketplace` | `getInformationProductItemMarketPlace(...)` | Lấy chi tiết sản phẩm |

Ví dụ workflow có connection pool:

```python
import httpx

from fbchat_v2._features._facebook import _blocking, _get_user_info, _search

async with httpx.AsyncClient(timeout=30) as client:
    search = await _search.func(data_fb, "m008v", client=client)
    info = await _get_user_info.func(
        data_fb,
        "100012345678",
        client=client,
    )
    blocked = await _blocking.func(
        data_fb,
        "100012345678",
        "block",
        client=client,
    )
```

`_createPost` chưa có schema Composer ổn định cho attachment. Truyền `attachmentID` sẽ raise `NotImplementedError`, tránh trường hợp caller tưởng ảnh đã được đăng trong khi module âm thầm bỏ qua.

`_archivePost` sử dụng `useCometArchivePostMutation` để chuyển bài viết vào kho lưu trữ (Archive). Cơ chế tham số tương tự `_deletePost`.

`_deletePost` dùng `useCometTrashPostMutation` để đưa bài viết vào thùng rác, không xóa vĩnh viễn. Tham số `typePost` (`"my_post"` hoặc `"others"`) quyết định định dạng ID Base64 mà Facebook yêu cầu.

Marketplace validate category, tên, giá không âm, danh sách ảnh và tọa độ seller trước request.


## Quản lý thread

| Module | API |
|---|---|
| `_all_thread_data` | `await func(dataFB, client=...)` |
| `_all_thread_data` | `await features(dataGet, threadID, commandUse)` |
| `_changeNameThread` | `await func(dataFB, threadID, newNameThread, client=...)` |
| `_changeEmoji` | `await func(dataFB, threadID, newEmoji, client=...)` |
| `_addAdmin` | `await func(dataFB, threadID, idUser, statusChoice=True, client=...)` |
| `_changeNickname` | `await func(dataFB, threadID, idUser, NewNickname, client=...)` |

```python
from fbchat_v2._features._thread import (
    _addAdmin,
    _all_thread_data,
    _changeEmoji,
    _changeNameThread,
    _changeNickname,
)

threads = await _all_thread_data.func(data_fb)
if threads.get("error"):
    raise RuntimeError(threads)

info = await _all_thread_data.features(
    threads["dataGet"],
    "thread-id",
    "threadInfomation",
)

await _changeNameThread.func(data_fb, "thread-id", "Tên mới")
await _changeEmoji.func(data_fb, "thread-id", "🔥")
await _changeNickname.func(data_fb, "thread-id", "user-id", "Biệt danh")
await _addAdmin.func(data_fb, "thread-id", "user-id", statusChoice=True)
await _addAdmin.func(data_fb, "thread-id", "user-id", statusChoice=False)
```

`statusChoice=False` thực sự gỡ admin. `features()` parse dữ liệu đã tải trong RAM và giữ coroutine để hợp đồng gọi nhất quán.
