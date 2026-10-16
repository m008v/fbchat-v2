# fbchat-v2 v2.3.1 - Cảm xúc bài viết và sửa lỗi đóng gói

> Bản `fbchat-v2==2.3.1` đã phát hành trên PyPI. Source của bản này được đồng bộ ở nhánh `main` và `pypi` khi phát hành.

`v2.3.1` thêm API thả và gỡ cảm xúc trên bài viết Facebook, bổ sung module còn thiếu trong public exports của `_features._facebook` và sửa lỗi CI/đóng gói. Request reaction cũng dùng referrer và attribution theo phiên thay cho các giá trị tĩnh cũ; thay đổi này không bảo đảm tài khoản tránh được checkpoint.

## ✨ Điểm nổi bật

### 1. Tính năng mới: Tương tác cảm xúc bài viết (`_reactionPost`)
- Thêm module `_features._facebook._reactionPost.func(dataFB, postID, typeReactions="LIKE", *, client=None)`:
  - Hỗ trợ 7 loại cảm xúc: `LIKE`, `LOVE`, `CARE` (hoặc `SUPPORT`), `HAHA`, `WOW`, `SAD` (hoặc `SORRY`), `ANGRY` (hoặc `ANGER`).
  - Gỡ cảm xúc bằng các alias `UNDO`, `UNREACT`, `NONE`.
  - Hỗ trợ định dạng chuỗi không phân biệt hoa thường (`case-insensitive`) như `"like"`, `"Love"`, `"care"`.
  - Chuẩn hóa `feedback_id`: encode ID bài viết thô thành Base64 dạng `feedback:<postID>`, giữ nguyên token feedback hợp lệ để không encode hai lần.
  - Dùng GraphQL mutation `CometUFIFeedbackReactMutation` (doc_id `27646120298312844`) của giao diện Comet.

### 2. Tối ưu Telemetry và bảo mật tài khoản
- Đổi referrer từ trang xác thực 2 bước (`/two_step_verification/two_factor/`) sang profile path `/{actor_id}`. Đây là sửa dữ liệu request, không phải cơ chế chống phát hiện bot.
- Sửa `attribution_id_v2` để dùng epoch milliseconds, `jazoest` và `actor_id` của phiên đăng nhập thay cho giá trị tĩnh.
- Bỏ payload tracking comment không dùng trong request reaction.

### 3. Đồng bộ Public Exports (`_features._facebook.__all__`)
- Bổ sung `_reactionPost`, `_archivePost`, `_deletePost` vào `__all__` của `_features._facebook.__init__.py` để export khớp với các module hiện có.

### 4. Gia cố CI / Quality Gate
- Bỏ import `random` không dùng trong `_reactionPost.py`, sửa lỗi Ruff `F401` tại bước `ruff check src tests scripts`.
- Bộ 149 test pytest đạt trên Python 3.10–3.14 khi kiểm tra bản này.

## 📖 Hướng dẫn sử dụng tính năng mới

```python
import asyncio
from _core._session import dataGetHome
from _features._facebook import _reactionPost

async def main():
    cookies = "PASTE_YOUR_COOKIES_HERE"
    dataFB = dataGetHome(cookies)

    # 1. Thả tim vào bài viết
    result_love = await _reactionPost.func(dataFB, postID="123456789012345", typeReactions="LOVE")
    print(result_love)
    # Output: {'success': 1, 'messages': 'Thả reaction thành công!'}

    # 2. Thả Haha (chấp nhận chữ thường)
    result_haha = await _reactionPost.func(dataFB, postID="123456789012345", typeReactions="haha")
    print(result_haha)

    # 3. Gỡ cảm xúc đã thả
    result_undo = await _reactionPost.func(dataFB, postID="123456789012345", typeReactions="UNREACT")
    print(result_undo)
    # Output: {'success': 1, 'messages': 'Gỡ reaction thành công!'}

asyncio.run(main())
```

## 📦 Cài đặt và Nâng cấp

Cài đúng bản `v2.3.1` từ PyPI:

```bash
python -m pip install --upgrade "fbchat-v2==2.3.1"
```

Với source checkout, các lệnh sau cập nhật nhánh `main`, không cố định ở `v2.3.1`:

```bash
git checkout main
git pull origin main
```
