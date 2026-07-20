"""
Đường dẫn file:
  src/_core/_types.py

Mục đích:
  - Cung cấp module cho thư viện fbchat-v2 (phiên bản async).
  - Comment đầu file giúp developer dễ dàng theo dõi vị trí, luồng xử lý và dữ liệu của tính năng.

Cách hoạt động:
  - Nạp dependency/guard cần thiết, thực hiện các async HTTP requests tới API nội bộ hoặc GraphQL của Facebook.
  - Các thao tác request đều phải thông qua httpx.AsyncClient và module _core._utils để bảo đảm an toàn kết nối.
  - Payload gửi đi/nhận về được xử lý JSON cẩn thận, bắt lỗi try-except đầy đủ để tránh crash hệ thống.

File liên quan:
  - src/main.py và các entrypoint khác.
  - Phụ thuộc vào _core._session, _core._utils để khởi tạo và thao tác HTTP.

Author: @m008v (MinhHuyDev)
"""

"""
Shared type definitions cho toàn bộ fbchat-v2 codebase.

Cung cấp TypedDict và type aliases cho các cấu trúc dữ liệu phổ biến:
- DataFB: Session data từ Facebook
- SuccessResponse / ErrorResponse: Chuẩn hoá return shape
- RequestKwargs: Cấu trúc dict cho HTTP transport dùng chung
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class DataFB(TypedDict):
    """Session data trả về từ ``dataGetHome()``.

    Chứa tất cả thông tin session cần thiết để gọi Facebook API.
    """

    fb_dtsg: str
    fb_dtsg_ag: str
    jazoest: str
    hash: str
    sessionID: str
    FacebookID: str
    clientRevision: str
    cookieFacebook: str


class SuccessResponse(TypedDict):
    """Chuẩn response khi thành công — ``{"success": 1, ...}``."""

    success: int  # always 1
    payload: NotRequired[dict[str, Any]]
    messages: NotRequired[str]
    data: NotRequired[dict[str, Any]]


class ErrorResponse(TypedDict):
    """Chuẩn response khi lỗi — ``{"error": 1, ...}``."""

    error: int  # always 1
    payload: NotRequired[dict[str, Any]]
    messages: NotRequired[str]


class RequestKwargs(TypedDict):
    """Cấu trúc dict trả về từ ``mainRequests()`` cho HTTP transport dùng chung."""

    headers: dict[str, str]
    timeout: int
    url: str
    data: dict[str, Any]
    cookies: dict[str, str]
    verify: bool


class LoginSuccessPayload(TypedDict):
    """Payload khi đăng nhập thành công."""

    setCookies: str
    accessTokenFB: str
    cookiesKeyValueList: NotRequired[list[dict[str, Any]]]


class LoginErrorPayload(TypedDict):
    """Payload khi đăng nhập thất bại."""

    title: str
    description: str
    error_subcode: int | None
    error_code: int | None
    fbtrace_id: str | None


class AttachmentResult(TypedDict):
    """Kết quả upload attachment."""

    attachmentID: str
    attachmentUrl: str
    attachmentType: str
    attachmentDataSend: dict[str, Any]
